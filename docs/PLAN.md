# BookAI — Kế hoạch phát triển & Ý tưởng

> Tài liệu tổng hợp toàn bộ ý tưởng, lộ trình, chiến lược cho ứng dụng
> chuyển đổi sách thành nội dung affiliate marketing bằng AI.

---

## Mục tiêu

- **Input**: File sách (PDF, EPUB, ảnh, audio)
- **Output**: 10-50 content pieces/ngày (video, audio, ảnh, text) sẵn đăng + affiliate link
- **Scale**: Từ 1-2 video/ngày (thủ công) → 10-50 video/ngày/kênh, nhiều kênh song song

---

## 1. Pipeline kỹ thuật

```
Sách (PDF/EPUB/ảnh/audio)
    │
    ▼
[CONVERT] → Markdown chuẩn hóa (fix tiếng Việt, clean watermark)
    │
    ▼
[CHUNK] → Semantic splitting (1200 tokens, chapter-aware)
    │
    ▼
[ANALYZE] → AI labeling (8 labels) + viral score (0-10) + summary
    │
    ▼
[SELECT] → Top N chunks theo viral score
    │
    ▼
[GENERATE] → Radio scripts, Quote cards, Listicles, Captions, Storyboard
    │
    ▼
[RENDER] → PNG quote cards, AI video prompts
    │
    ▼
[PUBLISH] → TikTok, Instagram, YouTube, Blog (chưa triển khai)
```

---

## 2. Trạng thái triển khai

### Đã hoàn thành

| Feature | Module | Mô tả |
|---------|--------|-------|
| EPUB converter | `converter.py` | ebooklib + html2text |
| PDF text converter | `converter.py` | PyMuPDF, fix ký tự "đ" tiếng Việt |
| PDF scan OCR | `ocr.py` | pytesseract, auto-detect scan vs text |
| Image OCR | `ocr.py` | PNG/JPG/TIFF → text |
| Audio transcription | `audio.py` | openai-whisper, chapters from silence |
| Semantic chunking | `chunker.py` | 1200 tokens, chapter-aware |
| AI analysis | `analyzer.py` | 8 labels + viral score + summary + reason |
| Mock provider | `analyzer.py` | Heuristic-based, offline testing |
| Custom API provider | `analyzer.py` | OpenAI-compatible endpoint |
| Radio scripts (template) | `content_studio.py` | Hook→Body→CTA, combine related chunks |
| Radio scripts (AI rewrite) | `content_studio.py` | LLM viết lại + mở rộng 1-5 phút |
| Quote cards | `content_studio.py` | Text + caption + hashtag |
| Listicles | `content_studio.py` | "X bài học từ sách" |
| TikTok captions | `content_studio.py` | SEO optimized + hashtag |
| Storyboard | `content_studio.py` | Visual prompts cho AI video (EN) |
| Quote card PNG | `quote_renderer.py` | 1080x1080, 4 themes |
| CLI | `cli.py` | process, generate, generate-ai, render-quotes, ocr, transcribe |
| Tests | `test_bookai.py` | 58 tests passing |

### Chưa triển khai

| # | Feature | Mức độ ưu tiên | Mô tả |
|---|---------|----------------|-------|
| 1 | **TTS + Video render** | Cao | Edge-TTS/ElevenLabs tạo voiceover → FFmpeg ghép video |
| 2 | **Affiliate link layer** | Cao | Auto-insert Shopee/Tiki/TikTok Shop links + sub-ID tracking |
| 3 | **Content Calendar** | Cao | Từ 1 sách → lịch đăng 30 ngày tự động |
| 4 | **Auto-post đa nền tảng** | Trung bình | API đăng TikTok/IG/YouTube/Blog |
| 5 | **Blog/SEO generator** | Trung bình | LLM sinh bài review SEO 1500-2000 từ |
| 6 | **Cross-book linking** | Trung bình | Phân tích nhiều sách, tìm liên kết chủ đề |
| 7 | **Vector DB (pgvector)** | Trung bình | Lưu chunks, tìm kiếm ngữ nghĩa |
| 8 | **Dashboard/Frontend** | Trung bình | Web UI duyệt + approve content |
| 9 | **Persona matching** | Thấp | "Nếu bạn hay bị lợi dụng → đọc cuốn X" |
| 10 | **A/B test hooks** | Thấp | Sinh nhiều hook → track viral |
| 11 | **Video slideshow** | Thấp | Render quote cards → video tự động |
| 12 | **Sách nói mini** | Thấp | Cắt audio chapters → podcast snippet |

---

## 3. Các dạng nội dung (10 loại)

### 3.1. "Radio Sách" (format chính — đã triển khai)
- **Input**: Chunks phân tích + AI rewrite
- **Output**: Script 1-5 phút (Hook → Body → CTA)
- **Phong cách**: @sachhayexpress — giọng trầm, kể chuyện, triết lý
- **AI rewrite**: LLM viết lại + mở rộng, thêm ví dụ, kể chuyện
- **Storyboard**: Phân cảnh + visual prompt tiếng Anh cho AI video

### 3.2. Quote Cards (đã triển khai)
- Câu trích dẫn hay + caption + hashtag
- Render PNG 1080x1080 (4 themes: dark, light, warm, gradient_blue)
- Platform: Instagram, Pinterest

### 3.3. Listicles/Carousel (đã triển khai)
- "X bài học từ [sách]", "X câu nói hay từ [sách]"
- Platform: Instagram carousel, TikTok slide

### 3.4. TikTok Captions (đã triển khai)
- SEO optimized: keyword + hashtag
- 3 lớp TikTok index: audio (ASR) + on-screen text (OCR) + caption

### 3.5. "Một câu đáng giá cả cuốn sách" (chưa triển khai)
- 1 quote mạnh + tên sách + bìa
- Video 15s hoặc ảnh tĩnh
- Dễ viral (save/share nhiều)

### 3.6. "Sách nói mini" (chưa triển khai)
- Cắt 1 chương → narrate 3-5 phút
- Dạng podcast snippet

### 3.7. "Ai nên đọc cuốn này?" (chưa triển khai)
- Persona matching: "Nếu bạn hay bị lợi dụng → đọc cuốn X"
- Format Q&A ngắn

### 3.8. "Sách vs Sách" (chưa triển khai)
- So sánh 2 cuốn cùng chủ đề
- "Đắc nhân tâm vs Nhìn thấu lòng người — cuốn nào hợp bạn?"

### 3.9. "Drama trong sách" (chưa triển khai)
- AI chọn câu chuyện/giai thoại hay nhất
- Storytelling kịch tính

### 3.10. "Thử thách 1 tuần áp dụng" (chưa triển khai)
- 7 tip từ sách → series 7 video
- "#7NgàyĐọcSách"

---

## 4. Chiến lược chọn sách

### Framework scoring:
```
Score = (Demand × Emotion × Quotability) / Competition
```

### Tiêu chí:
- Chủ đề gây tò mò / controversial (nhìn thấu lòng người, thao túng tâm lý...)
- Self-help / tâm lý (nhu cầu lớn, dễ trích quote)
- Giá rẻ 50-150k (impulse buy)
- Bìa đẹp (save nhiều trên IG)
- Trending theo mùa (Valentine → sách tình yêu, tựu trường → kỹ năng)

### Nguồn tìm sách (app có thể auto-crawl):
- Shopee/Tiki: top bán chạy theo tuần
- TikTok Shop: sách trending trong "Giỏ hàng"
- Google Trends VN
- Goodreads/Fahasa: sách mới + đánh giá cao

---

## 5. Chiến lược kênh (Multi-channel)

### Ma trận kênh:

| Kênh | Dạng content | Affiliate |
|------|-------------|-----------|
| TikTok chính | Radio sách 1-5p | TikTok Shop |
| TikTok phụ (2-3 niche) | Cùng format, khác chủ đề | TikTok Shop |
| Instagram | Quote cards + carousel | Link in bio → Shopee |
| YouTube Shorts | Repurpose từ TikTok | Shopee affiliate |
| Pinterest | Quote ảnh, infographic | Blog → affiliate |
| Blog/Website | Review SEO dài | Shopee/Tiki affiliate |
| Podcast | Audio 5-15p | Link in description |

### Multi-account TikTok:
```
Kênh 1: @sachhay_tamly      → Tâm lý, thao túng, nhìn thấu người
Kênh 2: @sachhay_kinhdoanh  → Kinh doanh, làm giàu
Kênh 3: @sachhay_chualanh   → Chữa lành, yêu thương bản thân
Kênh 4: @sachhay_tinhyeu    → Tình yêu, hôn nhân
Kênh 5: @sachhay_treem      → Sách trẻ em, parenting
```

### Content Flywheel (từ 1 cuốn sách):
```
1 cuốn sách → AI phân tích → sinh ra:
├── 5-45 video Radio sách (TikTok)
├── 100+ quote cards (Instagram)
├── 1 blog review SEO (Website)
├── 3-15 carousel (Instagram)
├── 1 podcast episode (Spotify)
└── 15 Pinterest pins
= 125-180+ content pieces từ 1 cuốn sách
```

---

## 6. TikTok SEO

### 3 lớp keyword TikTok index:
1. **Audio (ASR)** — giọng đọc phải NÓI keyword trong 3s đầu
2. **On-screen text (OCR)** — text overlay chứa keyword
3. **Caption** — mở đầu bằng keyword

### Keyword clusters niche sách VN:
| Cluster | Keywords |
|---------|----------|
| Tâm lý | nhìn thấu lòng người, thao túng tâm lý, đọc vị người khác |
| Làm giàu | tư duy người giàu, kiếm tiền, tự do tài chính |
| Tình yêu | giữ chồng, hiểu đàn ông, thu hút |
| Chữa lành | yêu bản thân, vượt qua tổn thương, buông bỏ |
| Xử thế | giao tiếp, ứng xử, EQ cao |

### Yếu tố ranking:
- **Completion rate** (xem hết) → giữ 60-90s
- **Save rate** → nội dung tips/list khiến save
- **Comment** → kết bằng câu hỏi

---

## 7. Affiliate & Monetization

| Nền tảng | Hoa hồng cơ bản | Campaign Xtra |
|----------|-----------------|---------------|
| Shopee | 0-3.68% | +20-35% |
| TikTok Shop | 5-20% (seller đặt) | Linh hoạt |
| Lazada | Theo ngành | Lên đến 35% |
| Tiki | 2-8% sách | Campaign đặc biệt |

### Chiến lược:
- Ưu tiên TikTok Shop (hoa hồng cao, chuyển đổi trong app)
- Canh mega sale (11.11, 12.12)
- Multi-platform: cùng sách gắn link nhiều sàn
- Sub-ID tracking: biết video nào ra đơn → optimize

---

## 8. Growth Hacking

1. **"Sách free chapter"** — đọc 1 chương hay nhất FREE → mua sách đầy đủ
2. **Comment bait** — "Bình luận 1 để nhận link sách"
3. **Series cliffhanger** — Chia 1 cuốn thành 5-7 video, kết bằng "Phần tiếp theo..."
4. **Timing** — 6-8h sáng, 12-13h, 20-22h (peak TikTok)
5. **Reaction to trending** — AI tìm quote sách liên quan drama/trend
6. **Duet/Stitch** — Stitch video viral + insight từ sách
7. **Livestream** — Script + talking points cho mỗi cuốn sách
8. **Combo sách** — "3 cuốn biến bạn thành người bản lĩnh"

---

## 9. SEO Blog (traffic dài hạn)

### Cấu trúc blog:
```
sachhay.com
├── /review/[ten-sach]     → Review chi tiết + affiliate
├── /tom-tat/[ten-sach]    → Tóm tắt sách (AI)
├── /quote/[chu-de]        → Tổng hợp quote theo chủ đề
├── /so-sanh/[sach-a-vs-b] → So sánh 2 cuốn
└── /top/[the-loai]        → "10 cuốn hay nhất về [X]"
```

### Keywords SEO:
- "review [tên sách]" — 1000-5000 searches/tháng
- "[tên sách] tóm tắt" — 500-2000
- "sách hay về [chủ đề]" — 2000-10000

---

## 10. Phân tích @sachhayexpress (660K followers)

### Format chính: "Radio Sách"
- Giọng nam trầm, đọc rõ ràng
- 87-155 giây (1.5-2.5 phút)
- Cấu trúc: Hook (3-5s) → Listicle tips (80%) → CTA mua sách (10-15s)
- Monetization: TikTok Shop trực tiếp

### Playlists: Sách Hay, Combo, Song Ngữ, Giao Tiếp, Chữa Lành,
Phát Triển Bản Thân, Tâm Thức, Sách Con Gái, Tình Yêu, Hôn Nhân, Truyện, Thơ

### Cơ hội vượt trội bằng AI:
- Họ: 1 người → 1-2 video/ngày | App: AI → 10-50/ngày
- Họ: chọn sách thủ công | App: data-driven
- Họ: không track conversion | App: sub-ID tracking

---

## 11. Tech Stack

| Layer | Công nghệ |
|-------|-----------|
| Language | Python 3.10+ |
| Models | Pydantic v2 |
| CLI | Typer + Rich |
| PDF | PyMuPDF |
| EPUB | ebooklib + html2text |
| OCR | pytesseract |
| Audio | openai-whisper |
| LLM | OpenAI-compatible API (httpx) |
| Images | Pillow |
| Testing | pytest + ruff |
| **Planned** | |
| API Server | FastAPI |
| Database | PostgreSQL + pgvector |
| Task Queue | Celery / RQ |
| TTS | Edge-TTS / ElevenLabs |
| Video | FFmpeg |
| Frontend | React/Next.js hoặc Streamlit |
| Deploy | Docker + GitHub Actions |

---

## 12. Lộ trình MVP

### MVP-1: Core Pipeline ✅
- [x] EPUB/PDF-text → Markdown converter
- [x] Semantic chunking (1200 tokens)
- [x] AI analysis: labels + viral score
- [x] CLI interface

### MVP-2: Input Formats ✅
- [x] OCR cho PDF scan/ảnh (pytesseract)
- [x] Whisper cho audio
- [x] Auto-detect scan vs text PDF

### MVP-3: Content Studio ✅
- [x] Radio scripts (template + AI rewrite)
- [x] Quote cards + PNG renderer
- [x] Listicles/carousel
- [x] TikTok captions SEO
- [x] Storyboard/phân cảnh cho AI video

### MVP-4: Video + Affiliate (tiếp theo)
- [ ] TTS voiceover (Edge-TTS)
- [ ] Video render (FFmpeg: audio + hình + text overlay)
- [ ] Affiliate link auto-insertion
- [ ] Content calendar (30 ngày)

### MVP-5: Dashboard & Automation
- [ ] Web dashboard (Streamlit hoặc Next.js)
- [ ] Auto-post API (TikTok, IG, YouTube)
- [ ] Performance tracking
- [ ] Multi-account management

### MVP-6: Scale & Optimize
- [ ] Vector DB (pgvector) cho cross-book search
- [ ] A/B testing engine
- [ ] Trend detection
- [ ] Livestream script generator

---

## 13. ROI ước tính

- 1 video viral = 100K-1M views = 50-500 đơn sách
- Hoa hồng TB: 10% × 100K/cuốn = 10K/đơn
- 50 đơn/video × 10K = 500K/video
- 10 video/ngày × 500K = **5M/ngày = 150M/tháng** (conservative)
