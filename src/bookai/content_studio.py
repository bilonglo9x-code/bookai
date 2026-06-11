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


@dataclass
class Scene:
    """A single scene in a video storyboard."""

    scene_number: int
    duration_seconds: str
    narration: str
    visual_prompt: str
    camera_note: str = ""

    def model_dump(self) -> dict:
        return {
            "scene_number": self.scene_number,
            "duration_seconds": self.duration_seconds,
            "narration": self.narration,
            "visual_prompt": self.visual_prompt,
            "camera_note": self.camera_note,
        }


@dataclass
class Storyboard:
    """Full video storyboard with scenes for AI video generation."""

    script_title: str
    total_scenes: int
    scenes: list[Scene]
    style_note: str = ""
    aspect_ratio: str = "9:16"

    def model_dump(self) -> dict:
        return {
            "script_title": self.script_title,
            "total_scenes": self.total_scenes,
            "scenes": [s.model_dump() for s in self.scenes],
            "style_note": self.style_note,
            "aspect_ratio": self.aspect_ratio,
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


def _split_complete_sentences(text: str) -> list[str]:
    """Split text into complete Vietnamese sentences.

    Handles Vietnamese punctuation properly, avoiding cuts mid-sentence.
    Cleans up line breaks within sentences.
    """
    import re as _re
    # First, normalize line breaks within sentences (PDF often breaks mid-line)
    clean = _re.sub(r'\n(?![A-ZĐ\d\-\(])', ' ', text)  # Join lines that don't start a new sentence
    clean = _re.sub(r'\s{2,}', ' ', clean)
    # Split on sentence-ending punctuation followed by space/newline
    parts = _re.split(r'(?<=[.!?…])[\s\n]+', clean)
    sentences = []
    for p in parts:
        p = p.strip()
        if len(p) >= 15:  # Skip very short fragments
            sentences.append(p)
    return sentences


def _extract_best_quote(text: str, min_len: int = 40, max_len: int = 300) -> str:
    """Extract the best complete sentence(s) for a quote card.

    Picks 1-3 complete sentences that form a meaningful, self-contained quote.
    Prioritizes sentences with emotional/philosophical content.
    """
    sentences = _split_complete_sentences(text)

    if not sentences:
        # Fallback: take text up to first natural break
        clean = text.replace('\n', ' ').strip()
        if len(clean) <= max_len:
            return clean
        # Find last sentence end within max_len
        for end in ['.', '!', '?', '…']:
            idx = clean.rfind(end, 0, max_len)
            if idx > min_len:
                return clean[:idx + 1]
        return clean[:max_len].rsplit(' ', 1)[0] + '...'

    # Score each sentence for "quotability"
    _boost = [
        'bạn', 'chúng ta', 'tại sao', 'hãy', 'đừng', 'sự thật',
        'không ai', 'mọi người', 'bí mật', 'sai lầm', 'thay đổi',
        'cuộc sống', 'hạnh phúc', 'đau khổ', 'tâm trí', 'ý thức',
        'tỉnh thức', 'hiện tại', 'bản ngã', 'tự do', 'sợ hãi',
    ]
    scored: list[tuple[float, int, str]] = []
    for i, s in enumerate(sentences):
        if len(s) < min_len or len(s) > max_len:
            continue
        score = sum(1 for w in _boost if w in s.lower())
        # Bonus for sentences that start with a strong opening
        if any(s.startswith(w) for w in ['Khi', 'Nếu', 'Sự', 'Bạn', 'Đừng', 'Hãy']):
            score += 1
        scored.append((score, i, s))

    if scored:
        scored.sort(key=lambda x: -x[0])
        best = scored[0][2]
        # If best sentence is short, try to combine with next sentence
        if len(best) < 80 and scored[0][1] + 1 < len(sentences):
            next_sent = sentences[scored[0][1] + 1]
            combined = best + ' ' + next_sent
            if len(combined) <= max_len:
                return combined
        return best

    # Fallback: combine first 2-3 sentences up to max_len
    combined = ''
    for s in sentences:
        if len(combined) + len(s) + 1 <= max_len:
            combined = (combined + ' ' + s).strip()
        else:
            break
    return combined if combined else text[:max_len].rsplit(' ', 1)[0] + '...'


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
    Combines 2-4 related chunks to achieve 90-150s duration (~300-500 words).
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

    for primary in candidates:
        if len(scripts) >= max_scripts:
            break
        cid = primary.chunk.chunk_id
        if cid in used_ids:
            continue
        used_ids.add(cid)

        # Gather related chunks to form a longer script (target 300-500 words)
        related_chunks = _find_related_chunks(primary, candidates, used_ids, target_words=400)
        for rc in related_chunks:
            used_ids.add(rc.chunk.chunk_id)

        all_chunks = [primary] + related_chunks
        combined_text = '\n\n'.join(c.chunk.text.strip() for c in all_chunks)
        chunk_ids = [c.chunk.chunk_id for c in all_chunks]

        # --- Hook (3-5s): a curiosity-gap opener ---
        hook = _make_hook(primary, metadata)

        # --- Body: full content from combined chunks ---
        body = _make_body_long(combined_text, target_words=400)

        # --- CTA (call to action) ---
        cta = (
            f'Nếu bạn muốn khám phá thêm nhiều bài học sâu sắc như thế này, '
            f'hãy đọc cuốn "{metadata.title}" của tác giả {metadata.author}. '
            f'Link mua sách ở giỏ hàng bên dưới video nhé.'
        )

        hashtags = _build_hashtags(primary.labels, metadata.title)
        full = f"{hook}\n\n{body}\n\n{cta}"
        est = _estimate_read_seconds(full)

        scripts.append(RadioScript(
            title=f"Radio Sách: {metadata.title}",
            hook=hook,
            body=body,
            cta=cta,
            hashtags=hashtags,
            estimated_seconds=est,
            source_chunks=chunk_ids,
        ))

    return scripts


def generate_quote_cards(
    analyzed: list[AnalyzedChunk],
    metadata: BookMetadata,
    max_cards: int = 10,
    min_score: float = 5.0,
) -> list[QuoteCard]:
    """Generate quote card content from chunks labelled as quote/insight.

    Extracts complete, meaningful sentences that work as standalone quotes.
    """
    candidates = sorted(
        [a for a in analyzed
         if a.viral_score >= min_score
         and (ChunkLabel.QUOTE in a.labels or ChunkLabel.INSIGHT in a.labels)],
        key=lambda a: -a.viral_score,
    )

    cards: list[QuoteCard] = []
    seen_quotes: set[str] = set()  # Avoid duplicate/similar quotes

    for chunk_data in candidates:
        if len(cards) >= max_cards:
            break

        quote = _extract_best_quote(chunk_data.chunk.text, min_len=40, max_len=280)

        # Skip if too similar to existing quote
        quote_key = quote[:50].lower()
        if quote_key in seen_quotes:
            continue
        seen_quotes.add(quote_key)

        # Build a proper caption with the full quote
        short_quote = quote if len(quote) <= 100 else quote[:97] + '...'
        caption = (
            f'"{short_quote}"\n\n'
            f'— {metadata.author}, "{metadata.title}"\n\n'
            f'Save lại nếu bạn thấy hay! Link sách ở giỏ hàng.'
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
            summary = a.summary or _extract_best_quote(a.chunk.text, min_len=30, max_len=200)
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
        summary = chunk_data.summary or _extract_best_quote(
            chunk_data.chunk.text, min_len=30, max_len=150
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
    """Create a curiosity-gap hook for a radio script (1-2 sentences, gây tò mò)."""
    text = chunk_data.chunk.text
    labels = set(chunk_data.labels)
    sentences = _split_complete_sentences(text)

    # Get first strong sentence
    first_sentence = ''
    if sentences:
        # Find a short, punchy sentence for the hook
        for s in sentences[:3]:
            if 20 <= len(s) <= 150:
                first_sentence = s
                break
        if not first_sentence:
            first_sentence = sentences[0][:150]
    else:
        first_sentence = text[:150].rsplit(' ', 1)[0]

    if ChunkLabel.CONTROVERSIAL in labels:
        return (
            f"Có một sự thật mà ít người dám nói ra. {first_sentence}"
        )
    if ChunkLabel.STORY in labels:
        return (
            f"Có một câu chuyện thế này mà khi nghe xong, bạn sẽ nhìn "
            f"cuộc sống khác đi hoàn toàn. {first_sentence}"
        )
    if ChunkLabel.HOOK in labels:
        return first_sentence
    if ChunkLabel.INSIGHT in labels:
        return (
            f"Tác giả {metadata.author} đã chỉ ra một điều cực kỳ quan trọng "
            f"mà hầu hết chúng ta đều bỏ qua. {first_sentence}"
        )
    return f"Bạn có bao giờ tự hỏi... {first_sentence}"


def _make_body(text: str, summary: str) -> str:
    """Create the main body for a radio script from chunk text + summary.

    Legacy function for backward compatibility with single-chunk scripts.
    """
    return _make_body_long(text, target_words=400)


def _make_body_long(text: str, target_words: int = 400) -> str:
    """Create a full radio script body (300-500 words) from combined text.

    Extracts complete sentences, preserving paragraph structure and
    natural flow. Target: 90-150 seconds of narration.
    """
    # Clean up the text
    clean = text.replace('\n', ' ').strip()
    import re as _re
    clean = _re.sub(r'\s{2,}', ' ', clean)

    sentences = _split_complete_sentences(clean)
    if not sentences:
        # Fallback to raw text
        words = clean.split()
        return ' '.join(words[:target_words])

    # Build body from complete sentences until we hit target word count
    body_parts: list[str] = []
    word_count = 0
    min_words = int(target_words * 0.7)  # At least 70% of target

    for sent in sentences:
        sent_words = len(sent.split())
        if word_count + sent_words > target_words + 50 and word_count >= min_words:
            break
        body_parts.append(sent)
        word_count += sent_words

    # If we got too little content, just use what we have
    if not body_parts:
        words = clean.split()
        return ' '.join(words[:target_words])

    return ' '.join(body_parts)


def _find_related_chunks(
    primary: AnalyzedChunk,
    candidates: list[AnalyzedChunk],
    used_ids: set[str],
    target_words: int = 400,
) -> list[AnalyzedChunk]:
    """Find chunks related to the primary chunk to build a longer script.

    Looks for chunks from the same chapter or with overlapping labels.
    """
    primary_words = len(primary.chunk.text.split())
    if primary_words >= target_words:
        return []  # Primary chunk is already long enough

    needed_words = target_words - primary_words
    related: list[AnalyzedChunk] = []
    collected_words = 0

    # Prefer chunks from same chapter, then same labels
    for candidate in candidates:
        if collected_words >= needed_words:
            break
        cid = candidate.chunk.chunk_id
        if cid in used_ids or cid == primary.chunk.chunk_id:
            continue

        # Check relatedness: same chapter or overlapping labels
        same_chapter = candidate.chunk.chapter == primary.chunk.chapter
        shared_labels = set(candidate.labels) & set(primary.labels)

        if same_chapter or len(shared_labels) >= 1:
            related.append(candidate)
            collected_words += len(candidate.chunk.text.split())

    return related[:3]  # Max 3 additional chunks


# ---------------------------------------------------------------------------
# AI Rewrite — Use LLM to produce polished radio scripts
# ---------------------------------------------------------------------------

_RADIO_REWRITE_PROMPT = """Bạn là scriptwriter viết kịch bản radio sách dài cho TikTok/YouTube.
Phong cách: @sachhayexpress — giọng kể chuyện trầm, sâu lắng, triết lý.

Từ đoạn trích sách dưới đây, hãy VIẾT LẠI thành kịch bản radio hoàn chỉnh {duration_target}.
KHÔNG chỉ copy nguyên văn — hãy diễn giải, mở rộng, thêm ví dụ,
kể chuyện để người nghe dễ hiểu.

THÔNG TIN:
- Tên sách: {book_title}
- Tác giả: {author}
- Đoạn trích gốc (dùng làm nguồn ý tưởng, KHÔNG copy nguyên):
---
{chunk_text}
---

CẤU TRÚC KỊCH BẢN:
1. HOOK (2-3 câu mở đầu cực gây tò mò, tạo curiosity gap, khiến người ta PHẢI nghe tiếp)
2. BODY (nội dung chính - PHẢI DÀI {word_target} từ):
   - Giải thích ý tưởng từ sách bằng ngôn ngữ đời thường
   - Thêm ví dụ thực tế, tình huống quen thuộc để minh họa
   - Kể câu chuyện ngắn nếu phù hợp
   - Phân tích sâu hơn, liên hệ với cuộc sống người nghe
   - Có thể chia thành 3-5 điểm chính nếu nội dung dạng listicle
3. CTA (2-3 câu kêu gọi tự nhiên: mua sách để đọc đầy đủ hơn)

FORMAT trả về JSON:
{{
  "hook": "nội dung hook 2-3 câu",
  "body": "nội dung body DÀI {word_target} từ trở lên",
  "cta": "nội dung CTA 2-3 câu",
  "title": "tiêu đề ngắn cho video"
}}

QUAN TRỌNG:
- Body phải DÀI ÍT NHẤT {word_target} từ — đây là video {duration_target}, không phải clip 30 giây
- Giọng văn tự nhiên, conversational, như đang KỂ CHUYỆN cho bạn bè nghe
- Dùng "bạn" để nói chuyện trực tiếp
- Diễn giải bằng ngôn ngữ đơn giản, ai cũng hiểu được
- Thêm câu chuyển đoạn: "Và đây là điều thú vị...",
  "Bạn biết không...", "Hãy tưởng tượng thế này..."
- KHÔNG dùng emoji, KHÔNG dùng tiếng Anh, KHÔNG dùng markdown formatting
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
    max_retries: int = 3,
) -> str:
    """Call LLM for content rewriting (uses same infrastructure as analyzer)."""
    import time as _time

    import httpx

    api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("key_api", "")
    if not api_key:
        raise ValueError("No API key available for AI rewrite")

    url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not url.endswith("/chat/completions"):
        url = url.rstrip("/") + "/chat/completions"

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = httpx.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 4000,
                    "stream": False,
                },
                timeout=180.0,
            )
            response.raise_for_status()
            break
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as e:
            last_error = e
            if attempt < max_retries - 1:
                _time.sleep(3 * (attempt + 1))
            else:
                raise
    else:
        raise last_error  # type: ignore[misc]

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
    duration_minutes: int = 3,
) -> list[RadioScript]:
    """Generate radio scripts using AI rewriting for higher quality.

    Unlike generate_radio_scripts() which uses templates, this function
    sends combined chunks to an LLM which REWRITES and EXPANDS the content
    into polished, natural-sounding radio scripts of 1-5 minutes.

    Args:
        duration_minutes: Target duration in minutes (1-5). Default 3 minutes.
    """
    # Calculate word target based on duration (Vietnamese ~2.5 words/sec)
    duration_minutes = max(1, min(5, duration_minutes))
    word_target = duration_minutes * 150  # ~150 words/min for Vietnamese narration
    duration_target = f"{duration_minutes} phút ({duration_minutes * 60} giây)"

    radio_labels = {ChunkLabel.INSIGHT, ChunkLabel.STORY, ChunkLabel.TIP,
                    ChunkLabel.HOOK, ChunkLabel.CONTROVERSIAL}
    candidates = sorted(
        [a for a in analyzed
         if a.viral_score >= min_score and radio_labels & set(a.labels)],
        key=lambda a: -a.viral_score,
    )

    scripts: list[RadioScript] = []
    used_ids: set[str] = set()

    for primary in candidates:
        if len(scripts) >= max_scripts:
            break
        cid = primary.chunk.chunk_id
        if cid in used_ids:
            continue
        used_ids.add(cid)

        # Gather related chunks to provide MORE source material for AI
        related = _find_related_chunks(primary, candidates, used_ids, target_words=800)
        for rc in related:
            used_ids.add(rc.chunk.chunk_id)

        all_chunks = [primary] + related
        # Combine text from all related chunks (give AI plenty of material)
        combined_text = '\n\n'.join(c.chunk.text.strip() for c in all_chunks)
        chunk_ids = [c.chunk.chunk_id for c in all_chunks]

        # Truncate to reasonable size for API (max ~4000 chars)
        if len(combined_text) > 4000:
            combined_text = combined_text[:4000]

        prompt = _RADIO_REWRITE_PROMPT.format(
            book_title=metadata.title,
            author=metadata.author,
            chunk_text=combined_text,
            duration_target=duration_target,
            word_target=word_target,
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

            hashtags = _build_hashtags(primary.labels, metadata.title)
            full = f"{hook}\n\n{body}\n\n{cta}"
            est = _estimate_read_seconds(full)

            scripts.append(RadioScript(
                title=title,
                hook=hook,
                body=body,
                cta=cta,
                hashtags=hashtags,
                estimated_seconds=est,
                source_chunks=chunk_ids,
            ))
        except Exception:
            # Fallback to template-based generation with long body
            combined_clean = combined_text.replace('\n', ' ')
            hook = _make_hook(primary, metadata)
            body = _make_body_long(combined_clean, target_words=word_target)
            cta = (
                f'Nếu bạn muốn khám phá thêm nhiều bài học sâu sắc như thế này, '
                f'hãy đọc cuốn "{metadata.title}" của tác giả {metadata.author}. '
                f'Link mua sách ở giỏ hàng bên dưới video nhé.'
            )
            hashtags = _build_hashtags(primary.labels, metadata.title)
            full = f"{hook}\n\n{body}\n\n{cta}"
            est = _estimate_read_seconds(full)
            scripts.append(RadioScript(
                title=f"Radio Sách: {metadata.title}",
                hook=hook,
                body=body,
                cta=cta,
                hashtags=hashtags,
                estimated_seconds=est,
                source_chunks=chunk_ids,
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
            summary = chunk_data.summary or _extract_best_quote(
                chunk_data.chunk.text, min_len=30, max_len=150
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
# Storyboard / Scene Prompts — AI Video Generation
# ---------------------------------------------------------------------------

_STORYBOARD_PROMPT = """Bạn là đạo diễn video chuyên phân cảnh cho video sách.
Từ kịch bản radio dưới đây, hãy chia thành 5-8 cảnh (scenes)
với mô tả hình ảnh chi tiết để dùng AI tạo video.

KỊCH BẢN:
---
{script_text}
---

TÊN SÁCH: {book_title}
TÁC GIẢ: {author}

YÊU CẦU mỗi cảnh:
- scene_number: số thứ tự
- duration_seconds: thời lượng cảnh (VD: "8-12")
- narration: phần lời đọc tương ứng cảnh này
- visual_prompt: mô tả hình ảnh/video chi tiết bằng TIẾNG ANH
  (dùng cho Runway/Pika/Midjourney/DALL-E)
  Phong cách: cinematic, moody lighting, book aesthetic
- camera_note: chuyển động camera (zoom in, pan left, static...)

FORMAT JSON:
{{
  "scenes": [
    {{
      "scene_number": 1,
      "duration_seconds": "5-8",
      "narration": "phần lời đọc cảnh 1",
      "visual_prompt": "English visual description for AI",
      "camera_note": "slow zoom in"
    }}
  ],
  "style_note": "ghi chú phong cách chung cho toàn bộ video"
}}

LƯU Ý:
- visual_prompt PHẢI bằng tiếng Anh (AI video tools chỉ hiểu English)
- Phong cách: cinematic, warm/moody lighting, depth of field
- Thêm chi tiết: màu sắc, ánh sáng, góc quay, đối tượng
- Cảnh đầu: hook visual (gây chú ý ngay), cảnh cuối: CTA visual
- Mỗi cảnh 5-15 giây
- Chỉ trả JSON, không giải thích."""


def generate_storyboard(
    script: RadioScript,
    metadata: BookMetadata,
    api_key: str | None = None,
    model: str = "gpt-4o-mini",
    base_url: str | None = None,
) -> Storyboard:
    """Generate a visual storyboard for a radio script.

    Splits the script into scenes with detailed visual prompts
    ready for AI video generators (Runway, Pika, Kling, etc).
    """
    prompt = _STORYBOARD_PROMPT.format(
        script_text=script.full_script,
        book_title=metadata.title,
        author=metadata.author,
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

        scenes = []
        for s in data.get("scenes", []):
            scenes.append(Scene(
                scene_number=s.get("scene_number", 0),
                duration_seconds=str(s.get("duration_seconds", "5-10")),
                narration=s.get("narration", ""),
                visual_prompt=s.get("visual_prompt", ""),
                camera_note=s.get("camera_note", ""),
            ))

        return Storyboard(
            script_title=script.title,
            total_scenes=len(scenes),
            scenes=scenes,
            style_note=data.get("style_note", ""),
        )
    except Exception:
        # Fallback: auto-split script into scenes by sentences
        return _auto_storyboard(script, metadata)


def _auto_storyboard(
    script: RadioScript, metadata: BookMetadata
) -> Storyboard:
    """Fallback storyboard: split script into scenes by paragraphs."""
    scenes: list[Scene] = []
    parts = [script.hook, script.body, script.cta]
    labels = ["hook", "body", "cta"]

    scene_num = 1
    for part, label in zip(parts, labels):
        sentences = _split_complete_sentences(part)
        # Group sentences into scenes of ~2-3 sentences each
        chunk_size = 3 if label == "body" else 2
        for i in range(0, len(sentences), chunk_size):
            group = sentences[i:i + chunk_size]
            narration = ' '.join(group)
            words = len(narration.split())
            dur = max(5, int(words / 2.5))

            if label == "hook" and scene_num == 1:
                visual = (
                    "Close-up of an old book opening slowly, "
                    "warm golden light, dust particles floating, "
                    "cinematic depth of field"
                )
                camera = "slow zoom in"
            elif label == "cta":
                visual = (
                    f"Book cover of '{metadata.title}' by "
                    f"{metadata.author}, elegant display, "
                    "soft spotlight, purchase button overlay"
                )
                camera = "static with subtle glow"
            else:
                visual = (
                    "Silhouette of person contemplating, "
                    "moody atmospheric lighting, "
                    "abstract bokeh background, cinematic"
                )
                camera = "slow pan right"

            scenes.append(Scene(
                scene_number=scene_num,
                duration_seconds=f"{dur-2}-{dur+2}",
                narration=narration,
                visual_prompt=visual,
                camera_note=camera,
            ))
            scene_num += 1

    return Storyboard(
        script_title=script.title,
        total_scenes=len(scenes),
        scenes=scenes,
        style_note=(
            "Cinematic, moody warm lighting, depth of field. "
            "Book/reading aesthetic. 9:16 vertical for TikTok."
        ),
    )


def generate_storyboards_batch(
    scripts: list[RadioScript],
    metadata: BookMetadata,
    api_key: str | None = None,
    model: str = "gpt-4o-mini",
    base_url: str | None = None,
) -> list[Storyboard]:
    """Generate storyboards for a batch of radio scripts."""
    storyboards: list[Storyboard] = []
    for script in scripts:
        sb = generate_storyboard(
            script, metadata,
            api_key=api_key, model=model, base_url=base_url,
        )
        storyboards.append(sb)
    return storyboards


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
        quote = _extract_best_quote(chunk_data.chunk.text, min_len=40, max_len=280)
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
    duration_minutes: int = 3,
) -> ContentPack:
    """Generate all content types using AI rewriting for premium quality.

    This is the AI-powered version of generate_all(). It uses LLM to
    rewrite and EXPAND book content into radio scripts (1-5 min) and
    captions for more natural, engaging output.
    Also generates quote card images if output_dir is provided.
    """
    radio = ai_rewrite_radio_scripts(
        analyzed, metadata,
        api_key=api_key, model=model, base_url=base_url,
        duration_minutes=duration_minutes,
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
