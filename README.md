# BookAI

AI-powered pipeline to convert books into affiliate marketing content.

**Pipeline:** `Book file → Markdown → Semantic chunks → AI analysis → Content ready for TikTok/IG/Blog`

## Features (MVP-1)

- **Multi-format converter**: EPUB, PDF (text), TXT, Markdown → normalized Markdown
- **Semantic chunking**: Chapter-aware splitting with configurable token bounds
- **AI analysis**: Labels each chunk (quote, hook, tip, story, insight, etc.) + viral score (0-10)
- **Multiple providers**: OpenAI, Anthropic, or mock (offline testing)
- **CLI interface**: Rich-formatted output with tables and panels

## Installation

```bash
pip install -e .

# For development
pip install -e ".[dev]"
```

## Usage

### Full pipeline (convert → chunk → analyze)
```bash
# With mock provider (no API key needed, heuristic-based)
bookai process book.epub

# With OpenAI
export OPENAI_API_KEY=sk-...
bookai process book.epub --provider openai --top 20

# With Anthropic
export ANTHROPIC_API_KEY=sk-ant-...
bookai process book.pdf --provider anthropic --model claude-sonnet-4-20250514
```

### Convert only
```bash
bookai convert book.epub -o output.md
bookai convert scan.pdf -o output.md
```

### View chunks
```bash
bookai chunks book.epub --max-tokens 300 --show 20
```

### Export results to JSON
```bash
bookai process book.epub -o results.json --provider openai
```

## Content Labels

Each chunk is classified with one or more labels:

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

## Viral Score

Each chunk gets a score from 0-10 based on:
- **Curiosity** (+2): Information gap that makes you want to know more
- **Emotion** (+2): Triggers strong feelings (surprise, fear, joy)
- **Actionable** (+2): Reader can apply immediately
- **Controversy** (+2): Sparks debate and comments
- **Relatability** (+2): Everyone sees themselves in it

## Roadmap

- [x] **MVP-1**: EPUB/PDF/TXT → Markdown → Chunk → AI Analysis
- [ ] **MVP-2**: OCR (PDF scan/images) + Whisper (audio/audiobooks)
- [ ] **MVP-3**: Content Studio (TTS + video render + quote cards + captions)
- [ ] **MVP-4**: Dashboard + auto-scheduling + affiliate link management

## Development

```bash
# Run tests
pytest

# Lint
ruff check src/ tests/

# Auto-fix lint
ruff check --fix src/ tests/
```

## License

MIT
