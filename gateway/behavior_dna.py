"""
ShieldForce AI - Behavior DNA Engine
Learn normal patterns and detect anomalies
"""

from collections import defaultdict
from datetime import datetime
from urllib.parse import urlparse


def extract_domain(url: str) -> str:
    """Extract domain from URL"""
    try:
        parsed = urlparse(url)
        return parsed.netloc or parsed.path.split('/')[0]
    except:
        return url


class BehaviorDNAEngine:
    """
    Track and analyze agent behavior patterns
    """
    
    def __init__(self):
        # Per-agent baselines
        self.baselines = {}
        
        # Thresholds
        self.min_samples_for_baseline = 10
        self.frequency_spike_threshold = 5.0  # 5x average
        self.hour_deviation_threshold = 3  # ±3 hours
        self.payload_spike_threshold = 3.0  # 3x max seen
    
    def analyze(
        self,
        agent_id: str,
        url: str,
        method: str,
        body_size: int,
        timestamp: float
    ) -> tuple[float, list[str]]:
        """
        Analyze request against agent's baseline
        
        Args:
            agent_id: Agent identifier
            url: Request URL
            method: HTTP method
            body_size: Size of request body
            timestamp: Request timestamp
            
        Returns:
            (anomaly_score, reasons)
        """
        
        # Initialize baseline if new agent
        if agent_id not in self.baselines:
            self.baselines[agent_id] = {
                "samples": 0,
                "avg_payload_size": 0,
                "max_payload_size": 0,
                "avg_requests_per_min": 0,
                "avg_active_hour": 0,
                "known_domains": set(),
                "known_apis": set(),
                "last_request_ts": 0,
                "request_timestamps": []
            }
        
        baseline = self.baselines[agent_id]
        score = 0.0
        reasons = []
        
        # Extract domain and API signature
        domain = extract_domain(url)
        api_sig = f"{method}:{domain}"
        
        # ============================================
        # ANOMALY DETECTION (only after min samples)
        # ============================================
        
        if baseline["samples"] >= self.min_samples_for_baseline:
            
            # Check 1: New domain
            if domain not in baseline["known_domains"]:
                score += 30
                reasons.append(f"new_domain:{domain}")
            
            # Check 2: New API endpoint
            if api_sig not in baseline["known_apis"]:
                score += 20
                reasons.append(f"new_api:{api_sig}")
            
            # Check 3: Payload size spike
            if baseline["max_payload_size"] > 0:
                if body_size > baseline["max_payload_size"] * self.payload_spike_threshold:
                    score += 20
                    reasons.append("oversized_payload")
            
            # Check 4: Frequency spike
            if len(baseline["request_timestamps"]) > 5:
                recent_requests = [
                    ts for ts in baseline["request_timestamps"]
                    if timestamp - ts < 60  # Last minute
                ]
                current_freq = len(recent_requests)
                
                if baseline["avg_requests_per_min"] > 0:
                    if current_freq > baseline["avg_requests_per_min"] * self.frequency_spike_threshold:
                        score += 25
                        reasons.append("frequency_spike")
            
            # Check 5: Odd hour (after enough samples)
            if baseline["samples"] >= 15:
                current_hour = datetime.fromtimestamp(timestamp).hour
                avg_hour = baseline["avg_active_hour"]
                
                hour_diff = abs(current_hour - avg_hour)
                # Handle wrap-around (e.g., 23 vs 1)
                if hour_diff > 12:
                    hour_diff = 24 - hour_diff
                
                if hour_diff > self.hour_deviation_threshold:
                    score += 10
                    reasons.append("unusual_hour")
        
        # ============================================
        # UPDATE BASELINE
        # ============================================
        
        baseline["samples"] += 1
        
        # Update payload stats
        baseline["avg_payload_size"] = (
            (baseline["avg_payload_size"] * (baseline["samples"] - 1) + body_size)
            / baseline["samples"]
        )
        baseline["max_payload_size"] = max(baseline["max_payload_size"], body_size)
        
        # Update known domains and APIs
        baseline["known_domains"].add(domain)
        baseline["known_apis"].add(api_sig)
        
        # Update timestamps
        baseline["request_timestamps"].append(timestamp)
        # Keep only last 100 timestamps
        if len(baseline["request_timestamps"]) > 100:
            baseline["request_timestamps"] = baseline["request_timestamps"][-100:]
        
        # Update frequency
        if baseline["last_request_ts"] > 0:
            time_diff_min = (timestamp - baseline["last_request_ts"]) / 60
            if time_diff_min > 0:
                current_freq = 1 / time_diff_min
                baseline["avg_requests_per_min"] = (
                    (baseline["avg_requests_per_min"] * 0.9 + current_freq * 0.1)
                )
        
        baseline["last_request_ts"] = timestamp
        
        # Update active hour
        current_hour = datetime.fromtimestamp(timestamp).hour
        if baseline["avg_active_hour"] == 0:
            baseline["avg_active_hour"] = current_hour
        else:
            # Exponential moving average
            baseline["avg_active_hour"] = (
                baseline["avg_active_hour"] * 0.9 + current_hour * 0.1
            )
        
        return min(score, 50.0), reasons  # Cap at 50 points
    
    def get_baseline(self, agent_id: str) -> dict:
        """
        Get baseline for an agent
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Baseline dictionary
        """
        return self.baselines.get(agent_id, {})
    
    def reset_baseline(self, agent_id: str):
        """
        Reset baseline for an agent
        
        Args:
            agent_id: Agent identifier
        """
        if agent_id in self.baselines:
            del self.baselines[agent_id]
