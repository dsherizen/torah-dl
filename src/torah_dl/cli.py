import importlib.metadata
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from torah_dl import download, extract, list_extractors, list_shiurim
from torah_dl.core.exceptions import ExtractorNotFoundError

try:
    __version__ = importlib.metadata.version(__package__ or __name__)
except importlib.metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = "develop"

app = typer.Typer()
console = Console()


@app.command(name="extract")
def extract_url(
    url: str,
    url_only: Annotated[bool, typer.Option("--url-only", help="Only output the download URL")] = False,
):
    """
    Extract information from a given URL
    """
    with console.status("Extracting URL..."):
        try:
            extraction = extract(url)
        except ExtractorNotFoundError:
            typer.echo(f"Extractor not found for URL: {url}", err=True)
            raise typer.Exit(1) from None

    if url_only:
        typer.echo(extraction.download_url)
    else:
        table = Table(box=None, pad_edge=False)
        table.add_column(style="bold")
        # Set no_wrap=True to display full URL
        table.add_column(style="cyan", no_wrap=True)
        table.add_row("Title", extraction.title)
        table.add_row("Download URL", extraction.download_url, style="green")
        console.print(table)


@app.command(name="download")
def download_url(
    url: Annotated[str, typer.Argument(help="URL to download")],
    output_path: Annotated[Path, typer.Argument(help="Path to save the downloaded file")] = Path("audio"),
):
    """Download a file from a URL and show progress."""
    with console.status("Extracting URL..."):
        extraction = extract(url)
    with console.status("Downloading file..."):
        download(extraction.download_url, output_path)


@app.command(name="list")
def list_extractors_command():
    """List all available extractors."""
    extractors = list_extractors()
    table = Table(box=None, pad_edge=False)
    table.add_row("Name", "Homepage")
    for name, homepage in extractors.items():
        table.add_row(name, homepage)
    console.print(table)


@app.command(name="list-shiurim")
def list_shiurim_command(
    url: Annotated[str, typer.Argument(help="Listing page URL (teacher, series, rabbi, etc.)")],
    urls_only: Annotated[bool, typer.Option("--urls-only", help="Print URLs only, one per line")] = False,
):
    """Enumerate every shiur URL on a teacher / series / category listing page."""
    with console.status("Scanning listing page..."):
        try:
            listing = list_shiurim(url)
        except ExtractorNotFoundError:
            typer.echo(f"No listing extractor found for URL: {url}", err=True)
            raise typer.Exit(1) from None

    if urls_only:
        for item in listing.items:
            typer.echo(item.url)
        return

    table = Table(box=None, pad_edge=False)
    table.add_column("#", style="dim")
    table.add_column("Title")
    table.add_column("URL", style="cyan", no_wrap=False)
    for i, item in enumerate(listing.items, 1):
        table.add_row(str(i), item.title or "—", item.url)
    console.print(f"[bold]{listing.label or 'Listing'}[/bold] — {len(listing.items)} shiurim")
    console.print(table)


@app.command(name="bulk-download")
def bulk_download_command(
    url: Annotated[str, typer.Argument(help="Listing page URL")],
    output_dir: Annotated[Path, typer.Argument(help="Directory to save downloaded files")] = Path("audio"),
    limit: Annotated[int, typer.Option("--limit", "-n", help="Max number of shiurim to download (0=all)")] = 0,
):
    """Enumerate a listing page and download every shiur to a directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    with console.status("Scanning listing page..."):
        try:
            listing = list_shiurim(url)
        except ExtractorNotFoundError:
            typer.echo(f"No listing extractor found for URL: {url}", err=True)
            raise typer.Exit(1) from None

    items = listing.items if limit <= 0 else listing.items[:limit]
    typer.echo(f"Found {len(listing.items)} shiurim, downloading {len(items)}...")

    for i, item in enumerate(items, 1):
        with console.status(f"[{i}/{len(items)}] Extracting {item.url}..."):
            try:
                extraction = extract(item.url)
            except Exception as e:
                typer.echo(f"  skip {item.url}: {e}", err=True)
                continue
        target = output_dir / (extraction.file_name or f"shiur-{i}.mp3")
        with console.status(f"[{i}/{len(items)}] Downloading {target.name}..."):
            try:
                download(extraction.download_url, target)
            except Exception as e:
                typer.echo(f"  fail {target.name}: {e}", err=True)
                continue
        typer.echo(f"  ✓ {target}")


def version_callback(value: bool):
    """
    print version information to shell
    """
    if value:
        typer.echo(f"torah-dl version: {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def callback(
    _: Annotated[
        bool | None,
        typer.Option("--version", callback=version_callback, is_eager=True),
    ] = None,
):
    """
    SoferAI's Torah Downloader
    """
    pass


if __name__ == "__main__":  # pragma: no cover
    app()
