"""Unit tests for local vs container parity script."""

from scripts.test_parity import run_local_benchmark, TEST_QUESTION


def test_run_local_benchmark_returns_valid_citations():
    res = run_local_benchmark(TEST_QUESTION)
    assert res["model_name"] == "BAAI/bge-small-en-v1.5"
    assert res["dimension"] == 384
    assert res["onnx_sha256"] == "51f1bd0addd6e859e42c2c8021a5e5461385bb676a649f4b269aa445449f2431"
    assert len(res["retrieved"]) >= 1
    assert res["retrieval_latency_ms"] < 2500.0
    # Top chunk should be kubernetes_crashloopbackoff.md
    assert res["retrieved"][0]["source_file"] == "kubernetes_crashloopbackoff.md"

