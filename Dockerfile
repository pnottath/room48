FROM python:3.12-slim

WORKDIR /app

# System deps (swisseph wheels are pre-built but a few build tools help with edge cases)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY kerala_astro/ ./kerala_astro/

EXPOSE 8000

# Health check hits the /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

CMD ["uvicorn", "kerala_astro.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
