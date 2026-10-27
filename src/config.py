"""
InfraRAG Global Configuration.
Manages environment variables, AWS Bedrock settings, and local/free test modes.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Project metadata
    PROJECT_NAME: str = "InfraRAG"
    APP_ENV: str = "development"

    # AWS Configuration
    AWS_REGION: str = "ap-south-1"  # Mumbai default
    AWS_FALLBACK_REGION: str = "us-east-1"  # N. Virginia fallback for Bedrock models if needed
    S3_BUCKET_NAME: str = "infrarag-storage-runbooks"

    # Amazon Bedrock Models
    # Titan Embeddings v2: 1024 dimensions, normalized
    BEDROCK_EMBEDDING_MODEL_ID: str = "amazon.titan-embed-text-v2:0"
    EMBEDDING_DIMENSION: int = 1024

    # Bedrock Generation Model: Amazon Nova Micro / Claude 3 Haiku for low-cost/free tier
    BEDROCK_LLM_MODEL_ID: str = "amazon.nova-micro-v1:0"

    # 100% Free / Local Development Mode
    # When True, uses local deterministic embeddings & mock generator without making external paid AWS API calls
    USE_MOCK_BEDROCK: bool = True

    # RAG Chunking & Retrieval Parameters
    CHUNK_SIZE: int = 500  # Words / tokens per chunk
    CHUNK_OVERLAP: int = 100  # Overlap between consecutive chunks
    TOP_K: int = 3  # Number of relevant chunks retrieved for generation

    # Local Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data" / "runbooks"
    CACHE_DIR: Path = BASE_DIR / "index_cache"


settings = Settings()
