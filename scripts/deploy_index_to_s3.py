#!/usr/bin/env python3
"""
Uploads runbooks and pre-computed Bedrock Titan FAISS index directly to AWS S3.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import boto3  # noqa: E402
from src.chain import RAGChain  # noqa: E402
from src.config import settings  # noqa: E402
from src.embeddings import BedrockTitanEmbeddingProvider  # noqa: E402
from src.vector_store import FAISSVectorStore  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Upload runbooks and vector index to AWS S3")
    parser.add_argument("--bucket", type=str, default=settings.S3_BUCKET_NAME, help="Target S3 Bucket")
    parser.add_argument("--region", type=str, default=settings.AWS_REGION, help="AWS Region")
    parser.add_argument("--data-dir", type=Path, default=settings.DATA_DIR, help="Runbooks data directory")
    return parser.parse_args()


def main():
    args = parse_args()
    print(f"🚀 Initializing Bedrock Titan v2 Indexer in {args.region}...")
    s3 = boto3.client("s3", region_name=args.region)

    # Use live Bedrock Titan v2 embeddings
    embedding_provider = BedrockTitanEmbeddingProvider(region_name=args.region)
    vector_store = FAISSVectorStore(dimension=1024)

    chain = RAGChain(embedding_provider=embedding_provider, vector_store=vector_store)

    print(f"📖 Ingesting runbooks from {args.data_dir}...")
    total_chunks = chain.ingest_directory(args.data_dir)
    print(f"✅ Generated and embedded {total_chunks} chunks.")

    # Save to local cache
    cache_dir = ROOT_DIR / "index_cache"
    chain.vector_store.save_local(cache_dir, embedding_model_id=settings.BEDROCK_EMBEDDING_MODEL_ID)
    print(f"💾 Persisted index locally to {cache_dir}.")

    # Upload to S3
    print(f"☁️ Uploading FAISS index artifacts to s3://{args.bucket}/faiss_index/ ...")
    chain.vector_store.save_to_s3(
        s3_client=s3,
        bucket=args.bucket,
        prefix="faiss_index",
        embedding_model_id=settings.BEDROCK_EMBEDDING_MODEL_ID,
    )
    print("🎉 Successfully uploaded index to S3!")


if __name__ == "__main__":
    main()
