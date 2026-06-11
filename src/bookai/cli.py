"""CLI interface for BookAI."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .analyzer import analyze_chunks, analyze_chunks_batch
from .chunker import chunk_markdown
from .content_studio import (
    generate_all,
    generate_all_with_ai,
    generate_quote_images,
)
from .converter import convert_audio, convert_file, convert_image, convert_images_dir
from .models import BookResult, ChunkLabel

app = typer.Typer(
    name="bookai",
    help="Convert books to affiliate marketing content using AI.",
)
console = Console()


@app.command()
def process(
    file_path: str = typer.Argument(
        help="Path to book file (.epub, .pdf, .txt, .md, .png, .jpg, .mp3, .wav, ...)"
    ),
    output: str | None = typer.Option(None, "-o", "--output", help="Output JSON file path"),
    max_chunks: int = typer.Option(100, "--max-chunks", help="Max chunks to analyze"),
    max_tokens: int = typer.Option(500, "--max-tokens", help="Max tokens per chunk"),
    provider: str = typer.Option(
        "mock", "--provider", help="AI provider: openai, anthropic, custom, mock"
    ),
    model: str = typer.Option("gpt-4o-mini", "--model", help="Model name for AI provider"),
    api_key: str | None = typer.Option(None, "--api-key", help="API key (or use env var)"),
    base_url: str | None = typer.Option(
        None, "--base-url", help="Custom API base URL (OpenAI-compatible)"
    ),
    top_n: int = typer.Option(10, "--top", help="Show top N results"),
    batch: bool = typer.Option(False, "--batch", help="Use batch analysis (faster, less accurate)"),
) -> None:
    """Process a book file: convert → chunk → analyze.

    Examples:
        bookai process book.epub
        bookai process book.pdf --provider openai --top 20
        bookai process book.epub -o results.json --provider mock
    """
    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(1)

    # Step 1: Convert
    console.print(f"\n[bold blue]📖 Converting:[/bold blue] {path.name}")
    try:
        metadata, markdown = convert_file(file_path)
    except Exception as e:
        console.print(f"[red]Error converting file: {e}[/red]")
        raise typer.Exit(1)

    console.print(f"  Title: [green]{metadata.title}[/green]")
    console.print(f"  Author: {metadata.author}")
    console.print(f"  Chapters: {metadata.chapters}")
    console.print(f"  Format: {metadata.source_format.value}")

    # Step 2: Chunk
    console.print(f"\n[bold blue]✂️  Chunking:[/bold blue] max {max_tokens} tokens/chunk")
    chunks = chunk_markdown(markdown, book_title=metadata.title, max_tokens=max_tokens)
    console.print(f"  Total chunks: [green]{len(chunks)}[/green]")

    # Step 3: Analyze
    chunks_to_analyze = chunks[:max_chunks]
    console.print(
        f"\n[bold blue]🤖 Analyzing:[/bold blue] {len(chunks_to_analyze)} chunks "
        f"(provider: {provider})"
    )

    try:
        if batch and provider != "mock":
            analyzed = analyze_chunks_batch(
                chunks_to_analyze,
                api_key=api_key,
                model=model,
                provider=provider,
                base_url=base_url,
            )
        else:
            analyzed = analyze_chunks(
                chunks_to_analyze,
                api_key=api_key,
                model=model,
                provider=provider,
                base_url=base_url,
            )
    except Exception as e:
        console.print(f"[red]Error during analysis: {e}[/red]")
        raise typer.Exit(1)

    # Build result
    result = BookResult(
        metadata=metadata,
        markdown=markdown[:1000] + "..." if len(markdown) > 1000 else markdown,
        chunks=chunks,
        analyzed=analyzed,
        top_quotes=[a for a in analyzed if ChunkLabel.QUOTE in a.labels],
        top_hooks=[a for a in analyzed if ChunkLabel.HOOK in a.labels],
    )

    # Display results
    _display_results(result, top_n=top_n)

    # Save output
    if output:
        output_path = Path(output)
        output_data = result.model_dump()
        output_path.write_text(json.dumps(output_data, ensure_ascii=False, indent=2))
        console.print(f"\n[green]Results saved to: {output_path}[/green]")


@app.command()
def convert(
    file_path: str = typer.Argument(help="Path to book file"),
    output: str | None = typer.Option(None, "-o", "--output", help="Output markdown file"),
) -> None:
    """Convert a book file to Markdown (without analysis)."""
    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(1)

    metadata, markdown = convert_file(file_path)

    console.print(f"Title: [green]{metadata.title}[/green]")
    console.print(f"Author: {metadata.author}")
    console.print(f"Chapters: {metadata.chapters}")
    console.print(f"Markdown length: {len(markdown)} chars")

    if output:
        Path(output).write_text(markdown, encoding="utf-8")
        console.print(f"\n[green]Saved to: {output}[/green]")
    else:
        console.print("\n" + markdown[:2000])
        if len(markdown) > 2000:
            console.print(f"\n[dim]... ({len(markdown) - 2000} more characters)[/dim]")


@app.command()
def chunks(
    file_path: str = typer.Argument(help="Path to book file"),
    max_tokens: int = typer.Option(500, "--max-tokens", help="Max tokens per chunk"),
    show: int = typer.Option(10, "--show", help="Number of chunks to display"),
) -> None:
    """Convert and chunk a book (without analysis)."""
    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(1)

    metadata, markdown = convert_file(file_path)
    chunk_list = chunk_markdown(markdown, book_title=metadata.title, max_tokens=max_tokens)

    console.print(f"Book: [green]{metadata.title}[/green]")
    console.print(f"Total chunks: [green]{len(chunk_list)}[/green]\n")

    table = Table(title=f"First {show} chunks")
    table.add_column("#", width=4)
    table.add_column("Chapter", width=20)
    table.add_column("Tokens", width=8)
    table.add_column("Preview", max_width=60)

    for i, chunk in enumerate(chunk_list[:show], 1):
        preview = chunk.text[:80].replace("\n", " ")
        table.add_row(
            str(i),
            chunk.chapter_title[:20],
            str(chunk.token_count),
            preview + "..." if len(chunk.text) > 80 else preview,
        )

    console.print(table)


@app.command()
def generate(
    input_json: str = typer.Argument(help="Path to analysis result JSON (from `process -o`)"),
    output: str | None = typer.Option(None, "-o", "--output", help="Output JSON file path"),
    format: str = typer.Option(
        "all", "--format", help="Content type: all, radio, quote, listicle, caption"
    ),
) -> None:
    """Generate ready-to-post content from analysis results.

    Takes the JSON output of `bookai process -o results.json` and generates
    radio scripts, quote cards, listicles, and captions.

    Examples:
        bookai generate results.json -o content.json
        bookai generate results.json --format radio
    """
    path = Path(input_json)
    if not path.exists():
        console.print(f"[red]Error: File not found: {input_json}[/red]")
        raise typer.Exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    result = BookResult(**data)

    if not result.analyzed:
        console.print("[red]No analyzed chunks found in input. Run `process` first.[/red]")
        raise typer.Exit(1)

    console.print(
        f"\n[bold blue]🎬 Generating content:[/bold blue] "
        f"{result.metadata.title} ({len(result.analyzed)} chunks)"
    )

    pack = generate_all(result.analyzed, result.metadata)

    # Display summary
    console.print(f"\n[bold green]Total content pieces: {pack.total_pieces}[/bold green]\n")

    # Radio scripts
    if pack.radio_scripts and format in ("all", "radio"):
        console.print(f"[bold]🎙️ Radio Scripts ({len(pack.radio_scripts)}):[/bold]\n")
        for i, script in enumerate(pack.radio_scripts, 1):
            console.print(Panel(
                f"[bold cyan]HOOK:[/bold cyan] {script.hook}\n\n"
                f"[bold]BODY:[/bold] {script.body[:300]}"
                f"{'...' if len(script.body) > 300 else ''}\n\n"
                f"[bold yellow]CTA:[/bold yellow] {script.cta}\n\n"
                f"[dim]~{script.estimated_seconds}s | "
                f"{'  '.join('#' + t for t in script.hashtags)}[/dim]",
                title=f"Script #{i}",
                border_style="cyan",
            ))

    # Quote cards
    if pack.quote_cards and format in ("all", "quote"):
        console.print(f"\n[bold]📸 Quote Cards ({len(pack.quote_cards)}):[/bold]\n")
        table = Table()
        table.add_column("#", width=3)
        table.add_column("Quote", max_width=60)
        table.add_column("Caption preview", max_width=40)
        for i, card in enumerate(pack.quote_cards[:10], 1):
            table.add_row(
                str(i),
                card.quote_text[:80] + "..." if len(card.quote_text) > 80 else card.quote_text,
                card.caption[:50] + "...",
            )
        console.print(table)

    # Listicles
    if pack.listicles and format in ("all", "listicle"):
        console.print(f"\n[bold]📋 Listicles ({len(pack.listicles)}):[/bold]\n")
        for ls in pack.listicles:
            console.print(Panel(
                f"[bold]{ls.intro}[/bold]\n\n"
                + "\n".join(ls.items)
                + f"\n\n[yellow]{ls.cta}[/yellow]",
                title=ls.title,
                border_style="green",
            ))

    # Captions
    if pack.captions and format in ("all", "caption"):
        console.print(f"\n[bold]💬 Captions ({len(pack.captions)}):[/bold]\n")
        for i, cap in enumerate(pack.captions[:5], 1):
            console.print(Panel(
                cap.text,
                title=f"Caption #{i} ({cap.platform})",
                border_style="magenta",
            ))

    # Save output
    if output:
        output_path = Path(output)
        output_path.write_text(
            json.dumps(pack.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        console.print(f"\n[green]Content saved to: {output_path}[/green]")


@app.command("generate-ai")
def generate_ai(
    input_json: str = typer.Argument(help="Path to analysis result JSON (from `process -o`)"),
    output: str | None = typer.Option(None, "-o", "--output", help="Output JSON file path"),
    images_dir: str | None = typer.Option(
        None, "--images", help="Directory to save quote card images"
    ),
    image_theme: str = typer.Option(
        "dark", "--theme", help="Image theme: dark, light, gradient_blue, warm"
    ),
    model: str = typer.Option("gpt-4o-mini", "--model", help="Model for AI rewriting"),
    api_key: str | None = typer.Option(None, "--api-key", help="API key"),
    base_url: str | None = typer.Option(
        None, "--base-url", help="Custom API base URL (OpenAI-compatible)"
    ),
    format: str = typer.Option(
        "all", "--format", help="Content type: all, radio, quote, listicle, caption"
    ),
    duration: int = typer.Option(
        3, "--duration", help="Target video duration in minutes (1-5)"
    ),
) -> None:
    """Generate premium content using AI rewriting + quote card images.

    Unlike `generate` (template-based), this command uses an LLM to
    rewrite and EXPAND book content into natural radio scripts (1-5 min).
    Also renders PNG quote card images ready for Instagram/Pinterest.

    Examples:
        bookai generate-ai results.json --base-url https://api.example.com/v1 --duration 3
        bookai generate-ai results.json --images ./cards --theme warm --duration 5
        bookai generate-ai results.json -o content.json --images ./output/cards
    """
    path = Path(input_json)
    if not path.exists():
        console.print(f"[red]Error: File not found: {input_json}[/red]")
        raise typer.Exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    result = BookResult(**data)

    if not result.analyzed:
        console.print("[red]No analyzed chunks found in input. Run `process` first.[/red]")
        raise typer.Exit(1)

    console.print(
        f"\n[bold blue]🎬 AI Content Generation:[/bold blue] "
        f"{result.metadata.title} ({len(result.analyzed)} chunks)"
    )

    # Generate with AI rewriting
    pack = generate_all_with_ai(
        result.analyzed,
        result.metadata,
        api_key=api_key,
        model=model,
        base_url=base_url,
        output_dir=images_dir,
        image_theme=image_theme,
        duration_minutes=duration,
    )

    # Display summary
    console.print(f"\n[bold green]Total content pieces: {pack.total_pieces}[/bold green]\n")

    # Radio scripts
    if pack.radio_scripts and format in ("all", "radio"):
        console.print(f"[bold]🎙️ AI Radio Scripts ({len(pack.radio_scripts)}):[/bold]\n")
        for i, script in enumerate(pack.radio_scripts, 1):
            console.print(Panel(
                f"[bold cyan]HOOK:[/bold cyan] {script.hook}\n\n"
                f"[bold]BODY:[/bold] {script.body[:400]}"
                f"{'...' if len(script.body) > 400 else ''}\n\n"
                f"[bold yellow]CTA:[/bold yellow] {script.cta}\n\n"
                f"[dim]~{script.estimated_seconds}s | "
                f"{'  '.join('#' + t for t in script.hashtags)}[/dim]",
                title=f"Script #{i}: {script.title}",
                border_style="cyan",
            ))

    # Quote cards
    if pack.quote_cards and format in ("all", "quote"):
        console.print(f"\n[bold]📸 Quote Cards ({len(pack.quote_cards)}):[/bold]\n")
        table = Table()
        table.add_column("#", width=3)
        table.add_column("Quote", max_width=60)
        table.add_column("Caption preview", max_width=40)
        for i, card in enumerate(pack.quote_cards[:10], 1):
            table.add_row(
                str(i),
                card.quote_text[:80] + ("..." if len(card.quote_text) > 80 else ""),
                card.caption[:50] + "...",
            )
        console.print(table)

    # Images generated?
    if images_dir:
        img_path = Path(images_dir)
        if img_path.exists():
            png_count = len(list(img_path.glob("*.png")))
            console.print(
                f"\n[bold green]🖼️ Generated {png_count} quote card images "
                f"in: {images_dir}[/bold green]"
            )

    # Listicles
    if pack.listicles and format in ("all", "listicle"):
        console.print(f"\n[bold]📋 Listicles ({len(pack.listicles)}):[/bold]\n")
        for ls in pack.listicles:
            console.print(Panel(
                f"[bold]{ls.intro}[/bold]\n\n"
                + "\n".join(ls.items)
                + f"\n\n[yellow]{ls.cta}[/yellow]",
                title=ls.title,
                border_style="green",
            ))

    # Captions
    if pack.captions and format in ("all", "caption"):
        console.print(f"\n[bold]💬 AI Captions ({len(pack.captions)}):[/bold]\n")
        for i, cap in enumerate(pack.captions[:5], 1):
            console.print(Panel(
                cap.text,
                title=f"Caption #{i} ({cap.platform})",
                border_style="magenta",
            ))

    # Save output
    if output:
        output_path = Path(output)
        output_path.write_text(
            json.dumps(pack.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        console.print(f"\n[green]Content saved to: {output_path}[/green]")


@app.command("render-quotes")
def render_quotes(
    input_json: str = typer.Argument(help="Path to analysis result JSON"),
    output_dir: str = typer.Option("./quote_cards", "-o", "--output", help="Output directory"),
    theme: str = typer.Option("dark", "--theme", help="Theme: dark, light, gradient_blue, warm"),
    max_cards: int = typer.Option(10, "--max", help="Maximum number of cards"),
    min_score: float = typer.Option(5.0, "--min-score", help="Minimum viral score"),
) -> None:
    """Render quote cards as PNG images.

    Generates beautiful 1080x1080 quote card images ready for
    Instagram, Pinterest, or any visual platform.

    Examples:
        bookai render-quotes results.json -o ./cards --theme warm
        bookai render-quotes results.json --max 20 --theme gradient_blue
    """
    path = Path(input_json)
    if not path.exists():
        console.print(f"[red]Error: File not found: {input_json}[/red]")
        raise typer.Exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    result = BookResult(**data)

    if not result.analyzed:
        console.print("[red]No analyzed chunks found. Run `process` first.[/red]")
        raise typer.Exit(1)

    console.print(
        f"\n[bold blue]🖼️ Rendering quote cards:[/bold blue] "
        f"{result.metadata.title} (theme: {theme})"
    )

    paths = generate_quote_images(
        result.analyzed,
        result.metadata,
        output_dir=output_dir,
        max_cards=max_cards,
        min_score=min_score,
        theme=theme,
    )

    console.print(f"\n[bold green]Generated {len(paths)} quote card images:[/bold green]")
    for p in paths:
        console.print(f"  {p}")


def _display_results(result: BookResult, top_n: int = 10) -> None:
    """Display analysis results in a formatted table."""
    console.print(f"\n[bold]{'=' * 60}[/bold]")
    console.print(f"[bold green]📊 Analysis Results: {result.metadata.title}[/bold green]")
    console.print(f"[bold]{'=' * 60}[/bold]\n")

    # Stats
    total = len(result.analyzed)
    avg_score = sum(a.viral_score for a in result.analyzed) / total if total else 0
    console.print(f"  Total analyzed: {total}")
    console.print(f"  Average viral score: {avg_score:.1f}/10")
    console.print(f"  Quotes found: {len(result.top_quotes)}")
    console.print(f"  Hooks found: {len(result.top_hooks)}")

    # Label distribution
    label_counts: dict[str, int] = {}
    for a in result.analyzed:
        for label in a.labels:
            label_counts[label.value] = label_counts.get(label.value, 0) + 1

    if label_counts:
        console.print("\n  [bold]Label distribution:[/bold]")
        for label, count in sorted(label_counts.items(), key=lambda x: -x[1]):
            bar = "█" * (count * 2)
            console.print(f"    {label:14s} {bar} ({count})")

    # Top content by viral score
    top = result.get_top_content(top_n)
    if top:
        console.print(f"\n[bold]🔥 Top {top_n} by Viral Score:[/bold]\n")
        table = Table()
        table.add_column("#", width=3)
        table.add_column("Score", width=6)
        table.add_column("Labels", width=24)
        table.add_column("Content Preview", max_width=50)

        for i, item in enumerate(top, 1):
            labels_str = ", ".join(lbl.value for lbl in item.labels)
            preview = item.chunk.text[:60].replace("\n", " ")
            score_color = (
                "green" if item.viral_score >= 7
                else "yellow" if item.viral_score >= 5
                else "white"
            )
            table.add_row(
                str(i),
                f"[{score_color}]{item.viral_score:.1f}[/{score_color}]",
                labels_str,
                preview + "...",
            )

        console.print(table)

    # Top quotes
    if result.top_quotes:
        console.print("\n[bold]💬 Best Quotes:[/bold]\n")
        for i, q in enumerate(sorted(result.top_quotes, key=lambda x: -x.viral_score)[:5], 1):
            console.print(
                Panel(
                    q.chunk.text[:200],
                    title=f"Quote #{i} (score: {q.viral_score})",
                    border_style="cyan",
                )
            )


@app.command("ocr")
def ocr_command(
    file_path: str = typer.Argument(help="Path to image file or directory of images"),
    output: str | None = typer.Option(None, "-o", "--output", help="Output markdown file"),
    lang: str = typer.Option("vie+eng", "--lang", help="OCR language (tesseract code)"),
) -> None:
    """Extract text from images or scanned documents using OCR.

    Supports single image files (.png, .jpg, .tiff, .bmp) or
    a directory of images (processed in sorted order as book pages).

    Examples:
        bookai ocr page.png -o output.md
        bookai ocr ./book_pages/ -o book.md
        bookai ocr scan.jpg --lang vie+eng
    """
    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]Error: Path not found: {file_path}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold blue]🔍 OCR Processing:[/bold blue] {path.name}")

    try:
        if path.is_dir():
            metadata, markdown = convert_images_dir(file_path, lang=lang)
        else:
            metadata, markdown = convert_image(file_path, lang=lang)
    except Exception as e:
        console.print(f"[red]Error during OCR: {e}[/red]")
        raise typer.Exit(1)

    console.print(f"  Title: [green]{metadata.title}[/green]")
    console.print(f"  Pages/images: {metadata.chapters}")
    console.print(f"  Text length: {len(markdown)} chars")

    if output:
        Path(output).write_text(markdown, encoding="utf-8")
        console.print(f"\n[green]Saved to: {output}[/green]")
    else:
        console.print("\n" + markdown[:2000])
        if len(markdown) > 2000:
            console.print(f"\n[dim]... ({len(markdown) - 2000} more characters)[/dim]")


@app.command("transcribe")
def transcribe_command(
    file_path: str = typer.Argument(help="Path to audio file (.mp3, .wav, .m4a, .flac, ...)"),
    output: str | None = typer.Option(None, "-o", "--output", help="Output markdown file"),
    model_size: str = typer.Option(
        "base", "--model-size", help="Whisper model: tiny, base, small, medium, large"
    ),
    language: str = typer.Option("vi", "--language", help="Language code (vi, en, etc.)"),
    timestamps: bool = typer.Option(
        False, "--timestamps", help="Include timestamp JSON in output"
    ),
) -> None:
    """Transcribe audio/audiobook to Markdown using Whisper.

    Converts audio files to text with timestamps, suitable for
    further processing with `process` or direct use.

    Examples:
        bookai transcribe audiobook.mp3 -o transcript.md
        bookai transcribe chapter1.m4a --model-size small --language vi
        bookai transcribe podcast.wav --timestamps -o output.md
    """
    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(1)

    from .audio import is_supported_audio

    if not is_supported_audio(file_path):
        console.print(
            f"[red]Error: Unsupported audio format: {path.suffix}[/red]\n"
            "Supported: .mp3, .wav, .m4a, .flac, .ogg, .wma, .aac, .opus"
        )
        raise typer.Exit(1)

    console.print(f"\n[bold blue]🎙️ Transcribing:[/bold blue] {path.name}")
    console.print(f"  Model: whisper-{model_size}, Language: {language}")

    try:
        if timestamps:
            from .audio import transcribe_audio_with_timestamps

            metadata, markdown, ts_data = transcribe_audio_with_timestamps(
                file_path, model_size=model_size, language=language
            )
            console.print(f"  Segments: {len(ts_data)}")
        else:
            metadata, markdown = convert_audio(file_path, model_size=model_size, language=language)
    except Exception as e:
        console.print(f"[red]Error during transcription: {e}[/red]")
        raise typer.Exit(1)

    console.print(f"  Title: [green]{metadata.title}[/green]")
    console.print(f"  Chapters detected: {metadata.chapters}")
    console.print(f"  Text length: {len(markdown)} chars")

    if output:
        out_path = Path(output)
        out_path.write_text(markdown, encoding="utf-8")
        console.print(f"\n[green]Transcript saved to: {out_path}[/green]")

        # Save timestamps JSON alongside if requested
        if timestamps:
            ts_path = out_path.with_suffix(".timestamps.json")
            ts_path.write_text(
                json.dumps(ts_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            console.print(f"[green]Timestamps saved to: {ts_path}[/green]")
    else:
        console.print("\n" + markdown[:2000])
        if len(markdown) > 2000:
            console.print(f"\n[dim]... ({len(markdown) - 2000} more characters)[/dim]")
