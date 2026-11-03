#!/usr/bin/env python3
"""
Empirical Relevance Threshold Calibration on Unseen Dev Set.

Directive from Client:
- Do NOT calibrate on Golden, v1, v2, or v3 evaluation suites.
- Calibrate strictly on a separate held-out dev set (evaluation/dev_calibration_dataset.json).
- Freeze the selected refusal threshold and evaluate all benchmark suites with it.
"""

import json
import logging
import statistics
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from rich.console import Console
from rich.table import Table

from src.config import settings
from src.embeddings import LocalFastEmbedProvider
from src.vector_store import FAISSVectorStore

console = Console()
logger = logging.getLogger("calibrate_local_threshold")

INDEX_DIR = settings.BASE_DIR / "index_cache" / "local_bge_small"
DEV_DATASET_PATH = settings.BASE_DIR / "evaluation" / "dev_calibration_dataset.json"


def calibrate_threshold() -> float:
    if not INDEX_DIR.exists():
        raise FileNotFoundError(f"Index directory {INDEX_DIR} does not exist. Run scripts/build_local_index.py first.")

    with open(DEV_DATASET_PATH, "r", encoding="utf-8") as f:
        dev_items = json.load(f)

    provider = LocalFastEmbedProvider()
    store = FAISSVectorStore(dimension=provider.dimension)
    store.load_local(INDEX_DIR, expected_model_id=f"fastembed:{provider.model_name}@{provider.revision}")

    in_domain_scores = []
    out_domain_scores = []

    for item in dev_items:
        q = item["query"]
        is_in = item["is_in_domain"]
        q_emb = provider.embed_text(q)
        matches = store.similarity_search(query_embedding=q_emb, top_k=1, query_text=None)
        if matches:
            top_score = matches[0][1]
            if is_in:
                in_domain_scores.append(top_score)
            else:
                out_domain_scores.append(top_score)

    table = Table(title="📊 Empirical Refusal Threshold Calibration (Local Dev Set)", show_header=True)
    table.add_column("Query Class", style="bold cyan")
    table.add_column("Count", justify="center")
    table.add_column("Min Score", justify="center")
    table.add_column("Median (p50)", justify="center")
    table.add_column("Max Score", justify="center")
    table.add_column("Mean Score", justify="center")

    table.add_row(
        f"In-Domain Technical ({len(in_domain_scores)} queries: 10 alert + 10 symptom)",
        str(len(in_domain_scores)),
        f"{min(in_domain_scores):.4f}",
        f"{statistics.median(in_domain_scores):.4f}",
        f"{max(in_domain_scores):.4f}",
        f"{statistics.mean(in_domain_scores):.4f}",
    )
    table.add_row(
        f"Out-of-Domain & Near-Domain ({len(out_domain_scores)} queries: 5 off-topic + 10 near-domain)",
        str(len(out_domain_scores)),
        f"{min(out_domain_scores):.4f}",
        f"{statistics.median(out_domain_scores):.4f}",
        f"{max(out_domain_scores):.4f}",
        f"{statistics.mean(out_domain_scores):.4f}",
    )

    console.print()
    console.print(table)

    max_out = max(out_domain_scores)
    min_in = min(in_domain_scores)

    # Pick calibrated threshold safely above maximum out-of-domain distractor
    # Margin of +0.02 above max out-of-domain score to achieve full refusal on dev calibration sample
    calibrated_threshold = round(max_out + 0.02, 2)
    console.print(f"\n[bold green]Maximum Out-of-Domain Score:[/bold green] {max_out:.4f}")
    console.print(f"[bold green]Minimum In-Domain Score:[/bold green] {min_in:.4f}")
    console.print(f"[bold magenta]Recommended Frozen Refusal Threshold:[/bold magenta] [bold yellow]{calibrated_threshold:.2f}[/bold yellow]\n")

    report = {
        "dev_dataset": str(DEV_DATASET_PATH.name),
        "total_queries": len(dev_items),
        "in_domain_scores": {
            "min": round(min(in_domain_scores), 4),
            "median": round(statistics.median(in_domain_scores), 4),
            "max": round(max(in_domain_scores), 4),
            "mean": round(statistics.mean(in_domain_scores), 4),
        },
        "out_of_domain_scores": {
            "min": round(min(out_domain_scores), 4),
            "median": round(statistics.median(out_domain_scores), 4),
            "max": round(max(out_domain_scores), 4),
            "mean": round(statistics.mean(out_domain_scores), 4),
        },
        "frozen_refusal_threshold": calibrated_threshold,
    }

    report_path = settings.BASE_DIR / "evaluation" / "dev_calibration_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return calibrated_threshold


if __name__ == "__main__":
    calibrate_threshold()

