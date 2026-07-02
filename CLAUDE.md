# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Python RAG microservice** ("ttb Policy Assistant") built as a take-home engineering assessment for TMBThanachart Bank's AI Centre of Excellence. It answers staff questions about bank policies using Retrieval-Augmented Generation with banking-grade guardrails and observability.

See `ASSIGNMENT.md` for the full specification and scoring rubric.

## Required Deliverables

The following must be built (nothing exists yet):

| Component | Description |
|---|---|
| `POST /ask` HTTP API | Input validation, structured JSON response with answer + citations |
| Ingestion pipeline | Chunk, embed, and index ~15-20 synthetic policy docs into a vector store |
| RAG pipeline | Retrieve relevant chunks, generate grounded answer with source citations |
| Guardrails | PII redaction on input/output, out-of-scope refusal, prompt-injection resistance |
| Observability | Structured logging, per-request token count and latency telemetry |
| Tests | Unit tests for chunking/guardrails + at least one `/ask` integration test |
| Eval harness | Runs 10 evaluation questions, prints groundedness/correctness summary |
| Dockerfile | Builds and runs the service on a clean machine |

## Architecture Decisions (to be made)

- **Vector store**: FAISS (no infra needed), pgvector, or Azure AI Search
- **LLM**: OpenAI-compatible API (Azure OpenAI preferred; mocking permitted)
- **Framework**: FastAPI recommended (async, auto-docs, Pydantic validation)
- **Secrets**: via environment variables only — never hardcoded

## Commands (once implemented)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
uvicorn app.main:app --reload

# Run tests
pytest

# Run eval harness
python eval/run_eval.py

# Build Docker image
docker build -t ttb-policy-assistant .
docker run --env-file .env -p 8000:8000 ttb-policy-assistant
```

## Key Constraints

- No real bank data or customer data anywhere in the repo
- All secrets via environment variables or `.env` file (`.env` is gitignored)
- Adversarial/out-of-scope questions must be refused, not answered
- Answers must cite source chunks — no hallucination without grounding
