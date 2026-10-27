"""
Vector Store implementation for InfraRAG.

Provides:
- BaseVectorStore: Abstract interface (swappable for S3 Vectors, pgvector, or OpenSearch)
- FAISSVectorStore: High-performance IndexFlatIP with S3 and local serialization
- NumPyVectorStore: Pure-Python/NumPy fallback for environments without faiss-cpu binaries
"""

import json
import logging
import pickle
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from src.models import DocumentChunk

logger = logging.getLogger(__name__)


class BaseVectorStore(ABC):
    """Abstract Vector Store Interface."""

    @abstractmethod
    def add_documents(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        """Add document chunks and their corresponding embedding vectors."""
        pass

    @abstractmethod
    def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 3,
        type_filter: str | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """Search top-k most similar document chunks and return (chunk, score) pairs, optionally filtered by type."""
        pass

    @abstractmethod
    def save_local(self, directory: str | Path) -> None:
        """Persist index and metadata to local disk."""
        pass

    @abstractmethod
    def load_local(self, directory: str | Path) -> None:
        """Load index and metadata from local disk."""
        pass


class FAISSVectorStore(BaseVectorStore):
    """
    FAISS-backed vector store using IndexFlatIP (Inner Product).
    With L2-normalized embeddings, Inner Product is mathematically identical to Cosine Similarity.
    Includes pure Python / NumPy fallbacks.
    """

    def __init__(self, dimension: int = 1024):
        self.dimension = dimension
        self.chunks: list[DocumentChunk] = []
        self._index: Any = None
        self._has_faiss = False
        self._vectors: list[list[float]] = []

        try:
            import faiss
            self.faiss = faiss
            self._index = faiss.IndexFlatIP(dimension)
            self._has_faiss = True
        except ImportError:
            self._has_faiss = False

    def add_documents(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError(f"Mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings")

        if not chunks:
            return

        if self._has_faiss and HAS_NUMPY:
            mat = np.array(embeddings, dtype=np.float32)
            self._index.add(mat)
        else:
            self._vectors.extend(embeddings)

        self.chunks.extend(chunks)

    def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 3,
        type_filter: str | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        if not self.chunks:
            return []

        search_k = min(len(self.chunks), max(top_k * 6, len(self.chunks)) if type_filter else top_k)

        if self._has_faiss and HAS_NUMPY:
            q_vec = np.array([query_embedding], dtype=np.float32)
            distances, indices = self._index.search(q_vec, search_k)
            results = []
            for score, idx in zip(distances[0], indices[0]):
                if idx != -1 and idx < len(self.chunks):
                    chunk = self.chunks[idx]
                    if type_filter and getattr(chunk, "type", "internal") != type_filter:
                        continue
                    clean_score = max(0.0, min(1.0, float(score)))
                    results.append((chunk, clean_score))
                    if len(results) >= top_k:
                        break
            return results
        elif HAS_NUMPY and self._vectors:
            q_vec = np.array(query_embedding, dtype=np.float32)
            mat = np.array(self._vectors, dtype=np.float32)
            scores = np.dot(mat, q_vec)
            top_indices = np.argsort(scores)[::-1]
            results = []
            for idx in top_indices:
                chunk = self.chunks[idx]
                if type_filter and getattr(chunk, "type", "internal") != type_filter:
                    continue
                clean_score = max(0.0, min(1.0, float(scores[idx])))
                results.append((chunk, clean_score))
                if len(results) >= top_k:
                    break
            return results
        else:
            # Pure Python inner product calculation
            scored = []
            for idx, vec in enumerate(self._vectors):
                dot = sum(a * b for a, b in zip(vec, query_embedding))
                scored.append((idx, dot))
            scored.sort(key=lambda x: x[1], reverse=True)
            results = []
            for idx, score in scored:
                chunk = self.chunks[idx]
                if type_filter and getattr(chunk, "type", "internal") != type_filter:
                    continue
                clean_score = max(0.0, min(1.0, float(score)))
                results.append((chunk, clean_score))
                if len(results) >= top_k:
                    break
            return results

    def save_local(self, directory: str | Path) -> None:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)

        # 1. Save chunks metadata
        metadata_file = path / "chunks.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump([chunk.model_dump() for chunk in self.chunks], f, indent=2)

        # 2. Save FAISS index binary or vectors
        if self._has_faiss and self._index is not None:
            self.faiss.write_index(self._index, str(path / "faiss.index"))
        else:
            with open(path / "vectors.pkl", "wb") as f:
                pickle.dump(getattr(self, "_vectors", []), f)

        logger.info(f"Vector store persisted to {path}")

    def load_local(self, directory: str | Path) -> None:
        path = Path(directory)
        metadata_file = path / "chunks.json"
        if not metadata_file.exists():
            raise FileNotFoundError(f"Missing index metadata at {metadata_file}")

        with open(metadata_file, "r", encoding="utf-8") as f:
            raw_chunks = json.load(f)
            for item in raw_chunks:
                item.setdefault("source", "internal")
                item.setdefault("path", "")
                item.setdefault("type", "internal")
            self.chunks = [DocumentChunk(**item) for item in raw_chunks]

        index_file = path / "faiss.index"
        if self._has_faiss and index_file.exists():
            self._index = self.faiss.read_index(str(index_file))
        else:
            vec_file = path / "vectors.pkl"
            if vec_file.exists():
                with open(vec_file, "rb") as f:
                    self._vectors = pickle.load(f)

        logger.info(f"Vector store loaded {len(self.chunks)} chunks from {path}")

    def save_to_s3(self, s3_client: Any, bucket: str, prefix: str = "faiss_index") -> None:
        """Serializes and uploads index to Amazon S3."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            self.save_local(tmpdir)
            for file_path in Path(tmpdir).iterdir():
                s3_key = f"{prefix}/{file_path.name}"
                s3_client.upload_file(str(file_path), bucket, s3_key)
                logger.info(f"Uploaded {file_path.name} to s3://{bucket}/{s3_key}")

    def load_from_s3(self, s3_client: Any, bucket: str, prefix: str = "faiss_index") -> None:
        """Downloads and deserializes index from Amazon S3."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            for filename in ["chunks.json", "faiss.index", "vectors.pkl"]:
                s3_key = f"{prefix}/{filename}"
                try:
                    local_target = tmp_path / filename
                    s3_client.download_file(bucket, s3_key, str(local_target))
                except Exception:
                    # Optional files (e.g. vectors.pkl when faiss is used) may not exist
                    pass
            self.load_local(tmp_path)
