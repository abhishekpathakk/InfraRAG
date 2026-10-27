"""
AWS Lambda Handler: /ask
Receives questions via API Gateway HTTP API POST /ask,
performs similarity search against cached FAISS index, and generates answers.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

from src.chain import RAGChain
from src.config import settings

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global warm cache for FAISS index across Lambda invocations
_CACHED_CHAIN: RAGChain | None = None


def get_cached_chain() -> RAGChain:
    global _CACHED_CHAIN
    if _CACHED_CHAIN is not None and _CACHED_CHAIN.vector_store.chunks:
        return _CACHED_CHAIN

    chain = RAGChain()
    tmp_path = Path("/tmp/faiss_index")
    bucket_name = os.environ.get("S3_BUCKET_NAME", settings.S3_BUCKET_NAME)

    # If warm cache in /tmp exists, load it
    if (tmp_path / "chunks.json").exists():
        chain.vector_store.load_local(tmp_path)
    elif not settings.USE_MOCK_BEDROCK and bucket_name:
        # Download from S3 into /tmp
        import boto3
        s3 = boto3.client("s3", region_name=settings.AWS_REGION)
        chain.vector_store.load_from_s3(s3_client=s3, bucket=bucket_name, prefix="faiss_index")
    else:
        # Ingest local runbooks on cold start
        chain.ingest_directory(settings.DATA_DIR)
        chain.vector_store.save_local(tmp_path)

    _CACHED_CHAIN = chain
    return _CACHED_CHAIN


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    logger.info(f"Received query event: {event.get('rawPath', '')}")

    try:
        body = event.get("body", "{}")
        if isinstance(body, str):
            body_json = json.loads(body) if body else {}
        else:
            body_json = body

        question = body_json.get("question") or body_json.get("query")
        type_filter = body_json.get("type_filter") or body_json.get("type")
        if type_filter and type_filter.lower() in ("all", "*", ""):
            type_filter = None
        elif type_filter:
            type_filter = type_filter.lower()

        if not question or not question.strip():
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing 'question' in request body."}),
            }

        chain = get_cached_chain()
        response = chain.answer_question(question.strip(), type_filter=type_filter)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "query": response.query,
                "answer": response.answer,
                "confidence": response.confidence,
                "citations": [c.model_dump() for c in response.citations],
                "metrics": {
                    "latency_ms": response.latency_ms,
                    "retrieval_latency_ms": response.retrieval_latency_ms,
                    "generation_latency_ms": response.generation_latency_ms,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "estimated_cost_usd": response.estimated_cost_usd,
                },
            }),
        }

    except Exception as e:
        logger.error(f"Ask handler failed: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }
