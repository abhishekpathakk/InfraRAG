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

        # Point ask handler to this tmp cache
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
            assert body["metrics"]["retrieval_latency_ms"] < 20.0


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
