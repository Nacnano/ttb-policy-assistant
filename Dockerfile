FROM python:3.11-slim

WORKDIR /app

# System deps for spaCy + FAISS
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy English model (needed by Presidio)
RUN python -m spacy download en_core_web_sm

# Copy source code and policies
COPY app/ ./app/
COPY policies/ ./policies/
COPY scripts/ ./scripts/

# Build the FAISS index at image build time using a BuildKit secret so the API key is
# NEVER persisted into an image layer (unlike ARG/ENV, which leak via `docker history`).
#   DOCKER_BUILDKIT=1 docker build --secret id=openai_key,env=OPENAI_API_KEY -t ttb-policy-assistant .
# If no secret is supplied the build still succeeds; the index must then be built at
# runtime (mount policies + run scripts/ingest.py, or ingest into a mounted volume).
RUN --mount=type=secret,id=openai_key \
    if [ -f /run/secrets/openai_key ]; then \
        OPENAI_API_KEY="$(cat /run/secrets/openai_key)" python scripts/ingest.py; \
    else echo "No build secret 'openai_key' — index NOT baked; build it at runtime."; fi

# Create non-root user and ensure the (possibly just-built) FAISS index directory
# is owned by it, since /app/data may be written either above (as root) or at
# runtime (as appuser).
RUN useradd --create-home appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app/data

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health',timeout=3).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
