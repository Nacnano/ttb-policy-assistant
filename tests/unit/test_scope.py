import pytest
from unittest.mock import patch, MagicMock
from app.guardrails.scope import ScopeChecker, _BLOCKLIST_PATTERNS


# Test the keyword blocklist directly
BLOCKED_BY_KEYWORD = [
    "What is my account balance?",
    "Show me the transaction history for customer 12345",
    "Can you check account balance for me?",
    "I want to transfer money to another account",
    "What is the bitcoin price?",
    "Tell me a joke",
    "What is the weather today?",
]

ALLOWED_BY_KEYWORD = [
    "What is the annual leave policy?",
    "How many sick days do I get?",
    "What is the password policy?",
    "Can I work from home?",
    "What are the KYC requirements?",
]


@pytest.mark.parametrize("text", BLOCKED_BY_KEYWORD)
def test_keyword_blocklist_blocks(text):
    for pattern in _BLOCKLIST_PATTERNS:
        if pattern.search(text):
            blocked = True
            break
    else:
        blocked = False
    assert blocked, f"Expected blocked by keyword: {text!r}"


@pytest.mark.parametrize("text", ALLOWED_BY_KEYWORD)
def test_keyword_blocklist_allows(text):
    blocked = any(p.search(text) for p in _BLOCKLIST_PATTERNS)
    assert not blocked, f"Expected allowed by keyword: {text!r}"


def test_scope_checker_no_anchors_allows_everything():
    """Without anchors loaded, scope checker only uses keyword blocklist."""
    checker = ScopeChecker(api_key="fake", base_url="https://api.openai.com/v1")
    # anchor_vectors is None — only blocklist runs
    assert checker.check_scope("What is the leave policy?") is True


def test_scope_checker_blocks_keywords_without_anchors():
    checker = ScopeChecker(api_key="fake", base_url="https://api.openai.com/v1")
    assert checker.check_scope("Show me my account balance") is False


def test_scope_checker_with_low_similarity_rejects():
    """When anchor similarity is below threshold, scope checker should reject."""
    import numpy as np
    checker = ScopeChecker(api_key="fake", base_url="https://api.openai.com/v1", threshold=0.9)

    # Inject mock anchor vectors
    checker._anchor_vectors = np.zeros((10, 1536), dtype="float32")

    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.0] * 1536)]

    with patch.object(checker._client.embeddings, "create", return_value=mock_response):
        result = checker.check_scope("random unrelated query")

    assert result is False
