"""Affiliate link management for BookAI.

Manages platform affiliate links per book, injects them into content CTAs,
and appends sub-ID tracking parameters for per-video conversion analytics.

Usage::

    from bookai.affiliate import AffiliateManager

    mgr = AffiliateManager.from_file("affiliate_links.json")
    link = mgr.get_link("Đắc Nhân Tâm", platform="shopee", sub_id="vid_001_tiktok")
    # → "https://shope.ee/xxx?sub_aff_id=vid_001_tiktok"

    injected = mgr.inject_into_cta(cta_text, "Đắc Nhân Tâm", platform="tiktok")
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

Platform = Literal["shopee", "tiktok", "tiki", "lazada"]

_PLATFORM_PARAM: dict[str, str] = {
    "shopee": "sub_aff_id",
    "tiktok": "sub_id",
    "tiki": "ref",
    "lazada": "sub_aff_id",
}

# Default CTA templates per platform (used when injecting links)
_CTA_TEMPLATES: dict[str, str] = {
    "tiktok": "👉 Đặt sách tại GIỎ HÀNG hoặc link: {link} | Mã: {sub_id}",
    "shopee": "🛒 Mua ngay trên Shopee: {link}",
    "tiki": "📦 Đặt sách Tiki: {link}",
    "instagram": "🔗 Link mua sách trong bio. Tìm: {title}",
    "youtube": "📖 Link mua sách trong phần mô tả: {link}",
    "blog": '👉 <a href="{link}">Mua sách {title} tại đây</a> (hoa hồng affiliate)',
    "pinterest": "🛍️ Mua sách: {link}",
}


@dataclass
class BookLinks:
    """Affiliate links for a single book across platforms."""

    book_title: str
    isbn: str = ""
    shopee: str = ""
    tiktok: str = ""
    tiki: str = ""
    lazada: str = ""
    notes: str = ""

    def get(self, platform: str) -> str:
        """Return the link for a platform, or empty string if not set."""
        return getattr(self, platform, "") or ""

    def model_dump(self) -> dict:
        return {
            "book_title": self.book_title,
            "isbn": self.isbn,
            "shopee": self.shopee,
            "tiktok": self.tiktok,
            "tiki": self.tiki,
            "lazada": self.lazada,
            "notes": self.notes,
        }


@dataclass
class AffiliateManager:
    """Central manager for all book affiliate links."""

    books: list[BookLinks] = field(default_factory=list)
    _index: dict[str, BookLinks] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """Rebuild lookup index (case-insensitive title key)."""
        self._index = {}
        for b in self.books:
            key = _normalize_title(b.book_title)
            self._index[key] = b
            if b.isbn:
                self._index[b.isbn] = b

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    @classmethod
    def from_file(cls, path: str | Path) -> AffiliateManager:
        """Load config from a JSON file. Returns empty manager if not found."""
        p = Path(path)
        if not p.exists():
            return cls()
        data = json.loads(p.read_text(encoding="utf-8"))
        books = [BookLinks(**item) for item in data.get("books", [])]
        return cls(books=books)

    def save(self, path: str | Path) -> None:
        """Persist config to JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {"books": [b.model_dump() for b in self.books]}
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_book(self, book: BookLinks) -> None:
        """Add or update a book's affiliate links."""
        key = _normalize_title(book.book_title)
        if key in self._index:
            # Update in-place
            existing = self._index[key]
            for attr in ("isbn", "shopee", "tiktok", "tiki", "lazada", "notes"):
                val = getattr(book, attr)
                if val:
                    setattr(existing, attr, val)
        else:
            self.books.append(book)
            self._rebuild_index()

    def remove_book(self, title: str) -> bool:
        """Remove a book by title. Returns True if found and removed."""
        key = _normalize_title(title)
        if key not in self._index:
            return False
        book = self._index[key]
        self.books = [b for b in self.books if b is not book]
        self._rebuild_index()
        return True

    # ------------------------------------------------------------------
    # Link retrieval
    # ------------------------------------------------------------------

    def get_book(self, title: str) -> BookLinks | None:
        """Find BookLinks by title (fuzzy-normalized)."""
        return self._index.get(_normalize_title(title))

    def get_link(
        self,
        title: str,
        platform: str = "tiktok",
        sub_id: str = "",
    ) -> str:
        """Return affiliate link for a book+platform, optionally with sub-ID tracking.

        Args:
            title: Book title (case-insensitive, accent-insensitive).
            platform: 'shopee', 'tiktok', 'tiki', or 'lazada'.
            sub_id: Tracking sub-ID appended as query param (e.g. 'vid_001_tiktok').

        Returns:
            URL string, or empty string if not configured.
        """
        book = self.get_book(title)
        if not book:
            return ""
        base_url = book.get(platform)
        if not base_url:
            return ""
        if not sub_id:
            return base_url
        return _append_sub_id(base_url, platform, sub_id)

    def get_best_link(self, title: str, sub_id: str = "") -> tuple[str, str]:
        """Return (platform, url) for the first configured link.

        Preference order: tiktok > shopee > tiki > lazada.
        """
        book = self.get_book(title)
        if not book:
            return "", ""
        for platform in ("tiktok", "shopee", "tiki", "lazada"):
            url = book.get(platform)
            if url:
                if sub_id:
                    url = _append_sub_id(url, platform, sub_id)
                return platform, url
        return "", ""

    # ------------------------------------------------------------------
    # Content injection
    # ------------------------------------------------------------------

    def inject_into_cta(
        self,
        cta: str,
        book_title: str,
        platform: str = "tiktok",
        sub_id: str = "",
        append: bool = True,
    ) -> str:
        """Inject affiliate link into a CTA string.

        If a URL is already present in `cta`, replaces it.
        Otherwise appends the link at the end (or prepends, if append=False).

        Args:
            cta: Original call-to-action text.
            book_title: Book to look up link for.
            platform: Affiliate platform to use.
            sub_id: Tracking sub-ID.
            append: If True, append link; if False, prepend.

        Returns:
            CTA string with link injected.
        """
        link = self.get_link(book_title, platform=platform, sub_id=sub_id)
        if not link:
            return cta

        # Replace existing URL placeholder or append
        if "{link}" in cta:
            return cta.replace("{link}", link)

        # If there's already a URL in the CTA, replace it
        url_pattern = r"https?://\S+"
        if re.search(url_pattern, cta):
            return re.sub(url_pattern, link, cta, count=1)

        # Append
        sep = "\n" if "\n" in cta else " "
        suffix = f"{sep}👉 {link}"
        if append:
            return cta.rstrip() + suffix
        return suffix.lstrip() + sep + cta

    def build_cta_line(
        self,
        book_title: str,
        platform: str = "tiktok",
        sub_id: str = "",
        content_output_type: str = "tiktok",
    ) -> str:
        """Build a standalone CTA line with affiliate link.

        Args:
            book_title: Book title for link lookup.
            platform: Affiliate platform ('shopee', 'tiktok', 'tiki').
            sub_id: Tracking sub-ID.
            content_output_type: Where this CTA will appear ('tiktok', 'instagram', 'blog', ...).

        Returns:
            Formatted CTA line, or fallback without link if none configured.
        """
        link = self.get_link(book_title, platform=platform, sub_id=sub_id)
        template = _CTA_TEMPLATES.get(content_output_type, _CTA_TEMPLATES["tiktok"])
        return template.format(
            link=link or f"[link {book_title}]",
            title=book_title,
            sub_id=sub_id or "—",
        )

    # ------------------------------------------------------------------
    # Batch injection into ContentPack
    # ------------------------------------------------------------------

    def inject_into_content_pack(
        self,
        pack: object,
        sub_id_prefix: str = "",
    ) -> object:
        """Inject affiliate links into all CTA fields of a ContentPack.

        Modifies `pack` in-place and returns it.

        Args:
            pack: A `ContentPack` instance from content_studio.
            sub_id_prefix: Prefix for sub-IDs (e.g. 'book_2025_08'). Final sub-ID:
                           '{prefix}_{content_type}_{index}'.

        Returns:
            The same pack with links injected.
        """
        book_title = pack.book_title  # type: ignore[attr-defined]

        for i, script in enumerate(getattr(pack, "radio_scripts", [])):
            sub_id = f"{sub_id_prefix}_radio_{i}" if sub_id_prefix else ""
            script.cta = self.inject_into_cta(
                script.cta, book_title, platform="tiktok", sub_id=sub_id
            )

        for i, card in enumerate(getattr(pack, "quote_cards", [])):
            sub_id = f"{sub_id_prefix}_quote_{i}" if sub_id_prefix else ""
            card.caption = self.inject_into_cta(
                card.caption, book_title, platform="shopee", sub_id=sub_id
            )

        for i, listicle in enumerate(getattr(pack, "listicles", [])):
            sub_id = f"{sub_id_prefix}_listicle_{i}" if sub_id_prefix else ""
            listicle.cta = self.inject_into_cta(
                listicle.cta, book_title, platform="shopee", sub_id=sub_id
            )

        for i, caption in enumerate(getattr(pack, "captions", [])):
            sub_id = f"{sub_id_prefix}_caption_{i}" if sub_id_prefix else ""
            caption.text = self.inject_into_cta(
                caption.text, book_title, platform="tiktok", sub_id=sub_id
            )

        return pack

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def list_books(self) -> list[dict]:
        """Return summary list of all configured books."""
        return [
            {
                "title": b.book_title,
                "isbn": b.isbn,
                "platforms": [
                    p for p in ("shopee", "tiktok", "tiki", "lazada") if b.get(p)
                ],
            }
            for b in self.books
        ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_title(title: str) -> str:
    """Lowercase + strip for fuzzy matching (not full accent normalization)."""
    return title.lower().strip()


def _append_sub_id(url: str, platform: str, sub_id: str) -> str:
    """Append sub-ID tracking parameter to a URL."""
    param_name = _PLATFORM_PARAM.get(platform, "sub_id")
    parsed = urlparse(url)
    # Preserve existing query params
    existing = parse_qs(parsed.query, keep_blank_values=True)
    existing[param_name] = [sub_id]
    new_query = urlencode({k: v[0] for k, v in existing.items()})
    return urlunparse(parsed._replace(query=new_query))


def make_sub_id(video_id: str, platform: str, niche: str = "") -> str:
    """Generate a standardized sub-ID for tracking.

    Format: ``{video_id}_{platform}[_{niche}]``

    Example::

        make_sub_id("vid_001", "tiktok", "tamly") → "vid_001_tiktok_tamly"
    """
    parts = [video_id, platform]
    if niche:
        parts.append(niche)
    return "_".join(p.strip("_") for p in parts if p)
