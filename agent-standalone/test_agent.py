#!/usr/bin/env python3
"""
Simple test script for the agent
"""
import requests
import json

def test_agent():
    base_url = "http://localhost:7000"
    
    print("🧪 Testing Agent...")
    
    # Test 1: Health check
    try:
        response = requests.get(f"{base_url}/health")
        print(f"✅ Health Check: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"❌ Health Check Failed: {e}")
        return
    
    # Test 2: Simple question
    try:
        test_data = {
            "purpose": "test_connection",
            "user_text": "Hello! Are you working with Claude API?",
            "allowed_tools": []
        }
        
        response = requests.post(
            f"{base_url}/test",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"\n✅ Simple Test: {response.status_code}")
        result = response.json()
        print(f"   Answer: {result.get('answer', 'No answer')}")
        print(f"   Logs: {result.get('logs', {})}")
        
    except Exception as e:
        print(f"❌ Simple Test Failed: {e}")
    
    # Test 3: FETCH request
    try:
        fetch_data = {
            "purpose": "web_research",
            "user_text": "FETCH https://api.github.com/users/octocat",
            "allowed_tools": ["http.fetch"]
        }
        
        response = requests.post(
            f"{base_url}/test",
            json=fetch_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"\n✅ FETCH Test: {response.status_code}")
        result = response.json()
        print(f"   Answer: {result.get('answer', 'No answer')}")
        print(f"   Fetch Decision: {result.get('fetch_decision', 'None')}")
        
    except Exception as e:
        print(f"❌ FETCH Test Failed: {e}")

if __name__ == "__main__":
    test_agent()