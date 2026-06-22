"""사전 사업성 검토 엔진 — DiagnoseEngine wrapper.

전략:
  1. 사용자 공모 요구치(target_*)를 검증 엔진의 "actual" 값으로 변환
  2. DiagnoseEngine.run() 호출 (단일 소스 — 법령·조례·완화 로직 재사용)
  3. 결과를 갭 분석 형태로 후처리

검증 모드와의 차이:
  - 검증: pass/fail 가중평균 → GREEN/YELLOW/RED
  - 사업성: 공모 요구치 vs 법적 한계 갭 → 참여/협상/패스 권장
"""
from __future__ import annotations

import logging
from typing import Any

from services.calculator import parking
from services.diagnose_engine import (
    DiagnoseEngine,
    _get_default_cov_limit,
    _get_default_far_limit,
)
from services.far_relief import compute_relief

logger = logging.getLogger(__name__)


# ── 갭 카테고리 정의 ────────────────────────────────────────────────────────
# (target_field, engine_result_key, engine_limit_key, unit, semantic)
# semantic: "max" (target ≤ limit이면 OK) / "min" (target ≥ limit이면 OK)
_GAP_SPECS = [
    {
        "key": "building_coverage",
        "label": "건폐율",
        "target_field": "target_building_coverage_pct",
        "engine_category": "건폐율",
        "limit_key": "limit_pct",
        "unit": "%",
        "semantic": "max",
    },
    {
        "key": "far",
        "label": "용적률",
        "target_field": "target_far_pct",
        "engine_category": "용적률",
        "limit_key": "limit_pct",
        "unit": "%",
        "semantic": "max",
    },
    {
        "key": "parking",
        "label": "주차",
        "target_field": "target_parking_count",
        "engine_category": "주차",
        "limit_key": "required_spaces",
        "unit": "대",
        "semantic": "min",  # 공모요구가 법정최소 이상이면 OK
    },
]


def _to_float(v: Any, default: float | None = None) -> float | None:
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _to_int(v: Any, default: int | None = None) -> int | None:
    if v is None or v == "":
        return default
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _build_engine_payload(req: dict, site_area: float) -> dict:
    """사업성 입력 → 검증 엔진 입력으로 변환.

    공모 요구치를 엔진의 actual 값으로 박는다.
    누락 필드는 엔진이 돌도록 최소값(1.0/1)으로 채움 — 갭 분석에선 "요구 없음"으로 표시.
    """
    target_bcr = _to_float(req.get("target_building_coverage_pct"))
    target_far = _to_float(req.get("target_far_pct"))
    target_floor_area = _to_float(req.get("target_floor_area_sqm"))
    target_height = _to_float(req.get("target_max_height_m"))
    target_floors = _to_int(req.get("target_floors_above"))
    target_parking = _to_int(req.get("target_parking_count"))
    target_open_space = _to_float(req.get("target_open_space_sqm"))

    # building_area: target_bcr 우선, 없으면 1.0 (엔진 동작 최소값)
    if target_bcr and target_bcr > 0:
        building_area = max(1.0, site_area * target_bcr / 100.0)
    else:
        building_area = 1.0

    # floor_area_above: target_floor_area 우선, 없으면 target_far 계산, 없으면 1.0
    if target_floor_area and target_floor_area > 0:
        floor_area_above = target_floor_area
    elif target_far and target_far > 0:
        floor_area_above = max(1.0, site_area * target_far / 100.0)
    else:
        floor_area_above = 1.0

    return {
        "address": req["address"],
        "pnu": req.get("pnu") or "",
        "building_use": req["facility_use"],
        "building_use_detail": req.get("building_use_detail"),
        "zone_use_override": req.get("zone_use_override"),
        "zone_district": req.get("zone_district"),
        "site_area": site_area,
        "building_area": building_area,
        "floor_area_above": floor_area_above,
        "floor_area_below": 0,
        "total_floor_area": floor_area_above,
        "floors_above": target_floors or 1,
        "floors_below": 0,
        "height": target_height or 1.0,
        "units": _to_int(req.get("target_units")),
        "road_width": _to_float(req.get("road_width")),
        "landscape_area": None,
        "provided_parking_spaces": target_parking,
        "unit_exclusive_area": _to_float(req.get("unit_exclusive_area")),
        "public_open_space_area": target_open_space,
        "applicant_type": req.get("applicant_type") or "개인",
        # 완화 레버 — 대안 비교(What-If). 미지정 시 OFF → raw 법한계.
        "green_grade": req.get("green_grade") or None,
        "energy_grade": req.get("energy_grade") or None,
        "zero_energy_grade": req.get("energy_grade") or None,
        "pilot_project": bool(req.get("pilot_project")),
        "smart_grade": None,
        "long_life_grade": None,
        "far_limit_manual_override": None,
        "relief_reason_manual": None,
        "building_agreement": bool(req.get("building_agreement")),
        "agreement_landscape_road_facing": False,
        "rema_zone": bool(req.get("rema_zone")),
        "easy_remodel": bool(req.get("easy_remodel")),
        "public_rental": False,
        # brief_conditions는 Step 2에서 처리 — 사업성 모드 v1에선 미사용
        "brief_conditions": None,
    }


def _compute_gap(target: float | None, limit: float | None, semantic: str) -> dict:
    """카테고리별 갭 분석.

    semantic="max": target이 limit 이하면 OK (건폐율·용적률 등 상한)
    semantic="min": target이 limit 이상이면 OK (주차 등 하한)
    """
    if target is None or target == 0:
        return {
            "has_target": False,
            "status": "no_target",
            "gap": None,
            "gap_text": "공모 요구 없음",
        }
    if limit is None:
        return {
            "has_target": True,
            "status": "unknown",
            "gap": None,
            "gap_text": "법규 한계 확인 불가",
        }

    if semantic == "max":
        gap = limit - target  # 양수=여유, 음수=부족
        if gap >= 0:
            status = "ok"
            gap_text = f"충족 · 여유 {gap:.1f}"
        else:
            status = "over"
            gap_text = f"초과 · 부족 {-gap:.1f}"
    else:  # min
        gap = target - limit  # 양수=과잉(OK), 음수=부족
        if gap >= 0:
            status = "ok"
            gap_text = f"법정 최소 충족 · 과잉 {gap:.0f}"
        else:
            status = "over"
            gap_text = f"법정 최소 미달 · 부족 {-gap:.0f}"

    return {
        "has_target": True,
        "status": status,
        "gap": round(gap, 2),
        "gap_text": gap_text,
    }


def _compute_max_with_relief(
    req: dict,
    site_area: float,
    base_far_limit: float | None,
    zone_use: str,
) -> dict:
    """FAR에 대해 가능한 모든 완화를 적용한 상한 계산.

    공모 요구 면적이 법한계는 넘되 완화로 커버 가능한 경우 시나리오 추천에 사용.
    """
    if base_far_limit is None or base_far_limit <= 0:
        return {"max_pct": None, "items": []}

    # 모든 완화 옵션을 최대치로 가정해 ceiling 계산
    relief = compute_relief(
        base_limit_pct=base_far_limit,
        zone_use=zone_use,
        building_use=req["facility_use"],
        site_area=site_area,
        public_open_space_area=_to_float(req.get("target_open_space_sqm")),
        green_grade="최우수",
        zero_energy_grade="1",
        pilot_project=False,
        smart_grade=None,  # 별표9 미포함
        long_life_grade=None,  # 별표9 미포함
    )
    return {
        "max_pct": relief.get("final_limit_pct"),
        "items": relief.get("applied_items", []),
    }


def _suggest_scenarios(
    target_far: float | None,
    base_far_limit: float | None,
    max_relief: dict,
) -> list[dict]:
    """공모 요구치가 base를 넘으면 어떤 완화 조합으로 커버 가능한지 제안."""
    if not target_far or not base_far_limit:
        return []
    if target_far <= base_far_limit:
        return []  # base만으로 충족 — 시나리오 불필요
    max_with_all = max_relief.get("max_pct")
    if not max_with_all or max_with_all < target_far:
        return [{
            "label": "완화 합산 최대",
            "result_pct": max_with_all,
            "covers_target": False,
            "note": "모든 완화 적용해도 공모 요구치 미달 — 협상/패스 검토",
        }]
    # 개별 완화 항목들을 누적 제시
    scenarios = []
    cumulative = base_far_limit
    for item in max_relief.get("items", []):
        cumulative += item.get("relief_pct", 0)
        if cumulative > max_with_all:
            cumulative = max_with_all
        scenarios.append({
            "label": item.get("label", item.get("kind", "")),
            "delta_pct": item.get("relief_pct", 0),
            "result_pct": round(cumulative, 1),
            "covers_target": cumulative >= target_far,
            "basis": item.get("basis", ""),
        })
        if cumulative >= target_far:
            break  # 충족된 시점까지만 표시
    return scenarios


def _build_review_burden(applicable_reviews: Any) -> dict:
    """심의·평가 트리거 — 개월수 없이 항목만 (Option A).

    엔진의 evaluate_reviews 반환 구조:
      {items: [{name, severity, triggered_reasons, law_ref, note}], ...}
    REQUIRED만 노출. MAYBE는 별도 섹션.
    """
    # dict({items: [...]}) 또는 list 둘 다 방어
    if isinstance(applicable_reviews, dict):
        items_raw = applicable_reviews.get("items") or []
    elif isinstance(applicable_reviews, list):
        items_raw = applicable_reviews
    else:
        items_raw = []

    required: list[dict] = []
    maybe: list[dict] = []
    for r in items_raw:
        if not isinstance(r, dict):
            continue
        sev = (r.get("severity") or r.get("status") or "").upper()
        reasons = r.get("triggered_reasons")
        if isinstance(reasons, list):
            reason = "; ".join(str(x) for x in reasons if x)
        else:
            reason = reasons or ""
        item = {
            "name": r.get("name") or r.get("category") or "",
            "reason": reason or r.get("note") or "",
            "law_ref": r.get("law_ref") or r.get("basis") or "",
        }
        if sev == "REQUIRED":
            required.append(item)
        elif sev == "MAYBE":
            maybe.append(item)
    return {
        "required": required,
        "maybe": maybe,
        "count_required": len(required),
        "count_maybe": len(maybe),
    }


def _compute_recommendation(categories: list[dict]) -> dict:
    """종합 판단 — 참여 권장 / 협상 필요 / 패스 권장.

    룰:
      - over 카테고리 있음 + 완화로도 커버 불가 → 패스 권장
      - over 카테고리 있음 + 완화 시나리오로 커버 가능 → 협상 필요
      - 모든 카테고리 ok 또는 no_target → 참여 권장
      - unknown만 있고 ok 없음 → 협상 필요 (정보 부족)
    """
    has_uncovered_over = False
    has_coverable_over = False
    has_unknown = False
    has_ok = False

    for cat in categories:
        gap = cat.get("gap_analysis", {})
        status = gap.get("status")
        if status == "over":
            scenarios = cat.get("scenarios", [])
            covers = any(s.get("covers_target") for s in scenarios)
            if covers:
                has_coverable_over = True
            else:
                has_uncovered_over = True
        elif status == "unknown":
            has_unknown = True
        elif status == "ok":
            has_ok = True

    if has_uncovered_over:
        verdict = "패스 권장"
        reason = "공모 요구치가 법적 한계를 초과하고 완화로도 커버 불가"
    elif has_coverable_over:
        verdict = "협상 필요"
        reason = "법 기본 한도는 초과하나 완화 시나리오 적용 시 충족 가능 — 인증·심의 협상 검토"
    elif has_unknown and not has_ok:
        verdict = "정보 부족"
        reason = "용도지역·한도 자동 조회 실패 — 직접 확인 필요"
    else:
        verdict = "참여 권장"
        reason = "공모 요구치가 모두 법적 가능 범위 내"

    return {"verdict": verdict, "reason": reason}


def _compute_proposal(
    req: dict,
    site_area: float,
    cov_limit: float | None,
    applied_far_limit: float | None,
    max_relief: dict,
    relief_items: list[dict] | None = None,
) -> dict:
    """제안 우선 — 이 대지의 가능 범위를 산정.

    applied_far_limit: 현재 선택한 완화 레버가 반영된 용적률 한도(엔진 결과).
      레버 없으면 = raw 법한계. → 카드의 "최대 용적률"은 항상 현재 시나리오 기준.
    max_relief: 이론상 모든 완화를 적용한 천장치(참고용 "완화 시 최대").
    """
    max_far_ceiling = max_relief.get("max_pct")

    # 건축면적 상한 (건폐율 × 대지면적)
    max_building_area = (
        site_area * cov_limit / 100.0 if cov_limit and cov_limit > 0 else None
    )

    # 연면적 — 현재 적용 용적률 기준 / 이론상 천장 기준
    floor_area = (
        site_area * applied_far_limit / 100.0
        if applied_far_limit and applied_far_limit > 0 else None
    )
    floor_area_ceiling = (
        site_area * max_far_ceiling / 100.0
        if max_far_ceiling and max_far_ceiling > 0 else None
    )

    # 권장 주차대수 — 현재 적용 용적률로 최대로 지었을 때의 법정 최소 주차
    recommended_parking = None
    parking_note = None
    if floor_area and floor_area > 0:
        try:
            pk = parking.calculate(
                req["facility_use"],
                floor_area,
                units=_to_int(req.get("target_units")),
                unit_exclusive_area=_to_float(req.get("unit_exclusive_area")),
            )
            recommended_parking = pk.get("required_spaces")
            parking_note = pk.get("notes")
        except Exception as e:  # 계산 불가 용도 등 — 제안에서만 graceful
            logger.warning("[사업성] 권장 주차 산정 실패: %s", e)

    return {
        "max_building_coverage_pct": cov_limit,
        "max_building_area_sqm": round(max_building_area, 1) if max_building_area else None,
        "far_pct": applied_far_limit,
        "max_far_pct_relief": max_far_ceiling,
        "max_floor_area_sqm": round(floor_area, 1) if floor_area else None,
        "max_floor_area_relief_sqm": round(floor_area_ceiling, 1) if floor_area_ceiling else None,
        "recommended_parking_spaces": recommended_parking,
        "parking_basis_floor_area_sqm": round(floor_area, 1) if floor_area else None,
        "parking_note": parking_note,
        "applied_relief_items": relief_items or [],
    }


async def run_feasibility(engine: DiagnoseEngine, req: dict) -> dict:
    """사전 사업성 검토 메인.

    Args:
      engine: DiagnoseEngine 인스턴스
      req: {
        address, pnu, facility_use, applicant_type, zone_use_override,
        zone_district, road_width,
        target_floor_area_sqm, target_building_coverage_pct, target_far_pct,
        target_max_height_m, target_floors_above, target_parking_count,
        target_open_space_sqm, target_units, unit_exclusive_area,
        site_area_override (선택 — 자동 조회 실패 시),
      }

    Returns:
      {
        address, land_facts, categories[], scenarios, review_burden,
        overall_recommendation, data_quality, mode
      }
    """
    address = req["address"]
    pnu = req.get("pnu") or ""

    # 1. 토지 정보 선조회 — site_area 자동 입력
    land = await engine._resolver.resolve(address, pnu=pnu)
    if req.get("zone_use_override"):
        land["zone_use"] = req["zone_use_override"]
    if req.get("zone_district"):
        land["zone_district"] = req["zone_district"]

    # site_area: 사용자 override > 자동 조회 > 기본값
    site_area = (
        _to_float(req.get("site_area_override"))
        or _to_float(land.get("parcel_area"))
        or 1000.0  # 임시 기본값 — 자동 조회 실패 시 비례 계산만 가능
    )

    # 2. 엔진 페이로드 빌드 + 호출
    engine_payload = _build_engine_payload(req, site_area)
    engine_payload["total_floor_area"] = (
        engine_payload["floor_area_above"] + engine_payload["floor_area_below"]
    )

    # diagnose_fast로 토지 재조회 생략, skip_ai=True로 fire_safety AI 호출 생략
    diag = await engine.diagnose_fast(
        engine_payload,
        zone_use=land.get("zone_use", ""),
        land_info=land,
        skip_ai=True,
    )

    # 3. 카테고리별 갭 분석
    results = diag.get("results", {})
    zone_use = land.get("zone_use", "")
    base_far_limit = _get_default_far_limit(zone_use) if zone_use else None

    max_relief = _compute_max_with_relief(
        req, site_area, base_far_limit, zone_use,
    )

    categories = []
    for spec in _GAP_SPECS:
        engine_result = results.get(spec["engine_category"], {})
        limit = engine_result.get(spec["limit_key"])
        target = _to_float(req.get(spec["target_field"]))

        gap = _compute_gap(target, limit, spec["semantic"])

        scenarios = []
        if spec["key"] == "far":
            scenarios = _suggest_scenarios(target, limit, max_relief)

        categories.append({
            "key": spec["key"],
            "label": spec["label"],
            "unit": spec["unit"],
            "competition_target": target,
            "legal_limit": limit,
            "max_with_relief": max_relief.get("max_pct") if spec["key"] == "far" else None,
            "gap_analysis": gap,
            "scenarios": scenarios,
            "source": engine_result.get("source"),
            "engine_notes": engine_result.get("notes"),
        })

    # 4. 연면적 갭 — 별도 처리 (FAR 한도 × 대지면적 / 100)
    target_floor_area = _to_float(req.get("target_floor_area_sqm"))
    if target_floor_area and base_far_limit:
        max_floor_area = site_area * base_far_limit / 100.0
        max_floor_area_relief = (
            site_area * max_relief["max_pct"] / 100.0
            if max_relief.get("max_pct") else None
        )
        gap = _compute_gap(target_floor_area, max_floor_area, "max")
        categories.append({
            "key": "floor_area",
            "label": "연면적",
            "unit": "㎡",
            "competition_target": target_floor_area,
            "legal_limit": round(max_floor_area, 1),
            "max_with_relief": round(max_floor_area_relief, 1) if max_floor_area_relief else None,
            "gap_analysis": gap,
            "scenarios": [],
            "source": "용적률 한도 × 대지면적 / 100",
            "engine_notes": "용적률 카테고리 참조",
        })

    # 5. 제안 우선 — 현재 완화 레버가 반영된 이 대지의 가능 범위 산정
    cov_limit = results.get("건폐율", {}).get("limit_pct")
    far_result = results.get("용적률", {})
    applied_far_limit = far_result.get("limit_pct")
    relief_items = (far_result.get("relief_info") or {}).get("applied_items", [])
    proposal = _compute_proposal(
        req, site_area, cov_limit, applied_far_limit, max_relief, relief_items,
    )

    # 6. 심의 부담 (Option A — 개월수 없음)
    review_burden = _build_review_burden(diag.get("applicable_reviews", []))

    # 7. 종합 판단
    recommendation = _compute_recommendation(categories)

    return {
        "address": address,
        "land_facts": diag.get("land_info", {}),
        "site_area_used": site_area,
        "site_area_source": (
            "user_override" if req.get("site_area_override")
            else ("auto" if land.get("parcel_area") else "default_1000")
        ),
        "proposal": proposal,
        "categories": categories,
        "review_burden": review_burden,
        "overall_recommendation": recommendation,
        "data_quality": diag.get("data_quality", {}),
        "mode": "feasibility",
        "phase": "Step1",
    }
