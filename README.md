# BookAI

AI-powered pipeline to convert books into affiliate marketing content.

**Pipeline:** `Book (PDF/EPUB/ảnh/audio) → Markdown → Chunks → AI Analysis → Content Studio → Ready-to-post`

## Features

- **Multi-format input**: EPUB, PDF (text + scan/OCR), images, audio (Whisper)
- **Semantic chunking**: Chapter-aware splitting (1200 tokens), Vietnamese-optimized
- **AI analysis**: 8 labels + viral score (0-10) + summary + reason
- **Content Studio**:
  - Radio scripts (1-5 phút, AI viết lại + mở rộng)
  - Quote cards (text + PNG 1080x1080)
  - Listicles/carousel
  - TikTok captions (SEO optimized)
  - Storyboard/phân cảnh cho AI video (visual prompts tiếng Anh)
- **Multiple providers**: OpenAI, Anthropic, custom API, hoặc mock (offline)
- **CLI interface**: Rich-formatted output

## Installation

```bash
pip install -e .

# For development
pip install -e ".[dev]"
```

## Quick Start

```bash
# Full pipeline (convert → chunk → analyze)
bookai process book.epub --provider mock
bookai process book.pdf --provider custom \
  --base-url https://api.example.com/v1 \
  --model model-name --api-key $API_KEY \
  --batch -o results.json

# Generate content (template-based, offline)
bookai generate results.json -o content.json

# Generate content (AI rewrite, 3 phút mỗi video)
bookai generate-ai results.json \
  --base-url https://api.example.com/v1 \
  --model model-name --api-key $API_KEY \
  --duration 3 --storyboard -o content.json

# Render quote card images (1080x1080 PNG)
bookai render-quotes results.json -o ./cards --theme warm

# Convert only
bookai convert book.epub -o output.md

# OCR (scanned PDF or images)
bookai ocr scan.pdf -o output.md --lang vie+eng
bookai ocr ./book_pages/ -o book.md

# Transcribe audio
bookai transcribe audiobook.mp3 -o transcript.md
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `process` | Full pipeline: convert → chunk → analyze |
| `convert` | Convert file to markdown |
| `chunks` | View chunks from a file |
| `generate` | Generate content (template-based) |
| `generate-ai` | Generate content (AI rewrite + storyboard) |
| `render-quotes` | Render PNG quote card images |
| `ocr` | OCR scanned PDF or images |
| `transcribe` | Transcribe audio file |

## Content Types Generated

| Type | Description | Platform |
|------|-------------|----------|
| **Radio Script** | Hook → Body → CTA (1-5 phút) | TikTok, YouTube |
| **Quote Card** | Câu trích + caption + PNG | Instagram, Pinterest |
| **Listicle** | "X bài học từ [sách]" | Instagram carousel |
| **Caption** | SEO keyword + hashtag | TikTok |
| **Storyboard** | Visual prompts per scene | Runway, Pika, Kling |

## Content Labels

| Label | Description |
|-------|-------------|
| `quote` | Memorable quotes, citations |
| `summary` | Chapter/book summaries |
| `story` | Stories, anecdotes |
| `example` | Illustrative examples |
| `insight` | Core lessons, principles |
| `hook` | Curiosity-inducing openings |
| `tip` | Actionable tips |
| `controversial` | Debate-worthy statements |

## Project Structure

```
src/bookai/
├── models.py          # Pydantic data models
├── converter.py       # EPUB/PDF/TXT → Markdown
├── chunker.py         # Semantic chunking (chapter-aware)
├── analyzer.py        # AI analysis (labels + viral score)
├── content_studio.py  # Content generation engine
├── quote_renderer.py  # PNG quote card renderer
├── audio.py           # Whisper transcription
├── ocr.py             # Tesseract OCR
└── cli.py             # Typer CLI
docs/
├── PLAN.md            # Full roadmap + ideas + strategies
└── ARCHITECTURE.md    # Technical architecture details
AGENTS.md              # Guide for AI IDEs to continue development
```

## Roadmap

- [x] **MVP-1**: Core pipeline (EPUB/PDF → Markdown → Chunk → AI Analysis)
- [x] **MVP-2**: OCR (scan PDF/images) + Whisper (audio)
- [x] **MVP-3**: Content Studio (radio scripts, quotes, listicles, storyboard)
- [ ] **MVP-4**: TTS + Video render + Affiliate links
- [ ] **MVP-5**: Dashboard + Auto-post + Content Calendar
- [ ] **MVP-6**: Vector DB + A/B testing + Scale

See `docs/PLAN.md` for detailed roadmap and strategies.

## Development

```bash
# Run tests (58 tests)
pytest

# Lint
ruff check src/ tests/

# Auto-fix lint
ruff check --fix src/ tests/
```

## License

MIT
