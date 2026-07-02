import re

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)", re.IGNORECASE),
    re.compile(r"reveal\s+(your\s+)?(system\s+prompt|instructions?|rules?)", re.IGNORECASE),
    re.compile(r"(act|pretend|behave|roleplay)\s+as\s+(if\s+)?(you\s+are\s+)?(?!a\s+staff)", re.IGNORECASE),
    re.compile(r"\bDAN\b"),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"<\|.*?\|>"),
    re.compile(r"you\s+are\s+now\s+(?!a\s+policy)", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous|prior|your)\s+(instructions?|training|rules?)", re.IGNORECASE),
    re.compile(r"(new|updated|override)\s+(system\s+)?(prompt|instructions?|rules?)", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    # Base64 blob of 20+ chars
    re.compile(r"[A-Za-z0-9+/]{20,}={0,2}"),
]


def detect_injection(text: str) -> bool:
    """Return True if the text appears to be a prompt injection attempt."""
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False
