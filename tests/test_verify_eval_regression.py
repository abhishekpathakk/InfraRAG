"""Unit tests for verify_eval_regression script and tolerance policies."""

import json
from pathlib import Path

from scripts.verify_eval_regression import verify_report


def _create_mock_report(overrides: dict | None = None) -> dict:
    base_report = {
        "golden_benchmark": {
            "top1_hit_rate_pct": 80.0,
            "top5_hit_rate_pct": 90.0,
            "mrr": 0.833,
            "out_domain_refusal_pct": 100.0,
        },
        "held_out_validation": {
            "top1_hit_rate_pct": 70.0,
            "top5_hit_rate_pct": 80.0,
            "mrr": 0.742,
            "out_domain_refusal_pct": 100.0,
        },
        "new_blind_held_out_v2": {
            "top1_hit_rate_pct": 50.0,
            "top5_hit_rate_pct": 50.0,
            "mrr": 0.500,
            "out_domain_refusal_pct": 100.0,
        },
        "new_blind_held_out_v3": {
            "top1_hit_rate_pct": 40.0,
            "top5_hit_rate_pct": 40.0,
            "mrr": 0.400,
            "out_domain_refusal_pct": 100.0,
        },
    }
    if overrides:
        for suite, metrics in overrides.items():
            base_report[suite].update(metrics)
    return base_report


def test_verify_report_pass(tmp_path: Path):
    report_file = tmp_path / "eval_report.json"
    report_file.write_text(json.dumps(_create_mock_report()), encoding="utf-8")

    failures = verify_report(report_file, margin=0.0)
    assert not failures


def test_verify_report_missing_file(tmp_path: Path):
    missing_file = tmp_path / "non_existent.json"
    failures = verify_report(missing_file)
    assert len(failures) == 1
    assert "not found" in failures[0]


def test_verify_report_malformed_json(tmp_path: Path):
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("{invalid json", encoding="utf-8")
    failures = verify_report(corrupt_file)
    assert len(failures) == 1
    assert "Failed to read evaluation report JSON" in failures[0]


def test_verify_report_fails_on_single_question_regression_at_zero_margin(tmp_path: Path):
    # On N=20 suite, a single question loss drops 80% to 75%
    regressed_report = _create_mock_report({"golden_benchmark": {"top1_hit_rate_pct": 75.0}})
    report_file = tmp_path / "eval_report.json"
    report_file.write_text(json.dumps(regressed_report), encoding="utf-8")

    failures = verify_report(report_file, margin=0.0)
    assert len(failures) == 1
    assert "Golden Benchmark Top-1 hit rate 75.0% < effective threshold 80.0%" in failures[0]


def test_verify_report_tolerates_margin_when_configured(tmp_path: Path):
    # Same single question loss (75.0% vs 80.0% base)
    regressed_report = _create_mock_report({"golden_benchmark": {"top1_hit_rate_pct": 75.0}})
    report_file = tmp_path / "eval_report.json"
    report_file.write_text(json.dumps(regressed_report), encoding="utf-8")

    # With margin=5.0, effective threshold becomes 75.0% and passes
    failures = verify_report(report_file, margin=5.0)
    assert not failures
