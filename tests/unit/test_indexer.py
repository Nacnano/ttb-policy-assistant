import numpy as np
import faiss

from app.ingestion.indexer import build_index, load_index


_CHUNKS = [
    {"chunk_id": "doc.md::chunk_0", "source": "doc.md", "header_path": "A", "text": "chunk zero text"},
    {"chunk_id": "doc.md::chunk_1", "source": "doc.md", "header_path": "B", "text": "chunk one text"},
    {"chunk_id": "doc.md::chunk_2", "source": "doc.md", "header_path": "C", "text": "chunk two text"},
]

_EMBEDDINGS = [
    [1.0, 0.0],
    [0.0, 1.0],
    [1.0, 1.0],
]


def test_build_and_load_index_round_trip(tmp_path):
    index_dir = str(tmp_path / "faiss_index")
    build_index(_EMBEDDINGS, _CHUNKS, index_dir)

    index, metadata = load_index(index_dir)

    assert index.ntotal == len(_CHUNKS)
    assert metadata == [
        {"chunk_id": c["chunk_id"], "source": c["source"], "header_path": c["header_path"], "text": c["text"]}
        for c in _CHUNKS
    ]


def test_search_returns_matching_chunk(tmp_path):
    index_dir = str(tmp_path / "faiss_index")
    build_index(_EMBEDDINGS, _CHUNKS, index_dir)
    index, metadata = load_index(index_dir)

    query = np.array([[1.0, 0.0]], dtype="float32")
    faiss.normalize_L2(query)
    scores, indices = index.search(query, 1)

    best_idx = int(indices[0][0])
    assert metadata[best_idx]["chunk_id"] == "doc.md::chunk_0"
    assert scores[0][0] > 0.99
