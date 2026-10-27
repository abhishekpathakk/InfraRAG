"""
InfraRAG Global Configuration.
Manages environment variables, AWS Bedrock settings, and local/free test modes.
Supports pydantic-settings when available, with standard library os.environ fallback for Lambda.
"""

import os
from pathlib import Path

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
        )

        PROJECT_NAME: str = "InfraRAG"
        APP_ENV: str = "development"
        AWS_REGION: str = os.getenv("AWS_REGION", "ap-south-1")
        AWS_FALLBACK_REGION: str = "us-east-1"
        S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "infrarag-storage-runbooks")

        BEDROCK_EMBEDDING_MODEL_ID: str = os.getenv("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")
        EMBEDDING_DIMENSION: int = 1024
        BEDROCK_LLM_MODEL_ID: str = os.getenv("BEDROCK_LLM_MODEL_ID", "amazon.nova-micro-v1:0")

        USE_MOCK_BEDROCK: bool = os.getenv("USE_MOCK_BEDROCK", "true").lower() in ("true", "1", "yes")
        CHUNK_SIZE: int = 500
        CHUNK_OVERLAP: int = 100
        TOP_K: int = 3

        BASE_DIR: Path = Path(__file__).resolve().parent.parent
        DATA_DIR: Path = BASE_DIR / "data" / "runbooks"
        CACHE_DIR: Path = BASE_DIR / "index_cache"

    settings = Settings()

except ImportError:
    class StandaloneSettings:
        def __init__(self):
            self.PROJECT_NAME = "InfraRAG"
            self.APP_ENV = "production"
            self.AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
            self.AWS_FALLBACK_REGION = "us-east-1"
            self.S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "infrarag-storage-runbooks")
            self.BEDROCK_EMBEDDING_MODEL_ID = os.getenv("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")
            self.EMBEDDING_DIMENSION = 1024
            self.BEDROCK_LLM_MODEL_ID = os.getenv("BEDROCK_LLM_MODEL_ID", "amazon.nova-micro-v1:0")
            self.USE_MOCK_BEDROCK = os.getenv("USE_MOCK_BEDROCK", "false").lower() in ("true", "1", "yes")
            self.CHUNK_SIZE = 500
            self.CHUNK_OVERLAP = 100
            self.TOP_K = 3
            self.BASE_DIR = Path("/tmp")
            self.DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "runbooks"
            self.CACHE_DIR = Path("/tmp/faiss_index")

    settings = StandaloneSettings()
