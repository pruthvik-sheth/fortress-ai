import os
import re
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse
import httpx
import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Egress Gateway", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment configuration
PORT = int(os.getenv("PORT", "9000"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

# Initialize Anthropic client
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

# In-memory storage for behavior baselines and quarantined agents
agent_baselines: Dict[str, Dict[str, Any]] = {}
quarantined_agents: set = set()
incidents: List[Dict[str, Any]] = []

# Denylist domains
DENYLIST_DOMAINS = {
    "pastebin.com",
    "filebin.net", 
    "ipfs.io",
    "0bin.net",
    "hastebin.com"
}

class ProxyRequest(BaseModel):
    agent_id: str
    url: str
    method: str = "GET"
    body: str = ""
    purpose: str = ""

class LLMRequest(BaseModel):
    agent_id: str
    purpose: str
    user_text: str

class ProxyResponse(BaseModel):
    status: str
    reason: Optional[str] = None
    score: Optional[int] = None
    upstream: Optional[Dict[str, Any]] = None

def log_event(filename: str, event_data: Dict[str, Any]):
    """Append event to specified log file."""
    try:
        os.makedirs("data", exist_ok=True)
        with open(f"data/{filename}", "a") as f:
            f.write(json.dumps(event_data) + "\n")
    except Exception as e:
        print(f"Logging error: {e}")

def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        return urlparse(url).netloc.lower()
    except:
        return ""

def detect_secrets_in_text(text: str) -> List[str]:
    """Detect secrets/PII in text."""
    secrets_found = []
    
    # AWS keys
    if re.search(r'AKIA[0-9A-Z]{16}', text):
        secrets_found.append("aws_access_key")
    
    # Generic API keys
    if re.search(r'(?:api[_-]?key|apikey|token)["\s]*[:=]["\s]*([a-zA-Z0-9_-]{20,})', text, re.IGNORECASE):
        secrets_found.append("api_key")
    
    # PEM certificates
    if re.search(r'-----BEGIN [A-Z ]+-----', text):
        secrets_found.append("pem_certificate")
    
    # SSN pattern
    if re.search(r'\b\d{3}-\d{2}-\d{4}\b', text):
        secrets_found.append("ssn")
    
    return secrets_found

def detect_encoded_blob(text: str) -> bool:
    """Detect large base64-like encoded blobs."""
    base64_pattern = r'[A-Za-z0-9+/]{200,}={0,2}'
    return bool(re.search(base64_pattern, text))

def update_agent_baseline(agent_id: str, url: str, method: str, body_size: int):
    """Update behavior baseline for an agent."""
    if agent_id not in agent_baselines:
        agent_baselines[agent_id] = {
            "sample_count": 0,
            "payload_sizes": [],
            "request_times": [],
            "domains": set(),
            "apis": set(),
            "avg_payload": 0,
            "max_payload": 0,
            "avg_freq": 0,
            "avg_hour": 12,  # Default to noon
            "known_domains": set(),
            "known_apis": set()
        }
    
    baseline = agent_baselines[agent_id]
    baseline["sample_count"] += 1
    baseline["payload_sizes"].append(body_size)
    baseline["request_times"].append(time.time())
    
    domain = extract_domain(url)
    api_signature = f"{method}:{domain}"
    
    baseline["domains"].add(domain)
    baseline["apis"].add(api_signature)
    
    # Update rolling averages (keep last 50 samples)
    if len(baseline["payload_sizes"]) > 50:
        baseline["payload_sizes"] = baseline["payload_sizes"][-50:]
    if len(baseline["request_times"]) > 50:
        baseline["request_times"] = baseline["request_times"][-50:]
    
    # Calculate averages
    baseline["avg_payload"] = sum(baseline["payload_sizes"]) / len(baseline["payload_sizes"])
    baseline["max_payload"] = max(baseline["payload_sizes"])
    
    # Calculate request frequency (requests per minute)
    if len(baseline["request_times"]) > 1:
        time_span = baseline["request_times"][-1] - baseline["request_times"][0]
        if time_span > 0:
            baseline["avg_freq"] = (len(baseline["request_times"]) - 1) / (time_span / 60)
    
    # Calculate average hour
    hours = [datetime.fromtimestamp(t).hour for t in baseline["request_times"]]
    baseline["avg_hour"] = sum(hours) / len(hours)
    
    # Update known sets after warm-up period
    if baseline["sample_count"] >= 10:
        baseline["known_domains"] = baseline["domains"].copy()
        baseline["known_apis"] = baseline["apis"].copy()

def calculate_risk_score(agent_id: str, url: str, method: str, body: str, purpose: str) -> tuple[int, List[str]]:
    """Calculate risk score for outbound request."""
    score = 0
    reasons = []
    
    domain = extract_domain(url)
    body_size = len(body)
    
    # Check denylist domains
    if domain in DENYLIST_DOMAINS:
        score += 70
        reasons.append(f"denylisted_domain: {domain}")
    
    # Check for secrets in body
    secrets = detect_secrets_in_text(body)
    if secrets:
        score = 100  # Immediate quarantine
        reasons.append(f"secrets_detected: {', '.join(secrets)}")
        return score, reasons
    
    # Check for encoded blobs
    if detect_encoded_blob(body):
        score += 15
        reasons.append("encoded_blob_detected")
    
    # Check payload size vs baseline
    if agent_id in agent_baselines:
        baseline = agent_baselines[agent_id]
        
        if baseline["sample_count"] >= 10:  # After warm-up
            # Oversized payload check
            if baseline["max_payload"] > 0 and body_size > baseline["max_payload"] * 3:
                score += 20
                reasons.append("oversized_payload")
            
            # New domain check
            if baseline["sample_count"] >= 10 and domain not in baseline["known_domains"]:
                score += 30
                reasons.append(f"new_domain: {domain}")
            
            # New API check
            api_signature = f"{method}:{domain}"
            if baseline["sample_count"] >= 10 and api_signature not in baseline["known_apis"]:
                score += 30
                reasons.append(f"new_api: {api_signature}")
            
            # Frequency spike check
            if baseline["avg_freq"] > 0:
                current_freq = len([t for t in baseline["request_times"] if time.time() - t < 60])
                if current_freq > baseline["avg_freq"] * 5:
                    score += 25
                    reasons.append("frequency_spike")
            
            # Odd hour check (after 15 samples)
            if baseline["sample_count"] >= 15:
                current_hour = datetime.now().hour
                if abs(current_hour - baseline["avg_hour"]) > 3:
                    score += 10
                    reasons.append("odd_hour")
    
    # Method/body oddity
    if method == "GET" and body_size > 100:
        score += 10
        reasons.append("get_with_large_body")
    
    return min(score, 100), reasons

async def perform_upstream_request(url: str, method: str, body: str) -> Dict[str, Any]:
    """Perform the actual upstream HTTP request."""
    async with httpx.AsyncClient(timeout=3.0) as client:
        try:
            start_time = time.time()
            
            if method.upper() == "GET":
                response = await client.get(url)
            elif method.upper() == "POST":
                response = await client.post(url, content=body)
            else:
                response = await client.request(method, url, content=body)
            
            ttfb_ms = round((time.time() - start_time) * 1000, 2)
            
            return {
                "status_code": response.status_code,
                "ttfb_ms": ttfb_ms,
                "content_len": len(response.content),
                "headers": dict(response.headers)
            }
        except Exception as e:
            return {
                "error": str(e),
                "status_code": 0
            }

def mask_secrets_for_llm(text: str) -> str:
    """Mask secrets before sending to LLM."""
    # AWS keys
    text = re.sub(r'AKIA[0-9A-Z]{16}', '***', text)
    # API keys
    text = re.sub(r'(?:api[_-]?key|apikey|token)["\s]*[:=]["\s]*([a-zA-Z0-9_-]{20,})', 
                  r'api_key=***', text, flags=re.IGNORECASE)
    # PEM certificates
    text = re.sub(r'-----BEGIN [A-Z ]+-----.*?-----END [A-Z ]+-----', 
                  '***', text, flags=re.DOTALL)
    # SSN
    text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '***', text)
    
    return text

@app.post("/proxy", response_model=ProxyResponse)
async def proxy_request(request: ProxyRequest):
    """Analyze and potentially proxy outbound requests."""
    start_time = time.time()
    
    # Update agent baseline
    update_agent_baseline(request.agent_id, request.url, request.method, len(request.body))
    
    # Calculate risk score
    score, reasons = calculate_risk_score(
        request.agent_id, 
        request.url, 
        request.method, 
        request.body, 
        request.purpose
    )
    
    # Determine action based on score
    if score >= 100 or any("secrets_detected" in r for r in reasons):
        action = "QUARANTINE"
        quarantined_agents.add(request.agent_id)
        
        # Log A10 control action
        log_event("a10_control_log.jsonl", {
            "ts": time.time(),
            "event": "apply_waf_quarantine",
            "agent_id": request.agent_id,
            "url": request.url,
            "score": score,
            "reasons": reasons
        })
        
    elif score >= 80:
        action = "QUARANTINE"
    elif score >= 60:
        action = "BLOCK"
    elif score >= 40:
        action = "ALLOW+WATCH"
    else:
        action = "ALLOW"
    
    # Log the request
    log_data = {
        "ts": time.time(),
        "agent_id": request.agent_id,
        "url": request.url,
        "method": request.method,
        "body_size": len(request.body),
        "purpose": request.purpose,
        "score": score,
        "reasons": reasons,
        "action": action,
        "processing_time_ms": round((time.time() - start_time) * 1000, 2)
    }
    log_event("gateway_log.jsonl", log_data)
    
    # Log incidents for non-ALLOW actions
    if action != "ALLOW":
        incident = {
            "ts": time.time(),
            "agent_id": request.agent_id,
            "score": score,
            "action": action,
            "reasons": reasons,
            "url": request.url
        }
        incidents.append(incident)
        log_event("incidents.jsonl", incident)
    
    # Perform upstream request if allowed
    upstream_result = None
    if action in ["ALLOW", "ALLOW+WATCH"]:
        upstream_result = await perform_upstream_request(request.url, request.method, request.body)
    
    return ProxyResponse(
        status=action,
        reason="; ".join(reasons) if reasons else None,
        score=score,
        upstream=upstream_result
    )

@app.post("/llm/claude")
async def claude_completion(request: LLMRequest):
    """Perform Claude API calls on behalf of agents."""
    if not anthropic_client:
        raise HTTPException(status_code=503, detail="Anthropic API key not configured")
    
    # Mask secrets before sending to Claude
    masked_text = mask_secrets_for_llm(request.user_text)
    
    try:
        response = anthropic_client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=300,
            temperature=0,
            messages=[{
                "role": "user", 
                "content": f"Purpose: {request.purpose}\n\nUser request: {masked_text}\n\nProvide a helpful, concise response."
            }]
        )
        
        answer = response.content[0].text if response.content else "No response generated"
        
        return {
            "answer": answer,
            "tokens_used": {
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
                "total": response.usage.input_tokens + response.usage.output_tokens
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Claude API error: {str(e)}")

@app.get("/incidents")
async def get_incidents():
    """Get list of security incidents."""
    # Return last 100 incidents
    return {"incidents": incidents[-100:]}

@app.get("/health")
async def health_check():
    """Health check with security score."""
    # Calculate health score based on recent incidents
    now = time.time()
    recent_incidents = [i for i in incidents if now - i["ts"] < 86400]  # Last 24h
    
    health_score = 100
    for incident in recent_incidents:
        score_impact = max(0, (incident["score"] - 40) * 0.2)
        health_score -= score_impact
    
    health_score = max(0, min(100, health_score))
    
    return {
        "status": "healthy" if health_score > 70 else "degraded",
        "health_score": round(health_score, 1),
        "quarantined_agents": len(quarantined_agents),
        "recent_incidents": len(recent_incidents),
        "timestamp": time.time()
    }

@app.post("/compliance/generate")
async def generate_compliance_report():
    """Generate professional compliance evidence pack."""
    from compliance import ComplianceGenerator
    
    # Use the advanced compliance generator
    compliance_gen = ComplianceGenerator("data/incidents.jsonl")
    
    # Calculate health score
    health_score = compliance_gen.calculate_health_score()
    
    # Generate professional HTML report
    html_report = compliance_gen.generate_evidence_pack(
        health_score=health_score,
        agents_seen=len(agent_baselines),
        quarantined_agents=list(quarantined_agents)
    )
    
    # Save to file
    try:
        os.makedirs("data", exist_ok=True)
        with open("data/evidence_pack.html", "w", encoding="utf-8") as f:
            f.write(html_report)
    except Exception as e:
        print(f"Error saving evidence pack: {e}")
    
    return {"html": html_report}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)