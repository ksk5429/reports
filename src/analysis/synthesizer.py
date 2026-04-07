"""LLM-powered synthesis engine using Claude API."""

import os
import json
from dataclasses import asdict

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from ..models import Restaurant, SearchConstraints, Recommendation


SYSTEM_PROMPT = """You are an expert restaurant recommendation analyst for Seoul, Korea.
You specialize in Japanese cuisine (스키야키, 이자카야, 오마카세, 일식).

Given search results from multiple platforms, you must:
1. Cross-reference data across sources for accuracy
2. Evaluate food quality, atmosphere, value, and logistics
3. Consider the specific constraints (location, budget, date-friendliness, parking, wait times)
4. Produce a ranked recommendation with clear reasoning

Always respond in a structured JSON format when asked for analysis.
Be honest about data gaps — if a restaurant has few reviews, flag it."""


def build_analysis_prompt(
    search_results: list[dict],
    constraints: dict,
    context: str = "",
) -> str:
    """Build the prompt for Claude analysis."""
    return f"""Analyze these restaurant search results and provide recommendations.

## Search Results (from multiple platforms)
{json.dumps(search_results, ensure_ascii=False, indent=2)}

## Constraints
{json.dumps(constraints, ensure_ascii=False, indent=2)}

## Additional Context
{context}

## Instructions
1. Cross-reference restaurants that appear on multiple platforms
2. Score each on: food_quality (0-10), atmosphere (0-10), value (0-10), logistics (0-10)
3. Factor in the specific constraints above
4. Return your top 3 recommendations

Respond in this exact JSON format:
{{
  "recommendations": [
    {{
      "rank": 1,
      "name": "...",
      "name_ko": "...",
      "category": "...",
      "address": "...",
      "scores": {{"food": 0, "atmosphere": 0, "value": 0, "logistics": 0, "composite": 0}},
      "price_range": "...",
      "reasoning": "...",
      "highlights": ["..."],
      "concerns": ["..."],
      "reservation_tip": "..."
    }}
  ],
  "methodology_notes": "..."
}}"""


async def synthesize_with_claude(
    search_results: list[dict],
    constraints: dict,
    context: str = "",
) -> dict | None:
    """Call Claude API to synthesize recommendations from raw search data."""
    if not HAS_ANTHROPIC:
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None

    client = anthropic.Anthropic(api_key=api_key)
    prompt = build_analysis_prompt(search_results, constraints, context)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text

        # Extract JSON from response
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0]
        else:
            json_str = response_text

        return json.loads(json_str.strip())

    except Exception as e:
        return {"error": str(e)}


def synthesize_locally(
    restaurants: list[Restaurant],
    constraints: SearchConstraints,
) -> list[dict]:
    """
    Local synthesis without LLM — rule-based scoring.
    Used as fallback when Claude API is unavailable.
    """
    scored = []
    for r in restaurants:
        # Food quality from ratings
        food = r.avg_rating * 10 if r.ratings else 5.0

        # Atmosphere
        atmosphere = r.date_friendly_score

        # Value (inverse of price, scaled)
        avg_price = r.price.avg_dinner or 80000
        if constraints.max_price_per_person > 0:
            value = max(0, 10 * (1 - avg_price / (constraints.max_price_per_person * 1.5)))
        else:
            value = max(0, 10 - avg_price / 20000)

        # Logistics (reservation + wait + parking)
        logistics = 5.0
        if r.reservation_info:
            logistics += 1.5
        if r.wait_time_estimate in ("없음", "없음 (예약)", "짧음"):
            logistics += 1.5
        if r.parking:
            logistics += 1.0
        if r.no_kids_zone:
            logistics += 0.5
        logistics = min(logistics, 10.0)

        composite = food * 0.30 + atmosphere * 0.25 + value * 0.20 + logistics * 0.25

        scored.append({
            "name": r.name,
            "name_ko": r.name_ko,
            "category": r.category,
            "address": r.location.address,
            "scores": {
                "food": round(food, 1),
                "atmosphere": round(atmosphere, 1),
                "value": round(value, 1),
                "logistics": round(logistics, 1),
                "composite": round(composite, 1),
            },
            "price_range": r.price.format_range("dinner"),
            "reasoning": "; ".join(r.pros[:3]),
            "highlights": r.highlights[:5],
            "concerns": r.cons[:3],
        })

    scored.sort(key=lambda x: x["scores"]["composite"], reverse=True)

    for i, item in enumerate(scored, 1):
        item["rank"] = i

    return scored
