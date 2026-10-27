"""
AWS Lambda Handler: /ingest
Triggered via API Gateway POST /ingest or S3 ObjectCreated events.
Chunks, embeds, builds FAISS index, and persists it to S3.
"""

import json
import logging
import os
import time
from typing import Any

from src.chain import RAGChain
from src.config import settings

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    start_time = time.perf_counter()
    logger.info("Starting InfraRAG Ingestion Handler...")

    try:
        # Determine source of runbooks (S3 or local data directory)
        bucket_name = os.environ.get("S3_BUCKET_NAME", settings.S3_BUCKET_NAME)
        chain = RAGChain()

        # In local/test mode, ingest from data directory; in cloud mode from S3
        total_chunks = chain.ingest_directory(settings.DATA_DIR)

        # Persist index to local /tmp or S3
        target_dir = "/tmp/faiss_index"
        chain.vector_store.save_local(target_dir)

        if not settings.USE_MOCK_BEDROCK and bucket_name:
            import boto3
            s3 = boto3.client("s3", region_name=settings.AWS_REGION)
            chain.vector_store.save_to_s3(s3_client=s3, bucket=bucket_name, prefix="faiss_index")

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "status": "success",
                "message": f"Successfully ingested {total_chunks} chunks into FAISS vector store.",
                "total_chunks": total_chunks,
                "latency_ms": round(elapsed_ms, 2),
            }),
        }

    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"status": "error", "message": str(e)}),
        }
