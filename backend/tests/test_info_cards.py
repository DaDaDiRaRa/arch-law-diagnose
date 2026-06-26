"""정보 카드 계산기 회귀 테스트 — 범죄예방 건축기준 대상 분류."""
from __future__ import annotations

from services.calculator import crime_prevention as cp


def test_crime_target_use():
    target = next(iter(cp._TARGET_USES))
    r = cp.calculate(building_use=target)
    assert r["pass"] is None        # 대상 → 체크리스트(확인필요)
    assert r["score"] == 5.0
    assert r["checks"]


def test_crime_non_target_use():
    r = cp.calculate(building_use="창고시설")
    assert r["pass"] is True
    assert r["score"] == 10.0
    assert r["checks"] == []
