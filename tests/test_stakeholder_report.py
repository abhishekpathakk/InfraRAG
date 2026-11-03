"""
Unit tests for InfraRAG Automated Stakeholder Reporting and AWS SES Dispatcher.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.generate_stakeholder_report import (
    build_stakeholder_digest,
    dispatch_via_ses,
    parse_trivy_report,
    render_html_email,
    render_plain_text,
)


def test_build_stakeholder_digest_pass():
    retrieval = {
        "status": "PASS",
        "top1_pct": 68.0,
        "top1_ci": [54.0, 79.3],
        "top5_pct": 84.0,
        "mrr": 0.75,
        "refusal_pct": 100.0,
        "refusal_count": "15/15",
        "avg_latency_ms": 5.2,
    }
    coverage = {"coverage_pct": 88.5, "status": "PASS"}
    security = {
        "status": "PASS",
        "critical_count": 0,
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "secrets_found": 0,
        "advisories": [],
    }
    sbom = {"status": "PASS", "generated": True, "format": "CycloneDX JSON"}

    digest = build_stakeholder_digest(
        commit_sha="abcd123",
        retrieval=retrieval,
        coverage=coverage,
        security=security,
        sbom=sbom,
    )

    assert digest["overall_status"] == "PASS"
    assert "ALL SYSTEMS PASS" in digest["overall_badge"]
    assert len(digest["scorecard"]) == 8
    assert any("Retrieval Top-1" in row["category"] for row in digest["scorecard"])


def test_build_stakeholder_digest_attention_on_medium_cve():
    retrieval = {"status": "PASS", "top1_pct": 68.0, "refusal_pct": 100.0}
    coverage = {"coverage_pct": 85.0, "status": "PASS"}
    security = {
        "status": "ATTENTION",
        "critical_count": 0,
        "high_count": 0,
        "medium_count": 2,
        "low_count": 1,
        "advisories": [
            {
                "id": "CVE-2024-9999",
                "package": "onnxruntime",
                "severity": "MEDIUM",
                "title": "Buffer allocation edge case",
                "fixed_version": "1.21.0",
            }
        ],
    }
    sbom = {"status": "PASS", "generated": True}

    digest = build_stakeholder_digest(
        commit_sha="abcd123",
        retrieval=retrieval,
        coverage=coverage,
        security=security,
        sbom=sbom,
    )

    assert digest["overall_status"] == "ATTENTION"
    assert "REQUIRES ATTENTION" in digest["overall_badge"]
    assert any("CVE-2024-9999" in item for item in digest["attention_items"])


def test_build_stakeholder_digest_failing_on_critical_cve():
    retrieval = {"status": "PASS", "top1_pct": 68.0, "refusal_pct": 100.0}
    coverage = {"coverage_pct": 85.0, "status": "PASS"}
    security = {
        "status": "FAILING",
        "critical_count": 1,
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "advisories": [],
    }
    sbom = {"status": "PASS", "generated": True}

    digest = build_stakeholder_digest(
        commit_sha="abcd123",
        retrieval=retrieval,
        coverage=coverage,
        security=security,
        sbom=sbom,
    )

    assert digest["overall_status"] == "FAILING"
    assert "FAILING CHECKS" in digest["overall_badge"]


def test_render_templates():
    digest = {
        "commit_sha": "test-sha",
        "timestamp": "2026-11-03 12:00:00 UTC",
        "overall_status": "PASS",
        "overall_color": "#38A169",
        "overall_badge": "🟢 ALL SYSTEMS PASS",
        "scorecard": [
            {"category": "Retrieval Top-1", "value": "68.0%", "target": ">= 65%", "verdict": "PASS"}
        ],
        "attention_items": ["[🟢 PASS] Clean bill of health."],
    }

    html = render_html_email(digest)
    assert "<!DOCTYPE html>" in html
    assert "test-sha" in html
    assert "ALL SYSTEMS PASS" in html

    txt = render_plain_text(digest)
    assert "test-sha" in txt
    assert "Retrieval Top-1" in txt


def test_parse_trivy_report_empty(tmp_path: Path):
    res = parse_trivy_report(None)
    assert res["status"] == "PASS"
    assert res["critical_count"] == 0

    dummy_trivy = tmp_path / "trivy.json"
    dummy_trivy.write_text('{"Results": [{"Vulnerabilities": [{"VulnerabilityID": "CVE-1", "PkgName": "pkg", "Severity": "CRITICAL"}]}]}')
    parsed = parse_trivy_report(dummy_trivy)
    assert parsed["status"] == "FAILING"
    assert parsed["critical_count"] == 1


def test_dispatch_via_ses_mock():
    with patch("boto3.client") as mock_boto:
        mock_ses = MagicMock()
        mock_boto.return_value = mock_ses
        mock_ses.send_email.return_value = {"MessageId": "msg-12345"}

        success = dispatch_via_ses(
            html_content="<p>Test</p>",
            text_content="Test",
            sender="sender@example.com",
            recipients=["dest@example.com"],
        )

        assert success is True
        mock_ses.send_email.assert_called_once()
