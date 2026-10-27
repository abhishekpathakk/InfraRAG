"""
Data models for InfraRAG.
Supports Pydantic v2 when available, with a standard-library dataclass fallback
for lightweight AWS Lambda execution environments.
"""

from typing import Any

try:
    from pydantic import BaseModel, Field

    class DocumentChunk(BaseModel):
        chunk_id: str
        source_file: str
        section_title: str = "General"
        content: str
        token_count: int = 0
        metadata: dict[str, Any] = Field(default_factory=dict)

    class Citation(BaseModel):
        source_file: str
        section_title: str
        chunk_id: str
        relevance_score: float = 0.0

    class RAGResponse(BaseModel):
        query: str
        answer: str
        citations: list[Citation] = Field(default_factory=list)
        confidence: str = "high"
        retrieved_chunks: list[DocumentChunk] = Field(default_factory=list)
        latency_ms: float = 0.0
        retrieval_latency_ms: float = 0.0
        generation_latency_ms: float = 0.0
        input_tokens: int = 0
        output_tokens: int = 0
        estimated_cost_usd: float = 0.0

except ImportError:
    import dataclasses

    @dataclasses.dataclass
    class DocumentChunk:
        chunk_id: str
        source_file: str
        content: str
        section_title: str = "General"
        token_count: int = 0
        metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

        def model_dump(self) -> dict[str, Any]:
            return dataclasses.asdict(self)

    @dataclasses.dataclass
    class Citation:
        source_file: str
        section_title: str
        chunk_id: str
        relevance_score: float = 0.0

        def model_dump(self) -> dict[str, Any]:
            return dataclasses.asdict(self)

    @dataclasses.dataclass
    class RAGResponse:
        query: str
        answer: str
        citations: list[Citation] = dataclasses.field(default_factory=list)
        confidence: str = "high"
        retrieved_chunks: list[DocumentChunk] = dataclasses.field(default_factory=list)
        latency_ms: float = 0.0
        retrieval_latency_ms: float = 0.0
        generation_latency_ms: float = 0.0
        input_tokens: int = 0
        output_tokens: int = 0
        estimated_cost_usd: float = 0.0

        def model_dump(self) -> dict[str, Any]:
            return dataclasses.asdict(self)
