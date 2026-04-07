"""Kakao Local Search API provider."""

import os
import httpx
from .base import SearchProvider, SearchResult


class KakaoSearchProvider(SearchProvider):
    """
    Kakao Local Search API.
    Requires KAKAO_REST_API_KEY env var.
    Docs: https://developers.kakao.com/docs/latest/ko/local/dev-guide
    """

    name = "kakao"
    BASE_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

    def __init__(self):
        self.api_key = os.environ.get("KAKAO_REST_API_KEY", "")

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str, location: str = "", **kwargs) -> list[SearchResult]:
        if not self.is_available():
            return []

        search_query = f"{location} {query}".strip() if location else query
        params = {
            "query": search_query,
            "size": min(kwargs.get("limit", 10), 15),
            "category_group_code": "FD6",  # 음식점
        }
        # Optional: center coordinates for proximity search
        if kwargs.get("lat") and kwargs.get("lng"):
            params["y"] = str(kwargs["lat"])
            params["x"] = str(kwargs["lng"])
            params["sort"] = "distance"

        headers = {"Authorization": f"KakaoAK {self.api_key}"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(self.BASE_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("documents", []):
            results.append(SearchResult(
                name=item.get("place_name", ""),
                name_ko=item.get("place_name", ""),
                address=item.get("road_address_name", "") or item.get("address_name", ""),
                category=item.get("category_name", ""),
                lat=float(item.get("y", 0)),
                lng=float(item.get("x", 0)),
                url=item.get("place_url", ""),
                phone=item.get("phone", ""),
                source="kakao",
                raw_data=item,
            ))
        return results

    async def get_details(self, place_id: str) -> SearchResult | None:
        results = await self.search(place_id)
        return results[0] if results else None
