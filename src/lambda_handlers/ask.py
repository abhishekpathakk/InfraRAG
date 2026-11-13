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


def get_expected_model_id() -> str:
    """Returns expected model ID for vector index verification based on active provider."""
    provider_type = os.getenv("EMBEDDING_PROVIDER", getattr(settings, "EMBEDDING_PROVIDER", "local")).lower()
    if provider_type in ("local", "fastembed"):
        return os.getenv(
            "EXPECTED_EMBEDDING_MODEL_ID",
            "fastembed:BAAI/bge-small-en-v1.5@5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
        )
    if provider_type == "mock" or os.getenv("USE_MOCK_BEDROCK", "").lower() in ("true", "1", "yes"):
        return os.getenv("EXPECTED_EMBEDDING_MODEL_ID", "mock")
    return os.getenv(
        "EXPECTED_EMBEDDING_MODEL_ID",
        getattr(settings, "BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"),
    )


def get_cached_chain() -> RAGChain:
    global _CACHED_CHAIN
    if _CACHED_CHAIN is not None and _CACHED_CHAIN.vector_store.chunks:
        return _CACHED_CHAIN

    chain = RAGChain()
    expected_model = get_expected_model_id()
    bucket_name = os.environ.get("S3_BUCKET_NAME", settings.S3_BUCKET_NAME)

    # 1. Resolve candidate directories in priority order:
    # Environment override -> Bundled container path -> Local workspace path -> /tmp scratch
    candidate_dirs: list[Path] = []
    if os.environ.get("INDEX_CACHE_PATH"):
        candidate_dirs.append(Path(os.environ["INDEX_CACHE_PATH"]))

    candidate_dirs.append(Path("/var/task/index_cache/local_bge_small"))
    candidate_dirs.append(Path("/var/task/index_cache"))

    if hasattr(settings, "CACHE_DIR") and settings.CACHE_DIR:
        candidate_dirs.append(settings.CACHE_DIR / "local_bge_small")
        candidate_dirs.append(settings.CACHE_DIR)

    tmp_path = Path("/tmp/faiss_index")  # nosec B108
    candidate_dirs.append(tmp_path)

    loaded = False
    for c_dir in candidate_dirs:
        if (c_dir / "chunks.json").exists():
            try:
                chain.vector_store.load_local(c_dir, expected_model_id=expected_model)
                logger.info(f"Loaded vector store from {c_dir} with {len(chain.vector_store.chunks)} chunks.")
                loaded = True
                break
            except Exception as e:
                logger.warning(f"Could not load index from candidate {c_dir}: {e}")

    # 2. Fall back to S3 download if local candidate directories not found
    if not loaded and not settings.USE_MOCK_BEDROCK and bucket_name:
        try:
            import boto3
            s3 = boto3.client("s3", region_name=settings.AWS_REGION)
            chain.vector_store.load_from_s3(
                s3_client=s3,
                bucket=bucket_name,
                prefix="faiss_index",
                expected_model_id=expected_model,
                target_dir=tmp_path,
            )
            loaded = True
        except Exception as e:
            logger.error(f"Failed to load vector store from S3: {e}")

    # 3. Fail fast if no index could be loaded from pre-baked container paths, /tmp, or S3
    if not loaded:
        logger.warning(
            "Vector index not found in pre-baked candidate paths, /tmp scratch, or S3. "
            "Returning unpopulated chain (handler will fail fast with 503)."
        )
        return chain

    _CACHED_CHAIN = chain
    return _CACHED_CHAIN


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    raw_path = event.get("rawPath") or event.get("path") or ""
    route_key = event.get("routeKey") or ""
    logger.info(f"Received query event: rawPath={raw_path}, routeKey={route_key}")

    # Health check probe (exempt from API key auth for ALB/monitoring probes)
    if raw_path == "/health" or route_key == "GET /health" or event.get("action") == "health" or event.get("health") is True:
        try:
            chain = get_cached_chain()
            emb = chain.embedding_provider
            provider_name = type(emb).__name__
            model_sha256 = getattr(emb, "onnx_sha256", "N/A")
            dimension = emb.dimension
            threshold = getattr(chain, "min_relevance_threshold", getattr(settings, "MIN_RELEVANCE_THRESHOLD", 0.0))
            chunks_count = len(chain.vector_store.chunks) if chain.vector_store and chain.vector_store.chunks else 0

            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "status": "healthy" if chunks_count > 0 else "degraded",
                    "provider": provider_name,
                    "model_sha256": model_sha256,
                    "dimension": dimension,
                    "threshold": threshold,
                    "chunks_count": chunks_count,
                }),
            }
        except Exception as e:
            logger.error(f"Health check probe failed: {e}", exc_info=True)
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"status": "unhealthy", "error": str(e)}),
            }

    try:
        # 1. API Key Authentication (fail-closed if expected key or REQUIRE_API_KEY is configured)
        expected_key = os.environ.get("INFRARAG_API_KEY")
        require_auth = os.environ.get("REQUIRE_API_KEY", "false").lower() == "true" or bool(expected_key)
        if require_auth:
            headers = event.get("headers") or {}
            client_key = headers.get("x-api-key") or headers.get("X-API-KEY") or ""
            if not expected_key or not hmac.compare_digest(client_key, expected_key):
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
        if not chain.vector_store.chunks:
            return {
                "statusCode": 503,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Service Unavailable: Vector index not loaded or empty."}),
            }
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

