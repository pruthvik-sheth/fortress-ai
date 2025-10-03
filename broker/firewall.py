"""
ShieldForce AI - Ingress Firewall
Prompt injection detection and input validation
"""

import re
import os
import time
from typing import Dict, Optional

# LLM imports (optional - fail gracefully if not available)
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("⚠️  LLM dependencies not available. Running in regex-only mode.")

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


class LLMClassifier:
    """
    PromptShield LLM-based semantic prompt injection detector
    """
    
    def __init__(self, model_name: str = "sumitranjan/PromptShield"):
        """Initialize LLM classifier"""
        self.model = None
        self.tokenizer = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.enabled = False
        
        if not LLM_AVAILABLE:
            print("⚠️  LLM classifier disabled - dependencies not available")
            return
        
        try:
            print(f"🤖 Loading PromptShield model: {model_name} on {self.device}...")
            
            # Load tokenizer and model
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
            self.model.to(self.device)
            self.model.eval()
            
            self.enabled = True
            print(f"✅ PromptShield ready on {self.device}")
            
        except Exception as e:
            print(f"⚠️  Failed to load LLM classifier: {e}")
            print("   Falling back to regex-only mode")
            self.enabled = False
    
    def analyze(self, text: str, timeout_ms: int = 100) -> Dict:
        """
        Analyze text for prompt injection using PromptShield
        
        Args:
            text: User input to analyze
            timeout_ms: Maximum inference time (milliseconds)
            
        Returns:
            {
                "is_safe": bool,
                "confidence": float,
                "inference_time_ms": float,
                "timeout": bool
            }
        """
        if not self.enabled:
            return {"is_safe": True, "confidence": 0.0, "inference_time_ms": 0.0, "timeout": False}
        
        start_time = time.time()
        
        try:
            # Tokenize input
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            ).to(self.device)
            
            # Run inference
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                probs = torch.softmax(logits, dim=-1)
            
            # Get prediction (0=safe, 1=unsafe)
            predicted_class = torch.argmax(probs, dim=-1).item()
            confidence = probs[0][predicted_class].item()
            
            inference_time_ms = (time.time() - start_time) * 1000
            
            # Check timeout
            if inference_time_ms > timeout_ms:
                print(f"⚠️  LLM inference timeout: {inference_time_ms:.1f}ms")
                return {
                    "is_safe": True,  # Fail open
                    "confidence": 0.0,
                    "inference_time_ms": inference_time_ms,
                    "timeout": True
                }
            
            # 0=safe, 1=unsafe
            is_safe = (predicted_class == 0)
            
            return {
                "is_safe": is_safe,
                "confidence": confidence,
                "inference_time_ms": inference_time_ms,
                "timeout": False
            }
            
        except Exception as e:
            print(f"❌ LLM classifier error: {e}")
            # Fail open (allow request) on error
            return {
                "is_safe": True,
                "confidence": 0.0,
                "inference_time_ms": (time.time() - start_time) * 1000,
                "error": str(e)
            }


class PromptFirewall:
    """
    Multi-layer firewall for detecting and blocking malicious prompts
    Layer 1: Fast regex patterns (1-2ms)
    Layer 2: LLM semantic analysis (30-50ms)
    """
    
    def __init__(self, enable_llm: bool = True):
        self.max_payload_size = 10_000  # 10KB max
        self.blocked_html_tags = ['<script>', '<iframe>', '<object>', '<embed>']
        
        # Initialize LLM classifier
        self.llm_classifier = None
        if enable_llm and LLM_AVAILABLE:
            self.llm_classifier = LLMClassifier()
        else:
            print("🔥 Firewall running in regex-only mode")
    
    def check(self, user_text: str) -> tuple[bool, str | None, list[str], dict]:
        """
        Multi-layer safety check
        
        Args:
            user_text: User input to validate
            
        Returns:
            (is_safe, block_reason, redactions, llm_result)
            - is_safe: True if safe to proceed
            - block_reason: Reason for blocking (if blocked)
            - redactions: List of redaction types applied
            - llm_result: LLM analysis results (for logging)
        """
        checks_fired = []
        llm_result = {}
        
        # ============================================
        # LAYER 1: FAST HEURISTICS (1-2ms)
        # ============================================
        
        # Check 1: Payload size
        if len(user_text) > self.max_payload_size:
            return False, "payload_too_large", [], llm_result
        
        # Check 2: Jailbreak/prompt injection (regex)
        is_jailbreak, matched_phrase = contains_jailbreak(user_text)
        if is_jailbreak:
            checks_fired.append(f"jailbreak:{matched_phrase}")
            return False, "instruction_override", [], llm_result
        
        # Check 3: HTML injection
        for tag in self.blocked_html_tags:
            if tag.lower() in user_text.lower():
                checks_fired.append(f"html_injection:{tag}")
                return False, "html_injection", [], llm_result
        
        # ============================================
        # LAYER 2: LLM SEMANTIC ANALYSIS (30-50ms)
        # ============================================
        
        if self.llm_classifier and self.llm_classifier.enabled:
            llm_result = self.llm_classifier.analyze(user_text, timeout_ms=2000)
            
            # Block if LLM detects unsafe content
            if not llm_result.get("is_safe", True):
                return False, "semantic_injection", [], llm_result
        
        # ============================================
        # LAYER 3: SECRET REDACTION (always last)
        # ============================================
        
        # Redact secrets (don't block, just mask)
        masked_text, redactions = mask_secrets(user_text)
        
        # All checks passed
        return True, None, redactions, llm_result
    
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
