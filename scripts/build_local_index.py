#!/usr/bin/env python3
"""
Builds a persistent vector index using open-source dense neural embeddings via FastEmbed.

Model Architecture:
- Canonical Model: BAAI/bge-small-en-v1.5
- HuggingFace Commit SHA: 5c38ec7c405ec4b44b94cc5a9bb96e735b38267a
- Quantized ONNX Engine: Qdrant/bge-small-en-v1.5-onnx-Q (Commit SHA: aa8f8b060edb00e03bfdd08813a2949946c8ba55)
- Vector Dimension: 384
- Zero AWS API / Token Costs: 100% Free, local CPU inference via ONNX Runtime.
"""

import logging
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.chunker import MarkdownChunker
from src.config import settings
from src.embeddings import LocalFastEmbedProvider
from src.vector_store import FAISSVectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_local_index")

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
DEFAULT_OUTPUT_DIR = settings.BASE_DIR / "index_cache" / "local_bge_small"


def build_local_index(
    data_dir: Path = settings.DATA_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    model_name: str = DEFAULT_MODEL,
    revision: str = DEFAULT_REVISION,
    batch_size: int = 64,
) -> None:
    start_total = time.perf_counter()
    logger.info(f"Initializing Local Neural Indexer: {model_name} (revision: {revision})")
    output_dir.mkdir(parents=True, exist_ok=True)

    provider = LocalFastEmbedProvider(model_name=model_name, revision=revision, batch_size=batch_size)
    store = FAISSVectorStore(dimension=provider.dimension)
    chunker = MarkdownChunker(chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP)

    files = sorted(list(data_dir.rglob("*.md")))
    logger.info(f"Discovered {len(files)} runbook files in {data_dir}.")

    all_chunks = []
    for file_path in files:
        try:
            doc_type = "internal" if "internal" in str(file_path) else "public"
            chunks = chunker.chunk_markdown_file(file_path, doc_type=doc_type)
            all_chunks.extend(chunks)
        except Exception as e:
            logger.warning(f"Skipping {file_path}: {e}")

    logger.info(f"Extracted {len(all_chunks)} chunks. Generating neural embeddings via FastEmbed ONNX...")
    embed_start = time.perf_counter()
    texts = [f"{c.section_title}\n{c.content}" for c in all_chunks]
    embeddings = provider.embed_batch(texts)
    embed_duration = time.perf_counter() - embed_start
    logger.info(
        f"Generated {len(embeddings)} vectors ({provider.dimension}-dim) in {embed_duration:.2f}s "
        f"({embed_duration / len(texts) * 1000.0:.2f} ms/chunk)."
    )

    store.add_documents(all_chunks, embeddings)
    store.save_local(output_dir, embedding_model_id=f"fastembed:{model_name}@{revision}")

    total_duration = time.perf_counter() - start_total
    logger.info(f"Local neural index successfully persisted to {output_dir} in {total_duration:.2f}s.")


if __name__ == "__main__":
    build_local_index()

