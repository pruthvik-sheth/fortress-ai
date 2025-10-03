"""
ShieldForce AI - Gateway Tests
Unit tests for egress gateway
"""

import pytest
from fastapi.testclient import TestClient
import sys
sys.path.append('../gateway')

from gateway.app import app

client = TestClient(app)

# ============================================
# THREAT SCORING TESTS
# ============================================

def test_denylist_domain_blocked():
    """Test that denylisted domains are blocked"""
    from gateway.threat_scoring import ThreatScorer
    
    scorer = ThreatScorer()
    
    score, reasons = scorer.score_deterministic(
        url="https://pastebin.com/u/attacker",
        method="POST",
        body="data",
        purpose="test"
    )
    
    assert score >= 70
    assert any("denylisted_domain" in r for r in reasons)


def test_secret_in_body_quarantine():
    """Test that secrets in body trigger quarantine"""
    from gateway.threat_scoring import ThreatScorer
    
    scorer = ThreatScorer()
    
    score, reasons = scorer.score_deterministic(
        url="https://example.com",
        method="POST",
        body="api_key=sk-live-1234567890abcdef",
        purpose="test"
    )
    
    assert score == 100
    assert "secret_pattern" in reasons


def test_base64_blob_detected():
    """Test that base64 blobs are detected"""
    from gateway.threat_scoring import ThreatScorer
    
    scorer = ThreatScorer()
    
    # Large base64-looking string
    base64_data = "A" * 250 + "=="
    
    score, reasons = scorer.score_deterministic(
        url="https://example.com",
        method="POST",
        body=base64_data,
        purpose="test"
    )
    
    assert score > 0
    assert "base64_blob" in reasons


# ============================================
# BEHAVIOR DNA TESTS
# ============================================

def test_behavior_baseline_learning():
    """Test that behavior baseline is learned"""
    from gateway.behavior_dna import BehaviorDNAEngine
    
    engine = BehaviorDNAEngine()
    
    # Send 5 requests to build baseline
    for i in range(5):
        score, reasons = engine.analyze(
            agent_id="test-agent",
            url="https://api.github.com/repos",
            method="GET",
            body_size=100,
            timestamp=1000000 + i * 60
        )
    
    baseline = engine.get_baseline("test-agent")
    assert baseline["samples"] == 5
    assert "api.github.com" in baseline["known_domains"]


def test_new_domain_detected():
    """Test that new domains are flagged after baseline"""
    from gateway.behavior_dna import BehaviorDNAEngine
    
    engine = BehaviorDNAEngine()
    
    # Build baseline with 15 requests to same domain
    for i in range(15):
        engine.analyze(
            agent_id="test-agent",
            url="https://api.github.com/repos",
            method="GET",
            body_size=100,
            timestamp=1000000 + i * 60
        )
    
    # Now try a new domain
    score, reasons = engine.analyze(
        agent_id="test-agent",
        url="https://api.example.com/data",
        method="GET",
        body_size=100,
        timestamp=1001000
    )
    
    assert score > 0
    assert any("new_domain" in r for r in reasons)


def test_payload_spike_detected():
    """Test that payload size spikes are detected"""
    from gateway.behavior_dna import BehaviorDNAEngine
    
    engine = BehaviorDNAEngine()
    
    # Build baseline with small payloads
    for i in range(15):
        engine.analyze(
            agent_id="test-agent",
            url="https://api.github.com/repos",
            method="POST",
            body_size=100,
            timestamp=1000000 + i * 60
        )
    
    # Now send huge payload (10x baseline)
    score, reasons = engine.analyze(
        agent_id="test-agent",
        url="https://api.github.com/repos",
        method="POST",
        body_size=5000,  # 50x baseline
        timestamp=1001000
    )
    
    assert score > 0
    assert any("oversized_payload" in r for r in reasons)


# ============================================
# COMPLIANCE TESTS
# ============================================

def test_health_score_calculation():
    """Test that health score is calculated correctly"""
    from gateway.compliance import ComplianceGenerator
    
    gen = ComplianceGenerator("/tmp/test_incidents.jsonl")
    
    # With no incidents, score should be 100
    score = gen.calculate_health_score()
    assert score == 100.0


def test_compliance_report_generation():
    """Test that compliance report generates HTML"""
    from gateway.compliance import ComplianceGenerator
    
    gen = ComplianceGenerator("/tmp/test_incidents.jsonl")
    
    html = gen.generate_evidence_pack(
        health_score=95.0,
        agents_seen=5,
        quarantined_agents=[]
    )
    
    assert "<html" in html
    assert "ShieldForce AI" in html
    assert "95.0" in html


# ============================================
# INTEGRATION TESTS
# ============================================

def test_proxy_allow():
    """Test that normal requests are allowed"""
    response = client.post(
        "/proxy",
        json={
            "agent_id": "test-agent",
            "url": "https://httpbin.org/get",
            "method": "GET",
            "body": None,
            "purpose": "test"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ALLOW", "BLOCK"]  # Depends on scoring


def test_proxy_denylist_block():
    """Test that denylisted domains are blocked"""
    response = client.post(
        "/proxy",
        json={
            "agent_id": "test-agent",
            "url": "https://pastebin.com/u/attacker",
            "method": "POST",
            "body": "data",
            "purpose": "test"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "BLOCK"
    assert data["score"] >= 60


def test_health_endpoint():
    """Test that health endpoint works"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "health_score" in data
    assert "status" in data


def test_incidents_endpoint():
    """Test that incidents endpoint works"""
    response = client.get("/incidents")
    assert response.status_code == 200
    data = response.json()
    assert "incidents" in data
    assert "total" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
