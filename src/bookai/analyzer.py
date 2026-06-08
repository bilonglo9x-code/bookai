"""AI-powered content analysis for book chunks."""

from __future__ import annotations

import json
import os

from .models import AnalyzedChunk, Chunk, ChunkLabel

ANALYSIS_PROMPT = """Bạn là một chuyên gia phân tích nội dung sách cho affiliate marketing.
Nhiệm vụ: phân tích đoạn text sau và đánh giá tiềm năng viral trên TikTok/mạng xã hội.

Đoạn text:
---
{text}
---

Trả về JSON với format:
{{
  "labels": ["quote"|"summary"|"story"|"example"|"insight"|"hook"|"tip"|"controversial"],
  "viral_score": <0.0-10.0>,
  "summary": "<tóm tắt ngắn 1-2 câu>",
  "reason": "<lý do chấm điểm viral>"
}}

Tiêu chí chấm viral_score:
- Curiosity (gây tò mò): +2 điểm
- Emotion (gây cảm xúc mạnh): +2 điểm
- Actionable (áp dụng được ngay): +2 điểm
- Controversy (gây tranh luận): +2 điểm
- Relatability (ai cũng thấy liên quan): +2 điểm

Chỉ trả về JSON, không giải thích thêm."""


def analyze_chunks(
    chunks: list[Chunk],
    api_key: str | None = None,
    model: str = "gpt-4o-mini",
    provider: str = "openai",
    base_url: str | None = None,
) -> list[AnalyzedChunk]:
    """Analyze a list of chunks using LLM.

    Args:
        chunks: List of text chunks to analyze.
        api_key: API key for LLM provider. Falls back to env vars.
        model: Model name to use.
        provider: LLM provider ("openai", "anthropic", "custom", or "mock").
        base_url: Custom API base URL (for OpenAI-compatible endpoints).

    Returns:
        List of AnalyzedChunk with labels and scores.
    """
    if provider == "mock":
        return [_mock_analyze(chunk) for chunk in chunks]

    api_key = api_key or _get_api_key(provider)
    if not api_key:
        raise ValueError(
            f"No API key found for {provider}. "
            f"Set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable, "
            f"or use --provider mock for testing."
        )

    results: list[AnalyzedChunk] = []
    for chunk in chunks:
        analyzed = _analyze_single(
            chunk, api_key=api_key, model=model, provider=provider, base_url=base_url
        )
        results.append(analyzed)

    return results


def analyze_chunks_batch(
    chunks: list[Chunk],
    api_key: str | None = None,
    model: str = "gpt-4o-mini",
    provider: str = "openai",
    batch_size: int = 5,
    base_url: str | None = None,
) -> list[AnalyzedChunk]:
    """Analyze chunks in batches for efficiency.

    Processes multiple chunks per API call using a batch prompt.
    """
    if provider == "mock":
        return [_mock_analyze(chunk) for chunk in chunks]

    api_key = api_key or _get_api_key(provider)
    if not api_key:
        raise ValueError(
            f"No API key found for {provider}. "
            f"Set OPENAI_API_KEY or ANTHROPIC_API_KEY, or use --provider mock."
        )

    results: list[AnalyzedChunk] = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        batch_results = _analyze_batch(
            batch, api_key=api_key, model=model, provider=provider, base_url=base_url
        )
        results.extend(batch_results)

    return results


def _analyze_single(
    chunk: Chunk,
    api_key: str,
    model: str,
    provider: str,
    base_url: str | None = None,
) -> AnalyzedChunk:
    """Analyze a single chunk via LLM API."""
    prompt = ANALYSIS_PROMPT.format(text=chunk.text[:2000])

    if provider in ("openai", "custom"):
        response_text = _call_openai(prompt, api_key=api_key, model=model, base_url=base_url)
    elif provider == "anthropic":
        response_text = _call_anthropic(prompt, api_key=api_key, model=model)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    return _parse_response(chunk, response_text)


def _analyze_batch(
    chunks: list[Chunk],
    api_key: str,
    model: str,
    provider: str,
    base_url: str | None = None,
) -> list[AnalyzedChunk]:
    """Analyze a batch of chunks in one API call."""
    batch_prompt = (
        "Phân tích từng đoạn text sau. "
        "Trả về JSON array với mỗi phần tử có format: "
        '{"labels": [...], "viral_score": X, "summary": "...", "reason": "..."}\n\n'
    )
    for i, chunk in enumerate(chunks):
        batch_prompt += f"--- Đoạn {i + 1} ---\n{chunk.text[:1000]}\n\n"

    batch_prompt += (
        "\nTiêu chí viral_score (0-10): Curiosity +2, Emotion +2, "
        "Actionable +2, Controversy +2, Relatability +2.\n"
        "Labels: quote, summary, story, example, insight, hook, tip, controversial.\n"
        "Trả về JSON array, không giải thích thêm."
    )

    if provider in ("openai", "custom"):
        response_text = _call_openai(batch_prompt, api_key=api_key, model=model, base_url=base_url)
    elif provider == "anthropic":
        response_text = _call_anthropic(batch_prompt, api_key=api_key, model=model)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    # Parse batch response
    try:
        # Extract JSON array from response
        json_match = response_text.strip()
        if json_match.startswith("```"):
            json_match = json_match.split("```")[1]
            if json_match.startswith("json"):
                json_match = json_match[4:]
        data = json.loads(json_match)
        if not isinstance(data, list):
            data = [data]
    except (json.JSONDecodeError, IndexError):
        # Fallback: analyze individually
        return [_mock_analyze(chunk) for chunk in chunks]

    valid_values = {lbl.value for lbl in ChunkLabel}
    results: list[AnalyzedChunk] = []
    for i, chunk in enumerate(chunks):
        if i < len(data):
            item = data[i]
            labels = [
                ChunkLabel(lbl)
                for lbl in item.get("labels", [])
                if lbl in valid_values
            ]
            results.append(
                AnalyzedChunk(
                    chunk=chunk,
                    labels=labels,
                    viral_score=float(item.get("viral_score", 0)),
                    summary=item.get("summary", ""),
                    reason=item.get("reason", ""),
                )
            )
        else:
            results.append(_mock_analyze(chunk))

    return results


def _call_openai(
    prompt: str, api_key: str, model: str, base_url: str | None = None
) -> str:
    """Call OpenAI-compatible API."""
    import httpx

    url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not url.endswith("/chat/completions"):
        url = url.rstrip("/") + "/chat/completions"

    response = httpx.post(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 1000,
        },
        timeout=120.0,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def _call_anthropic(prompt: str, api_key: str, model: str) -> str:
    """Call Anthropic API."""
    import httpx

    if not model.startswith("claude"):
        model = "claude-sonnet-4-20250514"

    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": model,
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    data = response.json()
    return data["content"][0]["text"]


def _parse_response(chunk: Chunk, response_text: str) -> AnalyzedChunk:
    """Parse LLM response into AnalyzedChunk."""
    try:
        # Clean response - extract JSON
        text = response_text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
    except (json.JSONDecodeError, IndexError):
        return _mock_analyze(chunk)

    labels = []
    for label_str in data.get("labels", []):
        try:
            labels.append(ChunkLabel(label_str))
        except ValueError:
            continue

    return AnalyzedChunk(
        chunk=chunk,
        labels=labels,
        viral_score=float(data.get("viral_score", 0)),
        summary=data.get("summary", ""),
        reason=data.get("reason", ""),
    )


def _mock_analyze(chunk: Chunk) -> AnalyzedChunk:
    """Generate mock analysis for testing without API."""
    text = chunk.text.lower()
    labels: list[ChunkLabel] = []
    score = 3.0

    # Simple heuristic labeling
    if any(w in text for w in ['"', "\u201c", "\u201d", "nói rằng", "từng nói"]):
        labels.append(ChunkLabel.QUOTE)
        score += 1.5

    if any(w in text for w in ["bài học", "nguyên tắc", "quy tắc", "tip", "mẹo"]):
        labels.append(ChunkLabel.TIP)
        score += 1.0

    if any(w in text for w in ["câu chuyện", "kể rằng", "ngày xưa", "có một"]):
        labels.append(ChunkLabel.STORY)
        score += 1.5

    if any(w in text for w in ["ví dụ", "chẳng hạn", "trường hợp"]):
        labels.append(ChunkLabel.EXAMPLE)
        score += 0.5

    if any(w in text for w in ["tóm lại", "kết luận", "tổng kết", "nhìn chung"]):
        labels.append(ChunkLabel.SUMMARY)

    if any(w in text for w in ["bạn có biết", "sự thật", "bí mật", "ít ai biết"]):
        labels.append(ChunkLabel.HOOK)
        score += 2.0

    if any(w in text for w in ["thật sự", "sai lầm", "nguy hiểm", "cảnh báo"]):
        labels.append(ChunkLabel.CONTROVERSIAL)
        score += 1.5

    if not labels:
        labels.append(ChunkLabel.INSIGHT)

    # Cap score at 10
    score = min(score, 10.0)

    return AnalyzedChunk(
        chunk=chunk,
        labels=labels,
        viral_score=round(score, 1),
        summary=chunk.text[:100] + "..." if len(chunk.text) > 100 else chunk.text,
        reason="Mock analysis (heuristic-based)",
    )


def _get_api_key(provider: str) -> str | None:
    """Get API key from environment."""
    if provider in ("openai", "custom"):
        return os.environ.get("OPENAI_API_KEY") or os.environ.get("API_KEY")
    elif provider == "anthropic":
        return os.environ.get("ANTHROPIC_API_KEY")
    return None
