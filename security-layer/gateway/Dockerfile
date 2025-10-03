# ShieldForce AI - Egress Gateway
FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies with uv
RUN uv pip install --system --no-cache -r requirements.txt

# Copy application files
COPY app.py .
COPY behavior_dna.py .
COPY threat_scoring.py .
COPY compliance.py .

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 9000

# Health check
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:9000/health', timeout=2)"

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000"]
