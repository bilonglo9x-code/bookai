"""OCR module for extracting text from scanned PDFs and images."""

from __future__ import annotations

import re
from pathlib import Path

from .models import BookMetadata, SourceFormat


def ocr_image(file_path: str, lang: str = "vie+eng") -> tuple[BookMetadata, str]:
    """Extract text from a single image file using Tesseract OCR.

    Args:
        file_path: Path to image file (PNG, JPG, TIFF, BMP).
        lang: Tesseract language code(s). Default: vie+eng for Vietnamese.

    Returns:
        Tuple of (metadata, markdown_text).
    """
    import pytesseract
    from PIL import Image

    path = Path(file_path)
    img = Image.open(path)

    # Run OCR
    text = pytesseract.image_to_string(img, lang=lang)
    text = _clean_ocr_text(text)

    metadata = BookMetadata(
        title=path.stem,
        chapters=1,
        source_format=SourceFormat.IMAGE,
        file_path=file_path,
    )

    return metadata, text


def ocr_images_batch(
    file_paths: list[str], lang: str = "vie+eng"
) -> tuple[BookMetadata, str]:
    """Extract text from multiple image files (e.g., photographed book pages).

    Args:
        file_paths: List of image file paths, in page order.
        lang: Tesseract language code(s).

    Returns:
        Tuple of (metadata, combined_markdown_text).
    """
    import pytesseract
    from PIL import Image

    pages: list[str] = []
    for fp in file_paths:
        img = Image.open(fp)
        text = pytesseract.image_to_string(img, lang=lang)
        text = _clean_ocr_text(text)
        if text.strip():
            pages.append(text)

    title = Path(file_paths[0]).parent.name if file_paths else "Scanned Book"
    markdown = "\n\n---\n\n".join(pages)

    metadata = BookMetadata(
        title=title,
        chapters=len(pages),
        source_format=SourceFormat.IMAGE,
        file_path=file_paths[0] if file_paths else "",
    )

    return metadata, markdown


def ocr_pdf(file_path: str, lang: str = "vie+eng") -> tuple[BookMetadata, str]:
    """Extract text from a scanned PDF using OCR on each page.

    Renders each PDF page as an image, then runs Tesseract OCR.

    Args:
        file_path: Path to scanned PDF file.
        lang: Tesseract language code(s).

    Returns:
        Tuple of (metadata, markdown_text).
    """
    import pymupdf
    import pytesseract
    from PIL import Image

    doc = pymupdf.open(file_path)
    pdf_meta = doc.metadata or {}
    title = pdf_meta.get("title") or Path(file_path).stem
    author = pdf_meta.get("author") or "Unknown"

    pages: list[str] = []
    for page_num, page in enumerate(doc):
        # Render page to image at 300 DPI for good OCR quality
        mat = pymupdf.Matrix(300 / 72, 300 / 72)
        pix = page.get_pixmap(matrix=mat)

        # Convert to PIL Image
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

        # Run OCR
        text = pytesseract.image_to_string(img, lang=lang)
        text = _clean_ocr_text(text)

        if text.strip():
            pages.append(text)

    doc.close()

    markdown = "\n\n---\n\n".join(pages)

    metadata = BookMetadata(
        title=title,
        author=author,
        chapters=len(pages),
        source_format=SourceFormat.PDF,
        file_path=file_path,
    )

    return metadata, markdown


def is_scanned_pdf(file_path: str, sample_pages: int = 5) -> bool:
    """Detect if a PDF is scanned (image-based) vs text-based.

    Checks the first few pages: if text extraction yields very little
    content relative to page size, it's likely a scanned PDF.

    Args:
        file_path: Path to PDF file.
        sample_pages: Number of pages to sample.

    Returns:
        True if PDF appears to be scanned/image-based.
    """
    import pymupdf

    doc = pymupdf.open(file_path)
    total_pages = len(doc)
    pages_to_check = min(sample_pages, total_pages)

    text_chars = 0
    for i in range(pages_to_check):
        page = doc[i]
        text = page.get_text()
        # Count meaningful characters (not just whitespace/numbers)
        meaningful = re.sub(r"[\s\d\W]", "", text)
        text_chars += len(meaningful)

    doc.close()

    # If less than 50 meaningful characters per page on average, likely scanned
    avg_chars_per_page = text_chars / pages_to_check if pages_to_check > 0 else 0
    return avg_chars_per_page < 50


def _clean_ocr_text(text: str) -> str:
    """Clean up OCR output text."""
    if not text:
        return ""

    # Fix common OCR errors for Vietnamese
    # Remove excessive whitespace but keep paragraph breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove very short lines that are likely noise (< 3 chars)
    lines = text.split("\n")
    lines = [line for line in lines if len(line.strip()) >= 3 or line.strip() == ""]

    # Remove lines that are purely special characters or numbers (page artifacts)
    lines = [
        line for line in lines
        if not re.match(r"^[\d\s\.\-\|_=]+$", line.strip())
    ]

    return "\n".join(lines).strip()
