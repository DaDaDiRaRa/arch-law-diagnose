"""국토계획법 시행령 제94조 임계치 정밀화 테스트.

도시지역 330 / 비도시 1000 / 노선상업 660 분기 검증.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from services.multi_parcel import aggregate_zones


def _parcels(*sizes):
    return [{"address": f"P{i}", "pnu": "", "site_area": s} for i, s in enumerate(sizes)]


def _lands(*zones, district=""):
    return [{"zone_use": z, "zone_district": district, "jurisdiction_name": "서울특별시"} for z in zones]


def main():
    # === 케이스 1: 도시지역 + 도시지역 — 작은 부분 300㎡ → 소규모 예외 (330 이하) ===
    print("=== 1) 도시지역 + 도시지역, 작은 부분 300㎡ ===")
    agg = aggregate_zones(
        _parcels(700, 300),
        _lands("제2종일반주거지역", "일반상업지역"),
    )
    print(f"   mode={agg['mode']} | threshold={agg['threshold_m2']} | basis={agg['threshold_basis']}")
    print(f"   calc: {agg['calc_method']}")
    assert agg["mode"] == "small_part"
    assert agg["threshold_m2"] == 330.0

    # === 케이스 2: 도시지역 + 도시지역 — 작은 부분 400㎡ → 가중평균 (330 초과) ===
    print("\n=== 2) 도시지역 + 도시지역, 작은 부분 400㎡ ===")
    agg = aggregate_zones(
        _parcels(700, 400),
        _lands("제2종일반주거지역", "일반상업지역"),
    )
    print(f"   mode={agg['mode']} | threshold={agg['threshold_m2']}")
    print(f"   weighted_far={agg['weighted_far_limit']} | weighted_cov={agg['weighted_coverage_limit']}")
    assert agg["mode"] == "weighted"
    assert agg["threshold_m2"] == 330.0

    # === 케이스 3: 비도시지역 + 비도시지역 — 작은 부분 900㎡ → 소규모 예외 (1000 이하) ===
    print("\n=== 3) 비도시지역 혼합, 작은 부분 900㎡ ===")
    agg = aggregate_zones(
        _parcels(2000, 900),
        _lands("계획관리지역", "보전관리지역"),
    )
    print(f"   mode={agg['mode']} | threshold={agg['threshold_m2']} | basis={agg['threshold_basis']}")
    assert agg["mode"] == "small_part"
    assert agg["threshold_m2"] == 1000.0

    # === 케이스 4: 비도시지역 + 비도시지역 — 작은 부분 1100㎡ → 가중평균 ===
    print("\n=== 4) 비도시지역 혼합, 작은 부분 1100㎡ ===")
    agg = aggregate_zones(
        _parcels(2000, 1100),
        _lands("계획관리지역", "농림지역"),
    )
    print(f"   mode={agg['mode']} | threshold={agg['threshold_m2']}")
    assert agg["mode"] == "weighted"
    assert agg["threshold_m2"] == 1000.0

    # === 케이스 5: 노선상업지역 명시 — 작은 부분 500㎡ → 소규모 예외 (660 이하) ===
    print("\n=== 5) 노선상업지역(도로변 띠), 작은 부분 500㎡ ===")
    agg = aggregate_zones(
        _parcels(1500, 500),
        _lands("제2종일반주거지역", "일반상업지역", district="노선상업지역"),
    )
    print(f"   mode={agg['mode']} | threshold={agg['threshold_m2']} | basis={agg['threshold_basis']}")
    assert agg["mode"] == "small_part"
    assert agg["threshold_m2"] == 660.0

    # === 케이스 6: 노선상업 명시 + 작은 부분 700㎡ → 가중평균 ===
    print("\n=== 6) 노선상업지역, 작은 부분 700㎡ ===")
    agg = aggregate_zones(
        _parcels(1500, 700),
        _lands("제2종일반주거지역", "일반상업지역", district="노선상업지역"),
    )
    print(f"   mode={agg['mode']} | threshold={agg['threshold_m2']}")
    assert agg["mode"] == "weighted"
    assert agg["threshold_m2"] == 660.0

    # === 케이스 7: 도시 + 비도시 혼재 — 작은 부분이 비도시(800㎡) → 1000 적용 → 소규모 예외 ===
    print("\n=== 7) 도시(주거)+비도시(관리) 혼재, 작은 부분 800㎡(관리) ===")
    agg = aggregate_zones(
        _parcels(2000, 800),
        _lands("제2종일반주거지역", "계획관리지역"),
    )
    print(f"   mode={agg['mode']} | threshold={agg['threshold_m2']} | basis={agg['threshold_basis']}")
    assert agg["threshold_m2"] == 1000.0
    assert agg["mode"] == "small_part"

    # === 케이스 8: 동일 용도지역 단순 합산 ===
    print("\n=== 8) 동일 용도지역 합산 ===")
    agg = aggregate_zones(
        _parcels(500, 300),
        _lands("제2종일반주거지역", "제2종일반주거지역"),
    )
    print(f"   mode={agg['mode']} | primary={agg['primary_zone']} | total={agg['total_site_area']}")
    assert agg["mode"] == "same_zone"
    assert agg["total_site_area"] == 800.0
    assert agg["threshold_m2"] is None  # same_zone 모드는 임계치 비교 안 함

    print("\n✅ 8개 케이스 모두 통과")


if __name__ == "__main__":
    main()
