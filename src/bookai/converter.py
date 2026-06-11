"""Convert various book formats to Markdown."""

from __future__ import annotations

import re
from pathlib import Path

from .models import BookMetadata, SourceFormat


def convert_epub(file_path: str) -> tuple[BookMetadata, str]:
    """Convert EPUB file to Markdown.

    Returns metadata and full markdown text.
    """
    import ebooklib
    from ebooklib import epub

    book = epub.read_epub(file_path)

    # Extract metadata
    title = _get_epub_metadata(book, "title") or Path(file_path).stem
    author = _get_epub_metadata(book, "creator") or "Unknown"
    publisher = _get_epub_metadata(book, "publisher") or ""
    language = _get_epub_metadata(book, "language") or "vi"

    # Extract content from all chapters
    chapters: list[str] = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        content = item.get_content().decode("utf-8", errors="ignore")
        md = _html_to_markdown(content)
        if md.strip():
            chapters.append(md)

    markdown = "\n\n---\n\n".join(chapters)

    metadata = BookMetadata(
        title=title,
        author=author,
        publisher=publisher,
        language=language,
        chapters=len(chapters),
        source_format=SourceFormat.EPUB,
        file_path=file_path,
    )

    return metadata, markdown


def convert_pdf(file_path: str) -> tuple[BookMetadata, str]:
    """Convert PDF file (text-based) to Markdown.

    Returns metadata and full markdown text.
    """
    import pymupdf

    doc = pymupdf.open(file_path)

    # Extract metadata
    pdf_meta = doc.metadata or {}
    title = pdf_meta.get("title") or Path(file_path).stem
    author = pdf_meta.get("author") or "Unknown"

    # Extract text from all pages
    chapters: list[str] = []
    current_chapter: list[str] = []
    chapter_count = 0

    for page in doc:
        text = _extract_pdf_page_text(page)
        if not text.strip():
            continue

        # Detect chapter boundaries (simple heuristic)
        lines = text.strip().split("\n")
        for line in lines:
            if _is_chapter_heading(line):
                if current_chapter:
                    chapters.append("\n".join(current_chapter))
                    current_chapter = []
                chapter_count += 1
                current_chapter.append(f"# {line.strip()}")
            else:
                current_chapter.append(line.strip())

    if current_chapter:
        chapters.append("\n".join(current_chapter))

    # If no chapters detected, treat each page as a section
    if not chapters:
        for page in doc:
            text = _extract_pdf_page_text(page)
            if text:
                chapters.append(text)
        chapter_count = len(chapters)

    markdown = "\n\n---\n\n".join(chapters)
    markdown = _clean_pdf_artifacts(markdown)
    doc.close()

    metadata = BookMetadata(
        title=title,
        author=author,
        chapters=chapter_count or len(chapters),
        source_format=SourceFormat.PDF,
        file_path=file_path,
    )

    return metadata, markdown


def convert_text(file_path: str) -> tuple[BookMetadata, str]:
    """Convert plain text file to Markdown.

    Returns metadata and the text content.
    """
    path = Path(file_path)
    text = path.read_text(encoding="utf-8")
    title = path.stem

    metadata = BookMetadata(
        title=title,
        chapters=1,
        source_format=SourceFormat.TEXT,
        file_path=file_path,
    )

    return metadata, text


def convert_image(file_path: str, lang: str = "vie+eng") -> tuple[BookMetadata, str]:
    """Convert image file(s) to Markdown using OCR.

    Supports: PNG, JPG, JPEG, TIFF, BMP.
    """
    from .ocr import ocr_image

    return ocr_image(file_path, lang=lang)


def convert_images_dir(dir_path: str, lang: str = "vie+eng") -> tuple[BookMetadata, str]:
    """Convert a directory of images (book pages) to Markdown.

    Images are sorted by name and processed in order.
    """
    from .ocr import ocr_images_batch

    path = Path(dir_path)
    image_exts = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
    files = sorted(
        [str(f) for f in path.iterdir() if f.suffix.lower() in image_exts]
    )

    if not files:
        raise ValueError(f"No image files found in: {dir_path}")

    return ocr_images_batch(files, lang=lang)


def convert_audio(
    file_path: str, model_size: str = "base", language: str = "vi"
) -> tuple[BookMetadata, str]:
    """Convert audio file to Markdown using Whisper transcription.

    Supports: MP3, WAV, M4A, FLAC, OGG, WMA, AAC, OPUS.
    """
    from .audio import transcribe_audio

    return transcribe_audio(file_path, model_size=model_size, language=language)


def convert_pdf_smart(file_path: str, lang: str = "vie+eng") -> tuple[BookMetadata, str]:
    """Smart PDF conversion: auto-detect text vs scanned and use appropriate method.

    - Text PDFs: fast text extraction (PyMuPDF)
    - Scanned PDFs: OCR extraction (Tesseract)
    """
    from .ocr import is_scanned_pdf, ocr_pdf

    if is_scanned_pdf(file_path):
        return ocr_pdf(file_path, lang=lang)
    return convert_pdf(file_path)


def convert_file(file_path: str, ocr_lang: str = "vie+eng") -> tuple[BookMetadata, str]:
    """Auto-detect format and convert to Markdown.

    Supported: .epub, .pdf, .txt, .md, images (.png, .jpg, .tiff, .bmp),
               audio (.mp3, .wav, .m4a, .flac, .ogg)
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()

    if suffix == ".epub":
        return convert_epub(file_path)
    elif suffix == ".pdf":
        return convert_pdf_smart(file_path, lang=ocr_lang)
    elif suffix in (".txt", ".md", ".markdown"):
        return convert_text(file_path)
    elif suffix in (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"):
        return convert_image(file_path, lang=ocr_lang)
    elif suffix in (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma", ".aac", ".opus"):
        return convert_audio(file_path)
    else:
        raise ValueError(
            f"Unsupported format: {suffix}. "
            "Supported: .epub, .pdf, .txt, .md, images (.png/.jpg/.tiff/.bmp), "
            "audio (.mp3/.wav/.m4a/.flac/.ogg)"
        )


def _get_epub_metadata(book: object, field: str) -> str | None:
    """Extract metadata field from EPUB book."""
    from ebooklib import epub

    if not isinstance(book, epub.EpubBook):
        return None
    values = book.get_metadata("DC", field)
    if values:
        return values[0][0]
    return None


def _html_to_markdown(html: str) -> str:
    """Convert HTML content to Markdown."""
    import html2text

    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.body_width = 0  # Don't wrap lines
    converter.unicode_snob = True

    md = converter.handle(html)

    # Clean up excessive whitespace
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def _clean_pdf_artifacts(text: str) -> str:
    """Remove common PDF artifacts: watermarks, page numbers, repeated URLs."""
    # Remove watermark URLs that appear on every page (e.g., thuviensach.vn)
    lines = text.split("\n")
    # Count URL-like lines to detect watermarks (appear on >30% of pages)
    from collections import Counter

    url_counts = Counter()
    for line in lines:
        stripped = line.strip()
        if re.match(r"^https?://\S+$", stripped):
            url_counts[stripped] += 1

    watermarks = {url for url, count in url_counts.items() if count > 5}

    if watermarks:
        lines = [line for line in lines if line.strip() not in watermarks]

    # Remove standalone page number lines (e.g., "34 -", "- 39", "34 - Book Title")
    lines = [
        line for line in lines
        if not re.match(r"^\s*-?\s*\d{1,4}\s*-?\s*$", line)
        and not re.match(r"^\s*\d{1,4}\s*-\s*.{1,40}\s*$", line)
        and not re.match(r"^\s*.{1,40}\s*-\s*\d{1,4}\s*$", line)
    ]

    result = "\n".join(lines)
    # Clean up excessive blank lines left after removal
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result


def _fix_vietnamese_pdf_text(text: str) -> str:
    """Fix broken Vietnamese 'đ' character in PDF text extraction.

    Many Vietnamese PDFs use fonts that map 'đ' (d-stroke) to control
    characters like \\x05. This function detects and fixes those mappings.
    """
    if not text:
        return text

    # Common pattern: \x05 is used for lowercase 'đ' in broken Vietnamese PDF fonts
    text = text.replace("\x05", "đ")

    # Remove form feed characters (page breaks)
    text = text.replace("\x0c", "")

    # Fix other potential control character mappings
    text = re.sub(r"[\x00-\x04\x06-\x08\x0e-\x1f]", "", text)

    return text


def _extract_pdf_page_text(page: object) -> str:
    """Extract text from PDF page using dict mode to fix broken Vietnamese fonts.

    In many Vietnamese PDFs, the 'đ/Đ' character is mapped to a newline (\\n)
    within font spans. Dict-mode extraction lets us detect these: real line breaks
    separate 'lines' objects, while \\n inside a span's text is a broken character.
    """
    import pymupdf  # noqa: F811

    if not isinstance(page, pymupdf.Page):
        return ""

    page_dict = page.get_text("dict")
    lines_out: list[str] = []

    for block in page_dict.get("blocks", []):
        if "lines" not in block:
            continue
        for line in block["lines"]:
            line_text = ""
            for span in line["spans"]:
                text = span["text"]
                # \n within a span = broken đ/Đ in Vietnamese PDF fonts
                text = text.replace("\n", "đ")
                # Also fix \x05 mapping
                text = text.replace("\x05", "đ")
                line_text += text
            if line_text.strip():
                lines_out.append(line_text.strip())

    result = "\n".join(lines_out)
    # Remove form feed and other control chars
    result = re.sub(r"[\x00-\x08\x0e-\x1f]", "", result)
    return result


def _is_chapter_heading(line: str) -> bool:
    """Heuristic to detect chapter headings in PDF text."""
    line = line.strip()
    if not line:
        return False

    # Common Vietnamese chapter patterns
    patterns = [
        r"^(Chương|CHƯƠNG|Chapter|CHAPTER)\s+\d+",
        r"^(Phần|PHẦN|Part|PART)\s+\d+",
        r"^(Bài|BÀI)\s+\d+",
        r"^(MỤC|Mục)\s+\d+",
    ]

    for pattern in patterns:
        if re.match(pattern, line):
            return True

    # All caps short line (likely a title)
    if line.isupper() and 5 < len(line) < 80:
        return True

    return False
