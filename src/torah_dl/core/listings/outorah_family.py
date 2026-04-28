"""Listing extractors for the OU family of sites.

OUTorah, AllDaf, and AllParsha all share the same publication backend
(media.ou.org). Their listing pages are server-rendered HTML containing
``<a href="/p/{id}">`` links to individual shiurim, so a single regex
walk is enough.
"""

import re
from re import Pattern

import requests

from ..exceptions import ContentExtractionError, NetworkError
from ..models import Listing, ListingExtractor, ListingItem


class _OUFamilyBase(ListingExtractor):
    """Shared listing-page logic for the OU sites."""

    DOMAIN: str = ""  # subclass sets this, e.g. "outorah.org"
    LISTING_PATTERN: Pattern = re.compile(r"")  # subclass sets

    @property
    def url_patterns(self) -> list[Pattern]:
        return [self.LISTING_PATTERN]

    def list_shiurim(self, url: str) -> Listing:
        try:
            response = requests.get(url, timeout=30, headers={"User-Agent": "torah-dl/1.0"})
            response.raise_for_status()
        except requests.RequestException as e:
            raise NetworkError(str(e)) from e

        # Match every /p/<digits> link on the page.
        href_re = re.compile(r'href="(/p/(\d+))"', flags=re.IGNORECASE)
        seen: dict[str, ListingItem] = {}
        for match in href_re.finditer(response.text):
            full = f"https://{self.DOMAIN}{match.group(1)}"
            if full not in seen:
                seen[full] = ListingItem(url=full)

        # Some listing pages render absolute URLs.
        abs_re = re.compile(
            rf"https?://(?:www\.)?{re.escape(self.DOMAIN)}/p/(\d+)",
            flags=re.IGNORECASE,
        )
        for match in abs_re.finditer(response.text):
            full = f"https://{self.DOMAIN}/p/{match.group(1)}"
            if full not in seen:
                seen[full] = ListingItem(url=full)

        if not seen:
            raise ContentExtractionError("No shiurim found on listing page")  # noqa: TRY003

        return Listing(source_url=url, label=f"{self.name} listing", items=list(seen.values()))


class OutorahListingExtractor(_OUFamilyBase):
    name: str = "OU Torah"
    homepage: str = "https://outorah.org"
    DOMAIN = "outorah.org"
    # /r/<id> rabbi pages, /s/<id> series pages, /series/<id>/, /rabbi/<id>/
    LISTING_PATTERN = re.compile(
        r"https?://(?:www\.)?outorah\.org/(?:r|s|rabbi|series)/\d+",
        flags=re.IGNORECASE,
    )


class AllDafListingExtractor(_OUFamilyBase):
    name: str = "AllDaf"
    homepage: str = "https://alldaf.org"
    DOMAIN = "alldaf.org"
    LISTING_PATTERN = re.compile(
        r"https?://(?:www\.)?alldaf\.org/(?:r|s|rabbi|series|masechta)/\S+",
        flags=re.IGNORECASE,
    )


class AllParshaListingExtractor(_OUFamilyBase):
    name: str = "AllParsha"
    homepage: str = "https://allparsha.org"
    DOMAIN = "allparsha.org"
    LISTING_PATTERN = re.compile(
        r"https?://(?:www\.)?allparsha\.org/(?:r|s|rabbi|series|parsha)/\S+",
        flags=re.IGNORECASE,
    )
