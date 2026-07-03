"""
PII redaction using Presidio (with spaCy NLP) when available,
falling back to regex-only redaction if the spaCy model is not installed.
"""
import re
from typing import Optional

import structlog

_logger = structlog.get_logger("ttb.pii")

# --- Regex-only fallback patterns ---
# Order matters: email first, then the most specific numeric patterns before the greedy
# phone pattern, so a bare 13-digit Thai ID is not mislabelled as a phone number (L4).
_REGEX_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"), "<EMAIL_ADDRESS>"),
    (re.compile(r"\b[0-9]{13}\b"), "<THAI_NATIONAL_ID>"),
    (re.compile(r"\b[0-9]{10,16}\b"), "<BANK_ACCOUNT>"),
    (re.compile(r"\+?[\d\s\-().]{10,17}(?=\s|$|[,.])", re.MULTILINE), "<PHONE_NUMBER>"),
]


def _regex_redact(text: str) -> str:
    """Regex-only fallback redaction. Covers email, Thai ID, bank account, and phone.
    NOTE: cannot detect PERSON names — that requires the Presidio/spaCy NER path."""
    for pattern, replacement in _REGEX_RULES:
        text = pattern.sub(replacement, text)
    return text

# --- Presidio setup (optional) ---
_presidio_available = False
_analyzer = None
_anonymizer = None


def _try_init_presidio():
    global _presidio_available, _analyzer, _anonymizer
    try:
        from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
        from presidio_analyzer.nlp_engine import SpacyNlpEngine
        from presidio_anonymizer import AnonymizerEngine

        # Explicitly use en_core_web_sm so Presidio does not auto-download en_core_web_lg
        nlp_engine = SpacyNlpEngine(
            models=[{"lang_code": "en", "model_name": "en_core_web_sm"}]
        )
        analyzer = AnalyzerEngine(nlp_engine=nlp_engine)

        thai_id_recognizer = PatternRecognizer(
            supported_entity="THAI_NATIONAL_ID",
            patterns=[Pattern("THAI_NATIONAL_ID", r"\b[0-9]{13}\b", 0.85)],
            context=["id", "national", "citizen"],
        )
        bank_account_recognizer = PatternRecognizer(
            supported_entity="BANK_ACCOUNT",
            patterns=[Pattern("BANK_ACCOUNT", r"\b[0-9]{10,16}\b", 0.75)],
            context=["account", "acc", "acct"],
        )
        analyzer.registry.add_recognizer(thai_id_recognizer)
        analyzer.registry.add_recognizer(bank_account_recognizer)

        # Warm up to catch model-not-found errors early
        analyzer.analyze(text="test", entities=["EMAIL_ADDRESS"], language="en")

        _analyzer = analyzer
        _anonymizer = AnonymizerEngine()
        _presidio_available = True
        _logger.info("pii_engine_initialized", engine="presidio")
    except Exception as exc:
        _presidio_available = False
        # WARNING, not info: in the container Presidio+spaCy are always installed, so this
        # path means degraded redaction (no PERSON detection) — it must be visible.
        _logger.warning("pii_engine_degraded", engine="regex_fallback", reason=str(exc))


_try_init_presidio()

_PRESIDIO_ENTITIES = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "PERSON",
    "THAI_NATIONAL_ID",
    "BANK_ACCOUNT",
]


def redact_pii(text: str) -> str:
    """Redact PII from text. Uses Presidio if available, else regex fallback."""
    if not text:
        return text

    if _presidio_available and _analyzer and _anonymizer:
        try:
            results = _analyzer.analyze(text=text, entities=_PRESIDIO_ENTITIES, language="en")
            if results:
                return _anonymizer.anonymize(text=text, analyzer_results=results).text
            return text
        except Exception as exc:
            _logger.warning("presidio_runtime_error", error=str(exc))

    # Regex fallback
    return _regex_redact(text)
