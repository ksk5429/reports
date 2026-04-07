"""
Restaurant Recommendation Report Generator (v2 — 복정역 반경)
================================================================
Date: 2026-04-07
Constraint: Within 20 minutes drive from 복정역
Cuisine: 관동식 스키야키 / 고퀄리티 이자카야 / 분위기 좋은 일식
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import load_curated_database, filter_by_radius
from src.models import SearchConstraints, TravelInfo
from src.scoring import rank_restaurants
from src.report_generator import generate_report
from src.analysis.traffic import Coordinates, estimate_drive_time_min, LANDMARKS


def main():
    print("=" * 60)
    print("  맛집 추천 시스템 v2")
    print("  날짜: 2026-04-07 | 기준: 복정역 20분 이내")
    print("=" * 60)

    # 1. Load database
    print("\n[1/4] 멀티 플랫폼 맛집 DB 로딩...")
    restaurants = load_curated_database()
    print(f"  -> {len(restaurants)}개 맛집 로딩 완료")

    # 2. Filter by 복정역 20min radius
    print("[2/4] 복정역 반경 20분 이내 필터링...")
    filtered = filter_by_radius(restaurants, "복정역", 20, rush_hour=True)
    print(f"  -> {len(filtered)}개 맛집 반경 이내")
    for r, t in filtered:
        print(f"     {r.name_ko}: ~{t}분")

    if not filtered:
        print("  ERROR: 반경 이내 맛집 없음. 범위를 확대하세요.")
        return

    restaurants_in_range = [r for r, _ in filtered]
    travel_times = {r.name: t for r, t in filtered}

    # 3. Constraints
    constraints = SearchConstraints(
        categories=["스키야키", "이자카야", "일식"],
        max_price_per_person=100000,
        date_friendly=True,
        quiet=True,
        no_wait=True,
        parking_needed=True,
        party_size=2,
    )

    # 4. Travel pairs
    user = LANDMARKS["개포레미안포레스트"]
    gf = LANDMARKS["인하대학교"]
    center = LANDMARKS["복정역"]

    travel_pairs = {}
    for r in restaurants_in_range:
        dest = Coordinates(r.location.lat, r.location.lng)
        ta = TravelInfo(
            origin_name="개포레미안포레스트",
            origin_coords=(user.lat, user.lng),
            departure_time="19:00", mode="car",
            estimated_duration_min=estimate_drive_time_min(user, dest, True),
        )
        tb = TravelInfo(
            origin_name="인하대학교",
            origin_coords=(gf.lat, gf.lng),
            departure_time="18:00", mode="car",
            estimated_duration_min=estimate_drive_time_min(gf, dest, True),
            traffic_notes="경인고속도로→서울 퇴근시간 1.5~2시간",
        )
        travel_pairs[r.name] = (ta, tb)

    # 5. Rank
    print("[3/4] 종합 점수 산출...")
    recommendations = rank_restaurants(restaurants_in_range, constraints, travel_pairs)
    for rec in recommendations[:5]:
        print(f"  #{rec.rank} {rec.restaurant.name_ko} -- 점수: {rec.composite_score}/10 (복정역 {travel_times.get(rec.restaurant.name, '?')}분)")

    # 6. Generate DOCX
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    output_path = os.path.join(output_dir, "맛집추천_2026-04-07_복정역.docx")

    print(f"\n[4/4] DOCX 리포트 생성...")
    search_context = {
        "date": "2026-04-07 (월요일)",
        "cuisine": "관동식 스키야키 / 고퀄리티 이자카야 / 분위기 좋은 일식",
        "budget": "1인 10만원 이하",
        "atmosphere": "조용하고 분위기 좋은 데이트",
        "logistics": [
            "여자친구: 인하대학교(인천 용현동) 18:00 출발, 자차 이동.",
            "퇴근시간(17~19시): 경인고속도로→서울 1.5~2시간 소요.",
            "사용자: 개포레미안포레스트(강남구) 출발.",
            "여자친구 거주지: 위례(송파구).",
            "핵심 제약: 복정역 반경 20분 이내 맛집.",
            "복정역 선정 이유: 위례 인근, 인천→서울 경로 종점, 개포에서도 접근 용이.",
            "여자친구 예상 도착 시간: 19:30~20:00.",
            "추천 예약 시간: 19:30 또는 20:00.",
        ],
    }

    report_path = generate_report(recommendations, constraints, output_path, search_context)
    print(f"  -> 리포트 저장: {report_path}")

    # Summary
    print(f"\n{'=' * 60}")
    print("  최종 추천 (복정역 20분 이내)")
    print("=" * 60)
    for rec in recommendations[:3]:
        r = rec.restaurant
        t = travel_times.get(r.name, "?")
        print(f"\n  #{rec.rank} {r.name_ko} ({r.name})")
        print(f"     분류: {r.category} -- {r.subcategory}")
        print(f"     지역: {r.location.district}")
        print(f"     복정역: ~{t}분")
        print(f"     저녁: {r.price.format_range('dinner')}")
        print(f"     점수: {rec.composite_score}/10")
        print(f"     핵심: {r.pros[0]}")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
