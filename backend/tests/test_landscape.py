"""calculator/landscape 회귀 테스트 — §27 면제 분기·의무비율·옥상조경 인정."""
from __future__ import annotations

from services.calculator import landscape

RES = "제2종일반주거지역"


def test_exempt_green_zone():
    r = landscape.calculate(None, 1000, "자연녹지지역", "업무시설")
    assert r["exempt"] is True
    assert r["pass"] is True


def test_exempt_management_zone():
    r = landscape.calculate(None, 1000, "농림지역", "업무시설")
    assert r["exempt"] is True


def test_exempt_chuksa():
    r = landscape.calculate(None, 1000, RES, "축사")
    assert r["exempt"] is True


def test_exempt_small_factory():
    r = landscape.calculate(None, 3000, RES, "공장")  # < 5000㎡
    assert r["exempt"] is True


def test_exempt_below_200():
    r = landscape.calculate(None, 150, RES, "업무시설")
    assert r["exempt"] is True


def test_200_to_300_fixed_10pct():
    """200~300㎡ 대지는 시행령 직접 명시 10% (조례 변경 불가)."""
    r = landscape.calculate(50, 250, RES, "업무시설")
    assert r["required_pct"] == 10.0
    assert r["exempt"] is False


def test_override_fail():
    r = landscape.calculate(100, 1000, RES, "업무시설", limit_override=15.0)
    assert r["required_pct"] == 15.0
    assert r["required_area_m2"] == 150.0
    assert r["pass"] is False  # 100㎡ = 10% < 15%


def test_override_pass():
    r = landscape.calculate(200, 1000, RES, "업무시설", limit_override=15.0)
    assert r["pass"] is True   # 200㎡ = 20% ≥ 15%


def test_rooftop_credit_capped():
    """옥상조경 2/3 인정, 의무면적 50% 상한."""
    # site 1000, 의무 10% → 의무면적 100㎡. 지상 50 + 옥상 90.
    # 옥상 credit = min(90*2/3=60, cap 100*0.5=50) = 50 → 유효 100㎡ = 10% → pass
    r = landscape.calculate(50, 1000, RES, "업무시설", limit_override=10.0, rooftop_landscape_area=90)
    assert r["rooftop_credit_m2"] == 50.0
    assert r["pass"] is True
