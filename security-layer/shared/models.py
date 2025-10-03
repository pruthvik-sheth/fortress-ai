"""
ShieldForce AI - Pydantic Models
Request/response schemas for API validation
"""

from pydantic import BaseModel, Field
from typing import Optional


# ============================================
# INGRESS BROKER MODELS
# ============================================

class InvokeRequest(BaseModel):
    """Request to invoke an agent"""
    agent_id: str = Field(..., description="Unique agent identifier")
    purpose: str = Field(..., description="Purpose of invocation (e.g., 'answer_customer_ticket')")
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
# EGRESS GATEWAY MODELS
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


class IncidentRecord(BaseModel):
    """Security incident record"""
    timestamp: str
    agent_id: str
    score: float
    action: str  # BLOCK or QUARANTINE
    reasons: list[str]
    url: Optional[str] = None
    method: Optional[str] = None


class HealthResponse(BaseModel):
    """Health and status response"""
    status: str = Field(..., description="healthy or degraded")
    health_score: float = Field(..., description="Organization health score (0-100)")
    agents_seen: int = Field(..., description="Number of unique agents")
    incidents_24h: int = Field(..., description="Incidents in last 24 hours")
    quarantined_agents: int = Field(..., description="Currently quarantined agents")


# ============================================
# CAPABILITY TOKEN CLAIMS
# ============================================

class CapabilityToken(BaseModel):
    """JWT capability token claims"""
    iss: str = Field(default="broker", description="Issuer")
    aud: str = Field(default="agent", description="Audience")
    sub: str = Field(..., description="Subject (agent_id)")
    tools: list[str] = Field(..., description="Allowed tools")
    scopes: list[str] = Field(..., description="Data scopes")
    budgets: dict = Field(..., description="Resource budgets")
    exp: int = Field(..., description="Expiration timestamp")
    iat: int = Field(..., description="Issued at timestamp")
