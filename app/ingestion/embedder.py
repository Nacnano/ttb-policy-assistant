import time
import openai
from tenacity import retry, stop_after_attempt, wait_exponential


_BATCH_SIZE = 100


def _get_client(api_key: str, base_url: str) -> openai.OpenAI:
    return openai.OpenAI(api_key=api_key, base_url=base_url)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _embed_batch(client: openai.OpenAI, texts: list[str], model: str) -> list[list[float]]:
    response = client.embeddings.create(input=texts, model=model)
    return [item.embedding for item in response.data]


def embed_chunks(
    chunks: list[dict],
    api_key: str,
    base_url: str,
    model: str = "text-embedding-3-small",
) -> list[list[float]]:
    """Embed all chunk texts in batches. Returns list of embedding vectors."""
    client = _get_client(api_key, base_url)
    texts = [c["text"] for c in chunks]
    embeddings = []

    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        batch_embeddings = _embed_batch(client, batch, model)
        embeddings.extend(batch_embeddings)
        if i + _BATCH_SIZE < len(texts):
            time.sleep(0.1)  # brief pause between batches

    return embeddings
