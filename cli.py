#!/usr/bin/env python3
"""
InfraRAG CLI: Interactive terminal interface for runbook indexing and Q&A.

Usage:
    python cli.py ingest
    python cli.py ask "What causes Exit Code 137?"
    python cli.py interactive
"""

import sys
from pathlib import Path
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


def do_ask(question: str):
    chain = get_chain()
    if not chain.vector_store.chunks:
        console.print("[yellow]Index not found. Running ingestion first...[/yellow]")
        do_ingest()
        chain = get_chain()

    with console.status("[bold blue]Querying runbooks & generating grounded answer...[/bold blue]"):
        response = chain.answer_question(question)

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
        cit_table.add_column("Runbook File", style="cyan")
        cit_table.add_column("Section", style="white")
        cit_table.add_column("Chunk ID", style="dim")
        cit_table.add_column("Score", justify="right", style="green")

        for cit in response.citations:
            cit_table.add_row(
                cit.source_file,
                cit.section_title,
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
    console.print(Panel.fit("[bold cyan]InfraRAG Interactive SRE Assistant[/bold cyan]\nType 'exit' or 'quit' to stop.", border_style="cyan"))
    while True:
        try:
            q = console.input("\n[bold green]Ask InfraRAG > [/bold green]").strip()
            if not q:
                continue
            if q.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break
            do_ask(q)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session closed.[/dim]")
            break


def main():
    if len(sys.argv) < 2:
        console.print("[bold red]Usage:[/bold red] python cli.py [ingest | ask '<question>' | interactive]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "ingest":
        do_ingest()
    elif cmd == "ask":
        if len(sys.argv) < 3:
            console.print("[bold red]Error:[/bold red] Please provide a question. Example: python cli.py ask 'What is Exit Code 137?'")
            sys.exit(1)
        do_ask(" ".join(sys.argv[2:]))
    elif cmd in ("interactive", "repl", "chat"):
        do_interactive()
    else:
        console.print(f"[bold red]Unknown command:[/bold red] {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
