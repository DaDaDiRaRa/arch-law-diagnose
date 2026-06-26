"""계산기 순수 함수 회귀 테스트 — 외부 API·설정 의존 없이 결정론적으로 동작.

건폐율·용적률·주차·용도지역 정규화의 경계값과 None 처리를 고정한다.
법령 임계값이 바뀌면 의도적으로 깨지도록 설계 (회귀 안전망).
"""
from __future__ import annotations

import pytest

from services.calculator import coverage, far, parking
from services import zone_use_normalizer as zn


# ─── 건폐율 ──────────────────────────────────────────────────────────────────
def test_coverage_pass_boundary():
    """실제 == 한도 → 적합(경계 포함)."""
    r = coverage.calculate(building_area=600, site_area=1000, zone_use="준공업지역",
                           limit_override=60.0)
    assert r["actual_pct"] == 60.0
    assert r["pass"] is True
    assert r["excess_pct"] == 0.0


def test_coverage_fail_over_limit():
    r = coverage.calculate(building_area=700, site_area=1000, zone_use="준공업지역",
                           limit_override=60.0)
    assert r["pass"] is False
    assert r["excess_pct"] == 10.0
    assert r["score"] == 0.0


def test_coverage_zero_site_area_no_crash():
    """대지면적 0 → ZeroDivision 없이 actual 0%, pass=True."""
    r = coverage.calculate(building_area=500, site_area=0, zone_use="준공업지역",
                           limit_override=60.0)
    assert r["actual_pct"] == 0.0
    assert r["pass"] is True


def test_coverage_unknown_zone_returns_none():
    """매칭 불가 용도지역 + override 없음 → pass=None(확인필요)."""
    r = coverage.calculate(building_area=500, site_area=1000, zone_use="존재하지않는지역")
    assert r["pass"] is None


# ─── 용적률 ──────────────────────────────────────────────────────────────────
def test_far_pass_boundary():
    r = far.calculate(floor_area_above=4000, site_area=1000, zone_use="준공업지역",
                      limit_override=400.0)
    assert r["actual_pct"] == 400.0
    assert r["pass"] is True


def test_far_fail_over_limit():
    r = far.calculate(floor_area_above=5000, site_area=1000, zone_use="준공업지역",
                      limit_override=400.0)
    assert r["pass"] is False
    assert r["score"] == 0.0


def test_far_zero_site_area_no_crash():
    r = far.calculate(floor_area_above=4000, site_area=0, zone_use="준공업지역",
                      limit_override=400.0)
    assert r["actual_pct"] == 0.0


# ─── 주차 ────────────────────────────────────────────────────────────────────
def test_parking_no_provided_returns_none():
    """계획 대수 미입력 → pass=None(법정 최소만 산정)."""
    r = parking.calculate(building_use="업무시설", total_floor_area=4000)
    assert r["pass"] is None
    assert r["provided_spaces"] is None
    assert r["required_spaces"] is not None


def test_parking_unit_based_without_units_returns_none():
    """공동주택인데 세대수 미입력 → 면적기반 오계산 대신 pass=None."""
    r = parking.calculate(building_use="아파트", total_floor_area=10000)
    assert r["pass"] is None
    assert r["confidence"] == 2


def test_parking_sufficient_passes():
    r = parking.calculate(building_use="업무시설", total_floor_area=4000, provided_spaces=999)
    assert r["pass"] is True
    assert r["deficit"] == 0


# ─── 용도지역 정규화 ────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw,expected", [
    ("준공업지역", "준공업지역"),          # 정확 매칭
    ("준공업", "준공업지역"),              # 별칭(접미사 생략)
    ("3종일반주거", "제3종일반주거지역"),    # 별칭(접두·접미 생략)
    ("서울특별시 제1종일반주거지역", "제1종일반주거지역"),  # 부분 일치
])
def test_normalize_known(raw, expected):
    assert zn.normalize(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   ", "알수없는지역", "주거지역"])
def test_normalize_ambiguous_returns_none(raw):
    """비었거나 모호한 입력(예: 종 미상 '주거지역')은 None → 확인필요."""
    assert zn.normalize(raw) is None


def test_category_of_specific_wins():
    assert zn.category_of("제1종전용주거지역") == "전용주거"
    assert zn.category_of("제3종일반주거지역") == "일반주거"
    assert zn.category_of("중심상업지역") == "상업"
