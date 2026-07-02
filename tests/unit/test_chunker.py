import pytest
from app.ingestion.chunker import chunk_document


SAMPLE_DOC = {
    "source": "test_policy.md",
    "content": """# Test Policy

## Section One

This is the first section with some content about bank policies and procedures.
It contains multiple sentences to ensure it gets chunked properly.

## Section Two

This is the second section. It covers different topics.

### Subsection 2.1

Detailed information in a subsection.
""",
}

LONG_DOC = {
    "source": "long_policy.md",
    "content": "# Long Policy\n\n## Big Section\n\n" + ("This is a long sentence about bank policy. " * 30),
}


def test_chunk_returns_list():
    chunks = chunk_document(SAMPLE_DOC)
    assert isinstance(chunks, list)
    assert len(chunks) > 0


def test_chunk_has_required_fields():
    chunks = chunk_document(SAMPLE_DOC)
    for chunk in chunks:
        assert "chunk_id" in chunk
        assert "source" in chunk
        assert "header_path" in chunk
        assert "text" in chunk


def test_chunk_source_preserved():
    chunks = chunk_document(SAMPLE_DOC)
    for chunk in chunks:
        assert chunk["source"] == "test_policy.md"


def test_chunk_id_unique():
    chunks = chunk_document(SAMPLE_DOC)
    ids = [c["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids))


def test_chunk_id_contains_source():
    chunks = chunk_document(SAMPLE_DOC)
    for chunk in chunks:
        assert "test_policy.md" in chunk["chunk_id"]


def test_long_section_is_split():
    chunks = chunk_document(LONG_DOC, chunk_size=200, chunk_overlap=40)
    # The long section should be split into multiple chunks
    assert len(chunks) > 1


def test_chunk_text_not_empty():
    chunks = chunk_document(SAMPLE_DOC)
    for chunk in chunks:
        assert chunk["text"].strip() != ""


def test_header_path_populated():
    chunks = chunk_document(SAMPLE_DOC)
    # At least some chunks should have a non-empty header_path
    non_empty_headers = [c for c in chunks if c["header_path"]]
    assert len(non_empty_headers) > 0


def test_chunk_size_respected():
    chunks = chunk_document(LONG_DOC, chunk_size=200, chunk_overlap=40)
    for chunk in chunks:
        # Allow some slack for overlap, but no chunk should be massively oversized
        assert len(chunk["text"]) <= 400
