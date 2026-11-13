#!/usr/bin/env python3
"""
Verify Evaluation Report against Baseline Tolerances.

This script gates CI and deployment by comparing retrieval metrics in
`evaluation/eval_report.json` against frozen baseline performance standards:
- Golden Benchmark:       Top-1 >= 80.0%, Top-5 >= 90.0%, MRR >= 0.800
- Tagged Held-Out v1:     Top-1 >= 70.0%, Top-5 >= 80.0%, MRR >= 0.700
- Blind Held-Out v2:      Top-1 >= 50.0%, Top-5 >= 50.0%, MRR >= 0.450
- Blind Held-Out v3:      Top-1 >= 40.0%, Top-5 >= 40.0%, MRR >= 0.350
- Out-of-Domain Refusal:  100.0% across all suites

Tolerance Policy & Statistical Sensitivity:
-------------------------------------------
1. Zero-Margin Default (--margin 0.0%):
   The evaluation suite runs with `MockEmbeddingProvider`, which is 100% deterministic.
   Because there is zero stochastic sampling or LLM temperature variance, any drop in
   hit-rate or MRR reflects an unintended code or indexing regression rather than random noise.
2. Sensitivity on Finite Suites (N=20):
   Each question in an N=20 evaluation set represents exactly 5.0% (1/20 = 5.0%).
   Consequently, under `--margin 0.0%`, a single failed question drops the metric below
   the baseline and fails the CI gate.
3. Configurable Margin:
   For non-deterministic or neural embeddings with variance, callers can provide
   an explicit tolerance margin via `--margin M` (e.g. `--margin 5.0` to tolerate
   a 1-question fluctuation).
"""

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_REPORT_PATH = ROOT_DIR / "evaluation" / "eval_report.json"

TOLERANCE_THRESHOLDS = {
    "golden_benchmark": {
        "name": "Golden Benchmark",
        "min_top1": 80.0,
        "min_top5": 90.0,
        "min_mrr": 0.800,
        "min_refusal": 100.0,
    },
    "held_out_validation": {
        "name": "Tagged Held-Out Baseline v1",
        "min_top1": 70.0,
        "min_top5": 80.0,
        "min_mrr": 0.700,
        "min_refusal": 100.0,
    },
    "new_blind_held_out_v2": {
        "name": "Blind Held-Out Suite v2",
        "min_top1": 50.0,
        "min_top5": 50.0,
        "min_mrr": 0.450,
        "min_refusal": 100.0,
    },
    "new_blind_held_out_v3": {
        "name": "Blind Held-Out Suite v3",
        "min_top1": 40.0,
        "min_top5": 40.0,
        "min_mrr": 0.350,
        "min_refusal": 100.0,
    },
}


def verify_report(report_path: Path, margin: float = 0.0) -> list[str]:
    """Verify evaluation report metrics against baseline thresholds with given margin."""
    if not report_path.exists():
        return [f"Evaluation report not found at {report_path}"]

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
    except Exception as exc:
        return [f"Failed to read evaluation report JSON: {exc}"]

    failures: list[str] = []
    print("🔍 Auditing evaluation report against regression tolerances...")
    print(
        f"📋 Tolerance Policy: {'Strict zero-margin' if margin == 0.0 else f'Margin ±{margin:.1f}%'} "
        f"(N=20 suites: 1 question = 5.0% resolution)"
    )

    for key, bounds in TOLERANCE_THRESHOLDS.items():
        suite = report.get(key)
        if not suite:
            failures.append(f"Missing required evaluation suite '{key}' in report")
            continue

        name = bounds["name"]
        top1 = suite.get("top1_hit_rate_pct", 0.0)
        top5 = suite.get("top5_hit_rate_pct", 0.0)
        mrr = suite.get("mrr", 0.0)
        refusal = suite.get("out_domain_refusal_pct", 0.0)

        effective_top1 = max(0.0, bounds["min_top1"] - margin)
        effective_top5 = max(0.0, bounds["min_top5"] - margin)
        effective_mrr = max(0.0, bounds["min_mrr"] - (margin / 100.0))
        effective_refusal = max(0.0, bounds["min_refusal"] - margin)

        print(f"\n📊 Suite: {name}")
        print(f"  • Top-1 Hit-Rate: {top1:.1f}% (effective min: {effective_top1:.1f}%, base: {bounds['min_top1']}%)")
        print(f"  • Top-5 Hit-Rate: {top5:.1f}% (effective min: {effective_top5:.1f}%, base: {bounds['min_top5']}%)")
        print(f"  • MRR:            {mrr:.3f} (effective min: {effective_mrr:.3f}, base: {bounds['min_mrr']:.3f})")
        print(f"  • Refusal Rate:   {refusal:.1f}% (effective min: {effective_refusal:.1f}%, base: {bounds['min_refusal']}%)")

        if top1 < effective_top1:
            failures.append(f"{name} Top-1 hit rate {top1:.1f}% < effective threshold {effective_top1:.1f}%")
        if top5 < effective_top5:
            failures.append(f"{name} Top-5 hit rate {top5:.1f}% < effective threshold {effective_top5:.1f}%")
        if mrr < effective_mrr:
            failures.append(f"{name} MRR {mrr:.3f} < effective threshold {effective_mrr:.3f}")
        if refusal < effective_refusal:
            failures.append(f"{name} Out-of-domain refusal {refusal:.1f}% < effective threshold {effective_refusal:.1f}%")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify Evaluation Report against Baseline Tolerances.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path to eval_report.json (default: evaluation/eval_report.json)",
    )
    parser.add_argument(
        "--margin",
        type=float,
        default=0.0,
        help="Allowed percentage drop margin below baseline thresholds (default: 0.0 for deterministic mock runs)",
    )
    args = parser.parse_args()

    failures = verify_report(args.report_path, margin=args.margin)
    if failures:
        print("\n❌ REGRESSION GATE FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("\n✅ ALL EVALUATION SUITES PASSED REGRESSION TOLERANCE CHECK!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
