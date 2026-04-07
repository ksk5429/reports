"""Data models for restaurant search."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Location:
    name: str
    address: str
    lat: float
    lng: float
    district: str = ""


@dataclass
class PriceRange:
    lunch_min: int = 0
    lunch_max: int = 0
    dinner_min: int = 0
    dinner_max: int = 0
    currency: str = "KRW"

    @property
    def avg_dinner(self) -> int:
        if self.dinner_min and self.dinner_max:
            return (self.dinner_min + self.dinner_max) // 2
        return self.dinner_max or self.dinner_min

    def format_range(self, meal: str = "dinner") -> str:
        if meal == "lunch":
            lo, hi = self.lunch_min, self.lunch_max
        else:
            lo, hi = self.dinner_min, self.dinner_max
        if lo == hi:
            return f"{lo:,}원"
        return f"{lo:,}~{hi:,}원"


@dataclass
class Rating:
    source: str
    score: float
    max_score: float = 5.0
    review_count: int = 0
    taste: float = 0.0
    service: float = 0.0
    price_satisfaction: float = 0.0

    @property
    def normalized(self) -> float:
        return self.score / self.max_score


@dataclass
class Restaurant:
    name: str
    name_ko: str
    category: str  # "스키야키", "이자카야", "일식"
    subcategory: str  # "관동식", "관서식", "오마카세", etc.
    location: Location
    price: PriceRange
    ratings: list[Rating] = field(default_factory=list)
    hours: str = ""
    break_time: str = ""
    phone: str = ""
    parking: str = ""
    reservation_info: str = ""
    wait_time_estimate: str = ""
    atmosphere: str = ""
    highlights: list[str] = field(default_factory=list)
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    date_friendly_score: float = 0.0  # 0-10
    noise_level: str = ""  # "quiet", "moderate", "loud"
    has_private_room: bool = False
    no_kids_zone: bool = False
    valet_parking: bool = False
    sources: list[str] = field(default_factory=list)

    @property
    def avg_rating(self) -> float:
        if not self.ratings:
            return 0.0
        return sum(r.normalized for r in self.ratings) / len(self.ratings)

    @property
    def weighted_score(self) -> float:
        """Composite score for ranking: taste, atmosphere, value, convenience."""
        taste_avg = sum(r.taste for r in self.ratings if r.taste) / max(1, sum(1 for r in self.ratings if r.taste))
        score = (
            taste_avg * 0.30
            + self.date_friendly_score / 10.0 * 5.0 * 0.25
            + self.avg_rating * 5.0 * 0.25
            + (5.0 - min(self.price.avg_dinner / 40000, 5.0)) * 0.10
            + (1.0 if self.reservation_info else 0.0) * 0.10
        )
        return round(score, 2)


@dataclass
class SearchConstraints:
    categories: list[str] = field(default_factory=list)
    max_price_per_person: int = 0
    min_quality_score: float = 0.0
    preferred_districts: list[str] = field(default_factory=list)
    date_friendly: bool = False
    quiet: bool = False
    no_wait: bool = False
    parking_needed: bool = True
    reservation_required: bool = True
    party_size: int = 2


@dataclass
class TravelInfo:
    origin_name: str
    origin_coords: tuple[float, float]
    departure_time: str
    mode: str  # "car", "transit"
    estimated_duration_min: int = 0
    traffic_notes: str = ""


@dataclass
class Recommendation:
    rank: int
    restaurant: Restaurant
    travel_info_a: Optional[TravelInfo] = None  # user
    travel_info_b: Optional[TravelInfo] = None  # girlfriend
    reasoning: str = ""
    composite_score: float = 0.0
