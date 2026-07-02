import hashlib
import logging
import sys
import structlog
from app.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str = "ttb.policy"):
    return structlog.get_logger(name)


def hash_question(question: str) -> str:
    """One-way hash of question so logs contain no PII."""
    return hashlib.sha256(question.encode()).hexdigest()[:16]


def log_request(
    logger,
    request_id: str,
    question: str,
    outcome: str,
    latency_ms: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    session_id: str | None = None,
    error_code: str | None = None,
) -> None:
    logger.info(
        "ask_request",
        request_id=request_id,
        question_hash=hash_question(question),
        outcome=outcome,
        latency_ms=round(latency_ms, 2),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        session_id=session_id,
        error_code=error_code,
    )
