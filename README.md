# TTB Policy Assistant

A production-style Python RAG microservice that answers TMBThanachart Bank staff questions about internal policies using Retrieval-Augmented Generation, with banking-grade guardrails and observability.

Built as a take-home engineering assessment for TTB's AI Centre of Excellence.

---

## Quick Start

### Prerequisites
- Python 3.11+
- OpenAI API key (`gpt-4o-mini` + `text-embedding-3-small`)

### Local setup

```bash
# 1. Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm   # optional: enables full Presidio NER

# 2. Configure secrets
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...

# 3. Build the vector index
python scripts/ingest.py

# 4. Start the service
uvicorn app.main:app --reload
# Auto docs: http://localhost:8000/docs
```

### Smoke test

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How many days of annual leave am I entitled to?"}'
```

---

## Running Tests

```bash
pytest -v
# 68 tests, all passing — no API key required (integration tests mock OpenAI)
```

---

## Eval Harness

```bash
python eval/run_eval.py
# Requires OPENAI_API_KEY + built index
```

Runs 18 grounded Q&A + 6 adversarial questions in-process via httpx, prints a scored table.

**Results (last run):**

| Metric | Score |
|---|---|
| Grounded keyword accuracy | 100% (18/18) |
| Grounded citation accuracy | 100% (18/18) |
| Adversarial pass rate | 100% (6/6) |
| **Overall** | **100%** |

---

## Docker

```bash
# Build - embeds FAISS index at build time
docker build --build-arg OPENAI_API_KEY=$OPENAI_API_KEY -t ttb-policy-assistant .

# Run
docker run --env-file .env -p 8000:8000 ttb-policy-assistant

# Or via Compose
docker-compose up --build
```

If `OPENAI_API_KEY` is not provided as a build arg, the index is built on first startup instead.

---

## API Reference

### `GET /health`

```json
{"status": "ok", "index_ready": true}
```

### `POST /ask`

**Request**
```json
{
  "question": "What is the annual leave entitlement?",
  "session_id": "optional-string"
}
```

**Response 200**
```json
{
  "answer": "Employees with less than 5 years of service receive 15 days...",
  "citations": [
    {
      "source": "leave_policy.md",
      "chunk_id": "leave_policy.md::chunk_0",
      "excerpt": "15 days of annual leave per year"
    }
  ],
  "model": "gpt-4o-mini",
  "prompt_tokens": 420,
  "completion_tokens": 85,
  "latency_ms": 1234.5
}
```

**Error 400**
```json
{"detail": {"error": "...", "code": "OUT_OF_SCOPE"}}
```

Error codes: `OUT_OF_SCOPE` | `INJECTION_DETECTED` | `VALIDATION_ERROR`

---

## Architecture

```
POST /ask
  |
  |-- [1] Pydantic validation (422 on fail)
  |-- [2] Injection detection -> 400 INJECTION_DETECTED
  |-- [3] PII redaction on input (Presidio + regex fallback)
  |-- [4] Scope check: keyword blocklist + embedding cosine gate -> 400 OUT_OF_SCOPE
  |-- [5] FAISS retrieval: embed query -> top-5 cosine-similar chunks
  |-- [6] LLM generation: structured system prompt with XML-delimited policy excerpts
  |-- [7] PII redaction on output
  |-- [8] structlog JSON log (question hash, latency, tokens, outcome)
  `-- [9] AskResponse
```

**Ingestion pipeline** (run once via `python scripts/ingest.py`):

```
policies/*.md -> loader -> MarkdownHeader chunker -> RecursiveChar fallback
             -> OpenAI embedder (batched) -> FAISS IndexFlatIP + metadata.json
```

---

## Architecture Decision Records

### ADR-001 — FAISS over pgvector / Azure AI Search

**Decision:** FAISS `IndexFlatIP` with L2-normalised vectors (inner product = cosine similarity after normalization).

**Rationale:** Zero infrastructure — runs in-process, no external service, no auth to configure. At 130 chunks exact search completes in under 1 ms. Index persists to disk as two files (`index.faiss` + `metadata.json`). Simple to test with mocks.

**Trade-off:** Not horizontally scalable. Each replica needs its own index copy, and adding documents requires a full rebuild. For thousands of documents or live update requirements, pgvector (Postgres extension) or Azure AI Search would be the right choice. The retriever interface is thin enough that swapping is a one-file change.

---

### ADR-002 — `gpt-4o-mini` for generation, `text-embedding-3-small` for retrieval

**Decision:** OpenAI hosted models via standard REST API.

**Rationale:** `gpt-4o-mini` is 10-20x cheaper than GPT-4o with sufficient quality for factual policy Q&A. `text-embedding-3-small` is fast, low-cost, and produces 1536-dim vectors well-suited for this scale. Both are available on Azure OpenAI — migrating requires only changing `OPENAI_BASE_URL` in `.env`.

**Trade-off:** Dependency on OpenAI availability. For production SLAs, Azure OpenAI with Provisioned Throughput Units (PTU) would cap latency variance and remove shared-capacity throttling risk.

---

### ADR-003 — MarkdownHeader splitting with Recursive fallback

**Decision:** `MarkdownHeaderTextSplitter` first (splits on `#`/`##`/`###`), then `RecursiveCharacterTextSplitter` (400 chars, 80 overlap) for sections that exceed the chunk size.

**Rationale:** Header-aware splitting keeps semantically coherent sections together (e.g., "Annual Leave" stays with its bullet points), which improves retrieval precision vs. pure character splitting. The recursive fallback handles unusually long sections without losing header context.

**Trade-off:** Quality depends on the document author using headers consistently. Unstructured PDFs would need a different extraction strategy (e.g., unstructured.io or Azure Document Intelligence).

---

### ADR-004 — Presidio with regex fallback for PII

**Decision:** `presidio-analyzer` with custom Thai national ID (`\b[0-9]{13}\b`) and bank account recognizers. Falls back to regex patterns for email, phone, and Thai ID if the spaCy model is not installed.

**Rationale:** Presidio provides a production-grade, pluggable PII redaction pipeline. Custom recognizers cover Thai-specific identifiers absent from the default configuration. The regex fallback means the service starts and provides baseline protection even in constrained environments (CI, Docker without the spaCy model).

**Trade-off:** Regex fallback cannot detect PERSON names without NER context. Full protection requires `python -m spacy download en_core_web_sm`. In production, the spaCy model is always present (it is installed in the Dockerfile).

---

### ADR-005 — Two-layer scope guard

**Decision:** Keyword regex blocklist (O(1)) as the first gate; embedding cosine similarity to 10 in-scope anchor phrases as the second gate (threshold 0.30, configurable via `SCOPE_SIMILARITY_THRESHOLD`).

**Rationale:** The blocklist catches obvious off-topic requests (account balances, crypto prices, weather) with zero API cost and sub-millisecond latency. The embedding gate catches subtler out-of-scope queries that bypass keywords. 15 anchors (one per policy area) are pre-computed at startup — the gate adds only one embedding call per request.

**Trade-off:** The 0.30 threshold was set heuristically. Production tuning would use a labelled evaluation set and precision/recall curves.

---

## Threat Model

| Threat | Control | Residual Risk |
|---|---|---|
| **Prompt injection** | `detect_injection()` regex on 11 known signatures (including base64 blobs); LLM system prompt uses XML-delimited excerpts and explicit "ignore embedded instructions" directive | Novel jailbreaks not in pattern list; sophisticated LLM-level bypass |
| **PII exfiltration via input** | `redact_pii()` applied to input before retrieval and logging | NER misses in regex-fallback mode; adversarially obfuscated PII |
| **PII leakage via output** | `redact_pii()` applied to LLM output before returning | LLM paraphrasing PII in novel phrasing not matching regex |
| **Question content in logs** | Questions are SHA-256 hashed (32 hex chars) before logging — raw text never written | Brute-force of short/common questions |
| **Secrets in codebase** | All secrets via `.env` / environment variables; `.env` is gitignored; no hardcoded keys | Accidental `git add .env` (mitigated by gitignore + CI pre-commit hook) |
| **Personal data access via questions** | Scope guard blocks `account balance`, `transaction history`, `customer [ID]`, etc. | Creative phrasing not covered by blocklist and above embedding threshold |
| **Hallucination / ungrounded answers** | System prompt instructs LLM to answer only from provided excerpts; citations parsed and returned; explicit no-context fallback message | LLM may still confabulate; citation format mismatch loses attribution |

---

## Observability

Every `/ask` request produces one structured JSON log line to stdout:

```json
{
  "event": "ask_request",
  "request_id": "1528514f-544b-4e9d-b545-bf5913d96efd",
  "question_hash": "73b27e79fbbec3b4a1c2d3e4f5a6b7c8",
  "outcome": "success",
  "latency_ms": 3389.55,
  "prompt_tokens": 517,
  "completion_tokens": 84,
  "total_tokens": 601,
  "session_id": null,
  "error_code": null,
  "timestamp": "2026-07-02T14:11:05.381Z"
}
```

`outcome` values: `success` | `injection_blocked` | `out_of_scope` | `error`

In production these logs feed:
- A cost dashboard (token counts -> OpenAI spend per day)
- A latency SLO dashboard (p50/p95/p99 per outcome type)
- An alert on sustained error rate > 1% over a 5-minute window

---

## SLOs (Production Targets)

| SLO | Target | Measurement |
|---|---|---|
| `POST /ask` p95 latency (successful) | < 5 s | `latency_ms` in logs |
| `POST /ask` p99 latency | < 10 s | `latency_ms` in logs |
| Availability | 99.5% | `/health` liveness probe |
| Guardrail false-positive rate | < 2% of legitimate questions blocked | Manual review sample |
| Hallucination rate | < 10% answers lacking grounded citations | Weekly eval harness run |

Current p95 in evaluation: ~5.1 s (two OpenAI round-trips: embed + generate). Streaming responses would reduce perceived latency significantly.

---

## Project Layout

```
ttb-policy-assistant/
├── app/
│   ├── main.py              # FastAPI app, lifespan, /health + /ask
│   ├── config.py            # pydantic-settings BaseSettings, @lru_cache
│   ├── models.py            # AskRequest, AskResponse, Citation, ErrorResponse
│   ├── ingestion/
│   │   ├── loader.py        # load .md files from policies/
│   │   ├── chunker.py       # MarkdownHeader + Recursive splitter
│   │   ├── embedder.py      # OpenAI batched embed with tenacity retry
│   │   └── indexer.py       # FAISS IndexFlatIP build + load
│   ├── retrieval/
│   │   └── retriever.py     # embed query, normalize, FAISS search
│   ├── generation/
│   │   └── generator.py     # structured prompt, gpt-4o-mini, citation parse
│   ├── guardrails/
│   │   ├── injection.py     # regex patterns for 10 attack signatures
│   │   ├── pii.py           # Presidio + regex fallback
│   │   └── scope.py         # keyword blocklist + embedding cosine gate
│   └── observability/
│       └── logging.py       # structlog JSON logger, log_request()
├── policies/                # 15 synthetic .md policy documents
├── data/faiss_index/        # index.faiss + metadata.json (gitignored)
├── eval/
│   ├── qa_pairs.json        # 18 grounded + 6 adversarial Q&A pairs
│   └── run_eval.py          # in-process httpx + asgi-lifespan eval runner
├── tests/
│   ├── unit/                # test_chunker, test_pii, test_scope, test_injection
│   └── integration/         # test_ask_endpoint (mocked OpenAI + FAISS)
├── scripts/ingest.py        # CLI: loader -> chunker -> embedder -> indexer
├── .env.example
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## What I Would Do With More Time

1. **Streaming responses** — `POST /ask/stream` with server-sent events. The OpenAI SDK supports streaming natively; FastAPI supports SSE via `StreamingResponse`. Reduces perceived latency from ~4 s to first-token in < 1 s.

2. **Hybrid retrieval** — combine BM25 keyword search with dense vector retrieval, merged via Reciprocal Rank Fusion. Improves recall for exact-match queries (specific policy amounts, named sections).

3. **Cross-encoder re-ranking** — add a reranker on top-10 FAISS results before passing top-5 to the LLM. Measurably improves answer groundedness on ambiguous queries.

4. **CI/CD pipeline expansion** — add `docker build` smoke test and eval harness run with a score threshold gate (fail build if overall score < 80%) to the existing GitHub Actions workflow.

5. **Live index updates** — replace FAISS with pgvector so new policy documents can be indexed without a full rebuild and without downtime.

6. **Answer confidence scoring** — embed the generated answer and measure cosine similarity to the retrieved chunks. Flag low-confidence answers for human review before returning.

7. **Rate limiting and authentication** — API key validation or JWT bearer tokens; per-key rate limiting via a Redis token bucket to prevent abuse.

8. **LLM-as-judge eval** — replace keyword-match correctness with a GPT-4o judge that scores semantic equivalence. Add RAGAS metrics (faithfulness, answer relevancy, context precision) for a more defensible quality signal.

9. **Async ingest pipeline** — parallelise embedding calls with `asyncio.gather`; cuts ingest time roughly proportionally to batch count at scale.

10. **Production hardening** — Kubernetes liveness/readiness probes tied to `/health`; graceful shutdown to drain in-flight requests; OpenAI client connection pooling; Sentry for exception tracking.

---

## AI Use Disclosure

This project was built with AI assistance (Claude by Anthropic) for code generation, including the FastAPI application structure, guardrail implementations, test suite, eval harness, and documentation. All generated code was reviewed, debugged, and verified against the assignment specification. The architectural decisions, ADRs, threat model, and trade-offs reflect deliberate engineering choices made during the build process.
