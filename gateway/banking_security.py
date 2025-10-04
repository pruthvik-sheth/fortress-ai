"""
Banking-specific security functions for the Gateway
"""

import re
import json
import hashlib
from pathlib import Path
from typing import List, Tuple, Dict, Any
from urllib.parse import urlparse

def load_banking_network_config() -> Dict[str, Any]:
    """Load banking network configuration"""
    config_path = Path(__file__).parent / "config" / "banking_network.json"
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback default config
        return {
            "mode": "deny_by_default",
            "allowlist": ["core-banking.internal", "payments.internal"],
            "denylist": ["pastebin.com", "filebin.net", "ipfs.io"],
            "email_apis": ["api.sendgrid.com", "smtp.gmail.com"]
        }

def luhn_check_gateway(card_number: str) -> bool:
    """
    Validate credit card number using Luhn algorithm (Gateway version)
    """
    # Remove spaces and non-digits
    card_number = re.sub(r'\D', '', card_number)
    
    if len(card_number) < 13 or len(card_number) > 19:
        return False
    
    # Luhn algorithm
    total = 0
    reverse_digits = card_number[::-1]
    
    for i, digit in enumerate(reverse_digits):
        n = int(digit)
        if i % 2 == 1:  # Every second digit from right
            n *= 2
            if n > 9:
                n = n // 10 + n % 10
        total += n
    
    return total % 10 == 0

def detect_pan_in_body(text: str) -> List[str]:
    """
    Detect Primary Account Numbers (PAN) in request/response body
    """
    # Regex for potential card numbers
    pan_patterns = [
        r'\b(?:\d{4}[-\s]?){3}\d{1,4}\b',  # 4-4-4-4 format
        r'\b\d{13,19}\b'  # Continuous digits
    ]
    
    detected_pans = []
    
    for pattern in pan_patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            potential_pan = re.sub(r'[-\s]', '', match.group())
            if luhn_check_gateway(potential_pan):
                detected_pans.append(potential_pan)
    
    return detected_pans

def detect_ssn_in_body(text: str) -> List[str]:
    """
    Detect Social Security Numbers in body
    """
    ssn_patterns = [
        r'\b\d{3}-\d{2}-\d{4}\b',  # XXX-XX-XXXX
        r'\b\d{9}\b'  # XXXXXXXXX (9 consecutive digits)
    ]
    
    detected_ssns = []
    
    for pattern in ssn_patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            ssn = match.group()
            # Basic validation - not all 9-digit numbers are SSNs
            if len(ssn) == 9 and not ssn.startswith('000') and not ssn.startswith('666'):
                detected_ssns.append(ssn)
            elif '-' in ssn:  # Formatted SSN
                detected_ssns.append(ssn)
    
    return detected_ssns

def detect_iban_in_body(text: str) -> List[str]:
    """
    Detect International Bank Account Numbers (IBAN)
    """
    # IBAN pattern: 2 letters + 2 digits + up to 30 alphanumeric
    iban_pattern = r'\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b'
    
    detected_ibans = []
    matches = re.finditer(iban_pattern, text)
    
    for match in matches:
        iban = match.group()
        # Basic length validation (IBANs are typically 15-34 characters)
        if 15 <= len(iban) <= 34:
            detected_ibans.append(iban)
    
    return detected_ibans

def detect_api_keys_in_body(text: str) -> List[str]:
    """
    Detect API keys and tokens in body
    """
    api_key_patterns = [
        r'(?:api[_-]?key|apikey|token|secret)["\s]*[:=]["\s]*([a-zA-Z0-9_-]{20,})',
        r'\bsk-[a-zA-Z0-9]{20,}\b',  # Stripe-style keys
        r'\bpk_[a-zA-Z0-9]{20,}\b',  # Public keys
        r'\bAKIA[0-9A-Z]{16}\b',     # AWS access keys
        r'\bghp_[a-zA-Z0-9]{36}\b'   # GitHub personal access tokens
    ]
    
    detected_keys = []
    
    for pattern in api_key_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            if match.groups():
                detected_keys.append(match.group(1))
            else:
                detected_keys.append(match.group())
    
    return detected_keys

def detect_private_keys_in_body(text: str) -> List[str]:
    """
    Detect private keys and certificates in body
    """
    private_key_patterns = [
        r'-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----',
        r'-----BEGIN RSA PRIVATE KEY-----.*?-----END RSA PRIVATE KEY-----',
        r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----'
    ]
    
    detected_keys = []
    
    for pattern in private_key_patterns:
        matches = re.finditer(pattern, text, re.DOTALL)
        for match in matches:
            detected_keys.append("private_key")  # Don't store the actual key
    
    return detected_keys

def check_domain_policy(url: str, network_config: Dict[str, Any]) -> Tuple[str, str]:
    """
    Check if domain is allowed based on banking network policy
    Returns (decision, reason)
    """
    try:
        domain = urlparse(url).netloc.lower()
    except:
        return "BLOCK", "invalid_url"
    
    # Check denylist first
    denylist = network_config.get("denylist", [])
    if domain in denylist:
        return "BLOCK", f"denylisted_domain: {domain}"
    
    # Check email APIs (also blocked for banking)
    email_apis = network_config.get("email_apis", [])
    if domain in email_apis:
        return "BLOCK", f"email_api_blocked: {domain}"
    
    # Check allowlist
    allowlist = network_config.get("allowlist", [])
    mode = network_config.get("mode", "deny_by_default")
    
    if mode == "deny_by_default":
        if domain in allowlist:
            return "ALLOW", f"allowlisted_domain: {domain}"
        else:
            return "BLOCK", f"not_allowlisted: {domain}"
    else:
        # Allow by default mode (not recommended for banking)
        return "ALLOW", "default_allow"

def scan_for_sensitive_data(text: str) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    Comprehensive scan for sensitive data in text
    Returns (detected_types, details)
    """
    detected_types = []
    details = {}
    
    # Check for PANs
    pans = detect_pan_in_body(text)
    if pans:
        detected_types.append("pii_match_pan")
        details["pans"] = [f"****{pan[-4:]}" for pan in pans]  # Masked
    
    # Check for SSNs
    ssns = detect_ssn_in_body(text)
    if ssns:
        detected_types.append("pii_match_ssn")
        details["ssns"] = ["***-**-****" for _ in ssns]  # Masked
    
    # Check for IBANs
    ibans = detect_iban_in_body(text)
    if ibans:
        detected_types.append("pii_match_iban")
        details["ibans"] = [f"{iban[:4]}****{iban[-4:]}" for iban in ibans]  # Masked
    
    # Check for API keys
    api_keys = detect_api_keys_in_body(text)
    if api_keys:
        detected_types.append("pii_match_apikey")
        details["api_keys"] = ["***REDACTED***" for _ in api_keys]
    
    # Check for private keys
    private_keys = detect_private_keys_in_body(text)
    if private_keys:
        detected_types.append("pii_match_privkey")
        details["private_keys"] = ["***REDACTED***" for _ in private_keys]
    
    return detected_types, details

def create_response_hash(content: str) -> str:
    """Create SHA256 hash of response content"""
    return hashlib.sha256(content.encode()).hexdigest()

def create_safe_excerpt(content: str, max_length: int = 200) -> str:
    """Create a safe excerpt of content, removing sensitive data"""
    # Remove potential sensitive patterns before creating excerpt
    safe_content = content
    
    # Replace potential PANs
    safe_content = re.sub(r'\b\d{13,19}\b', '[PAN-REDACTED]', safe_content)
    
    # Replace potential SSNs
    safe_content = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN-REDACTED]', safe_content)
    
    # Replace API keys
    safe_content = re.sub(r'\b[a-zA-Z0-9_-]{20,}\b', '[KEY-REDACTED]', safe_content)
    
    # Truncate to max length
    if len(safe_content) > max_length:
        safe_content = safe_content[:max_length] + "..."
    
    return safe_content