"""
ShieldForce AI - Threat Scoring
Deterministic rules for threat detection
"""

import re
from urllib.parse import urlparse

# ============================================
# REGEX PATTERNS (inlined from shared)
# ============================================

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


def contains_secrets(text: str) -> bool:
    """Quick check if text contains any secrets"""
    patterns = [
        AWS_KEY_PATTERN,
        API_KEY_PATTERN,
        PEM_PATTERN,
        JWT_PATTERN,
    ]
    
    return any(pattern.search(text) for pattern in patterns)


def contains_base64_blob(text: str) -> bool:
    """Check if text contains large base64 encoded data (potential exfiltration)"""
    return BASE64_BLOB_PATTERN.search(text) is not None


def extract_domain(url: str) -> str:
    """Extract domain from URL"""
    try:
        parsed = urlparse(url)
        return parsed.netloc or parsed.path.split('/')[0]
    except:
        return url


class ThreatScorer:
    """
    Score threats using deterministic rules
    """
    
    def __init__(self):
        # Denylist of known malicious/exfiltration domains
        self.denylist = {
            "pastebin.com",
            "filebin.net",
            "ipfs.io",
            "transfer.sh",
            "file.io",
            "0x0.st",
            "uguu.se",
            "catbox.moe",
            "anonfiles.com",
            "mega.nz"
        }
        
        # Suspicious TLDs
        self.suspicious_tlds = {".tk", ".ml", ".ga", ".cf", ".gq"}
    
    def score_deterministic(
        self,
        url: str,
        method: str,
        body: str,
        purpose: str
    ) -> tuple[float, list[str]]:
        """
        Score request using deterministic rules
        
        Args:
            url: Request URL
            method: HTTP method
            body: Request body
            purpose: Stated purpose
            
        Returns:
            (score, reasons)
        """
        score = 0.0
        reasons = []
        
        domain = extract_domain(url)
        
        # ============================================
        # RULE 1: DENYLIST DOMAIN
        # ============================================
        
        if domain in self.denylist:
            score += 70
            reasons.append(f"denylisted_domain:{domain}")
        
        # ============================================
        # RULE 2: SUSPICIOUS TLD
        # ============================================
        
        for tld in self.suspicious_tlds:
            if domain.endswith(tld):
                score += 15
                reasons.append(f"suspicious_tld:{tld}")
                break
        
        # ============================================
        # RULE 3: SECRETS IN BODY
        # ============================================
        
        if contains_secrets(body):
            score = 100  # Immediate quarantine
            reasons.append("secret_pattern")
        
        # ============================================
        # RULE 4: BASE64 BLOB (potential exfiltration)
        # ============================================
        
        if contains_base64_blob(body):
            score += 15
            reasons.append("base64_blob")
        
        # ============================================
        # RULE 5: OVERSIZED PAYLOAD
        # ============================================
        
        # This will be checked against baseline in behavior_dna
        # Here we just check absolute size
        if len(body) > 100_000:  # 100KB
            score += 20
            reasons.append("large_payload")
        
        # ============================================
        # RULE 6: SUSPICIOUS METHOD/BODY COMBO
        # ============================================
        
        if method == "GET" and len(body) > 1000:
            score += 10
            reasons.append("get_with_large_body")
        
        # ============================================
        # RULE 7: LOCALHOST/INTERNAL IPS
        # ============================================
        
        if any(x in domain.lower() for x in ["localhost", "127.0.0.1", "0.0.0.0", "192.168.", "10."]):
            score += 25
            reasons.append("internal_ip")
        
        # ============================================
        # RULE 8: SUSPICIOUS PURPOSE
        # ============================================
        
        suspicious_purposes = ["backup", "export", "dump", "exfiltrate", "leak"]
        if any(word in purpose.lower() for word in suspicious_purposes):
            score += 10
            reasons.append("suspicious_purpose")
        
        return min(score, 100.0), reasons
    
    def add_to_denylist(self, domain: str):
        """
        Add domain to denylist
        
        Args:
            domain: Domain to block
        """
        self.denylist.add(domain)
    
    def remove_from_denylist(self, domain: str):
        """
        Remove domain from denylist
        
        Args:
            domain: Domain to unblock
        """
        self.denylist.discard(domain)
