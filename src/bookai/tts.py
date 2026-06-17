"""Text-to-Speech module for BookAI.

Converts radio scripts to Vietnamese voiceover audio using Microsoft Edge TTS
(free, no API key required). Falls back gracefully if edge-tts is not installed.

Voices (Vietnamese):
    - vi-VN-HoaiMyNeural   — Female, clear narration (recommended)
    - vi-VN-NamMinhNeural  — Male, deeper tone

Usage::

    from bookai.tts import synthesize_text, synthesize_script

    # Simple text → MP3
    output = synthesize_text("Xin chào, đây là thử nghiệm.", "output.mp3")

    # Full radio script → MP3
    output = synthesize_script(script, "script_001.mp3", voice="vi-VN-HoaiMyNeural")
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Available voices
# ---------------------------------------------------------------------------

VIETNAMESE_VOICES: dict[str, str] = {
    "vi-VN-HoaiMyNeural": "Female — clear, warm (recommended for radio sách)",
    "vi-VN-NamMinhNeural": "Male — authoritative, deeper tone",
}

DEFAULT_VOICE = "vi-VN-HoaiMyNeural"


@dataclass
class TTSResult:
    """Result of a TTS synthesis operation."""

    output_path: Path
    voice: str
    duration_seconds: float = 0.0
    text_length: int = 0
    ok: bool = True
    error: str = ""

    @property
    def filename(self) -> str:
        return self.output_path.name


# ---------------------------------------------------------------------------
# Core synthesis
# ---------------------------------------------------------------------------


def synthesize_text(
    text: str,
    output_path: str | Path,
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
    pitch: str = "+0Hz",
) -> TTSResult:
    """Convert text to speech and save as MP3/WAV.

    Args:
        text: Text to synthesize (Vietnamese supported).
        output_path: Output file path (.mp3 recommended).
        voice: Edge TTS voice name (see VIETNAMESE_VOICES).
        rate: Speaking rate adjustment e.g. '+10%', '-5%', '+0%'.
        pitch: Pitch adjustment e.g. '+0Hz', '-5Hz'.

    Returns:
        TTSResult with output path and metadata.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    text = _clean_text_for_tts(text)
    if not text.strip():
        return TTSResult(
            output_path=output_path,
            voice=voice,
            ok=False,
            error="Empty text after cleaning",
        )

    try:
        import edge_tts  # noqa: PLC0415
    except ImportError:
        return TTSResult(
            output_path=output_path,
            voice=voice,
            ok=False,
            error="edge-tts not installed. Run: pip install edge-tts",
        )

    async def _run() -> None:
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        await communicate.save(str(output_path))

    try:
        asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001
        return TTSResult(
            output_path=output_path,
            voice=voice,
            ok=False,
            error=str(exc),
        )

    duration = _get_audio_duration(output_path)
    return TTSResult(
        output_path=output_path,
        voice=voice,
        duration_seconds=duration,
        text_length=len(text),
        ok=True,
    )


def synthesize_script(
    script: object,
    output_path: str | Path,
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
    include_hook: bool = True,
    include_body: bool = True,
    include_cta: bool = True,
) -> TTSResult:
    """Synthesize a RadioScript object to an audio file.

    Args:
        script: A `RadioScript` instance (from content_studio).
        output_path: Output .mp3 file.
        voice: TTS voice.
        rate: Speaking rate.
        include_hook: Include the hook section.
        include_body: Include the body section.
        include_cta: Include the CTA section.

    Returns:
        TTSResult.
    """
    parts: list[str] = []
    if include_hook and getattr(script, "hook", ""):
        parts.append(script.hook)  # type: ignore[attr-defined]
    if include_body and getattr(script, "body", ""):
        parts.append(script.body)  # type: ignore[attr-defined]
    if include_cta and getattr(script, "cta", ""):
        parts.append(script.cta)  # type: ignore[attr-defined]

    full_text = "\n\n".join(parts)
    return synthesize_text(full_text, output_path, voice=voice, rate=rate)


def synthesize_batch(
    texts: list[tuple[str, str]],
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
) -> list[TTSResult]:
    """Synthesize multiple (text, output_path) pairs sequentially.

    Args:
        texts: List of (text, output_path) tuples.
        voice: TTS voice for all items.
        rate: Speaking rate for all items.

    Returns:
        List of TTSResult.
    """
    results: list[TTSResult] = []
    for text, path in texts:
        result = synthesize_text(text, path, voice=voice, rate=rate)
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# Async variant (for concurrent synthesis)
# ---------------------------------------------------------------------------


async def synthesize_text_async(
    text: str,
    output_path: str | Path,
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
) -> TTSResult:
    """Async version of synthesize_text for concurrent use."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = _clean_text_for_tts(text)

    try:
        import edge_tts  # noqa: PLC0415

        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(str(output_path))
        duration = _get_audio_duration(output_path)
        return TTSResult(output_path=output_path, voice=voice, duration_seconds=duration, ok=True)
    except ImportError:
        return TTSResult(output_path=output_path, voice=voice, ok=False,
                         error="edge-tts not installed")
    except Exception as exc:  # noqa: BLE001
        return TTSResult(output_path=output_path, voice=voice, ok=False, error=str(exc))


async def synthesize_scripts_concurrent(
    scripts_and_paths: list[tuple[object, str | Path]],
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
) -> list[TTSResult]:
    """Synthesize multiple RadioScripts concurrently (faster for batches).

    Args:
        scripts_and_paths: List of (RadioScript, output_path) pairs.
        voice: TTS voice.
        rate: Speaking rate.

    Returns:
        List of TTSResult in same order.
    """
    tasks = []
    for script, path in scripts_and_paths:
        parts = [
            getattr(script, "hook", ""),
            getattr(script, "body", ""),
            getattr(script, "cta", ""),
        ]
        text = "\n\n".join(p for p in parts if p)
        tasks.append(synthesize_text_async(text, path, voice=voice, rate=rate))
    return list(await asyncio.gather(*tasks))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _clean_text_for_tts(text: str) -> str:
    """Remove markdown, emoji, and symbols that TTS reads awkwardly."""
    # Remove markdown bold/italic
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    # Remove markdown links [text](url) → text
    text = re.sub(r"\[(.+?)\]\(https?://\S+\)", r"\1", text)
    # Remove bare URLs
    text = re.sub(r"https?://\S+", "", text)
    # Remove emoji
    text = re.sub(
        r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
        r"\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF"
        r"\u2600-\u26FF\u2700-\u27BF]",
        "",
        text,
    )
    # Remove hashtags
    text = re.sub(r"#\w+", "", text)
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _get_audio_duration(path: Path) -> float:
    """Get audio duration in seconds using ffprobe, or 0 on failure."""
    import subprocess  # noqa: PLC0415

    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(path),
            ],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:  # noqa: BLE001
        return 0.0


def list_voices() -> dict[str, str]:
    """Return available Vietnamese TTS voices."""
    return dict(VIETNAMESE_VOICES)


def estimate_duration(text: str, rate_percent: int = 0) -> float:
    """Estimate audio duration in seconds for Vietnamese text.

    Vietnamese narration speed ≈ 2.5 words/sec at normal rate.
    """
    words = len(text.split())
    base_speed = 2.5  # words/sec
    multiplier = 1 + rate_percent / 100
    return words / (base_speed * multiplier)
