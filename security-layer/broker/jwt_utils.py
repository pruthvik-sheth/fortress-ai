"""
ShieldForce AI - JWT Capability Tokens
Issue and verify capability-based access tokens
"""

import jwt
import time
from datetime import datetime, timedelta


class CapabilityTokenManager:
    """
    Manage JWT capability tokens for agent authorization
    """
    
    def __init__(self, secret: str):
        """
        Initialize token manager
        
        Args:
            secret: JWT signing secret (HS256)
        """
        self.secret = secret
        self.algorithm = "HS256"
        self.token_ttl = 300  # 5 minutes
    
    def issue_token(
        self,
        agent_id: str,
        allowed_tools: list[str],
        data_scope: list[str],
        budgets: dict
    ) -> str:
        """
        Issue a capability token for an agent
        
        Args:
            agent_id: Agent identifier
            allowed_tools: List of tools agent can use
            data_scope: List of data scopes agent can access
            budgets: Resource budgets (max_tokens, max_tool_calls)
            
        Returns:
            JWT token string
        """
        now = int(time.time())
        
        payload = {
            "iss": "broker",
            "aud": "agent",
            "sub": agent_id,
            "tools": allowed_tools,
            "scopes": data_scope,
            "budgets": budgets,
            "iat": now,
            "exp": now + self.token_ttl
        }
        
        token = jwt.encode(payload, self.secret, algorithm=self.algorithm)
        return token
    
    def verify_token(self, token: str) -> dict | None:
        """
        Verify and decode a capability token
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded payload if valid, None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                audience="agent",
                issuer="broker"
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def get_token_info(self, token: str) -> dict:
        """
        Get token information without verification (for logging)
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded payload (unverified)
        """
        try:
            payload = jwt.decode(
                token,
                options={"verify_signature": False}
            )
            return payload
        except:
            return {}
