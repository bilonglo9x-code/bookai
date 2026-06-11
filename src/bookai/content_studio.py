"""Content Studio — Generate ready-to-post content from analyzed book chunks."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .models import AnalyzedChunk, BookMetadata, ChunkLabel


class ContentType(str, Enum):
    """Types of generated content."""

    RADIO_SCRIPT = "radio_script"
    QUOTE_CARD = "quote_card"
    LISTICLE = "listicle"
    CAPTION = "caption"


@dataclass
class RadioScript:
    """A TikTok/Reels radio-style narration script (90-150s)."""

    title: str
    hook: str
    body: str
    cta: str
    hashtags: list[str]
    estimated_seconds: int = 0
    source_chunks: list[str] = field(default_factory=list)

    @property
    def full_script(self) -> str:
        return f"{self.hook}\n\n{self.body}\n\n{self.cta}"

    def model_dump(self) -> dict:
        return {
            "type": ContentType.RADIO_SCRIPT.value,
            "title": self.title,
            "hook": self.hook,
            "body": self.body,
            "cta": self.cta,
            "full_script": self.full_script,
            "hashtags": self.hashtags,
            "estimated_seconds": self.estimated_seconds,
            "source_chunks": self.source_chunks,
        }


@dataclass
class QuoteCard:
    """A visual quote card for Instagram/Pinterest."""

    quote_text: str
    book_title: str
    author: str
    caption: str
    hashtags: list[str]
    source_chunk_id: str = ""

    def model_dump(self) -> dict:
        return {
            "type": ContentType.QUOTE_CARD.value,
            "quote_text": self.quote_text,
            "book_title": self.book_title,
            "author": self.author,
            "caption": self.caption,
            "hashtags": self.hashtags,
            "source_chunk_id": self.source_chunk_id,
        }


@dataclass
class Listicle:
    """A listicle/carousel post — "X bai hoc tu [sach]"."""

    title: str
    items: list[str]
    intro: str
    cta: str
    hashtags: list[str]
    source_chunks: list[str] = field(default_factory=list)

    def model_dump(self) -> dict:
        return {
            "type": ContentType.LISTICLE.value,
            "title": self.title,
            "items": self.items,
            "intro": self.intro,
            "cta": self.cta,
            "hashtags": self.hashtags,
            "source_chunks": self.source_chunks,
        }


@dataclass
class Caption:
    """A social media caption with hashtags, optimized for TikTok SEO."""

    text: str
    hashtags: list[str]
    platform: str = "tiktok"
    content_ref: str = ""

    def model_dump(self) -> dict:
        return {
            "type": ContentType.CAPTION.value,
            "text": self.text,
            "hashtags": self.hashtags,
            "platform": self.platform,
            "content_ref": self.content_ref,
        }


# ---------------------------------------------------------------------------
# Hashtag helpers
# ---------------------------------------------------------------------------

_BASE_HASHTAGS = ["sachhay", "reviewsach", "sachtamly", "baihoccuocsong"]

_LABEL_HASHTAGS: dict[ChunkLabel, list[str]] = {
    ChunkLabel.QUOTE: ["caunoihay", "trichdansach", "quotesach"],
    ChunkLabel.STORY: ["cauchuyenhay", "storytelling"],
    ChunkLabel.INSIGHT: ["baihocsach", "tuduymoi"],
    ChunkLabel.HOOK: ["sachgaynghien", "sachhaynendoc"],
    ChunkLabel.TIP: ["meo", "kynang", "tips"],
    ChunkLabel.CONTROVERSIAL: ["trietlycuocsong", "suththat"],
    ChunkLabel.EXAMPLE: ["viduhay", "kienthuc"],
    ChunkLabel.SUMMARY: ["tomtatsach", "reviewsach"],
}


def _build_hashtags(
    labels: list[ChunkLabel], book_title: str, extra: list[str] | None = None
) -> list[str]:
    """Build a de-duped hashtag list from labels + book title."""
    tags: list[str] = list(_BASE_HASHTAGS)
    for lbl in labels:
        tags.extend(_LABEL_HASHTAGS.get(lbl, []))
    # Slug the book title into a hashtag
    slug = book_title.lower().replace(" ", "").replace("-", "")[:30]
    if slug:
        tags.append(slug)
    if extra:
        tags.extend(extra)
    # De-dup while keeping order
    seen: set[str] = set()
    result: list[str] = []
    for t in tags:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            result.append(t)
    return result[:8]  # TikTok recommends 3-8 hashtags


def _estimate_read_seconds(text: str) -> int:
    """Estimate read-aloud duration in seconds (~2.5 words/sec for Vietnamese)."""
    words = len(text.split())
    return max(15, int(words / 2.5))


def _extract_best_sentence(text: str, max_len: int = 200) -> str:
    """Pick the first strong sentence from a chunk (for quotes)."""
    # Split on Vietnamese sentence enders
    sentences = []
    for sep in [".", "!", "?"]:
        for part in text.split(sep):
            part = part.strip()
            if 20 < len(part) <= max_len:
                sentences.append(part + sep)

    if not sentences:
        # Fallback: first max_len chars
        return text[:max_len].rsplit(" ", 1)[0] + "..."

    # Prefer sentences with emotional/action words
    _boost = [
        "bạn", "chúng ta", "tại sao", "hãy", "đừng", "sự thật",
        "không ai", "mọi người", "bí mật", "sai lầm", "thay đổi",
    ]
    scored = []
    for s in sentences:
        score = sum(1 for w in _boost if w in s.lower())
        scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1]


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


def generate_radio_scripts(
    analyzed: list[AnalyzedChunk],
    metadata: BookMetadata,
    max_scripts: int = 5,
    min_score: float = 6.0,
) -> list[RadioScript]:
    """Generate radio narration scripts (90-150s) from top-scored chunks.

    Format inspired by @sachhayexpress: hook -> body points -> CTA.
    """
    # Pick chunks suitable for radio: high score, has insight/story/tip
    radio_labels = {ChunkLabel.INSIGHT, ChunkLabel.STORY, ChunkLabel.TIP,
                    ChunkLabel.HOOK, ChunkLabel.CONTROVERSIAL}
    candidates = sorted(
        [a for a in analyzed
         if a.viral_score >= min_score and radio_labels & set(a.labels)],
        key=lambda a: -a.viral_score,
    )

    scripts: list[RadioScript] = []
    used_ids: set[str] = set()

    for chunk_data in candidates:
        if len(scripts) >= max_scripts:
            break
        cid = chunk_data.chunk.chunk_id
        if cid in used_ids:
            continue
        used_ids.add(cid)

        text = chunk_data.chunk.text.strip()
        summary = chunk_data.summary or ""

        # --- Hook (3-5s): a curiosity-gap opener ---
        hook = _make_hook(chunk_data, metadata)

        # --- Body: the main points from the chunk ---
        body = _make_body(text, summary)

        # --- CTA (call to action) ---
        cta = (
            f'Nếu bạn muốn tìm hiểu sâu hơn, hãy đọc cuốn "{metadata.title}" '
            f"của tác giả {metadata.author}. Link sách ở giỏ hàng bên dưới."
        )

        hashtags = _build_hashtags(chunk_data.labels, metadata.title)
        full = f"{hook}\n\n{body}\n\n{cta}"
        est = _estimate_read_seconds(full)

        scripts.append(RadioScript(
            title=f"Radio Sách: {metadata.title}",
            hook=hook,
            body=body,
            cta=cta,
            hashtags=hashtags,
            estimated_seconds=est,
            source_chunks=[cid],
        ))

    return scripts


def generate_quote_cards(
    analyzed: list[AnalyzedChunk],
    metadata: BookMetadata,
    max_cards: int = 10,
    min_score: float = 5.0,
) -> list[QuoteCard]:
    """Generate quote card content from chunks labelled as quote/insight."""
    candidates = sorted(
        [a for a in analyzed
         if a.viral_score >= min_score
         and (ChunkLabel.QUOTE in a.labels or ChunkLabel.INSIGHT in a.labels)],
        key=lambda a: -a.viral_score,
    )

    cards: list[QuoteCard] = []
    for chunk_data in candidates[:max_cards]:
        quote = _extract_best_sentence(chunk_data.chunk.text)
        caption = (
            f'"{quote[:80]}..." '
            f'- Trích "{metadata.title}" ({metadata.author})\n\n'
            f"Save lại nếu bạn thấy hay!"
        )
        hashtags = _build_hashtags(chunk_data.labels, metadata.title, ["quotesach"])
        cards.append(QuoteCard(
            quote_text=quote,
            book_title=metadata.title,
            author=metadata.author,
            caption=caption,
            hashtags=hashtags,
            source_chunk_id=chunk_data.chunk.chunk_id,
        ))

    return cards


def generate_listicles(
    analyzed: list[AnalyzedChunk],
    metadata: BookMetadata,
    max_listicles: int = 3,
    items_per_list: int = 5,
    min_score: float = 5.0,
) -> list[Listicle]:
    """Generate listicle / carousel posts — "X bai hoc tu [sach]".

    Groups chunks by label type, then builds a numbered-item list.
    """
    # Group by primary label
    label_groups: dict[ChunkLabel, list[AnalyzedChunk]] = {}
    for a in analyzed:
        if a.viral_score < min_score:
            continue
        for lbl in a.labels:
            label_groups.setdefault(lbl, []).append(a)

    _label_titles = {
        ChunkLabel.INSIGHT: "bài học",
        ChunkLabel.TIP: "mẹo hay",
        ChunkLabel.STORY: "câu chuyện hay",
        ChunkLabel.QUOTE: "câu nói đáng suy ngẫm",
        ChunkLabel.CONTROVERSIAL: "quan điểm gây tranh luận",
        ChunkLabel.EXAMPLE: "ví dụ thú vị",
    }

    listicles: list[Listicle] = []
    for lbl in [ChunkLabel.INSIGHT, ChunkLabel.TIP, ChunkLabel.QUOTE,
                ChunkLabel.STORY, ChunkLabel.CONTROVERSIAL]:
        if len(listicles) >= max_listicles:
            break
        items_pool = label_groups.get(lbl, [])
        if len(items_pool) < 3:
            continue
        # Top N by score
        top_items = sorted(items_pool, key=lambda a: -a.viral_score)[:items_per_list]
        label_name = _label_titles.get(lbl, lbl.value)
        n = len(top_items)

        items: list[str] = []
        chunk_ids: list[str] = []
        for idx, a in enumerate(top_items, 1):
            summary = a.summary or _extract_best_sentence(a.chunk.text, max_len=150)
            items.append(f"{idx}. {summary}")
            chunk_ids.append(a.chunk.chunk_id)

        title = f"{n} {label_name} từ \"{metadata.title}\""
        intro = (
            f"Cuốn \"{metadata.title}\" của {metadata.author} ẩn chứa "
            f"rất nhiều {label_name} đáng suy ngẫm. Đây là {n} {label_name} "
            f"hay nhất mà mình tổng hợp được:"
        )
        cta = (
            f"Bạn thích {label_name} số mấy nhất? Comment bên dưới nhé! "
            f"Link sách ở giỏ hàng."
        )
        hashtags = _build_hashtags([lbl], metadata.title, ["top" + str(n)])

        listicles.append(Listicle(
            title=title,
            items=items,
            intro=intro,
            cta=cta,
            hashtags=hashtags,
            source_chunks=chunk_ids,
        ))

    return listicles


def generate_captions(
    analyzed: list[AnalyzedChunk],
    metadata: BookMetadata,
    max_captions: int = 10,
    platform: str = "tiktok",
    min_score: float = 6.0,
) -> list[Caption]:
    """Generate platform-optimized captions for top content."""
    top = sorted(
        [a for a in analyzed if a.viral_score >= min_score],
        key=lambda a: -a.viral_score,
    )[:max_captions]

    captions: list[Caption] = []
    for chunk_data in top:
        summary = chunk_data.summary or _extract_best_sentence(
            chunk_data.chunk.text, max_len=120
        )
        hashtags = _build_hashtags(chunk_data.labels, metadata.title)
        tags_str = " ".join(f"#{t}" for t in hashtags)

        if platform == "tiktok":
            text = (
                f"{summary}\n\n"
                f'Trích từ "{metadata.title}" - {metadata.author}\n'
                f"Link sách ở giỏ hàng bên dưới\n\n"
                f"{tags_str}"
            )
        elif platform == "instagram":
            text = (
                f"{summary}\n\n"
                f'Cuốn sách: "{metadata.title}" - {metadata.author}\n'
                f".\n.\n.\n"
                f"Save lại nếu thấy hay!\n"
                f"{tags_str}"
            )
        else:
            text = f"{summary}\n\n{tags_str}"

        captions.append(Caption(
            text=text,
            hashtags=hashtags,
            platform=platform,
            content_ref=chunk_data.chunk.chunk_id,
        ))

    return captions


# ---------------------------------------------------------------------------
# Aggregate: generate all content types at once
# ---------------------------------------------------------------------------


@dataclass
class ContentPack:
    """All generated content from a single book analysis."""

    book_title: str
    author: str
    radio_scripts: list[RadioScript] = field(default_factory=list)
    quote_cards: list[QuoteCard] = field(default_factory=list)
    listicles: list[Listicle] = field(default_factory=list)
    captions: list[Caption] = field(default_factory=list)

    @property
    def total_pieces(self) -> int:
        return (
            len(self.radio_scripts)
            + len(self.quote_cards)
            + len(self.listicles)
            + len(self.captions)
        )

    def model_dump(self) -> dict:
        return {
            "book_title": self.book_title,
            "author": self.author,
            "total_pieces": self.total_pieces,
            "radio_scripts": [s.model_dump() for s in self.radio_scripts],
            "quote_cards": [q.model_dump() for q in self.quote_cards],
            "listicles": [ls.model_dump() for ls in self.listicles],
            "captions": [c.model_dump() for c in self.captions],
        }


def generate_all(
    analyzed: list[AnalyzedChunk],
    metadata: BookMetadata,
) -> ContentPack:
    """Generate all content types from analyzed chunks."""
    return ContentPack(
        book_title=metadata.title,
        author=metadata.author,
        radio_scripts=generate_radio_scripts(analyzed, metadata),
        quote_cards=generate_quote_cards(analyzed, metadata),
        listicles=generate_listicles(analyzed, metadata),
        captions=generate_captions(analyzed, metadata),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_hook(chunk_data: AnalyzedChunk, metadata: BookMetadata) -> str:
    """Create a curiosity-gap hook for a radio script."""
    text = chunk_data.chunk.text
    labels = set(chunk_data.labels)

    # Try to extract the first provocative sentence
    first_sentence = _extract_best_sentence(text, max_len=120)

    if ChunkLabel.CONTROVERSIAL in labels:
        return f"Bạn có biết rằng {first_sentence.lower()}"
    if ChunkLabel.STORY in labels:
        return f"Có một câu chuyện thế này... {first_sentence}"
    if ChunkLabel.HOOK in labels:
        return first_sentence
    if ChunkLabel.INSIGHT in labels:
        return (
            f"Trong cuốn \"{metadata.title}\", tác giả {metadata.author} "
            f"chia sẻ một bài học quan trọng..."
        )
    return f"Đây là điều ít người biết: {first_sentence}"


def _make_body(text: str, summary: str) -> str:
    """Create the main body for a radio script from chunk text + summary."""
    # Use summary if available, otherwise extract key sentences
    if summary and len(summary) > 30:
        body = summary
    else:
        # Extract 3-5 key sentences
        sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".")
                     if len(s.strip()) > 20]
        body = ". ".join(sentences[:5]) + "."

    # Keep body within radio length (roughly 200-400 words for 90-150s)
    words = body.split()
    if len(words) > 400:
        body = " ".join(words[:400]) + "..."
    return body


# ---------------------------------------------------------------------------
# AI Rewrite — Use LLM to produce polished radio scripts
# ---------------------------------------------------------------------------

_RADIO_REWRITE_PROMPT = """Bạn là scriptwriter chuyên viết kịch bản "radio sách" cho TikTok/Reels.
Phong cách: giống kênh @sachhayexpress (660K followers).

Từ đoạn sách dưới đây, viết 1 kịch bản radio sách hoàn chỉnh.

THÔNG TIN:
- Tên sách: {book_title}
- Tác giả: {author}
- Đoạn sách:
---
{chunk_text}
---

YÊU CẦU:
1. HOOK (1-2 câu mở đầu gây sốc/tò mò, khiến người ta dừng scroll)
2. BODY (nội dung chính 4-8 câu, dạng listicle tips ngắn gọn, dễ hiểu)
3. CTA (1-2 câu kêu gọi mua sách, tự nhiên không ép)

FORMAT trả về JSON:
{{
  "hook": "...",
  "body": "...",
  "cta": "...",
  "title": "tiêu đề ngắn cho video"
}}

Lưu ý:
- Giọng văn tự nhiên, conversational, như đang NÓI chứ không viết
- Dùng "bạn" để nói chuyện trực tiếp với người nghe
- Tổng kịch bản 90-150 giây khi đọc (khoảng 220-370 từ)
- KHÔNG dùng emoji, KHÔNG dùng tiếng Anh
- Chỉ trả về JSON, không giải thích thêm."""

_CAPTION_REWRITE_PROMPT = """Viết caption TikTok hấp dẫn cho đoạn sách sau.

Tên sách: {book_title}
Tác giả: {author}
Nội dung đoạn:
---
{chunk_text}
---

YÊU CẦU:
- Caption ngắn gọn 2-4 câu, gây tò mò
- Kết bằng CTA nhẹ (hỏi ý kiến hoặc mời mua sách)
- Không emoji, không tiếng Anh
- Tối ưu SEO TikTok (keyword ở đầu caption)

Trả về JSON:
{{
  "caption": "nội dung caption",
  "hook_keyword": "keyword chính cho SEO"
}}"""


def _call_llm_for_rewrite(
    prompt: str,
    api_key: str | None = None,
    model: str = "gpt-4o-mini",
    base_url: str | None = None,
) -> str:
    """Call LLM for content rewriting (uses same infrastructure as analyzer)."""
    import httpx

    api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("key_api", "")
    if not api_key:
        raise ValueError("No API key available for AI rewrite")

    url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not url.endswith("/chat/completions"):
        url = url.rstrip("/") + "/chat/completions"

    response = httpx.post(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 2000,
            "stream": False,
        },
        timeout=120.0,
    )
    response.raise_for_status()

    # Handle SSE streaming responses
    text = response.text.strip()
    if text.startswith("data: "):
        content_parts = []
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("data: ") and line != "data: [DONE]":
                try:
                    chunk_data = json.loads(line[6:])
                    delta = chunk_data.get("choices", [{}])[0]
                    if "message" in delta:
                        content_parts.append(delta["message"].get("content", ""))
                    elif "delta" in delta:
                        content_parts.append(delta["delta"].get("content", ""))
                except (json.JSONDecodeError, IndexError, KeyError):
                    continue
        return "".join(content_parts)

    data = response.json()
    return data["choices"][0]["message"]["content"]


def ai_rewrite_radio_scripts(
    analyzed: list[AnalyzedChunk],
    metadata: BookMetadata,
    max_scripts: int = 5,
    min_score: float = 6.0,
    api_key: str | None = None,
    model: str = "gpt-4o-mini",
    base_url: str | None = None,
) -> list[RadioScript]:
    """Generate radio scripts using AI rewriting for higher quality.

    Unlike generate_radio_scripts() which uses templates, this function
    sends each chunk to an LLM with a scriptwriter prompt to produce
    polished, natural-sounding radio scripts.
    """
    radio_labels = {ChunkLabel.INSIGHT, ChunkLabel.STORY, ChunkLabel.TIP,
                    ChunkLabel.HOOK, ChunkLabel.CONTROVERSIAL}
    candidates = sorted(
        [a for a in analyzed
         if a.viral_score >= min_score and radio_labels & set(a.labels)],
        key=lambda a: -a.viral_score,
    )

    scripts: list[RadioScript] = []
    used_ids: set[str] = set()

    for chunk_data in candidates:
        if len(scripts) >= max_scripts:
            break
        cid = chunk_data.chunk.chunk_id
        if cid in used_ids:
            continue
        used_ids.add(cid)

        prompt = _RADIO_REWRITE_PROMPT.format(
            book_title=metadata.title,
            author=metadata.author,
            chunk_text=chunk_data.chunk.text[:2000],
        )

        try:
            response_text = _call_llm_for_rewrite(
                prompt, api_key=api_key, model=model, base_url=base_url
            )
            # Parse JSON response
            text = response_text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text)

            hook = data.get("hook", "")
            body = data.get("body", "")
            cta = data.get("cta", "")
            title = data.get("title", f"Radio Sách: {metadata.title}")

            if not hook or not body:
                continue

            hashtags = _build_hashtags(chunk_data.labels, metadata.title)
            full = f"{hook}\n\n{body}\n\n{cta}"
            est = _estimate_read_seconds(full)

            scripts.append(RadioScript(
                title=title,
                hook=hook,
                body=body,
                cta=cta,
                hashtags=hashtags,
                estimated_seconds=est,
                source_chunks=[cid],
            ))
        except Exception:
            # Fallback to template-based generation
            text = chunk_data.chunk.text.strip()
            summary = chunk_data.summary or ""
            hook = _make_hook(chunk_data, metadata)
            body = _make_body(text, summary)
            cta = (
                f'Nếu bạn muốn tìm hiểu sâu hơn, hãy đọc cuốn "{metadata.title}" '
                f"của tác giả {metadata.author}. Link sách ở giỏ hàng bên dưới."
            )
            hashtags = _build_hashtags(chunk_data.labels, metadata.title)
            full = f"{hook}\n\n{body}\n\n{cta}"
            est = _estimate_read_seconds(full)
            scripts.append(RadioScript(
                title=f"Radio Sách: {metadata.title}",
                hook=hook,
                body=body,
                cta=cta,
                hashtags=hashtags,
                estimated_seconds=est,
                source_chunks=[cid],
            ))

    return scripts


def ai_rewrite_captions(
    analyzed: list[AnalyzedChunk],
    metadata: BookMetadata,
    max_captions: int = 10,
    min_score: float = 6.0,
    api_key: str | None = None,
    model: str = "gpt-4o-mini",
    base_url: str | None = None,
    platform: str = "tiktok",
) -> list[Caption]:
    """Generate AI-rewritten captions optimized for TikTok SEO."""
    top = sorted(
        [a for a in analyzed if a.viral_score >= min_score],
        key=lambda a: -a.viral_score,
    )[:max_captions]

    captions: list[Caption] = []
    for chunk_data in top:
        prompt = _CAPTION_REWRITE_PROMPT.format(
            book_title=metadata.title,
            author=metadata.author,
            chunk_text=chunk_data.chunk.text[:1500],
        )

        try:
            response_text = _call_llm_for_rewrite(
                prompt, api_key=api_key, model=model, base_url=base_url
            )
            text = response_text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text)

            caption_text = data.get("caption", "")
            if not caption_text:
                continue

            hashtags = _build_hashtags(chunk_data.labels, metadata.title)
            tags_str = " ".join(f"#{t}" for t in hashtags)
            full_text = f"{caption_text}\n\n{tags_str}"

            captions.append(Caption(
                text=full_text,
                hashtags=hashtags,
                platform=platform,
                content_ref=chunk_data.chunk.chunk_id,
            ))
        except Exception:
            # Fallback to template caption
            summary = chunk_data.summary or _extract_best_sentence(
                chunk_data.chunk.text, max_len=120
            )
            hashtags = _build_hashtags(chunk_data.labels, metadata.title)
            tags_str = " ".join(f"#{t}" for t in hashtags)
            text_out = (
                f"{summary}\n\n"
                f'Trích từ "{metadata.title}" - {metadata.author}\n'
                f"Link sách ở giỏ hàng bên dưới\n\n"
                f"{tags_str}"
            )
            captions.append(Caption(
                text=text_out,
                hashtags=hashtags,
                platform=platform,
                content_ref=chunk_data.chunk.chunk_id,
            ))

    return captions


# ---------------------------------------------------------------------------
# Quote card image generation
# ---------------------------------------------------------------------------


def generate_quote_images(
    analyzed: list[AnalyzedChunk],
    metadata: BookMetadata,
    output_dir: str | Path,
    max_cards: int = 10,
    min_score: float = 5.0,
    theme: str = "dark",
) -> list[Path]:
    """Generate quote card PNG images from analyzed chunks.

    Returns list of paths to generated images.
    """
    from .quote_renderer import render_quote_cards_batch

    candidates = sorted(
        [a for a in analyzed
         if a.viral_score >= min_score
         and (ChunkLabel.QUOTE in a.labels or ChunkLabel.INSIGHT in a.labels)],
        key=lambda a: -a.viral_score,
    )[:max_cards]

    quotes = []
    for chunk_data in candidates:
        quote = _extract_best_sentence(chunk_data.chunk.text)
        quotes.append({
            "quote_text": quote,
            "book_title": metadata.title,
            "author": metadata.author,
        })

    if not quotes:
        return []

    return render_quote_cards_batch(quotes, output_dir=output_dir, theme=theme)


def generate_all_with_ai(
    analyzed: list[AnalyzedChunk],
    metadata: BookMetadata,
    api_key: str | None = None,
    model: str = "gpt-4o-mini",
    base_url: str | None = None,
    output_dir: str | Path | None = None,
    image_theme: str = "dark",
) -> ContentPack:
    """Generate all content types using AI rewriting for premium quality.

    This is the AI-powered version of generate_all(). It uses LLM to
    rewrite radio scripts and captions for more natural, engaging output.
    Also generates quote card images if output_dir is provided.
    """
    radio = ai_rewrite_radio_scripts(
        analyzed, metadata,
        api_key=api_key, model=model, base_url=base_url,
    )
    quotes = generate_quote_cards(analyzed, metadata)
    listicles = generate_listicles(analyzed, metadata)
    captions = ai_rewrite_captions(
        analyzed, metadata,
        api_key=api_key, model=model, base_url=base_url,
    )

    # Generate images if output directory provided
    if output_dir:
        generate_quote_images(
            analyzed, metadata,
            output_dir=output_dir,
            theme=image_theme,
        )

    return ContentPack(
        book_title=metadata.title,
        author=metadata.author,
        radio_scripts=radio,
        quote_cards=quotes,
        listicles=listicles,
        captions=captions,
    )
