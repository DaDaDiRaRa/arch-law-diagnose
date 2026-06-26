"""multi_parcel 회귀 테스트 — 합필 모드 판정·임계치·가중평균·한도 적용.

국토계획법 §84·시행령 §94의 소규모 예외 임계치(330/660/1000㎡)와 면적 안분 로직을 고정.
zone_limits.json(로컬 config)만 사용 — 외부 API 불필요.
"""
from __future__ import annotations

import pytest

from services import multi_parcel as mp


def _parcels(*areas):
    return [{"address": f"p{i}", "pnu": "", "site_area": a} for i, a in enumerate(areas)]


def _lands(*zones, district="", jur="서울특별시 영등포구"):
    return [{"zone_use": z, "zone_district": district, "jurisdiction_name": jur} for z in zones]


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────
def test_is_urban_zone():
    assert mp._is_urban_zone("제2종일반주거지역") is True
    assert mp._is_urban_zone("일반상업지역") is True
    assert mp._is_urban_zone("계획관리지역") is False
    assert mp._is_urban_zone("농림지역") is False
    assert mp._is_urban_zone("") is True  # 정보 부족 → 보수적으로 도시


def test_roadside_commercial_detect():
    assert mp._is_roadside_commercial("노선상업지역") is True
    assert mp._is_roadside_commercial("일반미관지구") is False


def test_resolve_threshold_urban_vs_nonurban():
    t_urban, _ = mp._resolve_threshold("제2종일반주거지역", ["제2종일반주거지역", "일반상업지역"])
    assert t_urban == mp.THRESHOLD_URBAN_M2  # 330
    t_non, _ = mp._resolve_threshold("농림지역", ["계획관리지역", "농림지역"])
    assert t_non == mp.THRESHOLD_NON_URBAN_M2  # 1000
    t_road, _ = mp._resolve_threshold("근린상업지역", ["일반상업지역", "근린상업지역"],
                                      is_roadside_commercial=True)
    assert t_road == mp.THRESHOLD_ROADSIDE_COMMERCIAL_M2  # 660


# ── aggregate_zones 모드 판정 ────────────────────────────────────────────────
def test_same_zone_mode():
    agg = mp.aggregate_zones(_parcels(500, 300), _lands("제3종일반주거지역", "제3종일반주거지역"))
    assert agg["mode"] == "same_zone"
    assert agg["total_site_area"] == 800.0


def test_small_part_mode_urban():
    """작은 부분 200㎡ ≤ 330(도시) → 소규모 예외, 큰 zone 기준."""
    agg = mp.aggregate_zones(_parcels(5000, 200), _lands("일반상업지역", "제2종일반주거지역"))
    assert agg["mode"] == "small_part"
    assert agg["small_part_zone"] == "제2종일반주거지역"
    # 큰 부분(일반상업) 한도 사용
    assert agg["weighted_far_limit"] == mp._get_zone_limit("일반상업지역", "floor_area_ratio")


def test_weighted_mode_area_average():
    """작은 부분 1000㎡ > 330 → 면적 안분 가중평균."""
    agg = mp.aggregate_zones(_parcels(2000, 1000), _lands("일반상업지역", "제2종일반주거지역"))
    assert agg["mode"] == "weighted"
    f_comm = mp._get_zone_limit("일반상업지역", "floor_area_ratio")
    f_res = mp._get_zone_limit("제2종일반주거지역", "floor_area_ratio")
    expected = round((2000 * f_comm + 1000 * f_res) / 3000, 2)
    assert agg["weighted_far_limit"] == expected


def test_nonurban_uses_larger_threshold():
    """비도시(계획관리+농림) 작은 800㎡ ≤ 1000 → 소규모 예외 (도시였다면 weighted)."""
    agg = mp.aggregate_zones(_parcels(3000, 800), _lands("계획관리지역", "농림지역"))
    assert agg["mode"] == "small_part"
    assert agg["threshold_m2"] == mp.THRESHOLD_NON_URBAN_M2


def test_roadside_commercial_threshold_changes_mode():
    """노선상업 명시 시 임계치 660 → 작은 500㎡가 소규모로 (기본 330이면 weighted)."""
    agg = mp.aggregate_zones(
        _parcels(3000, 500), _lands("일반상업지역", "근린상업지역"),
        is_roadside_commercial=True,
    )
    assert agg["mode"] == "small_part"
    assert agg["threshold_m2"] == mp.THRESHOLD_ROADSIDE_COMMERCIAL_M2


def test_empty_zones_raises():
    with pytest.raises(ValueError):
        mp.aggregate_zones(_parcels(500), _lands(""))


def test_cross_jurisdiction_flag():
    agg = mp.aggregate_zones(
        _parcels(500, 500),
        [{"zone_use": "일반상업지역", "zone_district": "", "jurisdiction_name": "서울특별시 영등포구"},
         {"zone_use": "제2종일반주거지역", "zone_district": "", "jurisdiction_name": "경기도 성남시"}],
    )
    assert agg["cross_jurisdiction"] is True


# ── apply_weighted_limits ────────────────────────────────────────────────────
def _diag(actual_far):
    return {
        "results": {
            "용적률": {"actual_pct": actual_far, "limit_pct": 999, "pass": True,
                       "score": 9.0, "confidence": 5},
            "건폐율": {"actual_pct": 50, "limit_pct": 60, "pass": True, "score": 9.0, "confidence": 5},
        },
        "overall_score": 9.0, "signal": "GREEN", "risks": [], "warnings": [],
    }


def test_apply_weighted_overrides_and_fails():
    agg = {"mode": "weighted", "weighted_far_limit": 450.0, "weighted_coverage_limit": 60.0,
           "zone_breakdown": [{"zone": "일반상업지역", "area": 2000, "far_limit": 800, "coverage_limit": 60},
                              {"zone": "제2종일반주거지역", "area": 1000, "far_limit": 250, "coverage_limit": 60}]}
    out = mp.apply_weighted_limits(_diag(500), agg)
    far = out["results"]["용적률"]
    assert far["limit_pct"] == 450.0
    assert far["pass"] is False           # 500 > 450
    assert far["excess_pct"] == 50.0
    assert far["score"] == 0.0
    assert out["signal"] == "RED"


def test_apply_weighted_same_zone_noop():
    d = _diag(500)
    out = mp.apply_weighted_limits(d, {"mode": "same_zone"})
    assert out["results"]["용적률"]["limit_pct"] == 999  # 변경 없음
