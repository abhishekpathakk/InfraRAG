"""
Vector Store implementation for InfraRAG.

Provides:
- BaseVectorStore: Abstract interface (swappable for S3 Vectors, pgvector, or OpenSearch)
- FAISSVectorStore: High-performance IndexFlatIP with S3 and local serialization
- NumPyVectorStore: Pure-Python/NumPy fallback for environments without faiss-cpu binaries
"""

import json
import logging
import math
import pickle
import re
import time
from abc import ABC, abstractmethod
from collections import Counter
from pathlib import Path
from typing import Any
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from src.models import DocumentChunk

logger = logging.getLogger(__name__)


ENGLISH_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can",
    "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't",
    "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have",
    "haven't", "having", "he", "her", "here", "hers", "herself", "him", "himself", "his", "how", "i",
    "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most",
    "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she", "should",
    "shouldn't", "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "were", "weren't", "what", "when", "where", "which", "while", "who",
    "whom", "why", "with", "won't", "would", "wouldn't", "you", "your", "yours", "yourself", "yourselves",
}


class BM25Index:
    """Lightweight in-memory Okapi BM25 keyword index for DevOps exact-token matching."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_lengths: list[int] = []
        self.avg_doc_len: float = 0.0
        self.doc_freqs: dict[str, int] = {}
        self.term_freqs: list[dict[str, int]] = []
        self.num_docs: int = 0

    @staticmethod
    def tokenize(text: str) -> list[str]:
        """Tokenize text into lowercase words and alphanumeric incident identifiers, filtering common stopwords."""
        words = re.findall(r"\b[a-zA-Z0-9_\-\.]+\b", text.lower())
        return [w for w in words if w not in ENGLISH_STOPWORDS and len(w) > 1]

    def index_documents(self, documents: list[str]) -> None:
        """Indexes a collection of document texts."""
        self.num_docs = len(documents)
        self.doc_lengths = []
        doc_freq_counts: Counter[str] = Counter()
        self.term_freqs = []

        total_tokens = 0
        for doc in documents:
            tokens = self.tokenize(doc)
            length = len(tokens)
            self.doc_lengths.append(length)
            total_tokens += length

            tf: dict[str, int] = dict(Counter(tokens))
            self.term_freqs.append(tf)
            for token in tf:
                doc_freq_counts[token] += 1

        self.doc_freqs = dict(doc_freq_counts)
        self.avg_doc_len = total_tokens / max(1, self.num_docs)

    def search(self, query: str, top_k: int = 30) -> list[tuple[int, float]]:
        """Scores documents for query and returns list of (doc_idx, score)."""
        tokens = self.tokenize(query)
        if not tokens or self.num_docs == 0:
            return []

        scores: list[float] = [0.0] * self.num_docs
        for token in tokens:
            df = self.doc_freqs.get(token, 0)
            if df == 0:
                continue
            # Lucene / BM25 Robertson IDF
            idf = math.log(1.0 + (self.num_docs - df + 0.5) / (df + 0.5))
            for idx in range(self.num_docs):
                f = self.term_freqs[idx].get(token, 0)
                if f > 0:
                    dl = self.doc_lengths[idx]
                    denom = f + self.k1 * (1.0 - self.b + self.b * (dl / self.avg_doc_len))
                    scores[idx] += idf * (f * (self.k1 + 1.0)) / denom

        ranked = [(idx, score) for idx, score in enumerate(scores) if score > 0.0]
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

    def to_dict(self) -> dict[str, Any]:
        """Serializes BM25 statistical model state into a JSON-compatible dict."""
        return {
            "k1": self.k1,
            "b": self.b,
            "num_docs": self.num_docs,
            "avg_doc_len": self.avg_doc_len,
            "doc_lengths": self.doc_lengths,
            "doc_freqs": self.doc_freqs,
            "term_freqs": self.term_freqs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BM25Index":
        """Reconstructs BM25 index directly from pre-computed serialized statistics."""
        idx = cls(k1=data.get("k1", 1.5), b=data.get("b", 0.75))
        idx.num_docs = data.get("num_docs", 0)
        idx.avg_doc_len = data.get("avg_doc_len", 0.0)
        idx.doc_lengths = data.get("doc_lengths", [])
        idx.doc_freqs = data.get("doc_freqs", {})
        idx.term_freqs = data.get("term_freqs", [])
        return idx


class BaseVectorStore(ABC):
    """Abstract Vector Store Interface."""

    def __init__(self) -> None:
        self.chunks: list[DocumentChunk] = []

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
        query_text: str | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """Search top-k most similar document chunks and return (chunk, score) pairs, optionally filtered by type."""
        pass

    @abstractmethod
    def save_local(self, directory: str | Path, embedding_model_id: str = "mock") -> None:
        """Persist index and metadata to local disk."""
        pass

    @abstractmethod
    def load_local(self, directory: str | Path, expected_model_id: str | None = None) -> None:
        """Load index and metadata from local disk."""
        pass

    @abstractmethod
    def save_to_s3(self, s3_client: Any, bucket: str, prefix: str = "faiss_index", embedding_model_id: str = "mock") -> None:
        """Uploads index artifacts to Amazon S3."""
        pass

    @abstractmethod
    def load_from_s3(
        self,
        s3_client: Any,
        bucket: str,
        prefix: str = "faiss_index",
        expected_model_id: str | None = None,
        target_dir: str | Path | None = None,
    ) -> None:
        """Downloads index artifacts from Amazon S3."""
        pass


class FAISSVectorStore(BaseVectorStore):
    """
    FAISS-backed vector store using IndexFlatIP (Inner Product) + BM25 Hybrid Search.
    With L2-normalized embeddings, Inner Product is mathematically identical to Cosine Similarity.
    Includes pure Python / NumPy fallbacks.
    """

    def __init__(self, dimension: int = 1024):
        super().__init__()
        self.dimension = dimension
        self.chunks: list[DocumentChunk] = []
        self._index: Any = None
        self._has_faiss = False
        self._vectors: list[list[float]] = []
        self._matrix: Any = None
        self.faiss: Any = None
        self.bm25 = BM25Index()

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
        elif HAS_NUMPY:
            new_mat = np.array(embeddings, dtype=np.float32)
            if getattr(self, "_matrix", None) is None:
                self._matrix = new_mat
            else:
                self._matrix = np.vstack([self._matrix, new_mat])
            self._vectors.extend(embeddings)
        else:
            self._vectors.extend(embeddings)

        self.chunks.extend(chunks)
        # Update BM25 index with section header + body text
        self.bm25.index_documents([f"{c.section_title} {c.content}" for c in self.chunks])

    def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 3,
        type_filter: str | None = None,
        query_text: str | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        if not self.chunks:
            return []

        candidate_pool = min(len(self.chunks), max(top_k * 15, 60)) if (query_text or type_filter) else top_k

        # 1. Dense retrieval candidates
        dense_matches: list[tuple[int, float]] = []
        if self._has_faiss and HAS_NUMPY:
            q_vec = np.array([query_embedding], dtype=np.float32)
            distances, indices = self._index.search(q_vec, candidate_pool)
            for score, idx in zip(distances[0], indices[0]):
                if idx != -1 and idx < len(self.chunks):
                    dense_matches.append((int(idx), float(score)))
        elif HAS_NUMPY and (getattr(self, "_matrix", None) is not None or self._vectors):
            mat = getattr(self, "_matrix", None)
            if mat is None:
                mat = np.array(self._vectors, dtype=np.float32)
                self._matrix = mat
            q_vec = np.array(query_embedding, dtype=np.float32)
            scores = np.dot(mat, q_vec)
            if candidate_pool < len(scores):
                top_indices = np.argpartition(scores, -candidate_pool)[-candidate_pool:]
                top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
            else:
                top_indices = np.argsort(scores)[::-1]
            for idx in top_indices:
                dense_matches.append((int(idx), float(scores[idx])))
        else:
            scored = []
            for idx, vec in enumerate(self._vectors):
                dot = sum(a * b for a, b in zip(vec, query_embedding))
                scored.append((idx, dot))
            scored.sort(key=lambda x: x[1], reverse=True)
            dense_matches = [(idx, float(score)) for idx, score in scored[:candidate_pool]]

        # 2. Hybrid Boost with BM25 if query_text is provided
        if query_text and self.bm25.num_docs > 0:
            bm25_matches = dict(self.bm25.search(query_text, top_k=candidate_pool))
            if bm25_matches:
                max_bm25 = max(bm25_matches.values())
                boosted_candidates: list[tuple[int, float]] = []
                for idx, score in dense_matches:
                    b_score = bm25_matches.get(idx, 0.0)
                    if b_score > 0 and score >= 0.15:
                        b_norm = b_score / max_bm25
                        final_score = min(1.0, score + 0.15 * b_norm)
                    else:
                        final_score = score
                    boosted_candidates.append((idx, final_score))

                boosted_candidates.sort(key=lambda x: x[1], reverse=True)

                results: list[tuple[DocumentChunk, float]] = []
                for idx, score in boosted_candidates:
                    chunk = self.chunks[idx]
                    if type_filter and getattr(chunk, "type", "internal") != type_filter:
                        continue
                    results.append((chunk, round(score, 4)))
                    if len(results) >= top_k:
                        break
                return results

        # 3. Pure Dense fallback if query_text is None
        results = []
        for idx, score in dense_matches:
            chunk = self.chunks[idx]
            if type_filter and getattr(chunk, "type", "internal") != type_filter:
                continue
            clean_score = max(0.0, min(1.0, float(score)))
            results.append((chunk, clean_score))
            if len(results) >= top_k:
                break
        return results

    def save_local(self, directory: str | Path, embedding_model_id: str = "mock") -> None:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)

        # 1. Save chunks metadata
        metadata_file = path / "chunks.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump([chunk.model_dump() for chunk in self.chunks], f, indent=2)

        # 2. Save index metadata to prevent embedding model/dimension mismatch
        index_meta = {
            "embedding_model_id": embedding_model_id,
            "dimension": self.dimension,
            "total_chunks": len(self.chunks),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(path / "index_metadata.json", "w", encoding="utf-8") as f:
            json.dump(index_meta, f, indent=2)

        # 3. Save FAISS index binary AND safe NumPy vectors as universal fallback
        if self._has_faiss and self._index is not None:
            self.faiss.write_index(self._index, str(path / "faiss.index"))

        if HAS_NUMPY:
            mat = getattr(self, "_matrix", None)
            if mat is None and self._vectors:
                mat = np.array(self._vectors, dtype=np.float32)
            elif mat is None and self._has_faiss and self._index is not None:
                try:
                    reconstructed = [self._index.reconstruct(i) for i in range(self._index.ntotal)]
                    mat = np.array(reconstructed, dtype=np.float32)
                except Exception:
                    mat = None
            if mat is not None:
                np.save(str(path / "vectors.npy"), mat)
        elif not self._has_faiss:
            with open(path / "vectors.json", "w", encoding="utf-8") as f:
                json.dump(getattr(self, "_vectors", []), f)

        # 4. Save pre-computed BM25 keyword index state for fast zero-cost cold-starts
        if self.bm25.num_docs > 0:
            with open(path / "bm25_index.json", "w", encoding="utf-8") as f:
                json.dump(self.bm25.to_dict(), f)

        logger.info(f"Vector store persisted to {path} (model: {embedding_model_id}, dim: {self.dimension})")

    def load_local(self, directory: str | Path, expected_model_id: str | None = None) -> None:
        path = Path(directory)
        metadata_file = path / "chunks.json"
        if not metadata_file.exists():
            raise FileNotFoundError(f"Missing index metadata at {metadata_file}")

        # 1. Validate index metadata if present
        meta_file = path / "index_metadata.json"
        if meta_file.exists():
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            stored_model = meta.get("embedding_model_id")
            stored_dim = meta.get("dimension")
            if expected_model_id and stored_model and stored_model != expected_model_id:
                raise ValueError(
                    f"Embedding model mismatch! Index was created with '{stored_model}', "
                    f"but current system is configured for '{expected_model_id}'. "
                    f"Re-run ingestion or update embedding provider."
                )
            if stored_dim and stored_dim != self.dimension:
                raise ValueError(
                    f"Vector dimension mismatch! Index has {stored_dim} dimensions, "
                    f"but vector store expects {self.dimension}."
                )

        # 2. Load chunk definitions
        with open(metadata_file, "r", encoding="utf-8") as f:
            raw_chunks = json.load(f)
            for item in raw_chunks:
                item.setdefault("source", "internal")
                item.setdefault("path", "")
                item.setdefault("type", "internal")
            self.chunks = [DocumentChunk(**item) for item in raw_chunks]

        # Rebuild or restore BM25 index on load (pre-computed json saves ~1.5s cold-start latency)
        bm25_file = path / "bm25_index.json"
        if bm25_file.exists():
            try:
                with open(bm25_file, "r", encoding="utf-8") as f:
                    self.bm25 = BM25Index.from_dict(json.load(f))
            except Exception as e:
                logger.warning(f"Could not load pre-computed BM25 index ({e}). Rebuilding...")
                self.bm25.index_documents([f"{c.section_title} {c.content}" for c in self.chunks])
        else:
            self.bm25.index_documents([f"{c.section_title} {c.content}" for c in self.chunks])

        # 3. Load vectors / FAISS index and immediately cache contiguous matrix
        index_file = path / "faiss.index"
        vec_npy = path / "vectors.npy"
        vec_pkl = path / "vectors.pkl"
        vec_json = path / "vectors.json"

        loaded_vectors = False
        if self._has_faiss and index_file.exists():
            self._index = self.faiss.read_index(str(index_file))
            loaded_vectors = True

        if HAS_NUMPY and vec_npy.exists():
            mat = np.load(str(vec_npy), allow_pickle=False)
            self._matrix = mat
            self._vectors = mat.tolist()
            loaded_vectors = True
        elif vec_pkl.exists() and not loaded_vectors:
            # Backward-compatibility fallback for legacy pickle files
            with open(vec_pkl, "rb") as f:
                self._vectors = pickle.load(f)
            if HAS_NUMPY and self._vectors:
                self._matrix = np.array(self._vectors, dtype=np.float32)
            loaded_vectors = True
        elif vec_json.exists() and not loaded_vectors:
            with open(vec_json, "r", encoding="utf-8") as f:
                self._vectors = json.load(f)
            if HAS_NUMPY and self._vectors:
                self._matrix = np.array(self._vectors, dtype=np.float32)
            loaded_vectors = True

        if not loaded_vectors and index_file.exists() and not self._has_faiss:
            raise RuntimeError(
                f"Found FAISS index at {index_file}, but 'faiss-cpu' is not installed in the current environment "
                f"and no fallback 'vectors.npy' exists. Please install faiss-cpu or regenerate the index."
            )

        logger.info(f"Vector store loaded {len(self.chunks)} chunks from {path}")

    def save_to_s3(self, s3_client: Any, bucket: str, prefix: str = "faiss_index", embedding_model_id: str = "mock") -> None:
        """Serializes and uploads index to Amazon S3."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            self.save_local(tmpdir, embedding_model_id=embedding_model_id)
            for file_path in Path(tmpdir).iterdir():
                s3_key = f"{prefix}/{file_path.name}"
                s3_client.upload_file(str(file_path), bucket, s3_key)
                logger.info(f"Uploaded {file_path.name} to s3://{bucket}/{s3_key}")

    def load_from_s3(
        self,
        s3_client: Any,
        bucket: str,
        prefix: str = "faiss_index",
        expected_model_id: str | None = None,
        target_dir: str | Path | None = None,
    ) -> None:
        """Downloads and deserializes index from Amazon S3.

        If target_dir is specified (e.g. /tmp/faiss_index in Lambda), downloaded files
        persist across invocations for high-performance warm-start reuse.
        """
        if target_dir is not None:
            dest_dir = Path(target_dir)
            dest_dir.mkdir(parents=True, exist_ok=True)
            for filename in ["chunks.json", "index_metadata.json", "faiss.index", "vectors.npy", "vectors.pkl", "bm25_index.json"]:
                s3_key = f"{prefix}/{filename}"
                try:
                    local_target = dest_dir / filename
                    s3_client.download_file(bucket, s3_key, str(local_target))
                except Exception:
                    pass
            self.load_local(dest_dir, expected_model_id=expected_model_id)
        else:
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                for filename in ["chunks.json", "index_metadata.json", "faiss.index", "vectors.npy", "vectors.pkl", "bm25_index.json"]:
                    s3_key = f"{prefix}/{filename}"
                    try:
                        local_target = tmp_path / filename
                        s3_client.download_file(bucket, s3_key, str(local_target))
                    except Exception:
                        pass
                self.load_local(tmp_path, expected_model_id=expected_model_id)

