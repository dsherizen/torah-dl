"""Unit tests for listing-page extractors.

Uses mocked HTTP responses so the tests are deterministic and don't depend
on the upstream sites being reachable.
"""

from unittest.mock import patch

import pytest

from torah_dl import LISTING_EXTRACTORS, can_handle_listing, list_shiurim
from torah_dl.core.exceptions import ContentExtractionError, ExtractorNotFoundError

# ───────────── Registration ─────────────


def test_listing_extractors_registered():
    names = {e.name for e in LISTING_EXTRACTORS}
    assert "YUTorah" in names
    assert "OU Torah" in names
    assert "AllDaf" in names
    assert "AllParsha" in names


def test_unknown_url_raises():
    with pytest.raises(ExtractorNotFoundError):
        list_shiurim("https://example.com/nope")


def test_can_handle_listing():
    assert can_handle_listing("https://www.yutorah.org/teachers/details/?teacherID=80714")
    assert can_handle_listing("https://www.yutorah.org/series/details/?seriesid=234")
    assert can_handle_listing("https://outorah.org/r/238")
    assert can_handle_listing("https://alldaf.org/r/100")
    assert can_handle_listing("https://allparsha.org/series/abc")
    # Single shiur URLs should NOT be claimed by listing extractors
    assert not can_handle_listing("https://www.yutorah.org/lectures/1116616")
    assert not can_handle_listing("https://outorah.org/p/212365")


# ───────────── YUTorah ─────────────

YU_RSS_BODY = """<?xml version="1.0"?>
<rss><channel>
  <item>
    <title>Shiur One</title>
    <link>https://www.yutorah.org/lectures/1000001/Shiur-One</link>
    <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Shiur Two</title>
    <link>https://www.yutorah.org/lectures/1000002/Shiur-Two</link>
    <pubDate>Tue, 02 Jan 2024 00:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Not a lecture</title>
    <link>https://www.yutorah.org/some/other/page</link>
  </item>
</channel></rss>
"""


class _FakeResponse:
    def __init__(self, text="", status=200):
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"{self.status_code}", response=self)


def test_yutorah_teacher_listing_via_rss():
    def fake_get(url, **_):
        if "teacherRSS.cfm" in url:
            return _FakeResponse(YU_RSS_BODY)
        return _FakeResponse("", status=404)

    with patch("torah_dl.core.listings.yutorah.requests.get", side_effect=fake_get):
        listing = list_shiurim("https://www.yutorah.org/teachers/details/?teacherID=80714")

    assert len(listing.items) == 2
    assert listing.items[0].url == "https://www.yutorah.org/lectures/1000001/Shiur-One"
    assert listing.items[0].title == "Shiur One"
    assert listing.items[1].title == "Shiur Two"
    assert listing.label == "YUTorah teacher 80714"


def test_yutorah_series_listing_via_rss():
    def fake_get(url, **_):
        if "seriesRSS.cfm" in url:
            return _FakeResponse(YU_RSS_BODY.replace("teacher", "series"))
        return _FakeResponse("", status=404)

    with patch("torah_dl.core.listings.yutorah.requests.get", side_effect=fake_get):
        listing = list_shiurim("https://www.yutorah.org/series/details/?seriesid=234")

    assert len(listing.items) == 2
    assert listing.label == "YUTorah series 234"


def test_yutorah_falls_back_to_search_when_rss_empty():
    pages = [
        # Page 1: two distinct shiurim
        '<a href="/lectures/2000001/Title-A"><a href="/lectures/details?shiurid=2000002">',
        # Page 2: one new shiur
        '<a href="/lectures/lecture.cfm/2000003">',
        # Page 3: empty -> stops loop
        "",
    ]
    calls = {"i": 0}

    def fake_get(url, **_):
        if "teacherRSS.cfm" in url:
            return _FakeResponse('<?xml version="1.0"?><rss><channel></channel></rss>')
        if "/Search/" in url:
            i = calls["i"]
            calls["i"] += 1
            if i < len(pages):
                return _FakeResponse(pages[i])
            return _FakeResponse("")
        return _FakeResponse("", status=404)

    with patch("torah_dl.core.listings.yutorah.requests.get", side_effect=fake_get):
        listing = list_shiurim("https://www.yutorah.org/teachers/details/?teacherID=80714")

    urls = [item.url for item in listing.items]
    assert "https://www.yutorah.org/lectures/2000001/Title-A" in urls
    assert "https://www.yutorah.org/lectures/details?shiurid=2000002" in urls
    assert "https://www.yutorah.org/lectures/lecture.cfm/2000003" in urls
    assert len(listing.items) == 3


def test_yutorah_no_results_raises():
    def fake_get(url, **_):
        if "teacherRSS.cfm" in url:
            return _FakeResponse('<?xml version="1.0"?><rss><channel></channel></rss>')
        return _FakeResponse("")  # search returns empty

    with (
        patch("torah_dl.core.listings.yutorah.requests.get", side_effect=fake_get),
        pytest.raises(ContentExtractionError),
    ):
        list_shiurim("https://www.yutorah.org/teachers/details/?teacherID=99999999")


# ───────────── OU family ─────────────


def test_outorah_listing():
    html = """
    <ul>
      <li><a href="/p/212365">Parshat Miketz</a></li>
      <li><a href="/p/212366">Parshat Vayigash</a></li>
      <li><a href="/p/212365">Duplicate (should dedupe)</a></li>
      <li><a href="https://outorah.org/p/212367">Absolute</a></li>
      <li><a href="/about">Not a shiur</a></li>
    </ul>
    """
    with patch("torah_dl.core.listings.outorah_family.requests.get", return_value=_FakeResponse(html)):
        listing = list_shiurim("https://outorah.org/r/238")

    urls = sorted(item.url for item in listing.items)
    assert urls == [
        "https://outorah.org/p/212365",
        "https://outorah.org/p/212366",
        "https://outorah.org/p/212367",
    ]


def test_alldaf_listing():
    html = '<a href="/p/36785">Sanhedrin 40</a><a href="/p/36786">Sanhedrin 41</a>'
    with patch("torah_dl.core.listings.outorah_family.requests.get", return_value=_FakeResponse(html)):
        listing = list_shiurim("https://alldaf.org/masechta/sanhedrin")

    assert len(listing.items) == 2
    assert all(item.url.startswith("https://alldaf.org/p/") for item in listing.items)


def test_allparsha_listing():
    html = '<a href="/p/197738">Mishpatim</a>'
    with patch("torah_dl.core.listings.outorah_family.requests.get", return_value=_FakeResponse(html)):
        listing = list_shiurim("https://allparsha.org/parsha/mishpatim")

    assert len(listing.items) == 1
    assert listing.items[0].url == "https://allparsha.org/p/197738"


def test_outorah_empty_raises():
    with (
        patch("torah_dl.core.listings.outorah_family.requests.get", return_value=_FakeResponse("<html></html>")),
        pytest.raises(ContentExtractionError),
    ):
        list_shiurim("https://outorah.org/r/0")
