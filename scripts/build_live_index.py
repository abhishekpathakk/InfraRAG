#!/usr/bin/env python3
"""
InfraRAG Offline Live Index Builder.

Builds a production vector index locally using Amazon Bedrock Titan Text Embeddings v2
with concurrent ThreadPoolExecutor and adaptive retries to overcome Lambda 60s timeout limits.

Persists index metadata guard (embedding_model_id, dimension) to prevent silent index corruption,
and optionally uploads directly to Amazon S3.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from pathlib import Path
import sys
import time
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from rich.console import Console  # noqa: E402
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn  # noqa: E402

from src.chunker import MarkdownChunker  # noqa: E402
from src.config import settings  # noqa: E402
from src.embeddings import BedrockTitanEmbeddingProvider, MockEmbeddingProvider  # noqa: E402
from src.models import DocumentChunk  # noqa: E402
from src.vector_store import FAISSVectorStore  # noqa: E402

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_live_index")


def parse_args():
    parser = argparse.ArgumentParser(description="InfraRAG Offline Live Index Builder")
    parser.add_argument("--data-dir", type=Path, default=settings.DATA_DIR, help="Path to runbooks directory")
    parser.add_argument("--output-dir", type=Path, default=settings.BASE_DIR / "index_cache", help="Output directory for index")
    parser.add_argument("--workers", type=int, default=6, help="Parallel worker threads for Bedrock embedding calls")
    parser.add_argument("--mock", action="store_true", help="Use MockEmbeddingProvider for offline dry-run test")
    parser.add_argument("--upload-s3", action="store_true", help="Upload built index directly to S3")
    parser.add_argument("--bucket", type=str, default=settings.S3_BUCKET_NAME, help="Destination S3 bucket name")
    parser.add_argument("--region", type=str, default=settings.AWS_REGION, help="AWS region")
    parser.add_argument("--model-id", type=str, default=settings.BEDROCK_EMBEDDING_MODEL_ID, help="Titan embedding model ID")
    return parser.parse_args()


def load_and_chunk_documents(data_dir: Path) -> list[DocumentChunk]:
    chunker = MarkdownChunker(chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP)
    md_files = list(data_dir.glob("**/*.md"))
    valid_files = [f for f in md_files if f.is_file() and not f.name.startswith(".")]

    console.print(f"[bold cyan]Found {len(valid_files)} runbooks in {data_dir}...[/bold cyan]")
    all_chunks: list[DocumentChunk] = []

    for file_path in valid_files:
        rel_path = file_path.relative_to(data_dir)
        source = "public" if "public" in rel_path.parts else "internal"
        doc_type = "public" if source == "public" else "internal"
        chunks = chunker.chunk_markdown_file(file_path=file_path, source=source, doc_type=doc_type)
        all_chunks.extend(chunks)

    console.print(f"[bold green]Parsed {len(all_chunks)} chunks across corpus.[/bold green]")
    return all_chunks


def embed_chunks_concurrently(
    chunks: list[DocumentChunk],
    provider: Any,
    max_workers: int = 6,
) -> list[list[float]]:
    """Embeds all document chunks using a thread pool with adaptive rate limiting."""
    total = len(chunks)
    embeddings: list[list[float] | None] = [None] * total

    def embed_single(idx: int, text: str) -> tuple[int, list[float]]:
        # BedrockTitanEmbeddingProvider internally uses adaptive retry config
        vec = provider.embed_text(text)
        return idx, vec

    console.print(f"[bold yellow]Embedding {total} chunks with {max_workers} worker threads...[/bold yellow]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Embedding runbooks...", total=total)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(embed_single, i, chunks[i].content): i
                for i in range(total)
            }
            for future in as_completed(future_to_idx):
                idx, vec = future.result()
                embeddings[idx] = vec
                progress.advance(task)

    return [v for v in embeddings if v is not None]


def main():
    args = parse_args()

    console.print(
        f"\n[bold green]=======================================================\n"
        f"  InfraRAG Offline Live Index Builder\n"
        f"  Region: {args.region} | Model: {args.model_id if not args.mock else 'mock'}\n"
        f"=======================================================[/bold green]\n"
    )

    # 1. Initialize Embedding Provider & Vector Store
    if args.mock:
        console.print("[dim]Running in MOCK mode (--mock flag passed).[/dim]")
        provider = MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)
        active_model_id = "mock"
    else:
        console.print(f"[bold]Connecting to Amazon Bedrock ({args.region})...[/bold]")
        provider = BedrockTitanEmbeddingProvider(
            region_name=args.region,
            model_id=args.model_id,
            dimension=settings.EMBEDDING_DIMENSION,
        )
        active_model_id = args.model_id

    vector_store = FAISSVectorStore(dimension=settings.EMBEDDING_DIMENSION)

    # 2. Chunk runbooks
    start_time = time.time()
    chunks = load_and_chunk_documents(args.data_dir)
    if not chunks:
        console.print("[red]No chunks found to index. Aborting.[/red]")
        return

    # 3. Embed chunks concurrently
    embeddings = embed_chunks_concurrently(chunks, provider, max_workers=args.workers)
    vector_store.add_documents(chunks, embeddings)

    elapsed = time.time() - start_time
    console.print(f"[bold green]Ingestion complete in {elapsed:.1f}s ({len(chunks) / elapsed:.1f} chunks/sec).[/bold green]")

    # 4. Save locally with metadata guard
    args.output_dir.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(args.output_dir, embedding_model_id=active_model_id)
    console.print(f"[bold]Saved index and metadata guard to [cyan]{args.output_dir}[/cyan][/bold]")

    # 5. Optional S3 Upload
    if args.upload_s3:
        console.print(f"\n[bold yellow]Uploading index to s3://{args.bucket}/faiss_index/ ...[/bold yellow]")
        import boto3
        s3 = boto3.client("s3", region_name=args.region)
        vector_store.save_to_s3(
            s3_client=s3,
            bucket=args.bucket,
            prefix="faiss_index",
            embedding_model_id=active_model_id,
        )
        console.print(f"[bold green]Index successfully uploaded to S3 bucket '{args.bucket}'![/bold green]")

    # 6. Verify index can be re-loaded cleanly
    test_store = FAISSVectorStore(dimension=settings.EMBEDDING_DIMENSION)
    test_store.load_local(args.output_dir, expected_model_id=active_model_id)
    console.print(f"[bold green]Self-test verification passed: loaded {len(test_store.chunks)} chunks.[/bold green]\n")


if __name__ == "__main__":
    main()
