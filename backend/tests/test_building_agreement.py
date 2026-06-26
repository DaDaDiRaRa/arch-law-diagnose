"""building_agreement 회귀 테스트 — §110의7 협정 완화(1.2배 / 조경 0.8배) + 법정 캡."""
from __future__ import annotations

from services import building_agreement as ba

RES = "제2종일반주거지역"


def test_coverage_not_applied():
    r = {"limit_pct": 60, "actual_pct": 50}
    out = ba.apply_to_coverage(r, applied=False, zone_use=RES)
    assert "agreement_applied" not in out


def test_coverage_limit_none():
    out = ba.apply_to_coverage({"limit_pct": None}, applied=True, zone_use=RES)
    assert "agreement_applied" not in out


def test_coverage_applied_with_legal_cap():
    cap = ba._zone_cap("building_coverage_ratio", RES)
    base = cap - 5            # base*1.2 가 캡 초과하도록
    r = {"limit_pct": base, "actual_pct": 40}
    out = ba.apply_to_coverage(r, applied=True, zone_use=RES)
    assert out["agreement_applied"] is True
    assert out["limit_pct"] == round(min(base * 1.2, cap), 2)
    assert out["pass"] is True  # 40 ≤ 한도


def test_far_applied_not_capped():
    cap = ba._zone_cap("floor_area_ratio", RES)
    base = cap / 2            # 1.2배 해도 캡 미만
    r = {"limit_pct": base, "actual_pct": 0}
    out = ba.apply_to_far(r, applied=True, zone_use=RES)
    assert out["limit_pct"] == round(base * 1.2, 2)
    assert out["agreement_applied"] is True


def test_landscape_requires_road_facing():
    r = {"required_pct": 15, "required_area_m2": 150, "exempt": False}
    out = ba.apply_to_landscape(r, applied=True, road_facing_integrated=False)
    assert out["required_pct"] == 15  # 변경 없음 (안내만)
    assert "agreement_applied" not in out


def test_landscape_relief_08x():
    r = {"required_pct": 15, "required_area_m2": 150, "exempt": False}
    out = ba.apply_to_landscape(r, applied=True, road_facing_integrated=True)
    assert out["required_pct"] == 12.0   # 15 * 0.8
    assert out["agreement_applied"] is True


def test_landscape_exempt_unchanged():
    r = {"required_pct": 0, "exempt": True}
    out = ba.apply_to_landscape(r, applied=True, road_facing_integrated=True)
    assert out.get("agreement_applied") is None


def test_height_requires_wide_road():
    r = {"street_block_max_height_m": 30, "actual_height_m": 32, "pass": False, "score": 0}
    out = ba.apply_to_height(r, applied=True, road_width=4.0)  # < 6m
    assert "agreement_applied" not in out


def test_height_relief_12x():
    r = {"street_block_max_height_m": 30, "actual_height_m": 32, "pass": False, "score": 0}
    out = ba.apply_to_height(r, applied=True, road_width=8.0)
    assert out["street_block_max_height_m"] == 36.0  # 30 * 1.2
    assert out["pass"] is True  # 32 ≤ 36
    assert out["agreement_applied"] is True
