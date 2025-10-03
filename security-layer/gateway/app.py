"""
ShieldForce AI - Egress Gateway
Back door security for AI agents - monitors all outbound requests
"""

import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, Field
import httpx

from behavior_dna import BehaviorDNAEngine
from threat_scoring import ThreatScorer
from compliance import ComplianceGenerator

# ============================================
# MODELS (inlined from shared)
# ============================================

class ProxyRequest(BaseModel):
    """Request to proxy an outbound call"""
    agent_id: str = Field(..., description="Agent making the request")
    url: str = Field(..., description="Destination URL")
    method: str = Field(..., description="HTTP method (GET, POST, etc.)")
    headers: Optional[dict] = Field(default_factory=dict, description="HTTP headers")
    body: Optional[str] = Field(None, description="Request body")
    purpose: str = Field(..., description="Purpose of the request")


class ProxyResponse(BaseModel):
    """Response from gateway"""
    status: str = Field(..., description="ALLOW, BLOCK, or QUARANTINED")
    score: Optional[float] = Field(None, description="Threat score (0-100)")
    reasons: Optional[list[str]] = Field(None, description="Reasons for decision")
    upstream: Optional[dict] = Field(None, description="Upstream response if allowed")
    incident_id: Optional[str] = Field(None, description="Incident ID if quarantined")


class HealthResponse(BaseModel):
    """Health and status response"""
    status: str = Field(..., description="healthy or degraded")
    health_score: float = Field(..., description="Organization health score (0-100)")
    agents_seen: int = Field(..., description="Number of unique agents")
    incidents_24h: int = Field(..., description="Incidents in last 24 hours")
    quarantined_agents: int = Field(..., description="Currently quarantined agents")


# ============================================
# LOGGING UTILS (inlined from shared)
# ============================================

def log_event(
    log_file: str,
    event_type: str,
    data: dict[str, Any],
    mask_fields: list[str] | None = None
) -> None:
    """Append event to JSONL log file"""
    # Ensure data directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Build log entry
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": event_type,
        **data
    }
    
    # Append to file
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        print(f"Warning: Failed to write log: {e}")

# ============================================
# CONFIGURATION
# ============================================

GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "9000"))
EGRESS_AUDITOR = os.getenv("EGRESS_AUDITOR", "off") == "on"

LOG_FILE = "/app/data/gateway_log.jsonl"
INCIDENTS_FILE = "/app/data/incidents.jsonl"
A10_LOG_FILE = "/app/data/a10_control_log.jsonl"

# ============================================
# INITIALIZE
# ============================================

app = FastAPI(title="ShieldForce Egress Gateway", version="0.1.0")

behavior_engine = BehaviorDNAEngine()
threat_scorer = ThreatScorer()
compliance_gen = ComplianceGenerator(INCIDENTS_FILE)

# Quarantined agents (in-memory for demo, would be Redis in production)
quarantined_agents: set[str] = set()

# ============================================
# ENDPOINTS
# ============================================

@app.get("/health")
async def health():
    """
    Health check with organization health score
    """
    health_score = compliance_gen.calculate_health_score()
    incidents_24h = compliance_gen.get_incidents_count(hours=24)
    
    return HealthResponse(
        status="healthy" if health_score > 70 else "degraded",
        health_score=health_score,
        agents_seen=len(behavior_engine.baselines),
        incidents_24h=incidents_24h,
        quarantined_agents=len(quarantined_agents)
    )


@app.get("/incidents")
async def get_incidents(limit: int = 100):
    """
    Get recent security incidents
    """
    incidents = compliance_gen.get_recent_incidents(limit=limit)
    return {"incidents": incidents, "total": len(incidents)}


@app.post("/compliance/generate")
async def generate_compliance():
    """
    Generate compliance evidence pack (HTML)
    """
    html = compliance_gen.generate_evidence_pack(
        health_score=compliance_gen.calculate_health_score(),
        agents_seen=len(behavior_engine.baselines),
        quarantined_agents=list(quarantined_agents)
    )
    
    # Also save to file
    with open("/app/data/evidence_pack.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    return HTMLResponse(content=html)


@app.post("/proxy")
async def proxy(request: ProxyRequest):
    """
    Proxy outbound requests with threat analysis
    
    Security pipeline:
    1. Check if agent is quarantined
    2. Run deterministic threat rules
    3. Analyze behavior baseline
    4. Optional: LLM auditor
    5. Calculate final threat score
    6. Take action (ALLOW/BLOCK/QUARANTINE)
    """
    
    start_time = time.time()
    
    # ============================================
    # 1. QUARANTINE CHECK
    # ============================================
    
    if request.agent_id in quarantined_agents:
        log_event(
            LOG_FILE,
            "quarantine_blocked",
            {
                "agent_id": request.agent_id,
                "url": request.url,
                "method": request.method
            }
        )
        
        return ProxyResponse(
            status="QUARANTINED",
            score=100.0,
            reasons=["agent_locked"],
            incident_id=None
        )
    
    # ============================================
    # 2. DETERMINISTIC THREAT RULES
    # ============================================
    
    rules_score, rules_reasons = threat_scorer.score_deterministic(
        url=request.url,
        method=request.method,
        body=request.body or "",
        purpose=request.purpose
    )
    
    # ============================================
    # 3. BEHAVIOR DNA ANALYSIS
    # ============================================
    
    behavior_score, behavior_reasons = behavior_engine.analyze(
        agent_id=request.agent_id,
        url=request.url,
        method=request.method,
        body_size=len(request.body or ""),
        timestamp=time.time()
    )
    
    # ============================================
    # 4. OPTIONAL: LLM AUDITOR
    # ============================================
    
    llm_score = 0.0
    llm_reasons = []
    
    if EGRESS_AUDITOR:
        # TODO: Implement LLM auditor
        # For now, placeholder
        pass
    
    # ============================================
    # 5. CALCULATE FINAL SCORE
    # ============================================
    
    final_score = min(rules_score + behavior_score + llm_score, 100.0)
    all_reasons = rules_reasons + behavior_reasons + llm_reasons
    
    # ============================================
    # 6. TAKE ACTION
    # ============================================
    
    action = "ALLOW"
    watch = False
    
    # Immediate quarantine on secret detection
    if "secret_pattern" in all_reasons:
        action = "QUARANTINE"
        quarantined_agents.add(request.agent_id)
        
        # Log to A10 control log
        log_event(
            A10_LOG_FILE,
            "apply_waf_quarantine",
            {
                "agent_id": request.agent_id,
                "reason": "secret_exfiltration_detected",
                "score": final_score
            }
        )
    
    elif final_score >= 80:
        action = "QUARANTINE"
        quarantined_agents.add(request.agent_id)
        
        log_event(
            A10_LOG_FILE,
            "apply_waf_quarantine",
            {
                "agent_id": request.agent_id,
                "reason": "high_threat_score",
                "score": final_score
            }
        )
    
    elif final_score >= 60:
        action = "BLOCK"
    
    elif final_score >= 40:
        action = "ALLOW"
        watch = True
    
    else:
        action = "ALLOW"
    
    # ============================================
    # 7. LOG DECISION
    # ============================================
    
    log_event(
        LOG_FILE,
        f"proxy_{action.lower()}",
        {
            "agent_id": request.agent_id,
            "url": request.url,
            "method": request.method,
            "score": final_score,
            "reasons": all_reasons,
            "action": action,
            "watch": watch,
            "latency_ms": int((time.time() - start_time) * 1000)
        }
    )
    
    # Log incidents (BLOCK or QUARANTINE)
    if action in ["BLOCK", "QUARANTINE"]:
        log_event(
            INCIDENTS_FILE,
            "security_incident",
            {
                "agent_id": request.agent_id,
                "url": request.url,
                "method": request.method,
                "score": final_score,
                "action": action,
                "reasons": all_reasons
            }
        )
    
    # ============================================
    # 8. EXECUTE OR BLOCK
    # ============================================
    
    if action == "ALLOW":
        # Make the actual upstream request
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                upstream_start = time.time()
                
                response = await client.request(
                    method=request.method,
                    url=request.url,
                    headers=request.headers or {},
                    content=request.body,
                )
                
                ttfb_ms = int((time.time() - upstream_start) * 1000)
                
                return ProxyResponse(
                    status="ALLOW",
                    score=final_score,
                    reasons=all_reasons if watch else None,
                    upstream={
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "body": response.text,
                        "ttfb_ms": ttfb_ms,
                        "content_len": len(response.content)
                    }
                )
        
        except httpx.TimeoutException:
            return ProxyResponse(
                status="ALLOW",
                score=final_score,
                reasons=["upstream_timeout"],
                upstream={"error": "timeout"}
            )
        
        except httpx.RequestError as e:
            return ProxyResponse(
                status="ALLOW",
                score=final_score,
                reasons=["upstream_error"],
                upstream={"error": str(e)}
            )
    
    else:
        # BLOCK or QUARANTINE
        return ProxyResponse(
            status=action,
            score=final_score,
            reasons=all_reasons,
            incident_id=None
        )


# ============================================
# STARTUP
# ============================================

@app.on_event("startup")
async def startup():
    """Initialize on startup"""
    print("🛡️  ShieldForce Egress Gateway starting...")
    print(f"   Port: {GATEWAY_PORT}")
    print(f"   LLM Auditor: {'ENABLED' if EGRESS_AUDITOR else 'DISABLED'}")
    print(f"   Log file: {LOG_FILE}")
    print("✅ Gateway ready!")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=GATEWAY_PORT)
