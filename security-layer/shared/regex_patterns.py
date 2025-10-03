"""
ShieldForce AI - Regex Patterns for Secret Detection
Patterns for detecting sensitive data in requests/responses
"""

import re

# AWS Access Keys
AWS_KEY_PATTERN = re.compile(r'AKIA[0-9A-Z]{16}')

# Generic API Keys and Tokens
API_KEY_PATTERN = re.compile(r'(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*["\']?([A-Za-z0-9_\-]{12,})["\']?')

# Private Keys (PEM format)
PEM_PATTERN = re.compile(r'-----BEGIN (?:RSA )?PRIVATE KEY-----')

# Base64 encoded blobs (potential data exfiltration)
BASE64_BLOB_PATTERN = re.compile(r'([A-Za-z0-9+/]{200,}={0,2})')

# JWT tokens
JWT_PATTERN = re.compile(r'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+')

# Credit card numbers (basic pattern)
CREDIT_CARD_PATTERN = re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b')

# Email addresses (PII)
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

# Phone numbers (basic US format)
PHONE_PATTERN = re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b')

# Social Security Numbers
SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')

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


def mask_secrets(text: str) -> tuple[str, list[str]]:
    """
    Mask secrets in text and return masked text + list of redaction types
    
    Args:
        text: Input text to scan
        
    Returns:
        (masked_text, redactions) where redactions is list of types found
    """
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
    
    # Credit Cards
    if CREDIT_CARD_PATTERN.search(masked):
        masked = CREDIT_CARD_PATTERN.sub('[REDACTED_CC]', masked)
        redactions.append('credit_card')
    
    # Emails (optional - might be legitimate)
    # if EMAIL_PATTERN.search(masked):
    #     masked = EMAIL_PATTERN.sub('[REDACTED_EMAIL]', masked)
    #     redactions.append('email')
    
    return masked, redactions


def contains_secrets(text: str) -> bool:
    """
    Quick check if text contains any secrets
    
    Args:
        text: Input text to scan
        
    Returns:
        True if secrets found
    """
    patterns = [
        AWS_KEY_PATTERN,
        API_KEY_PATTERN,
        PEM_PATTERN,
        JWT_PATTERN,
    ]
    
    return any(pattern.search(text) for pattern in patterns)


def contains_jailbreak(text: str) -> tuple[bool, str | None]:
    """
    Check if text contains jailbreak/prompt injection attempts
    
    Args:
        text: Input text to scan
        
    Returns:
        (is_jailbreak, matched_phrase)
    """
    text_lower = text.lower()
    
    for phrase in JAILBREAK_PHRASES:
        if phrase in text_lower:
            return True, phrase
    
    return False, None


def contains_base64_blob(text: str) -> bool:
    """
    Check if text contains large base64 encoded data (potential exfiltration)
    
    Args:
        text: Input text to scan
        
    Returns:
        True if large base64 blob found
    """
    return BASE64_BLOB_PATTERN.search(text) is not None


def extract_domain(url: str) -> str:
    """
    Extract domain from URL
    
    Args:
        url: Full URL
        
    Returns:
        Domain name (e.g., "api.github.com")
    """
    from urllib.parse import urlparse
    
    try:
        parsed = urlparse(url)
        return parsed.netloc or parsed.path.split('/')[0]
    except:
        return url
