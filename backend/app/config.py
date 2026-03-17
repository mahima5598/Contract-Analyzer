"""Application configuration loaded from environment variables."""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(
        extra="allow",
        env_file=".env",
    )

    openai_api_key: str = ""
    model_name: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    chunk_size: int = 1500
    chunk_overlap: int = 200
    retrieval_k: int = 8


settings = Settings()