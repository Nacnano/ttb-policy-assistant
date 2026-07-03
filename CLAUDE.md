# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Python RAG microservice** ("ttb Policy Assistant") built as a take-home engineering assessment for TMBThanachart Bank's AI Centre of Excellence. It answers staff questions about bank policies using Retrieval-Augmented Generation with banking-grade guardrails and observability.

See `ASSIGNMENT.md` for the full specification and scoring rubric, and `README.md` for design decisions (ADRs), the threat model, SLOs, and the API reference.

## Architecture

- **Framework**: FastAPI + Pydantic v2 + pydantic-settings (`get_settings()` is `@lru_cache`d)
- **Vector store**: FAISS `IndexFlatIP` with L2-normalised vectors (= cosine similarity), persisted to `data/faiss_index/` (gitignored — run `python scripts/ingest.py` to build)
- **LLM**: OpenAI `gpt-4o-mini` (chat, temp 0) + `text-embedding-3-small` (embeddings); Azure OpenAI reachable by changing `OPENAI_BASE_URL`
- **Logging**: structlog JSON to stdout — one `ask_request` line per request on every terminal path, with hashed question, latency, and full token counts

### Request flow (`POST /ask`, see `app/main.py`)

Pydantic validation → injection detection (400) → PII redaction on input → scope gate (keyword blocklist + embedding cosine, **fails closed** with 503 `SCOPE_UNAVAILABLE`) → FAISS retrieval with relevance floor (grounded refusal if nothing clears it, no LLM call) → generation with citation parsing → PII redaction on output → structured log → response. Upstream failures return 503 `UPSTREAM_ERROR`; a global handler backstops anything else with 500 `INTERNAL_ERROR`.

## Module Map

| Path | Purpose |
|---|---|
| `app/main.py` | FastAPI app, lifespan (loads index via try/except so tests can mock `app.main.load_index`), `/health` + `/ask` |
| `app/config.py` | pydantic-settings; all tunables (`RETRIEVAL_MIN_SCORE`, `SCOPE_SIMILARITY_THRESHOLD`, `TOP_K`, …) |
| `app/ingestion/` | loader → MarkdownHeader/Recursive chunker → batched OpenAI embedder (tenacity retries) → FAISS indexer |
| `app/retrieval/retriever.py` | embed query, normalise, FAISS search with score floor |
| `app/generation/generator.py` | structured prompt (XML-delimited, section-tagged excerpts), citation parsing |
| `app/guardrails/` | `injection.py` (12 regex attack signatures), `pii.py` (Presidio + regex fallback), `scope.py` (blocklist + embedding gate) |
| `app/observability/logging.py` | structlog config, `log_request()` |
| `scripts/ingest.py` | CLI: load → chunk → embed → index |
| `eval/run_eval.py` | in-process httpx eval harness; 18 grounded + 6 adversarial pairs in `eval/qa_pairs.json`; exits non-zero if gate fails (grounded ≥ 80% AND adversarial = 100%) |

## Commands

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm   # optional: full Presidio NER (regex fallback otherwise)

python scripts/ingest.py                  # build the FAISS index (requires OPENAI_API_KEY)
uvicorn app.main:app --reload             # run the service

pytest                                    # 95 tests; no API key needed (OpenAI is mocked)
python eval/run_eval.py                   # eval harness (requires OPENAI_API_KEY + built index)

# Docker — API key passed as a BuildKit secret to bake the index (never stored in a layer)
DOCKER_BUILDKIT=1 docker build --secret id=openai_key,env=OPENAI_API_KEY -t ttb-policy-assistant .
docker run --env-file .env -p 8000:8000 ttb-policy-assistant
```

## Implementation Notes

- The embedded text of each chunk is **prefixed with its source + header path** (ADR-003). After changing chunking or embedding, re-run `scripts/ingest.py` — a stale index silently degrades retrieval.
- Integration tests mock `app.main.load_index` and `openai.OpenAI` — patch those exact targets.
- Presidio needs the `en_core_web_sm` spaCy model; without it the PII layer falls back to regex (no PERSON detection) and logs a WARNING.
- `requirements.txt` is fully pinned; regenerate deliberately, not ad hoc.

## Key Constraints

- No real bank data or customer data anywhere in the repo — all policy docs are synthetic
- All secrets via environment variables or `.env` file (`.env` is gitignored); never hardcoded
- Adversarial/out-of-scope questions must be refused, not answered; guardrails fail closed
- Answers must cite source chunks — no hallucination without grounding
