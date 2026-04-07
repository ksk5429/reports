"""General web search fallback using multiple search engines."""

import re
import httpx
from bs4 import BeautifulSoup
from .base import SearchProvider, SearchResult


class WebSearchProvider(SearchProvider):
    """
    Fallback search using public web scraping.
    Searches multiple Korean platforms via their search pages.
    No API key required.
    """

    name = "web_search"

    SIKSINHOT_SEARCH = "https://www.siksinhot.com/search"
    MANGOPLATE_SEARCH = "https://www.mangoplate.com/search/{query}"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9",
    }

    async def search(self, query: str, location: str = "", **kwargs) -> list[SearchResult]:
        """Search across multiple platforms concurrently."""
        search_query = f"{location} {query}".strip() if location else query
        results = []

        # Siksinhot
        try:
            siksin_results = await self._search_siksinhot(search_query)
            results.extend(siksin_results)
        except Exception:
            pass

        return results

    async def _search_siksinhot(self, query: str) -> list[SearchResult]:
        """Scrape Siksinhot search results."""
        params = {"keywords": query}
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(self.SIKSINHOT_SEARCH, params=params, headers=self.HEADERS)
                resp.raise_for_status()
                html = resp.text
        except Exception:
            return []

        soup = BeautifulSoup(html, "html.parser")
        results = []

        for item in soup.select(".shopInfo, .localRestaurantRow, .store_list li"):
            name_el = item.select_one("h2 a, .store_name a, .titleHeading a")
            if not name_el:
                continue

            name = name_el.get_text(strip=True)
            url = name_el.get("href", "")
            if url and not url.startswith("http"):
                url = "https://www.siksinhot.com" + url

            addr_el = item.select_one(".addr, .store_addr, p.address")
            address = addr_el.get_text(strip=True) if addr_el else ""

            score_el = item.select_one(".score, .totalScore, .star em")
            rating = 0.0
            if score_el:
                nums = re.findall(r"[\d.]+", score_el.get_text(strip=True))
                if nums:
                    rating = float(nums[0])

            results.append(SearchResult(
                name=name,
                name_ko=name,
                address=address,
                rating=rating,
                url=url,
                source="siksinhot",
            ))

        return results

    async def get_details(self, place_id: str) -> SearchResult | None:
        results = await self.search(place_id)
        return results[0] if results else None
