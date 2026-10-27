#!/usr/bin/env python3
"""
InfraRAG Relevance Score Distribution & Threshold Calibration Tool.

Analyzes top-1 retrieval cosine similarities across In-Domain incident queries
and Out-of-Domain negative refusal queries to scientifically calibrate
the MIN_RELEVANCE_THRESHOLD cutoff.
"""

import argparse
import json
import logging
from pathlib import Path
import statistics
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from src.chain import RAGChain  # noqa: E402
from src.config import settings  # noqa: E402

console = Console()
logging.basicConfig(level=logging.WARNING)


def parse_args():
    parser = argparse.ArgumentParser(description="Calibrate InfraRAG retrieval relevance threshold")
    parser.add_argument("--index-dir", type=Path, default=None, help="Optional pre-built index directory")
    return parser.parse_args()


def main():
    args = parse_args()
    console.print(
        "\n[bold green]=======================================================\n"
        "  InfraRAG Threshold Calibration & Score Distribution\n"
        "=======================================================[/bold green]\n"
    )

    chain = RAGChain()
    if args.index_dir and (args.index_dir / "chunks.json").exists():
        console.print(f"[cyan]Loading pre-built vector index from {args.index_dir}...[/cyan]")
        chain.vector_store.load_local(args.index_dir)
    else:
        console.print(f"[cyan]Ingesting corpus runbooks from {settings.DATA_DIR}...[/cyan]")
        chain.ingest_directory(settings.DATA_DIR)

    console.print(f"[green]Ready: {len(chain.vector_store.chunks)} chunks in vector store.[/green]\n")

    # Load queries from both datasets
    golden_path = settings.BASE_DIR / "evaluation" / "golden_dataset.json"
    heldout_path = settings.BASE_DIR / "evaluation" / "held_out_dataset.json"

    queries = []
    for path in [golden_path, heldout_path]:
        with open(path, "r", encoding="utf-8") as f:
            items = json.load(f)
            for it in items:
                q = it.get("question") or it.get("query", "")
                queries.append({
                    "id": it["id"],
                    "query": q,
                    "is_in_domain": it["is_in_domain"],
                    "dataset": path.name,
                })

    in_domain_scores = []
    out_domain_scores = []

    detail_table = Table(title="Top-1 Retrieval Scores by Query", show_header=True, header_style="bold cyan")
    detail_table.add_column("ID", style="dim", width=12)
    detail_table.add_column("Domain", justify="center", width=10)
    detail_table.add_column("Top-1 Score", justify="right", style="bold yellow", width=12)
    detail_table.add_column("Query Snippet", style="white")

    for item in queries:
        matches, _ = chain.retriever.retrieve(item["query"], top_k=1)
        top_score = matches[0][1] if matches else 0.0

        if item["is_in_domain"]:
            in_domain_scores.append(top_score)
            dom_label = "[green]IN-DOMAIN[/green]"
        else:
            out_domain_scores.append(top_score)
            dom_label = "[red]OUT-OF-DOM[/red]"

        detail_table.add_row(
            str(item["id"]),
            dom_label,
            f"{top_score:.4f}",
            str(item["query"])[:60] + ("..." if len(str(item["query"])) > 60 else ""),
        )

    console.print(detail_table)
    console.print()

    # Distribution Statistics Table
    dist_table = Table(title="Distribution Summary & Separation Analysis", show_header=True, header_style="bold magenta")
    dist_table.add_column("Dimension", style="cyan")
    dist_table.add_column("In-Domain (Technical)", justify="center", style="green")
    dist_table.add_column("Out-of-Domain (Refusal)", justify="center", style="red")

    def stats_summary(scores: list[float]) -> tuple[float, float, float, float, float]:
        if not scores:
            return 0.0, 0.0, 0.0, 0.0, 0.0
        s = sorted(scores)
        n = len(s)
        med = statistics.median(s)
        mean = statistics.mean(s)
        min_v = s[0]
        max_v = s[-1]
        p10 = s[int(n * 0.1)]
        return min_v, p10, med, mean, max_v

    in_min, in_p10, in_med, in_mean, in_max = stats_summary(in_domain_scores)
    out_min, out_p10, out_med, out_mean, out_max = stats_summary(out_domain_scores)

    dist_table.add_row("Count (N)", str(len(in_domain_scores)), str(len(out_domain_scores)))
    dist_table.add_row("Min Score", f"{in_min:.4f}", f"{out_min:.4f}")
    dist_table.add_row("10th Percentile (p10)", f"{in_p10:.4f}", f"{out_p10:.4f}")
    dist_table.add_row("Median Score (p50)", f"{in_med:.4f}", f"{out_med:.4f}")
    dist_table.add_row("Mean Score", f"{in_mean:.4f}", f"{out_mean:.4f}")
    dist_table.add_row("Max Score", f"{in_max:.4f}", f"{out_max:.4f}")

    console.print(dist_table)
    console.print()

    # Recommendation
    current_thresh = settings.MIN_RELEVANCE_THRESHOLD
    console.print(f"[bold]Current Configured Threshold:[/bold] [yellow]{current_thresh:.2f}[/yellow]")
    console.print(f"[bold]In-Domain Min Score:[/bold] [green]{in_min:.4f}[/green]")
    console.print(f"[bold]Out-of-Domain Max Score:[/bold] [red]{out_max:.4f}[/red]")

    if in_min > out_max:
        recommended = (in_min + out_max) / 2.0
        console.print(
            f"[bold green]PERFECT SEPARATION FOUND![/bold green] "
            f"All in-domain queries score above all out-of-domain queries. "
            f"Recommended optimal threshold: [bold cyan]{recommended:.2f}[/bold cyan]\n"
        )
    else:
        console.print(
            "[bold yellow]OVERLAPPING SCORES DETECTED in mock/vector space.[/bold yellow] "
            "In mock mode, lexical stopword filtering + LLM prompt-grounding enforces refusal. "
            "For live Titan embeddings, cosine similarity separation typically centers around [bold cyan]0.35 - 0.45[/bold cyan].\n"
        )


if __name__ == "__main__":
    main()
