#!/usr/bin/env python3
"""
Test script for FortressAI Banking System
"""

import requests
import json
import time

# Configuration
BROKER_URL = "http://localhost:8001"
GATEWAY_URL = "http://localhost:9000"
API_KEY = "DEMO-KEY"

def test_health_checks():
    """Test system health endpoints"""
    print("🏥 Testing Health Checks...")
    
    # Broker health
    try:
        response = requests.get(f"{BROKER_URL}/health")
        print(f"Broker Health: {response.json()}")
    except Exception as e:
        print(f"Broker Health Error: {e}")
    
    # Gateway health
    try:
        response = requests.get(f"{GATEWAY_URL}/health")
        print(f"Gateway Health: {response.json()}")
    except Exception as e:
        print(f"Gateway Health Error: {e}")

def test_pan_detection():
    """Test PAN detection and blocking"""
    print("\n💳 Testing PAN Detection...")
    
    payload = {
        "agent_id": "cust-support-bot",
        "purpose": "payment_attempt",
        "user_text": "This is my card 4111 1111 1111 1111, cvv 123, run $500",
        "allowed_tools": ["payments.create"],
        "data_scope": ["accounts:owner_only"]
    }
    
    try:
        response = requests.post(
            f"{BROKER_URL}/invoke",
            json=payload,
            headers={"X-API-Key": API_KEY}
        )
        result = response.json()
        print(f"PAN Detection Result: {result}")
        
        if result.get("decision") == "BLOCK" and result.get("reason") == "pan_in_chat":
            print("✅ PAN correctly blocked!")
        else:
            print("❌ PAN detection failed!")
            
    except Exception as e:
        print(f"PAN Test Error: {e}")

def test_otp_flow():
    """Test OTP send and verify"""
    print("\n🔐 Testing OTP Flow...")
    
    # Send OTP
    try:
        otp_send_payload = {
            "phone_number": "+1234567890",
            "purpose": "payment_verification"
        }
        
        response = requests.post(f"{BROKER_URL}/otp/send", json=otp_send_payload)
        otp_result = response.json()
        print(f"OTP Send Result: {otp_result}")
        
        if otp_result.get("sent"):
            challenge_id = otp_result.get("challenge_id")
            print(f"Challenge ID: {challenge_id}")
            
            # Verify OTP (using demo code - in real system, user would provide this)
            verify_payload = {
                "challenge_id": challenge_id,
                "code": "123456"  # Demo code
            }
            
            verify_response = requests.post(f"{BROKER_URL}/otp/verify", json=verify_payload)
            verify_result = verify_response.json()
            print(f"OTP Verify Result: {verify_result}")
            
    except Exception as e:
        print(f"OTP Test Error: {e}")

def test_payment_request():
    """Test legitimate payment request"""
    print("\n💸 Testing Payment Request...")
    
    payload = {
        "agent_id": "cust-support-bot",
        "purpose": "payment_create",
        "user_text": "Wire $500 to ACME LLC",
        "allowed_tools": ["payments.create", "accounts.read"],
        "data_scope": ["accounts:owner_only", "payments:preapproved_only"]
    }
    
    try:
        response = requests.post(
            f"{BROKER_URL}/invoke",
            json=payload,
            headers={"X-API-Key": API_KEY}
        )
        result = response.json()
        print(f"Payment Request Result: {result}")
        
    except Exception as e:
        print(f"Payment Test Error: {e}")

def test_account_inquiry():
    """Test account balance inquiry"""
    print("\n🏦 Testing Account Inquiry...")
    
    payload = {
        "agent_id": "cust-support-bot",
        "purpose": "account_inquiry",
        "user_text": "Show my account balance and last 3 transactions",
        "allowed_tools": ["accounts.read", "transactions.read"],
        "data_scope": ["accounts:owner_only", "transactions:last_90d"]
    }
    
    try:
        response = requests.post(
            f"{BROKER_URL}/invoke",
            json=payload,
            headers={"X-API-Key": API_KEY}
        )
        result = response.json()
        print(f"Account Inquiry Result: {result}")
        
    except Exception as e:
        print(f"Account Test Error: {e}")

def test_data_exfiltration():
    """Test data exfiltration attempt"""
    print("\n🚨 Testing Data Exfiltration Detection...")
    
    # Test via gateway directly
    payload = {
        "agent_id": "cust-support-bot",
        "url": "https://pastebin.com/api",
        "method": "POST",
        "body": "account_data=1234567890&balance=50000",
        "purpose": "data_export"
    }
    
    try:
        response = requests.post(f"{GATEWAY_URL}/proxy", json=payload)
        result = response.json()
        print(f"Exfiltration Test Result: {result}")
        
        if result.get("status") in ["BLOCK", "QUARANTINE"]:
            print("✅ Data exfiltration correctly blocked!")
        else:
            print("❌ Data exfiltration not detected!")
            
    except Exception as e:
        print(f"Exfiltration Test Error: {e}")

def test_compliance_report():
    """Test compliance report generation"""
    print("\n📋 Testing Compliance Report...")
    
    try:
        response = requests.post(f"{GATEWAY_URL}/compliance/generate")
        result = response.json()
        
        if "html" in result:
            print("✅ Compliance report generated successfully!")
            print(f"Report length: {len(result['html'])} characters")
        else:
            print("❌ Compliance report generation failed!")
            
    except Exception as e:
        print(f"Compliance Test Error: {e}")

def main():
    """Run all banking system tests"""
    print("🏦 FortressAI Banking System Test Suite")
    print("=" * 50)
    
    test_health_checks()
    test_pan_detection()
    test_otp_flow()
    test_payment_request()
    test_account_inquiry()
    test_data_exfiltration()
    test_compliance_report()
    
    print("\n" + "=" * 50)
    print("🎉 Banking system tests completed!")

if __name__ == "__main__":
    main()