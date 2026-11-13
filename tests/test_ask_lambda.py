"""Unit tests for AWS Lambda /ask handler (local loading, S3 download, and auth)."""

import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from src.lambda_handlers import ask
from src.models import DocumentChunk
from src.embeddings import MockEmbeddingProvider
from src.vector_store import FAISSVectorStore


def test_ask_handler_warm_cache_local():
    """Tests handler execution with a pre-populated local index cache."""
    provider = MockEmbeddingProvider()
    store = FAISSVectorStore()
    chunk = DocumentChunk(
        chunk_id="k8s-c1",
        source_file="kubernetes_oom_killed.md",
        section_title="Exit Code 137",
        content="Container terminated with Exit Code 137 when pod exceeds memory limits",
    )
    store.add_documents([chunk], provider.embed_batch([chunk.content]))

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        store.save_local(tmp_path, embedding_model_id="mock")

        # Point ask handler to this tmp cache with mock provider environment
        with patch.dict("os.environ", {"EMBEDDING_PROVIDER": "mock", "EMBEDDING_DIMENSION": "1024", "USE_MOCK_BEDROCK": "true"}):
            with patch.object(ask, "Path", return_value=tmp_path):
                # Reset global cache
                ask._CACHED_CHAIN = None

                event = {
                    "rawPath": "/ask",
                    "body": json.dumps({"question": "What does Exit Code 137 mean?"}),
                }
                res = ask.handler(event, None)
                assert res["statusCode"] == 200
                body = json.loads(res["body"])
                assert "Exit Code 137" in body["answer"] or "memory limits" in body["answer"]
                assert len(body["citations"]) > 0
                assert body["metrics"]["retrieval_latency_ms"] >= 0.0
                assert body["metrics"]["retrieval_latency_ms"] < 2500.0  # Production latency SLA ceiling


def test_ask_handler_local_neural_parity():
    """Tests handler execution with the benchmarked Local FastEmbed neural pipeline."""
    # Reset global cache
    ask._CACHED_CHAIN = None
    with patch.dict(
        "os.environ",
        {
            "EMBEDDING_PROVIDER": "local",
            "EMBEDDING_DIMENSION": "384",
            "USE_MOCK_BEDROCK": "true",
            "INDEX_CACHE_PATH": "index_cache/local_bge_small",
        },
    ):
        event = {
            "rawPath": "/ask",
            "body": json.dumps({"question": "What causes container Exit Code 137 and OOMKilled termination?"}),
        }
        res = ask.handler(event, None)
        assert res["statusCode"] == 200
        body = json.loads(res["body"])
        assert "Exit Code 137" in body["answer"] or "OOMKilled" in body["answer"]
        assert len(body["citations"]) >= 1
        assert any(c["source_file"] in ("kubernetes_crashloopbackoff.md", "kubernetes_oom_killed.md") for c in body["citations"])
        assert body["metrics"]["retrieval_latency_ms"] < 2500.0


def test_ask_handler_auth_and_validation():
    """Tests API key authentication and input validation in ask handler."""
    with patch.dict("os.environ", {"INFRARAG_API_KEY": "secret-123"}):
        # 1. Missing header -> 401
        res = ask.handler({"body": json.dumps({"question": "test"})}, None)
        assert res["statusCode"] == 401

        # 2. Invalid header -> 401
        res = ask.handler({
            "headers": {"x-api-key": "wrong-key"},
            "body": json.dumps({"question": "test"}),
        }, None)
        assert res["statusCode"] == 401

        # 3. Valid key but missing question -> 400
        res = ask.handler({
            "headers": {"x-api-key": "secret-123"},
            "body": json.dumps({"question": ""}),
        }, None)
        assert res["statusCode"] == 400

        # 4. Question too long -> 400
        res = ask.handler({
            "headers": {"x-api-key": "secret-123"},
            "body": json.dumps({"question": "a" * 1005}),
        }, None)
        assert res["statusCode"] == 400


def test_ask_handler_empty_index_503():
    """Tests that handler returns 503 when vector index is empty."""
    from unittest.mock import MagicMock
    mock_chain = MagicMock()
    mock_chain.vector_store.chunks = []

    with patch.object(ask, "get_cached_chain", return_value=mock_chain):
        res = ask.handler({"body": json.dumps({"question": "Any question?"})}, None)
        assert res["statusCode"] == 503
        body = json.loads(res["body"])
        assert "Service Unavailable" in body["error"]


def test_ask_handler_fail_closed_auth():
    """Tests that REQUIRE_API_KEY=true fails closed when no key is configured."""
    with patch.dict("os.environ", {"REQUIRE_API_KEY": "true"}, clear=False):
        # Even with no INFRARAG_API_KEY set, it must reject requests (fail-closed)
        res = ask.handler({"body": json.dumps({"question": "test"})}, None)
        assert res["statusCode"] == 401


def test_ask_handler_health_check():
    """Tests that /health route returns provider, model SHA-256, dimension, and threshold."""
    ask._CACHED_CHAIN = None
    with patch.dict(
        "os.environ",
        {
            "EMBEDDING_PROVIDER": "local",
            "EMBEDDING_DIMENSION": "384",
            "USE_MOCK_BEDROCK": "true",
            "REQUIRE_API_KEY": "true",  # Health route must remain accessible even when auth is strictly required
            "INDEX_CACHE_PATH": "index_cache/local_bge_small",
        },
    ):
        # 1. Direct path /health
        res = ask.handler({"rawPath": "/health"}, None)
        assert res["statusCode"] == 200
        body = json.loads(res["body"])
        assert body["status"] == "healthy"
        assert body["provider"] == "LocalFastEmbedProvider"
        assert body["model_sha256"] == "51f1bd0addd6e859e42c2c8021a5e5461385bb676a649f4b269aa445449f2431"
        assert body["dimension"] == 384
        assert body["threshold"] == 0.25
        assert body["chunks_count"] == 7207

        # 2. RouteKey GET /health
        res2 = ask.handler({"routeKey": "GET /health"}, None)
        assert res2["statusCode"] == 200
        body2 = json.loads(res2["body"])
        assert body2["status"] == "healthy"


