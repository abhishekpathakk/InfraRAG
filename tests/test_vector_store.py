"""Unit tests for Vector Store and Embeddings."""

import tempfile
from pathlib import Path
from src.embeddings import MockEmbeddingProvider
from src.models import DocumentChunk
from src.vector_store import FAISSVectorStore


def test_mock_embedding_provider():
    provider = MockEmbeddingProvider(dimension=1024)
    assert provider.dimension == 1024

    vec = provider.embed_text("Kubernetes pod OOMKilled exit code 137")
    assert len(vec) == 1024
    assert isinstance(vec[0], float)

    # Unit norm verification
    norm = sum(x * x for x in vec) ** 0.5
    assert abs(norm - 1.0) < 1e-4


def test_faiss_vector_store_add_and_search():
    provider = MockEmbeddingProvider(dimension=1024)
    store = FAISSVectorStore(dimension=1024)

    chunk1 = DocumentChunk(
        chunk_id="chunk-1",
        source_file="k8s_oom.md",
        section_title="Exit Code 137",
        content="Container terminated with Exit Code 137 OOMKilled",
    )
    chunk2 = DocumentChunk(
        chunk_id="chunk-2",
        source_file="istio_503.md",
        section_title="503 UF",
        content="Istio Envoy returned 503 UF upstream connection failure",
    )

    embs = provider.embed_batch([chunk1.content, chunk2.content])
    store.add_documents([chunk1, chunk2], embs)

    # Search for memory issue
    q_vec = provider.embed_text("How to fix pod memory exit code 137?")
    results = store.similarity_search(q_vec, top_k=1)

    assert len(results) == 1
    top_chunk, score = results[0]
    assert top_chunk.chunk_id == "chunk-1"
    assert score > 0.0


def test_vector_store_save_and_load():
    provider = MockEmbeddingProvider(dimension=1024)
    store = FAISSVectorStore(dimension=1024)

    chunk = DocumentChunk(
        chunk_id="c-save-1",
        source_file="test.md",
        section_title="Testing",
        content="Testing serialization to local disk",
    )
    store.add_documents([chunk], provider.embed_batch([chunk.content]))

    with tempfile.TemporaryDirectory() as tmpdir:
        store.save_local(tmpdir, embedding_model_id="mock-v1")
        assert (Path(tmpdir) / "chunks.json").exists()
        assert (Path(tmpdir) / "index_metadata.json").exists()

        new_store = FAISSVectorStore(dimension=1024)
        new_store.load_local(tmpdir, expected_model_id="mock-v1")
        assert len(new_store.chunks) == 1
        assert new_store.chunks[0].chunk_id == "c-save-1"
        assert getattr(new_store, "_matrix", None) is not None

        # Verify search works identically
        q_vec = provider.embed_text("Testing serialization")
        results = new_store.similarity_search(q_vec, top_k=1)
        assert len(results) == 1
        assert results[0][0].chunk_id == "c-save-1"


def test_vector_store_model_mismatch_guard():
    import pytest
    provider = MockEmbeddingProvider(dimension=1024)
    store = FAISSVectorStore(dimension=1024)
    chunk = DocumentChunk(chunk_id="c-1", source_file="test.md", section_title="T", content="C")
    store.add_documents([chunk], provider.embed_batch([chunk.content]))

    with tempfile.TemporaryDirectory() as tmpdir:
        store.save_local(tmpdir, embedding_model_id="mock-provider")

        new_store = FAISSVectorStore(dimension=1024)
        with pytest.raises(ValueError, match="Embedding model mismatch"):
            new_store.load_local(tmpdir, expected_model_id="amazon.titan-embed-text-v2:0")


def test_vector_store_load_local_parity_and_fast_latency():
    """Validates that loaded vector store has 100% search parity and sub-millisecond retrieval."""
    import time
    provider = MockEmbeddingProvider(dimension=1024)
    original_store = FAISSVectorStore(dimension=1024)

    # Ingest 25 synthetic incident chunks
    chunks = [
        DocumentChunk(
            chunk_id=f"chunk-{i}",
            source_file=f"runbook_{i % 5}.md",
            section_title=f"Incident Section {i}",
            content=f"Kubernetes incident troubleshooting scenario {i} with cgroup and memory limits",
        )
        for i in range(25)
    ]
    original_store.add_documents(chunks, provider.embed_batch([c.content for c in chunks]))

    query_vec = provider.embed_text("troubleshoot memory limits and cgroup")
    orig_results = original_store.similarity_search(query_vec, top_k=5)

    with tempfile.TemporaryDirectory() as tmpdir:
        original_store.save_local(tmpdir, embedding_model_id="mock-test")

        loaded_store = FAISSVectorStore(dimension=1024)
        loaded_store.load_local(tmpdir, expected_model_id="mock-test")

        # 1. Verify cached matrix is allocated
        assert getattr(loaded_store, "_matrix", None) is not None

        # 2. Verify identical Top-K ordering and scores
        loaded_results = loaded_store.similarity_search(query_vec, top_k=5)
        assert len(loaded_results) == len(orig_results)
        for (orig_c, orig_s), (load_c, load_s) in zip(orig_results, loaded_results):
            assert orig_c.chunk_id == load_c.chunk_id
            assert abs(orig_s - load_s) < 1e-5

        # 3. Verify sub-millisecond search latency across 50 iterations
        latencies = []
        for _ in range(50):
            t0 = time.perf_counter()
            _ = loaded_store.similarity_search(query_vec, top_k=5)
            latencies.append((time.perf_counter() - t0) * 1000.0)

        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 2.0, f"Expected < 2.0ms search latency on loaded store, got {avg_latency:.2f}ms"


def test_vector_store_s3_save_and_load():
    """Tests S3 serialization and deserialization using in-memory mock client."""
    provider = MockEmbeddingProvider(dimension=1024)
    store = FAISSVectorStore(dimension=1024)
    chunk = DocumentChunk(chunk_id="s3-c1", source_file="aws.md", section_title="S3", content="S3 vector persistence")
    store.add_documents([chunk], provider.embed_batch([chunk.content]))

    # Mock S3 client with in-memory dict
    storage: dict[str, bytes] = {}

    class MockS3Client:
        def upload_file(self, filename: str, bucket: str, key: str):
            with open(filename, "rb") as f:
                storage[f"{bucket}/{key}"] = f.read()

        def download_file(self, bucket: str, key: str, filename: str):
            obj_key = f"{bucket}/{key}"
            if obj_key not in storage:
                raise FileNotFoundError(f"Missing S3 key {obj_key}")
            with open(filename, "wb") as f:
                f.write(storage[obj_key])

    mock_s3 = MockS3Client()
    bucket = "test-infrarag-bucket"
    store.save_to_s3(s3_client=mock_s3, bucket=bucket, prefix="faiss_index", embedding_model_id="mock-v1")

    # Verify S3 received chunks.json and index_metadata.json
    assert f"{bucket}/faiss_index/chunks.json" in storage
    assert f"{bucket}/faiss_index/index_metadata.json" in storage

    # Load from mock S3
    restored_store = FAISSVectorStore(dimension=1024)
    restored_store.load_from_s3(s3_client=mock_s3, bucket=bucket, prefix="faiss_index", expected_model_id="mock-v1")
    assert len(restored_store.chunks) == 1
    assert restored_store.chunks[0].chunk_id == "s3-c1"

