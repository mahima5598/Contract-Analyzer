"""Application configuration loaded from environment variables."""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseSettings):
    model_config = ConfigDict(
        extra="allow",
        env_file=".env",
    )

    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    model_name: str = "gemini-1.5-flash"
    embedding_model: str = "text-embedding-3-small"
    chunk_size: int = 1500
    chunk_overlap: int = 200
    retrieval_k: int = 8


settings = Settings()