# ttb Policy Assistant

A small RAG microservice that answers staff questions about ttb bank policies. Ask it a question over HTTP and it retrieves the relevant policy chunks from a FAISS index, generates an answer grounded in those chunks with citations, and refuses anything off-topic or adversarial.

Built as a take-home for ttb's AI Centre of Excellence, and treated as code headed for stabilization rather than a demo: guardrails, structured telemetry, tests, an eval gate, and Docker.

## How to run

You need Python 3.11+ and an OpenAI API key.

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm   # optional: full PII detection (regex fallback otherwise)

cp .env.example .env                      # then set OPENAI_API_KEY=sk-...
python scripts/ingest.py                  # chunk + embed + index the policies (one-time)
uvicorn app.main:app --reload             # interactive docs at http://localhost:8000/docs
```

Try it:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How many days of annual leave am I entitled to?"}'
```

Tests need no API key — OpenAI is mocked:

```bash
pytest   # 95 tests: unit (chunking, guardrails, retrieval, generation) + /ask integration
```

CI (GitHub Actions) runs the suite on Python 3.11 and 3.12 and verifies the Docker image builds on every push.

### Docker

```bash
# The key is passed as a BuildKit secret to bake the index at build time,
# so it never lands in an image layer (a build-arg or ENV would leak via `docker history`).
DOCKER_BUILDKIT=1 docker build --secret id=openai_key,env=OPENAI_API_KEY -t ttb-policy-assistant .
docker run --env-file .env -p 8000:8000 ttb-policy-assistant

# or: OPENAI_API_KEY=$OPENAI_API_KEY docker compose up --build
```

Without the build secret the image still builds — the index just isn't baked, and `/ask` returns `503 INDEX_NOT_READY` until you ingest into a mounted volume. The container runs as a non-root user with a `HEALTHCHECK` on `GET /health`. That check is liveness only: it stays green even if OpenAI is down, since that failure mode surfaces on `/ask` as a 503.

## API

`GET /health` → `{"status": "ok", "index_ready": true}`

`POST /ask` takes `{"question": "...", "session_id": "optional"}` and returns:

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

Errors come back as `{"detail": {"error": "...", "code": "..."}}`:

| Code | Status | Meaning |
|---|---|---|
| `INJECTION_DETECTED` | 400 | prompt-injection signature matched |
| `OUT_OF_SCOPE` | 400 | not a bank-policy question |
| — | 422 | request validation failed (FastAPI default shape) |
| `INDEX_NOT_READY` | 503 | knowledge base not built yet |
| `SCOPE_UNAVAILABLE` | 503 | scope guardrail couldn't load — failing closed |
| `UPSTREAM_ERROR` | 503 | OpenAI call failed (timeout, rate limit, ...) |
| `INTERNAL_ERROR` | 500 | backstop — no exception escapes without a structured body and a log line |

## How it works

```
POST /ask
  ├─ Pydantic validation (question length, session_id charset)
  ├─ injection detection: 12 regex attack signatures            → 400
  ├─ PII redaction on input (Presidio + regex fallback)
  ├─ scope gate: keyword blocklist, then embedding cosine       → 400 out-of-scope
  │    (fails CLOSED with 503 if the semantic gate can't load)
  ├─ FAISS retrieval: top-5 chunks above a relevance floor
  │    (nothing clears the floor → grounded refusal, no LLM call)
  ├─ generation at temp 0: XML-delimited excerpts, citation parsing
  ├─ PII redaction on output
  └─ one structured JSON log line, on every path
```

Ingestion (`python scripts/ingest.py`): load `policies/*.md` → split on Markdown headers, recursive fallback for long sections → batch-embed → FAISS index + metadata on disk.

## Design decisions (ADRs)

**ADR-001 — FAISS over pgvector / Azure AI Search.** I wanted zero infrastructure: FAISS runs in-process, persists as two files, and exact search over ~130 chunks takes under a millisecond. The trade-off is scalability — every replica carries its own index and adding documents means a rebuild. At thousands of documents I'd move to pgvector or Azure AI Search; the retriever interface is thin enough that it's a one-file swap.

**ADR-002 — `gpt-4o-mini` + `text-embedding-3-small`.** Factual policy Q&A doesn't need a frontier model, and 4o-mini is 10–20x cheaper than GPT-4o. Both models are available on Azure OpenAI, so migrating is a `OPENAI_BASE_URL` change. The trade-off is depending on OpenAI's shared capacity; for production SLAs I'd use Azure Provisioned Throughput.

**ADR-003 — header-aware chunking with a recursive fallback.** Markdown headers mark real semantic boundaries in policy docs (an "Annual Leave" section stays intact), so I split on those first and only fall back to recursive character splitting (400 chars, 80 overlap) for oversized sections. Each chunk's source + header path is prefixed to the text that gets embedded and shown to the LLM, so sub-chunks that lost their header line still carry context. This relies on authors actually using headers — PDFs would need a different extraction step.

**ADR-004 — Presidio for PII, with a regex fallback.** Presidio gives a pluggable redaction pipeline, extended with custom recognizers for Thai national IDs and bank account numbers. If the spaCy model isn't installed, the service still starts and falls back to regex for email/phone/Thai ID — degraded but never absent, and it logs a WARNING so the degradation is visible. The fallback can't catch person names; the Dockerfile installs the spaCy model so production always has full coverage.

**ADR-005 — two-layer scope guard, failing closed.** A keyword blocklist catches the obvious off-topic asks (account balances, crypto, weather) for free; an embedding-similarity gate against 15 in-scope anchor phrases (threshold 0.30, configurable) catches the subtler ones. If the anchors can't load while an API key is configured, the service refuses with `503 SCOPE_UNAVAILABLE` rather than silently degrading to keywords only — a security gate should never disappear unnoticed. The threshold is heuristic; with more time I'd tune it against a labelled set.

## Threat model

| Threat | Control | Residual risk |
|---|---|---|
| Prompt injection | 12 regex signatures (incl. base64 blobs), tuned against false positives; XML-delimited excerpts + explicit "ignore embedded instructions" in the system prompt | novel jailbreaks; patterns are English-only (Thai relies on the embedding scope gate) |
| PII in input | redacted before retrieval and before logging | NER misses in regex-fallback mode (a WARNING makes the degraded mode visible) |
| PII in output | redacted before returning | LLM paraphrasing PII into shapes the regex won't match |
| Question content in logs | only a SHA-256 hash is logged, never raw text; `session_id` constrained to `[A-Za-z0-9_-]{1,64}` against log forging | brute-forcing short common questions |
| Secrets in the repo | env vars only, `.env` gitignored, BuildKit secret for the Docker build | an accidental `git add .env` |
| Customer-data fishing | blocklist (account balance, customer IDs, transactions) + embedding gate; fails closed on gate failure | creative phrasing above the similarity threshold; English-only keywords |
| Hallucination | system prompt restricts answers to provided excerpts; relevance floor short-circuits to a refusal; citations reflect only what the model actually cited — no fabricated fallbacks | the model can still confabulate within its excerpts |

## Observability

Every request — success or any failure path — emits exactly one `ask_request` JSON line to stdout, so no outcome is invisible on a dashboard:

```json
{
  "event": "ask_request",
  "request_id": "1528514f-...",
  "question_hash": "73b27e79...",
  "outcome": "success",
  "latency_ms": 3389.55,
  "prompt_tokens": 517,
  "completion_tokens": 84,
  "embedding_tokens": 22,
  "total_tokens": 623,
  "error_code": null,
  "timestamp": "2026-07-02T14:11:05.381Z"
}
```

`outcome` is one of `success | no_context | injection_blocked | out_of_scope | error`. `embedding_tokens` counts the scope-gate and retrieval embedding calls too, so `total_tokens` reflects true per-request OpenAI spend, not just chat tokens. In production these lines feed a cost dashboard, a latency SLO dashboard (p50/p95/p99 per outcome), and an alert on sustained error rate.

## SLOs (production targets)

| SLO | Target | Measured via |
|---|---|---|
| `/ask` p95 latency (successful) | < 5 s | `latency_ms` in logs |
| `/ask` p99 latency | < 10 s | `latency_ms` in logs |
| Availability | 99.5% | `/health` liveness probe |
| Guardrail false-positive rate | < 2% of legitimate questions | manual review sample |
| Hallucination rate | < 10% answers without grounded citations | weekly eval run |

Current p95 in evaluation is ~5.1 s — two sequential OpenAI round-trips (embed, then generate). Streaming would cut perceived latency the most.

## Eval harness

```bash
python eval/run_eval.py   # needs OPENAI_API_KEY + a freshly built index (run scripts/ingest.py first)
```

Runs 18 grounded questions plus 6 adversarial ones in-process against the real `/ask` path, at temperature 0 so results are reproducible; model and embedding IDs are printed for provenance. A grounded answer scores only if the expected fact appears **and** the expected source is cited — correctness without attribution doesn't count.

Last verified run (`gpt-4o-mini` / `text-embedding-3-small`): **groundedness 100% (18/18), adversarial 100% (6/6)**. The honest caveat: keyword-matching against paraphrased LLM output isn't perfectly stable even at temp 0 — an earlier run scored 16/18 before a keyword was broadened. That's why the harness enforces a gate (grounded ≥ 80% and adversarial = 100%) and exits non-zero on failure, rather than promising a flat 100%.

## What I cut, and what I'd do next

I kept to the assignment's 1–2 day time-box, which meant cutting deliberately: no auth or rate limiting (internal single-tenant demo), keyword-match eval instead of an LLM judge (cruder, but deterministic and free), no streaming, no hybrid retrieval, and guardrail patterns in English only — Thai coverage leans on the multilingual embedding gate.

With more time, roughly in order:

1. **LLM-as-judge eval** — replace keyword matching with a GPT-4o judge plus RAGAS metrics (faithfulness, context precision) for a more defensible quality signal.
2. **Streaming responses** — SSE via `StreamingResponse`; first token in under a second instead of ~4 s.
3. **Hybrid retrieval + re-ranking** — BM25 merged with dense retrieval via reciprocal rank fusion, and a cross-encoder over the top 10; helps exact-match queries like specific allowance amounts.
4. **pgvector** — live index updates without rebuilds or downtime.
5. **Auth + rate limiting** — API keys or JWT, Redis token bucket.
6. **Ops hardening** — eval-gate step in CI, readiness probes, graceful shutdown, exception tracking.

## AI use disclosure

I built this with AI assistance (Claude, by Anthropic) doing much of the code generation: the FastAPI scaffolding, guardrail implementations, tests, eval harness, and drafts of this README. I directed the architecture, reviewed and debugged all of the generated code, and verified the behaviour against the assignment spec — the design decisions, threat model, and trade-offs above are choices I made and can defend.
