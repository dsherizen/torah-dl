"""Auto-discovery and dispatch for listing-page extractors."""

import importlib
import inspect
import pkgutil

from . import listings as listings_pkg
from .exceptions import ExtractorNotFoundError
from .models import Listing, ListingExtractor

LISTING_EXTRACTORS: list[ListingExtractor] = []
for _, _name, _ in pkgutil.iter_modules(listings_pkg.__path__):
    _module = importlib.import_module(f".{_name}", "torah_dl.core.listings")
    for _, _obj in inspect.getmembers(_module):
        if (
            inspect.isclass(_obj)
            and issubclass(_obj, ListingExtractor)
            and _obj is not ListingExtractor
            and not _obj.__name__.startswith("_")
        ):
            LISTING_EXTRACTORS.append(_obj())


def list_shiurim(url: str) -> Listing:
    """Enumerate all shiur URLs on a listing page (teacher, series, etc)."""
    for extractor in LISTING_EXTRACTORS:
        if extractor.can_handle(url):
            return extractor.list_shiurim(url)
    raise ExtractorNotFoundError(url)


def can_handle_listing(url: str) -> bool:
    return any(e.can_handle(url) for e in LISTING_EXTRACTORS)
