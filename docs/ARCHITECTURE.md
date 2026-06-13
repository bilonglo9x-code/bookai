# BookAI — Kiến trúc kỹ thuật

## Data Flow

```
                    ┌─────────────┐
                    │   CLI       │  (cli.py)
                    │  Commands   │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
     ┌─────▼─────┐  ┌─────▼─────┐  ┌──────▼──────┐
     │  process   │  │ generate  │  │ render-quotes│
     │            │  │ generate-ai│  │             │
     └─────┬──────┘  └─────┬──────┘  └──────┬──────┘
           │               │               │
     ┌─────▼─────┐  ┌─────▼──────┐  ┌──────▼──────┐
     │ converter  │  │  content   │  │    quote    │
     │ chunker    │  │  _studio   │  │  _renderer  │
     │ analyzer   │  │            │  │             │
     └────────────┘  └────────────┘  └─────────────┘
```

## Modules chi tiết

### 1. `models.py` (93 lines)
Data models cho toàn bộ pipeline.

```python
SourceFormat    # enum: epub, pdf, text, markdown, image, audio
ChunkLabel      # enum: quote, summary, story, example, insight, hook, tip, controversial
BookMetadata    # title, author, publisher, language, chapters, source_format
Chunk           # chunk_id, book_title, chapter, chapter_title, position, text, token_count
AnalyzedChunk   # chunk + labels + viral_score + summary + reason
BookResult      # metadata + markdown + chunks + analyzed + top_quotes + top_hooks
```

### 2. `converter.py` (355 lines)
Chuyển đổi file → Markdown.

**Functions:**
- `convert_file(path)` → `(markdown, metadata)` — auto-detect format, dispatch
- `convert_epub(path)` → EPUB via ebooklib + html2text
- `convert_pdf(path)` → PDF text via PyMuPDF, fix Vietnamese "đ" encoding
- `convert_text(path)` → TXT/MD passthrough
- `convert_audio(path)` → dispatch to `audio.py`
- `convert_image(path)` → dispatch to `ocr.py`

**Vietnamese PDF fix:**
PDF fonts thường map sai ký tự "đ/Đ". Code detect và fix pattern
`ñ → đ`, `Ñ → Đ` + clean watermark URLs + page numbers.

### 3. `chunker.py` (179 lines)
Semantic splitting giữ chapter structure.

**Logic:**
1. Split markdown by `# heading` → chapters
2. Within each chapter, split by paragraphs
3. Merge paragraphs until reaching `max_tokens` (default 1200)
4. Each chunk gets `chapter`, `chapter_title`, `position`

**Key param:** `max_tokens=1200` — tối ưu cho Vietnamese text, giữ
đoạn văn/câu chuyện hoàn chỉnh.

### 4. `analyzer.py` (367 lines)
AI phân tích + gắn nhãn.

**Providers:**
- `mock` — heuristic-based, offline, dùng regex + keyword matching
- `openai` / `anthropic` — official APIs
- `custom` — any OpenAI-compatible endpoint (base_url + model)

**Output per chunk:**
```json
{
  "labels": ["quote", "story", "hook"],
  "viral_score": 8.5,
  "summary": "Tóm tắt nội dung đoạn",
  "reason": "Lý do score cao: curiosity + emotion"
}
```

**Batch mode:** `--batch` flag groups chunks into batches of 5
for API efficiency.

### 5. `content_studio.py` (1304 lines)
Content generation engine — module lớn nhất.

**Dataclasses:**
```python
RadioScript     # title, hook, body, cta, hashtags, estimated_seconds, source_chunks
QuoteCard       # quote_text, book_title, author, caption, hashtags
Listicle        # title, items, intro, cta, hashtags
Caption         # text, hashtags, platform
Scene           # scene_number, duration_seconds, narration, visual_prompt, camera_note
Storyboard      # script_title, total_scenes, scenes, style_note, aspect_ratio
ContentPack     # All content types bundled
```

**Key functions:**

| Function | Mô tả |
|----------|-------|
| `generate_radio_scripts()` | Template-based: combine related chunks → 300-500 word scripts |
| `ai_rewrite_radio_scripts()` | LLM rewrite + expand → 1-5 min scripts (configurable `duration_minutes`) |
| `generate_quote_cards()` | Extract best quotes → QuoteCard with caption + hashtags |
| `generate_listicles()` | Group insights → "X bài học từ sách" |
| `generate_captions()` | Template TikTok captions |
| `ai_rewrite_captions()` | LLM-rewritten captions |
| `generate_storyboard()` | LLM splits script → 5-8 scenes with visual prompts |
| `_auto_storyboard()` | Fallback: auto-split by sentences with default visuals |
| `generate_all()` | Bundle all template-based content |
| `generate_all_with_ai()` | Bundle all AI-rewritten content |

**Helper functions:**
- `_split_complete_sentences()` — Vietnamese sentence splitting (handle `.` `!` `?` `…`)
- `_extract_best_quote()` — Select 1-3 best sentences by emotional keyword scoring
- `_find_related_chunks()` — Find same-chapter chunks for combining
- `_make_hook()` — Generate curiosity-gap hooks
- `_make_body_long()` — Build body from complete sentences, target word count
- `_estimate_read_seconds()` — Vietnamese narration speed (~2.5 words/sec)
- `_call_llm_for_rewrite()` — HTTP call to LLM with retry logic

**AI Prompts:**
- `_RADIO_REWRITE_PROMPT` — Instructs LLM to REWRITE (not copy) book content
  into natural radio script with examples, stories, analysis. Returns JSON.
- `_CAPTION_REWRITE_PROMPT` — TikTok SEO caption with hashtags
- `_STORYBOARD_PROMPT` — Split script into scenes with English visual prompts
  for AI video tools (Runway/Pika/Kling/Midjourney)

### 6. `quote_renderer.py` (208 lines)
PIL-based PNG quote card renderer.

**Themes:** dark, light, gradient_blue, warm
**Output:** 1080x1080 PNG
**Layout:** Quote text (centered) + "— Author" + book title footer

### 7. `audio.py` (224 lines)
Whisper-based audio transcription.

**Features:**
- Auto chapter detection from silence gaps (>2s)
- Optional timestamps
- Model sizes: tiny → large

### 8. `ocr.py` (183 lines)
Tesseract OCR for scanned PDFs and images.

**Features:**
- Auto-detect PDF scan vs text
- Supported: PNG, JPG, TIFF, BMP, WebP
- Language: `vie+eng` (Vietnamese + English)
- Directory batch processing

### 9. `cli.py` (705 lines)
Typer CLI with Rich output.

**Commands:**

| Command | Description |
|---------|-------------|
| `process` | Full pipeline: convert → chunk → analyze |
| `convert` | Convert only (any format → markdown) |
| `chunks` | View chunks from a file |
| `generate` | Generate content (template-based) |
| `generate-ai` | Generate content (AI rewrite + storyboard) |
| `render-quotes` | Render PNG quote card images |
| `ocr` | OCR a file or directory |
| `transcribe` | Transcribe audio file |

---

## Testing

```bash
pytest tests/test_bookai.py -q     # 58 tests
ruff check src/ tests/              # lint
```

**Test coverage:**
- Converter: EPUB, PDF, text, audio dispatch, image dispatch
- Chunker: splitting, chapter awareness, token limits
- Analyzer: mock provider, label detection, batch mode
- Content Studio: radio scripts, quotes, listicles, captions
- Audio: transcription, chapter detection
- OCR: image processing, PDF scan detection
- CLI: all commands

---

## API Integration

```python
# Custom OpenAI-compatible API
import httpx

response = httpx.post(
    "https://rh486zc.abc-tunnel.us/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": "WindsurfAPI/gemini-2.5-flash",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 4000,
    },
    timeout=180.0,
)
```

**Retry logic:** 3 attempts with exponential backoff (3s, 6s, 9s).
Handles `HTTPStatusError`, `ConnectError`, `TimeoutException`.

**Fallback:** If LLM call fails, falls back to template-based generation.

---

## Key Design Decisions

1. **Dataclass vs Pydantic**: Pipeline models use Pydantic (serialization).
   Content types use `@dataclass` (simpler, no validation needed).

2. **Chunk size 1200 tokens**: Optimized for Vietnamese text — keeps
   paragraphs/stories intact while fitting in LLM context.

3. **Vietnamese sentence splitting**: Custom regex handles PDF line breaks,
   abbreviations, and Vietnamese punctuation patterns.

4. **Dual generation**: Template (offline, fast, consistent) + AI rewrite
   (online, higher quality, natural language).

5. **Storyboard visual prompts in English**: AI video tools (Runway, Pika,
   Midjourney) only understand English prompts.

6. **Source chunk tracking**: Every generated content piece links back to
   original `chunk_id`(s) for traceability.
