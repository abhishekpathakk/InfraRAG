"""
Unit tests for the default Sovereign Local Neural Pipeline (BAAI/bge-small-en-v1.5).

Verifies that when InfraRAG is executed with zero environment variables:
1. get_embedding_provider() returns LocalFastEmbedProvider (384 dimensions).
2. End-to-end RAGChain retrieval, indexing, BM25 dense gating, and citation grounding
   function out-of-the-box without requiring AWS credentials or mock overrides.
"""

import pytest

from src.chain import RAGChain
from src.embeddings import LocalFastEmbedProvider, get_embedding_provider
from src.generator import MockLLMProvider
from src.models import DocumentChunk
from src.vector_store import FAISSVectorStore


def test_default_embedding_provider_is_local():
    """Verifies that calling get_embedding_provider() with no env vars defaults to local BGE-small with verified ONNX checksum."""
    provider = get_embedding_provider()
    assert isinstance(provider, LocalFastEmbedProvider), f"Expected LocalFastEmbedProvider, got {type(provider)}"
    assert provider.dimension == 384, f"Expected 384 dimensions for bge-small, got {provider.dimension}"
    assert provider.onnx_sha256 == "51f1bd0addd6e859e42c2c8021a5e5461385bb676a649f4b269aa445449f2431", f"Unexpected sha256: {provider.onnx_sha256}"


def test_integrity_check_fails_closed_when_model_dir_unresolvable(monkeypatch):
    """Verifies fail-closed behavior: raises RuntimeError if _model_dir cannot be introspected."""
    from fastembed import TextEmbedding
    original_init = TextEmbedding.__init__

    def dummy_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        # Simulate private attribute rename or missing _model_dir
        if hasattr(self.model, "_model_dir"):
            delattr(self.model, "_model_dir")

    monkeypatch.setattr(TextEmbedding, "__init__", dummy_init)
    with pytest.raises(RuntimeError, match="model directory attribute '_model_dir' could not be resolved"):
        LocalFastEmbedProvider()


def test_integrity_check_fails_closed_when_onnx_missing(monkeypatch, tmp_path):
    """Verifies fail-closed behavior: raises RuntimeError if the resolved model dir contains no ONNX binary."""
    from fastembed import TextEmbedding
    original_init = TextEmbedding.__init__

    empty_dir = tmp_path / "empty_model_dir"
    empty_dir.mkdir()

    def dummy_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.model._model_dir = str(empty_dir)

    monkeypatch.setattr(TextEmbedding, "__init__", dummy_init)
    with pytest.raises(RuntimeError, match="no ONNX binary found"):
        LocalFastEmbedProvider()


def test_integrity_check_fails_closed_on_hash_mismatch():
    """Verifies fail-closed behavior: raises RuntimeError when binary checksum does not match expected_sha256."""
    mismatched_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    with pytest.raises(RuntimeError, match="FastEmbed ONNX integrity violation"):
        LocalFastEmbedProvider(expected_sha256=mismatched_hash)


def test_local_neural_pipeline_end_to_end_smoke():
    """
    Smoke test: executes indexing, dense retrieval, and grounded Q&A
    using real BAAI/bge-small-en-v1.5 neural embeddings with default settings.
    """
    provider = get_embedding_provider()
    store = FAISSVectorStore(dimension=provider.dimension)
    llm = MockLLMProvider()

    chain = RAGChain(
        embedding_provider=provider,
        vector_store=store,
        llm_provider=llm,
        min_relevance_threshold=0.80,
    )

    # Ingest technical runbook chunk
    chunk = DocumentChunk(
        chunk_id="smoke-k8s-oom",
        source_file="kubernetes_oom_killed.md",
        section_title="Exit Code 137 Resolution",
        content="Container terminated with Exit Code 137 due to OOMKilled cgroup limits. Increase container memory requests and limits.",
    )
    embeddings = provider.embed_batch([chunk.content])
    store.add_documents([chunk], embeddings)

    # 1. In-domain technical query (passes documented 0.80 threshold)
    response = chain.answer_question("What causes container Exit Code 137 and OOMKilled termination?", hybrid=True)
    assert "Exit Code 137" in response.answer or "OOMKilled" in response.answer
    assert len(response.citations) > 0
    assert response.citations[0].source_file == "kubernetes_oom_killed.md"
    assert response.confidence in ("high", "medium")

    # 2. Out-of-domain negative refusal query
    negative_response = chain.answer_question("What is the recipe for baking a chocolate cake?", hybrid=True)
    assert "I don't know based on the provided runbooks." in negative_response.answer
    assert len(negative_response.citations) == 0

    # 3. Near-domain negative refusal query (gated out by 0.80 threshold)
    near_domain_response = chain.answer_question("How to configure route table blackholes in AWS Transit Gateway peering attachments?", hybrid=True)
    assert "I don't know based on the provided runbooks." in near_domain_response.answer
    assert len(near_domain_response.citations) == 0

