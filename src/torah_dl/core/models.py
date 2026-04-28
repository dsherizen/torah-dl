from abc import ABC, abstractmethod
from re import Pattern
from typing import ClassVar

from pydantic import BaseModel


class Extraction(BaseModel):
    """Represents the extracted data from a source."""

    title: str | None = None
    download_url: str
    file_format: str | None = None
    file_name: str | None = None
    # Add other common fields that all extractions should have


class ExtractionExample(BaseModel):
    """Represents an example of an extraction."""

    name: str
    url: str
    download_url: str
    title: str
    file_format: str
    valid: bool


class ListingItem(BaseModel):
    """A single shiur reference discovered on a listing page."""

    url: str
    title: str | None = None
    speaker: str | None = None
    date: str | None = None


class Listing(BaseModel):
    """Result of scanning a listing page (teacher, series, category, etc.)."""

    source_url: str
    label: str | None = None  # e.g. "Rabbi X — Teacher Page"
    items: list[ListingItem]


class Extractor(ABC):
    """Abstract base class for all extractors."""

    name: str
    homepage: str

    EXAMPLES: ClassVar[list[ExtractionExample]] = []

    @property
    @abstractmethod
    def url_patterns(self) -> Pattern | list[Pattern]:
        """
        Returns the regex pattern(s) that match URLs this extractor can handle.
        Can return either a single compiled regex pattern or a list of patterns.
        """
        ...  # pragma: no cover

    def can_handle(self, url: str) -> bool:
        """
        Checks if this extractor can handle the given URL.

        Args:
            url: The URL to check

        Returns:
            bool: True if this extractor can handle the URL, False otherwise
        """
        patterns = self.url_patterns
        if isinstance(patterns, Pattern):
            patterns = [patterns]

        return any(pattern.match(url) for pattern in patterns)

    @abstractmethod
    def extract(self, url: str) -> Extraction:
        """
        Extracts data from the given URL.

        Args:
            url: The URL to extract from

        Returns:
            Extraction: The extracted data

        Raises:
            ValueError: If the URL is not supported by this extractor
        """
        ...  # pragma: no cover


class ListingExtractor(ABC):
    """Abstract base class for listing-page extractors.

    A listing extractor knows how to take a teacher / series / category page
    URL and enumerate every individual shiur URL on it. The returned URLs
    are themselves extractable by the regular per-shiur Extractor.
    """

    name: str
    homepage: str

    @property
    @abstractmethod
    def url_patterns(self) -> Pattern | list[Pattern]: ...  # pragma: no cover

    def can_handle(self, url: str) -> bool:
        patterns = self.url_patterns
        if isinstance(patterns, Pattern):
            patterns = [patterns]
        return any(pattern.search(url) for pattern in patterns)

    @abstractmethod
    def list_shiurim(self, url: str) -> Listing:
        """Return every shiur reference found at this listing URL."""
        ...  # pragma: no cover
