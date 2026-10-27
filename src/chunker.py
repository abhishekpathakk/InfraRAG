"""
Document Chunker for InfraRAG.

Explaining Chunk Size and Overlap for DevOps/SRE:
------------------------------------------------
1. Chunk Size (e.g., 500 tokens / ~350-400 words):
   - In DevOps runbooks, troubleshooting steps must be kept together. If a chunk is too small
     (e.g., 50 words), the command (`kubectl describe pod`) gets separated from its explanation
     ("Exit code 137 indicates OOMKilled").
   - If a chunk is too large (e.g., 3000 words), the embedding vector averages out multiple
     different topics, diluting search accuracy and wasting LLM context window tokens.
2. Chunk Overlap (e.g., 100 tokens / ~70 words):
   - Overlap acts as a sliding buffer across chunk boundaries. It guarantees that multi-line
     YAML snippets or consecutive shell commands that span boundary lines are never split
     in half without context in at least one chunk.
"""

import re
from pathlib import Path
from src.models import DocumentChunk


class MarkdownChunker:
    """
    Sliding-window chunker with Markdown header awareness.
    Splits documents into overlapping chunks while tagging each chunk
    with its containing Markdown section header.
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be strictly less than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def approximate_token_count(self, text: str) -> int:
        """Rough token count approximation (1 token ≈ 4 characters or ~0.75 words)."""
        words = text.split()
        return max(1, int(len(words) * 1.3))

    def chunk_markdown_file(
        self,
        file_path: Path | str,
        source: str | None = None,
        doc_type: str | None = None,
    ) -> list[DocumentChunk]:
        """Reads a Markdown file and produces chunks with section and source metadata."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Runbook file not found: {file_path}")

        path_str = str(path)
        if doc_type is None:
            doc_type = "public" if "public" in path_str else "internal"

        if source is None:
            if "kubernetes" in path_str:
                source = "kubernetes"
            elif "istio" in path_str:
                source = "istio"
            elif "gitlab" in path_str:
                source = "gitlab"
            else:
                source = "internal"

        content = path.read_text(encoding="utf-8")
        return self.chunk_text(
            content=content,
            source_file=path.name,
            source=source,
            path=path_str,
            doc_type=doc_type,
        )

    def chunk_text(
        self,
        content: str,
        source_file: str,
        source: str = "internal",
        path: str = "",
        doc_type: str = "internal",
    ) -> list[DocumentChunk]:
        """
        Splits text content into overlapping chunks tagged with Markdown heading hierarchy.
        Stores metadata: source, path, section, type.
        """
        # Split into sections based on markdown headers (# to ####)
        section_pattern = re.compile(r"^(#{1,4}\s+.+)$", re.MULTILINE)
        splits = section_pattern.split(content)

        chunks: list[DocumentChunk] = []
        current_section = "General Overview"
        chunk_idx = 0

        idx = 0
        while idx < len(splits):
            part = splits[idx].strip()
            if not part:
                idx += 1
                continue

            if part.startswith("#"):
                current_section = part.lstrip("#").strip()
                idx += 1
                continue

            words = part.split()
            if not words:
                idx += 1
                continue

            step = max(1, self.chunk_size - self.chunk_overlap)
            start_word = 0

            while start_word < len(words):
                end_word = min(start_word + self.chunk_size, len(words))
                chunk_words = words[start_word:end_word]
                chunk_text = " ".join(chunk_words)

                # Prepend the section title to the chunk text so embedding captures the header
                enriched_text = f"[{current_section}]\n{chunk_text}"
                approx_tokens = self.approximate_token_count(enriched_text)

                chunk = DocumentChunk(
                    chunk_id=f"{source_file}-c{chunk_idx}",
                    source_file=source_file,
                    section_title=current_section,
                    content=enriched_text,
                    source=source,
                    path=path,
                    type=doc_type,
                    token_count=approx_tokens,
                    metadata={
                        "source": source,
                        "path": path,
                        "section": current_section,
                        "type": doc_type,
                        "word_count": len(chunk_words),
                        "start_word_index": start_word,
                        "end_word_index": end_word,
                    },
                )
                chunks.append(chunk)
                chunk_idx += 1

                if end_word >= len(words):
                    break
                start_word += step

            idx += 1

        return chunks
