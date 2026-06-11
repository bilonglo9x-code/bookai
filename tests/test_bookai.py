"""Tests for BookAI module."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from bookai.analyzer import _mock_analyze, analyze_chunks
from bookai.chunker import _split_chapters, _split_sentences, chunk_markdown
from bookai.content_studio import (
    ContentPack,
    ai_rewrite_radio_scripts,
    generate_all,
    generate_all_with_ai,
    generate_captions,
    generate_listicles,
    generate_quote_cards,
    generate_quote_images,
    generate_radio_scripts,
)
from bookai.converter import convert_file, convert_images_dir, convert_text
from bookai.models import (
    AnalyzedChunk,
    BookMetadata,
    BookResult,
    Chunk,
    ChunkLabel,
    SourceFormat,
)
from bookai.quote_renderer import render_quote_card, render_quote_cards_batch

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


# --- Content Studio tests ---


def _make_analyzed_chunks() -> tuple[list[AnalyzedChunk], BookMetadata]:
    """Helper to create test data for content studio."""
    metadata = BookMetadata(title="Nhìn Thấu Lòng Người", author="Tác giả mẫu")
    analyzed = [
        AnalyzedChunk(
            chunk=Chunk(text=(
                "Muốn biết một người đàn ông ra sao, hãy nhìn vào đôi giày anh ta đi. "
                "Đôi giày sạch sẽ cho thấy anh ta cẩn thận và chăm chút bản thân."
            )),
            labels=[ChunkLabel.QUOTE, ChunkLabel.INSIGHT],
            viral_score=9.0,
            summary="Đôi giày phản ánh tính cách con người.",
            reason="Curiosity cao, actionable.",
        ),
        AnalyzedChunk(
            chunk=Chunk(text=(
                "Có một câu chuyện kể rằng ngày xưa có một vị vua rất thông minh. "
                "Vua hỏi quần thần ai là kẻ nguy hiểm nhất. Mọi người đều chỉ ra ngoài, "
                "nhưng vua chỉ vào gương. Bài học: kẻ thù lớn nhất là chính bản thân ta."
            )),
            labels=[ChunkLabel.STORY, ChunkLabel.INSIGHT, ChunkLabel.HOOK],
            viral_score=8.5,
            summary="Câu chuyện vua và gương: kẻ thù lớn nhất là chính mình.",
            reason="Story mạnh, emotion tốt.",
        ),
        AnalyzedChunk(
            chunk=Chunk(text=(
                "Nguyên tắc 1: Đừng bao giờ tin hoàn toàn vào lời nói. "
                "Nguyên tắc 2: Quan sát hành động ít nhất 3 tháng. "
                "Nguyên tắc 3: Nhìn cách họ đối xử với người phục vụ."
            )),
            labels=[ChunkLabel.TIP, ChunkLabel.INSIGHT],
            viral_score=7.5,
            summary="3 nguyên tắc nhìn thấu lòng người.",
            reason="Actionable cao, liệt kê rõ ràng.",
        ),
        AnalyzedChunk(
            chunk=Chunk(text=(
                "Người thành công thường dậy sớm và đọc sách mỗi ngày. "
                "Đây là thói quen đơn giản nhưng ít người thực hiện được."
            )),
            labels=[ChunkLabel.TIP, ChunkLabel.CONTROVERSIAL],
            viral_score=6.0,
            summary="Thói quen dậy sớm và đọc sách.",
        ),
        AnalyzedChunk(
            chunk=Chunk(text=(
                "Bạn có biết sự thật ít ai biết về tâm lý con người? "
                "Khi ai đó cười với bạn nhưng mắt không cười, đó là dấu hiệu nguy hiểm."
            )),
            labels=[ChunkLabel.HOOK, ChunkLabel.CONTROVERSIAL],
            viral_score=8.0,
            summary="Dấu hiệu cười giả qua ánh mắt.",
        ),
    ]
    return analyzed, metadata


class TestContentStudio:
    def test_generate_radio_scripts(self):
        analyzed, metadata = _make_analyzed_chunks()
        scripts = generate_radio_scripts(analyzed, metadata, max_scripts=3, min_score=6.0)
        assert len(scripts) >= 1
        assert scripts[0].hook
        assert scripts[0].body
        assert scripts[0].cta
        assert "Nhìn Thấu Lòng Người" in scripts[0].cta
        assert scripts[0].estimated_seconds > 0
        assert len(scripts[0].hashtags) >= 3

    def test_generate_quote_cards(self):
        analyzed, metadata = _make_analyzed_chunks()
        cards = generate_quote_cards(analyzed, metadata, max_cards=5, min_score=5.0)
        assert len(cards) >= 1
        assert cards[0].quote_text
        assert cards[0].book_title == "Nhìn Thấu Lòng Người"
        assert cards[0].author == "Tác giả mẫu"
        assert len(cards[0].hashtags) >= 3

    def test_generate_listicles(self):
        analyzed, metadata = _make_analyzed_chunks()
        listicles = generate_listicles(
            analyzed, metadata, max_listicles=3, items_per_list=3, min_score=5.0,
        )
        assert len(listicles) >= 1
        assert len(listicles[0].items) >= 2
        assert "Nhìn Thấu Lòng Người" in listicles[0].title

    def test_generate_captions_tiktok(self):
        analyzed, metadata = _make_analyzed_chunks()
        captions = generate_captions(
            analyzed, metadata, max_captions=5, platform="tiktok", min_score=6.0,
        )
        assert len(captions) >= 1
        assert "giỏ hàng" in captions[0].text
        assert captions[0].platform == "tiktok"
        assert "#" in captions[0].text  # has hashtags

    def test_generate_captions_instagram(self):
        analyzed, metadata = _make_analyzed_chunks()
        captions = generate_captions(
            analyzed, metadata, max_captions=3, platform="instagram", min_score=6.0,
        )
        assert len(captions) >= 1
        assert "Save lại" in captions[0].text
        assert captions[0].platform == "instagram"

    def test_generate_all(self):
        analyzed, metadata = _make_analyzed_chunks()
        pack = generate_all(analyzed, metadata)
        assert isinstance(pack, ContentPack)
        assert pack.total_pieces > 0
        assert pack.book_title == "Nhìn Thấu Lòng Người"

    def test_content_pack_model_dump(self):
        analyzed, metadata = _make_analyzed_chunks()
        pack = generate_all(analyzed, metadata)
        data = pack.model_dump()
        assert "radio_scripts" in data
        assert "quote_cards" in data
        assert "listicles" in data
        assert "captions" in data
        assert data["total_pieces"] == pack.total_pieces

    def test_radio_script_full_script(self):
        analyzed, metadata = _make_analyzed_chunks()
        scripts = generate_radio_scripts(analyzed, metadata, max_scripts=1)
        if scripts:
            script = scripts[0]
            assert script.hook in script.full_script
            assert script.cta in script.full_script

    def test_empty_analyzed_returns_empty(self):
        metadata = BookMetadata(title="Empty Book")
        pack = generate_all([], metadata)
        assert pack.total_pieces == 0
        assert pack.radio_scripts == []
        assert pack.quote_cards == []

    def test_low_score_chunks_filtered(self):
        metadata = BookMetadata(title="Test")
        analyzed = [
            AnalyzedChunk(
                chunk=Chunk(text="Low quality content"),
                labels=[ChunkLabel.SUMMARY],
                viral_score=1.0,
            ),
        ]
        scripts = generate_radio_scripts(analyzed, metadata, min_score=6.0)
        assert scripts == []


# --- Quote Card Renderer tests ---


class TestQuoteRenderer:
    def test_render_single_quote_card(self):
        """Test rendering a single quote card PNG."""
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "test_quote.png"
            result = render_quote_card(
                quote_text="Hãy sống như thể ngày mai bạn sẽ chết.",
                book_title="Thức tỉnh mục đích sống",
                author="Eckhart Tolle",
                output_path=output_path,
                theme="dark",
            )
            assert result.exists()
            assert result.suffix == ".png"
            # Check file is not empty (PNG has header)
            assert result.stat().st_size > 1000

    def test_render_quote_card_light_theme(self):
        """Test light theme rendering."""
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "light.png"
            result = render_quote_card(
                quote_text="Mỗi khoảnh khắc đều là một cơ hội mới.",
                book_title="Sống Trọn Vẹn",
                author="Tác giả",
                output_path=output_path,
                theme="light",
            )
            assert result.exists()
            assert result.stat().st_size > 1000

    def test_render_quote_card_gradient_blue(self):
        """Test gradient_blue theme."""
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "blue.png"
            result = render_quote_card(
                quote_text="Tĩnh lặng không phải là vắng bóng tiếng ồn.",
                book_title="Sức mạnh của tĩnh lặng",
                author="Eckhart Tolle",
                output_path=output_path,
                theme="gradient_blue",
            )
            assert result.exists()

    def test_render_batch_quote_cards(self):
        """Test batch rendering multiple quote cards."""
        with tempfile.TemporaryDirectory() as tmp:
            quotes = [
                {"quote_text": "Quote one", "book_title": "Book A", "author": "Author"},
                {"quote_text": "Quote two", "book_title": "Book A", "author": "Author"},
                {"quote_text": "Quote three", "book_title": "Book A", "author": "Author"},
            ]
            paths = render_quote_cards_batch(quotes, output_dir=tmp, theme="dark")
            assert len(paths) == 3
            for p in paths:
                assert p.exists()
                assert p.suffix == ".png"

    def test_render_creates_output_dir(self):
        """Test that missing output directories are created."""
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "deep" / "nested" / "dir"
            output_path = nested / "quote.png"
            result = render_quote_card(
                quote_text="Test quote",
                book_title="Test",
                author="Author",
                output_path=output_path,
            )
            assert result.exists()

    def test_render_long_quote_wraps(self):
        """Test that long quotes are wrapped properly."""
        long_quote = (
            "Đây là một câu trích dẫn rất dài cần được wrap lại nhiều dòng "
            "để hiển thị đẹp trên ảnh quote card. Nội dung sẽ tự động xuống "
            "dòng khi quá dài và vẫn giữ được thẩm mỹ tốt."
        )
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "long.png"
            result = render_quote_card(
                quote_text=long_quote,
                book_title="Sách Hay",
                author="Tác giả",
                output_path=output_path,
            )
            assert result.exists()
            assert result.stat().st_size > 1000


class TestQuoteImageGeneration:
    """Test generate_quote_images integration with content_studio."""

    def test_generate_quote_images_from_analyzed(self):
        """Test generating quote images from analyzed chunks."""
        analyzed, metadata = _make_analyzed_chunks()
        with tempfile.TemporaryDirectory() as tmp:
            paths = generate_quote_images(
                analyzed, metadata,
                output_dir=tmp,
                max_cards=3,
                min_score=5.0,
                theme="dark",
            )
            assert len(paths) >= 1
            for p in paths:
                assert p.exists()
                assert p.suffix == ".png"

    def test_generate_quote_images_empty(self):
        """Test with no qualifying chunks."""
        metadata = BookMetadata(title="Empty")
        paths = generate_quote_images(
            [], metadata, output_dir="/tmp/empty_test", max_cards=5
        )
        assert paths == []

    def test_generate_quote_images_warm_theme(self):
        """Test with warm theme."""
        analyzed, metadata = _make_analyzed_chunks()
        with tempfile.TemporaryDirectory() as tmp:
            paths = generate_quote_images(
                analyzed, metadata,
                output_dir=tmp,
                max_cards=2,
                theme="warm",
            )
            assert len(paths) >= 1


class TestAIRewrite:
    """Test AI rewrite functions (with mocked LLM calls)."""

    def test_ai_rewrite_radio_scripts_fallback(self):
        """Test that AI rewrite falls back to template on API error."""
        analyzed, metadata = _make_analyzed_chunks()
        with patch(
            "bookai.content_studio._call_llm_for_rewrite",
            side_effect=ValueError("No API key"),
        ):
            scripts = ai_rewrite_radio_scripts(
                analyzed, metadata,
                max_scripts=2, min_score=6.0,
            )
            # Should fallback to template generation
            assert len(scripts) >= 1
            assert scripts[0].hook
            assert scripts[0].body
            assert scripts[0].cta

    def test_ai_rewrite_radio_scripts_success(self):
        """Test AI rewrite with mocked successful LLM response."""
        analyzed, metadata = _make_analyzed_chunks()
        mock_response = (
            '{"hook": "Bạn có biết tại sao 90% người thất bại?", '
            '"body": "Theo nghiên cứu, người thành công có 3 thói quen...", '
            '"cta": "Đọc cuốn sách này để biết thêm.", '
            '"title": "Bí mật thành công"}'
        )
        with patch(
            "bookai.content_studio._call_llm_for_rewrite",
            return_value=mock_response,
        ):
            scripts = ai_rewrite_radio_scripts(
                analyzed, metadata,
                max_scripts=2, min_score=6.0,
            )
            assert len(scripts) >= 1
            assert "90%" in scripts[0].hook
            assert scripts[0].title == "Bí mật thành công"

    def test_generate_all_with_ai_fallback(self):
        """Test generate_all_with_ai with mocked API errors."""
        analyzed, metadata = _make_analyzed_chunks()
        with patch(
            "bookai.content_studio._call_llm_for_rewrite",
            side_effect=ValueError("No API key"),
        ):
            pack = generate_all_with_ai(analyzed, metadata)
            assert isinstance(pack, ContentPack)
            # Should still produce content via fallback
            assert pack.total_pieces > 0

    def test_generate_all_with_ai_and_images(self):
        """Test generate_all_with_ai with image generation."""
        analyzed, metadata = _make_analyzed_chunks()
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "bookai.content_studio._call_llm_for_rewrite",
                side_effect=ValueError("No API key"),
            ):
                pack = generate_all_with_ai(
                    analyzed, metadata,
                    output_dir=tmp,
                    image_theme="light",
                )
                assert pack.total_pieces > 0
                # Check images were generated
                png_files = list(Path(tmp).glob("*.png"))
                assert len(png_files) >= 1


# --- OCR tests ---


class TestOCR:
    def test_ocr_image_basic(self):
        """Test OCR on a simple image with text."""
        # Create a test image with text using Pillow
        from PIL import Image, ImageDraw

        from bookai.ocr import ocr_image

        with tempfile.TemporaryDirectory() as tmp:
            img_path = Path(tmp) / "test_page.png"
            img = Image.new("RGB", (800, 200), "white")
            draw = ImageDraw.Draw(img)
            # Use default font
            draw.text((50, 80), "Hello World Test OCR", fill="black")
            img.save(str(img_path))

            metadata, text = ocr_image(str(img_path), lang="eng")
            assert metadata.source_format.value == "image"
            assert metadata.title == "test_page"
            # OCR should extract some text (may not be perfect)
            assert len(text) > 0

    def test_ocr_images_batch(self):
        """Test batch OCR on multiple images."""
        from PIL import Image, ImageDraw

        from bookai.ocr import ocr_images_batch

        with tempfile.TemporaryDirectory() as tmp:
            # Create 3 test pages
            for i in range(3):
                img_path = Path(tmp) / f"page_{i:03d}.png"
                img = Image.new("RGB", (800, 200), "white")
                draw = ImageDraw.Draw(img)
                draw.text((50, 80), f"Page {i + 1} content here", fill="black")
                img.save(str(img_path))

            files = sorted(str(f) for f in Path(tmp).glob("*.png"))
            metadata, text = ocr_images_batch(files, lang="eng")
            assert metadata.chapters == 3
            assert "---" in text  # Pages separated by ---

    def test_is_scanned_pdf(self):
        """Test scanned PDF detection."""
        # Create a text-based PDF (should NOT be detected as scanned)
        import pymupdf

        from bookai.ocr import is_scanned_pdf

        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = Path(tmp) / "text_based.pdf"
            doc = pymupdf.open()
            page = doc.new_page()
            # Insert plenty of text
            text_content = "Đây là một đoạn văn bản tiếng Việt dài " * 20
            page.insert_text((50, 100), text_content, fontsize=12)
            doc.save(str(pdf_path))
            doc.close()

            assert is_scanned_pdf(str(pdf_path)) is False

    def test_clean_ocr_text(self):
        """Test OCR text cleaning."""
        from bookai.ocr import _clean_ocr_text

        # Test noise removal
        dirty = "  Hello  World  \n\n\n\n\nParagraph two\n12\n---\nGood text"
        clean = _clean_ocr_text(dirty)
        assert "\n\n\n" not in clean
        # Short noise lines should be removed
        assert "12" not in clean

    def test_convert_file_detects_image(self):
        """Test that convert_file handles image files via OCR."""
        from PIL import Image, ImageDraw

        with tempfile.TemporaryDirectory() as tmp:
            img_path = Path(tmp) / "test.png"
            img = Image.new("RGB", (400, 100), "white")
            draw = ImageDraw.Draw(img)
            draw.text((20, 30), "Test image text", fill="black")
            img.save(str(img_path))

            metadata, text = convert_file(str(img_path))
            assert metadata.source_format.value == "image"

    def test_convert_images_dir(self):
        """Test converting a directory of images."""
        from PIL import Image, ImageDraw

        with tempfile.TemporaryDirectory() as tmp:
            for i in range(2):
                img_path = Path(tmp) / f"page_{i}.jpg"
                img = Image.new("RGB", (400, 100), "white")
                draw = ImageDraw.Draw(img)
                draw.text((20, 30), f"Directory page {i}", fill="black")
                img.save(str(img_path))

            metadata, text = convert_images_dir(tmp, lang="eng")
            assert metadata.chapters == 2


# --- Audio transcription tests ---


class TestAudio:
    def test_is_supported_audio(self):
        """Test audio format detection."""
        from bookai.audio import is_supported_audio

        assert is_supported_audio("file.mp3") is True
        assert is_supported_audio("file.wav") is True
        assert is_supported_audio("file.m4a") is True
        assert is_supported_audio("file.flac") is True
        assert is_supported_audio("file.ogg") is True
        assert is_supported_audio("file.pdf") is False
        assert is_supported_audio("file.txt") is False

    def test_format_timestamp(self):
        """Test timestamp formatting."""
        from bookai.audio import _format_timestamp

        assert _format_timestamp(0) == "00:00"
        assert _format_timestamp(65) == "01:05"
        assert _format_timestamp(3661) == "01:01:01"
        assert _format_timestamp(125.7) == "02:05"

    def test_estimate_chapters(self):
        """Test chapter estimation from segments."""
        from bookai.audio import _estimate_chapters

        # No segments
        assert _estimate_chapters([]) == 0

        # Single continuous segment
        segments = [{"start": 0, "end": 10}]
        assert _estimate_chapters(segments) == 1

        # Two segments with small gap (same chapter)
        segments = [
            {"start": 0, "end": 10},
            {"start": 11, "end": 20},
        ]
        assert _estimate_chapters(segments) == 1

        # Two segments with large gap (new chapter)
        segments = [
            {"start": 0, "end": 10},
            {"start": 20, "end": 30},
        ]
        assert _estimate_chapters(segments) == 2

    def test_segments_to_markdown(self):
        """Test segment to markdown conversion."""
        from bookai.audio import _segments_to_markdown

        segments = [
            {"start": 0, "end": 5, "text": " Hello world"},
            {"start": 5.5, "end": 10, "text": " Second sentence"},
            {"start": 15, "end": 20, "text": " After a gap"},
        ]

        md = _segments_to_markdown(segments, "Test Audio")
        assert "# Test Audio" in md
        assert "Hello world" in md
        assert "Second sentence" in md
        assert "[00:00]" in md  # First timestamp

    def test_get_audio_duration(self):
        """Test getting audio duration with ffprobe."""
        from bookai.audio import get_audio_duration

        # Non-existent file should return 0
        assert get_audio_duration("/nonexistent/file.mp3") == 0.0

    def test_transcribe_audio_creates_metadata(self):
        """Test that transcribe creates proper metadata (using a tiny WAV)."""
        import struct
        import wave

        with tempfile.TemporaryDirectory() as tmp:
            # Create a tiny valid WAV file (0.5s of silence)
            wav_path = Path(tmp) / "test.wav"
            with wave.open(str(wav_path), "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                # 0.5 seconds of silence
                frames = struct.pack("<" + "h" * 8000, *([0] * 8000))
                wf.writeframes(frames)

            # Transcribe the silence (should work without errors)
            from bookai.audio import transcribe_audio

            metadata, text = transcribe_audio(
                str(wav_path), model_size="tiny", language="en"
            )
            assert metadata.source_format.value == "audio"
            assert metadata.title == "test"

    def test_convert_file_detects_audio(self):
        """Test that convert_file routes audio files correctly."""
        import struct
        import wave

        with tempfile.TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "audiobook.wav"
            with wave.open(str(wav_path), "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                frames = struct.pack("<" + "h" * 8000, *([0] * 8000))
                wf.writeframes(frames)

            metadata, text = convert_file(str(wav_path))
            assert metadata.source_format.value == "audio"
