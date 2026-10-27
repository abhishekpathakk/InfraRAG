"""Unit tests for Document Chunker."""

import pytest
from pathlib import Path
from src.chunker import MarkdownChunker
from src.models import DocumentChunk


@pytest.fixture
def chunker():
    return MarkdownChunker(chunk_size=50, chunk_overlap=10)


def test_chunker_initialization_invalid():
    with pytest.raises(ValueError):
        MarkdownChunker(chunk_size=100, chunk_overlap=100)
    with pytest.raises(ValueError):
        MarkdownChunker(chunk_size=50, chunk_overlap=80)


def test_chunk_text_sections(chunker):
    text = """# Header 1
This is the first paragraph under header one. It describes Kubernetes pod crashes.

## Subsection 1.1
This is a subsection with remediation steps for crashloop backoff. Run kubectl logs.
"""
    chunks = chunker.chunk_text(text, source_file="test_doc.md")
    assert len(chunks) >= 2
    assert all(isinstance(c, DocumentChunk) for c in chunks)
    assert chunks[0].source_file == "test_doc.md"
    assert "Header 1" in chunks[0].section_title or "Subsection" in chunks[0].section_title
    assert chunks[0].token_count > 0


def test_chunk_real_runbook(chunker):
    runbook_path = Path("data/runbooks/kubernetes_oom_killed.md")
    if runbook_path.exists():
        chunks = chunker.chunk_markdown_file(runbook_path)
        assert len(chunks) > 0
        assert chunks[0].source_file == "kubernetes_oom_killed.md"
        assert any("OOMKilled" in c.content for c in chunks)
