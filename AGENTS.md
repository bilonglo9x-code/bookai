# AGENTS.md — Hướng dẫn cho AI IDE tiếp tục dự án BookAI

> File này dành cho Cursor, Windsurf, Copilot, Devin, hoặc bất kỳ AI IDE nào
> để hiểu context dự án và tiếp tục phát triển.

## Dự án là gì?

**BookAI** — Pipeline AI tự động chuyển sách (PDF/EPUB/ảnh/audio) thành nội dung
affiliate marketing sẵn đăng TikTok/Instagram/YouTube/Blog.

**Mục tiêu kinh doanh:** Scale từ 1-2 video/ngày (làm tay) lên 10-50 content/ngày/kênh,
chạy nhiều kênh song song, gắn affiliate link Shopee/TikTok Shop/Tiki.

## Trạng thái hiện tại

### Đã hoàn thành:
- **Ingest**: EPUB, PDF (text + scan/OCR), images, audio (Whisper)
- **Convert**: → Markdown chuẩn hóa, fix ký tự tiếng Việt, clean watermark
- **Chunk**: Semantic splitting 1200 tokens, chapter-aware
- **Analyze**: AI labeling (8 labels) + viral score 0-10, batch mode
- **Content Studio**:
  - Radio scripts (template-based, 3-5 phút)
  - AI rewrite scripts (LLM viết lại + mở rộng, configurable 1-5 phút)
  - Quote cards (text + caption + hashtag)
  - Listicles/carousel
  - TikTok captions (SEO optimized)
  - Storyboard/phân cảnh minh họa (visual prompts cho AI video)
  - Quote card PNG renderer (1080x1080, 4 themes)

### MVP-4 — Đã triển khai:
- **Affiliate link layer** (`affiliate.py`): AffiliateManager, BookLinks, sub-ID tracking, inject vào ContentPack
- **TTS** (`tts.py`): Edge-TTS giọng Việt (HoaiMyNeural / NamMinhNeural), async batch synthesis
- **Video render** (`video_render.py`): FFmpeg, render_radio_video / render_quote_video / render_slideshow_video, 1080×1920
- **Content Calendar** (`calendar.py`): 30-day 4-week strategy, CSV + JSON export

### Chưa triển khai (xem `docs/PLAN.md`):
- Auto-post đa nền tảng
- Dashboard/Frontend (Web UI — Streamlit đề xuất cho MVP nhanh)
- Vector DB (pgvector)
- Blog/SEO generator
- A/B test hooks
- Cross-book linking

## Cấu trúc code

```
src/bookai/
├── models.py          # Pydantic models: Chunk, AnalyzedChunk, BookResult, BookMetadata
├── converter.py       # EPUB/PDF/TXT → Markdown (+ audio/image dispatch)
├── chunker.py         # Semantic chunking (chapter-aware, 1200 tokens)
├── analyzer.py        # AI analysis: labels + viral_score + summary
├── content_studio.py  # Content generation: radio, quotes, listicles, storyboard
├── quote_renderer.py  # PIL-based PNG quote card renderer
├── audio.py           # Whisper transcription
├── ocr.py             # Tesseract OCR for scanned PDFs/images
├── affiliate.py       # MVP-4: Affiliate link manager (Shopee/TikTok/Tiki + sub-ID)
├── tts.py             # MVP-4: Edge-TTS Vietnamese voiceover synthesis
├── video_render.py    # MVP-4: FFmpeg video rendering (1080×1920 MP4)
├── calendar.py        # MVP-4: 30-day content posting calendar (CSV/JSON)
├── cli.py             # Typer CLI: process, generate, generate-ai, render-quotes,
│                      #            affiliate, tts, render-video, calendar
└── __init__.py
tests/
├── test_bookai.py     # 58 tests (original)
└── test_mvp4.py       # 55 tests (MVP-4 modules)
docs/
├── PLAN.md            # Lộ trình chi tiết + ý tưởng
└── ARCHITECTURE.md    # Kiến trúc kỹ thuật chi tiết
```

## Tech stack

- **Python 3.10+**, Pydantic v2, Typer, Rich
- **PyMuPDF** (PDF text), **ebooklib** (EPUB), **pytesseract** (OCR), **openai-whisper** (audio)
- **httpx** (API calls), **Pillow** (image rendering)
- **pytest** + **ruff** (testing + linting)

## API / LLM

Sử dụng OpenAI-compatible API:
- **Base URL**: `https://rh486zc.abc-tunnel.us/v1` (Cloudflare tunnel, có thể offline)
- **Model**: `WindsurfAPI/gemini-2.5-flash` hoặc `cx/gpt-5.4`
- **API key**: environment variable `key_api`
- Fallback: `--provider mock` cho testing offline

## CLI Commands

```bash
# Full pipeline
bookai process book.pdf --provider custom \
  --base-url https://rh486zc.abc-tunnel.us/v1 \
  --model WindsurfAPI/gemini-2.5-flash \
  --api-key $key_api --batch -o results.json

# Generate content (template)
bookai generate results.json -o content.json

# Generate content (AI rewrite — viết lại + mở rộng 1-5 phút)
bookai generate-ai results.json \
  --base-url ... --model ... --api-key ... \
  --duration 3 --storyboard -o content.json

# Render quote card images
bookai render-quotes results.json -o ./cards --theme warm

# Convert only
bookai convert book.epub -o output.md

# OCR
bookai ocr scan.pdf -o output.md --lang vie+eng

# Transcribe audio
bookai transcribe audiobook.mp3 -o transcript.md
```

## Conventions

- **Language**: Code + comments in English, user-facing content in Vietnamese
- **Lint**: `ruff check src/ tests/` (line-length 100)
- **Tests**: `pytest tests/test_bookai.py` — all 58 must pass
- **Git**: Branch `initial-setup`, NEVER force push to main
- **Imports**: All at top of file, no nested imports (except lazy CLI imports)
- **Models**: Pydantic v2 BaseModel, dataclass for content types
- **Error handling**: Fallback to template-based generation if LLM fails

## Khi tiếp tục phát triển

1. Đọc `docs/PLAN.md` để biết feature tiếp theo cần làm
2. Đọc `docs/ARCHITECTURE.md` để hiểu flow dữ liệu
3. Chạy `pytest` trước và sau khi thay đổi code
4. Chạy `ruff check src/ tests/` để kiểm tra lint
5. Test thực tế với file PDF: `/home/ubuntu/attachments/b8fdfedf.../Thuc+tinh+muc+ich+song-Eckhart+Tolle.pdf`
6. Cached analysis: `/tmp/eckhart_analysis_v2.json` (177 chunks analyzed)

## Tài liệu tham khảo

- **Plan đầy đủ**: `docs/PLAN.md` (lộ trình + ý tưởng + chiến lược)
- **Kiến trúc**: `docs/ARCHITECTURE.md` (data flow + module details)
- **Phân tích @sachhayexpress**: Xem section trong `docs/PLAN.md`
