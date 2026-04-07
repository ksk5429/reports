"""Scoring and ranking engine for restaurant recommendations."""

from .models import Restaurant, SearchConstraints, Recommendation, TravelInfo


def compute_composite_score(
    restaurant: Restaurant,
    constraints: SearchConstraints,
    travel_a: TravelInfo | None = None,
    travel_b: TravelInfo | None = None,
) -> float:
    """
    Multi-factor scoring:
      - Food quality (30%)
      - Date atmosphere (25%)
      - Value for money (15%)
      - Accessibility / travel time (15%)
      - Reservation ease / no wait (15%)
    """
    # Food quality: average normalized rating * 10
    food = restaurant.avg_rating * 10.0

    # Atmosphere: date_friendly_score already 0-10
    atmosphere = restaurant.date_friendly_score

    # Value: inverse of price, scaled
    avg_price = restaurant.price.avg_dinner or 80000
    if constraints.max_price_per_person > 0:
        value = max(0, 10 - (avg_price / constraints.max_price_per_person) * 5)
    else:
        value = max(0, 10 - avg_price / 20000)

    # Travel convenience
    travel_score = 10.0
    if travel_a and travel_b:
        total_min = travel_a.estimated_duration_min + travel_b.estimated_duration_min
        travel_score = max(0, 10 - total_min / 20)
    elif travel_b:
        travel_score = max(0, 10 - travel_b.estimated_duration_min / 15)

    # Reservation / wait
    reserve_score = 5.0
    if restaurant.reservation_info:
        reserve_score += 2.5
    if restaurant.wait_time_estimate in ("없음", "없음 (예약)", "짧음"):
        reserve_score += 2.5
    if restaurant.no_kids_zone:
        reserve_score += 1.0
    reserve_score = min(reserve_score, 10.0)

    composite = (
        food * 0.30
        + atmosphere * 0.25
        + value * 0.15
        + travel_score * 0.15
        + reserve_score * 0.15
    )
    return round(composite, 2)


def rank_restaurants(
    restaurants: list[Restaurant],
    constraints: SearchConstraints,
    travel_pairs: dict[str, tuple[TravelInfo | None, TravelInfo | None]] | None = None,
) -> list[Recommendation]:
    """Rank and return top recommendations."""
    travel_pairs = travel_pairs or {}
    scored = []
    for r in restaurants:
        ta, tb = travel_pairs.get(r.name, (None, None))
        score = compute_composite_score(r, constraints, ta, tb)
        scored.append((r, score, ta, tb))

    scored.sort(key=lambda x: x[1], reverse=True)

    recommendations = []
    for rank, (rest, score, ta, tb) in enumerate(scored, 1):
        recommendations.append(
            Recommendation(
                rank=rank,
                restaurant=rest,
                travel_info_a=ta,
                travel_info_b=tb,
                composite_score=score,
            )
        )
    return recommendations
