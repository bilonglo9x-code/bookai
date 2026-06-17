"""Video rendering module for BookAI.

Combines TTS audio + book cover image + text overlays into a TikTok/Reels-ready MP4.
Uses FFmpeg (must be installed: `apt install ffmpeg`).

Output format: 1080×1920 (9:16 portrait), H.264, AAC audio.

Usage::

    from bookai.video_render import render_radio_video, VideoConfig

    cfg = VideoConfig(resolution="1080x1920", font_size=48)
    result = render_radio_video(
        script=radio_script,
        audio_path="output/script_001.mp3",
        cover_image="cover.jpg",     # optional
        output_path="output/video_001.mp4",
        config=cfg,
    )
    print(result.output_path, result.duration_seconds)
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class VideoConfig:
    """Configuration for video rendering."""

    resolution: str = "1080x1920"          # WxH — TikTok/Reels portrait
    fps: int = 30
    font_size: int = 52                     # px for body text
    hook_font_size: int = 64               # px for hook (opening text)
    font_color: str = "white"
    bg_color: str = "black"                # fallback background color
    cover_blur: bool = True                # blur cover image as background
    blur_strength: int = 20               # gaussian blur sigma
    overlay_opacity: float = 0.55         # dark overlay on blurred cover
    text_x: str = "(w-tw)/2"              # centered
    text_y: str = "(h-th)/2"              # vertically centered
    max_chars_per_line: int = 30          # Vietnamese chars per line
    video_bitrate: str = "4M"
    audio_bitrate: str = "192k"
    watermark: str = ""                   # e.g. "@yourtiktok" — bottom-right

    @property
    def width(self) -> int:
        return int(self.resolution.split("x")[0])

    @property
    def height(self) -> int:
        return int(self.resolution.split("x")[1])


@dataclass
class VideoResult:
    """Result of a video render operation."""

    output_path: Path
    duration_seconds: float = 0.0
    file_size_mb: float = 0.0
    ok: bool = True
    error: str = ""
    cmd: str = ""  # ffmpeg command used (for debugging)


# ---------------------------------------------------------------------------
# Main render functions
# ---------------------------------------------------------------------------


def render_radio_video(
    script: object,
    audio_path: str | Path,
    output_path: str | Path,
    cover_image: str | Path | None = None,
    config: VideoConfig | None = None,
) -> VideoResult:
    """Render a complete TikTok video from a RadioScript + audio.

    Layout:
        - Background: blurred + darkened book cover (or solid color)
        - Hook text: large, centered, shown for ~3s
        - Body: scrolling subtitles synced to audio duration
        - CTA: shown in final ~10s

    Args:
        script: RadioScript from content_studio.
        audio_path: Path to MP3/WAV voiceover.
        output_path: Output MP4 path.
        cover_image: Optional book cover image path.
        config: VideoConfig (uses defaults if None).

    Returns:
        VideoResult with path, duration, file size.
    """
    cfg = config or VideoConfig()
    output_path = Path(output_path)
    audio_path = Path(audio_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not audio_path.exists():
        return VideoResult(output_path=output_path, ok=False,
                           error=f"Audio not found: {audio_path}")

    # Get audio duration
    duration = _get_duration(audio_path)
    if duration <= 0:
        return VideoResult(output_path=output_path, ok=False,
                           error="Could not determine audio duration")

    hook = getattr(script, "hook", "") or ""
    cta = getattr(script, "cta", "") or ""
    cta_start = max(duration - 12.0, duration * 0.85)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # Step 1: Build background video (image loop or color)
        bg_video = _build_background(
            tmp_path / "bg.mp4",
            duration=duration,
            cover_image=cover_image,
            cfg=cfg,
        )

        # Step 2: Add text overlays (hook at start, CTA at end)
        with_text = _add_text_overlays(
            bg_video,
            tmp_path / "with_text.mp4",
            hook=hook,
            cta=cta,
            cta_start=cta_start,
            cfg=cfg,
        )

        # Step 3: Merge with audio
        result = _merge_audio(
            with_text,
            audio_path,
            output_path,
            cfg=cfg,
        )

    if result.ok and output_path.exists():
        result.duration_seconds = _get_duration(output_path)
        result.file_size_mb = output_path.stat().st_size / (1024 * 1024)

    return result


def render_quote_video(
    quote_text: str,
    audio_path: str | Path,
    output_path: str | Path,
    book_title: str = "",
    author: str = "",
    cover_image: str | Path | None = None,
    config: VideoConfig | None = None,
) -> VideoResult:
    """Render a short quote video (15-30s) for Instagram/TikTok.

    Args:
        quote_text: The quote to display.
        audio_path: Audio narration of the quote.
        output_path: Output MP4 path.
        book_title: Book title shown as subtitle.
        author: Author shown below quote.
        cover_image: Optional background cover image.
        config: VideoConfig.

    Returns:
        VideoResult.
    """
    cfg = config or VideoConfig()
    output_path = Path(output_path)
    audio_path = Path(audio_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not audio_path.exists():
        return VideoResult(output_path=output_path, ok=False,
                           error=f"Audio not found: {audio_path}")

    duration = _get_duration(audio_path)
    if duration <= 0:
        return VideoResult(output_path=output_path, ok=False, error="Invalid audio")

    attribution = f"— {author}, {book_title}" if author and book_title else book_title or author

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        bg = _build_background(tmp_path / "bg.mp4", duration=duration,
                               cover_image=cover_image, cfg=cfg)

        with_text = _add_centered_text(
            bg,
            tmp_path / "with_text.mp4",
            main_text=quote_text,
            subtitle=attribution,
            cfg=cfg,
        )

        result = _merge_audio(with_text, audio_path, output_path, cfg=cfg)

    if result.ok and output_path.exists():
        result.duration_seconds = _get_duration(output_path)
        result.file_size_mb = output_path.stat().st_size / (1024 * 1024)

    return result


def render_slideshow_video(
    slides: list[dict],
    output_path: str | Path,
    audio_path: str | Path | None = None,
    seconds_per_slide: float = 4.0,
    config: VideoConfig | None = None,
) -> VideoResult:
    """Render a carousel/slideshow video from a list of slide dicts.

    Each slide dict: ``{"text": "...", "image": "path/to/img.png" (optional)}``

    Args:
        slides: List of slide definitions.
        output_path: Output MP4 path.
        audio_path: Optional background audio.
        seconds_per_slide: Duration per slide.
        config: VideoConfig.

    Returns:
        VideoResult.
    """
    cfg = config or VideoConfig()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not slides:
        return VideoResult(output_path=output_path, ok=False, error="No slides provided")

    total_duration = len(slides) * seconds_per_slide

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        slide_videos: list[Path] = []

        for i, slide in enumerate(slides):
            text = slide.get("text", "")
            img = slide.get("image")
            slide_out = tmp_path / f"slide_{i:03d}.mp4"

            bg = _build_background(
                tmp_path / f"bg_{i}.mp4",
                duration=seconds_per_slide,
                cover_image=img,
                cfg=cfg,
            )
            with_text = _add_centered_text(
                bg, slide_out, main_text=text, cfg=cfg
            )
            slide_videos.append(with_text)

        # Concatenate slides
        concat_list = tmp_path / "concat.txt"
        concat_list.write_text(
            "\n".join(f"file '{p}'" for p in slide_videos), encoding="utf-8"
        )
        concat_out = tmp_path / "concat.mp4"
        _run_ffmpeg([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list), "-c", "copy", str(concat_out),
        ])

        if audio_path and Path(audio_path).exists():
            result = _merge_audio(concat_out, Path(audio_path), output_path, cfg=cfg,
                                  trim_audio=True, total_duration=total_duration)
        else:
            import shutil
            shutil.copy(concat_out, output_path)
            result = VideoResult(output_path=output_path, ok=True)

    if result.ok and output_path.exists():
        result.duration_seconds = _get_duration(output_path)
        result.file_size_mb = output_path.stat().st_size / (1024 * 1024)
    return result


# ---------------------------------------------------------------------------
# FFmpeg building blocks
# ---------------------------------------------------------------------------


def _build_background(
    output: Path,
    duration: float,
    cover_image: str | Path | None,
    cfg: VideoConfig,
) -> Path:
    """Build a background video: blurred cover or solid color loop."""
    w, h = cfg.width, cfg.height

    if cover_image and Path(cover_image).exists():
        # Blur + darken cover image, loop for `duration` seconds
        vf_parts = [
            f"scale={w}:{h}:force_original_aspect_ratio=increase",
            f"crop={w}:{h}",
            f"gblur=sigma={cfg.blur_strength}" if cfg.cover_blur else "",
        ]
        vf = ",".join(v for v in vf_parts if v)
        # Overlay dark semi-transparent rectangle
        overlay_color = f"color=black:size={w}x{h}:rate={cfg.fps}"
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(cover_image),
            "-f", "lavfi", "-i", overlay_color,
            "-filter_complex",
            f"[0:v]{vf}[bg];[bg][1:v]blend=all_mode=multiply:all_opacity={cfg.overlay_opacity}[v]",
            "-map", "[v]",
            "-t", str(duration), "-r", str(cfg.fps),
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            str(output),
        ]
    else:
        # Solid color background
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i",
            f"color=c={cfg.bg_color}:size={w}x{h}:rate={cfg.fps}:duration={duration}",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            str(output),
        ]

    _run_ffmpeg(cmd)
    return output


def _add_text_overlays(
    input_video: Path,
    output: Path,
    hook: str,
    cta: str,
    cta_start: float,
    cfg: VideoConfig,
) -> Path:
    """Add hook text at start (0-3s) and CTA at end."""
    hook_clean = _escape_ffmpeg_text(hook[:120])  # cap at 120 chars
    cta_clean = _escape_ffmpeg_text(cta[:200])

    hook_wrapped = _wrap_text(hook_clean, cfg.max_chars_per_line)
    cta_wrapped = _wrap_text(cta_clean, cfg.max_chars_per_line)

    draw_hook = (
        f"drawtext=text='{hook_wrapped}':"
        f"fontsize={cfg.hook_font_size}:fontcolor={cfg.font_color}:"
        f"x={cfg.text_x}:y=100:enable='between(t,0,3)':"
        "shadowcolor=black:shadowx=2:shadowy=2"
    )
    draw_cta = (
        f"drawtext=text='{cta_wrapped}':"
        f"fontsize={cfg.font_size}:fontcolor=yellow:"
        f"x={cfg.text_x}:y=(h-200):"
        f"enable='gte(t,{cta_start:.1f})':"
        "shadowcolor=black:shadowx=2:shadowy=2"
    )

    vf = f"{draw_hook},{draw_cta}"
    if cfg.watermark:
        wm = _escape_ffmpeg_text(cfg.watermark)
        vf += (
            f",drawtext=text='{wm}':fontsize=28:fontcolor=white@0.6:"
            "x=(w-tw-20):y=(h-th-20)"
        )

    cmd = [
        "ffmpeg", "-y", "-i", str(input_video),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        str(output),
    ]
    _run_ffmpeg(cmd)
    return output


def _add_centered_text(
    input_video: Path,
    output: Path,
    main_text: str,
    subtitle: str = "",
    cfg: VideoConfig | None = None,
) -> Path:
    """Add centered main text + optional subtitle (for quote videos)."""
    cfg = cfg or VideoConfig()
    main_clean = _escape_ffmpeg_text(main_text[:300])
    main_wrapped = _wrap_text(main_clean, cfg.max_chars_per_line)

    draw_main = (
        f"drawtext=text='{main_wrapped}':"
        f"fontsize={cfg.font_size}:fontcolor={cfg.font_color}:"
        f"x={cfg.text_x}:y={cfg.text_y}:"
        "shadowcolor=black:shadowx=3:shadowy=3"
    )
    vf = draw_main

    if subtitle:
        sub_clean = _escape_ffmpeg_text(subtitle[:100])
        draw_sub = (
            f"drawtext=text='{sub_clean}':"
            f"fontsize={int(cfg.font_size * 0.65)}:fontcolor=white@0.8:"
            f"x={cfg.text_x}:y=(h*3/4):"
            "shadowcolor=black:shadowx=2:shadowy=2"
        )
        vf = f"{draw_main},{draw_sub}"

    cmd = [
        "ffmpeg", "-y", "-i", str(input_video),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        str(output),
    ]
    _run_ffmpeg(cmd)
    return output


def _merge_audio(
    video: Path,
    audio: Path,
    output: Path,
    cfg: VideoConfig,
    trim_audio: bool = False,
    total_duration: float = 0.0,
) -> VideoResult:
    """Merge video + audio track into final MP4."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video),
        "-i", str(audio),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", cfg.audio_bitrate,
        "-shortest",
    ]
    if trim_audio and total_duration > 0:
        cmd += ["-t", str(total_duration)]
    cmd.append(str(output))

    returncode, stderr = _run_ffmpeg(cmd)
    if returncode != 0:
        return VideoResult(output_path=output, ok=False,
                           error=f"FFmpeg merge failed:\n{stderr[-500:]}")
    return VideoResult(output_path=output, ok=True, cmd=" ".join(cmd))


# ---------------------------------------------------------------------------
# FFmpeg utilities
# ---------------------------------------------------------------------------


def _run_ffmpeg(cmd: list[str]) -> tuple[int, str]:
    """Run an FFmpeg command. Returns (returncode, stderr)."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300
        )
        return result.returncode, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "FFmpeg timed out"
    except FileNotFoundError:
        return -1, "ffmpeg not found — install with: sudo apt install ffmpeg"


def _get_duration(path: Path) -> float:
    """Get media duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(path),
            ],
            capture_output=True, text=True, timeout=15,
        )
        return float(result.stdout.strip())
    except Exception:  # noqa: BLE001
        return 0.0


def _escape_ffmpeg_text(text: str) -> str:
    """Escape special characters for FFmpeg drawtext filter."""
    # Order matters: escape backslash first
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    text = text.replace(":", "\\:")
    text = text.replace("%", "\\%")
    return text


def _wrap_text(text: str, max_chars: int) -> str:
    """Wrap text into multiple lines for drawtext (using \\n)."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = f"{current} {word}".strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\\n".join(lines)


def check_ffmpeg() -> bool:
    """Return True if ffmpeg is available."""
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return result.returncode == 0
    except Exception:  # noqa: BLE001
        return False
