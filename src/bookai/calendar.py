"""Content Calendar Generator for BookAI.

Turns a ContentPack into a 30-day posting schedule optimized for affiliate conversion.

Strategy (based on @sachhayexpress analysis + docs/PLAN.md):
    Week 1 — Hook & Tease:    Quote cards + short clips → build curiosity
    Week 2 — Deep Content:    Radio scripts → deliver value
    Week 3 — Engagement:      Listicles + story-driven posts → comments/shares
    Week 4 — Conversion Push: Captions + combo CTAs → drive purchase

Usage::

    from bookai.calendar import generate_calendar, save_calendar_csv

    entries = generate_calendar(
        pack, start_date="2025-08-01", days=30, sub_id_prefix="eckhart_aug"
    )
    save_calendar_csv(entries, "calendar.csv")
    save_calendar_json(entries, "calendar.json")
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

# Optimal posting times per platform (hour, minute)
_POST_TIMES: dict[str, list[tuple[int, int]]] = {
    "tiktok":    [(6, 30), (12, 15), (20, 0)],   # 3 slots/day
    "instagram": [(7, 0), (12, 0), (19, 30)],
    "youtube":   [(9, 0), (19, 0)],
    "pinterest": [(8, 0), (14, 0), (21, 0)],
    "facebook":  [(7, 30), (12, 0), (20, 30)],
    "blog":      [(8, 0)],
}

_DEFAULT_PLATFORMS = ["tiktok", "instagram"]


@dataclass
class CalendarEntry:
    """A single scheduled content item."""

    entry_id: str                   # e.g. "d01_tiktok_radio_0"
    date: str                       # ISO format: "2025-08-01"
    day_number: int                 # 1-based
    week_number: int                # 1-based
    post_time: str                  # "HH:MM"
    platform: str                   # tiktok, instagram, youtube, blog, ...
    content_type: str               # radio_script, quote_card, listicle, caption
    content_index: int              # index in the ContentPack list
    content_title: str              # human-readable title
    caption: str                    # full caption text
    hashtags: list[str] = field(default_factory=list)
    affiliate_link: str = ""        # pre-filled affiliate link
    image_path: str = ""            # path to quote card PNG (if applicable)
    status: str = "scheduled"       # scheduled | approved | posted
    notes: str = ""

    @property
    def hashtag_string(self) -> str:
        return " ".join(f"#{h}" for h in self.hashtags)

    def as_flat_dict(self) -> dict:
        """Return a flat dict suitable for CSV export."""
        d = asdict(self)
        d["hashtags"] = self.hashtag_string
        return d


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


def generate_calendar(
    pack: object,
    start_date: str | date = "2025-08-01",
    days: int = 30,
    platforms: list[str] | None = None,
    sub_id_prefix: str = "",
    posts_per_day: int = 2,
) -> list[CalendarEntry]:
    """Generate a content posting calendar from a ContentPack.

    Args:
        pack: A `ContentPack` instance from content_studio.
        start_date: First posting date (ISO string or date object).
        days: Calendar length in days.
        platforms: List of platforms to schedule for. Default: tiktok + instagram.
        sub_id_prefix: Prefix for affiliate sub-IDs (e.g. 'eckhart_aug').
        posts_per_day: Max posts per day across all platforms.

    Returns:
        List of CalendarEntry objects, sorted by date.
    """
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)

    platforms = platforms or _DEFAULT_PLATFORMS

    # Pull content from pack
    radio_scripts = list(getattr(pack, "radio_scripts", []))
    quote_cards = list(getattr(pack, "quote_cards", []))
    listicles = list(getattr(pack, "listicles", []))
    captions = list(getattr(pack, "captions", []))
    _ = getattr(pack, "book_title", "")  # available for future use

    # Build the 4-week strategy pool
    strategy = _build_strategy(
        days=days,
        radio_count=len(radio_scripts),
        quote_count=len(quote_cards),
        listicle_count=len(listicles),
        caption_count=len(captions),
    )

    entries: list[CalendarEntry] = []
    slot_index = 0  # global content slot counter

    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        day_num = day_offset + 1
        week_num = (day_offset // 7) + 1

        day_slots = strategy.get(day_num, [])[:posts_per_day]
        platform_cycle = _cycle(platforms)

        for slot_num, content_spec in enumerate(day_slots):
            content_type = content_spec["type"]
            idx = content_spec["index"]
            platform = next(platform_cycle)

            # Get content object
            content_obj = _get_content(
                content_type, idx, radio_scripts, quote_cards, listicles, captions
            )
            if content_obj is None:
                continue

            caption = _build_caption(content_obj, content_type)
            hashtags = _get_hashtags(content_obj)
            title = _get_title(content_obj, content_type, idx)
            image_path = _get_image_path(content_obj, content_type)

            # Affiliate link
            aff_link = _get_affiliate_link(content_obj, content_type)

            # Post time
            times = _POST_TIMES.get(platform, [(9, 0)])
            post_time_tuple = times[slot_num % len(times)]
            post_time = f"{post_time_tuple[0]:02d}:{post_time_tuple[1]:02d}"

            entry_id = f"d{day_num:02d}_{platform}_{content_type}_{idx}"
            entry = CalendarEntry(
                entry_id=entry_id,
                date=current_date.isoformat(),
                day_number=day_num,
                week_number=week_num,
                post_time=post_time,
                platform=platform,
                content_type=content_type,
                content_index=idx,
                content_title=title,
                caption=caption,
                hashtags=hashtags,
                affiliate_link=aff_link,
                image_path=image_path,
                notes=f"Week {week_num} — {_WEEK_THEMES.get(week_num, 'Content')}",
            )
            entries.append(entry)
            slot_index += 1

    return sorted(entries, key=lambda e: (e.date, e.post_time))


# ---------------------------------------------------------------------------
# Strategy builder
# ---------------------------------------------------------------------------

_WEEK_THEMES = {
    1: "Hook & Tease",
    2: "Deep Content",
    3: "Engagement",
    4: "Conversion Push",
}


def _build_strategy(
    days: int,
    radio_count: int,
    quote_count: int,
    listicle_count: int,
    caption_count: int,
) -> dict[int, list[dict]]:
    """Build day → content_type mapping for 4-week strategy.

    Returns dict[day_number] → list of {type, index}.
    """
    strategy: dict[int, list[dict]] = {}

    # Infinite cycled pools
    radio_pool = _infinite_cycle(list(range(radio_count))) if radio_count else None
    quote_pool = _infinite_cycle(list(range(quote_count))) if quote_count else None
    listicle_pool = _infinite_cycle(list(range(listicle_count))) if listicle_count else None
    caption_pool = _infinite_cycle(list(range(caption_count))) if caption_count else None

    for day in range(1, days + 1):
        week = (day - 1) // 7 + 1
        dow = (day - 1) % 7  # 0=Mon, 6=Sun
        slots: list[dict] = []

        if week == 1:
            # Hook & Tease: quote cards + captions
            if quote_pool:
                slots.append({"type": "quote_card", "index": next(quote_pool)})
            if caption_pool and dow in (2, 4, 6):
                slots.append({"type": "caption", "index": next(caption_pool)})

        elif week == 2:
            # Deep Content: radio scripts primary
            if radio_pool:
                slots.append({"type": "radio_script", "index": next(radio_pool)})
            if quote_pool and dow in (0, 2, 4):
                slots.append({"type": "quote_card", "index": next(quote_pool)})

        elif week == 3:
            # Engagement: listicles + stories
            if listicle_pool:
                slots.append({"type": "listicle", "index": next(listicle_pool)})
            if radio_pool and dow in (1, 3, 5):
                slots.append({"type": "radio_script", "index": next(radio_pool)})

        else:
            # Week 4+: Conversion Push — captions + radio
            if caption_pool:
                slots.append({"type": "caption", "index": next(caption_pool)})
            if radio_pool and dow in (0, 3, 6):
                slots.append({"type": "radio_script", "index": next(radio_pool)})
            if quote_pool and dow in (1, 4):
                slots.append({"type": "quote_card", "index": next(quote_pool)})

        strategy[day] = slots

    return strategy


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def save_calendar_csv(entries: list[CalendarEntry], output_path: str | Path) -> Path:
    """Export calendar to CSV.

    Columns: entry_id, date, day_number, week_number, post_time, platform,
             content_type, content_title, caption, hashtags, affiliate_link,
             image_path, status, notes.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not entries:
        output_path.write_text("", encoding="utf-8")
        return output_path

    fieldnames = [
        "entry_id", "date", "day_number", "week_number", "post_time",
        "platform", "content_type", "content_title",
        "caption", "hashtags", "affiliate_link", "image_path",
        "status", "notes",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for e in entries:
            writer.writerow(e.as_flat_dict())

    return output_path


def save_calendar_json(entries: list[CalendarEntry], output_path: str | Path) -> Path:
    """Export calendar to JSON."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(e) for e in entries]
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def calendar_summary(entries: list[CalendarEntry]) -> dict:
    """Return a summary dict of the calendar (for CLI display)."""
    if not entries:
        return {"total": 0}

    platforms: dict[str, int] = {}
    content_types: dict[str, int] = {}
    weeks: dict[int, int] = {}

    for e in entries:
        platforms[e.platform] = platforms.get(e.platform, 0) + 1
        content_types[e.content_type] = content_types.get(e.content_type, 0) + 1
        weeks[e.week_number] = weeks.get(e.week_number, 0) + 1

    return {
        "total": len(entries),
        "date_range": f"{entries[0].date} → {entries[-1].date}",
        "by_platform": platforms,
        "by_content_type": content_types,
        "by_week": {f"week_{k}": v for k, v in sorted(weeks.items())},
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_content(
    content_type: str,
    idx: int,
    radio_scripts: list,
    quote_cards: list,
    listicles: list,
    captions: list,
) -> object | None:
    pools = {
        "radio_script": radio_scripts,
        "quote_card": quote_cards,
        "listicle": listicles,
        "caption": captions,
    }
    pool = pools.get(content_type, [])
    if not pool:
        return None
    return pool[idx % len(pool)]


def _build_caption(obj: object, content_type: str) -> str:
    if content_type == "radio_script":
        return getattr(obj, "hook", "") or ""
    elif content_type == "quote_card":
        return getattr(obj, "caption", "") or ""
    elif content_type == "listicle":
        return getattr(obj, "intro", "") or ""
    elif content_type == "caption":
        return getattr(obj, "text", "") or ""
    return ""


def _get_hashtags(obj: object) -> list[str]:
    return list(getattr(obj, "hashtags", []) or [])


def _get_title(obj: object, content_type: str, idx: int) -> str:
    title = getattr(obj, "title", "")
    if title:
        return str(title)
    return f"{content_type.replace('_', ' ').title()} #{idx + 1}"


def _get_image_path(obj: object, content_type: str) -> str:
    if content_type == "quote_card":
        return str(getattr(obj, "image_path", "") or "")
    return ""


def _get_affiliate_link(obj: object, content_type: str) -> str:
    # Try to extract URL from CTA/caption text
    import re
    text = ""
    if content_type == "radio_script":
        text = getattr(obj, "cta", "") or ""
    elif content_type in ("caption", "quote_card"):
        text = getattr(obj, "text", "") or getattr(obj, "caption", "") or ""
    elif content_type == "listicle":
        text = getattr(obj, "cta", "") or ""
    urls = re.findall(r"https?://\S+", text)
    return urls[0] if urls else ""


def _cycle(items: list):  # type: ignore[return]
    """Infinite cycle over a list."""
    import itertools
    return itertools.cycle(items)


def _infinite_cycle(items: list):  # type: ignore[return]
    """Infinite cycle iterator."""
    import itertools
    return itertools.cycle(items)
