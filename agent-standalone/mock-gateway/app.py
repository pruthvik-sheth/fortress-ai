import os
import anthropic
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Mock Gateway", version="1.0.0")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

class LLMRequest(BaseModel):
    agent_id: str
    purpose: str
    user_text: str

class ProxyRequest(BaseModel):
    agent_id: str
    url: str
    method: str = "GET"
    body: str = ""
    purpose: str = ""

@app.post("/llm/claude")
async def claude_completion(request: LLMRequest):
    """Mock Claude API endpoint."""
    if not anthropic_client:
        return {"answer": "Mock response - Claude API not configured", "tokens_used": {"total": 0}}
    
    try:
        message = anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=300,
            temperature=0,
            messages=[{
                "role": "user", 
                "content": f"Purpose: {request.purpose}\n\nUser request: {request.user_text}\n\nProvide a helpful, concise response."
            }]
        )
        
        answer = message.content[0].text if message.content else "No response generated"
        
        return {
            "answer": answer,
            "tokens_used": {
                "input": message.usage.input_tokens,
                "output": message.usage.output_tokens,
                "total": message.usage.input_tokens + message.usage.output_tokens
            }
        }
    except Exception as e:
        return {"answer": f"Claude API error: {str(e)}", "tokens_used": {"total": 0}}

@app.post("/proxy")
async def proxy_request(request: ProxyRequest):
    """Mock proxy endpoint - always allows for testing."""
    return {
        "status": "ALLOW",
        "reason": "Mock gateway - all requests allowed",
        "score": 5,
        "upstream": {
            "status_code": 200,
            "ttfb_ms": 150,
            "content_len": 1024
        }
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "mock-gateway"}