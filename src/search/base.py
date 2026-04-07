"""Abstract base for search providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SearchResult:
    """Raw result from a single platform."""
    name: str
    name_ko: str = ""
    address: str = ""
    category: str = ""
    lat: float = 0.0
    lng: float = 0.0
    rating: float = 0.0
    rating_max: float = 5.0
    review_count: int = 0
    price_info: str = ""
    phone: str = ""
    hours: str = ""
    url: str = ""
    source: str = ""
    raw_data: dict = field(default_factory=dict)


class SearchProvider(ABC):
    """Base class for all search providers."""

    name: str = "base"

    @abstractmethod
    async def search(self, query: str, location: str = "", **kwargs) -> list[SearchResult]:
        """Search for restaurants matching query in location."""
        ...

    @abstractmethod
    async def get_details(self, place_id: str) -> SearchResult | None:
        """Get detailed info for a specific place."""
        ...

    def is_available(self) -> bool:
        """Check if this provider is configured (API key, etc)."""
        return True
