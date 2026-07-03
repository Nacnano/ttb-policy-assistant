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
        self._client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=30.0)
        self._embedding_model = embedding_model
        self.last_embed_tokens = 0

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _embed_query(self, query: str) -> np.ndarray:
        response = await self._client.embeddings.create(input=[query], model=self._embedding_model)
        usage = getattr(response, "usage", None)
        tokens = getattr(usage, "total_tokens", 0)
        # Guard against mocked usage (MagicMock) in tests
        self.last_embed_tokens = tokens if isinstance(tokens, int) else 0
        vec = np.array([response.data[0].embedding], dtype="float32")
        faiss.normalize_L2(vec)
        return vec

    async def retrieve(self, query: str, top_k: int = 5, min_score: float = 0.0) -> list[dict]:
        """Return chunks scoring above `min_score`, most similar first (max top_k)."""
        query_vec = await self._embed_query(query)
        scores, indices = self._index.search(query_vec, top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            if float(score) < min_score:
                continue  # relevance floor: don't feed weak matches to the LLM
            chunk = self._metadata[idx].copy()
            chunk["score"] = float(score)
            results.append(chunk)
        return results
