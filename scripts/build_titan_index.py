#!/usr/bin/env python3
"""
Builds a persistent vector index using Amazon Bedrock Titan Text Embeddings v2.

Prerequisites:
- AWS credentials with Bedrock access in a region where Titan v2 is enabled (e.g., us-west-2).
- Bedrock token quotas available (on-demand throughput).
"""

import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.chunker import MarkdownChunker
from src.config import settings
from src.embeddings import BedrockTitanEmbeddingProvider
from src.vector_store import FAISSVectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_titan_index")


def build_titan_index(
    data_dir: Path = settings.DATA_DIR,
    output_dir: Path = settings.BASE_DIR / "index_cache" / "titan_v2",
    region: str = "us-west-2",
) -> None:
    logger.info(f"Initializing Amazon Bedrock Titan v2 Indexer (Region: {region})")
    output_dir.mkdir(parents=True, exist_ok=True)

    provider = BedrockTitanEmbeddingProvider(region_name=region)
    store = FAISSVectorStore(dimension=provider.dimension)
    chunker = MarkdownChunker(chunk_size=500, chunk_overlap=100)

    # Prioritize internal runbooks first, followed by public runbooks
    files = sorted(list((data_dir / "internal").glob("*.md")))
    if not files:
        files = sorted(list(data_dir.rglob("*.md")))

    logger.info(f"Discovered {len(files)} runbook files for Titan indexing.")

    all_chunks = []
    for file_path in files:
        try:
            doc_type = "internal" if "internal" in str(file_path) else "public"
            file_chunks = chunker.chunk_markdown_file(file_path, doc_type=doc_type)
            all_chunks.extend(file_chunks)
        except Exception as e:
            logger.warning(f"Skipping {file_path}: {e}")

    logger.info(f"Total chunks extracted: {len(all_chunks)}. Commencing Titan v2 embeddings generation...")

    texts = [f"{c.section_title}\n{c.content}" for c in all_chunks]
    embeddings = []
    
    # Process in batches to handle API rate limits gracefully
    for idx, text in enumerate(texts):
        logger.info(f"Embedding chunk {idx + 1}/{len(texts)}: {all_chunks[idx].chunk_id}")
        try:
            emb = provider.embed_text(text)
            embeddings.append(emb)
        except Exception as e:
            logger.error(f"Bedrock Titan embedding failed at chunk {idx + 1}: {e}")
            logger.error("Live AWS Bedrock quota exhausted or access throttled. Halting Titan index build.")
            sys.exit(1)

    store.add_documents(all_chunks, embeddings)
    store.save_local(output_dir, embedding_model_id="amazon.titan-embed-text-v2:0")
    logger.info(f"Titan v2 index successfully persisted to {output_dir}")


if __name__ == "__main__":
    build_titan_index()
