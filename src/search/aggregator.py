"""Multi-source search aggregator — the core search pipeline."""

import asyncio
import json
import os
import hashlib
from datetime import datetime
from dataclasses import asdict

from .base import SearchProvider, SearchResult
from .naver import NaverSearchProvider
from .kakao import KakaoSearchProvider
from .google_places import GooglePlacesProvider
from .diningcode import DiningCodeProvider
from .web_search import WebSearchProvider


CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "cache")


def _cache_key(query: str, location: str) -> str:
    raw = f"{query}|{location}|{datetime.now().strftime('%Y-%m-%d')}"
    return hashlib.md5(raw.encode()).hexdigest()


def _load_cache(key: str) -> list[SearchResult] | None:
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [SearchResult(**item) for item in data]
    except Exception:
        return None


def _save_cache(key: str, results: list[SearchResult]):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{key}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in results], f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class SearchAggregator:
    """
    Orchestrates parallel search across all available providers,
    deduplicates, and merges results.
    """

    def __init__(self):
        self.providers: list[SearchProvider] = [
            NaverSearchProvider(),
            KakaoSearchProvider(),
            GooglePlacesProvider(),
            DiningCodeProvider(),
            WebSearchProvider(),
        ]

    def available_providers(self) -> list[str]:
        return [p.name for p in self.providers if p.is_available()]

    async def search(
        self,
        query: str,
        location: str = "",
        use_cache: bool = True,
        **kwargs,
    ) -> list[SearchResult]:
        """
        Search all available providers in parallel.
        Returns merged, deduplicated results.
        """
        # Check cache
        if use_cache:
            key = _cache_key(query, location)
            cached = _load_cache(key)
            if cached:
                return cached

        # Run all providers concurrently
        active_providers = [p for p in self.providers if p.is_available()]
        if not active_providers:
            return []

        tasks = [p.search(query, location, **kwargs) for p in active_providers]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten and tag
        merged = []
        for provider, result in zip(active_providers, all_results):
            if isinstance(result, Exception):
                continue
            for r in result:
                r.source = provider.name
                merged.append(r)

        # Deduplicate by name similarity
        deduped = self._deduplicate(merged)

        # Sort by rating (descending), then review count
        deduped.sort(key=lambda r: (r.rating, r.review_count), reverse=True)

        # Cache
        if use_cache and deduped:
            _save_cache(_cache_key(query, location), deduped)

        return deduped

    async def multi_query_search(
        self,
        queries: list[str],
        location: str = "",
        **kwargs,
    ) -> list[SearchResult]:
        """Run multiple queries and merge all results."""
        tasks = [self.search(q, location, **kwargs) for q in queries]
        all_results = await asyncio.gather(*tasks)
        merged = []
        for results in all_results:
            merged.extend(results)
        return self._deduplicate(merged)

    def _deduplicate(self, results: list[SearchResult]) -> list[SearchResult]:
        """Deduplicate by normalized name."""
        seen = {}
        for r in results:
            norm_name = self._normalize_name(r.name_ko or r.name)
            if norm_name in seen:
                # Merge: keep the one with more data
                existing = seen[norm_name]
                if r.rating > existing.rating:
                    seen[norm_name] = r
                if r.review_count > existing.review_count:
                    seen[norm_name].review_count = r.review_count
                if r.address and not existing.address:
                    seen[norm_name].address = r.address
                if r.phone and not existing.phone:
                    seen[norm_name].phone = r.phone
            else:
                seen[norm_name] = r
        return list(seen.values())

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize restaurant name for dedup."""
        # Remove common suffixes and whitespace
        name = name.strip().lower()
        for suffix in ["점", "본점", "1호점", "2호점", "강남점", "서초점", "역삼점"]:
            name = name.replace(suffix, "")
        return name.strip()
