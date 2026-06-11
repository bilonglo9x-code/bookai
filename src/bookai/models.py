"""Data models for BookAI pipeline."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SourceFormat(str, Enum):
    """Supported input formats."""

    EPUB = "epub"
    PDF = "pdf"
    TEXT = "text"
    MARKDOWN = "markdown"
    IMAGE = "image"
    AUDIO = "audio"


class ChunkLabel(str, Enum):
    """Content labels for analyzed chunks."""

    QUOTE = "quote"
    SUMMARY = "summary"
    STORY = "story"
    EXAMPLE = "example"
    INSIGHT = "insight"
    HOOK = "hook"
    TIP = "tip"
    CONTROVERSIAL = "controversial"


class BookMetadata(BaseModel):
    """Metadata extracted from a book file."""

    title: str
    author: str = "Unknown"
    publisher: str = ""
    language: str = "vi"
    chapters: int = 0
    source_format: SourceFormat = SourceFormat.TEXT
    file_path: str = ""


class Chunk(BaseModel):
    """A semantic unit of text from a book."""

    chunk_id: str = Field(default_factory=lambda: "")
    book_title: str = ""
    chapter: int = 0
    chapter_title: str = ""
    position: int = 0
    text: str
    token_count: int = 0

    def model_post_init(self, _context: object) -> None:
        if not self.chunk_id:
            import hashlib

            self.chunk_id = hashlib.md5(self.text.encode()).hexdigest()[:12]
        if self.token_count == 0:
            self.token_count = len(self.text.split())


class AnalyzedChunk(BaseModel):
    """A chunk with AI-generated analysis."""

    chunk: Chunk
    labels: list[ChunkLabel] = Field(default_factory=list)
    viral_score: float = 0.0
    summary: str = ""
    reason: str = ""


class BookResult(BaseModel):
    """Complete result from processing a book."""

    metadata: BookMetadata
    markdown: str = ""
    chunks: list[Chunk] = Field(default_factory=list)
    analyzed: list[AnalyzedChunk] = Field(default_factory=list)
    top_quotes: list[AnalyzedChunk] = Field(default_factory=list)
    top_hooks: list[AnalyzedChunk] = Field(default_factory=list)
    chapter_summaries: list[str] = Field(default_factory=list)

    def get_top_content(self, n: int = 10) -> list[AnalyzedChunk]:
        """Return top N chunks by viral score."""
        return sorted(self.analyzed, key=lambda x: x.viral_score, reverse=True)[:n]

    def get_by_label(self, label: ChunkLabel) -> list[AnalyzedChunk]:
        """Filter analyzed chunks by label."""
        return [a for a in self.analyzed if label in a.labels]
