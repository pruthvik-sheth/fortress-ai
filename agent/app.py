import os
import re
import json
import time
from typing import Dict, Any, Optional
import jwt
import httpx
from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel

from banking_agent import (
    validate_payment_request, format_account_balance, format_transaction_list,
    generate_secure_paylink, mock_account_data, mock_transaction_data
)

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
    payment_result: Optional[Dict[str, Any]] = None
    account_data: Optional[Dict[str, Any]] = None
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
    
    # Initialize response components
    fetch_decision = None
    payment_result = None
    account_data = None
    llm_answer = ""
    
    # ============================================
    # BANKING OPERATIONS HANDLING
    # ============================================
    
    user_text_lower = request.user_text.lower()
    
    # Check for fetch/export requests FIRST (higher priority than account queries)
    fetch_url = extract_fetch_url(request.user_text)
    
    # Handle general fetch requests (including data exfiltration attempts)
    if fetch_url or any(keyword in user_text_lower for keyword in ["export", "fetch", "send to", "upload to"]):
        if not fetch_url:
            # Try to extract URL from export/send commands
            import re
            url_match = re.search(r'https?://[^\s]+', request.user_text)
            if url_match:
                fetch_url = url_match.group()
        
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
            
            if fetch_decision.get("status") == "ALLOW":
                llm_answer = "✅ External request completed successfully."
            else:
                llm_answer = f"❌ External request blocked: {fetch_decision.get('reason', 'Security policy violation')}"
    
    # Handle account balance/transaction requests (only if not an export/fetch)
    elif any(keyword in user_text_lower for keyword in ["balance", "account", "transactions", "statement"]):
        if "accounts.read" not in allowed_tools:
            raise HTTPException(
                status_code=403,
                detail="Account access not permitted - missing 'accounts.read' capability"
            )
        
        # Mock account data retrieval via Gateway
        account_fetch = await call_gateway_proxy(
            request.agent_id,
            "https://core-banking.internal/accounts/summary",
            "account_inquiry",
            ""
        )
        
        if account_fetch.get("status") == "ALLOW":
            account_data = mock_account_data()
            
            if "transactions" in user_text_lower or "statement" in user_text_lower:
                transactions = mock_transaction_data()
                llm_answer = f"Here's your account summary:\n\n"
                llm_answer += f"Account: {account_data['account_number']}\n"
                llm_answer += f"Available Balance: {format_account_balance(account_data['available_balance'])}\n\n"
                llm_answer += format_transaction_list(transactions)
            else:
                llm_answer = f"Your current account balance is {format_account_balance(account_data['available_balance'])}. "
                llm_answer += f"Your account number ending in {account_data['account_number'][-4:]} has ${account_data['balance']:,.2f} total balance."
        else:
            llm_answer = "I'm unable to access your account information at this time. Please try again later."
    
    # Handle payment requests
    elif any(keyword in user_text_lower for keyword in ["wire", "transfer", "send money", "pay"]):
        if "payments.create" not in allowed_tools:
            raise HTTPException(
                status_code=403,
                detail="Payment creation not permitted - missing 'payments.create' capability"
            )
        
        # Extract payment details
        amount_match = re.search(r'\$([0-9,]+(?:\.[0-9]{2})?)', request.user_text)
        payee_match = re.search(r'to\s+([A-Z][A-Z\s&\.,]+?)(?:\s|$|[^A-Za-z])', request.user_text, re.IGNORECASE)
        
        if amount_match and payee_match:
            amount = float(amount_match.group(1).replace(',', ''))
            payee_name = payee_match.group(1).strip()
            
            # Validate payment request
            validation = validate_payment_request(amount, payee_name, capabilities)
            
            if validation["valid"]:
                # Call Gateway to process payment
                payment_body = {
                    "amount": amount,
                    "payee_id": validation["payee_info"]["id"],
                    "payee_name": validation["payee_info"]["name"],
                    "currency": "USD"
                }
                
                payment_fetch = await call_gateway_proxy(
                    request.agent_id,
                    "https://payments.internal/transfers",
                    "payment_create",
                    json.dumps(payment_body)
                )
                
                payment_result = {
                    "amount": amount,
                    "payee": validation["payee_info"]["name"],
                    "status": payment_fetch.get("status", "UNKNOWN"),
                    "gateway_response": payment_fetch
                }
                
                if payment_fetch.get("status") == "ALLOW":
                    llm_answer = f"✅ Payment of ${amount:,.2f} to {validation['payee_info']['name']} has been processed successfully. "
                    llm_answer += f"Transaction ID: TXN_{int(time.time())}"
                else:
                    llm_answer = f"❌ Payment could not be processed. Reason: {payment_fetch.get('reason', 'Unknown error')}"
            else:
                reasons = validation["reasons"]
                if "amount_exceeds_limit" in str(reasons):
                    llm_answer = f"❌ Payment amount ${amount:,.2f} exceeds the chat limit of $5,000. Please use online banking for larger transfers."
                elif "payee_not_preapproved" in reasons:
                    llm_answer = f"❌ '{payee_name}' is not in your pre-approved payee list. Please add them through online banking first."
                else:
                    llm_answer = f"❌ Payment cannot be processed: {', '.join(reasons)}"
        else:
            llm_answer = "I need both an amount and payee name to process a payment. For example: 'Wire $500 to ACME LLC'"
    
    # Handle secure paylink requests
    elif "secure pay" in user_text_lower or "payment link" in user_text_lower:
        if "secure_paylink.create" not in allowed_tools:
            raise HTTPException(
                status_code=403,
                detail="Secure paylink creation not permitted"
            )
        
        amount_match = re.search(r'\$([0-9,]+(?:\.[0-9]{2})?)', request.user_text)
        if amount_match:
            amount = float(amount_match.group(1).replace(',', ''))
            
            # Call Gateway to create paylink
            paylink_fetch = await call_gateway_proxy(
                request.agent_id,
                "https://payments.internal/paylinks",
                "paylink_create",
                json.dumps({"amount": amount, "description": "Customer payment request"})
            )
            
            if paylink_fetch.get("status") == "ALLOW":
                paylink = generate_secure_paylink(amount, "Customer payment request")
                llm_answer = f"🔗 I've created a secure payment link for ${amount:,.2f}. "
                llm_answer += f"Link: {paylink['url']} (expires in 1 hour)"
            else:
                llm_answer = "❌ Unable to create secure payment link at this time."
        else:
            llm_answer = "Please specify an amount for the secure payment link. For example: 'Create a secure pay link for $100'"
    
    # Default: Get LLM answer for general queries
    else:
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
        "fetch_attempted": fetch_decision is not None,
        "payment_attempted": payment_result is not None,
        "account_accessed": account_data is not None,
        "request_id": request.request_id
    }
    
    return AgentResponse(
        answer=llm_answer,
        fetch_decision=fetch_decision,
        payment_result=payment_result,
        account_data=account_data,
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