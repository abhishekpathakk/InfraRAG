#!/usr/bin/env python3
"""
Uploads runbooks and pre-computed Bedrock Titan FAISS index directly to AWS S3.
"""

import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import boto3  # noqa: E402
from src.chain import RAGChain  # noqa: E402
from src.embeddings import BedrockTitanEmbeddingProvider  # noqa: E402
from src.vector_store import FAISSVectorStore  # noqa: E402

S3_BUCKET = "infrarag-storage-ap0wa5"
REGION = "ap-south-1"


def main():
    print(f"🚀 Initializing Bedrock Titan v2 Indexer in {REGION}...")
    s3 = boto3.client("s3", region_name=REGION)

    # Use live Bedrock Titan v2 embeddings
    embedding_provider = BedrockTitanEmbeddingProvider(region_name=REGION)
    vector_store = FAISSVectorStore(dimension=1024)

    chain = RAGChain(embedding_provider=embedding_provider, vector_store=vector_store)

    data_dir = ROOT_DIR / "data" / "runbooks"
    print(f"📖 Ingesting runbooks from {data_dir}...")
    total_chunks = chain.ingest_directory(data_dir)
    print(f"✅ Generated and embedded {total_chunks} chunks.")

    # Save to local cache
    cache_dir = ROOT_DIR / "index_cache"
    chain.vector_store.save_local(cache_dir)
    print(f"💾 Persisted index locally to {cache_dir}.")

    # Upload to S3
    print(f"☁️ Uploading FAISS index artifacts to s3://{S3_BUCKET}/faiss_index/ ...")
    chain.vector_store.save_to_s3(s3_client=s3, bucket=S3_BUCKET, prefix="faiss_index")
    print("🎉 Successfully uploaded index to S3!")


if __name__ == "__main__":
    main()
