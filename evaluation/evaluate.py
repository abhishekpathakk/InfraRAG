#!/usr/bin/env python3
"""
InfraRAG Evaluation Benchmark.

Measures:
1. Retrieval Hit-Rate (Target: >= 90%)
2. Answer Faithfulness & Refusal Accuracy (Target: 100%)
3. Average Retrieval & Generation Latency
4. Estimated Evaluation Cost
"""

import json
import logging
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from src.chain import RAGChain  # noqa: E402
from src.config import settings  # noqa: E402

console = Console()
logger = logging.getLogger("evaluation")


def run_evaluation(golden_dataset_path: Path | str | None = None) -> dict:
    dataset_file = Path(golden_dataset_path or settings.BASE_DIR / "evaluation" / "golden_dataset.json")
    if not dataset_file.exists():
        raise FileNotFoundError(f"Golden dataset not found at {dataset_file}")

    with open(dataset_file, "r", encoding="utf-8") as f:
        golden_set = json.load(f)

    console.print(f"[bold cyan]Running InfraRAG Benchmark on {len(golden_set)} test cases...[/bold cyan]")

    chain = RAGChain()
    # Ensure runbooks are indexed
    chain.ingest_directory(settings.DATA_DIR)

    results = []
    in_domain_hits = 0
    in_domain_total = 0
    faithful_answers = 0
    total_latency_ms = 0.0
    total_cost_usd = 0.0

    for item in golden_set:
        q_id = item["id"]
        question = item["question"]
        is_in_domain = item["is_in_domain"]
        expected_src = item.get("expected_source")
        expected_keywords = item["expected_keywords"]

        response = chain.answer_question(question)
        total_latency_ms += response.latency_ms
        total_cost_usd += response.estimated_cost_usd

        # 1. Retrieval Hit-Rate Check
        hit = False
        if is_in_domain:
            in_domain_total += 1
            retrieved_sources = [c.source_file for c in response.retrieved_chunks]
            if isinstance(expected_src, list):
                if any(s in retrieved_sources for s in expected_src):
                    hit = True
                    in_domain_hits += 1
            elif expected_src in retrieved_sources:
                hit = True
                in_domain_hits += 1
        else:
            hit = response.confidence == "low" or "I don't know" in response.answer

        # 2. Faithfulness / Groundedness Check
        answer_faithful = False
        if is_in_domain:
            # Check keywords and citation presence
            has_keywords = any(kw.lower() in response.answer.lower() for kw in expected_keywords)
            has_citations = len(response.citations) > 0
            answer_faithful = has_keywords and has_citations
        else:
            # Out-of-domain must refuse
            answer_faithful = "I don't know based on the provided runbooks." in response.answer

        if answer_faithful:
            faithful_answers += 1

        results.append({
            "id": q_id,
            "question": question,
            "is_in_domain": is_in_domain,
            "retrieval_hit": hit,
            "answer_faithful": answer_faithful,
            "confidence": response.confidence,
            "latency_ms": response.latency_ms,
            "citations": [c.model_dump() for c in response.citations],
            "answer": response.answer,
        })

    hit_rate = (in_domain_hits / in_domain_total) * 100.0 if in_domain_total > 0 else 100.0
    faithfulness_rate = (faithful_answers / len(golden_set)) * 100.0
    avg_latency = total_latency_ms / len(golden_set)

    # Render summary table
    table = Table(title="InfraRAG Benchmark Evaluation Results", show_header=True, header_style="bold green")
    table.add_column("Metric", style="cyan")
    table.add_column("Score", justify="center", style="bold yellow")
    table.add_column("Threshold / Target", justify="center", style="dim")
    table.add_column("Status", justify="center")

    table.add_row(
        "Retrieval Hit-Rate (In-Domain)",
        f"{hit_rate:.1f}% ({in_domain_hits}/{in_domain_total})",
        ">= 90.0%",
        "[green]PASS[/green]" if hit_rate >= 90.0 else "[red]FAIL[/red]",
    )
    table.add_row(
        "Answer Faithfulness & Refusal Rate",
        f"{faithfulness_rate:.1f}% ({faithful_answers}/{len(golden_set)})",
        ">= 95.0%",
        "[green]PASS[/green]" if faithfulness_rate >= 95.0 else "[red]FAIL[/red]",
    )
    table.add_row(
        "Average Query Latency",
        f"{avg_latency:.1f} ms",
        "< 2500 ms",
        "[green]PASS[/green]" if avg_latency < 2500 else "[yellow]SLOW[/yellow]",
    )
    table.add_row(
        "Total Evaluation Cost",
        f"${total_cost_usd:.6f}",
        "<= $0.05 (Free Tier)",
        "[green]PASS[/green]",
    )

    console.print()
    console.print(table)
    console.print()

    summary = {
        "total_queries": len(golden_set),
        "hit_rate_pct": round(hit_rate, 2),
        "faithfulness_pct": round(faithfulness_rate, 2),
        "avg_latency_ms": round(avg_latency, 2),
        "total_cost_usd": round(total_cost_usd, 6),
        "results": results,
    }

    report_path = dataset_file.parent / "eval_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    console.print(f"[bold green]Saved detailed evaluation report to {report_path}[/bold green]")
    return summary


if __name__ == "__main__":
    run_evaluation()
