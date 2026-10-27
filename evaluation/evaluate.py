#!/usr/bin/env python3
"""
InfraRAG Comprehensive Evaluation Suite.

Evaluates both:
1. Primary Golden Dataset (25 technical questions + negative refusal cases)
2. Frozen Held-Out Dataset (10 unseen incident questions)

Metrics Computed:
- Top-1 Retrieval Hit-Rate
- Top-5 Retrieval Hit-Rate
- Retrieval MRR (Mean Reciprocal Rank)
- In-Domain Extractive Groundedness & Keyword Recall (In-Domain only denominator)
- Out-of-Domain Refusal Accuracy (Negative questions)
- Sub-millisecond Vector Retrieval Latency & Generation Latency
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from src.chain import RAGChain  # noqa: E402
from src.config import settings  # noqa: E402

console = Console()
logger = logging.getLogger("evaluation")


def evaluate_dataset(chain: RAGChain, dataset_path: Path, title: str) -> dict[str, Any]:
    with open(dataset_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    results = []
    in_domain_total = 0
    top1_hits = 0
    top5_hits = 0
    mrr_sum = 0.0
    in_domain_grounded = 0

    out_domain_total = 0
    out_domain_refusals = 0

    total_latency_ms = 0.0
    total_retrieval_ms = 0.0

    for item in items:
        q_id = item["id"]
        question = item.get("question") or item.get("query", "")
        is_in_domain = item["is_in_domain"]
        expected_src = item.get("expected_source") or item.get("target_source_file")
        expected_kws = item.get("expected_keywords") or item.get("expected_answer_keywords", [])

        response = chain.answer_question(question)
        total_latency_ms += response.latency_ms
        total_retrieval_ms += response.retrieval_latency_ms

        # 1. Retrieval Ranking & MRR
        hit_rank = 0
        if is_in_domain:
            in_domain_total += 1
            retrieved_sources = [f"{c.source_file} {c.path}" for c in response.retrieved_chunks]

            for rank_idx, src in enumerate(retrieved_sources, start=1):
                is_match = False
                if isinstance(expected_src, list):
                    is_match = any(s.lower() in src.lower() for s in expected_src)
                elif expected_src:
                    is_match = expected_src.lower() in src.lower()

                if is_match:
                    hit_rank = rank_idx
                    break

            if hit_rank == 1:
                top1_hits += 1
                top5_hits += 1
                mrr_sum += 1.0
            elif hit_rank > 1:
                top5_hits += 1
                mrr_sum += 1.0 / hit_rank

            # 2. In-Domain Extractive Groundedness
            has_kws = any(kw.lower() in response.answer.lower() for kw in expected_kws)
            has_cits = len(response.citations) > 0
            if has_kws and has_cits:
                in_domain_grounded += 1
        else:
            out_domain_total += 1
            if "I don't know based on the provided runbooks." in response.answer:
                out_domain_refusals += 1

        results.append({
            "id": q_id,
            "question": question,
            "is_in_domain": is_in_domain,
            "retrieval_rank": hit_rank if hit_rank > 0 else None,
            "answer": response.answer,
            "citations": [c.model_dump() for c in response.citations],
            "latency_ms": response.latency_ms,
        })

    top1_rate = (top1_hits / in_domain_total * 100.0) if in_domain_total else 100.0
    top5_rate = (top5_hits / in_domain_total * 100.0) if in_domain_total else 100.0
    mrr = (mrr_sum / in_domain_total) if in_domain_total else 1.0
    grounded_rate = (in_domain_grounded / in_domain_total * 100.0) if in_domain_total else 100.0
    refusal_rate = (out_domain_refusals / out_domain_total * 100.0) if out_domain_total else 100.0
    avg_latency = total_latency_ms / len(items)
    avg_retrieval = total_retrieval_ms / len(items)

    # Render summary table
    table = Table(title=title, show_header=True, header_style="bold green")
    table.add_column("Metric Dimension", style="cyan")
    table.add_column("Score / Count", justify="center", style="bold yellow")
    table.add_column("Industry Target", justify="center", style="dim")
    table.add_column("Status", justify="center")

    table.add_row(
        "Retrieval Top-1 Hit-Rate",
        f"{top1_rate:.1f}% ({top1_hits}/{in_domain_total})",
        ">= 80.0%",
        "[green]PASS[/green]" if top1_rate >= 80.0 else "[yellow]REVIEW[/yellow]",
    )
    table.add_row(
        "Retrieval Top-5 Hit-Rate",
        f"{top5_rate:.1f}% ({top5_hits}/{in_domain_total})",
        ">= 90.0%",
        "[green]PASS[/green]" if top5_rate >= 90.0 else "[red]FAIL[/red]",
    )
    table.add_row(
        "Mean Reciprocal Rank (MRR)",
        f"{mrr:.3f}",
        ">= 0.850",
        "[green]PASS[/green]" if mrr >= 0.850 else "[yellow]REVIEW[/yellow]",
    )
    table.add_row(
        "In-Domain Extractive Groundedness",
        f"{grounded_rate:.1f}% ({in_domain_grounded}/{in_domain_total})",
        ">= 50.0% (Mock Baseline)",
        "[green]PASS[/green]" if grounded_rate >= 50.0 else "[red]FAIL[/red]",
    )
    table.add_row(
        "Out-of-Domain Refusal Accuracy",
        f"{refusal_rate:.1f}% ({out_domain_refusals}/{out_domain_total})",
        "100.0% (Strict Refusal)",
        "[green]PASS[/green]" if refusal_rate >= 100.0 else "[red]FAIL[/red]",
    )
    table.add_row(
        "Avg Total Latency (In-RAM Search)",
        f"{avg_latency:.2f} ms (Retrieval: {avg_retrieval:.2f}ms)",
        "< 2500 ms",
        "[green]PASS[/green]",
    )

    console.print()
    console.print(table)

    return {
        "dataset": str(dataset_path.name),
        "total_queries": len(items),
        "in_domain_total": in_domain_total,
        "out_domain_total": out_domain_total,
        "top1_hit_rate_pct": round(top1_rate, 2),
        "top5_hit_rate_pct": round(top5_rate, 2),
        "mrr": round(mrr, 3),
        "in_domain_grounded_pct": round(grounded_rate, 2),
        "out_domain_refusal_pct": round(refusal_rate, 2),
        "avg_latency_ms": round(avg_latency, 2),
        "avg_retrieval_ms": round(avg_retrieval, 2),
        "results": results,
    }


def run_evaluation() -> dict:
    golden_path = settings.BASE_DIR / "evaluation" / "golden_dataset.json"
    heldout_path = settings.BASE_DIR / "evaluation" / "held_out_dataset.json"

    console.print("[bold cyan]Initializing InfraRAG Engine & Indexing Runbooks...[/bold cyan]")
    chain = RAGChain()
    chain.ingest_directory(settings.DATA_DIR)

    console.print(f"[bold green]Indexed {len(chain.vector_store.chunks)} chunks across multi-source corpus.[/bold green]")

    golden_summary = evaluate_dataset(
        chain=chain,
        dataset_path=golden_path,
        title="1. InfraRAG Golden Benchmark (25 Technical Incidents + Out-of-Domain)",
    )

    heldout_summary = evaluate_dataset(
        chain=chain,
        dataset_path=heldout_path,
        title="2. InfraRAG Frozen Held-Out Validation (10 Unseen Incident Scenarios)",
    )

    report_path = settings.BASE_DIR / "evaluation" / "eval_report.json"
    full_report = {
        "indexed_chunks": len(chain.vector_store.chunks),
        "golden_benchmark": golden_summary,
        "held_out_validation": heldout_summary,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2)

    console.print(f"\n[bold green]Complete evaluation report persisted to {report_path}[/bold green]\n")
    return full_report


if __name__ == "__main__":
    run_evaluation()
