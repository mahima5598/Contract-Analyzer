"""Application configuration loaded from environment variables."""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from dotenv import load_dotenv
import os
import logging

load_dotenv()

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    model_config = ConfigDict(
        extra="allow",
        env_file=".env",
    )

    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    model_name: str = "llama-3.1-8b-instant"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size: int = 1500
    chunk_overlap: int = 200
    retrieval_k: int = 8


settings = Settings()

if not settings.groq_api_key:
    logger.warning("⚠️  GROQ_API_KEY is not set")