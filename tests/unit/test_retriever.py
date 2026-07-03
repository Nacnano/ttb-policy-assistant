import numpy as np
import faiss
import pytest
from unittest.mock import MagicMock, patch

from app.retrieval.retriever import Retriever


_METADATA = [
    {"chunk_id": "doc.md::chunk_0", "source": "doc.md", "header_path": "A", "text": "chunk zero text"},
    {"chunk_id": "doc.md::chunk_1", "source": "doc.md", "header_path": "B", "text": "chunk one text"},
    {"chunk_id": "doc.md::chunk_2", "source": "doc.md", "header_path": "C", "text": "chunk two text"},
]


def _make_index():
    """Three normalized vectors with known cosine similarity to query [1, 0]:
    chunk 0 -> 1.0, chunk 1 -> 0.8, chunk 2 -> 0.0."""
    index = faiss.IndexFlatIP(2)
    vectors = np.array(
        [
            [1.0, 0.0],
            [0.8, 0.6],
            [0.0, 1.0],
        ],
        dtype="float32",
    )
    index.add(vectors)
    return index


def _mock_embedding_response(vec):
    resp = MagicMock()
    resp.data = [MagicMock(embedding=list(vec))]
    resp.usage = MagicMock(total_tokens=5)
    return resp


def _make_retriever(index):
    retriever = Retriever(
        index=index, metadata=_METADATA, api_key="fake", base_url="https://api.openai.com/v1"
    )
    return retriever


def test_results_sorted_by_score_descending():
    retriever = _make_retriever(_make_index())
    with patch.object(
        retriever._client.embeddings, "create", return_value=_mock_embedding_response([1.0, 0.0])
    ):
        results = retriever.retrieve("query", top_k=3, min_score=0.0)

    assert len(results) == 3
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert results[0]["chunk_id"] == "doc.md::chunk_0"


def test_chunks_below_min_score_excluded():
    retriever = _make_retriever(_make_index())
    with patch.object(
        retriever._client.embeddings, "create", return_value=_mock_embedding_response([1.0, 0.0])
    ):
        results = retriever.retrieve("query", top_k=3, min_score=0.5)

    ids = [r["chunk_id"] for r in results]
    assert ids == ["doc.md::chunk_0", "doc.md::chunk_1"]


def test_all_below_threshold_returns_empty_list():
    retriever = _make_retriever(_make_index())
    with patch.object(
        retriever._client.embeddings, "create", return_value=_mock_embedding_response([1.0, 0.0])
    ):
        results = retriever.retrieve("query", top_k=3, min_score=1.5)

    assert results == []


def test_faiss_padding_idx_skipped_when_top_k_exceeds_ntotal():
    retriever = _make_retriever(_make_index())
    with patch.object(
        retriever._client.embeddings, "create", return_value=_mock_embedding_response([1.0, 0.0])
    ):
        # top_k > ntotal (3) forces FAISS to pad the result with idx == -1
        results = retriever.retrieve("query", top_k=10, min_score=0.0)

    assert len(results) == 3
    assert all(r["chunk_id"] in {m["chunk_id"] for m in _METADATA} for r in results)
