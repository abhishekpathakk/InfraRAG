"""
Observability and Telemetry module for InfraRAG.

Provides:
- CloudWatch-ready Structured JSON Logging
- Query Trace IDs
- Latency, Token Usage, and Cost Profiling
- SRE Metric Summaries
"""

import json
import logging
import sys
import time
import uuid
from typing import Any

from src.models import RAGResponse


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects for AWS CloudWatch."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include custom extra attributes if passed
        for key in ["trace_id", "query", "latency_ms", "tokens", "cost_usd", "citations_count"]:
            if hasattr(record, key):
                log_obj[key] = getattr(record, key)

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def configure_structured_logging(level: int = logging.INFO) -> logging.Logger:
    """Configures root logger with CloudWatch-compliant JSON output."""
    logger = logging.getLogger("infrarag")
    logger.setLevel(level)

    # Avoid duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)

    return logger


logger = configure_structured_logging()


def log_query_telemetry(response: RAGResponse, trace_id: str | None = None) -> None:
    """Emits structured audit log for query answering."""
    tid = trace_id or str(uuid.uuid4())
    logger.info(
        "RAG Query Executed",
        extra={
            "trace_id": tid,
            "query": response.query,
            "latency_ms": response.latency_ms,
            "retrieval_latency_ms": response.retrieval_latency_ms,
            "generation_latency_ms": response.generation_latency_ms,
            "tokens": {
                "input": response.input_tokens,
                "output": response.output_tokens,
                "total": response.input_tokens + response.output_tokens,
            },
            "cost_usd": response.estimated_cost_usd,
            "citations_count": len(response.citations),
            "confidence": response.confidence,
        },
    )
