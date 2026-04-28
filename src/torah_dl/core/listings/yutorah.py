"""YUTorah listing extractor.

Handles teacher pages and series pages. Uses the public RSS feeds where
possible (most reliable), with HTML fallback that walks paginated search
results.
"""

import re
from re import Pattern
from urllib.parse import parse_qs, urlparse

import defusedxml.ElementTree as DET
import requests

from ..exceptions import ContentExtractionError, NetworkError
from ..models import Listing, ListingExtractor, ListingItem


class YutorahListingExtractor(ListingExtractor):
    """Enumerate shiurim from a YUTorah teacher or series page."""

    name: str = "YUTorah"
    homepage: str = "https://yutorah.org"

    URL_PATTERN = re.compile(
        r"https?://(?:www\.)?yutorah\.org/(?:teachers/details|series/details)",
        flags=re.IGNORECASE,
    )

    @property
    def url_patterns(self) -> list[Pattern]:
        return [self.URL_PATTERN]

    def list_shiurim(self, url: str) -> Listing:
        kind, target_id = self._classify(url)
        if not target_id:
            raise ContentExtractionError("Could not parse teacher/series ID from URL")  # noqa: TRY003

        rss_url = (
            f"https://www.yutorah.org/teacherRSS.cfm?teacherID={target_id}"
            if kind == "teacher"
            else f"https://www.yutorah.org/seriesRSS.cfm?seriesID={target_id}"
        )

        items = self._from_rss(rss_url)
        if not items:
            # Fallback: walk paginated search results
            items = self._from_search(kind, target_id)

        if not items:
            raise ContentExtractionError("No shiurim found on listing page")  # noqa: TRY003

        return Listing(source_url=url, label=f"YUTorah {kind} {target_id}", items=items)

    def _classify(self, url: str) -> tuple[str, str | None]:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if "teacherID" in query or "teacherid" in query:
            tid = query.get("teacherID", query.get("teacherid", [None]))[0]
            return ("teacher", tid)
        if "seriesid" in query or "seriesID" in query:
            sid = query.get("seriesid", query.get("seriesID", [None]))[0]
            return ("series", sid)
        return ("unknown", None)

    def _from_rss(self, rss_url: str) -> list[ListingItem]:
        try:
            response = requests.get(rss_url, timeout=30, headers={"User-Agent": "torah-dl/1.0"})
            response.raise_for_status()
        except requests.RequestException:
            return []

        try:
            root = DET.fromstring(response.content)
        except Exception:
            return []

        items: list[ListingItem] = []
        for item in root.findall(".//item"):
            link_el = item.find("link")
            title_el = item.find("title")
            date_el = item.find("pubDate")
            if link_el is None or not link_el.text:
                continue
            link = link_el.text.strip()
            if not re.search(r"yutorah\.org/lectures/", link, re.IGNORECASE):
                continue
            items.append(
                ListingItem(
                    url=link,
                    title=(title_el.text.strip() if title_el is not None and title_el.text else None),
                    date=(date_el.text.strip() if date_el is not None and date_el.text else None),
                )
            )
        return items

    def _from_search(self, kind: str, target_id: str) -> list[ListingItem]:
        param = "teacher_id" if kind == "teacher" else "series_id"
        seen: dict[str, ListingItem] = {}
        for page in range(1, 21):  # safety cap
            try:
                response = requests.get(
                    f"https://www.yutorah.org/Search/?{param}={target_id}&pageNumber={page}",
                    timeout=30,
                    headers={"User-Agent": "torah-dl/1.0"},
                )
                response.raise_for_status()
            except requests.RequestException as e:
                raise NetworkError(str(e)) from e

            found_on_page = 0
            for match in re.finditer(
                r'href="(/lectures/(?:lecture\.cfm/\d+|details\?shiurid=\d+|\d+)[^"]*)"',
                response.text,
                flags=re.IGNORECASE,
            ):
                href = match.group(1)
                full = "https://www.yutorah.org" + href
                if full not in seen:
                    seen[full] = ListingItem(url=full)
                    found_on_page += 1

            if found_on_page == 0:
                break

        return list(seen.values())
