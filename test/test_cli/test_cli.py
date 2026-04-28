import os
from unittest.mock import patch

from typer.testing import CliRunner

from torah_dl.cli import __version__, app
from torah_dl.core.exceptions import ExtractorNotFoundError
from torah_dl.core.models import Listing, ListingItem

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "SoferAI's Torah Downloader" in result.output


def test_extract_url():
    result = runner.invoke(
        app,
        ["extract", "https://www.kolhalashon.com/new/Media/PlayShiur.aspx?FileName=34412186&English=True&Lang=English"],
    )
    assert result.exit_code == 0
    assert "Shiur 34412186" in result.output


def test_extract_url_only():
    result = runner.invoke(
        app,
        [
            "extract",
            "https://www.kolhalashon.com/new/Media/PlayShiur.aspx?FileName=34412186&English=True&Lang=English",
            "--url-only",
        ],
    )
    assert result.exit_code == 0
    assert "https://www.kolhalashon.com/mp3/NewArchive/34412/34412186.mp3" in result.output


def test_extract_url_failed():
    result = runner.invoke(app, ["extract", "https://www.gashmius.xyz/"])
    assert result.exit_code == 1
    assert "Extractor not found" in result.output


def test_download_url(tmp_path):
    result = runner.invoke(
        app,
        [
            "download",
            "https://www.kolhalashon.com/new/Media/PlayShiur.aspx?FileName=34412186&English=True&Lang=English",
            str(tmp_path / "test.mp3"),
        ],
    )
    assert result.exit_code == 0
    assert os.path.exists(tmp_path / "test.mp3")


def test_list_extractors():
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "YUTorah" in result.output


def _fake_listing(url: str = "https://www.yutorah.org/teachers/details/?teacherID=1"):
    return Listing(
        source_url=url,
        label="YUTorah teacher 1",
        items=[
            ListingItem(url="https://www.yutorah.org/lectures/1000001", title="Shiur One"),
            ListingItem(url="https://www.yutorah.org/lectures/1000002", title="Shiur Two"),
        ],
    )


def test_list_shiurim_command():
    with patch("torah_dl.cli.list_shiurim", return_value=_fake_listing()):
        result = runner.invoke(app, ["list-shiurim", "https://www.yutorah.org/teachers/details/?teacherID=1"])
    assert result.exit_code == 0
    assert "Shiur One" in result.output
    assert "Shiur Two" in result.output
    assert "2 shiurim" in result.output


def test_list_shiurim_urls_only():
    with patch("torah_dl.cli.list_shiurim", return_value=_fake_listing()):
        result = runner.invoke(
            app,
            ["list-shiurim", "--urls-only", "https://www.yutorah.org/teachers/details/?teacherID=1"],
        )
    assert result.exit_code == 0
    lines = [ln for ln in result.output.strip().splitlines() if ln.strip()]
    assert lines == [
        "https://www.yutorah.org/lectures/1000001",
        "https://www.yutorah.org/lectures/1000002",
    ]


def test_list_shiurim_unknown_url():
    with patch("torah_dl.cli.list_shiurim", side_effect=ExtractorNotFoundError("nope")):
        result = runner.invoke(app, ["list-shiurim", "https://example.com/nope"])
    assert result.exit_code == 1
    assert "No listing extractor" in result.output


def test_bulk_download_unknown_url(tmp_path):
    with patch("torah_dl.cli.list_shiurim", side_effect=ExtractorNotFoundError("nope")):
        result = runner.invoke(app, ["bulk-download", "https://example.com/nope", str(tmp_path)])
    assert result.exit_code == 1


def test_bulk_download_with_limit(tmp_path):
    """Bulk-download with --limit only processes that many items.

    We mock list_shiurim, extract, and download so no network is touched.
    """
    from torah_dl.core.models import Extraction

    extraction = Extraction(
        download_url="https://example.com/x.mp3",
        title="x",
        file_format="audio/mp3",
        file_name="x.mp3",
    )

    download_calls = []

    def fake_download(url, path):
        download_calls.append((url, str(path)))
        # Simulate the file being written
        with open(path, "wb") as f:
            f.write(b"\x00")

    with (
        patch("torah_dl.cli.list_shiurim", return_value=_fake_listing()),
        patch("torah_dl.cli.extract", return_value=extraction),
        patch("torah_dl.cli.download", side_effect=fake_download),
    ):
        result = runner.invoke(
            app,
            [
                "bulk-download",
                "https://www.yutorah.org/teachers/details/?teacherID=1",
                str(tmp_path),
                "--limit",
                "1",
            ],
        )

    assert result.exit_code == 0
    assert len(download_calls) == 1
    assert "Found 2 shiurim, downloading 1" in result.output
