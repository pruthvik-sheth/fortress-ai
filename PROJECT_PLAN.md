# ShieldForce AI - Project Plan & Integration Strategy
## Modular Architecture for Team Collaboration

---

## 🎯 TEAM STRUCTURE

**You (Security Layer)**: Ingress Broker + Egress Gateway + Monitoring
**Teammate (Agent Sandbox)**: AI Agent Runtime + Execution Environment
**Integration Point**: Docker Compose orchestration

---

## 📦 MODULAR FOLDER STRUCTURE

```
shieldforce-ai/                    # Root project (shared repo)
│
├── security-layer/                # YOUR WORK (this folder)
│   ├── broker/                    # Ingress service
│   │   ├── app.py
│   │   ├── firewall.py
│   │   ├── jwt_utils.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── gateway/                   # Egress service
│   │   ├── app.py
│   │   ├── behavior_dna.py
│   │   ├── threat_scoring.py
│   │   ├── compliance.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── shared/                    # Shared utilities
│   │   ├── __init__.py
│   │   ├── logging_utils.py
│   │   ├── regex_patterns.py
│   │   └── models.py             # Pydantic schemas
│   │
│   ├── tests/                     # Your tests
│   │   ├── test_broker.py
│   │   ├── test_gateway.py
│   │   └── test_integration.py
│   │
│   ├── docker-compose.security.yml  # Your services only
│   ├── .env.security.example
│   └── README.md                  # Your component docs
│
├── agent-sandbox/                 # TEAMMATE'S WORK
│   ├── agent/
│   │   ├── main.py
│   │   ├── executor.py
│   │   ├── tools/
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── tests/
│   │   └── test_agent.py
│   │
│   ├── docker-compose.agent.yml   # Agent service only
│   ├── .env.agent.example
│   └── README.md                  # Agent docs
│
├── integration/                   # MERGE POINT
│   ├── docker-compose.yml         # Full stack orchestration
│   ├── docker-compose.override.yml # Local dev overrides
│   ├── .env.example               # All environment vars
│   └── integration_tests.py       # End-to-end tests
│
├── data/                          # Shared volume (logs, evidence)
│   ├── broker_log.jsonl
│   ├── gateway_log.jsonl
│   ├── incidents.jsonl
│   ├── a10_control_log.jsonl
│   └── evidence_pack.html
│
├── docs/                          # Documentation
│   ├── ARCHITECTURE.md
│   ├── API_CONTRACT.md            # Interface between components
│   ├── DEMO_SCRIPT.md
│   └── DEPLOYMENT.md
│
├── .gitignore
├── README.md                      # Main project README
└── PROJECT_PLAN.md                # This file
```

---

## 🔌 INTEGRATION CONTRACT

### API Contract Between Components

**1. Broker → Agent**
```
Endpoint: POST http://agent:7000/_internal/run
Headers:
  Authorization: Bearer <JWT_CAPABILITY_TOKEN>
  Content-Type: application/json

Request Body:
{
  "agent_id": "github-analyzer",
  "purpose": "answer_customer_ticket",
  "user_text": "Find the last ticket status",
  "attachments": [],
  "budgets": {
    "max_tokens": 1500,
    "max_tool_calls": 3
  },
  "request_id": "uuid-optional"
}

Response:
{
  "status": "success",
  "result": "...",
  "tokens_used": 342,
  "tool_calls": 1,
  "execution_time_ms": 1234
}
```

**2. Agent → Gateway**
```
Endpoint: POST http://gateway:9000/proxy
Headers:
  Content-Type: application/json

Request Body:
{
  "agent_id": "github-analyzer",
  "url": "https://api.github.com/repos/user/repo",
  "method": "GET",
  "headers": {"Authorization": "token ghp_..."},
  "body": null,
  "purpose": "fetch_repo_data"
}

Response:
{
  "status": "ALLOW",
  "upstream": {
    "status_code": 200,
    "headers": {...},
    "body": "...",
    "ttfb_ms": 234,
    "content_len": 1024
  }
}

OR (if blocked):
{
  "status": "BLOCK",
  "score": 75,
  "reasons": ["denylisted_domain", "suspicious_payload"]
}

OR (if quarantined):
{
  "status": "QUARANTINED",
  "reason": "agent_locked",
  "incident_id": "inc_123"
}
```

**3. JWT Capability Token Format**
```json
{
  "iss": "broker",
  "aud": "agent",
  "sub": "github-analyzer",
  "tools": ["kb.search", "github.api"],
  "scopes": ["kb:public", "github:read"],
  "budgets": {
    "max_tokens": 1500,
    "max_tool_calls": 3
  },
  "exp": 1696348800,
  "iat": 1696348500
}
```

---

## 🔀 MERGE STRATEGY

### Phase 1: Independent Development (Days 1-2)

**You work in**: `security-layer/`
- Develop broker and gateway independently
- Use mock agent responses for testing
- Run with: `docker-compose -f security-layer/docker-compose.security.yml up`

**Teammate works in**: `agent-sandbox/`
- Develop agent independently
- Use mock broker/gateway for testing
- Run with: `docker-compose -f agent-sandbox/docker-compose.agent.yml up`

### Phase 2: Integration (Day 2 afternoon)

**Step 1**: Align on API contract
```bash
# Create integration/API_CONTRACT.md together
# Define exact request/response formats
# Agree on error codes and edge cases
```

**Step 2**: Create unified docker-compose
```bash
# integration/docker-compose.yml
# Combines both docker-compose files
# Defines shared networks and volumes
```

**Step 3**: Test integration
```bash
cd integration/
docker-compose up
# Run integration_tests.py
```

### Phase 3: Final Merge (Day 2 evening)

**Merge checklist**:
- [ ] API contract documented
- [ ] All services start successfully
- [ ] Network isolation verified (agent can't reach internet)
- [ ] End-to-end test passes (external → broker → agent → gateway → external)
- [ ] Logs are being written to shared volume
- [ ] Health endpoints responding
- [ ] Demo scenarios work

---

## 🐳 DOCKER COMPOSE STRATEGY

### Your Security Layer Compose (security-layer/docker-compose.security.yml)

```yaml
version: '3.8'

networks:
  mesh:
    driver: bridge
    internal: true
  public:
    driver: bridge

services:
  broker:
    build: ./broker
    container_name: shieldforce-broker
    ports:
      - "8001:8001"
    networks:
      - mesh
    environment:
      - BROKER_API_KEY=${BROKER_API_KEY}
      - CAPABILITY_SECRET=${CAPABILITY_SECRET}
      - BROKER_PORT=8001
      - AGENT_URL=http://agent:7000
    volumes:
      - ../data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  gateway:
    build: ./gateway
    container_name: shieldforce-gateway
    ports:
      - "9000:9000"
    networks:
      - mesh
      - public
    environment:
      - GATEWAY_PORT=9000
      - EGRESS_AUDITOR=${EGRESS_AUDITOR:-off}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ../data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  # Mock agent for your testing
  mock-agent:
    image: python:3.11-slim
    container_name: mock-agent
    networks:
      - mesh
    command: >
      sh -c "pip install fastapi uvicorn &&
             python -c '
      from fastapi import FastAPI, Header
      import uvicorn
      app = FastAPI()
      @app.post(\"/_internal/run\")
      async def run(authorization: str = Header(None)):
          return {\"status\": \"success\", \"result\": \"Mock agent response\"}
      uvicorn.run(app, host=\"0.0.0.0\", port=7000)
      '"
    expose:
      - "7000"
```

### Teammate's Agent Compose (agent-sandbox/docker-compose.agent.yml)

```yaml
version: '3.8'

networks:
  mesh:
    driver: bridge
    internal: true

services:
  agent:
    build: ./agent
    container_name: shieldforce-agent
    networks:
      - mesh
    environment:
      - AGENT_PORT=7000
      - GATEWAY_URL=http://gateway:9000
    expose:
      - "7000"
    # No ports exposed to host!

  # Mock broker for agent testing
  mock-broker:
    image: python:3.11-slim
    container_name: mock-broker
    networks:
      - mesh
    ports:
      - "8001:8001"
    command: >
      sh -c "pip install fastapi uvicorn pyjwt &&
             python -c '
      from fastapi import FastAPI
      import uvicorn
      app = FastAPI()
      @app.post(\"/invoke\")
      async def invoke(data: dict):
          return {\"status\": \"success\", \"result\": \"Mock broker\"}
      uvicorn.run(app, host=\"0.0.0.0\", port=8001)
      '"

  # Mock gateway for agent testing
  mock-gateway:
    image: python:3.11-slim
    container_name: mock-gateway
    networks:
      - mesh
    expose:
      - "9000"
    command: >
      sh -c "pip install fastapi uvicorn httpx &&
             python -c '
      from fastapi import FastAPI
      import uvicorn, httpx
      app = FastAPI()
      @app.post(\"/proxy\")
      async def proxy(data: dict):
          async with httpx.AsyncClient() as client:
              resp = await client.request(data[\"method\"], data[\"url\"])
              return {\"status\": \"ALLOW\", \"upstream\": {\"status_code\": resp.status_code}}
      uvicorn.run(app, host=\"0.0.0.0\", port=9000)
      '"
```

### Final Integrated Compose (integration/docker-compose.yml)

```yaml
version: '3.8'

networks:
  mesh:
    driver: bridge
    internal: true
  public:
    driver: bridge

volumes:
  data:
    driver: local

services:
  broker:
    build: ../security-layer/broker
    container_name: shieldforce-broker
    ports:
      - "8001:8001"
    networks:
      - mesh
    environment:
      - BROKER_API_KEY=${BROKER_API_KEY}
      - CAPABILITY_SECRET=${CAPABILITY_SECRET}
      - BROKER_PORT=8001
      - AGENT_URL=http://agent:7000
      - INGRESS_AUDITOR=${INGRESS_AUDITOR:-off}
    volumes:
      - ../data:/app/data
    depends_on:
      - agent

  agent:
    build: ../agent-sandbox/agent
    container_name: shieldforce-agent
    networks:
      - mesh
    environment:
      - AGENT_PORT=7000
      - GATEWAY_URL=http://gateway:9000
      - CAPABILITY_SECRET=${CAPABILITY_SECRET}
    expose:
      - "7000"
    depends_on:
      - gateway

  gateway:
    build: ../security-layer/gateway
    container_name: shieldforce-gateway
    ports:
      - "9000:9000"
    networks:
      - mesh
      - public
    environment:
      - GATEWAY_PORT=9000
      - EGRESS_AUDITOR=${EGRESS_AUDITOR:-off}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ../data:/app/data
```

---

## 📋 DEVELOPMENT WORKFLOW

### Your Daily Workflow

**Morning (Setup)**:
```bash
cd shieldforce-ai/security-layer
cp .env.security.example .env
# Edit .env with your keys
docker-compose -f docker-compose.security.yml up --build
```

**Development Loop**:
```bash
# Make changes to broker/app.py or gateway/app.py
docker-compose -f docker-compose.security.yml restart broker
# Test with curl
curl -X POST http://localhost:8001/invoke -H 'X-API-Key: DEMO-KEY' -d '{...}'
```

**Testing**:
```bash
cd security-layer
pytest tests/ -v
```

**Commit**:
```bash
git add security-layer/
git commit -m "feat: add prompt injection firewall"
git push origin feature/security-layer
```

### Integration Day Workflow

**Step 1: Pull teammate's work**
```bash
git fetch origin
git checkout main
git pull
# Now you have agent-sandbox/ folder
```

**Step 2: Test integration**
```bash
cd integration/
cp .env.example .env
# Edit .env with all keys
docker-compose up --build
```

**Step 3: Run integration tests**
```bash
python integration_tests.py
# Should see all 6 scenarios pass
```

**Step 4: Debug issues**
```bash
# Check logs
docker-compose logs broker
docker-compose logs agent
docker-compose logs gateway

# Check network connectivity
docker exec shieldforce-broker ping agent
docker exec shieldforce-agent ping gateway

# Verify network isolation
docker exec shieldforce-agent ping google.com  # Should FAIL
docker exec shieldforce-gateway ping google.com  # Should SUCCEED
```

---

## 🧪 TESTING STRATEGY

### Unit Tests (Your Responsibility)

**security-layer/tests/test_broker.py**:
```python
def test_prompt_injection_detection():
    """Test firewall blocks jailbreak attempts"""
    
def test_secret_redaction():
    """Test AWS keys are masked"""
    
def test_jwt_generation():
    """Test capability tokens are valid"""
    
def test_rbac():
    """Test unauthorized agent access is blocked"""
```

**security-layer/tests/test_gateway.py**:
```python
def test_denylist_blocking():
    """Test pastebin.com is blocked"""
    
def test_behavior_baseline():
    """Test anomaly detection after 10 samples"""
    
def test_quarantine():
    """Test agent is locked after secret exfil"""
    
def test_health_score():
    """Test health score calculation"""
```

### Integration Tests (Shared Responsibility)

**integration/integration_tests.py**:
```python
def test_end_to_end_normal():
    """External → Broker → Agent → Gateway → External"""
    
def test_prompt_injection_blocked():
    """Jailbreak attempt never reaches agent"""
    
def test_data_exfiltration_quarantine():
    """Agent locked after secret leak attempt"""
    
def test_threat_intelligence_sharing():
    """Attack on Agent A blocks Agent B"""
    
def test_compliance_generation():
    """Evidence pack generated successfully"""
    
def test_network_isolation():
    """Agent cannot reach internet directly"""
```

---

## 📝 DOCUMENTATION RESPONSIBILITIES

### You Document:
- `security-layer/README.md` - How to run broker/gateway
- `docs/API_CONTRACT.md` - Broker and gateway endpoints
- `docs/THREAT_RULES.md` - All detection rules and thresholds
- `docs/COMPLIANCE.md` - Evidence generation logic

### Teammate Documents:
- `agent-sandbox/README.md` - How to run agent
- `docs/AGENT_CAPABILITIES.md` - What tools agent supports
- `docs/CAPABILITY_TOKENS.md` - How agent validates JWT

### Shared Documentation:
- `README.md` - Main project overview
- `docs/ARCHITECTURE.md` - Full system architecture
- `docs/DEMO_SCRIPT.md` - Step-by-step demo
- `docs/DEPLOYMENT.md` - Production deployment guide

---

## 🚀 DEPLOYMENT STRATEGY

### Local Development
```bash
cd integration/
docker-compose up
```

### Demo Environment (Hackathon)
```bash
# On your A100 machine
cd integration/
docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up
# docker-compose.gpu.yml adds GPU passthrough for vLLM
```

### Production (Future)
```bash
# Kubernetes manifests
kubectl apply -f k8s/broker-deployment.yml
kubectl apply -f k8s/agent-deployment.yml
kubectl apply -f k8s/gateway-deployment.yml
kubectl apply -f k8s/network-policies.yml
```

---

## 🔐 SECURITY CONSIDERATIONS

### Network Isolation
- **mesh** network is `internal: true` (no internet)
- Agent MUST NOT have access to public network
- Only gateway bridges mesh and public

### Secret Management
- Use `.env` files (never commit)
- Rotate `CAPABILITY_SECRET` regularly
- Hash API keys in logs

### Logging
- Never log raw secrets
- Mask PII before writing to disk
- Rotate logs to prevent disk fill

---

## 📊 SUCCESS CRITERIA

### Your Component (Security Layer)
- [ ] Broker blocks 5/5 jailbreak attempts
- [ ] Gateway detects 5/5 exfiltration attempts
- [ ] Behavior DNA learns baseline after 10 samples
- [ ] Health score calculation is accurate
- [ ] Compliance report generates in <5s
- [ ] All logs are JSONL formatted
- [ ] Response time <500ms with LLM

### Integration
- [ ] All services start without errors
- [ ] Network isolation verified
- [ ] End-to-end test passes
- [ ] Demo scenarios work
- [ ] No false positives on normal traffic
- [ ] Quarantine persists across restarts

### Demo
- [ ] 5 scenarios run smoothly
- [ ] Dashboard shows real-time updates
- [ ] Compliance report looks professional
- [ ] Pitch is under 5 minutes
- [ ] Judges understand the value prop

---

## 🎯 TIMELINE

### Day 1 (You)
- **Morning**: Set up project structure, Docker Compose
- **Afternoon**: Build broker with firewall
- **Evening**: Build gateway with threat scoring

### Day 1 (Teammate)
- **Morning**: Set up agent runtime
- **Afternoon**: Implement tool execution
- **Evening**: Add capability token validation

### Day 2 (Both)
- **Morning**: Independent testing with mocks
- **Afternoon**: Integration (merge docker-compose)
- **Evening**: Demo polish, documentation

### Day 3 (Demo Day)
- **Morning**: Final testing, bug fixes
- **Afternoon**: Pitch practice
- **Evening**: Present to judges

---

## 🤝 COMMUNICATION PROTOCOL

### Daily Sync (15 min)
- What did you complete?
- What are you working on?
- Any blockers?
- API contract changes?

### Integration Checkpoint (30 min)
- Test API contract with curl
- Verify request/response formats
- Align on error handling
- Update documentation

### Pre-Demo Rehearsal (1 hour)
- Run through all 5 scenarios
- Time the demo (target: 3-4 min)
- Prepare for Q&A
- Backup plan if something breaks

---

## 🛠️ TOOLS & UTILITIES

### Shared Utilities (security-layer/shared/)

**logging_utils.py**:
```python
def log_event(event_type: str, data: dict, log_file: str):
    """Append JSONL log entry"""
    
def mask_secrets(text: str) -> str:
    """Replace secrets with [REDACTED_*]"""
    
def hash_api_key(key: str) -> str:
    """SHA256 hash for logging"""
```

**regex_patterns.py**:
```python
AWS_KEY_PATTERN = r'AKIA[0-9A-Z]{16}'
API_KEY_PATTERN = r'(?i)(api[_-]?key|token)\s*[:=]\s*([A-Za-z0-9_\-]{12,})'
PEM_PATTERN = r'-----BEGIN (?:RSA )?PRIVATE KEY-----'
BASE64_BLOB_PATTERN = r'([A-Za-z0-9+/]{200,}={0,2})'
```

**models.py**:
```python
from pydantic import BaseModel

class InvokeRequest(BaseModel):
    agent_id: str
    purpose: str
    user_text: str
    allowed_tools: list[str]
    data_scope: list[str]
    budgets: dict
    
class ProxyRequest(BaseModel):
    agent_id: str
    url: str
    method: str
    body: str | None
    purpose: str
```

---

## 📦 DELIVERABLES CHECKLIST

### Your Deliverables (security-layer/)
- [ ] `broker/app.py` - Ingress service
- [ ] `broker/firewall.py` - Prompt injection detection
- [ ] `broker/jwt_utils.py` - Token generation
- [ ] `broker/Dockerfile`
- [ ] `gateway/app.py` - Egress service
- [ ] `gateway/behavior_dna.py` - Baseline tracking
- [ ] `gateway/threat_scoring.py` - Multi-layer scoring
- [ ] `gateway/compliance.py` - Evidence generation
- [ ] `gateway/Dockerfile`
- [ ] `shared/` utilities
- [ ] `tests/` unit tests
- [ ] `docker-compose.security.yml`
- [ ] `README.md`

### Shared Deliverables (integration/)
- [ ] `docker-compose.yml` - Full stack
- [ ] `.env.example` - All environment vars
- [ ] `integration_tests.py` - E2E tests
- [ ] `API_CONTRACT.md` - Interface spec

### Documentation (docs/)
- [ ] `ARCHITECTURE.md` - System design
- [ ] `DEMO_SCRIPT.md` - Presentation guide
- [ ] `THREAT_RULES.md` - Detection logic
- [ ] `COMPLIANCE.md` - Evidence format

---

## 🎬 DEMO PREPARATION

### Pre-Demo Checklist
- [ ] All services healthy
- [ ] Logs cleared (fresh start)
- [ ] Health score at 100
- [ ] No quarantined agents
- [ ] Evidence pack deleted (will regenerate)
- [ ] Terminal windows arranged
- [ ] Backup slides ready

### Demo Environment Setup
```bash
# Terminal 1: Services
cd integration/
docker-compose up

# Terminal 2: Logs
docker-compose logs -f gateway | grep -E "BLOCK|QUARANTINE"

# Terminal 3: Commands
cd integration/
# Ready to run curl commands

# Browser: Dashboard
open http://localhost:9000/health
```

### Backup Plan
- If Docker fails: Have screenshots/video
- If LLM times out: Disable auditor, use deterministic only
- If network issues: Run locally without internet
- If demo breaks: Jump to compliance report

---

**Status**: Ready for implementation
**Next Step**: Create security-layer/ folder structure
**Estimated Time**: 18 hours over 2 days
**Risk Level**: Low (modular design, clear interfaces)
