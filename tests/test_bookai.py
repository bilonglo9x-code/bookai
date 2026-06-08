"""Tests for BookAI module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from bookai.analyzer import _mock_analyze, analyze_chunks
from bookai.chunker import _split_chapters, _split_sentences, chunk_markdown
from bookai.converter import convert_file, convert_text
from bookai.models import (
    AnalyzedChunk,
    BookMetadata,
    BookResult,
    Chunk,
    ChunkLabel,
    SourceFormat,
)

# --- Model tests ---


class TestModels:
    def test_chunk_auto_id(self):
        chunk = Chunk(text="Hello world test")
        assert chunk.chunk_id != ""
        assert len(chunk.chunk_id) == 12

    def test_chunk_token_count(self):
        chunk = Chunk(text="one two three four five")
        assert chunk.token_count == 5

    def test_book_result_get_top_content(self):
        chunks = [
            AnalyzedChunk(chunk=Chunk(text="low"), viral_score=2.0),
            AnalyzedChunk(chunk=Chunk(text="high"), viral_score=9.0),
            AnalyzedChunk(chunk=Chunk(text="mid"), viral_score=5.0),
        ]
        result = BookResult(
            metadata=BookMetadata(title="Test"),
            analyzed=chunks,
        )
        top = result.get_top_content(2)
        assert len(top) == 2
        assert top[0].viral_score == 9.0
        assert top[1].viral_score == 5.0

    def test_book_result_get_by_label(self):
        chunks = [
            AnalyzedChunk(chunk=Chunk(text="a"), labels=[ChunkLabel.QUOTE]),
            AnalyzedChunk(chunk=Chunk(text="b"), labels=[ChunkLabel.TIP]),
            AnalyzedChunk(chunk=Chunk(text="c"), labels=[ChunkLabel.QUOTE, ChunkLabel.HOOK]),
        ]
        result = BookResult(metadata=BookMetadata(title="Test"), analyzed=chunks)
        quotes = result.get_by_label(ChunkLabel.QUOTE)
        assert len(quotes) == 2


# --- Converter tests ---


class TestConverter:
    def test_convert_text_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("# Chapter 1\n\nHello world.\n\n# Chapter 2\n\nGoodbye world.")
            f.flush()

            metadata, markdown = convert_text(f.name)
            assert metadata.title == Path(f.name).stem
            assert metadata.source_format == SourceFormat.TEXT
            assert "Hello world" in markdown
            assert "Goodbye world" in markdown

    def test_convert_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            convert_file("/nonexistent/file.epub")

    def test_convert_file_unsupported_format(self):
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            f.write(b"test")
            f.flush()
            with pytest.raises(ValueError, match="Unsupported format"):
                convert_file(f.name)

    def test_convert_markdown_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Test Book\n\nSome content here.")
            f.flush()

            metadata, markdown = convert_file(f.name)
            assert metadata.source_format == SourceFormat.TEXT
            assert "Some content here" in markdown


# --- Chunker tests ---


class TestChunker:
    def test_chunk_simple_text(self):
        md = "# Chapter 1\n\nFirst paragraph.\n\nSecond paragraph."
        chunks = chunk_markdown(md, book_title="Test", max_tokens=100)
        assert len(chunks) >= 1
        assert chunks[0].book_title == "Test"

    def test_chunk_respects_max_tokens(self):
        # Create a long text
        long_text = "Word " * 1000
        md = f"# Chapter\n\n{long_text}"
        chunks = chunk_markdown(md, max_tokens=100)
        for chunk in chunks:
            # Allow some flexibility due to merging
            assert chunk.token_count <= 200  # 2x max_tokens as upper bound

    def test_chunk_multiple_chapters(self):
        md = "# Chapter 1\n\nContent one.\n\n---\n\n# Chapter 2\n\nContent two."
        chunks = chunk_markdown(md, max_tokens=100)
        chapters = set(c.chapter for c in chunks)
        assert len(chapters) >= 2

    def test_split_chapters(self):
        md = "# First\n\nContent 1.\n\n---\n\n# Second\n\nContent 2."
        chapters = _split_chapters(md)
        assert len(chapters) == 2
        assert chapters[0][0] == "First"
        assert chapters[1][0] == "Second"

    def test_split_sentences_vietnamese(self):
        text = "Câu một. Câu hai! Câu ba? Câu bốn."
        sentences = _split_sentences(text)
        assert len(sentences) == 4

    def test_chunk_empty_text(self):
        chunks = chunk_markdown("", book_title="Empty")
        assert chunks == []

    def test_chunk_metadata_populated(self):
        md = "# My Chapter\n\nSome text content here with enough words to form a chunk."
        chunks = chunk_markdown(md, book_title="My Book", min_tokens=5)
        assert chunks[0].chapter == 1
        assert chunks[0].chapter_title == "My Chapter"
        assert chunks[0].book_title == "My Book"
        assert chunks[0].position == 1


# --- Analyzer tests ---


class TestAnalyzer:
    def test_mock_analyze_quote(self):
        chunk = Chunk(text='Anh ấy từng nói rằng "cuộc đời rất ngắn"')
        result = _mock_analyze(chunk)
        assert ChunkLabel.QUOTE in result.labels
        assert result.viral_score > 3.0

    def test_mock_analyze_tip(self):
        chunk = Chunk(text="10 nguyên tắc sống để thành công trong cuộc sống")
        result = _mock_analyze(chunk)
        assert ChunkLabel.TIP in result.labels

    def test_mock_analyze_hook(self):
        chunk = Chunk(text="Bạn có biết sự thật ít ai biết này không?")
        result = _mock_analyze(chunk)
        assert ChunkLabel.HOOK in result.labels
        assert result.viral_score >= 5.0

    def test_mock_analyze_story(self):
        chunk = Chunk(text="Câu chuyện kể rằng ngày xưa có một vị vua")
        result = _mock_analyze(chunk)
        assert ChunkLabel.STORY in result.labels

    def test_analyze_chunks_mock_provider(self):
        chunks = [
            Chunk(text="Bài học số 1: luôn trung thực"),
            Chunk(text='Người ta nói rằng "thời gian là vàng"'),
            Chunk(text="Bạn có biết bí mật này không?"),
        ]
        results = analyze_chunks(chunks, provider="mock")
        assert len(results) == 3
        assert all(isinstance(r, AnalyzedChunk) for r in results)
        assert all(r.viral_score > 0 for r in results)

    def test_analyze_no_api_key_raises(self):
        import os

        # Ensure no API key is set
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            chunks = [Chunk(text="test")]
            with pytest.raises(ValueError, match="No API key"):
                analyze_chunks(chunks, provider="openai")
        finally:
            if old_key:
                os.environ["OPENAI_API_KEY"] = old_key


# --- Integration test ---


class TestIntegration:
    def test_full_pipeline_text_file(self):
        """Test the complete pipeline: convert → chunk → analyze."""
        content = """# Chương 1: Nhìn thấu lòng người

Đàn ông sợ ba cái lắc đầu, đàn bà sợ bước trên quá dốc.
Muốn biết một người đàn ông ra sao, hãy nhìn vào đôi dày anh ta đi.

Nguyên tắc số 1: Đừng bao giờ tin hoàn toàn vào lời nói.
Hãy quan sát hành động của họ trong ba tháng.

# Chương 2: Quy tắc xử thế

Có một câu chuyện kể rằng ngày xưa có một vị vua rất thông minh.
Ông nói rằng "kẻ thù nguy hiểm nhất là kẻ đội lốt bạn bè".

Bạn có biết sự thật ít ai biết về tâm lý con người?
Khi ai đó cười với bạn nhưng mắt không cười, đó là dấu hiệu nguy hiểm.
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            f.flush()

            # Convert
            metadata, markdown = convert_file(f.name)
            assert "Nhìn thấu lòng người" in markdown

            # Chunk
            chunks = chunk_markdown(markdown, book_title=metadata.title, min_tokens=10)
            assert len(chunks) >= 2

            # Analyze
            analyzed = analyze_chunks(chunks, provider="mock")
            assert len(analyzed) == len(chunks)

            # Build result
            result = BookResult(
                metadata=metadata,
                chunks=chunks,
                analyzed=analyzed,
                top_quotes=[a for a in analyzed if ChunkLabel.QUOTE in a.labels],
                top_hooks=[a for a in analyzed if ChunkLabel.HOOK in a.labels],
            )

            # Verify
            top = result.get_top_content(3)
            assert len(top) <= 3
            assert top[0].viral_score >= top[-1].viral_score
