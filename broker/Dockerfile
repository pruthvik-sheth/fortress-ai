# ShieldForce AI - Ingress Broker
FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy requirements first for better caching
COPY requirements.txt .
COPY requirements-llm.txt .

# Install core dependencies with uv
RUN uv pip install --system --no-cache -r requirements.txt

# Optionally install LLM dependencies (set ENABLE_LLM_BUILD=true)
ARG ENABLE_LLM_BUILD=false
RUN if [ "$ENABLE_LLM_BUILD" = "true" ]; then \
        echo "Installing LLM dependencies..." && \
        uv pip install --system --no-cache -r requirements-llm.txt; \
    else \
        echo "Skipping LLM dependencies (set ENABLE_LLM_BUILD=true to enable)"; \
    fi

# Copy application files
COPY app.py .
COPY firewall.py .
COPY jwt_utils.py .

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8001/health', timeout=2)"

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
