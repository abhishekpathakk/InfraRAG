#!/usr/bin/env python3
"""
InfraRAG CLI: Interactive terminal interface for runbook indexing and Q&A.

Usage:
    python cli.py ingest
    python cli.py ask "What causes Exit Code 137?"
    python cli.py interactive
"""

import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.chain import RAGChain
from src.config import settings

console = Console()


def get_chain() -> RAGChain:
    chain = RAGChain()
    # If index cache exists, load it
    cache_file = settings.CACHE_DIR / "chunks.json"
    if cache_file.exists():
        chain.vector_store.load_local(settings.CACHE_DIR)
    return chain


def do_ingest():
    console.print(Panel.fit("[bold cyan]InfraRAG Ingestion Pipeline[/bold cyan]", border_style="cyan"))
    console.print(f"[dim]Scanning runbooks directory: {settings.DATA_DIR}[/dim]")

    chain = RAGChain()
    total_chunks = chain.ingest_directory(settings.DATA_DIR)

    # Persist locally to cache directory
    chain.vector_store.save_local(settings.CACHE_DIR)

    console.print(f"[bold green]✔ Successfully indexed and saved {total_chunks} chunks to {settings.CACHE_DIR}[/bold green]\n")


def do_ask(question: str, type_filter: str | None = None):
    chain = get_chain()
    if not chain.vector_store.chunks:
        console.print("[yellow]Index not found. Running ingestion first...[/yellow]")
        do_ingest()
        chain = get_chain()

    status_msg = f"[bold blue]Querying runbooks (type filter: {type_filter or 'ALL'}) & generating grounded answer...[/bold blue]"
    with console.status(status_msg):
        response = chain.answer_question(question, type_filter=type_filter)

    # Render Answer Panel
    console.print(
        Panel(
            response.answer,
            title=f"[bold green]Answer (Confidence: {response.confidence.upper()})[/bold green]",
            border_style="green" if response.confidence == "high" else "yellow",
        )
    )

    # Render Citations Table
    if response.citations:
        cit_table = Table(title="Source Citations", show_header=True, header_style="bold magenta")
        cit_table.add_column("Source", style="cyan")
        cit_table.add_column("Type", style="bold yellow")
        cit_table.add_column("File / Section", style="white")
        cit_table.add_column("Chunk ID", style="dim")
        cit_table.add_column("Score", justify="right", style="green")

        for cit in response.citations:
            cit_table.add_row(
                cit.source,
                cit.type,
                f"{cit.source_file}\n{cit.section_title}",
                cit.chunk_id,
                f"{cit.relevance_score:.4f}",
            )
        console.print(cit_table)

    # Render Metrics Table
    metrics_table = Table(title="Execution & Cost Metrics", show_header=True, header_style="bold yellow")
    metrics_table.add_column("Total Latency", justify="center")
    metrics_table.add_column("Retrieval Latency", justify="center")
    metrics_table.add_column("Gen Latency", justify="center")
    metrics_table.add_column("Tokens (In / Out)", justify="center")
    metrics_table.add_column("Estimated Cost", justify="center", style="bold green")

    metrics_table.add_row(
        f"{response.latency_ms:.1f} ms",
        f"{response.retrieval_latency_ms:.1f} ms",
        f"{response.generation_latency_ms:.1f} ms",
        f"{response.input_tokens} / {response.output_tokens}",
        f"${response.estimated_cost_usd:.6f}",
    )
    console.print(metrics_table)
    console.print()


def do_interactive():
    console.print(Panel.fit("[bold cyan]InfraRAG Interactive SRE Assistant[/bold cyan]\nType 'exit' or 'quit' to stop.\nPrefix query with '[internal]' or '[public]' to filter.", border_style="cyan"))
    while True:
        try:
            q = console.input("\n[bold green]Ask InfraRAG > [/bold green]").strip()
            if not q:
                continue
            if q.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break
            
            type_filter = None
            if q.lower().startswith("[internal]"):
                type_filter = "internal"
                q = q[len("[internal]"):].strip()
            elif q.lower().startswith("[public]"):
                type_filter = "public"
                q = q[len("[public]"):].strip()

            do_ask(q, type_filter=type_filter)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session closed.[/dim]")
            break


def main():
    import argparse
    parser = argparse.ArgumentParser(description="InfraRAG CLI: SRE & DevOps Runbook Assistant")
    subparsers = parser.add_subparsers(dest="command")

    # Ingest
    subparsers.add_parser("ingest", help="Chunk and index runbooks")

    # Ask
    ask_parser = subparsers.add_parser("ask", help="Ask a question with optional type filter")
    ask_parser.add_argument("question", nargs="+", help="The question to ask")
    ask_parser.add_argument("--type", choices=["internal", "public", "all"], default=None, help="Filter corpus by type")

    # Interactive
    subparsers.add_parser("interactive", help="Start interactive terminal chat")

    args = parser.parse_args()

    if args.command == "ingest":
        do_ingest()
    elif args.command == "ask":
        q = " ".join(args.question)
        type_filter = None if args.type in (None, "all") else args.type
        do_ask(q, type_filter=type_filter)
    elif args.command in ("interactive", "repl", "chat"):
        do_interactive()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
