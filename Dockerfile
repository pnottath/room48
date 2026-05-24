FROM python:3.12-slim

WORKDIR /app

# System deps:
#  - build-essential: belt-and-braces for any source-built wheels
#  - libpango / libpangoft2 / libharfbuzz-subset0 / libcairo / libgdk-pixbuf
#    / libffi / shared-mime-info:
#       WeasyPrint's runtime dependencies (text shaping, drawing, image
#       loading, mime type detection). Without these, `import weasyprint`
#       succeeds but rendering crashes at runtime.
#       libharfbuzz-subset0 is required by WeasyPrint 60+ and is the
#       single most common cause of "weasyprint installs but crashes at
#       PDF time" failures on slim Debian images.
#  - fonts-liberation: Liberation Serif used as the PDF body face.
#  - fonts-noto: Devanagari (for the ॐ symbol) and broad Unicode coverage.
#       Without this, the Aum and Malayalam glyphs may render as boxes.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz-subset0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        shared-mime-info \
        fonts-liberation \
        fonts-noto-core \
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
