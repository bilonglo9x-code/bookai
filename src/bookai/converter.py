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
        text = page.get_text("text")
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
            text = page.get_text("text").strip()
            if text:
                chapters.append(text)
        chapter_count = len(chapters)

    markdown = "\n\n---\n\n".join(chapters)
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


def convert_file(file_path: str) -> tuple[BookMetadata, str]:
    """Auto-detect format and convert to Markdown.

    Supported: .epub, .pdf, .txt, .md
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()

    if suffix == ".epub":
        return convert_epub(file_path)
    elif suffix == ".pdf":
        return convert_pdf(file_path)
    elif suffix in (".txt", ".md", ".markdown"):
        return convert_text(file_path)
    else:
        raise ValueError(f"Unsupported format: {suffix}. Supported: .epub, .pdf, .txt, .md")


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
