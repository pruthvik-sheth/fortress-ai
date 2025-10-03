"""
ShieldForce AI - Ingress Firewall
Prompt injection detection and input validation
"""

import re

# ============================================
# REGEX PATTERNS (inlined from shared)
# ============================================

# Prompt injection phrases (case-insensitive)
JAILBREAK_PHRASES = [
    "ignore previous instructions",
    "ignore previous",
    "ignore all previous",
    "disregard previous",
    "forget previous",
    "reveal system prompt",
    "show system prompt",
    "print system prompt",
    "system prompt",
    "show config",
    "dump memory",
    "print your instructions",
    "what are your instructions",
    "disable safety",
    "bypass",
    "jailbreak",
    "sudo mode",
    "developer mode",
    "god mode",
    "admin mode",
    "root access",
]

# AWS Access Keys
AWS_KEY_PATTERN = re.compile(r'AKIA[0-9A-Z]{16}')

# Generic API Keys and Tokens
API_KEY_PATTERN = re.compile(r'(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*["\']?([A-Za-z0-9_\-]{12,})["\']?')

# Private Keys (PEM format)
PEM_PATTERN = re.compile(r'-----BEGIN (?:RSA )?PRIVATE KEY-----')

# JWT tokens
JWT_PATTERN = re.compile(r'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+')


def contains_jailbreak(text: str) -> tuple[bool, str | None]:
    """Check if text contains jailbreak/prompt injection attempts"""
    text_lower = text.lower()
    
    for phrase in JAILBREAK_PHRASES:
        if phrase in text_lower:
            return True, phrase
    
    return False, None


def mask_secrets(text: str) -> tuple[str, list[str]]:
    """Mask secrets in text and return masked text + list of redaction types"""
    redactions = []
    masked = text
    
    # AWS Keys
    if AWS_KEY_PATTERN.search(masked):
        masked = AWS_KEY_PATTERN.sub('[REDACTED_AWS_KEY]', masked)
        redactions.append('aws_key')
    
    # API Keys
    if API_KEY_PATTERN.search(masked):
        masked = API_KEY_PATTERN.sub(r'\1=[REDACTED_API_KEY]', masked)
        redactions.append('api_key')
    
    # Private Keys
    if PEM_PATTERN.search(masked):
        masked = PEM_PATTERN.sub('[REDACTED_PRIVATE_KEY]', masked)
        redactions.append('private_key')
    
    # JWT Tokens
    if JWT_PATTERN.search(masked):
        masked = JWT_PATTERN.sub('[REDACTED_JWT]', masked)
        redactions.append('jwt_token')
    
    return masked, redactions


class PromptFirewall:
    """
    Firewall for detecting and blocking malicious prompts
    """
    
    def __init__(self):
        self.max_payload_size = 10_000  # 10KB max
        self.blocked_html_tags = ['<script>', '<iframe>', '<object>', '<embed>']
    
    def check(self, user_text: str) -> tuple[bool, str | None, list[str]]:
        """
        Check if user text is safe
        
        Args:
            user_text: User input to validate
            
        Returns:
            (is_safe, block_reason, redactions)
            - is_safe: True if safe to proceed
            - block_reason: Reason for blocking (if blocked)
            - redactions: List of redaction types applied
        """
        checks_fired = []
        
        # Check 1: Payload size
        if len(user_text) > self.max_payload_size:
            return False, "payload_too_large", []
        
        # Check 2: Jailbreak/prompt injection
        is_jailbreak, matched_phrase = contains_jailbreak(user_text)
        if is_jailbreak:
            checks_fired.append(f"jailbreak:{matched_phrase}")
            return False, "instruction_override", []
        
        # Check 3: HTML injection
        for tag in self.blocked_html_tags:
            if tag.lower() in user_text.lower():
                checks_fired.append(f"html_injection:{tag}")
                return False, "html_injection", []
        
        # Check 4: Redact secrets (don't block, just mask)
        masked_text, redactions = mask_secrets(user_text)
        
        # All checks passed
        return True, None, redactions
    
    def sanitize(self, user_text: str) -> str:
        """
        Sanitize user text by masking secrets
        
        Args:
            user_text: Input text
            
        Returns:
            Sanitized text with secrets masked
        """
        masked_text, _ = mask_secrets(user_text)
        return masked_text
