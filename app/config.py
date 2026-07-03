from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    chat_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    policies_dir: str = "policies"
    faiss_index_dir: str = "data/faiss_index"
    log_level: str = "INFO"
    top_k: int = 5
    chunk_size: int = 400
    chunk_overlap: int = 80
    scope_similarity_threshold: float = 0.30
    retrieval_min_score: float = 0.25  # drop retrieved chunks below this cosine score
    generation_temperature: float = 0.0  # 0 = deterministic (reproducible eval)
    generation_max_tokens: int = Field(default=1024, gt=0)  # cap on generated answer length


@lru_cache
def get_settings() -> Settings:
    return Settings()
