"""Unit tests for RAG Chain orchestrator, citations, and groundedness."""

from src.chain import RAGChain
from src.embeddings import MockEmbeddingProvider
from src.generator import MockLLMProvider
from src.models import DocumentChunk
from src.vector_store import FAISSVectorStore


def test_rag_chain_grounded_answer():
    provider = MockEmbeddingProvider()
    store = FAISSVectorStore()
    llm = MockLLMProvider()

    chain = RAGChain(embedding_provider=provider, vector_store=store, llm_provider=llm)

    # Ingest synthetic chunks
    chunk = DocumentChunk(
        chunk_id="oom-c0",
        source_file="kubernetes_oom_killed.md",
        section_title="Exit Code 137",
        content="Container terminated with Exit Code 137 due to OOMKilled cgroup limits",
    )
    store.add_documents([chunk], provider.embed_batch([chunk.content]))

    response = chain.answer_question("What causes Exit Code 137?")
    assert "Exit Code 137" in response.answer or "OOMKilled" in response.answer
    assert len(response.citations) > 0
    assert response.citations[0].source_file == "kubernetes_oom_killed.md"
    assert response.confidence == "high"


def test_rag_chain_ungrounded_fallback():
    provider = MockEmbeddingProvider()
    store = FAISSVectorStore()
    llm = MockLLMProvider()

    chain = RAGChain(embedding_provider=provider, vector_store=store, llm_provider=llm)

    # Test an out-of-domain question that is not in any runbook
    response = chain.answer_question("What is the recipe to bake a chocolate cake?")
    assert "I don't know based on the provided runbooks." in response.answer
