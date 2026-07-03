import re

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?)", re.IGNORECASE),
    re.compile(r"reveal\s+(your\s+)?(system\s+prompt|instructions?|rules?)", re.IGNORECASE),
    # "pretend"/"roleplay" are strong signals; rarely legitimate in policy Q&A.
    re.compile(r"(pretend|roleplay)\s+(to\s+be|you(?:'re|\s+are)|as)\b", re.IGNORECASE),
    # "act/behave as" only when the target is an adversarial persona — NOT "act as an
    # approving manager" (a legitimate policy question).
    re.compile(r"(act|behave)\s+as\s+(an?\s+)?(unrestricted|unfiltered|jailbroken|evil|malicious|hacker|dan\b|different\s+(ai|assistant|model|bot))", re.IGNORECASE),
    # Case-SENSITIVE: the "DAN" jailbreak, not the given name "Dan".
    re.compile(r"\bDAN\b"),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"<\|.*?\|>"),
    # "you are now …" only for adversarial reassignments, not "you are now able to…".
    re.compile(r"you\s+are\s+now\s+(an?\s+)?(different|unrestricted|unfiltered|jailbroken|evil|new\s+(ai|assistant|model)|dan\b)", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous|prior|your)\s+(instructions?|training|rules?)", re.IGNORECASE),
    re.compile(r"(new|updated|override)\s+(system\s+)?(prompt|instructions?|rules?)", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    # Base64 blob — require 60+ chars to avoid false positives on normal text
    re.compile(r"(?<!\w)[A-Za-z0-9+/]{60,}={0,2}(?!\w)"),
]


def detect_injection(text: str) -> bool:
    """Return True if the text appears to be a prompt injection attempt."""
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False
