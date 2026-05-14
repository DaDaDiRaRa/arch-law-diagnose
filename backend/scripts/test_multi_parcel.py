"""multi_parcel 모듈 단위 검증."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.multi_parcel import aggregate_zones, apply_weighted_limits


def show(title, result):
    print(f"\n=== {title} ===")
    print(f"  mode: {result['mode']}")
    print(f"  primary_zone: {result['primary_zone']}")
    print(f"  total_area: {result['total_site_area']}㎡")
    print(f"  cov_limit: {result['weighted_coverage_limit']}%")
    print(f"  far_limit: {result['weighted_far_limit']}%")
    if result["small_part_zone"]:
        print(f"  small_part: {result['small_part_zone']}")
    print(f"  cross_jurisdiction: {result['cross_jurisdiction']}")
    print(f"  calc_method: {result['calc_method']}")
    print("  breakdown:")
    for b in result["zone_breakdown"]:
        print(f"    - {b['zone']:20s} {b['area']:7.1f}㎡ ({b['area_ratio']*100:5.2f}%) "
              f"건폐 {b['coverage_limit']}% / 용적 {b['far_limit']}%")


# 케이스 1: 동일 용도지역
r1 = aggregate_zones(
    parcels=[
        {"site_area": 500},
        {"site_area": 300},
    ],
    lands=[
        {"zone_use": "일반상업지역", "jurisdiction_name": "서울특별시 강남구"},
        {"zone_use": "일반상업지역", "jurisdiction_name": "서울특별시 강남구"},
    ],
)
show("케이스 1 — 동일 용도지역 (단순 합산)", r1)
assert r1["mode"] == "same_zone"

# 케이스 2: 다른 zone, 작은 부분 300㎡ (≤330)
r2 = aggregate_zones(
    parcels=[
        {"site_area": 1000},
        {"site_area": 300},
    ],
    lands=[
        {"zone_use": "일반상업지역", "jurisdiction_name": "서울특별시 강남구"},
        {"zone_use": "제2종일반주거지역", "jurisdiction_name": "서울특별시 강남구"},
    ],
)
show("케이스 2 — 소규모 예외 (작은 부분 300㎡ ≤ 330)", r2)
assert r2["mode"] == "small_part"
assert r2["primary_zone"] == "일반상업지역"
assert r2["weighted_coverage_limit"] == 80  # 일반상업 건폐 80% 적용

# 케이스 3: 다른 zone, 둘 다 큰 부분 (면적 안분)
r3 = aggregate_zones(
    parcels=[
        {"site_area": 400},
        {"site_area": 600},
    ],
    lands=[
        {"zone_use": "일반상업지역", "jurisdiction_name": "서울특별시 강남구"},
        {"zone_use": "제2종일반주거지역", "jurisdiction_name": "서울특별시 강남구"},
    ],
)
show("케이스 3 — 면적 안분 (400+600, 가중평균)", r3)
assert r3["mode"] == "weighted"
# 건폐: (400*80 + 600*60) / 1000 = (32000+36000)/1000 = 68%
# 용적: (400*1300 + 600*250) / 1000 = (520000+150000)/1000 = 670%
expected_cov = (400 * 80 + 600 * 60) / 1000
expected_far = (400 * 1300 + 600 * 250) / 1000
print(f"\n  검증 — 기대 건폐 {expected_cov}% / 실제 {r3['weighted_coverage_limit']}%")
print(f"  검증 — 기대 용적 {expected_far}% / 실제 {r3['weighted_far_limit']}%")
assert abs(r3["weighted_coverage_limit"] - expected_cov) < 0.01
assert abs(r3["weighted_far_limit"] - expected_far) < 0.01

# 케이스 4: 시·도 다름 (서울+경기)
r4 = aggregate_zones(
    parcels=[
        {"site_area": 500},
        {"site_area": 500},
    ],
    lands=[
        {"zone_use": "제2종일반주거지역", "jurisdiction_name": "서울특별시 강남구"},
        {"zone_use": "제3종일반주거지역", "jurisdiction_name": "경기도 성남시 분당구"},
    ],
)
show("케이스 4 — 시·도 다름 (서울+경기, 안분)", r4)
assert r4["cross_jurisdiction"] is True
assert "서울특별시" in r4["jurisdictions"]
assert "경기도" in r4["jurisdictions"]


# ── apply_weighted_limits 검증 ───────────────────────────────────────────
print("\n\n=== apply_weighted_limits 검증 ===")
fake_diag = {
    "results": {
        "건폐율": {
            "category": "건폐율", "actual_pct": 65.0, "limit_pct": 80,
            "pass": True, "excess_pct": 0, "score": 8.5, "confidence": 5,
            "source": "국토계획법", "notes": "기존 노트",
        },
        "용적률": {
            "category": "용적률", "actual_pct": 500.0, "limit_pct": 1300,
            "pass": True, "excess_pct": 0, "score": 10.0, "confidence": 5,
            "source": "국토계획법", "notes": "기존 노트",
        },
    },
    "overall_score": 9.0,
    "signal": "GREEN",
}

apply_weighted_limits(fake_diag, r3)
cov = fake_diag["results"]["건폐율"]
far = fake_diag["results"]["용적률"]
print(f"  건폐율 → 한도 {cov['limit_pct']}% (기대 68%), pass={cov['pass']}, score={cov['score']}")
print(f"  용적률 → 한도 {far['limit_pct']}% (기대 670%), pass={far['pass']}, score={far['score']}")
print(f"  signal={fake_diag['signal']}, overall={fake_diag['overall_score']}")
print(f"  cov notes: {cov['notes'][:80]}...")
assert abs(cov["limit_pct"] - 68) < 0.01
assert cov["pass"] is False  # 65 > 68 인 줄 알았는데 65 ≤ 68 이라 적합!  잠깐...
# 65 ≤ 68 이라 적합이 맞음
assert cov["pass"] is True
assert far["pass"] is True  # 500 ≤ 670

print("\n✅ 모든 케이스 통과")
