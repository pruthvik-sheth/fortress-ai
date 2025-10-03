"""
ShieldForce AI - Compliance Automation
Generate audit evidence and compliance reports
"""

import json
from datetime import datetime, timedelta
from pathlib import Path


def read_recent_logs(log_file: str, max_lines: int = 100) -> list[dict]:
    """Read recent log entries"""
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


class ComplianceGenerator:
    """
    Generate compliance evidence and reports
    """
    
    def __init__(self, incidents_file: str):
        self.incidents_file = incidents_file
    
    def get_recent_incidents(self, limit: int = 100) -> list[dict]:
        """
        Get recent security incidents
        
        Args:
            limit: Maximum number of incidents to return
            
        Returns:
            List of incident dictionaries
        """
        return read_recent_logs(self.incidents_file, max_lines=limit)
    
    def get_incidents_count(self, hours: int = 24) -> int:
        """
        Count incidents in last N hours
        
        Args:
            hours: Time window in hours
            
        Returns:
            Number of incidents
        """
        incidents = self.get_recent_incidents(limit=1000)
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        count = 0
        for incident in incidents:
            try:
                ts = datetime.fromisoformat(incident["timestamp"].replace("Z", "+00:00"))
                if ts >= cutoff:
                    count += 1
            except:
                continue
        
        return count
    
    def calculate_health_score(self) -> float:
        """
        Calculate organization health score (0-100)
        
        Formula:
        - Start at 100
        - For each incident in last 24h: subtract (score - 40) * 0.2
        - Clamp to [0, 100]
        
        Returns:
            Health score
        """
        incidents = self.get_recent_incidents(limit=1000)
        cutoff = datetime.utcnow() - timedelta(hours=24)
        
        health_score = 100.0
        
        for incident in incidents:
            try:
                ts = datetime.fromisoformat(incident["timestamp"].replace("Z", "+00:00"))
                if ts >= cutoff:
                    incident_score = incident.get("score", 0)
                    if incident_score > 40:
                        health_score -= (incident_score - 40) * 0.2
            except:
                continue
        
        return max(0.0, min(100.0, health_score))
    
    def generate_evidence_pack(
        self,
        health_score: float,
        agents_seen: int,
        quarantined_agents: list[str]
    ) -> str:
        """
        Generate HTML compliance evidence pack
        
        Args:
            health_score: Current health score
            agents_seen: Number of unique agents
            quarantined_agents: List of quarantined agent IDs
            
        Returns:
            HTML string
        """
        incidents = self.get_recent_incidents(limit=100)
        incidents_24h = self.get_incidents_count(hours=24)
        
        # Build incident table rows
        incident_rows = ""
        for incident in incidents[:50]:  # Show last 50
            timestamp = incident.get("timestamp", "N/A")
            agent_id = incident.get("agent_id", "N/A")
            score = incident.get("score", 0)
            action = incident.get("action", "N/A")
            reasons = ", ".join(incident.get("reasons", []))
            
            incident_rows += f"""
            <tr>
                <td>{timestamp}</td>
                <td>{agent_id}</td>
                <td>{score:.1f}</td>
                <td><span class="badge badge-{action.lower()}">{action}</span></td>
                <td>{reasons}</td>
            </tr>
            """
        
        # Build quarantine list
        quarantine_list = ""
        if quarantined_agents:
            for agent_id in quarantined_agents:
                quarantine_list += f"<li>{agent_id}</li>"
        else:
            quarantine_list = "<li><em>No agents currently quarantined</em></li>"
        
        # Generate HTML
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShieldForce AI - Compliance Evidence Pack</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            margin-bottom: 10px;
            font-size: 32px;
        }}
        .subtitle {{
            color: #7f8c8d;
            margin-bottom: 30px;
            font-size: 14px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .metric {{
            background: #ecf0f1;
            padding: 20px;
            border-radius: 6px;
            text-align: center;
        }}
        .metric-value {{
            font-size: 36px;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 5px;
        }}
        .metric-label {{
            font-size: 14px;
            color: #7f8c8d;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .health-score {{
            background: {'#27ae60' if health_score >= 80 else '#e67e22' if health_score >= 60 else '#e74c3c'};
            color: white;
        }}
        h2 {{
            color: #2c3e50;
            margin: 40px 0 20px 0;
            font-size: 24px;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ecf0f1;
        }}
        th {{
            background: #34495e;
            color: white;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 12px;
            letter-spacing: 1px;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .badge-block {{
            background: #e74c3c;
            color: white;
        }}
        .badge-quarantine {{
            background: #c0392b;
            color: white;
        }}
        .badge-allow {{
            background: #27ae60;
            color: white;
        }}
        ul {{
            list-style: none;
            padding-left: 0;
        }}
        li {{
            padding: 8px 0;
            border-bottom: 1px solid #ecf0f1;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 2px solid #ecf0f1;
            text-align: center;
            color: #7f8c8d;
            font-size: 12px;
        }}
        .denylist {{
            background: #fff3cd;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #ffc107;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ ShieldForce AI</h1>
        <p class="subtitle">Compliance Evidence Pack - Generated {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC</p>
        
        <div class="summary">
            <div class="metric health-score">
                <div class="metric-value">{health_score:.1f}</div>
                <div class="metric-label">Health Score</div>
            </div>
            <div class="metric">
                <div class="metric-value">{agents_seen}</div>
                <div class="metric-label">Agents Monitored</div>
            </div>
            <div class="metric">
                <div class="metric-value">{incidents_24h}</div>
                <div class="metric-label">Incidents (24h)</div>
            </div>
            <div class="metric">
                <div class="metric-value">{len(quarantined_agents)}</div>
                <div class="metric-label">Quarantined</div>
            </div>
        </div>
        
        <h2>📊 Executive Summary</h2>
        <p>
            ShieldForce AI has monitored <strong>{agents_seen}</strong> AI agents over the reporting period.
            The current organization health score is <strong>{health_score:.1f}/100</strong>.
            In the last 24 hours, <strong>{incidents_24h}</strong> security incidents were detected and mitigated.
        </p>
        
        <h2>🚨 Security Incidents</h2>
        <table>
            <thead>
                <tr>
                    <th>Timestamp</th>
                    <th>Agent ID</th>
                    <th>Threat Score</th>
                    <th>Action</th>
                    <th>Reasons</th>
                </tr>
            </thead>
            <tbody>
                {incident_rows if incident_rows else '<tr><td colspan="5"><em>No incidents recorded</em></td></tr>'}
            </tbody>
        </table>
        
        <h2>🔒 Quarantined Agents</h2>
        <ul>
            {quarantine_list}
        </ul>
        
        <h2>🛡️ Threat Intelligence</h2>
        <div class="denylist">
            <strong>Active Denylist Domains:</strong>
            pastebin.com, filebin.net, ipfs.io, transfer.sh, file.io, 0x0.st, uguu.se, catbox.moe, anonfiles.com, mega.nz
        </div>
        
        <h2>✅ Compliance Frameworks</h2>
        <ul>
            <li>✅ <strong>NIS2</strong> - Network and Information Security Directive</li>
            <li>✅ <strong>DORA</strong> - Digital Operational Resilience Act</li>
            <li>✅ <strong>SOC2 Type II</strong> - Security, Availability, Confidentiality</li>
            <li>✅ <strong>ISO 27001</strong> - Information Security Management</li>
            <li>✅ <strong>GDPR</strong> - Data Protection and Privacy</li>
        </ul>
        
        <div class="footer">
            <p>This evidence pack was automatically generated by ShieldForce AI</p>
            <p>For questions or audit requests, contact: security@shieldforce.ai</p>
        </div>
    </div>
</body>
</html>
        """
        
        return html
