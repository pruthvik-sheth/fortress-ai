import os
import re
import json
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import jwt
import httpx
from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel

app = FastAPI(title="Ingress Broker", version="1.0.0")

# Environment configuration
PORT = int(os.getenv("PORT", "8001"))
BROKER_API_KEY = os.getenv("BROKER_API_KEY", "DEMO-KEY")
CAPABILITY_SECRET = os.getenv("CAPABILITY_SECRET", "dev-secret")
AGENT_URL = "http://agent:7000"

# Simple RBAC mapping: API key -> allowed agent IDs
API_KEY_PERMISSIONS = {
    "DEMO-KEY": ["customer-bot", "support-agent", "data-analyst"],
    "ADMIN-KEY": ["*"]  # Admin can access any agent
}

class InvokeRequest(BaseModel):
    agent_id: str
    purpose: str
    user_text: str
    allowed_tools: List[str]
    data_scope: List[str]
    budgets: Optional[Dict[str, int]] = None
    request_id: Optional[str] = None

class BlockedResponse(BaseModel):
    decision: str
    reason: str
    timestamp: float

def hash_api_key(api_key: str) -> str:
    """Hash API key for logging (privacy)."""
    return hashlib.sha256(api_key.encode()).hexdigest()[:12]

def log_event(event_data: Dict[str, Any]):
    """Append event to broker log file."""
    try:
        os.makedirs("data", exist_ok=True)
        with open("data/broker_log.jsonl", "a") as f:
            f.write(json.dumps(event_data) + "\n")
    except Exception as e:
        print(f"Logging error: {e}")

def validate_api_key(api_key: str, agent_id: str) -> bool:
    """Validate API key and check agent access permissions."""
    if api_key not in API_KEY_PERMISSIONS:
        return False
    
    allowed_agents = API_KEY_PERMISSIONS[api_key]
    return "*" in allowed_agents or agent_id in allowed_agents

def detect_instruction_override(text: str) -> Optional[str]:
    """Detect prompt injection attempts."""
    dangerous_patterns = [
        r'ignore\s+previous\s+instructions?',
        r'reveal\s+(?:your\s+)?system\s+prompt',
        r'dump\s+(?:your\s+)?memory',
        r'bypass\s+(?:all\s+)?(?:safety|security)',
        r'jailbreak',
        r'disable\s+safety',
        r'forget\s+(?:your\s+)?(?:instructions?|rules?)',
        r'act\s+as\s+(?:if\s+)?you\s+are\s+not',
        r'pretend\s+(?:that\s+)?you\s+are\s+not'
    ]
    
    text_lower = text.lower()
    for pattern in dangerous_patterns:
        if re.search(pattern, text_lower):
            return f"instruction_override: {pattern}"
    
    return None

def strip_html_and_scripts(text: str) -> str:
    """Remove HTML tags and script content."""
    # Remove script tags and content
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    return text

def detect_and_redact_secrets(text: str) -> tuple[str, List[str]]:
    """Detect and redact common secret patterns."""
    redactions = []
    
    # AWS keys
    aws_pattern = r'AKIA[0-9A-Z]{16}'
    if re.search(aws_pattern, text):
        text = re.sub(aws_pattern, '***AWS_KEY_REDACTED***', text)
        redactions.append("aws_access_key")
    
    # Generic API keys
    api_key_pattern = r'(?:api[_-]?key|apikey|token)["\s]*[:=]["\s]*([a-zA-Z0-9_-]{20,})'
    if re.search(api_key_pattern, text, re.IGNORECASE):
        text = re.sub(api_key_pattern, r'api_key=***REDACTED***', text, flags=re.IGNORECASE)
        redactions.append("api_key")
    
    # PEM certificates/keys
    pem_pattern = r'-----BEGIN [A-Z ]+-----.*?-----END [A-Z ]+-----'
    if re.search(pem_pattern, text, re.DOTALL):
        text = re.sub(pem_pattern, '***PEM_REDACTED***', text, flags=re.DOTALL)
        redactions.append("pem_certificate")
    
    # Simple SSN pattern
    ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
    if re.search(ssn_pattern, text):
        text = re.sub(ssn_pattern, '***SSN_REDACTED***', text)
        redactions.append("ssn")
    
    return text, redactions

def create_capability_jwt(agent_id: str, tools: List[str], scopes: List[str], budgets: Dict[str, Any]) -> str:
    """Create a capability JWT for the agent."""
    now = datetime.utcnow()
    payload = {
        "iss": "broker",
        "aud": "agent", 
        "sub": agent_id,
        "tools": tools,
        "scopes": scopes,
        "budgets": budgets or {},
        "iat": now,
        "exp": now + timedelta(minutes=5)
    }
    
    return jwt.encode(payload, CAPABILITY_SECRET, algorithm="HS256")

@app.post("/invoke")
async def invoke_agent(
    request: InvokeRequest,
    x_api_key: str = Header(..., alias="X-API-Key")
):
    """Main broker endpoint - validates requests and forwards to agent."""
    start_time = time.time()
    request_id = request.request_id or f"req_{int(time.time() * 1000)}"
    
    # Authentication & RBAC
    if not validate_api_key(x_api_key, request.agent_id):
        log_event({
            "ts": time.time(),
            "caller_hash": hash_api_key(x_api_key),
            "agent_id": request.agent_id,
            "decision": "AUTH_FAILED",
            "reason": "invalid_api_key_or_agent_access",
            "request_id": request_id
        })
        raise HTTPException(status_code=403, detail="Invalid API key or agent access denied")
    
    # Envelope validation
    if not request.purpose or not request.user_text or not request.allowed_tools:
        log_event({
            "ts": time.time(),
            "caller_hash": hash_api_key(x_api_key),
            "agent_id": request.agent_id,
            "decision": "VALIDATION_FAILED",
            "reason": "missing_required_fields",
            "request_id": request_id
        })
        raise HTTPException(status_code=400, detail="Missing required fields: purpose, user_text, allowed_tools")
    
    # Prompt firewall - instruction override detection
    override_reason = detect_instruction_override(request.user_text)
    if override_reason:
        log_event({
            "ts": time.time(),
            "caller_hash": hash_api_key(x_api_key),
            "agent_id": request.agent_id,
            "decision": "BLOCK",
            "reason": override_reason,
            "request_id": request_id
        })
        return BlockedResponse(
            decision="BLOCK",
            reason=override_reason,
            timestamp=time.time()
        )
    
    # Input sanitization
    sanitized_text = strip_html_and_scripts(request.user_text)
    
    # Length check
    if len(sanitized_text) > 10000:
        log_event({
            "ts": time.time(),
            "caller_hash": hash_api_key(x_api_key),
            "agent_id": request.agent_id,
            "decision": "BLOCK",
            "reason": "text_too_long",
            "text_length": len(sanitized_text),
            "request_id": request_id
        })
        return BlockedResponse(
            decision="BLOCK",
            reason="text_too_long",
            timestamp=time.time()
        )
    
    # Secret detection and redaction
    redacted_text, redactions = detect_and_redact_secrets(sanitized_text)
    
    # Create capability JWT
    capability_token = create_capability_jwt(
        request.agent_id,
        request.allowed_tools,
        request.data_scope,
        request.budgets
    )
    
    # Forward to agent
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                f"{AGENT_URL}/_internal/run",
                headers={
                    "Authorization": f"Bearer {capability_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "agent_id": request.agent_id,
                    "purpose": request.purpose,
                    "user_text": redacted_text,
                    "request_id": request_id
                }
            )
            response.raise_for_status()
            agent_response = response.json()
            
            # Log successful invoke
            log_event({
                "ts": time.time(),
                "caller_hash": hash_api_key(x_api_key),
                "agent_id": request.agent_id,
                "decision": "INVOKE_ALLOWED",
                "redactions": redactions,
                "processing_time_ms": round((time.time() - start_time) * 1000, 2),
                "request_id": request_id
            })
            
            return agent_response
            
        except httpx.HTTPError as e:
            log_event({
                "ts": time.time(),
                "caller_hash": hash_api_key(x_api_key),
                "agent_id": request.agent_id,
                "decision": "AGENT_ERROR",
                "reason": str(e),
                "request_id": request_id
            })
            raise HTTPException(status_code=502, detail=f"Agent communication failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "broker",
        "agent_url": AGENT_URL,
        "timestamp": time.time()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)