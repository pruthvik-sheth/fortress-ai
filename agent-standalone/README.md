# Agent Standalone Testing

This is a standalone version of the AI Agent that you can run independently while your friend works on the broker and gateway components.

## Features

- **Direct Testing**: `/test` endpoint that bypasses JWT requirements
- **Claude Integration**: Direct connection to your Claude API
- **Mock Gateway**: Simulates the gateway responses for FETCH requests
- **Full Agent Logic**: Same core agent functionality as the full system

## Quick Start

1. **Set your Claude API key:**
```bash
export ANTHROPIC_API_KEY=your-claude-api-key-here
```

2. **Start the services:**
```bash
cd agent-standalone
docker compose up --build
```

3. **Test the agent:**
```bash
# Simple question
curl -X POST http://localhost:7000/test \
  -H "Content-Type: application/json" \
  -d '{
    "purpose": "answer_question",
    "user_text": "What is the capital of France?",
    "allowed_tools": []
  }'

# Question with FETCH request
curl -X POST http://localhost:7000/test \
  -H "Content-Type: application/json" \
  -d '{
    "purpose": "web_research", 
    "user_text": "FETCH https://api.github.com/users/octocat",
    "allowed_tools": ["http.fetch"]
  }'
```

## Endpoints

- **POST /test** - Direct testing without JWT (recommended for development)
- **POST /_internal/run** - Full JWT-protected endpoint (for integration testing)
- **GET /health** - Health check

## Services Running

- **Agent**: http://localhost:7000 (your main agent)
- **Mock Gateway**: http://localhost:9001 (simulates the real gateway)

## Integration Ready

When your friend finishes the broker/gateway, you can easily switch back to the full system by using the main docker-compose.yml in the root directory.