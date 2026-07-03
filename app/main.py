import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models import AskRequest, AskResponse, Citation, ErrorResponse
from app.ingestion.indexer import load_index
from app.retrieval.retriever import Retriever
from app.generation.generator import Generator
from app.guardrails.injection import detect_injection
from app.guardrails.pii import redact_pii
from app.guardrails.scope import ScopeChecker
from app.observability.logging import configure_logging, get_logger, log_request

logger = get_logger()

# Global state populated during lifespan
_retriever: Retriever | None = None
_generator: Generator | None = None
_scope_checker: ScopeChecker | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _retriever, _generator, _scope_checker
    configure_logging()
    settings = get_settings()

    if not settings.openai_api_key:
        logger.warning("openai_api_key_empty", msg="OPENAI_API_KEY is not set. LLM calls will fail.")

    try:
        index, metadata = load_index(settings.faiss_index_dir)
        _retriever = Retriever(
            index=index,
            metadata=metadata,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            embedding_model=settings.embedding_model,
        )
        logger.info("retriever_loaded", chunk_count=len(metadata))
    except Exception as exc:
        logger.warning("faiss_index_not_found", path=settings.faiss_index_dir, error=str(exc))

    _generator = Generator(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.chat_model,
        temperature=settings.generation_temperature,
        max_tokens=settings.generation_max_tokens,
    )

    _scope_checker = ScopeChecker(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        embedding_model=settings.embedding_model,
        threshold=settings.scope_similarity_threshold,
    )
    if settings.openai_api_key:
        try:
            _scope_checker.load_anchors()
            logger.info("scope_anchors_loaded")
        except Exception as e:
            logger.warning("scope_anchors_failed", error=str(e))

    yield
    # cleanup (nothing needed for FAISS)


app = FastAPI(title="TTB Policy Assistant", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def inject_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Backstop: no request path should escape without a structured error + log."""
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "unhandled_exception",
        request_id=request_id,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(error="Internal server error.", code="INTERNAL_ERROR").model_dump(),
    )


@app.get("/health")
async def health():
    return {"status": "ok", "index_ready": _retriever is not None}


@app.post("/ask", response_model=AskResponse, responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
async def ask(body: AskRequest, request: Request):
    start = time.perf_counter()
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    settings = get_settings()

    # 1. Injection check
    if detect_injection(body.question):
        latency_ms = (time.perf_counter() - start) * 1000
        log_request(logger, request_id, body.question, "injection_blocked", latency_ms,
                    session_id=body.session_id, error_code="INJECTION_DETECTED")
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(error="Prompt injection detected.", code="INJECTION_DETECTED").model_dump(),
        )

    # 2. PII redaction on input
    redacted_question = redact_pii(body.question)

    try:
        # 3. Scope check — fail CLOSED. If the semantic gate was expected (an API key is
        #    configured) but its anchors could not be loaded, refuse rather than silently
        #    degrading to the keyword blocklist only.
        if _scope_checker is not None:
            if settings.openai_api_key and not _scope_checker.anchors_ready:
                latency_ms = (time.perf_counter() - start) * 1000
                logger.warning("scope_gate_unavailable", request_id=request_id)
                log_request(logger, request_id, body.question, "error", latency_ms,
                            session_id=body.session_id, error_code="SCOPE_UNAVAILABLE")
                raise HTTPException(
                    status_code=503,
                    detail=ErrorResponse(
                        error="Scope guardrail is unavailable; refusing to answer.",
                        code="SCOPE_UNAVAILABLE",
                    ).model_dump(),
                )
            if not _scope_checker.check_scope(redacted_question):
                latency_ms = (time.perf_counter() - start) * 1000
                log_request(logger, request_id, body.question, "out_of_scope", latency_ms,
                            session_id=body.session_id, error_code="OUT_OF_SCOPE")
                raise HTTPException(
                    status_code=400,
                    detail=ErrorResponse(
                        error="This question is outside the scope of bank policy topics.",
                        code="OUT_OF_SCOPE",
                    ).model_dump(),
                )

        # 4. Retrieval
        if _retriever is None:
            latency_ms = (time.perf_counter() - start) * 1000
            log_request(logger, request_id, body.question, "error", latency_ms,
                        session_id=body.session_id, error_code="INDEX_NOT_READY")
            raise HTTPException(
                status_code=503,
                detail=ErrorResponse(
                    error="Knowledge base not ready. Run scripts/ingest.py first.",
                    code="INDEX_NOT_READY",
                ).model_dump(),
            )
        chunks = _retriever.retrieve(
            redacted_question, top_k=settings.top_k, min_score=settings.retrieval_min_score
        )
        embedding_tokens = _scope_checker.last_embed_tokens if _scope_checker else 0
        embedding_tokens += _retriever.last_embed_tokens

        # 5. No chunk cleared the relevance floor → grounded refusal, skip the LLM call.
        if not chunks:
            latency_ms = (time.perf_counter() - start) * 1000
            safe_answer = "I could not find the answer in the available policies."
            log_request(logger, request_id, body.question, "no_context", latency_ms,
                        embedding_tokens=embedding_tokens, session_id=body.session_id)
            return AskResponse(
                answer=safe_answer, citations=[], model=settings.chat_model,
                prompt_tokens=0, completion_tokens=0, latency_ms=round(latency_ms, 2),
            )

        # 6. Generation
        result = _generator.generate(redacted_question, chunks)

        # 7. PII redaction on output
        safe_answer = redact_pii(result["answer"])

        latency_ms = (time.perf_counter() - start) * 1000

        # 8. Log
        log_request(
            logger,
            request_id,
            body.question,
            "success",
            latency_ms,
            prompt_tokens=result["prompt_tokens"],
            completion_tokens=result["completion_tokens"],
            embedding_tokens=embedding_tokens,
            session_id=body.session_id,
        )

        return AskResponse(
            answer=safe_answer,
            citations=result["citations"],
            model=result["model"],
            prompt_tokens=result["prompt_tokens"],
            completion_tokens=result["completion_tokens"],
            latency_ms=round(latency_ms, 2),
        )

    except HTTPException:
        raise
    except Exception as exc:
        # Upstream failure (OpenAI timeout / rate-limit / parse error). Emit structured
        # telemetry so the failure is debuggable, and return the documented error shape.
        latency_ms = (time.perf_counter() - start) * 1000
        logger.error("ask_upstream_error", request_id=request_id,
                     error=str(exc), error_type=type(exc).__name__)
        log_request(logger, request_id, body.question, "error", latency_ms,
                    session_id=body.session_id, error_code="UPSTREAM_ERROR")
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error="The assistant is temporarily unavailable. Please retry shortly.",
                code="UPSTREAM_ERROR",
            ).model_dump(),
        )
