"""
Retriever Module for InfraRAG.

Performs semantic search over indexed runbooks using query embeddings and top-k retrieval.
"""

import logging
import time
from src.embeddings import BaseEmbeddingProvider
from src.models import DocumentChunk
from src.vector_store import BaseVectorStore

logger = logging.getLogger(__name__)


class Retriever:
    """
    Coordinates query embedding and vector store similarity search.
    Provides confidence estimation based on cosine similarity thresholds.
    """

    def __init__(
        self,
        vector_store: BaseVectorStore,
        embedding_provider: BaseEmbeddingProvider,
        top_k: int = 3,
        min_relevance_threshold: float = 0.20,
    ):
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.top_k = top_k
        self.min_relevance_threshold = min_relevance_threshold

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        type_filter: str | None = None,
    ) -> tuple[list[tuple[DocumentChunk, float]], float]:
        """
        Retrieves top-k relevant chunks for a user query, optionally filtered by type.

        Returns:
            (results, latency_ms) where results is a list of (DocumentChunk, score)
        """
        start_time = time.perf_counter()
        k = top_k or self.top_k

        # 1. Embed query
        query_vector = self.embedding_provider.embed_text(query)

        # 2. Similarity search in vector store with type filter
        matches = self.vector_store.similarity_search(
            query_embedding=query_vector,
            top_k=k,
            type_filter=type_filter,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        logger.info(f"Retrieved {len(matches)} chunks in {latency_ms:.2f}ms for query: '{query}' (filter: {type_filter})")

        return matches, latency_ms
