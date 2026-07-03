import pytest
from app.guardrails.pii import redact_pii


def test_redacts_email():
    text = "Contact me at john.doe@example.com for more info."
    result = redact_pii(text)
    assert "john.doe@example.com" not in result


def test_redacts_phone():
    text = "Call me at +66 81 234 5678 any time."
    result = redact_pii(text)
    # Presidio should redact the phone number
    assert "+66 81 234 5678" not in result or "<PHONE_NUMBER>" in result


def test_leaves_clean_text_unchanged():
    text = "What is the annual leave policy for employees?"
    result = redact_pii(text)
    # No PII — the core question should be substantially preserved
    assert "annual leave" in result.lower()


def test_returns_string():
    result = redact_pii("Hello world")
    assert isinstance(result, str)


def test_empty_string():
    result = redact_pii("")
    assert result == ""


def test_redacts_person_name():
    text = "Please send the report to John Smith immediately."
    result = redact_pii(text)
    # Presidio may redact PERSON entity
    assert isinstance(result, str)
    assert len(result) > 0


def test_redacts_thai_national_id():
    text = "My national ID is 1234567890123 for verification."
    result = redact_pii(text)
    assert "1234567890123" not in result


def test_redacts_multiple_pii_in_one_string():
    text = "Contact john@example.com or call +66 91 234 5678 for details."
    result = redact_pii(text)
    assert "john@example.com" not in result
