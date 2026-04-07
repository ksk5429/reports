"""Traffic and travel time estimation module."""

import math
from dataclasses import dataclass


@dataclass
class Coordinates:
    lat: float
    lng: float
    name: str = ""


# Key Seoul landmarks with coordinates
LANDMARKS = {
    "복정역": Coordinates(37.4720, 127.1266, "복정역 (Line 8 / Suinbundang)"),
    "위례": Coordinates(37.4780, 127.1400, "위례신도시"),
    "개포레미안포레스트": Coordinates(37.4830, 127.0620, "개포레미안포레스트"),
    "인하대학교": Coordinates(37.4494, 126.6570, "인하대학교 (Incheon)"),
    "강남역": Coordinates(37.4979, 127.0276, "강남역"),
    "선릉역": Coordinates(37.5045, 127.0489, "선릉역"),
    "압구정역": Coordinates(37.5268, 127.0285, "압구정역"),
    "잠실역": Coordinates(37.5133, 127.1001, "잠실역"),
    "송파역": Coordinates(37.5057, 127.1128, "송파역"),
    "가락시장역": Coordinates(37.4928, 127.1182, "가락시장역"),
    "수서역": Coordinates(37.4874, 127.1020, "수서역"),
    "석촌역": Coordinates(37.5056, 127.1067, "석촌역"),
    "문정역": Coordinates(37.4849, 127.1222, "문정역"),
    "장지역": Coordinates(37.4784, 127.1264, "장지역"),
    "오금역": Coordinates(37.5016, 127.1270, "오금역"),
}


def haversine_km(a: Coordinates, b: Coordinates) -> float:
    """Great-circle distance between two points in km."""
    R = 6371.0
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat = math.radians(b.lat - a.lat)
    dlng = math.radians(b.lng - a.lng)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def estimate_drive_time_min(
    origin: Coordinates,
    dest: Coordinates,
    rush_hour: bool = True,
) -> int:
    """
    Estimate driving time in minutes.
    Uses haversine distance with urban correction factor.
    Rush hour adds 40-60% to base time.
    """
    dist_km = haversine_km(origin, dest)
    # Short distances (<5km) in same district: local roads, less congestion
    # Longer distances: more highway/arterial, more affected by rush hour
    if dist_km < 5:
        avg_speed = 20.0 if rush_hour else 30.0
        road_factor = 1.25
    elif dist_km < 15:
        avg_speed = 18.0 if rush_hour else 28.0
        road_factor = 1.30
    else:
        avg_speed = 15.0 if rush_hour else 25.0
        road_factor = 1.35
    time_min = (dist_km * road_factor / avg_speed) * 60
    return max(3, round(time_min))


def is_within_radius(
    center: Coordinates,
    target: Coordinates,
    max_minutes: int = 20,
    rush_hour: bool = True,
) -> tuple[bool, int]:
    """Check if target is within max_minutes drive from center."""
    est_min = estimate_drive_time_min(center, target, rush_hour)
    return (est_min <= max_minutes, est_min)


def get_landmark(name: str) -> Coordinates | None:
    """Look up a named landmark."""
    return LANDMARKS.get(name)


def estimate_all_travel(
    restaurant_lat: float,
    restaurant_lng: float,
    origins: dict[str, Coordinates],
    rush_hour: bool = True,
) -> dict[str, int]:
    """Estimate travel time from multiple origins to one restaurant."""
    dest = Coordinates(restaurant_lat, restaurant_lng)
    return {
        name: estimate_drive_time_min(origin, dest, rush_hour)
        for name, origin in origins.items()
    }
