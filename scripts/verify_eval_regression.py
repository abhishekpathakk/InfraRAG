#!/usr/bin/env python3
"""
Verify Evaluation Report against Baseline Tolerances.

Prevents silent regressions in mock baseline retrieval metrics:
- Golden Benchmark: Top-1 >= 80.0%, Top-5 >= 90.0%, MRR >= 0.800
- Tagged Held-Out v1: Top-1 >= 70.0%, Top-5 >= 80.0%, MRR >= 0.700
- Blind Held-Out v2: Top-1 >= 50.0%, Top-5 >= 50.0%, MRR >= 0.450
- Blind Held-Out v3: Top-1 >= 40.0%, Top-5 >= 40.0%, MRR >= 0.350
- Out-of-Domain Refusal: 100.0% across all suites
"""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
REPORT_PATH = ROOT_DIR / "evaluation" / "eval_report.json"

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


def main() -> int:
    if not REPORT_PATH.exists():
        print(f"❌ Error: Evaluation report not found at {REPORT_PATH}")
        return 1

    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        report = json.load(f)

    failures = []
    print("🔍 Auditing evaluation report against regression tolerances...")

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

        print(f"\n📊 Suite: {name}")
        print(f"  • Top-1 Hit-Rate: {top1:.1f}% (min: {bounds['min_top1']}%)")
        print(f"  • Top-5 Hit-Rate: {top5:.1f}% (min: {bounds['min_top5']}%)")
        print(f"  • MRR:            {mrr:.3f} (min: {bounds['min_mrr']:.3f})")
        print(f"  • Refusal Rate:   {refusal:.1f}% (min: {bounds['min_refusal']}%)")

        if top1 < bounds["min_top1"]:
            failures.append(f"{name} Top-1 hit rate {top1:.1f}% < minimum tolerance {bounds['min_top1']}%")
        if top5 < bounds["min_top5"]:
            failures.append(f"{name} Top-5 hit rate {top5:.1f}% < minimum tolerance {bounds['min_top5']}%")
        if mrr < bounds["min_mrr"]:
            failures.append(f"{name} MRR {mrr:.3f} < minimum tolerance {bounds['min_mrr']:.3f}")
        if refusal < bounds["min_refusal"]:
            failures.append(f"{name} Out-of-domain refusal {refusal:.1f}% < minimum tolerance {bounds['min_refusal']}%")

    if failures:
        print("\n❌ REGRESSION GATE FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("\n✅ ALL EVALUATION SUITES PASSED REGRESSION TOLERANCE CHECK!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
