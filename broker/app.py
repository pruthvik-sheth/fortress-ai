"""
ShieldForce AI - Ingress Broker
Front door security for AI agents
"""

import os
import json
import hashlib
import time
import random
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
from banking_utils import (
    load_banking_policy, detect_pan_in_text, detect_cvv_in_text, 
    redact_sensitive_data, generate_otp_code, store_otp, verify_otp,
    is_payment_request, extract_payment_details, cleanup_expired_otps
)

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
    message: Optional[str] = Field(None, description="User-friendly message for blocks")

class OTPSendRequest(BaseModel):
    """Request to send OTP"""
    phone_number: Optional[str] = Field(None, description="Phone number (optional for demo)")
    purpose: str = Field(..., description="Purpose of OTP (e.g., payment_verification)")

class OTPSendResponse(BaseModel):
    """Response from OTP send"""
    sent: bool = Field(..., description="Whether OTP was sent")
    channel: str = Field(..., description="Channel used (sms, email)")
    challenge_id: str = Field(..., description="Challenge ID for verification")
    expires_in: int = Field(..., description="Expiry time in seconds")

class OTPVerifyRequest(BaseModel):
    """Request to verify OTP"""
    challenge_id: str = Field(..., description="Challenge ID from send request")
    code: str = Field(..., description="OTP code to verify")

class OTPVerifyResponse(BaseModel):
    """Response from OTP verification"""
    verified: bool = Field(..., description="Whether OTP was verified")
    reason: Optional[str] = Field(None, description="Reason if verification failed")


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

# Load banking policy
BANKING_POLICY = load_banking_policy()

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

# RBAC from banking policy
RBAC_MAP = BANKING_POLICY.get("rbac", {
    "DEMO-KEY": ["cust-support-bot"],
    "BANKING-KEY": ["cust-support-bot", "payment-bot"]
})

# ============================================
# ENDPOINTS
# ============================================

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "ingress-broker",
        "version": "0.1.0",
        "banking_mode": True
    }

@app.post("/otp/send", response_model=OTPSendResponse)
async def send_otp(request: OTPSendRequest):
    """
    Send OTP for verification (mock implementation)
    """
    # Clean up expired OTPs
    cleanup_expired_otps()
    
    # Generate OTP
    otp_settings = BANKING_POLICY.get("otp_settings", {})
    code_length = otp_settings.get("code_length", 6)
    expiry_seconds = otp_settings.get("expiry_seconds", 300)
    
    code = generate_otp_code(code_length)
    challenge_id = f"otp_{int(time.time())}_{random.randint(1000, 9999)}"
    
    # Store OTP
    store_otp(challenge_id, code, expiry_seconds)
    
    # Log OTP send (without the actual code)
    log_event(
        LOG_FILE,
        "otp_sent",
        {
            "challenge_id": challenge_id,
            "purpose": request.purpose,
            "phone_number": request.phone_number,
            "expires_in": expiry_seconds
        }
    )
    
    # In a real implementation, send SMS/email here
    print(f"🔐 OTP Code for demo: {code} (Challenge ID: {challenge_id})")
    
    return OTPSendResponse(
        sent=True,
        channel="sms",
        challenge_id=challenge_id,
        expires_in=expiry_seconds
    )

@app.post("/otp/verify", response_model=OTPVerifyResponse)
async def verify_otp_endpoint(request: OTPVerifyRequest):
    """
    Verify OTP code
    """
    otp_settings = BANKING_POLICY.get("otp_settings", {})
    max_attempts = otp_settings.get("max_attempts", 3)
    
    success, reason = verify_otp(request.challenge_id, request.code, max_attempts)
    
    # Log verification attempt
    log_event(
        LOG_FILE,
        "otp_verified" if success else "otp_failed",
        {
            "challenge_id": request.challenge_id,
            "success": success,
            "reason": reason
        }
    )
    
    return OTPVerifyResponse(
        verified=success,
        reason=None if success else reason
    )


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
    # 4. BANKING SECURITY CHECKS (PAN/CVV Detection)
    # ============================================
    
    # Check for PAN in user input
    detected_pans = detect_pan_in_text(request.user_text)
    detected_cvvs = detect_cvv_in_text(request.user_text)
    
    if detected_pans or detected_cvvs:
        log_event(
            LOG_FILE,
            "pan_in_chat",
            {
                "reason": "pan_or_cvv_detected",
                "agent_id": request.agent_id,
                "api_key_hash": hash_api_key(x_api_key),
                "user_text_preview": request.user_text[:100],
                "detected_pans": len(detected_pans),
                "detected_cvvs": len(detected_cvvs),
                "request_id": request_id
            }
        )
        
        return InvokeResponse(
            decision="BLOCK",
            reason="pan_in_chat",
            message="For your security, I can't process card numbers in chat. I can send a secure pay link or do a transfer to a pre-approved payee (≤ $5,000) after verification.",
            request_id=request_id
        )
    
    # ============================================
    # 5. PROMPT FIREWALL (Multi-Layer)
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
    # 6. SECRET REDACTION
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
    # 7. BANKING CAPABILITY SCOPING
    # ============================================
    
    # Determine if this is a payment request and scope accordingly
    payment_details = None
    if is_payment_request(request.user_text):
        payment_details = extract_payment_details(request.user_text)
        
        # For payment requests, use restricted banking tools
        banking_tools = ["payments.create", "accounts.read", "transactions.read"]
        banking_scopes = ["accounts:owner_only", "transactions:last_90d", "payments:preapproved_only"]
        banking_budgets = {"max_tokens": 300, "max_tool_calls": 3}
        
        capability_token = token_manager.issue_token(
            agent_id=request.agent_id,
            allowed_tools=banking_tools,
            data_scope=banking_scopes,
            budgets=banking_budgets,
            payment_policy=BANKING_POLICY.get("payment_limits", {}),
            payment_details=payment_details
        )
    else:
        # Default service tools for general banking queries
        default_tools = ["accounts.read", "transactions.read", "secure_paylink.create", "http.fetch"]
        
        capability_token = token_manager.issue_token(
            agent_id=request.agent_id,
            allowed_tools=request.allowed_tools or default_tools,
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
