# Book-to-Content: Ứng dụng AI chuyển đổi sách thành nội dung Affiliate

> Tài liệu ý tưởng & kế hoạch phát triển ứng dụng hỗ trợ chuyển đổi sách (PDF, images, audio, EPUB,...) sang Markdown, phân tích AI để tạo nội dung quảng bá sách phục vụ affiliate marketing.

---

## Mục lục

1. [Tổng quan & Mục tiêu](#1-tổng-quan--mục-tiêu)
2. [Pipeline kỹ thuật](#2-pipeline-kỹ-thuật)
3. [Chuyển đổi định dạng → Markdown](#3-chuyển-đổi-định-dạng--markdown)
4. [Chunking thông minh](#4-chunking-thông-minh)
5. [AI phân tích & chọn nội dung hay](#5-ai-phân-tích--chọn-nội-dung-hay)
6. [Các dạng nội dung (Content Types)](#6-các-dạng-nội-dung-content-types)
7. [Content Studio (tạo nội dung tự động)](#7-content-studio-tạo-nội-dung-tự-động)
8. [Chiến lược chọn sách](#8-chiến-lược-chọn-sách)
9. [Chiến lược kênh (Multi-channel)](#9-chiến-lược-kênh-multi-channel)
10. [TikTok SEO](#10-tiktok-seo)
11. [SEO Blog (traffic dài hạn)](#11-seo-blog-traffic-dài-hạn)
12. [Affiliate & Monetization](#12-affiliate--monetization)
13. [Growth Hacking & Tricks](#13-growth-hacking--tricks)
14. [Tính năng thông minh](#14-tính-năng-thông-minh)
15. [Tech Stack](#15-tech-stack)
16. [Lộ trình MVP](#16-lộ-trình-mvp)
17. [Phân tích đối thủ: @sachhayexpress](#17-phân-tích-đối-thủ-sachhayexpress)

---

## 1. Tổng quan & Mục tiêu

### Vấn đề
- Affiliate sách trên TikTok/Shopee đang bùng nổ (600 tỷ VNĐ doanh thu sách trên TikTok trong 6 tháng đầu 2024)
- Nhưng việc tạo nội dung vẫn chủ yếu thủ công: đọc sách → chọn đoạn hay → quay video → edit → đăng
- Mỗi creator chỉ sản xuất được 1-2 video/ngày

### Giải pháp
Ứng dụng AI tự động hóa toàn bộ pipeline:
- **Input**: File sách (PDF, EPUB, ảnh, audio)
- **Output**: 10-50 content pieces/ngày (video, audio, ảnh, text) sẵn sàng đăng + gắn affiliate link

### Mục tiêu
- Scale content từ 1-2 video/ngày lên 10-50 video/ngày/kênh
- Chạy nhiều kênh song song (multi-niche)
- A/B test tự động: hook nào viral, sách nào chuyển đổi
- Giảm thời gian từ "có sách" đến "có content" xuống còn 10 phút

---

## 2. Pipeline kỹ thuật

```
┌─────────────────────────────────────────────────────────────┐
│                    BOOK-TO-CONTENT PIPELINE                   │
└─────────────────────────────────────────────────────────────┘

  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │  INGEST  │ ──► │ CONVERT  │ ──► │  CHUNK   │ ──► │ ANALYZE  │
  │          │     │          │     │          │     │          │
  │ PDF      │     │ → Markdown│    │ Semantic │     │ AI Label │
  │ EPUB     │     │ + metadata│    │ splitting│     │ + Score  │
  │ Images   │     │          │     │          │     │          │
  │ Audio    │     │          │     │          │     │          │
  │ DOCX     │     │          │     │          │     │          │
  └──────────┘     └──────────┘     └──────────┘     └──────────┘
                                                           │
                                                           ▼
  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ PUBLISH  │ ◄── │AFFILIATE │ ◄── │ GENERATE │ ◄── │  SELECT  │
  │          │     │          │     │          │     │          │
  │ TikTok   │     │ Shopee   │     │ Radio    │     │ Top N    │
  │ IG       │     │ TikTok   │     │ Quote    │     │ by viral │
  │ YouTube  │     │ Shop     │     │ Carousel │     │ score    │
  │ Blog     │     │ Tiki     │     │ Blog     │     │          │
  │ Pinterest│     │ Sub-ID   │     │ Video    │     │          │
  └──────────┘     └──────────┘     └──────────┘     └──────────┘
```

---

## 3. Chuyển đổi định dạng → Markdown

| Định dạng | Công cụ | Ghi chú |
|-----------|---------|---------|
| **PDF (text)** | PyMuPDF / pdfplumber | Giữ cấu trúc heading, paragraph |
| **PDF (scan)** | OCR: docTR / Google Vision | Google Vision tốt hơn cho tiếng Việt có dấu |
| **Images** | Google Vision API / Tesseract | Vision API chính xác cao cho chữ Việt |
| **Audio (sách nói)** | Whisper (faster-whisper) | Transcript + timestamp (quý cho cắt clip) |
| **EPUB** | ebooklib + html2text | Định dạng sạch nhất, ưu tiên format này |
| **DOCX** | Pandoc / mammoth | Giữ heading, bold, list |

### Output chuẩn hoá
```markdown
---
title: "Tên sách"
author: "Tác giả"
publisher: "NXB"
isbn: "..."
chapters: 12
source_format: "epub"
processed_at: "2025-01-01"
---

# Chương 1: Tên chương

Nội dung sách được convert sang markdown...
```

---

## 4. Chunking thông minh

### Nguyên tắc
- Tách theo **cấu trúc** (chương → mục → đoạn) thay vì cắt cứng theo token
- Mỗi chunk là 1 đơn vị ngữ nghĩa hoàn chỉnh (1 ý, 1 câu chuyện, 1 ví dụ)

### Metadata mỗi chunk
```json
{
  "chunk_id": "uuid",
  "book_id": "isbn-or-uuid",
  "chapter": 3,
  "section": "3.2",
  "position": 42,
  "token_count": 256,
  "type": "paragraph",
  "text": "Nội dung chunk..."
}
```

### Lưu trữ
- **Postgres + pgvector**: embedding vector cho tìm kiếm ngữ nghĩa
- **Qdrant** (alternative): nếu cần scale lớn
- Tránh phân tích trùng lặp giữa các lần xử lý

---

## 5. AI phân tích & chọn nội dung hay

### Labels (nhãn phân loại)
Mỗi đoạn được AI gắn 1 hoặc nhiều nhãn:

| Nhãn | Mô tả | Ví dụ |
|------|-------|-------|
| `quote` | Câu nói hay, trích dẫn | "Đừng để đến lúc bị đâm sau lưng mới học bài học về lòng người" |
| `summary` | Tóm tắt chương/sách | Tổng hợp ý chính |
| `story` | Câu chuyện, giai thoại | Ví dụ minh hoạ bằng câu chuyện |
| `example` | Ví dụ minh hoạ | Case study, tình huống |
| `insight` | Bài học / luận điểm cốt lõi | Nguyên tắc, quy tắc |
| `hook` | Đoạn gây tò mò, sốc | Mở đầu video |
| `tip` | Mẹo thực hành, actionable | Người đọc áp dụng ngay |
| `controversial` | Quan điểm trái chiều | Gây tranh luận, comment nhiều |

### Viral Score (điểm hấp dẫn)
```
Viral Score = w1×Curiosity + w2×Emotion + w3×Actionable + w4×Controversy + w5×Relatability

- Curiosity (0-10): Có gap thông tin gây tò mò?
- Emotion (0-10): Gây cảm xúc mạnh (sợ, bất ngờ, cảm động)?
- Actionable (0-10): Người xem áp dụng được ngay?
- Controversy (0-10): Có gây tranh luận?
- Relatability (0-10): Người xem thấy mình trong đó?
```

### 2 lớp xử lý (tiết kiệm chi phí)
1. **Lớp lọc** (model rẻ/nhanh): phân loại + chấm điểm sơ bộ
2. **Lớp viết** (model mạnh): chỉ viết content cho đoạn đã được chọn (top 10-20%)

---

## 6. Các dạng nội dung (Content Types)

### 6.1. "Radio Sách" (format chính - như @sachhayexpress)
- **Mô tả**: Giọng đọc narrate nội dung từ sách, nền hình tĩnh/slideshow
- **Thời lượng**: 90-150 giây
- **Cấu trúc**:
  1. Hook (3-5s): 1 câu gây sốc/tò mò
  2. Nội dung chính (80%): Listicle tips/insight ngắn gọn
  3. CTA cuối (10-15s): "Đọc thêm tại cuốn X - link ở giỏ hàng"
- **Platform**: TikTok, YouTube Shorts

### 6.2. "Một câu đáng giá cả cuốn sách" (Quote đơn)
- **Mô tả**: 1 câu trích dẫn mạnh + tên sách + bìa
- **Dạng**: Ảnh tĩnh hoặc video 15s (text xuất hiện dần + nhạc)
- **Platform**: Instagram, Pinterest, TikTok

### 6.3. "X bài học từ [Tên sách]" (Listicle)
- **Mô tả**: 5-10 bài học, mỗi bài 1 slide
- **Dạng**: Carousel (IG) hoặc slideshow video (TikTok)
- **Platform**: Instagram, TikTok

### 6.4. "Sách nói mini" (Audio snippet)
- **Mô tả**: Cắt 1 chương hay → narrate 3-5 phút
- **Dạng**: Podcast snippet
- **Platform**: TikTok, Spotify, Apple Podcasts

### 6.5. "Ai nên đọc cuốn này?" (Persona matching)
- **Mô tả**: "Nếu bạn hay bị lợi dụng → đọc cuốn X"
- **Dạng**: Video ngắn Q&A
- **Platform**: TikTok, Instagram Reels

### 6.6. "Sách vs Sách" (So sánh)
- **Mô tả**: 2 cuốn cùng chủ đề, AI phân tích khác biệt
- **Dạng**: Video chia đôi màn hình hoặc carousel
- **Platform**: TikTok, YouTube

### 6.7. "Drama trong sách" (Storytelling)
- **Mô tả**: AI chọn câu chuyện hay nhất → kể lại dạng kịch tính
- **Hook**: "Có một tên trộm đã dạy tôi bài học lớn nhất đời..."
- **Platform**: TikTok (video dài hơn 2-3 phút)

### 6.8. "Thử thách 1 tuần áp dụng" (Challenge)
- **Mô tả**: 7 tips từ sách → mỗi ngày 1 tip → series 7 video
- **Hashtag**: #7NgàyĐọcSách
- **Platform**: TikTok

### 6.9. "Reaction/Giải mã" (Trend-jacking)
- **Mô tả**: Tình huống trending → AI tìm quote sách phân tích
- **Ví dụ**: Drama ngoại tình → "Sách này giải thích chính xác..."
- **Platform**: TikTok (stitch/duet)

### 6.10. "Combo sách" (Bundle)
- **Mô tả**: AI gom 3-5 sách cùng chủ đề → "bộ sưu tập"
- **Ví dụ**: "3 cuốn sách biến bạn thành người đàn ông bản lĩnh"
- **Platform**: TikTok, Blog

---

## 7. Content Studio (tạo nội dung tự động)

### Pipeline tự động từ 1 cuốn sách
```
1 cuốn sách → AI phân tích → sinh ra:
├── 5 video Radio sách (TikTok) 
├── 10 quote cards (Instagram)
├── 1 blog review SEO (Website)
├── 3 carousel "X bài học" (Instagram)
├── 1 podcast episode 5-10p (Spotify)
├── 15 Pinterest pins
└── 1 video kịch bản dài (YouTube)

= 35+ content pieces từ 1 cuốn sách
```

### Công cụ sinh nội dung

| Output | Công cụ | Chi tiết |
|--------|---------|----------|
| Voiceover/TTS | Edge-TTS / ElevenLabs | Giọng Việt trầm, rõ ràng |
| Video render | FFmpeg / Remotion | Ghép audio + hình + text overlay |
| Ảnh quote | Pillow / HTML→ảnh | Template + font đẹp + bìa sách |
| Carousel | HTML→ảnh series | Multi-slide |
| Blog | LLM generate | 1500-2000 từ, SEO-optimized |
| Caption + hashtag | LLM | Tối ưu 3 lớp keyword TikTok |

### Template video Radio sách
```
[0-3s]   Text overlay: Tiêu đề gây tò mò (font lớn, bold)
[0-3s]   Audio: Hook đọc câu đầu tiên
[3-120s] Background: Bìa sách + text highlight từng câu
[3-120s] Audio: Narrate nội dung chính
[120-135s] Background: Bìa sách + "Đặt sách tại giỏ hàng"
[120-135s] Audio: CTA - kêu gọi mua sách
```

---

## 8. Chiến lược chọn sách

### Tiêu chí chọn sách "dễ viral + dễ ra đơn"

| Tiêu chí | Lý do | Ví dụ |
|-----------|-------|-------|
| **Chủ đề gây tò mò / controversial** | Hook mạnh, comment nhiều | "Nhìn thấu lòng người", "Thao túng tâm lý" |
| **Self-help / tâm lý** | Nhu cầu lớn, dễ trích quote | Đắc Nhân Tâm, Trí Tuệ Xúc Cảm |
| **Giá rẻ (50-150k)** | Dễ chốt đơn impulse buy | Sách bỏ túi, sách mỏng |
| **Bìa đẹp / aesthetic** | Pin/save nhiều trên Instagram | Sách song ngữ, sách minh họa |
| **Trending theo mùa** | Tận dụng xu hướng | Valentine → sách tình yêu |
| **Combo/bundle** | Tăng giá trị đơn hàng | "3 cuốn nhìn thấu nhân tính" |
| **Sách mới ra** | Ít cạnh tranh, NXB hỗ trợ | Sách sắp phát hành |
| **Bestseller kinh điển** | Demand ổn định, search volume cao | Đắc Nhân Tâm, 7 Habits |

### Framework chấm điểm sách
```
Book Score = (Demand × Emotion × Quotability) / Competition

- Demand (1-10): Search volume keyword trên TikTok + Google
- Emotion (1-10): Sách có gây cảm xúc mạnh không?
- Quotability (1-10): Dễ trích đoạn hay, câu quote viral?
- Competition (1-10): Càng ít creator review = điểm cao
```

### Nguồn tìm sách tiềm năng (app auto-crawl)
- **Shopee/Tiki**: Top bán chạy theo tuần
- **TikTok Shop**: Sách trending trong "Giỏ hàng"
- **Google Trends VN**: Từ khóa liên quan đến sách
- **Goodreads/Fahasa**: Sách mới + đánh giá cao
- **NXB partner**: Sách sắp phát hành (review trước = lợi thế)

### Thể loại hot (từ phân tích @sachhayexpress + thị trường)
1. Tâm lý / Nhìn thấu người
2. Làm giàu / Tư duy tài chính
3. Chữa lành / Self-love
4. Tình yêu / Hôn nhân
5. Kỹ năng giao tiếp / EQ
6. Phát triển bản thân
7. Kinh doanh / Khởi nghiệp
8. Truyện / Tiểu thuyết (cho engagement, ít bán)
9. Sách trẻ em / Parenting
10. Thao túng tâm lý / Dark psychology

---

## 9. Chiến lược kênh (Multi-channel)

### Ma trận kênh

| Kênh | Dạng content | Mục đích | Affiliate |
|------|-------------|----------|-----------|
| **TikTok chính** | Radio sách 90-150s | Reach + bán TikTok Shop | TikTok Shop affiliate |
| **TikTok phụ (2-3 niche)** | Cùng format, khác chủ đề | Phủ nhiều niche | TikTok Shop |
| **Instagram** | Quote cards + carousel | Save/share, brand | Link in bio → Shopee |
| **YouTube Shorts** | Repurpose từ TikTok | Thêm traffic + ads | Shopee affiliate |
| **Pinterest** | Quote ảnh, infographic | SEO dài hạn | Blog → affiliate |
| **Blog/Website** | Review chi tiết, SEO | Google organic | Shopee/Tiki affiliate |
| **Podcast** | Audio dài 5-15p | Audience trung thành | Link in description |
| **Facebook** | Share video + group | Community building | Shopee affiliate |

### Chiến lược Multi-account TikTok
```
Kênh 1: @sachhay_tamly      → Tâm lý, thao túng, nhìn thấu người
Kênh 2: @sachhay_kinhdoanh  → Kinh doanh, làm giàu, đầu tư
Kênh 3: @sachhay_chualanh   → Chữa lành, yêu thương bản thân
Kênh 4: @sachhay_tinhyeu    → Tình yêu, hôn nhân, gia đình
Kênh 5: @sachhay_treem      → Sách cho trẻ em, parenting
```

**Lợi thế multi-account:**
- Mỗi kênh tập trung 1 niche → algorithm đẩy đúng người xem
- 1 cuốn sách chạy trên nhiều kênh với góc khác nhau
- Nếu 1 kênh bị hạn chế, các kênh khác vẫn hoạt động
- A/B test niche nào chuyển đổi tốt nhất

### Content Flywheel
```
1 cuốn sách
    ↓
AI phân tích (10 phút)
    ↓
┌───────────────────────────────────┐
│        Content Library            │
├───────────────────────────────────┤
│ 5 video Radio sách (TikTok)      │
│ 10 quote cards (Instagram)       │
│ 3 carousel (Instagram)           │
│ 1 blog review (Website)          │
│ 1 podcast episode (Spotify)      │
│ 15 Pinterest pins                │
│ = 35+ pieces                     │
└───────────────────────────────────┘
    ↓
Auto-schedule (30 ngày content calendar)
    ↓
Track performance → AI optimize
```

---

## 10. TikTok SEO

### 3 lớp keyword TikTok index (2025-2026)

| Lớp | Cách tối ưu | Ví dụ |
|-----|-------------|-------|
| **Audio (ASR)** | Nói keyword trong 3s đầu | "Đây là cách nhìn thấu lòng người..." |
| **On-screen text (OCR)** | Text overlay chứa keyword | "NHÌN THẤU LÒNG NGƯỜI" |
| **Caption** | Caption mở đầu bằng keyword | "Nhìn thấu lòng người - 10 dấu hiệu..." |

### App tự động tối ưu SEO
```
Input: chủ đề "nhìn thấu lòng người"

Auto-generate:
├── Hook audio: "Đây là cách nhìn thấu lòng người chỉ trong 3 giây..."
├── Text overlay: "NHÌN THẤU LÒNG NGƯỜI" (frame 1)
├── Caption: "Nhìn thấu lòng người - 10 dấu hiệu nhận biết kẻ giả tạo"
└── Hashtags: #sachhay #nhinthaulongnguoi #tamly #baihoccuocsong (3-5 tags)
```

### Keyword clusters cho niche sách VN

| Cluster | Keywords (search volume cao) |
|---------|------------------------------|
| Tâm lý | nhìn thấu lòng người, thao túng tâm lý, đọc vị người khác |
| Làm giàu | tư duy người giàu, kiếm tiền, tự do tài chính |
| Tình yêu | giữ chồng, hiểu đàn ông, thu hút người khác giới |
| Chữa lành | yêu bản thân, vượt qua tổn thương, buông bỏ |
| Xử thế | giao tiếp, ứng xử, quy tắc xã hội, EQ cao |
| Gia đình | dạy con, hôn nhân hạnh phúc, mẹ thông thái |

### Yếu tố ranking quan trọng nhất (2026)

| # | Yếu tố | Tác động | Cách tối ưu |
|---|---------|----------|-------------|
| 1 | **Completion rate** | Cao nhất | Video 60-90s, hook mạnh |
| 2 | **Keyword signals** | Cao | 3 lớp keyword |
| 3 | **Save rate** | Cao | Nội dung dạng tips/list |
| 4 | **Comment** | Trung bình | Kết bằng câu hỏi |
| 5 | **Share** | Trung bình | Quote relatable |

---

## 11. SEO Blog (traffic dài hạn)

### Cấu trúc website
```
Domain: sachhay[brand].com

├── /review/[ten-sach]          → Review chi tiết + affiliate link
├── /tom-tat/[ten-sach]         → Tóm tắt sách (AI sinh từ markdown)
├── /quote/[chu-de]             → Tổng hợp quote theo chủ đề
├── /so-sanh/[sach-a-vs-sach-b] → So sánh 2 cuốn sách
├── /top/[the-loai]             → "10 cuốn sách hay nhất về [X]"
└── /bai-hoc/[ten-sach]         → Bài học rút ra từ sách
```

### Keywords SEO mục tiêu

| Dạng keyword | Search volume | Purchase intent | Ví dụ |
|--------------|---------------|-----------------|-------|
| "review [tên sách]" | 1000-5000/tháng | Cao | "review đắc nhân tâm" |
| "[tên sách] tóm tắt" | 500-2000 | Trung bình | "nhà giả kim tóm tắt" |
| "sách hay về [chủ đề]" | 2000-10000 | Cao | "sách hay về tâm lý" |
| "[tên sách] mua ở đâu" | 100-500 | Rất cao | "sách X mua ở đâu rẻ" |
| "sách nên đọc [năm]" | 5000-20000 | Cao | "sách nên đọc 2025" |

### App auto-generate blog
- Từ markdown đã phân tích → sinh bài blog 1500-2000 từ
- Tự chèn affiliate link theo ngữ cảnh (tên sách → link mua)
- Schema markup cho Rich Snippet (star rating, price, availability)
- Internal linking tự động giữa các bài review

---

## 12. Affiliate & Monetization

### Bảng hoa hồng (data 2025-2026)

| Nền tảng | Hoa hồng cơ bản | Hoa hồng Xtra/Campaign | Cookie | Ghi chú |
|----------|-----------------|------------------------|--------|---------|
| **Shopee** | 0-3.68% | +20-35% (mega campaign) | 7 ngày | Xtra từ seller, campaign ngắn hạn |
| **TikTok Shop** | Do seller đặt (5-20%) | Linh hoạt | Session | Chuyển đổi cao vì trong app |
| **Lazada** | Theo ngành hàng | Lên đến 35% | 7 ngày | Campaign đặc biệt |
| **Tiki** | 2-8% (sách) | Campaign | 30 ngày | Cookie dài nhất |

### Chiến lược tối ưu hoa hồng
1. **Ưu tiên TikTok Shop**: hoa hồng cao nhất (seller đặt 10-20%), chuyển đổi trong app
2. **Canh Shopee Xtra**: Mega sale (11.11, 12.12) hoa hồng lên 20-35%
3. **Multi-platform**: Cùng 1 sách, gắn link cả Shopee + TikTok Shop + Tiki
4. **Sub-ID tracking**: Mỗi video gắn sub-id riêng → biết video nào ra đơn → AI optimize

### Mô hình kiếm tiền đa kênh

| Kênh thu nhập | Cách thức | Tiềm năng |
|---------------|-----------|------------|
| TikTok Shop Affiliate | Link sách trong video | Chính (5-20% hoa hồng) |
| Shopee/Tiki/Lazada | Link bio/caption | Bổ sung |
| TikTok Creator Fund | View-based | Nhỏ nhưng ổn định |
| YouTube Ads | Monetize video dài | Bền vững |
| Blog Adsense | Display ads | Traffic SEO |
| Sponsorship NXB | NXB trả review sách mới | Cao (deal trực tiếp) |
| SaaS tool | Cho creator khác thuê | Scale lớn |
| Khóa học | "Đọc sách cùng AI" subscription | Recurring revenue |
| Livestream bán sách | 300tr/3h (theo báo cáo) | Rất cao |

### Lớp Affiliate trong app
- Quản lý link affiliate theo sách (multi-platform)
- Tự chèn link vào caption/CTA theo template
- Sub-ID tracking theo: video_id + platform + niche
- Dashboard: sách nào → content nào → đơn hàng nào
- AI recommend: "Sách X nên push thêm vì conversion rate cao"

---

## 13. Growth Hacking & Tricks

### 1. "Sách free chapter" strategy
- Đọc 1 chương hay nhất FREE → người nghe muốn biết tiếp → mua sách
- Kiểu "sample miễn phí" dưới dạng audio content

### 2. "Comment bait" templates
```
- "Bình luận '1' để nhận link sách"
- "Tag người bạn cần đọc cuốn này"
- "Bạn thấy quy tắc số mấy đúng nhất?"
- "Ai đồng ý like, ai không đồng ý comment lý do"
- "Save lại để đọc khi cần"
```

### 3. "Series cliffhanger"
- Chia 1 cuốn sách thành 5-7 video
- Cuối mỗi video: "Phần tiếp theo còn hay hơn, follow để không bỏ lỡ..."
- Tăng follow + watch time + return viewers

### 4. "Timing" đăng bài tối ưu
| Khung giờ | Lý do |
|-----------|-------|
| 6-8h sáng | Đi làm, lướt điện thoại |
| 12-13h | Giờ nghỉ trưa |
| 20-22h | Trước ngủ, peak TikTok |
| Chủ nhật tối | Review dài, người ta rảnh |

### 5. "Reaction to trending" (real-time)
- Khi có drama/trend → AI tìm ngay quote sách liên quan → đăng trong 2h
- VD: Drama ngoại tình trending → "Sách dạy nhìn thấu kẻ phản bội"
- VD: Trend "quiet quitting" → "Sách giải thích tại sao bạn hết đam mê"

### 6. "Duet/Stitch" growth
- Stitch video viral khác + thêm insight từ sách
- Duet reaction: "Sách này giải thích chính xác điều bạn vừa nói"
- Leverage audience của creator lớn hơn

### 7. Livestream script AI
- App chuẩn bị sẵn script + talking points cho mỗi cuốn sách
- AI gợi ý "lúc nào nên show cuốn nào" based on chat sentiment
- Flash sale timer + urgency CTA

### 8. Cross-promotion loop
```
TikTok video → "Full review trên blog" (dẫn traffic blog)
Blog → "Xem video tóm tắt trên TikTok" (dẫn follow TikTok)
Instagram → "Nghe full chương trên podcast" (dẫn subscriber)
```

### 9. UGC (User Generated Content)
- Challenge: "Đọc quote từ sách yêu thích + tag kênh"
- Review contest: "Review sách hay nhất tháng = tặng combo sách"
- Tạo template cho followers tự làm content

### 10. Email list building
- "Đăng ký nhận 5 quote hay mỗi sáng" (lead magnet)
- Nurture → recommend sách mới → affiliate link trong email
- Retention channel khi algorithm thay đổi

---

## 14. Tính năng thông minh

### 14.1. Auto-detect thể loại sách
- AI phân loại: self-help, tiểu thuyết, kinh doanh, kỹ năng, tâm lý...
- Mỗi thể loại → prompt/template phân tích khác nhau
- Self-help → trích tips, quotes
- Tiểu thuyết → trích câu chuyện, tình tiết hay
- Kinh doanh → trích case study, framework

### 14.2. Content Calendar Generator
Từ 1 cuốn sách → lịch đăng 30 ngày:
```
Tuần 1 (Hook & Tease):
  Ngày 1-3: Quote cards (Instagram + TikTok)
  Ngày 4-5: "3 câu đáng giá cả cuốn sách" (video)
  
Tuần 2 (Deep Content):
  Ngày 6-8: Radio sách - chương hay nhất
  Ngày 9-10: "X bài học từ sách" (carousel)
  
Tuần 3 (Engagement):
  Ngày 11-13: So sánh với sách khác
  Ngày 14-15: Storytelling - câu chuyện hay nhất

Tuần 4 (Conversion Push):
  Ngày 16-18: "Ai nên đọc cuốn này" (persona)
  Ngày 19-20: Combo recommendation
  Ngày 21: Blog review chi tiết + SEO
```

### 14.3. Cross-book linking
Khi nhập nhiều sách, AI tìm liên kết:
- "Cuốn A nói X, cuốn B cũng nói X nhưng từ góc khác" → content so sánh
- Tạo "reading path" theo chủ đề
- Bundle recommendation tự động

### 14.4. Audience Persona matching
Mỗi đoạn content được gắn persona phù hợp:
- Dân startup → sách kinh doanh, mindset
- Sinh viên → sách kỹ năng, phát triển bản thân
- Phụ huynh → sách dạy con, gia đình
- Phụ nữ → sách tình yêu, chữa lành, tự tin
→ Target quảng cáo/kênh phù hợp

### 14.5. Performance Optimizer
- Track: video nào → bao nhiêu view → bao nhiêu đơn
- AI phân tích pattern: hook nào viral, thời lượng nào tối ưu
- Auto-adjust: tăng production content dạng performing tốt
- Suggest: "Sách X nên làm thêm 3 video vì đang trending"

### 14.6. A/B Test Engine
- Từ 1 insight → sinh 3 hook khác nhau → đăng cả 3
- Track performance → chọn winner → scale
- Test: thời lượng, giọng đọc, thumbnail, caption style

---

## 15. Tech Stack

### Backend
| Component | Công nghệ | Lý do |
|-----------|-----------|-------|
| API Server | Python + FastAPI | Đồng bộ repo `shopper` hiện tại |
| Task Queue | Celery / RQ | OCR & Whisper chạy nền, lâu |
| Database | PostgreSQL + pgvector | Relational + vector search |
| File Storage | S3 / MinIO | Lưu file sách, audio, video |
| Cache | Redis | Session, task status |

### AI / ML
| Component | Công nghệ | Lý do |
|-----------|-----------|-------|
| LLM (phân tích) | OpenAI / Claude / Gemini | Phân loại, score, viết content |
| STT (Speech-to-Text) | Whisper (faster-whisper) | Transcribe audio sách nói |
| TTS (Text-to-Speech) | Edge-TTS / ElevenLabs | Tạo voiceover cho video |
| OCR | Google Vision / docTR | Nhận dạng chữ Việt từ ảnh |
| Embedding | OpenAI / sentence-transformers | Vector search cho chunks |

### Content Generation
| Component | Công nghệ | Lý do |
|-----------|-----------|-------|
| Video render | FFmpeg / Remotion | Ghép audio + hình + text |
| Image gen | Pillow / HTML→PNG | Quote cards, thumbnails |
| Blog | LLM + Jinja2 template | SEO-optimized articles |

### Frontend (Dashboard)
| Component | Công nghệ |
|-----------|-----------|
| Web UI | React / Next.js hoặc Streamlit (MVP) |
| Features | Duyệt đoạn hay, 1-click xuất content, calendar view |

### Deployment
| Component | Công nghệ |
|-----------|-----------|
| Container | Docker |
| Orchestration | Docker Compose (MVP) → K8s (scale) |
| CI/CD | GitHub Actions |

---

## 16. Lộ trình MVP

### MVP-1: Core Pipeline (2-3 tuần)
- [ ] EPUB/PDF-text → Markdown converter
- [ ] Chunking engine (semantic splitting)
- [ ] AI phân tích: gắn nhãn + viral score
- [ ] Output: danh sách quote + tóm tắt (text thuần)
- [ ] CLI interface: `bookai process book.epub`

### MVP-2: Audio Support (1-2 tuần)
- [ ] OCR cho PDF scan/ảnh (Google Vision)
- [ ] Whisper integration cho audio/sách nói
- [ ] Timestamp alignment (audio ↔ text)

### MVP-3: Content Studio (2-3 tuần)
- [ ] TTS voiceover generation (Edge-TTS)
- [ ] Video render: audio + text overlay + bìa sách
- [ ] Quote card generator (ảnh)
- [ ] Caption + hashtag SEO generator
- [ ] Affiliate link auto-insertion

### MVP-4: Dashboard & Automation (2-3 tuần)
- [ ] Web dashboard: duyệt content, chỉnh sửa, approve
- [ ] Content calendar + auto-scheduling
- [ ] Multi-platform export (TikTok, IG, YouTube, Blog)
- [ ] Performance tracking + Sub-ID analytics

### MVP-5: Scale & Optimize (ongoing)
- [ ] Multi-account management
- [ ] A/B testing engine
- [ ] Trend detection + auto-content
- [ ] Livestream script generator
- [ ] NXB partner portal

---

## 17. Phân tích đối thủ: @sachhayexpress

### Profile
- **Followers**: 660.8K
- **Likes**: 8.4M
- **Bio**: "❤ Radio những trang sách hay / ĐẶT SÁCH TẠI ⬇️ GIỎ HÀNG Ạ"
- **Monetization**: TikTok Shop trực tiếp trong video

### Format nội dung (từ transcript thực tế)
- **Dạng**: Audio-only + hình tĩnh (bìa sách / text)
- **Giọng**: 1 giọng nam, đọc rõ ràng, tốc độ vừa phải
- **Thời lượng**: 87-155 giây (1.5-2.5 phút)
- **Audio**: "âm thanh gốc" - tự thu/TTS

### Cấu trúc video phổ biến
```
[Hook] "Đàn ông sợ ba cái lắc đầu, đàn bà sợ bước trên quá dốc..."
[Body] Liệt kê 10-30 tips/rules/insights ngắn gọn
[CTA]  "Cuốn sách X này sinh ra là để cứu vớt cuộc đời bạn.
        Dù bạn 20 hay 50 tuổi, nhất định phải có cuốn này..."
```

### Playlists (phân loại content)
1. Sách Hay - Mua Tại Video (14 posts)
2. Combo Sách Hay (11 posts)
3. Sách Song Ngữ (6 posts)
4. Sách Giao Tiếp (2 posts)
5. Sách Chữa Lành (11 posts)
6. Phát Triển Bản Thân (6 posts)
7. Bạn Hay Phiền Não Nên Đọc (3 posts)
8. Phát Triển Tâm Thức (10 posts)
9. Con Gái Đọc Gì? (4 posts)
10. Sách Tình Yêu (14 posts)
11. Hôn Nhân - Gia Đình (4 posts)
12. Truyện - Tiểu Thuyết (6 posts)
13. Tập Thơ (5 posts)

### Điểm mạnh
- Consistency: đăng đều đặn
- Niche rõ ràng: tâm lý, xử thế, nhìn thấu người
- CTA mạnh: dẫn thẳng TikTok Shop
- Hook tốt: câu đầu luôn gây tò mò

### Cơ hội vượt trội bằng AI
- Họ: 1 người → 1-2 video/ngày
- App: AI → 10-50 video/ngày, nhiều kênh, nhiều niche
- Họ: chọn sách thủ công
- App: data-driven book selection (score + trending)
- Họ: không track conversion chi tiết
- App: Sub-ID tracking, biết content nào ra đơn → optimize

---

## Tổng kết

App "Book-to-Content" giải quyết bài toán **scale** trong affiliate sách:
- Từ 1 cuốn sách → 35+ content pieces trong 10 phút
- Chạy song song nhiều kênh, nhiều niche
- Data-driven: biết sách nào, content nào, platform nào hiệu quả
- Tự động hóa 90% công việc (chỉ cần human review + approve)

**ROI ước tính** (dựa trên data thị trường):
- 1 video viral = 100K-1M views = 50-500 đơn sách
- Hoa hồng trung bình: 10% × 100K/cuốn = 10K/đơn
- 50 đơn/video × 10K = 500K/video
- 10 video/ngày × 500K = 5M/ngày = 150M/tháng (conservative)

---

*Tài liệu này là ý tưởng tổng hợp, chưa phải tài liệu kỹ thuật chi tiết. Khi sẵn sàng code, cần refine thêm data model, API design, và UI wireframes.*
