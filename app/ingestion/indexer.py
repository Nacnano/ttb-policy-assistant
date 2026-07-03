import json
from pathlib import Path

import faiss
import numpy as np

from app.observability.logging import get_logger

logger = get_logger()


def build_index(embeddings: list[list[float]], chunks: list[dict], index_dir: str) -> None:
    """Build FAISS IndexFlatIP (inner-product = cosine after L2 norm) and save to disk."""
    Path(index_dir).mkdir(parents=True, exist_ok=True)

    vectors = np.array(embeddings, dtype="float32")
    faiss.normalize_L2(vectors)

    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)

    faiss.write_index(index, str(Path(index_dir) / "index.faiss"))

    metadata = [
        {"chunk_id": c["chunk_id"], "source": c["source"], "header_path": c["header_path"], "text": c["text"]}
        for c in chunks
    ]
    (Path(index_dir) / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("index_built", vector_count=index.ntotal, dim=dim, index_dir=str(index_dir))


def load_index(index_dir: str) -> tuple[faiss.Index, list[dict]]:
    """Load FAISS index and metadata from disk."""
    index = faiss.read_index(str(Path(index_dir) / "index.faiss"))
    metadata = json.loads((Path(index_dir) / "metadata.json").read_text(encoding="utf-8"))
    return index, metadata
