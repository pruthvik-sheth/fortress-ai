import os
import re
import json
import time
from typing import Dict, Any, Optional
import jwt
import httpx
from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel

app = FastAPI(title="AI Agent", version="1.0.0")

# Environment configuration
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://gateway:9000")
CAPABILITY_SECRET = os.getenv("CAPABILITY_SECRET", "dev-secret")
CAP_ISS = os.getenv("CAP_ISS", "broker")
CAP_AUD = os.getenv("CAP_AUD", "agent")

class AgentRequest(BaseModel):
    agent_id: str
    purpose: str
    user_text: str
    request_id: Optional[str] = None

class AgentResponse(BaseModel):
    answer: str
    fetch_decision: Optional[Dict[str, Any]] = None
    logs: Dict[str, Any]

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
            return f"LLM call failed: {str(e)}"

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
            return {
                "status": "ERROR",
                "reason": f"Gateway proxy call failed: {str(e)}"
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
        
        # Extract any body content for the fetch (look for patterns like "with api_key=...")
        body_match = re.search(r'with\s+(.+)', request.user_text, re.IGNORECASE)
        fetch_body = body_match.group(1) if body_match else ""
        
        # Call Gateway proxy
        fetch_decision = await call_gateway_proxy(
            request.agent_id, 
            fetch_url, 
            request.purpose,
            fetch_body
        )
    
    # Always get LLM answer via Gateway
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
        "request_id": request.request_id
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
        "service": "agent",
        "gateway_url": GATEWAY_URL,
        "timestamp": time.time()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7000)