"""Google Places API provider."""

import os
import httpx
from .base import SearchProvider, SearchResult


class GooglePlacesProvider(SearchProvider):
    """
    Google Places API (New).
    Requires GOOGLE_PLACES_API_KEY env var.
    Docs: https://developers.google.com/maps/documentation/places/web-service
    """

    name = "google_places"
    SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
    DETAILS_URL = "https://places.googleapis.com/v1/places"

    def __init__(self):
        self.api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str, location: str = "", **kwargs) -> list[SearchResult]:
        if not self.is_available():
            return []

        search_query = f"{location} {query}".strip() if location else query
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "places.displayName,places.formattedAddress,places.location,"
                "places.rating,places.userRatingCount,places.priceLevel,"
                "places.regularOpeningHours,places.nationalPhoneNumber,"
                "places.websiteUri,places.id"
            ),
        }
        body = {
            "textQuery": search_query,
            "languageCode": "ko",
            "maxResultCount": min(kwargs.get("limit", 10), 20),
        }
        if kwargs.get("lat") and kwargs.get("lng"):
            body["locationBias"] = {
                "circle": {
                    "center": {"latitude": kwargs["lat"], "longitude": kwargs["lng"]},
                    "radius": kwargs.get("radius", 5000.0),
                }
            }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(self.SEARCH_URL, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for place in data.get("places", []):
            loc = place.get("location", {})
            name = place.get("displayName", {}).get("text", "")
            results.append(SearchResult(
                name=name,
                name_ko=name,
                address=place.get("formattedAddress", ""),
                rating=place.get("rating", 0),
                review_count=place.get("userRatingCount", 0),
                lat=loc.get("latitude", 0),
                lng=loc.get("longitude", 0),
                phone=place.get("nationalPhoneNumber", ""),
                url=place.get("websiteUri", ""),
                source="google_places",
                raw_data=place,
            ))
        return results

    async def get_details(self, place_id: str) -> SearchResult | None:
        if not self.is_available():
            return None

        url = f"{self.DETAILS_URL}/{place_id}"
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "displayName,formattedAddress,location,rating,"
                "userRatingCount,priceLevel,regularOpeningHours,"
                "nationalPhoneNumber,websiteUri,reviews,editorialSummary"
            ),
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            place = resp.json()

        loc = place.get("location", {})
        name = place.get("displayName", {}).get("text", "")
        return SearchResult(
            name=name,
            name_ko=name,
            address=place.get("formattedAddress", ""),
            rating=place.get("rating", 0),
            review_count=place.get("userRatingCount", 0),
            lat=loc.get("latitude", 0),
            lng=loc.get("longitude", 0),
            phone=place.get("nationalPhoneNumber", ""),
            url=place.get("websiteUri", ""),
            source="google_places",
            raw_data=place,
        )
