"""
CLI ingestion script: load → chunk → embed → index.
Usage: python scripts/ingest.py
Requires OPENAI_API_KEY in environment or .env file.
"""
import sys
from pathlib import Path

# Ensure repo root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.config import get_settings
from app.ingestion.loader import load_policies
from app.ingestion.chunker import chunk_document
from app.ingestion.embedder import embed_chunks
from app.ingestion.indexer import build_index


def main():
    settings = get_settings()

    if not settings.openai_api_key:
        print("ERROR: OPENAI_API_KEY is not set. Add it to .env or export it.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading policies from: {settings.policies_dir}")
    docs = load_policies(settings.policies_dir)
    print(f"  Loaded {len(docs)} documents")

    print("Chunking documents...")
    all_chunks = []
    for doc in docs:
        chunks = chunk_document(doc, chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)
        all_chunks.extend(chunks)
        print(f"  {doc['source']}: {len(chunks)} chunks")
    print(f"  Total: {len(all_chunks)} chunks")

    print(f"Embedding chunks with model: {settings.embedding_model}")
    embeddings = embed_chunks(
        all_chunks,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.embedding_model,
    )
    print(f"  Embedded {len(embeddings)} vectors")

    print(f"Building FAISS index in: {settings.faiss_index_dir}")
    build_index(embeddings, all_chunks, settings.faiss_index_dir)
    print("Ingestion complete.")


if __name__ == "__main__":
    main()
