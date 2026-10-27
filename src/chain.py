"""
RAG Orchestration Chain for InfraRAG.

Coordinates the complete lifecycle:
- Ingestion: Documents -> Chunker -> Embeddings -> FAISS Vector Store -> S3/Disk
- Query: User Question -> Embedding -> Vector Search -> Grounded LLM Prompt -> Answer + Citations
- Observability: Latency, token metrics, and cost calculation
"""

import logging
import time
from pathlib import Path

from src.chunker import MarkdownChunker
from src.config import settings
from src.embeddings import BaseEmbeddingProvider, get_embedding_provider
from src.generator import BaseLLMProvider, get_llm_provider
from src.models import DocumentChunk, RAGResponse
from src.retriever import Retriever
from src.vector_store import BaseVectorStore, FAISSVectorStore

logger = logging.getLogger(__name__)


class RAGChain:
    """End-to-end RAG orchestrator."""

    def __init__(
        self,
        embedding_provider: BaseEmbeddingProvider | None = None,
        vector_store: BaseVectorStore | None = None,
        llm_provider: BaseLLMProvider | None = None,
        chunk_size: int = settings.CHUNK_SIZE,
        chunk_overlap: int = settings.CHUNK_OVERLAP,
        top_k: int = settings.TOP_K,
    ):
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.vector_store = vector_store or FAISSVectorStore(dimension=self.embedding_provider.dimension)
        self.llm_provider = llm_provider or get_llm_provider()
        self.chunker = MarkdownChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.retriever = Retriever(
            vector_store=self.vector_store,
            embedding_provider=self.embedding_provider,
            top_k=top_k,
        )

    def ingest_directory(self, runbook_dir: Path | str) -> int:
        """
        Reads all Markdown files in directory, chunks them, embeds them,
        and indexes them into the vector store.
        Returns total number of chunks indexed.
        """
        start = time.perf_counter()
        dir_path = Path(runbook_dir)
        md_files = list(dir_path.glob("*.md"))
        if not md_files:
            logger.warning(f"No .md files found in {dir_path}")
            return 0

        all_chunks: list[DocumentChunk] = []
        for file_path in md_files:
            chunks = self.chunker.chunk_markdown_file(file_path)
            all_chunks.extend(chunks)

        logger.info(f"Generated {len(all_chunks)} chunks from {len(md_files)} runbooks.")

        # Batch embed chunks
        contents = [c.content for c in all_chunks]
        embeddings = self.embedding_provider.embed_batch(contents)

        # Store in vector store
        self.vector_store.add_documents(all_chunks, embeddings)
        elapsed = (time.perf_counter() - start) * 1000.0
        logger.info(f"Indexed {len(all_chunks)} chunks in {elapsed:.2f}ms.")

        return len(all_chunks)

    def answer_question(self, query: str) -> RAGResponse:
        """
        Executes end-to-end query answering with grounded citations and observability metrics.
        """
        total_start = time.perf_counter()

        # 1. Retrieve relevant chunks
        matched_chunks, retrieval_latency_ms = self.retriever.retrieve(query)

        # 2. Determine confidence
        confidence = "high"
        if not matched_chunks or matched_chunks[0][1] < 0.25:
            confidence = "low"

        # 3. Generate grounded answer
        answer_text, citations, in_tokens, out_tokens, gen_latency_ms = self.llm_provider.generate(
            query=query, chunks=matched_chunks
        )

        total_latency_ms = (time.perf_counter() - total_start) * 1000.0

        # 4. Calculate cost
        estimated_cost = 0.0
        if not settings.USE_MOCK_BEDROCK:
            # Bedrock Pricing (ap-south-1):
            # Titan Text Embeddings v2: $0.0001 / 1k tokens
            # Nova Micro: $0.000035 / 1k input tokens, $0.00014 / 1k output tokens
            query_tokens = len(query.split()) * 1.3
            embed_cost = (query_tokens / 1000.0) * 0.0001
            gen_cost = ((in_tokens / 1000.0) * 0.000035) + ((out_tokens / 1000.0) * 0.00014)
            estimated_cost = embed_cost + gen_cost

        return RAGResponse(
            query=query,
            answer=answer_text,
            citations=citations,
            confidence=confidence,
            retrieved_chunks=[c for c, _ in matched_chunks],
            latency_ms=round(total_latency_ms, 2),
            retrieval_latency_ms=round(retrieval_latency_ms, 2),
            generation_latency_ms=round(gen_latency_ms, 2),
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            estimated_cost_usd=round(estimated_cost, 6),
        )
