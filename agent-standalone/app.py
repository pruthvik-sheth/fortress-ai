import os
import re
import json
import time
from typing import Dict, Any, Optional
import jwt
import httpx
import anthropic
from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel

app = FastAPI(title="AI Agent - Standalone", version="1.0.0")

# Environment configuration
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://mock-gateway:9001")
CAPABILITY_SECRET = os.getenv("CAPABILITY_SECRET", "dev-secret")
CAP_ISS = os.getenv("CAP_ISS", "broker")
CAP_AUD = os.getenv("CAP_AUD", "agent")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Initialize Anthropic client for direct testing
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

class AgentRequest(BaseModel):
    agent_id: str
    purpose: str
    user_text: str
    request_id: Optional[str] = None

class AgentResponse(BaseModel):
    answer: str
    fetch_decision: Optional[Dict[str, Any]] = None
    logs: Dict[str, Any]

class DirectRequest(BaseModel):
    """For direct testing without JWT"""
    agent_id: str = "test-agent"
    purpose: str
    user_text: str
    allowed_tools: list = ["http.fetch"]

def verify_capability_jwt(token: str) -> Dict[str, Any]:
    """Verify and decode the capability JWT from the broker."""
    try:
        payload = jwt.decode(
            token, 
            CAPABILITY_SECRET, 
            algorithms=["HS256"],
            issuer=CAP_ISS,
            audience=CAP_AUD
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Capability token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid capability token: {str(e)}")

def extract_fetch_url(text: str) -> Optional[str]:
    """Extract FETCH URL from user text if present."""
    fetch_pattern = r'FETCH\s+(https?://[^\s]+)'
    match = re.search(fetch_pattern, text, re.IGNORECASE)
    return match.group(1) if match else None

async def call_claude_direct(purpose: str, user_text: str) -> str:
    """Call Claude API directly for standalone testing."""
    if not anthropic_client:
        return "Claude API not configured - set ANTHROPIC_API_KEY"
    
    try:
        # Updated Anthropic API syntax
        message = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=300,
            temperature=0,
            messages=[{
                "role": "user", 
                "content": f"Purpose: {purpose}\n\nUser request: {user_text}\n\nProvide a helpful, concise response."
            }]
        )
        
        return message.content[0].text if message.content else "No response generated"
    except Exception as e:
        return f"Claude API error: {str(e)}"

async def call_gateway_llm(agent_id: str, purpose: str, user_text: str) -> str:
    """Call the Gateway's Claude API endpoint."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.post(
                f"{GATEWAY_URL}/llm/claude",
                json={
                    "agent_id": agent_id,
                    "purpose": purpose,
                    "user_text": user_text
                }
            )
            response.raise_for_status()
            result = response.json()
            return result.get("answer", "No response from LLM")
        except Exception as e:
            # Fallback to direct Claude call for standalone testing
            print(f"Gateway call failed, using direct Claude: {e}")
            return await call_claude_direct(purpose, user_text)

async def call_gateway_proxy(agent_id: str, url: str, purpose: str, body: str = "") -> Dict[str, Any]:
    """Call the Gateway's proxy endpoint for HTTP requests."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.post(
                f"{GATEWAY_URL}/proxy",
                json={
                    "agent_id": agent_id,
                    "url": url,
                    "method": "GET",
                    "body": body,
                    "purpose": purpose
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            # Mock response for standalone testing
            return {
                "status": "ALLOW",
                "reason": f"Mock response - Gateway unavailable: {str(e)}",
                "score": 10,
                "upstream": {"status_code": 200, "content": "Mock response"}
            }

@app.post("/_internal/run", response_model=AgentResponse)
async def run_agent(
    request: AgentRequest,
    authorization: str = Header(..., description="Bearer token with capability JWT")
):
    """Main agent endpoint - processes requests with capability verification."""
    start_time = time.time()
    
    # Extract and verify JWT
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    token = authorization[7:]  # Remove "Bearer " prefix
    capabilities = verify_capability_jwt(token)
    
    # Verify agent_id matches JWT subject
    if capabilities.get("sub") != request.agent_id:
        raise HTTPException(status_code=403, detail="Agent ID mismatch with capability token")
    
    # Extract allowed tools from JWT
    allowed_tools = capabilities.get("tools", [])
    
    # Check for FETCH requests
    fetch_url = extract_fetch_url(request.user_text)
    fetch_decision = None
    
    if fetch_url:
        if "http.fetch" not in allowed_tools:
            raise HTTPException(
                status_code=403, 
                detail="HTTP fetch not allowed - missing 'http.fetch' capability"
            )
        
        # Extract any body content for the fetch
        body_match = re.search(r'with\s+(.+)', request.user_text, re.IGNORECASE)
        fetch_body = body_match.group(1) if body_match else ""
        
        # Call Gateway proxy
        fetch_decision = await call_gateway_proxy(
            request.agent_id, 
            fetch_url, 
            request.purpose,
            fetch_body
        )
    
    # Get LLM answer via Gateway (with fallback to direct)
    llm_answer = await call_gateway_llm(
        request.agent_id,
        request.purpose, 
        request.user_text
    )
    
    # Prepare response logs
    logs = {
        "processing_time_ms": round((time.time() - start_time) * 1000, 2),
        "capabilities_verified": True,
        "allowed_tools": allowed_tools,
        "fetch_attempted": fetch_url is not None,
        "request_id": request.request_id,
        "mode": "standalone"
    }
    
    return AgentResponse(
        answer=llm_answer,
        fetch_decision=fetch_decision,
        logs=logs
    )

@app.post("/test", response_model=AgentResponse)
async def test_agent_direct(request: DirectRequest):
    """Direct testing endpoint without JWT requirements."""
    start_time = time.time()
    
    print(f"Direct test request: {request.purpose} - {request.user_text}")
    
    # Check for FETCH requests
    fetch_url = extract_fetch_url(request.user_text)
    fetch_decision = None
    
    if fetch_url:
        if "http.fetch" not in request.allowed_tools:
            return AgentResponse(
                answer="HTTP fetch not allowed in current configuration",
                fetch_decision={"status": "BLOCKED", "reason": "tool_not_allowed"},
                logs={"error": "fetch_not_allowed"}
            )
        
        # Extract any body content for the fetch
        body_match = re.search(r'with\s+(.+)', request.user_text, re.IGNORECASE)
        fetch_body = body_match.group(1) if body_match else ""
        
        # Call Gateway proxy (will fallback to mock)
        fetch_decision = await call_gateway_proxy(
            request.agent_id, 
            fetch_url, 
            request.purpose,
            fetch_body
        )
    
    # Get LLM answer (direct Claude call)
    llm_answer = await call_claude_direct(request.purpose, request.user_text)
    
    # Prepare response logs
    logs = {
        "processing_time_ms": round((time.time() - start_time) * 1000, 2),
        "mode": "direct_test",
        "allowed_tools": request.allowed_tools,
        "fetch_attempted": fetch_url is not None,
        "claude_direct": True
    }
    
    return AgentResponse(
        answer=llm_answer,
        fetch_decision=fetch_decision,
        logs=logs
    )

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "agent-standalone",
        "gateway_url": GATEWAY_URL,
        "claude_configured": anthropic_client is not None,
        "timestamp": time.time()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7000)