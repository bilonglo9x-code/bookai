"""Quote Card Image Renderer — Generate PNG quote cards using Pillow."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Color themes
# ---------------------------------------------------------------------------

THEMES: dict[str, dict[str, str | tuple[int, ...]]] = {
    "dark": {
        "bg": (30, 30, 40),
        "text": (255, 255, 255),
        "accent": (255, 165, 0),
        "meta": (180, 180, 180),
    },
    "light": {
        "bg": (250, 248, 240),
        "text": (40, 40, 40),
        "accent": (180, 60, 60),
        "meta": (100, 100, 100),
    },
    "gradient_blue": {
        "bg": (20, 30, 60),
        "text": (240, 240, 255),
        "accent": (100, 200, 255),
        "meta": (170, 190, 210),
    },
    "warm": {
        "bg": (45, 25, 20),
        "text": (255, 245, 230),
        "accent": (255, 180, 80),
        "meta": (200, 170, 140),
    },
}


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Try to load a system font that supports Vietnamese/Unicode."""
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in font_candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    # Fallback to default
    return ImageFont.load_default()


def _wrap_text(text: str, max_chars: int = 35) -> list[str]:
    """Wrap text for rendering, respecting Vietnamese word boundaries."""
    return textwrap.wrap(text, width=max_chars, break_long_words=False)


def _draw_gradient_bg(img: Image.Image, color_top: tuple, color_bottom: tuple) -> None:
    """Draw a vertical gradient background."""
    width, height = img.size
    for y in range(height):
        ratio = y / height
        r = int(color_top[0] * (1 - ratio) + color_bottom[0] * ratio)
        g = int(color_top[1] * (1 - ratio) + color_bottom[1] * ratio)
        b = int(color_top[2] * (1 - ratio) + color_bottom[2] * ratio)
        for x in range(width):
            img.putpixel((x, y), (r, g, b))


def render_quote_card(
    quote_text: str,
    book_title: str,
    author: str,
    output_path: str | Path,
    theme: str = "dark",
    width: int = 1080,
    height: int = 1080,
) -> Path:
    """Render a quote card as PNG image.

    Args:
        quote_text: The quote text to display.
        book_title: Title of the book.
        author: Author name.
        output_path: Where to save the PNG.
        theme: Color theme name (dark, light, gradient_blue, warm).
        width: Image width in pixels.
        height: Image height in pixels.

    Returns:
        Path to the saved image file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    colors = THEMES.get(theme, THEMES["dark"])
    bg_color = colors["bg"]
    text_color = colors["text"]
    accent_color = colors["accent"]
    meta_color = colors["meta"]

    # Create image
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Fonts
    quote_font = _get_font(42, bold=False)
    title_font = _get_font(28, bold=True)
    author_font = _get_font(24, bold=False)

    # Layout: quote centered, metadata at bottom
    margin = 80
    usable_width = width - 2 * margin

    # Wrap quote text
    chars_per_line = max(20, usable_width // 25)
    wrapped_lines = _wrap_text(quote_text, max_chars=chars_per_line)

    # Calculate quote text height
    line_height = 58
    quote_block_height = len(wrapped_lines) * line_height

    # Vertical positioning: center the quote, metadata at bottom
    meta_area_height = 120
    available_height = height - 2 * margin - meta_area_height
    quote_y_start = margin + max(0, (available_height - quote_block_height) // 2)

    # Draw opening quote mark
    quote_mark_font = _get_font(80, bold=True)
    draw.text(
        (margin - 10, quote_y_start - 60),
        "\u201c",
        font=quote_mark_font,
        fill=accent_color,
    )

    # Draw quote lines
    for i, line in enumerate(wrapped_lines):
        y = quote_y_start + i * line_height
        draw.text((margin + 20, y), line, font=quote_font, fill=text_color)

    # Draw closing quote mark
    last_line_y = quote_y_start + len(wrapped_lines) * line_height
    draw.text(
        (margin - 10, last_line_y - 10),
        "\u201d",
        font=quote_mark_font,
        fill=accent_color,
    )

    # Draw separator line
    sep_y = height - meta_area_height - margin
    draw.line(
        [(margin, sep_y), (width - margin, sep_y)],
        fill=accent_color,
        width=2,
    )

    # Draw book title
    title_y = sep_y + 20
    draw.text((margin, title_y), book_title, font=title_font, fill=accent_color)

    # Draw author
    author_y = title_y + 40
    draw.text((margin, author_y), f"— {author}", font=author_font, fill=meta_color)

    img.save(str(output_path), "PNG", quality=95)
    return output_path


def render_quote_cards_batch(
    quotes: list[dict],
    output_dir: str | Path,
    theme: str = "dark",
) -> list[Path]:
    """Render multiple quote cards.

    Args:
        quotes: List of dicts with keys: quote_text, book_title, author.
        output_dir: Directory to save images.
        theme: Color theme name.

    Returns:
        List of paths to generated images.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for i, q in enumerate(quotes):
        filename = f"quote_{i + 1:03d}.png"
        path = render_quote_card(
            quote_text=q["quote_text"],
            book_title=q["book_title"],
            author=q["author"],
            output_path=output_dir / filename,
            theme=theme,
        )
        paths.append(path)

    return paths
