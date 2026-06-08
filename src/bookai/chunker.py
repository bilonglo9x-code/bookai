"""Semantic chunking for book content."""

from __future__ import annotations

import re

from .models import Chunk


def chunk_markdown(
    markdown: str,
    book_title: str = "",
    max_tokens: int = 500,
    min_tokens: int = 50,
) -> list[Chunk]:
    """Split markdown text into semantic chunks.

    Strategy:
    1. Split by chapter headings (# or ---)
    2. Within chapters, split by paragraphs
    3. Merge small paragraphs, split large ones

    Args:
        markdown: Full markdown text of the book.
        book_title: Title for metadata.
        max_tokens: Maximum words per chunk.
        min_tokens: Minimum words per chunk (merge if smaller).

    Returns:
        List of Chunk objects with metadata.
    """
    # Split into chapters first
    chapters = _split_chapters(markdown)

    chunks: list[Chunk] = []
    position = 0

    for chapter_idx, (chapter_title, chapter_text) in enumerate(chapters, 1):
        # Split chapter into paragraphs
        paragraphs = _split_paragraphs(chapter_text)

        # Merge small paragraphs, split large ones
        merged = _merge_and_split(paragraphs, max_tokens=max_tokens, min_tokens=min_tokens)

        for para in merged:
            if not para.strip():
                continue
            position += 1
            chunk = Chunk(
                book_title=book_title,
                chapter=chapter_idx,
                chapter_title=chapter_title,
                position=position,
                text=para.strip(),
            )
            chunks.append(chunk)

    return chunks


def _split_chapters(markdown: str) -> list[tuple[str, str]]:
    """Split markdown into chapters by headings or separators.

    Returns list of (chapter_title, chapter_content) tuples.
    """
    # Split by H1 headings or --- separators
    parts = re.split(r"\n(?=# )|(?:\n---\n)", markdown)

    chapters: list[tuple[str, str]] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Extract title from first heading if present
        title_match = re.match(r"^#\s+(.+?)$", part, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
            content = part[title_match.end() :].strip()
        else:
            title = f"Section {len(chapters) + 1}"
            content = part

        if content:
            chapters.append((title, content))

    # If no chapters found, treat entire text as one chapter
    if not chapters and markdown.strip():
        chapters = [("Content", markdown.strip())]

    return chapters


def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs (double newline or heading boundaries)."""
    # Split on double newlines or sub-headings
    parts = re.split(r"\n\n+|\n(?=##)", text)
    return [p.strip() for p in parts if p.strip()]


def _merge_and_split(
    paragraphs: list[str],
    max_tokens: int = 500,
    min_tokens: int = 50,
) -> list[str]:
    """Merge small paragraphs and split large ones.

    Ensures each output chunk is between min_tokens and max_tokens words.
    """
    result: list[str] = []
    buffer: list[str] = []
    buffer_tokens = 0

    for para in paragraphs:
        para_tokens = len(para.split())

        # If single paragraph exceeds max, split it by sentences
        if para_tokens > max_tokens:
            # Flush buffer first
            if buffer:
                result.append("\n\n".join(buffer))
                buffer = []
                buffer_tokens = 0

            # Split large paragraph into sentence groups
            sentences = _split_sentences(para)
            sent_buffer: list[str] = []
            sent_tokens = 0

            for sent in sentences:
                sent_len = len(sent.split())
                if sent_tokens + sent_len > max_tokens and sent_buffer:
                    result.append(" ".join(sent_buffer))
                    sent_buffer = []
                    sent_tokens = 0
                sent_buffer.append(sent)
                sent_tokens += sent_len

            if sent_buffer:
                result.append(" ".join(sent_buffer))
            continue

        # If adding this paragraph exceeds max, flush buffer
        if buffer_tokens + para_tokens > max_tokens and buffer:
            result.append("\n\n".join(buffer))
            buffer = []
            buffer_tokens = 0

        buffer.append(para)
        buffer_tokens += para_tokens

    # Flush remaining buffer
    if buffer:
        result.append("\n\n".join(buffer))

    # Filter out chunks below minimum (merge with neighbors)
    final: list[str] = []
    for chunk in result:
        if len(chunk.split()) < min_tokens and final:
            # Merge with previous chunk
            final[-1] = final[-1] + "\n\n" + chunk
        else:
            final.append(chunk)

    return final


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences (Vietnamese-aware)."""
    # Split on sentence-ending punctuation followed by space or newline
    sentences = re.split(r"(?<=[.!?。])\s+", text)
    result = [s.strip() for s in sentences if s.strip()]
    # If no split happened (no punctuation), fall back to splitting by word groups
    if len(result) <= 1 and len(text.split()) > 100:
        words = text.split()
        result = []
        for i in range(0, len(words), 100):
            result.append(" ".join(words[i : i + 100]))
    return result
