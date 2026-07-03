import numpy as np
import openai
import faiss
from tenacity import retry, stop_after_attempt, wait_exponential


class Retriever:
    def __init__(
        self,
        index: faiss.Index,
        metadata: list[dict],
        api_key: str,
        base_url: str,
        embedding_model: str = "text-embedding-3-small",
    ):
        self._index = index
        self._metadata = metadata
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=30.0)
        self._embedding_model = embedding_model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _embed_query(self, query: str) -> np.ndarray:
        response = self._client.embeddings.create(input=[query], model=self._embedding_model)
        vec = np.array([response.data[0].embedding], dtype="float32")
        faiss.normalize_L2(vec)
        return vec

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """Return top_k most similar chunks."""
        query_vec = self._embed_query(query)
        scores, indices = self._index.search(query_vec, top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            chunk = self._metadata[idx].copy()
            chunk["score"] = float(score)
            results.append(chunk)
        return results
