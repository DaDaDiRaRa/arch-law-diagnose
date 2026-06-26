"""review_triggers 회귀 테스트 — 심의/영향평가 임계값 고정.

법규 규모 기준(16층·10만㎡·굴착깊이·세대수 등)이 바뀌면 깨지도록 설계.
"""
from __future__ import annotations

from services.review_triggers import evaluate_reviews
from services import review_triggers as rt


def _sev(items, name):
    return next(x["severity"] for x in items if x["name"] == name)


def _req(**kw):
    base = {"building_use": "업무시설", "site_area": 1000, "total_floor_area": 2000,
            "floors_above": 5, "floors_below": 0, "height": 20, "units": 0}
    base.update(kw)
    return base


# ── 건축위원회 심의 (다중이용·16층·21층) ──────────────────────────────────────
def test_building_committee_16층_required():
    r = rt._eval_building_committee(_req(floors_above=16, total_floor_area=6000), {})
    assert r["severity"] == "REQUIRED"


def test_building_committee_11층_maybe():
    r = rt._eval_building_committee(_req(floors_above=11, total_floor_area=4000), {})
    assert r["severity"] == "MAYBE"


def test_building_committee_small_none():
    r = rt._eval_building_committee(_req(floors_above=5, total_floor_area=2000), {})
    assert r["severity"] == "NONE"


# ── 건축물 안전영향평가 (초고층 / 10만㎡+16층) ────────────────────────────────
def test_building_safety_superhigh_floors():
    assert rt._eval_building_safety(_req(floors_above=50), {})["severity"] == "REQUIRED"


def test_building_safety_superhigh_height():
    assert rt._eval_building_safety(_req(height=200), {})["severity"] == "REQUIRED"


def test_building_safety_large_needs_both():
    # 10만㎡지만 15층 → 2호 미충족(16층 AND 필요) → NONE
    assert rt._eval_building_safety(_req(total_floor_area=100000, floors_above=15), {})["severity"] == "NONE"
    # 10만㎡ + 16층 → REQUIRED
    assert rt._eval_building_safety(_req(total_floor_area=100000, floors_above=16), {})["severity"] == "REQUIRED"


# ── 지하안전영향평가 (굴착 깊이 추정 = 지하층×3.5m) ──────────────────────────
def test_underground_safety_levels():
    assert rt._eval_underground_safety(_req(floors_below=6), {})["severity"] == "REQUIRED"  # 제1종
    assert rt._eval_underground_safety(_req(floors_below=3), {})["severity"] == "REQUIRED"  # 제2종
    assert rt._eval_underground_safety(_req(floors_below=2), {})["severity"] == "MAYBE"
    assert rt._eval_underground_safety(_req(floors_below=1), {})["severity"] == "NONE"


# ── 교통영향평가 ─────────────────────────────────────────────────────────────
def test_traffic_urban_area():
    r = rt._eval_traffic_impact(_req(total_floor_area=50000, address="서울특별시 영등포구"), {})
    assert r["severity"] == "REQUIRED"


def test_traffic_units():
    assert rt._eval_traffic_impact(_req(units=1000), {})["severity"] == "REQUIRED"


def test_traffic_maybe():
    assert rt._eval_traffic_impact(_req(total_floor_area=30000, address="강원도 어딘가"), {})["severity"] == "MAYBE"


# ── 환경영향평가 ─────────────────────────────────────────────────────────────
def test_environmental_large_dev():
    assert rt._eval_environmental(_req(site_area=250000), {"zone_use": "일반상업지역"})["severity"] == "REQUIRED"


def test_environmental_nonurban_small():
    assert rt._eval_environmental(_req(site_area=8000), {"zone_use": "계획관리지역"})["severity"] == "REQUIRED"
    # 도시지역 8000㎡는 대상 아님
    assert rt._eval_environmental(_req(site_area=8000), {"zone_use": "일반상업지역"})["severity"] == "NONE"


# ── 사전재해영향성검토 ───────────────────────────────────────────────────────
def test_disaster_impact():
    assert rt._eval_disaster_impact(_req(site_area=5000), {})["severity"] == "REQUIRED"
    assert rt._eval_disaster_impact(_req(site_area=3000), {})["severity"] == "MAYBE"
    assert rt._eval_disaster_impact(_req(site_area=1000), {})["severity"] == "NONE"


# ── 범죄예방 / 도시계획위원회 ────────────────────────────────────────────────
def test_crime_prevention_use():
    assert rt._eval_crime_prevention(_req(building_use="공동주택"), {})["severity"] == "REQUIRED"
    assert rt._eval_crime_prevention(_req(building_use="단독주택"), {})["severity"] == "NONE"


def test_urban_planning_district():
    r = rt._eval_urban_planning(_req(), {"zone_district": "지구단위계획구역"})
    assert r["severity"] == "REQUIRED"


# ── 진입점 ───────────────────────────────────────────────────────────────────
def test_evaluate_reviews_shape():
    out = evaluate_reviews(_req(floors_above=16, total_floor_area=6000), {})
    assert len(out["items"]) == 11
    assert out["required_count"] >= 1
    assert "maybe_count" in out


def test_evaluate_reviews_no_land():
    out = evaluate_reviews(_req())
    assert len(out["items"]) == 11
