"""Audio transcription module for converting audiobooks/podcasts to text."""

from __future__ import annotations

import re
from pathlib import Path

from .models import BookMetadata, SourceFormat


def transcribe_audio(
    file_path: str,
    model_size: str = "base",
    language: str = "vi",
) -> tuple[BookMetadata, str]:
    """Transcribe an audio file to Markdown text using Whisper.

    Args:
        file_path: Path to audio file (MP3, WAV, M4A, FLAC, OGG, etc.).
        model_size: Whisper model size (tiny, base, small, medium, large).
        language: Language code for transcription.

    Returns:
        Tuple of (metadata, markdown_text with timestamps).
    """
    import whisper

    path = Path(file_path)

    # Load model
    model = whisper.load_model(model_size)

    # Transcribe
    result = model.transcribe(
        str(path),
        language=language,
        verbose=False,
    )

    # Build markdown with timestamps
    segments = result.get("segments", [])
    markdown = _segments_to_markdown(segments, path.stem)

    # Estimate chapters from silence gaps or segment clustering
    chapters = _estimate_chapters(segments)

    metadata = BookMetadata(
        title=path.stem,
        chapters=chapters,
        source_format=SourceFormat.AUDIO,
        file_path=file_path,
        language=language,
    )

    return metadata, markdown


def transcribe_audio_with_timestamps(
    file_path: str,
    model_size: str = "base",
    language: str = "vi",
) -> tuple[BookMetadata, str, list[dict]]:
    """Transcribe audio and return both text and timestamp data.

    Useful for video clip generation — timestamps allow cutting
    audio at specific quotes/segments.

    Args:
        file_path: Path to audio file.
        model_size: Whisper model size.
        language: Language code.

    Returns:
        Tuple of (metadata, markdown_text, segments_with_timestamps).
    """
    import whisper

    path = Path(file_path)
    model = whisper.load_model(model_size)

    result = model.transcribe(
        str(path),
        language=language,
        verbose=False,
    )

    segments = result.get("segments", [])
    markdown = _segments_to_markdown(segments, path.stem)
    chapters = _estimate_chapters(segments)

    # Build timestamp data for clip generation
    timestamp_data = [
        {
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip(),
            "id": i,
        }
        for i, seg in enumerate(segments)
    ]

    metadata = BookMetadata(
        title=path.stem,
        chapters=chapters,
        source_format=SourceFormat.AUDIO,
        file_path=file_path,
        language=language,
    )

    return metadata, markdown, timestamp_data


def _segments_to_markdown(segments: list[dict], title: str) -> str:
    """Convert Whisper segments to readable Markdown with timestamps."""
    if not segments:
        return ""

    lines: list[str] = []
    lines.append(f"# {title}\n")

    current_paragraph: list[str] = []
    last_end = 0.0

    for seg in segments:
        start = seg["start"]
        text = seg["text"].strip()

        if not text:
            continue

        # New paragraph if gap > 2 seconds
        if start - last_end > 2.0 and current_paragraph:
            lines.append(" ".join(current_paragraph))
            lines.append("")
            current_paragraph = []

        # Add timestamp marker every ~30 seconds
        if not current_paragraph or start - last_end > 30.0:
            timestamp = _format_timestamp(start)
            current_paragraph.append(f"[{timestamp}] {text}")
        else:
            current_paragraph.append(text)

        last_end = seg["end"]

    # Flush remaining
    if current_paragraph:
        lines.append(" ".join(current_paragraph))

    return "\n".join(lines)


def _format_timestamp(seconds: float) -> str:
    """Format seconds to MM:SS or HH:MM:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _estimate_chapters(segments: list[dict]) -> int:
    """Estimate number of chapters/sections from audio segments.

    Uses silence gaps (>5s) as chapter boundaries.
    """
    if not segments:
        return 0

    chapters = 1
    for i in range(1, len(segments)):
        gap = segments[i]["start"] - segments[i - 1]["end"]
        if gap > 5.0:  # 5+ second gap = likely new section
            chapters += 1

    return chapters


def get_audio_duration(file_path: str) -> float:
    """Get audio file duration in seconds using ffprobe.

    Args:
        file_path: Path to audio file.

    Returns:
        Duration in seconds.
    """
    import subprocess

    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-show_entries",
            "format=duration", "-of",
            "default=noprint_wrappers=1:nokey=1",
            file_path,
        ],
        capture_output=True,
        text=True,
    )

    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def is_supported_audio(file_path: str) -> bool:
    """Check if a file is a supported audio format."""
    supported = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma", ".aac", ".opus"}
    return Path(file_path).suffix.lower() in supported


def _clean_transcript(text: str) -> str:
    """Clean up transcription text."""
    # Remove filler words common in Vietnamese audiobooks
    fillers = [r"\b(ừm|à|uh|uhm|hmm)\b"]
    for filler in fillers:
        text = re.sub(filler, "", text, flags=re.IGNORECASE)

    # Clean extra spaces
    text = re.sub(r"  +", " ", text)
    return text.strip()
