"""DiningCode scraper — Korea's largest restaurant review platform."""

import re
import httpx
from bs4 import BeautifulSoup
from .base import SearchProvider, SearchResult


class DiningCodeProvider(SearchProvider):
    """
    Scrapes DiningCode (diningcode.com) for restaurant data.
    No API key required — uses public web pages.
    """

    name = "diningcode"
    BASE_URL = "https://www.diningcode.com"
    SEARCH_URL = "https://www.diningcode.com/list.dc"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9",
    }

    async def search(self, query: str, location: str = "", **kwargs) -> list[SearchResult]:
        search_query = f"{location} {query}".strip() if location else query
        params = {"query": search_query}

        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(self.SEARCH_URL, params=params, headers=self.HEADERS)
                resp.raise_for_status()
                html = resp.text
        except Exception:
            return []

        return self._parse_search_results(html)

    def _parse_search_results(self, html: str) -> list[SearchResult]:
        soup = BeautifulSoup(html, "html.parser")
        results = []

        # DiningCode list items
        for item in soup.select(".dc-restaurant, .PoiBlock, li.dc-poi"):
            name_el = item.select_one(".InfoHeader a, .dc-restaurant-name, h2 a")
            if not name_el:
                continue

            name = name_el.get_text(strip=True)
            url = name_el.get("href", "")
            if url and not url.startswith("http"):
                url = self.BASE_URL + url

            addr_el = item.select_one(".addr, .dc-address")
            address = addr_el.get_text(strip=True) if addr_el else ""

            cat_el = item.select_one(".category, .dc-category")
            category = cat_el.get_text(strip=True) if cat_el else ""

            score_el = item.select_one(".score, .dc-score, .point")
            rating = 0.0
            if score_el:
                score_text = score_el.get_text(strip=True)
                nums = re.findall(r"[\d.]+", score_text)
                if nums:
                    rating = float(nums[0])

            review_el = item.select_one(".review-count, .dc-review-count")
            review_count = 0
            if review_el:
                nums = re.findall(r"\d+", review_el.get_text())
                if nums:
                    review_count = int(nums[0])

            results.append(SearchResult(
                name=name,
                name_ko=name,
                address=address,
                category=category,
                rating=rating,
                review_count=review_count,
                url=url,
                source="diningcode",
            ))

        return results

    async def get_details(self, place_id: str) -> SearchResult | None:
        """Fetch detail page for a restaurant."""
        url = place_id if place_id.startswith("http") else f"{self.BASE_URL}/profile.php?rid={place_id}"

        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url, headers=self.HEADERS)
                resp.raise_for_status()
                html = resp.text
        except Exception:
            return None

        return self._parse_detail(html, url)

    def _parse_detail(self, html: str, url: str) -> SearchResult | None:
        soup = BeautifulSoup(html, "html.parser")

        name_el = soup.select_one("h1.tit, .dc-name, .InfoHeader h1")
        if not name_el:
            return None

        name = name_el.get_text(strip=True)

        addr_el = soup.select_one(".locat, .dc-address, .addr")
        address = addr_el.get_text(strip=True) if addr_el else ""

        score_el = soup.select_one(".point, .dc-score, .score-total")
        rating = 0.0
        if score_el:
            nums = re.findall(r"[\d.]+", score_el.get_text(strip=True))
            if nums:
                rating = float(nums[0])

        phone_el = soup.select_one(".tel, .phone")
        phone = phone_el.get_text(strip=True) if phone_el else ""

        hours_el = soup.select_one(".time, .hours")
        hours = hours_el.get_text(strip=True) if hours_el else ""

        return SearchResult(
            name=name,
            name_ko=name,
            address=address,
            rating=rating,
            phone=phone,
            hours=hours,
            url=url,
            source="diningcode",
        )
