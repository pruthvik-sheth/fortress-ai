"""
Banking-specific agent functionality
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List

def load_preapproved_payees() -> Dict[str, Dict[str, Any]]:
    """Load pre-approved payees configuration"""
    payees_path = Path(__file__).parent / "config" / "preapproved_payees.json"
    try:
        with open(payees_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback default payees
        return {
            "ACME-LLC": {"id": "p_1001", "name": "ACME LLC", "verified": True},
            "UTILS-CO": {"id": "p_1002", "name": "Utilities Co", "verified": True}
        }

def find_payee_by_name(payee_name: str, preapproved_payees: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Find a payee by name (case-insensitive, fuzzy matching)
    """
    payee_name_clean = payee_name.upper().strip()
    
    # Direct match
    if payee_name_clean in preapproved_payees:
        return preapproved_payees[payee_name_clean]
    
    # Fuzzy matching
    for key, payee_data in preapproved_payees.items():
        # Check if the provided name is contained in the key or payee name
        if (payee_name_clean in key or 
            payee_name_clean in payee_data.get("name", "").upper() or
            key in payee_name_clean):
            return payee_data
    
    return None

def validate_payment_request(amount: float, payee_name: str, capabilities: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a payment request against banking policies
    Returns validation result with success/failure and reasons
    """
    result = {
        "valid": False,
        "reasons": [],
        "payee_info": None,
        "amount": amount
    }
    
    # Check if payments.create is in allowed tools
    allowed_tools = capabilities.get("tools", [])
    if "payments.create" not in allowed_tools:
        result["reasons"].append("payments_not_permitted")
        return result
    
    # Load payment policy from capabilities
    payment_policy = capabilities.get("payment_policy", {})
    max_amount = payment_policy.get("max_amount", 5000)
    preapproved_only = payment_policy.get("preapproved_only", True)
    
    # Check amount limit
    if amount > max_amount:
        result["reasons"].append(f"amount_exceeds_limit_{max_amount}")
        return result
    
    # Check if payee is pre-approved (if required)
    if preapproved_only:
        preapproved_payees = load_preapproved_payees()
        payee_info = find_payee_by_name(payee_name, preapproved_payees)
        
        if not payee_info:
            result["reasons"].append("payee_not_preapproved")
            return result
        
        result["payee_info"] = payee_info
    
    # All checks passed
    result["valid"] = True
    return result

def format_account_balance(balance: float, currency: str = "USD") -> str:
    """Format account balance for display"""
    return f"${balance:,.2f} {currency}"

def format_transaction_list(transactions: List[Dict[str, Any]]) -> str:
    """Format transaction list for display"""
    if not transactions:
        return "No recent transactions found."
    
    formatted = "Recent Transactions:\n"
    for i, txn in enumerate(transactions[:5], 1):  # Show last 5
        date = txn.get("date", "Unknown")
        description = txn.get("description", "Unknown")
        amount = txn.get("amount", 0)
        txn_type = txn.get("type", "unknown")
        
        sign = "-" if txn_type == "debit" else "+"
        formatted += f"{i}. {date} | {description} | {sign}${abs(amount):,.2f}\n"
    
    return formatted.strip()

def generate_secure_paylink(amount: float, description: str) -> Dict[str, Any]:
    """
    Generate a secure payment link (mock implementation)
    """
    import uuid
    import time
    
    paylink_id = str(uuid.uuid4())
    
    return {
        "paylink_id": paylink_id,
        "url": f"https://secure.bank.example/pay/{paylink_id}",
        "amount": amount,
        "description": description,
        "expires_at": int(time.time()) + 3600,  # 1 hour
        "status": "active"
    }

def mock_account_data() -> Dict[str, Any]:
    """
    Generate mock account data for demo
    """
    return {
        "account_number": "****1234",
        "balance": 15750.50,
        "available_balance": 15250.50,
        "currency": "USD",
        "account_type": "checking"
    }

def mock_transaction_data() -> List[Dict[str, Any]]:
    """
    Generate mock transaction data for demo
    """
    return [
        {
            "id": "txn_001",
            "date": "2024-01-15",
            "description": "Online Purchase - Amazon",
            "amount": 89.99,
            "type": "debit",
            "category": "shopping"
        },
        {
            "id": "txn_002", 
            "date": "2024-01-14",
            "description": "Salary Deposit",
            "amount": 3500.00,
            "type": "credit",
            "category": "income"
        },
        {
            "id": "txn_003",
            "date": "2024-01-13", 
            "description": "Grocery Store",
            "amount": 127.45,
            "type": "debit",
            "category": "groceries"
        },
        {
            "id": "txn_004",
            "date": "2024-01-12",
            "description": "Utilities Payment",
            "amount": 245.67,
            "type": "debit", 
            "category": "utilities"
        },
        {
            "id": "txn_005",
            "date": "2024-01-11",
            "description": "ATM Withdrawal",
            "amount": 100.00,
            "type": "debit",
            "category": "cash"
        }
    ]