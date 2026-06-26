"""calculator/height 회귀 테스트 — §60 가로구역·§61/§86 정북 일조 사선 자동 판정."""
from __future__ import annotations

from services.calculator import height

RES = "제2종일반주거지역"   # 일조 사선 적용(일반주거)
COMM = "일반상업지역"        # 사선 미적용


def test_street_block_height_violation():
    r = height.calculate(height=40, floors_above=12, zone_use=COMM, street_block_max_height_m=35)
    assert r["pass"] is False
    assert r["score"] == 0


def test_street_block_height_ok_commercial():
    r = height.calculate(height=30, floors_above=10, zone_use=COMM, street_block_max_height_m=35)
    assert r["pass"] is True  # 가로구역 이하 + 상업(사선 미적용)


def test_commercial_no_shadow():
    r = height.calculate(height=50, floors_above=15, zone_use=COMM)
    assert r["shadow_applies"] is False
    assert r["pass"] is True


def test_residential_setback_sufficient_low():
    # 높이 10m 이하 → 필요 이격 1.5m
    r = height.calculate(height=9, floors_above=3, zone_use=RES, north_setback_m=2.0)
    assert r["shadow_min_setback_m"] == 1.5
    assert r["pass"] is True


def test_residential_setback_insufficient_high():
    # 높이 20m → 필요 이격 10m (height/2)
    r = height.calculate(height=20, floors_above=6, zone_use=RES, north_setback_m=5.0)
    assert r["shadow_min_setback_m"] == 10.0
    assert r["pass"] is False


def test_residential_no_setback_manual_review():
    r = height.calculate(height=15, floors_above=5, zone_use=RES)
    assert r["pass"] is None
    assert r["needs_manual_review"] is True


def test_exemption_road_20m():
    r = height.calculate(height=15, floors_above=5, zone_use=RES, road_20m_adjacent=True)
    assert r["pass"] is True
    assert any("20m" in e for e in r["exemptions"])


def test_exemption_north_nonresidential():
    r = height.calculate(height=15, floors_above=5, zone_use=RES, adjacent_zone_north="일반상업지역")
    assert r["pass"] is True
    assert r["exemptions"]
