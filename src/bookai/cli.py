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
from .converter import convert_file
from .models import BookResult, ChunkLabel

app = typer.Typer(
    name="bookai",
    help="Convert books to affiliate marketing content using AI.",
)
console = Console()


@app.command()
def process(
    file_path: str = typer.Argument(help="Path to book file (.epub, .pdf, .txt, .md)"),
    output: str | None = typer.Option(None, "-o", "--output", help="Output JSON file path"),
    max_chunks: int = typer.Option(100, "--max-chunks", help="Max chunks to analyze"),
    max_tokens: int = typer.Option(500, "--max-tokens", help="Max tokens per chunk"),
    provider: str = typer.Option("mock", "--provider", help="AI provider: openai, anthropic, mock"),
    model: str = typer.Option("gpt-4o-mini", "--model", help="Model name for AI provider"),
    api_key: str | None = typer.Option(None, "--api-key", help="API key (or use env var)"),
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
                chunks_to_analyze, api_key=api_key, model=model, provider=provider
            )
        else:
            analyzed = analyze_chunks(
                chunks_to_analyze, api_key=api_key, model=model, provider=provider
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
