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


# ── 교통영향평가 — 용도별 임계값(시행령 별표1, 법제처 PDF 검증) ────────────────
def test_traffic_office_25000_threshold():
    """업무시설(오피스텔 포함) 도시교통정비지역 임계 25,000㎡ — 과거 50,000 오류 정정.

    실 사례(오피스텔 47,629㎡)가 교통영향평가를 거쳤으나 과거 엔진은 MAYBE 였다.
    """
    r = rt._eval_traffic_impact(
        _req(building_use="오피스텔", total_floor_area=47629, address="서울특별시"), {})
    assert r["severity"] == "REQUIRED"
    # 24,000㎡ 업무시설(서울) → 임계 미만이나 80% 근접 → MAYBE
    r2 = rt._eval_traffic_impact(
        _req(building_use="업무시설", total_floor_area=24000, address="서울특별시"), {})
    assert r2["severity"] == "MAYBE"
    # 10,000㎡ 업무시설(서울) → NONE
    r3 = rt._eval_traffic_impact(
        _req(building_use="업무시설", total_floor_area=10000, address="서울특별시"), {})
    assert r3["severity"] == "NONE"


def test_traffic_use_specific_thresholds():
    """용도별로 임계가 다름 — 숙박 40,000 vs 업무 25,000(도시교통정비지역)."""
    assert rt._eval_traffic_impact(
        _req(building_use="숙박시설", total_floor_area=30000, address="서울특별시"), {})["severity"] == "NONE"
    assert rt._eval_traffic_impact(
        _req(building_use="업무시설", total_floor_area=30000, address="서울특별시"), {})["severity"] == "REQUIRED"


def test_traffic_region_column_for_non_urban():
    """비도시교통정비지역(교통권역)은 1.5배 임계 적용 — 업무 37,500㎡."""
    assert rt._eval_traffic_impact(
        _req(building_use="업무시설", total_floor_area=37500, address="강원도 어딘가"), {})["severity"] == "REQUIRED"
    assert rt._eval_traffic_impact(
        _req(building_use="업무시설", total_floor_area=26000, address="강원도 어딘가"), {})["severity"] == "NONE"


# ── 환경영향평가 ─────────────────────────────────────────────────────────────
def test_environmental_large_dev():
    assert rt._eval_environmental(_req(site_area=250000), {"zone_use": "일반상업지역"})["severity"] == "REQUIRED"


def test_environmental_nonurban_small():
    # 보전관리지역: 별표4 기준 5,000㎡ 이상 → REQUIRED
    assert rt._eval_environmental(_req(site_area=5500), {"zone_use": "보전관리지역"})["severity"] == "REQUIRED"
    # 계획관리지역: 별표4 기준 10,000㎡ 이상 (8,000㎡는 미달 → NONE)
    assert rt._eval_environmental(_req(site_area=8000), {"zone_use": "계획관리지역"})["severity"] == "NONE"
    assert rt._eval_environmental(_req(site_area=11000), {"zone_use": "계획관리지역"})["severity"] == "REQUIRED"
    # 도시지역 기타(일반상업): 60,000㎡ 미만 → NONE
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


# ── 교육환경평가 ─────────────────────────────────────────────────────────────
def test_education_degrade_none_returns_maybe():
    """nearby_schools=None → API 미조회 degrade → MAYBE."""
    r = rt._eval_education(_req(), {}, nearby_schools=None)
    assert r["severity"] == "MAYBE"


def test_education_no_schools_returns_none():
    """nearby_schools=[] → 200m 내 학교 없음 → NONE."""
    r = rt._eval_education(_req(), {}, nearby_schools=[])
    assert r["severity"] == "NONE"


def test_education_absolute_zone():
    """학교가 50m 이내 → 절대보호구역 → REQUIRED."""
    schools = [{"name": "영등포초등학교", "distance_m": 30, "address": ""}]
    r = rt._eval_education(_req(building_use="업무시설"), {}, nearby_schools=schools)
    assert r["severity"] == "REQUIRED"
    assert "절대보호구역" in r["triggered_reasons"][0]


def test_education_relative_zone_restricted_use():
    """학교가 50~200m + 숙박 용도 → 상대보호구역 + 제한용도 → REQUIRED."""
    schools = [{"name": "영등포중학교", "distance_m": 120, "address": ""}]
    r = rt._eval_education(_req(building_use="숙박시설"), {}, nearby_schools=schools)
    assert r["severity"] == "REQUIRED"
    assert "상대보호구역" in r["triggered_reasons"][0]


def test_education_relative_zone_non_restricted_use():
    """학교가 50~200m + 업무시설 → 상대보호구역이지만 제한용도 아님 → MAYBE."""
    schools = [{"name": "영등포고등학교", "distance_m": 150, "address": ""}]
    r = rt._eval_education(_req(building_use="업무시설"), {}, nearby_schools=schools)
    assert r["severity"] == "MAYBE"


# ── 문화재 현상변경 ──────────────────────────────────────────────────────────
def test_heritage_degrade_text_signal():
    """nearby_heritages=None + 지역지구 단서 있음 → degrade → REQUIRED."""
    r = rt._eval_cultural_heritage(_req(), {"zone_district": "역사문화환경보존지역"})
    assert r["severity"] == "REQUIRED"


def test_heritage_degrade_no_signal():
    """nearby_heritages=None + 단서 없음 → degrade → MAYBE."""
    r = rt._eval_cultural_heritage(_req(), {}, nearby_heritages=None)
    assert r["severity"] == "MAYBE"


def test_heritage_api_found():
    """nearby_heritages 있음 → API 확인 → REQUIRED."""
    heritages = [{"name": "영등포 사적지", "heritage_type": "11", "distance_m": 280}]
    r = rt._eval_cultural_heritage(_req(), {}, nearby_heritages=heritages)
    assert r["severity"] == "REQUIRED"
    assert "500m" in r["triggered_reasons"][0]


def test_heritage_api_empty_no_signal():
    """nearby_heritages=[] + 단서 없음 → NONE."""
    r = rt._eval_cultural_heritage(_req(), {}, nearby_heritages=[])
    assert r["severity"] == "NONE"


def test_heritage_api_empty_with_signal():
    """nearby_heritages=[] but 지역지구 단서 있음 → REQUIRED (텍스트 단서 우선)."""
    r = rt._eval_cultural_heritage(
        _req(), {"zone_district": "역사문화환경보존지역"}, nearby_heritages=[]
    )
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


def test_evaluate_reviews_nearby_params_forwarded():
    """evaluate_reviews에 nearby 파라미터 전달 시 교육환경 결과에 반영."""
    out_none = evaluate_reviews(_req(), {}, nearby_schools=None)
    out_empty = evaluate_reviews(_req(), {}, nearby_schools=[])
    edu_none = next(x for x in out_none["items"] if x["name"] == "교육환경평가")
    edu_empty = next(x for x in out_empty["items"] if x["name"] == "교육환경평가")
    assert edu_none["severity"] == "MAYBE"
    assert edu_empty["severity"] == "NONE"
