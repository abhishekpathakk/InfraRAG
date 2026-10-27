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
        store.save_local(tmpdir)
        assert (Path(tmpdir) / "chunks.json").exists()

        new_store = FAISSVectorStore(dimension=1024)
        new_store.load_local(tmpdir)
        assert len(new_store.chunks) == 1
        assert new_store.chunks[0].chunk_id == "c-save-1"
