from unittest.mock import MagicMock

import app.ingestion.embedder as embedder
from app.ingestion.embedder import _embed_text, embed_chunks


def test_embed_text_prefixes_source_and_header_path():
    chunk = {"source": "leave.md", "header_path": "Leave Policy > Annual Leave", "text": "15 days per year."}
    result = _embed_text(chunk)
    assert result == "leave.md — Leave Policy > Annual Leave\n15 days per year."


def test_embed_text_falls_back_to_source_when_header_path_empty():
    chunk = {"source": "leave.md", "header_path": "", "text": "15 days per year."}
    result = _embed_text(chunk)
    assert result == "leave.md — leave.md\n15 days per year."


def test_embed_text_falls_back_to_source_when_header_path_none():
    chunk = {"source": "leave.md", "header_path": None, "text": "15 days per year."}
    result = _embed_text(chunk)
    assert result == "leave.md — leave.md\n15 days per year."


def test_embed_chunks_batches_and_preserves_order(monkeypatch):
    monkeypatch.setattr(embedder, "_BATCH_SIZE", 2)
    monkeypatch.setattr(embedder, "_get_client", lambda api_key, base_url: MagicMock())

    fake_embed_batch = MagicMock(side_effect=lambda client, texts, model: [[t] for t in texts])
    monkeypatch.setattr(embedder, "_embed_batch", fake_embed_batch)
    monkeypatch.setattr(embedder.time, "sleep", lambda s: None)

    chunks = [
        {"source": "doc.md", "header_path": f"Section {i}", "text": f"text {i}"} for i in range(5)
    ]

    result = embed_chunks(chunks, api_key="fake", base_url="https://api.openai.com/v1")

    # 5 chunks / batch size 2 -> ceil(5/2) = 3 batches
    assert fake_embed_batch.call_count == 3
    expected_texts = [_embed_text(c) for c in chunks]
    assert result == [[t] for t in expected_texts]
