from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    session_id: str | None = None


class Citation(BaseModel):
    source: str
    chunk_id: str
    excerpt: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float


class ErrorResponse(BaseModel):
    error: str
    code: str  # OUT_OF_SCOPE | PII_BLOCKED | INJECTION_DETECTED | VALIDATION_ERROR
