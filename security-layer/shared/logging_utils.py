"""
ShieldForce AI - Logging Utilities
JSONL logging with automatic secret masking
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any


def hash_api_key(api_key: str) -> str:
    """
    Hash API key for logging (SHA256)
    
    Args:
        api_key: API key to hash
        
    Returns:
        Hex digest of hash
    """
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


def log_event(
    log_file: str,
    event_type: str,
    data: dict[str, Any],
    mask_fields: list[str] | None = None
) -> None:
    """
    Append event to JSONL log file
    
    Args:
        log_file: Path to log file
        event_type: Type of event (e.g., "invoke_allowed", "threat_blocked")
        data: Event data dictionary
        mask_fields: List of field names to mask (optional)
    """
    # Ensure data directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Build log entry
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": event_type,
        **data
    }
    
    # Mask sensitive fields
    if mask_fields:
        for field in mask_fields:
            if field in entry and entry[field]:
                entry[field] = "***MASKED***"
    
    # Append to file
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        # Fail gracefully - don't break the request
        print(f"Warning: Failed to write log: {e}")


def read_recent_logs(log_file: str, max_lines: int = 100) -> list[dict]:
    """
    Read recent log entries
    
    Args:
        log_file: Path to log file
        max_lines: Maximum number of lines to read
        
    Returns:
        List of log entry dictionaries
    """
    log_path = Path(log_file)
    
    if not log_path.exists():
        return []
    
    entries = []
    
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            # Read last N lines
            lines = f.readlines()[-max_lines:]
            
            for line in lines:
                try:
                    entries.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Warning: Failed to read log: {e}")
    
    return entries


def get_log_stats(log_file: str) -> dict[str, Any]:
    """
    Get statistics from log file
    
    Args:
        log_file: Path to log file
        
    Returns:
        Dictionary with stats (total_events, event_types, etc.)
    """
    entries = read_recent_logs(log_file, max_lines=1000)
    
    if not entries:
        return {
            "total_events": 0,
            "event_types": {},
            "first_event": None,
            "last_event": None
        }
    
    event_types = {}
    for entry in entries:
        event_type = entry.get("event_type", "unknown")
        event_types[event_type] = event_types.get(event_type, 0) + 1
    
    return {
        "total_events": len(entries),
        "event_types": event_types,
        "first_event": entries[0].get("timestamp"),
        "last_event": entries[-1].get("timestamp")
    }
