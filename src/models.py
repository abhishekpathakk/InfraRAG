"""
Data models for InfraRAG.
Uses Pydantic v2 for strict validation and serialization.
"""

from typing import Any
from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """Represents a discrete text chunk from a runbook."""
    chunk_id: str = Field(..., description="Unique deterministic chunk ID (e.g., file-chunk-0)")
    source_file: str = Field(..., description="Name of the source runbook file (e.g., kubernetes_oom_killed.md)")
    section_title: str = Field(default="General", description="Markdown header under which this chunk appears")
    content: str = Field(..., description="The textual chunk content")
    token_count: int = Field(default=0, description="Approximate token count of the chunk")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional custom metadata")


class Citation(BaseModel):
    """Source attribution for a generated answer."""
    source_file: str
    section_title: str
    chunk_id: str
    relevance_score: float = Field(default=0.0, description="Cosine similarity score (0.0 - 1.0)")


class RAGResponse(BaseModel):
    """End-to-end response returned to the user or API client."""
    query: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: str = Field(default="high", description="high, low, or ungrounded")
    retrieved_chunks: list[DocumentChunk] = Field(default_factory=list)
    latency_ms: float = Field(default=0.0, description="End-to-end processing latency in milliseconds")
    retrieval_latency_ms: float = Field(default=0.0)
    generation_latency_ms: float = Field(default=0.0)
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    estimated_cost_usd: float = Field(default=0.0)
