"""
AWS Lambda Handler: /ask
Receives questions via API Gateway HTTP API POST /ask,
performs similarity search against cached FAISS index, and generates answers.
"""

import hmac
import json
import logging
import os
from pathlib import Path
from typing import Any
import uuid

from src.chain import RAGChain
from src.config import settings

logger = logging.getLogger()
logger.setLevel(logging.INFO)

MAX_QUESTION_LENGTH = 1000
ALLOWED_TYPES = {"internal", "public"}

# Global warm cache for FAISS index across Lambda invocations
_CACHED_CHAIN: RAGChain | None = None


def get_cached_chain() -> RAGChain:
    global _CACHED_CHAIN
    if _CACHED_CHAIN is not None and _CACHED_CHAIN.vector_store.chunks:
        return _CACHED_CHAIN

    chain = RAGChain()
    tmp_path = Path("/tmp/faiss_index")
    bucket_name = os.environ.get("S3_BUCKET_NAME", settings.S3_BUCKET_NAME)

    expected_model = settings.BEDROCK_EMBEDDING_MODEL_ID if not settings.USE_MOCK_BEDROCK else "mock"

    # If warm cache in /tmp exists, load it
    if (tmp_path / "chunks.json").exists():
        chain.vector_store.load_local(tmp_path, expected_model_id=expected_model)
    elif not settings.USE_MOCK_BEDROCK and bucket_name:
        # Download from S3 into /tmp
        import boto3
        s3 = boto3.client("s3", region_name=settings.AWS_REGION)
        chain.vector_store.load_from_s3(
            s3_client=s3,
            bucket=bucket_name,
            prefix="faiss_index",
            expected_model_id=expected_model,
        )
    else:
        # Ingest local runbooks on cold start
        chain.ingest_directory(settings.DATA_DIR)
        chain.vector_store.save_local(tmp_path, embedding_model_id=expected_model)

    _CACHED_CHAIN = chain
    return _CACHED_CHAIN


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    logger.info(f"Received query event: {event.get('rawPath', '')}")

    try:
        # 1. API Key Authentication (fail-closed if expected key is configured)
        expected_key = os.environ.get("INFRARAG_API_KEY")
        if expected_key:
            headers = event.get("headers") or {}
            client_key = headers.get("x-api-key") or headers.get("X-API-KEY") or ""
            if not hmac.compare_digest(client_key, expected_key):
                return {
                    "statusCode": 401,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({"error": "Unauthorized: Missing or invalid 'x-api-key' header."}),
                }

        body = event.get("body", "{}")
        if isinstance(body, str):
            body_json = json.loads(body) if body else {}
        else:
            body_json = body

        question = body_json.get("question") or body_json.get("query")
        if not question or not str(question).strip():
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing 'question' in request body."}),
            }

        question_str = str(question).strip()
        if len(question_str) > MAX_QUESTION_LENGTH:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": f"Question exceeds maximum length of {MAX_QUESTION_LENGTH} characters."
                }),
            }

        type_filter = body_json.get("type_filter") or body_json.get("type")
        if type_filter and str(type_filter).lower() in ("all", "*", ""):
            type_filter = None
        elif type_filter:
            type_filter = str(type_filter).lower().strip()
            if type_filter not in ALLOWED_TYPES:
                return {
                    "statusCode": 400,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "error": f"Invalid 'type_filter'. Allowed values: {sorted(list(ALLOWED_TYPES))}, or omit for all."
                    }),
                }

        chain = get_cached_chain()
        response = chain.answer_question(question_str, type_filter=type_filter)

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
        request_id = str(uuid.uuid4())[:8]
        logger.error(f"Ask handler failed [request_id={request_id}]: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "Internal server error during question processing.",
                "request_id": request_id,
            }),
        }

