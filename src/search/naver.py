"""Naver Local Search API provider."""

import os
import httpx
from .base import SearchProvider, SearchResult


class NaverSearchProvider(SearchProvider):
    """
    Naver Local Search API.
    Requires NAVER_CLIENT_ID and NAVER_CLIENT_SECRET env vars.
    Docs: https://developers.naver.com/docs/serviceapi/search/local/local.md
    """

    name = "naver"
    BASE_URL = "https://openapi.naver.com/v1/search/local.json"

    def __init__(self):
        self.client_id = os.environ.get("NAVER_CLIENT_ID", "")
        self.client_secret = os.environ.get("NAVER_CLIENT_SECRET", "")

    def is_available(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def search(self, query: str, location: str = "", **kwargs) -> list[SearchResult]:
        if not self.is_available():
            return []

        search_query = f"{location} {query}".strip() if location else query
        params = {
            "query": search_query,
            "display": kwargs.get("limit", 10),
            "sort": "comment",  # Sort by review count
        }
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(self.BASE_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("items", []):
            # Strip HTML tags from title
            name = item.get("title", "").replace("<b>", "").replace("</b>", "")
            results.append(SearchResult(
                name=name,
                name_ko=name,
                address=item.get("roadAddress", "") or item.get("address", ""),
                category=item.get("category", ""),
                lat=float(item.get("mapy", 0)) / 1e7 if item.get("mapy") else 0,
                lng=float(item.get("mapx", 0)) / 1e7 if item.get("mapx") else 0,
                url=item.get("link", ""),
                phone=item.get("telephone", ""),
                source="naver",
                raw_data=item,
            ))
        return results

    async def get_details(self, place_id: str) -> SearchResult | None:
        # Naver Local Search doesn't have a detail endpoint by ID.
        # Use search with specific name instead.
        results = await self.search(place_id)
        return results[0] if results else None
