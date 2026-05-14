"""8개 심의 자동 트리거 룰 테스트."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from services.review_triggers import evaluate_reviews


def show(req, land, title):
    print(f"=== {title} ===")
    out = evaluate_reviews(req, land)
    print(f"  REQUIRED: {out['required_count']}건 | MAYBE: {out['maybe_count']}건")
    for it in out["items"]:
        icon = {"REQUIRED": "🔴", "MAYBE": "🟡", "NONE": "  "}[it["severity"]]
        reasons = "; ".join(it["triggered_reasons"]) if it["triggered_reasons"] else "—"
        print(f"  {icon} {it['name']}: {reasons}")
    print()


# 케이스 1: 소규모 다세대주택 (5층, 1500㎡) — 거의 무트리거
show(
    req={
        "address": "서울특별시 강서구 등촌동 580",
        "building_use": "다세대주택",
        "site_area": 500,
        "total_floor_area": 1500,
        "floors_above": 5,
        "height": 15,
        "units": 12,
    },
    land={"zone_use": "제2종일반주거지역", "zone_district": ""},
    title="1) 소규모 다세대 (5F, 1,500㎡)",
)

# 케이스 2: 중간 규모 — 12층 오피스, 18000㎡
show(
    req={
        "address": "서울특별시 영등포구 여의도동 12",
        "building_use": "업무시설",
        "site_area": 1500,
        "total_floor_area": 18000,
        "floors_above": 12,
        "height": 50,
    },
    land={"zone_use": "일반상업지역", "zone_district": ""},
    title="2) 중간 오피스 (12F, 18,000㎡)",
)

# 케이스 3: 대규모 다중이용 — 18층 호텔, 6만㎡
show(
    req={
        "address": "서울특별시 중구 명동",
        "building_use": "관광숙박시설",
        "site_area": 4000,
        "total_floor_area": 60000,
        "floors_above": 18,
        "height": 72,
    },
    land={"zone_use": "중심상업지역", "zone_district": ""},
    title="3) 대규모 호텔 (18F, 60,000㎡)",
)

# 케이스 4: 초고층 분양 — 21층, 11만㎡, 1200세대
show(
    req={
        "address": "서울특별시 강남구 역삼동",
        "building_use": "공동주택",
        "site_area": 6000,
        "total_floor_area": 110000,
        "floors_above": 35,
        "height": 110,
        "units": 1200,
    },
    land={"zone_use": "제3종일반주거지역", "zone_district": ""},
    title="4) 초고층 아파트 (35F, 1,200세대)",
)

# 케이스 5: 지구단위계획 + 경관지구
show(
    req={
        "address": "서울특별시 성동구",
        "building_use": "공동주택",
        "site_area": 3000,
        "total_floor_area": 25000,
        "floors_above": 10,
        "height": 32,
    },
    land={
        "zone_use": "제2종일반주거지역",
        "zone_district": "지구단위계획구역, 경관지구",
    },
    title="5) 지구단위 + 경관지구 (10F, 25,000㎡)",
)

# 케이스 6: 비도시 + 큰 사이트 — 환경영향평가
show(
    req={
        "address": "경기도 양평군",
        "building_use": "근린생활시설",
        "site_area": 12000,
        "total_floor_area": 3500,
        "floors_above": 3,
        "height": 12,
    },
    land={"zone_use": "계획관리지역", "zone_district": ""},
    title="6) 계획관리지역 12,000㎡ (소규모환경영향평가)",
)

print("✅ 6개 케이스 출력 완료 — 룰 정확성은 사용자 시나리오로 검증 권장")
