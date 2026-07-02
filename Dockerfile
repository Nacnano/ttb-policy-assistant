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

# Build the FAISS index at image build time
# Requires OPENAI_API_KEY as build argument
ARG OPENAI_API_KEY
ENV OPENAI_API_KEY=${OPENAI_API_KEY}
RUN if [ -n "$OPENAI_API_KEY" ]; then python scripts/ingest.py; \
    else echo "WARNING: OPENAI_API_KEY not provided — index will be built at runtime"; fi

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
