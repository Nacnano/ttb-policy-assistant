from pydantic import BaseModel, Field, field_validator


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    session_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("question")
    @classmethod
    def _strip_question(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("question must contain at least 3 non-whitespace characters")
        return v


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
    # Codes actually emitted by /ask:
    # INJECTION_DETECTED | OUT_OF_SCOPE | INDEX_NOT_READY | SCOPE_UNAVAILABLE
    # | UPSTREAM_ERROR | INTERNAL_ERROR
    code: str
