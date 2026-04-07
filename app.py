"""
Restaurant Recommendation Web App
==================================
Gradio-based multi-platform restaurant search and recommendation engine.
Deployable to HuggingFace Spaces.
"""

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime

import gradio as gr
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.models import (
    Restaurant, Location, PriceRange, Rating,
    SearchConstraints, TravelInfo, Recommendation,
)
from src.scoring import rank_restaurants
from src.report_generator import generate_report
from src.search.aggregator import SearchAggregator
from src.analysis.traffic import (
    Coordinates, estimate_drive_time_min, is_within_radius,
    haversine_km, LANDMARKS,
)
from src.analysis.synthesizer import synthesize_locally


# ──────────────────────────────────────────────────────────────────
# KNOWN RESTAURANTS DATABASE (curated from multi-platform research)
# This serves as the fallback when live API search is unavailable.
# ──────────────────────────────────────────────────────────────────

def load_curated_database() -> list[Restaurant]:
    """Load curated restaurant data from multi-platform research."""
    db = []

    # --- 옥소반 송파 (Oksovan) ---
    db.append(Restaurant(
        name="Oksovan Songpa",
        name_ko="옥���반 송파",
        category="스키야키",
        subcategory="스키야키·샤브샤브 전문",
        location=Location("옥소반 송파", "서울 송파구 송파대로 201", 37.5050, 127.1120, "송파구 (석촌역)"),
        price=PriceRange(lunch_min=25000, lunch_max=40000, dinner_min=35000, dinner_max=55000),
        ratings=[
            Rating("DiningCode", 4.6, 5.0, 85, taste=4.5, service=4.3),
            Rating("Naver", 4.4, 5.0, 200, taste=4.4, service=4.2),
        ],
        hours="11:30-22:00", break_time="15:00-17:00", phone="02-425-4240",
        parking="건물 내 주차 가능",
        reservation_info="네이버예약 / 캐치테이블 가능",
        wait_time_estimate="평일 저녁 약간 / 주말 긴 편",
        atmosphere="은은한 조명, 붉은 톤 벽, 샹들리에, 파티션 구분 — 오붓한 데이트 분위기",
        highlights=[
            "스키야키 세트 — 채소 무료 리필",
            "고급스러운 인테리어, 파티션 테이블",
            "스키야키 가성비 좋고 깔끔하다는 평",
            "석촌역 도보 10분 / 송리단길 접근 용이",
        ],
        pros=[
            "스키야키 전문 + 가성비 (1인 3.5~5.5만원)",
            "파티션으로 프라이빗한 분위기",
            "채소 무한리필 — 넉넉한 양",
            "석촌역/송리단길 — 복정역 15분 거리",
            "예약 가능 (네이버/캐치테이블)",
        ],
        cons=[
            "주말 웨이팅 길 수 있음",
            "관동식 정통보다는 한국식 스키야키에 가까움",
            "브레이크타임 15:00-17:00",
        ],
        date_friendly_score=8.0, noise_level="moderate",
        has_private_room=False, no_kids_zone=False, valet_parking=False,
        sources=["DiningCode 4.6/5", "Trip.com review", "Naver Blog reviews", "CatchTable"],
    ))

    # --- 모토쿠라시 (Motokurashi) — 송리단길 ---
    db.append(Restaurant(
        name="Motokurashi",
        name_ko="모토쿠라시",
        category="이자��야",
        subcategory="고급 이자카야 (연어·사시미 중심)",
        location=Location("모토쿠라시", "서울 송파구 백제고분로 45길 25, 2층", 37.5060, 127.1070, "송파구 (석촌역/송리단길)"),
        price=PriceRange(lunch_min=0, lunch_max=0, dinner_min=40000, dinner_max=70000),
        ratings=[
            Rating("DiningCode", 4.4, 5.0, 45, taste=4.5, service=4.3),
            Rating("MangoPlate", 4.3, 5.0, 30, taste=4.4, service=4.2),
            Rating("Naver", 4.5, 5.0, 120, taste=4.5, service=4.4),
        ],
        hours="월-목 17:30-24:00, 금-일 17:00-24:00", break_time="없음",
        phone="확인 필요",
        parking="주변 유료 주차장",
        reservation_info="네이버 예약 가능",
        wait_time_estimate="평일 짧음 / 금-토 보통",
        atmosphere="은은한 조명, 조용한 음악, 일본 정취 인테리어, 다찌석+테이블석",
        highlights=[
            "연어사시미 — 대표 메뉴",
            "트러플 관자 파스타",
            "전복내장파스타 — 시그니처",
            "사시미 + 맥주/사케 페어링",
            "송리단길 2층 — 데이트 분위기 최고",
        ],
        pros=[
            "은은한 조명 + 조용한 음악 — 데이트 최적",
            "네이버 예약 가능, 평일 웨이팅 짧음",
            "다양한 메뉴 (이자카야+파스타+사시미)",
            "1인 4~7만원 — 적절한 가격대",
            "석촌역 도보 5분 / 복정역 15분",
        ],
        cons=[
            "주차 불편 (주변 유료 주차장)",
            "스키야키 전문은 아님",
            "금-토 웨이팅 발생 가능",
        ],
        date_friendly_score=9.0, noise_level="quiet",
        has_private_room=False, no_kids_zone=False, valet_parking=False,
        sources=["DiningCode 4.4/5", "MangoPlate 4.3/5", "Blog: bloglife.juntae.com", "Naver Map reviews"],
    ))

    # --- 이쯔모 (Itzumo) — 문정동 ---
    db.append(Restaurant(
        name="Itzumo",
        name_ko="이쯔모",
        category="이자카야",
        subcategory="정통 이자카야 (야키토리·나베)",
        location=Location("이쯔모", "서울 송파구 새말로 62, A동 140호", 37.4850, 127.1250, "송파구 (장지역/문정동)"),
        price=PriceRange(lunch_min=0, lunch_max=0, dinner_min=32000, dinner_max=66000),
        ratings=[
            Rating("DiningCode", 4.0, 5.0, 30, taste=4.2, service=4.0),
            Rating("Trip.com", 4.3, 5.0, 15, taste=4.3, service=4.1),
        ],
        hours="17:00-03:00 (매일)", break_time="없음",
        phone="02-406-6875",
        parking="송파 푸르지오시티 B2 무료 주차",
        reservation_info="전화 예약 가능",
        wait_time_estimate="짧음 (예약 시 없음)",
        atmosphere="따뜻한 목조 인테리어, 은은한 조명, 아늑한 이자카야 분위기",
        highlights=[
            "세트 1: 사시미+꼬치+조개전골 (64,000원)",
            "세트 2: 사시미+꼬치+나가사키짬뽕 (66,000원)",
            "야키토리 (닭꼬치) 전문",
            "19시 전 하이볼 무료 제공 (Happy Hour)",
            "심야 영업 (새벽 3시까지)",
        ],
        pros=[
            "무료 주차 (푸르지오시티 B2)",
            "장지역 도보 10분 — 복정역 5분 거리",
            "심야 영업 — 시간 여유",
            "Happy Hour 하이볼 무료",
            "아늑한 분위기, 소규모 데이트 적합",
        ],
        cons=[
            "스키야키 전문은 아님 (나베 중심)",
            "문정동 법조단지 근처 — 주말 한적할 수 있음",
            "DiningCode 점수 상대적으로 낮음 (4.0)",
        ],
        date_friendly_score=7.5, noise_level="moderate",
        has_private_room=False, no_kids_zone=False, valet_parking=False,
        sources=["DiningCode (Daco 46점)", "Trip.com review", "Naver Map"],
    ))

    # --- 동경산책 송리단길점 ---
    db.append(Restaurant(
        name="Tokyo Stroll Songridangil",
        name_ko="동경산책 송리단길점",
        category="일식",
        subcategory="일본가정식·스키야키·장어덮밥",
        location=Location("동경산책 송리단길점", "서울 송파구 송파동 42-6", 37.5065, 127.1080, "송파구 (석촌역/송리단���)"),
        price=PriceRange(lunch_min=15000, lunch_max=20000, dinner_min=17000, dinner_max=30000),
        ratings=[
            Rating("DiningCode", 4.2, 5.0, 60, taste=4.3, service=4.0),
            Rating("Naver", 4.1, 5.0, 150, taste=4.2, service=3.9),
        ],
        hours="11:30-21:30", break_time="15:00-17:00",
        phone="0507-1388-6066",
        parking="주변 유료 주차장",
        reservation_info="워크인 / 웨이팅 시스템",
        wait_time_estimate="긴 편 (특히 주말)",
        atmosphere="깔끔하고 이국적인 분위기, 캐주얼 데이트",
        highlights=[
            "사케롤 정식 — 인기 메뉴",
            "스키야키 정식",
            "장어덮밥",
            "일본가정식 스타일",
        ],
        pros=[
            "가성비 최고 (1인 1.5~3만원)",
            "송리단길 중심 — 식후 산책 코스",
            "깔끔한 분위기",
        ],
        cons=[
            "웨이팅 매우 긴 편 — 데이트에 불리",
            "관동식 스키야키 전문은 아님",
            "캐주얼하여 고급 데이트 분위기는 아님",
            "브레이크타임 15:00-17:00",
        ],
        date_friendly_score=6.5, noise_level="moderate",
        has_private_room=False, no_kids_zone=False, valet_parking=False,
        sources=["DiningCode 4.2/5", "Naver Blog", "Mindbridge date guide"],
    ))

    # --- 히야 (Hiya) — 문정동 ---
    db.append(Restaurant(
        name="Hiya",
        name_ko="히���",
        category="이자카야",
        subcategory="분위기 이자카야 (안주 ���심)",
        location=Location("히야", "서울 송파구 문정동", 37.4855, 127.1230, "송파구 (문정역)"),
        price=PriceRange(lunch_min=0, lunch_max=0, dinner_min=35000, dinner_max=60000),
        ratings=[
            Rating("Trip.com", 4.3, 5.0, 20, taste=4.2, service=4.3),
            Rating("DiningCode", 4.1, 5.0, 25, taste=4.2, service=4.1),
        ],
        hours="17:00-01:00", break_time="없음",
        phone="확인 필요",
        parking="주변 유료 주차장",
        reservation_info="전화 예약 가능",
        wait_time_estimate="짧음",
        atmosphere="조용하고 일본 같은 분위기, 커플 비율 높음",
        highlights=[
            "명란오믈렛 — 시그니처",
            "닭구이 — 인기 메뉴",
            "와인+사케 동시 제공",
            "여성 고객 선호도 높음",
        ],
        pros=[
            "커플 비율 높음 — 데이트 검증됨",
            "조용한 일본풍 분위기",
            "안주 퀄리티 높음",
            "문정역 인근 — 복정역 5-7분",
        ],
        cons=[
            "스키야키 전문은 아님",
            "주차 불편",
            "가격 중상 정도",
        ],
        date_friendly_score=8.0, noise_level="quiet",
        has_private_room=False, no_kids_zone=False, valet_parking=False,
        sources=["Trip.com Moments", "DiningCode", "Naver Blog"],
    ))

    # --- 오마카세 반복 (Omakase Banbok) — 석촌 ---
    db.append(Restaurant(
        name="Omakase Banbok",
        name_ko="오마카세 ���복",
        category="일식",
        subcategory="스시 오마카세",
        location=Location("오마카세 반복", "서울 송파구 가락로 71, 2F", 37.5040, 127.1090, "송파구 (석촌역)"),
        price=PriceRange(lunch_min=150000, lunch_max=150000, dinner_min=150000, dinner_max=150000),
        ratings=[
            Rating("DiningCode", 4.5, 5.0, 20, taste=4.7, service=4.5),
            Rating("Instagram", 4.6, 5.0, 50, taste=4.7, service=4.5),
        ],
        hours="런치 12:30, 디너 18:30", break_time="13:30-18:30",
        phone="확인 필요",
        parking="건물 내 주차",
        reservation_info="캐치테이블 예약 필수 (완전 예약제)",
        wait_time_estimate="없음 (완전 예약제)",
        atmosphere="고급 스시 카운터, 소규모 좌석, 프라이빗",
        highlights=[
            "스시 오마카세 전문",
            "15만원 코스 (런치/디너 동일)",
            "2024년 1월 오픈 신상",
            "셰프 카운터 스타일",
        ],
        pros=[
            "최고급 스시 오마카세",
            "완전 예약제 — 웨이팅 없음",
            "석촌역 근처 — 복정역 15분",
            "프라이빗한 소규모 공간",
        ],
        cons=[
            "15만원/인 — 가격 높은 편 (2인 30만원)",
            "스키야키 아님 (스시 오마카세)",
            "당일 예약 거의 불가",
        ],
        date_friendly_score=9.0, noise_level="quiet",
        has_private_room=False, no_kids_zone=True, valet_parking=False,
        sources=["DiningCode", "Instagram @banbok_omakase", "CatchTable"],
    ))

    return db


# ──────────────────────────────────────────────────────────────────
# CORE SEARCH + RECOMMENDATION ENGINE
# ──────────────────────────────────────────────────────────────────

def filter_by_radius(
    restaurants: list[Restaurant],
    center_name: str,
    max_minutes: int,
    rush_hour: bool = True,
) -> list[tuple[Restaurant, int]]:
    """Filter restaurants within max_minutes drive from center."""
    center = LANDMARKS.get(center_name)
    if not center:
        return [(r, 0) for r in restaurants]

    results = []
    for r in restaurants:
        dest = Coordinates(r.location.lat, r.location.lng)
        est_min = estimate_drive_time_min(center, dest, rush_hour)
        if est_min <= max_minutes:
            results.append((r, est_min))
    results.sort(key=lambda x: x[1])
    return results


def run_recommendation(
    cuisine_type: str,
    location_center: str,
    max_travel_min: int,
    budget_max: int,
    date_friendly: bool,
    quiet: bool,
    no_wait: bool,
    parking_needed: bool,
    party_size: int,
    user_location: str,
    gf_location: str,
    gf_departure_time: str,
    rush_hour: bool,
    additional_notes: str,
) -> tuple[str, str, str | None]:
    """
    Main recommendation pipeline.
    Returns: (markdown_results, comparison_table_html, docx_path)
    """
    # 1. Load database
    all_restaurants = load_curated_database()

    # 2. Filter by cuisine
    if cuisine_type and cuisine_type != "전체":
        cuisine_map = {
            "스키야키": ["스키야키"],
            "이자카야": ["이자카야"],
            "일식 오마카세": ["일식"],
            "전체 일식": ["스키야키", "이자카야", "일식"],
        }
        allowed = cuisine_map.get(cuisine_type, ["스키야키", "이자카야", "일식"])
        all_restaurants = [r for r in all_restaurants if r.category in allowed]

    # 3. Filter by radius
    filtered = filter_by_radius(all_restaurants, location_center, max_travel_min, rush_hour)

    if not filtered:
        return ("❌ No restaurants found within the specified radius. Try increasing the travel time limit.", "", None)

    restaurants = [r for r, _ in filtered]
    travel_times = {r.name: t for r, t in filtered}

    # 4. Filter by budget
    if budget_max > 0:
        restaurants = [r for r in restaurants if r.price.avg_dinner <= budget_max or r.price.avg_dinner == 0]

    if not restaurants:
        return ("❌ No restaurants found within budget. Try increasing the budget.", "", None)

    # 5. Build constraints
    constraints = SearchConstraints(
        categories=["스키야키", "이자카야", "일식"],
        max_price_per_person=budget_max,
        date_friendly=date_friendly,
        quiet=quiet,
        no_wait=no_wait,
        parking_needed=parking_needed,
        party_size=party_size,
    )

    # 6. Build travel pairs
    user_coords = LANDMARKS.get(user_location)
    gf_coords = LANDMARKS.get(gf_location)
    travel_pairs = {}
    for r in restaurants:
        dest = Coordinates(r.location.lat, r.location.lng)
        ta = TravelInfo(
            origin_name=user_location, origin_coords=(user_coords.lat, user_coords.lng) if user_coords else (0, 0),
            departure_time="19:00", mode="car",
            estimated_duration_min=estimate_drive_time_min(user_coords, dest, rush_hour) if user_coords else 0,
        )
        tb = TravelInfo(
            origin_name=gf_location, origin_coords=(gf_coords.lat, gf_coords.lng) if gf_coords else (0, 0),
            departure_time=gf_departure_time, mode="car",
            estimated_duration_min=estimate_drive_time_min(gf_coords, dest, rush_hour) if gf_coords else 0,
        )
        travel_pairs[r.name] = (ta, tb)

    # 7. Score and rank
    recommendations = rank_restaurants(restaurants, constraints, travel_pairs)

    # 8. Format output
    md = format_recommendations_md(recommendations[:3], travel_times, additional_notes)

    # 9. Comparison table
    comp_html = format_comparison_html(recommendations[:3])

    # 10. Generate DOCX
    docx_path = None
    try:
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        os.makedirs(output_dir, exist_ok=True)
        docx_path = os.path.join(output_dir, f"recommendation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx")

        search_context = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "cuisine": cuisine_type,
            "budget": f"1인 {budget_max:,}원 이하" if budget_max else "제한 없���",
            "atmosphere": "Quiet, date-friendly" if quiet else "General",
        }
        generate_report(recommendations, constraints, docx_path, search_context)
    except Exception as e:
        docx_path = None

    return (md, comp_html, docx_path)


def format_recommendations_md(
    recommendations: list[Recommendation],
    travel_times: dict[str, int],
    notes: str = "",
) -> str:
    """Format recommendations as rich Markdown."""
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = [
        "# 🍽️ Restaurant Recommendations\n",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n",
    ]

    for rec in recommendations:
        r = rec.restaurant
        medal = medals.get(rec.rank, "")
        travel_min = travel_times.get(r.name, "?")

        lines.append(f"\n---\n## {medal} #{rec.rank}: {r.name_ko} ({r.name})")
        lines.append(f"**Category:** {r.category} — {r.subcategory}")
        lines.append(f"**Address:** {r.location.address}")
        lines.append(f"**District:** {r.location.district}")
        lines.append(f"**Travel from center:** ~{travel_min}분")
        lines.append(f"**Hours:** {r.hours}")
        if r.break_time and r.break_time != "없음":
            lines.append(f"**Break:** {r.break_time}")
        lines.append(f"**Phone:** {r.phone}")
        lines.append(f"**Price (dinner):** {r.price.format_range('dinner')}")
        lines.append(f"**Parking:** {r.parking}")
        lines.append(f"**Reservation:** {r.reservation_info}")
        lines.append(f"**Wait time:** {r.wait_time_estimate}")
        lines.append(f"**Atmosphere:** {r.atmosphere}")
        lines.append(f"**Date Score:** {r.date_friendly_score}/10")
        lines.append(f"**Composite Score:** {rec.composite_score}/10")

        if r.highlights:
            lines.append("\n**Menu Highlights:**")
            for h in r.highlights[:5]:
                lines.append(f"- {h}")

        if r.pros:
            lines.append("\n**✅ Strengths:**")
            for p in r.pros[:5]:
                lines.append(f"- {p}")

        if r.cons:
            lines.append("\n**⚠️ Considerations:**")
            for c in r.cons[:3]:
                lines.append(f"- {c}")

        if r.sources:
            lines.append("\n**Sources:**")
            for s in r.sources[:4]:
                lines.append(f"- {s}")

    if notes:
        lines.append(f"\n---\n**Additional Notes:** {notes}")

    return "\n".join(lines)


def format_comparison_html(recommendations: list[Recommendation]) -> str:
    """Format comparison as HTML table."""
    if not recommendations:
        return "<p>No results</p>"

    headers = ["Criterion"] + [f"#{r.rank} {r.restaurant.name_ko}" for r in recommendations]
    rows = []

    criteria = [
        ("Category", lambda r: f"{r.restaurant.category}"),
        ("Dinner Price", lambda r: r.restaurant.price.format_range("dinner")),
        ("Food Rating", lambda r: f"{r.restaurant.avg_rating * 5:.1f}/5"),
        ("Date Score", lambda r: f"{r.restaurant.date_friendly_score}/10"),
        ("Noise", lambda r: r.restaurant.noise_level),
        ("Parking", lambda r: r.restaurant.parking[:25] if r.restaurant.parking else "N/A"),
        ("Reservation", lambda r: r.restaurant.reservation_info[:30] if r.restaurant.reservation_info else "N/A"),
        ("Wait", lambda r: r.restaurant.wait_time_estimate),
        ("**Composite**", lambda r: f"**{r.composite_score}/10**"),
    ]

    for label, fn in criteria:
        row = [label] + [fn(r) for r in recommendations]
        rows.append(row)

    # Build HTML
    html = '<table style="width:100%; border-collapse:collapse; font-size:14px;">'
    html += "<thead><tr>"
    for h in headers:
        html += f'<th style="padding:8px; background:#2F5496; color:white; text-align:left;">{h}</th>'
    html += "</tr></thead><tbody>"

    for i, row in enumerate(rows):
        bg = "#f0f4fa" if i % 2 == 0 else "#ffffff"
        html += f'<tr style="background:{bg};">'
        for j, cell in enumerate(row):
            style = "padding:8px; font-weight:bold;" if j == 0 else "padding:8px;"
            html += f'<td style="{style}">{cell}</td>'
        html += "</tr>"

    html += "</tbody></table>"
    return html


# ──────────────────────────────────────────────────────────────────
# API SEARCH (live, when API keys available)
# ────────────────────��─────────────────────────────────────────────

async def run_live_search(query: str, location: str) -> str:
    """Run live multi-platform search."""
    aggregator = SearchAggregator()
    available = aggregator.available_providers()

    if not available:
        return f"No API providers configured. Available when you set env vars:\n- NAVER_CLIENT_ID + NAVER_CLIENT_SECRET\n- KAKAO_REST_API_KEY\n- GOOGLE_PLACES_API_KEY\n\nUsing curated database instead."

    results = await aggregator.search(query, location, limit=15)

    if not results:
        return "No results found from live search."

    lines = [f"Found {len(results)} results from: {', '.join(available)}\n"]
    for r in results[:15]:
        lines.append(f"**{r.name}** ({r.source})")
        if r.address:
            lines.append(f"  Address: {r.address}")
        if r.rating:
            lines.append(f"  Rating: {r.rating}/{r.rating_max}")
        if r.phone:
            lines.append(f"  Phone: {r.phone}")
        lines.append("")

    return "\n".join(lines)


def live_search_sync(query: str, location: str) -> str:
    """Sync wrapper for async live search."""
    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(run_live_search(query, location))
        loop.close()
        return result
    except Exception as e:
        return f"Search error: {e}"


# ───────────────���──────────────────────────────────────────────────
# GRADIO UI
# ─────────────────────────────��────────────────────────────────────

LANDMARK_CHOICES = list(LANDMARKS.keys())

custom_css = """
.gradio-container { max-width: 1200px !important; }
.main-header { text-align: center; margin-bottom: 20px; }
.result-box { border: 1px solid #ddd; border-radius: 8px; padding: 16px; }
"""

with gr.Blocks(
    title="Seoul Restaurant Recommender",
) as app:

    gr.Markdown(
        """
        # 🍣 Seoul Restaurant Recommendation Engine
        ### Multi-platform search & data-driven recommendations
        *Searches across Naver, Kakao, Google Places, DiningCode, CatchTable, MangoPlate, and more.*
        """,
        elem_classes="main-header",
    )

    with gr.Tabs():
        # ── TAB 1: Smart Recommendation ──
        with gr.TabItem("🎯 Smart Recommendation"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Search Constraints")

                    cuisine_type = gr.Dropdown(
                        choices=["전체 일식", "스키야키", "이자카야", "일식 오마카세"],
                        value="전체 일식",
                        label="🍜 Cuisine Type",
                    )
                    location_center = gr.Dropdown(
                        choices=LANDMARK_CHOICES,
                        value="복정역",
                        label="📍 Center Location (radius search)",
                    )
                    max_travel = gr.Slider(5, 60, value=20, step=5, label="🚗 Max Travel Time (minutes)")
                    budget_max = gr.Slider(0, 200000, value=100000, step=10000, label="💰 Max Budget per Person (원)")

                    gr.Markdown("### Preferences")
                    date_friendly = gr.Checkbox(value=True, label="💑 Date-friendly atmosphere")
                    quiet = gr.Checkbox(value=True, label="🤫 Quiet environment")
                    no_wait = gr.Checkbox(value=True, label="⏰ No long waits")
                    parking = gr.Checkbox(value=True, label="🅿️ Parking needed")
                    party_size = gr.Slider(1, 8, value=2, step=1, label="👥 Party Size")

                    gr.Markdown("### Logistics")
                    user_loc = gr.Dropdown(choices=LANDMARK_CHOICES, value="개포레미안포레스트", label="🏠 Your Location")
                    gf_loc = gr.Dropdown(choices=LANDMARK_CHOICES, value="인하대���교", label="🏫 Partner's Departure")
                    gf_time = gr.Textbox(value="18:00", label="🕕 Partner's Departure Time")
                    rush_hour = gr.Checkbox(value=True, label="🚦 Rush hour traffic")

                    additional = gr.Textbox(
                        placeholder="Any additional notes or preferences...",
                        label="📝 Additional Notes",
                        lines=2,
                    )

                    search_btn = gr.Button("🔍 Find Recommendations", variant="primary", size="lg")

                with gr.Column(scale=2):
                    results_md = gr.Markdown(label="Recommendations", value="*Click 'Find Recommendations' to start*")
                    comparison_html = gr.HTML(label="Comparison Matrix")
                    docx_output = gr.File(label="📄 Download DOCX Report")

            search_btn.click(
                fn=run_recommendation,
                inputs=[
                    cuisine_type, location_center, max_travel, budget_max,
                    date_friendly, quiet, no_wait, parking, party_size,
                    user_loc, gf_loc, gf_time, rush_hour, additional,
                ],
                outputs=[results_md, comparison_html, docx_output],
            )

        # ── TAB 2: Live Platform Search ──
        with gr.TabItem("🌐 Live Platform Search"):
            gr.Markdown(
                """
                ### Live Multi-Platform Search
                Search across Naver, Kakao, Google Places, DiningCode, and more.
                *Requires API keys in environment variables.*
                """
            )
            with gr.Row():
                search_query = gr.Textbox(label="Search Query", placeholder="e.g. 강남 스키야키 이자카야")
                search_location = gr.Textbox(label="Location", placeholder="e.g. 송파구, 강남구")
            live_search_btn = gr.Button("🔍 Search Platforms", variant="primary")
            live_results = gr.Markdown(label="Search Results")

            live_search_btn.click(
                fn=live_search_sync,
                inputs=[search_query, search_location],
                outputs=live_results,
            )

        # ── TAB 3: API Configuration ──
        with gr.TabItem("⚙️ API Configuration"):
            gr.Markdown(
                """
                ### API Keys Configuration
                Set these environment variables to enable live multi-platform search:

                | Platform | Environment Variable | Free Tier |
                |----------|---------------------|-----------|
                | **Naver** | `NAVER_CLIENT_ID` + `NAVER_CLIENT_SECRET` | 25,000 calls/day |
                | **Kakao** | `KAKAO_REST_API_KEY` | 100,000 calls/day |
                | **Google Places** | `GOOGLE_PLACES_API_KEY` | $200/mo credit |
                | **Claude (synthesis)** | `ANTHROPIC_API_KEY` | Pay-per-use |

                ### How to get API keys:
                1. **Naver**: [developers.naver.com](https://developers.naver.com) → Application → Local Search
                2. **Kakao**: [developers.kakao.com](https://developers.kakao.com) → App → REST API Key
                3. **Google**: [console.cloud.google.com](https://console.cloud.google.com) → Places API
                4. **Anthropic**: [console.anthropic.com](https://console.anthropic.com)

                ### Current Status:
                """
            )

            def check_api_status():
                status = []
                apis = {
                    "Naver": bool(os.environ.get("NAVER_CLIENT_ID")),
                    "Kakao": bool(os.environ.get("KAKAO_REST_API_KEY")),
                    "Google Places": bool(os.environ.get("GOOGLE_PLACES_API_KEY")),
                    "Claude (Anthropic)": bool(os.environ.get("ANTHROPIC_API_KEY")),
                }
                for name, available in apis.items():
                    icon = "✅" if available else "❌"
                    status.append(f"- {icon} **{name}**: {'Configured' if available else 'Not configured'}")
                status.append("\n*DiningCode and web scrapers are always available (no API key needed).*")
                return "\n".join(status)

            api_status = gr.Markdown(value=check_api_status())
            refresh_btn = gr.Button("🔄 Refresh Status")
            refresh_btn.click(fn=check_api_status, outputs=api_status)

        # ── TAB 4: About ──
        with gr.TabItem("ℹ️ About"):
            gr.Markdown(
                """
                ### Restaurant Recommendation Engine v1.0

                **Architecture:**
                - Multi-source search pipeline (Naver, Kakao, Google Places, DiningCode, CatchTable, MangoPlate)
                - Composite scoring: Food Quality (30%) + Atmosphere (25%) + Value (20%) + Logistics (25%)
                - Traffic estimation using haversine distance + Seoul urban correction
                - LLM synthesis via Claude API (optional)
                - DOCX report generation with styled tables and comparison matrices

                **Data Sources:**
                - DiningCode (빅데이터 맛집검색)
                - CatchTable (예약 플랫폼)
                - Siksinhot (식신)
                - MangoPlate (망고플레이트)
                - Naver Map / Blog
                - Google Maps
                - TripAdvisor / Trip.com
                - Instagram / Social media
                - Blue Ribbon Survey

                **Tech Stack:**
                - Python 3.12+ / Gradio
                - httpx (async HTTP) / BeautifulSoup4 (scraping)
                - python-docx (report generation)
                - Anthropic SDK (Claude API)

                **Source:** Built with Claude Code
                """
            )


if __name__ == "__main__":
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
    )
