"""
Banking-specific utilities for PAN detection, Luhn validation, and policy enforcement
"""

import re
import json
import random
import time
from typing import Tuple, List, Optional, Dict, Any
from pathlib import Path

# In-memory OTP store (in production, use Redis or similar)
otp_store: Dict[str, Dict[str, Any]] = {}

def load_banking_policy() -> Dict[str, Any]:
    """Load banking policy configuration"""
    policy_path = Path(__file__).parent / "config" / "banking_policy.json"
    try:
        with open(policy_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback default policy
        return {
            "max_prompt_len": 10000,
            "jailbreak_phrases": ["ignore previous", "reveal system prompt"],
            "forbidden_in_chat": {"pan": True, "cvv": True},
            "safe_paths": ["accounts.read", "transactions.read"],
            "payment_limits": {"max_amount": 5000, "preapproved_only": True},
            "rbac": {"DEMO-KEY": ["cust-support-bot"]},
            "otp_settings": {"expiry_seconds": 300, "max_attempts": 3, "code_length": 6}
        }

def luhn_check(card_number: str) -> bool:
    """
    Validate credit card number using Luhn algorithm
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

def detect_pan_in_text(text: str) -> List[str]:
    """
    Detect Primary Account Numbers (PAN) in text using regex + Luhn validation
    Returns list of detected PANs
    """
    # Regex for potential card numbers (13-19 digits, with optional spaces/dashes)
    pan_patterns = [
        r'\b(?:\d{4}[-\s]?){3}\d{1,4}\b',  # 4-4-4-4 format
        r'\b\d{13,19}\b'  # Continuous digits
    ]
    
    detected_pans = []
    
    for pattern in pan_patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            potential_pan = re.sub(r'[-\s]', '', match.group())
            if luhn_check(potential_pan):
                detected_pans.append(potential_pan)
    
    return detected_pans

def detect_cvv_in_text(text: str) -> List[str]:
    """
    Detect CVV codes in text (3-4 digits often near card numbers)
    """
    cvv_patterns = [
        r'\bcvv\s*:?\s*(\d{3,4})\b',
        r'\bcvc\s*:?\s*(\d{3,4})\b',
        r'\bsecurity\s+code\s*:?\s*(\d{3,4})\b'
    ]
    
    detected_cvvs = []
    
    for pattern in cvv_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            detected_cvvs.append(match.group(1))
    
    return detected_cvvs

def detect_ssn_in_text(text: str) -> List[str]:
    """
    Detect Social Security Numbers in text
    """
    ssn_patterns = [
        r'\b\d{3}-\d{2}-\d{4}\b',  # XXX-XX-XXXX
        r'\b\d{9}\b'  # XXXXXXXXX (9 consecutive digits)
    ]
    
    detected_ssns = []
    
    for pattern in ssn_patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            detected_ssns.append(match.group())
    
    return detected_ssns

def redact_sensitive_data(text: str) -> Tuple[str, List[str]]:
    """
    Redact sensitive data from text and return cleaned text + list of redaction types
    """
    redacted_text = text
    redactions = []
    
    # Redact PANs
    pans = detect_pan_in_text(text)
    if pans:
        redactions.append("pan")
        for pan in pans:
            # Replace with masked version (show first 4 and last 4 digits)
            if len(pan) >= 8:
                masked = pan[:4] + "*" * (len(pan) - 8) + pan[-4:]
            else:
                masked = "*" * len(pan)
            redacted_text = redacted_text.replace(pan, f"[REDACTED-PAN:{masked}]")
    
    # Redact CVVs
    cvvs = detect_cvv_in_text(text)
    if cvvs:
        redactions.append("cvv")
        for cvv in cvvs:
            redacted_text = re.sub(
                rf'\bcvv\s*:?\s*{re.escape(cvv)}\b',
                '[REDACTED-CVV]',
                redacted_text,
                flags=re.IGNORECASE
            )
    
    # Redact SSNs
    ssns = detect_ssn_in_text(text)
    if ssns:
        redactions.append("ssn")
        for ssn in ssns:
            redacted_text = redacted_text.replace(ssn, "[REDACTED-SSN]")
    
    return redacted_text, redactions

def generate_otp_code(length: int = 6) -> str:
    """Generate a random OTP code"""
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])

def store_otp(challenge_id: str, code: str, expiry_seconds: int = 300) -> None:
    """Store OTP in memory with expiry"""
    otp_store[challenge_id] = {
        "code": code,
        "created_at": time.time(),
        "expires_at": time.time() + expiry_seconds,
        "attempts": 0,
        "verified": False
    }

def verify_otp(challenge_id: str, provided_code: str, max_attempts: int = 3) -> Tuple[bool, str]:
    """
    Verify OTP code
    Returns (success, reason)
    """
    if challenge_id not in otp_store:
        return False, "invalid_challenge_id"
    
    otp_data = otp_store[challenge_id]
    
    # Check expiry
    if time.time() > otp_data["expires_at"]:
        del otp_store[challenge_id]
        return False, "expired"
    
    # Check attempts
    if otp_data["attempts"] >= max_attempts:
        del otp_store[challenge_id]
        return False, "max_attempts_exceeded"
    
    # Increment attempts
    otp_data["attempts"] += 1
    
    # Check code
    if otp_data["code"] == provided_code:
        otp_data["verified"] = True
        return True, "verified"
    else:
        return False, "invalid_code"

def is_payment_request(user_text: str) -> bool:
    """
    Detect if user text is requesting a payment/transfer
    """
    payment_keywords = [
        "wire", "transfer", "send money", "pay", "payment", 
        "send $", "wire $", "transfer $", "pay $"
    ]
    
    text_lower = user_text.lower()
    return any(keyword in text_lower for keyword in payment_keywords)

def extract_payment_details(user_text: str) -> Dict[str, Any]:
    """
    Extract payment amount and payee from user text
    Returns dict with amount, payee, currency
    """
    # Extract amount (supports $500, $1,000.50, 500 USD, etc.)
    amount_patterns = [
        r'\$([0-9,]+(?:\.[0-9]{2})?)',  # $500, $1,000.50
        r'([0-9,]+(?:\.[0-9]{2})?)\s*(?:USD|dollars?)',  # 500 USD, 500 dollars
        r'([0-9,]+(?:\.[0-9]{2})?)\s*\$'  # 500$
    ]
    
    amount = None
    for pattern in amount_patterns:
        match = re.search(pattern, user_text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                amount = float(amount_str)
                break
            except ValueError:
                continue
    
    # Extract payee (look for "to [NAME]" patterns)
    payee_patterns = [
        r'to\s+([A-Z][A-Z\s&\.,]+?)(?:\s|$|[^A-Za-z])',
        r'wire\s+.*?to\s+([A-Z][A-Z\s&\.,]+?)(?:\s|$|[^A-Za-z])',
        r'pay\s+([A-Z][A-Z\s&\.,]+?)(?:\s|$|[^A-Za-z])'
    ]
    
    payee = None
    for pattern in payee_patterns:
        match = re.search(pattern, user_text, re.IGNORECASE)
        if match:
            payee = match.group(1).strip()
            # Clean up common endings
            payee = re.sub(r'\s+(LLC|Inc|Corp|Co)\.?$', r' \1', payee, flags=re.IGNORECASE)
            break
    
    return {
        "amount": amount,
        "payee": payee,
        "currency": "USD"
    }

def cleanup_expired_otps() -> None:
    """Clean up expired OTP entries"""
    current_time = time.time()
    expired_keys = [
        key for key, data in otp_store.items()
        if current_time > data["expires_at"]
    ]
    for key in expired_keys:
        del otp_store[key]