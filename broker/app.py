"""
ShieldForce AI - Ingress Broker
Front door security for AI agents
"""

import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import uuid

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import httpx

from firewall import PromptFirewall
from jwt_utils import CapabilityTokenManager

# ============================================
# MODELS (inlined from shared)
# ============================================

class InvokeRequest(BaseModel):
    """Request to invoke an agent"""
    agent_id: str = Field(..., description="Unique agent identifier")
    purpose: str = Field(..., description="Purpose of invocation")
    user_text: str = Field(..., description="User input text to process")
    attachments: list[dict] = Field(default_factory=list, description="Optional attachments")
    allowed_tools: list[str] = Field(..., description="Tools agent is allowed to use")
    data_scope: list[str] = Field(..., description="Data scopes agent can access")
    budgets: dict = Field(
        default_factory=lambda: {"max_tokens": 1500, "max_tool_calls": 3},
        description="Resource budgets"
    )
    request_id: Optional[str] = Field(None, description="Optional request correlation ID")


class InvokeResponse(BaseModel):
    """Response from broker"""
    decision: str = Field(..., description="ALLOW or BLOCK")
    reason: Optional[str] = Field(None, description="Reason for decision")
    result: Optional[dict] = Field(None, description="Agent result if allowed")
    request_id: Optional[str] = Field(None, description="Request correlation ID")


# ============================================
# LOGGING UTILS (inlined from shared)
# ============================================

def hash_api_key(api_key: str) -> str:
    """Hash API key for logging (SHA256)"""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


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
    
    # Mask sensitive fields
    if mask_fields:
        for field in mask_fields:
            if field in entry and entry[field]:
                entry[field] = "***MASKED***"
    
    # Append to file
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        # Fail gracefully - don't break the request
        print(f"Warning: Failed to write log: {e}")

# ============================================
# CONFIGURATION
# ============================================

PORT = int(os.getenv("PORT", "8001"))
BROKER_API_KEY = os.getenv("BROKER_API_KEY", "DEMO-KEY")
CAPABILITY_SECRET = os.getenv("CAPABILITY_SECRET", "dev-secret")
AGENT_URL = os.getenv("AGENT_URL", "http://agent:7000")
INGRESS_AUDITOR = os.getenv("INGRESS_AUDITOR", "off") == "on"
ENABLE_LLM_FIREWALL = os.getenv("ENABLE_LLM_FIREWALL", "true").lower() == "true"

LOG_FILE = "data/broker_log.jsonl"

# ============================================
# INITIALIZE
# ============================================

app = FastAPI(title="ShieldForce Ingress Broker", version="0.1.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

firewall = PromptFirewall(enable_llm=ENABLE_LLM_FIREWALL)
token_manager = CapabilityTokenManager(CAPABILITY_SECRET)

# Simple RBAC: API key -> allowed agent IDs
# In production, this would be in a database
RBAC_MAP = {
    "DEMO-KEY": ["customer-bot", "support-agent", "data-analyst", "*"],
    "ADMIN-KEY": ["*"]  # Admin can access any agent
}

# ============================================
# ENDPOINTS
# ============================================

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "ingress-broker",
        "version": "0.1.0"
    }


@app.post("/invoke")
async def invoke(
    request: InvokeRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    Main entry point for agent invocation
    
    Security checks:
    1. API key authentication
    2. RBAC (role-based access control)
    3. Envelope validation
    4. Prompt firewall
    5. Secret redaction
    6. JWT capability token issuance
    """
    
    request_id = request.request_id or str(uuid.uuid4())
    
    # ============================================
    # 1. AUTHENTICATION
    # ============================================
    
    if not x_api_key:
        log_event(
            LOG_FILE,
            "auth_failed",
            {
                "reason": "missing_api_key",
                "agent_id": request.agent_id,
                "request_id": request_id
            }
        )
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    
    if x_api_key not in RBAC_MAP:
        log_event(
            LOG_FILE,
            "auth_failed",
            {
                "reason": "invalid_api_key",
                "api_key_hash": hash_api_key(x_api_key),
                "agent_id": request.agent_id,
                "request_id": request_id
            }
        )
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # ============================================
    # 2. RBAC
    # ============================================
    
    allowed_agents = RBAC_MAP[x_api_key]
    
    if "*" not in allowed_agents and request.agent_id not in allowed_agents:
        log_event(
            LOG_FILE,
            "rbac_denied",
            {
                "api_key_hash": hash_api_key(x_api_key),
                "agent_id": request.agent_id,
                "allowed_agents": allowed_agents,
                "request_id": request_id
            }
        )
        raise HTTPException(
            status_code=403,
            detail=f"Not authorized to access agent {request.agent_id}"
        )
    
    # ============================================
    # 3. ENVELOPE VALIDATION
    # ============================================
    
    # Pydantic already validates required fields
    # Additional validation can go here
    
    if not request.user_text.strip():
        log_event(
            LOG_FILE,
            "validation_failed",
            {
                "reason": "empty_user_text",
                "agent_id": request.agent_id,
                "request_id": request_id
            }
        )
        raise HTTPException(status_code=400, detail="user_text cannot be empty")
    
    # ============================================
    # 4. PROMPT FIREWALL (Multi-Layer)
    # ============================================
    
    is_safe, block_reason, redactions, llm_result = firewall.check(request.user_text)
    
    if not is_safe:
        # Enhanced logging with LLM results
        log_data = {
            "reason": block_reason,
            "agent_id": request.agent_id,
            "api_key_hash": hash_api_key(x_api_key),
            "user_text_preview": request.user_text[:100],
            "request_id": request_id
        }
        
        # Add LLM analysis results if available
        if llm_result:
            log_data["llm_confidence"] = llm_result.get("confidence", 0.0)
            log_data["llm_inference_time_ms"] = llm_result.get("inference_time_ms", 0.0)
            log_data["llm_timeout"] = llm_result.get("timeout", False)
        
        log_event(
            LOG_FILE,
            "firewall_blocked",
            log_data
        )
        
        return InvokeResponse(
            decision="BLOCK",
            reason=block_reason,
            request_id=request_id
        )
    
    # ============================================
    # 5. SECRET REDACTION
    # ============================================
    
    sanitized_text = firewall.sanitize(request.user_text)
    
    if redactions:
        log_event(
            LOG_FILE,
            "secrets_redacted",
            {
                "redactions": redactions,
                "agent_id": request.agent_id,
                "request_id": request_id
            }
        )
    
    # ============================================
    # 6. JWT CAPABILITY TOKEN
    # ============================================
    
    capability_token = token_manager.issue_token(
        agent_id=request.agent_id,
        allowed_tools=request.allowed_tools,
        data_scope=request.data_scope,
        budgets=request.budgets
    )
    
    # ============================================
    # 7. FORWARD TO AGENT
    # ============================================
    
    agent_request = {
        "agent_id": request.agent_id,
        "purpose": request.purpose,
        "user_text": sanitized_text,  # Send sanitized version
        "attachments": request.attachments,
        "budgets": request.budgets,
        "request_id": request_id
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{AGENT_URL}/_internal/run",
                json=agent_request,
                headers={
                    "Authorization": f"Bearer {capability_token}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code != 200:
                log_event(
                    LOG_FILE,
                    "agent_error",
                    {
                        "status_code": response.status_code,
                        "agent_id": request.agent_id,
                        "request_id": request_id
                    }
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Agent returned error: {response.text}"
                )
            
            agent_result = response.json()
            
    except httpx.TimeoutException:
        log_event(
            LOG_FILE,
            "agent_timeout",
            {
                "agent_id": request.agent_id,
                "request_id": request_id
            }
        )
        raise HTTPException(status_code=504, detail="Agent timeout")
    
    except httpx.RequestError as e:
        log_event(
            LOG_FILE,
            "agent_unreachable",
            {
                "error": str(e),
                "agent_id": request.agent_id,
                "request_id": request_id
            }
        )
        raise HTTPException(status_code=503, detail="Agent unreachable")
    
    # ============================================
    # 8. LOG SUCCESS
    # ============================================
    
    log_event(
        LOG_FILE,
        "invoke_allowed",
        {
            "agent_id": request.agent_id,
            "api_key_hash": hash_api_key(x_api_key),
            "purpose": request.purpose,
            "redactions": redactions,
            "tokens_used": agent_result.get("tokens_used", 0),
            "tool_calls": agent_result.get("tool_calls", 0),
            "request_id": request_id
        }
    )
    
    # ============================================
    # 9. RETURN RESULT
    # ============================================
    
    return InvokeResponse(
        decision="ALLOW",
        result=agent_result,
        request_id=request_id
    )


# ============================================
# ERROR HANDLERS
# ============================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler"""
    log_event(
        LOG_FILE,
        "internal_error",
        {
            "error": str(exc),
            "path": request.url.path
        }
    )
    
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# ============================================
# STARTUP
# ============================================

@app.on_event("startup")
async def startup():
    """Initialize on startup"""
    print("🛡️  ShieldForce Ingress Broker starting...")
    print(f"   Agent URL: {AGENT_URL}")
    print(f"   LLM Auditor: {'ENABLED' if INGRESS_AUDITOR else 'DISABLED'}")
    print(f"   LLM Firewall: {'ENABLED' if ENABLE_LLM_FIREWALL else 'DISABLED'}")
    if firewall.llm_classifier and firewall.llm_classifier.enabled:
        print(f"   PromptShield: ✅ Ready on {firewall.llm_classifier.device}")
    elif ENABLE_LLM_FIREWALL:
        print("   PromptShield: ⚠️  Failed to load (regex-only mode)")
    print(f"   Log file: {LOG_FILE}")
    print("✅ Broker ready!")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
