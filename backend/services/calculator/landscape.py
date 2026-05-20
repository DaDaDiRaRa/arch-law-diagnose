"""조경 계산기.

건축법 제42조 + 시행령 제27조 — 대지 안의 조경 의무.
조경기준 고시 (국토부 고시 제2021-1778호, 2022.1.7.) — 식재수량·면적 산정 기준.

시행령 §27 ①항 면제 대상 (법제처 API 확인, 2026 현행):
  1호. 녹지지역에 건축하는 건축물
  2호. 면적 5천㎡ 미만 대지의 공장
  3호. 연면적 1,500㎡ 미만 공장
  4호. 산업단지의 공장
  5호. 염분/용도 특성상 곤란 — 건축조례
  6호. 축사
  7호. 가설건축물
  8호. 1,500㎡ 미만 물류시설 (주거·상업 제외)
  9호. 자연환경보전·농림·관리지역 (지구단위계획구역 제외)
  10호. 그 밖에 건축조례

시행령 §27 ②항 — 의무 비율:
  4호. 면적 200~300㎡ 미만 대지: 대지면적의 10% 이상
  그 외 일반 건축물 비율은 건축조례에 위임 — by_zone JSON은 지자체 평균 추정값.
  confidence 3 (지자체 조례 확인 필요).
"""
from __future__ import annotations

import json
import math
import os

_STANDARDS: dict = {}


def _load_standards() -> dict:
    global _STANDARDS
    if _STANDARDS:
        return _STANDARDS
    cfg = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../config/landscape_standards.json")
    )
    with open(cfg, encoding="utf-8") as f:
        _STANDARDS = json.load(f)
    return _STANDARDS


def calculate(
    landscape_area: float | None,
    site_area: float,
    zone_use: str,
    building_use: str,
    limit_override: float | None = None,
    source_override: str | None = None,
    is_estimate_override: bool = False,
    rooftop_landscape_area: float | None = None,
) -> dict:
    """조경 진단 결과.

    Args:
      landscape_area: 조경면적(㎡). 미입력 시 요건만 표시.
      site_area: 대지면적(㎡).
      zone_use: 용도지역.
      building_use: 건축물 용도.
      limit_override: OrdinanceResolver가 결정한 의무 비율(%). 시행령 §27 ①항
        면제 분기 통과 후 ②항 비율에 적용. by_zone JSON 평균값보다 우선.
      source_override: "조례" | "시행령" 레이블 (resolver 결과).
      is_estimate_override: resolver가 반환한 값이 시행령 평균 추정값임을 표시.
        True면 source 라벨과 confidence 를 추정값 기준으로 낮춤.

    Returns:
      {category, actual_pct, required_pct, exempt, pass, deficit_m2,
       required_area_m2, score, confidence, source, law_refs, notes}
    """
    std = _load_standards()
    exempt_threshold = std.get("exempt_below_site_area", 200)

    exempt = False
    exempt_reason: str | None = None
    required_pct: float = 0.0

    # ── 시행령 §27 ①항 면제 (우선순위 순) ──────────────────────────────────
    # 1호: 녹지지역
    if _is_green_zone(zone_use):
        exempt = True
        exempt_reason = (
            f"{zone_use} 건축 — 조경 면제 (시행령 §27 ①항 1호: 녹지지역)"
        )
    # 9호: 자연환경보전·농림·관리지역 (단, 지구단위계획구역은 제외)
    elif _is_conservation_or_management_zone(zone_use):
        # 지구단위계획구역인지 확인은 사용자 입력 zone_district 등에 단서 필요.
        # 현재 calculator에는 그 정보가 없으므로 보수적으로 면제 처리 + 안내.
        exempt = True
        exempt_reason = (
            f"{zone_use} 건축 — 조경 면제 (시행령 §27 ①항 9호: "
            f"자연환경보전·농림·관리지역). 지구단위계획구역이면 면제 제외 — 별도 확인 필요"
        )
    # 6호: 축사
    elif "축사" in (building_use or ""):
        exempt = True
        exempt_reason = "축사 — 조경 면제 (시행령 §27 ①항 6호)"
    # 7호: 가설건축물
    elif "가설" in (building_use or ""):
        exempt = True
        exempt_reason = "가설건축물 — 조경 면제 (시행령 §27 ①항 7호)"
    # 2호: 면적 5천㎡ 미만 대지의 공장
    elif "공장" in (building_use or "") and site_area < 5000:
        exempt = True
        exempt_reason = (
            f"공장 + 대지 {site_area:.0f}㎡ < 5,000㎡ — 조경 면제 "
            f"(시행령 §27 ①항 2호)"
        )
    # 200㎡ 미만 대지 (시행령 §27 ②항 4호의 반대 — 200㎡ 이상부터 의무)
    elif site_area < exempt_threshold:
        exempt = True
        exempt_reason = (
            f"대지면적 {site_area:.0f}㎡ < {exempt_threshold}㎡ — 조경 의무 없음 "
            f"(시행령 §27 ②항 4호 적용 외)"
        )
    else:
        # ②항 4호: 200~300㎡ 미만은 10% 의무 (시행령 직접 명시 — 조례로 변경 불가)
        if site_area < 300:
            required_pct: float | None = 10.0
        else:
            # 그 외 비율은 시·도 조례 위임. resolver 결과(limit_override) 우선,
            # 없으면 by_use_override(시행령 직접 명시 용도만) → None(조례 확인 필요) 순.
            if limit_override is not None:
                required_pct = float(limit_override)
            else:
                required_pct = _required_ratio(building_use, site_area, zone_use, std)
        if required_pct == 0:
            exempt = True
            exempt_reason = f"용도 '{building_use}' 별 면제"

    # 조례 데이터 없고 시행령 직접 명시 용도도 아님 → 확인 필요
    if required_pct is None:
        return _result(
            actual_pct=None,
            required_pct=None,
            required_area=0.0,
            exempt=False,
            passed=None,
            deficit=None,
            score=None,
            confidence=2,
            source="건축법 시행령 §27 ②항 — 비율은 시·도 조례에 위임",
            law_refs=_law_refs(),
            notes=(
                "조경 의무비율은 시행령 §27 ②항에 의해 지자체 조례에서 정함."
                " 해당 시·군·구 도시계획조례를 직접 확인하거나, 조례 조회 결과가 확인되면 재진단 필요."
            ),
        )

    required_area = round(site_area * required_pct / 100, 2)
    law_refs = _law_refs()

    # 비면제 분기에서 사용할 source/confidence — 조례 적용 시 갱신
    # 시행령 ②항 4호 (200~300㎡=10%) 는 조례 변경 불가이므로 site_area >= 300 일 때만 조례값 적용
    ordinance_applied = (
        not exempt and limit_override is not None and site_area >= 300
    )
    if ordinance_applied and not is_estimate_override:
        nonexempt_source = source_override or "지자체 도시계획조례 (의무 조경 비율)"
        nonexempt_confidence = 5
    elif ordinance_applied and is_estimate_override:
        # 시도 평균 추정값(seed) — 시군구 조례 미수집 상태
        nonexempt_source = source_override or "시행령 §27 평균 추정값 (지자체 조례 확인 필요)"
        nonexempt_confidence = 4
    else:
        # by_use_override 매칭(시행령 직접 명시) 또는 200~300㎡ 직접 규정
        nonexempt_source = "건축법 시행령 제27조"
        nonexempt_confidence = 5

    # 고시 §7조 식재수량 (의무 조경면적 기준 최소 수량)
    planting = _calc_planting(required_area, zone_use, std) if not exempt else {}

    # 고시 §4조 조경면적 산정 조건 안내 (면제 아닌 경우)
    hint_4 = (
        "※ 고시 §4조: 식재면적 ≥ 의무면적 50% / 1개 식재면적 ≥ 1㎡ / 조경시설공간 ≥ 10㎡."
        if not exempt else ""
    )
    # 고시 §5조 자연지반 안내
    hint_5 = (
        f"※ 고시 §5조: 의무면적({required_area:.0f}㎡)의 10% 이상({required_area * 0.1:.0f}㎡)은 자연지반."
        if not exempt and required_area > 0 else ""
    )

    # 조경면적 미입력 처리
    if landscape_area is None:
        if exempt:
            return _result(
                actual_pct=None,
                required_pct=required_pct,
                required_area=required_area,
                exempt=True,
                passed=True,
                deficit=0.0,
                score=10.0,
                confidence=5,
                source="건축법 시행령 제27조 (면제 대상)",
                law_refs=law_refs,
                notes=exempt_reason or "조경 의무 면제",
                **planting,
            )
        planting_note = _planting_note(planting)
        return _result(
            actual_pct=None,
            required_pct=required_pct,
            required_area=required_area,
            exempt=False,
            passed=None,
            deficit=None,
            score=None,
            confidence=nonexempt_confidence,
            source=nonexempt_source,
            law_refs=law_refs,
            notes=" ".join(filter(None, [
                f"조경 의무 {required_pct:.0f}% 이상 (≈ {required_area:.0f}㎡). "
                "조경면적 입력 시 적합 여부 자동 판정.",
                planting_note,
                hint_4,
                hint_5,
            ])),
            **planting,
        )

    # 시행령 §27 ③항 — 옥상조경 인정
    #   - 옥상 조경면적의 2/3 인정
    #   - 의무 조경면적의 50%까지만 인정 (상한 캡)
    rooftop_credit = 0.0
    rooftop_credit_note = ""
    if rooftop_landscape_area and rooftop_landscape_area > 0 and not exempt:
        cap = required_area * 0.5
        rooftop_credit = round(min(rooftop_landscape_area * (2 / 3), cap), 2)
        rooftop_credit_note = (
            f"옥상조경 {rooftop_landscape_area:.0f}㎡ × 2/3 = "
            f"{rooftop_landscape_area * 2/3:.1f}㎡, "
            f"의무면적 50% 캡 {cap:.1f}㎡ → 인정 {rooftop_credit:.1f}㎡ (시행령 §27 ③항)"
        )

    effective_landscape = (landscape_area or 0.0) + rooftop_credit
    actual_pct = (effective_landscape / site_area * 100) if site_area > 0 else 0.0

    if exempt:
        return _result(
            actual_pct=round(actual_pct, 2),
            required_pct=required_pct,
            required_area=required_area,
            exempt=True,
            passed=True,
            deficit=0.0,
            score=10.0,
            confidence=5,
            source="건축법 시행령 제27조 (면제 대상)",
            law_refs=law_refs,
            notes=(exempt_reason or "조경 의무 면제") + f" (계획 조경 {actual_pct:.1f}%)",
            **planting,
        )

    passed = actual_pct >= required_pct
    deficit = max(0.0, required_area - effective_landscape)

    if not passed:
        score = 0.0
    else:
        margin_ratio = (actual_pct - required_pct) / required_pct if required_pct > 0 else 1.0
        if margin_ratio >= 0.3:
            score = 10.0
        elif margin_ratio >= 0.1:
            score = round(8.0 + (margin_ratio - 0.1) / 0.2 * 2.0, 1)
        else:
            score = round(7.0 + margin_ratio / 0.1 * 1.0, 1)

    planting_note = _planting_note(planting)
    base_notes = _notes(passed, actual_pct, required_pct, deficit, zone_use)
    notes = " ".join(filter(None, [
        (base_notes + " " + rooftop_credit_note).strip() if rooftop_credit_note else base_notes,
        planting_note,
        hint_4,
        hint_5,
    ]))

    return _result(
        actual_pct=round(actual_pct, 2),
        required_pct=required_pct,
        required_area=required_area,
        exempt=False,
        passed=passed,
        deficit=round(deficit, 2),
        score=round(score, 1),
        confidence=nonexempt_confidence,
        source=nonexempt_source,
        law_refs=law_refs,
        notes=notes,
        rooftop_landscape_area=rooftop_landscape_area or 0.0,
        rooftop_credit_m2=rooftop_credit,
        **planting,
    )


def _calc_planting(required_area: float, zone_use: str, std: dict) -> dict:
    """고시 §7조 식재수량 계산.

    의무 조경면적(required_area) 기준 최소 교목·관목 수 반환.
    zone_use → 용도지역 카테고리 → planting_rates 조회.
    매칭 없으면 주거(기본값) 적용.
    """
    from services.zone_use_normalizer import category_of

    rates = std.get("planting_rates", {})
    cat = category_of(zone_use) or "주거"
    rate = rates.get(cat) or rates.get("주거", {"tree_per_m2": 0.2, "shrub_per_m2": 1.0})

    tree_per = float(rate.get("tree_per_m2", 0.2))
    shrub_per = float(rate.get("shrub_per_m2", 1.0))

    required_trees = math.ceil(required_area * tree_per) if required_area > 0 else 0
    required_shrubs = math.ceil(required_area * shrub_per) if required_area > 0 else 0

    return {
        "required_trees": required_trees,
        "required_shrubs": required_shrubs,
        "planting_zone_cat": cat,
        "planting_tree_rate": tree_per,
        "planting_shrub_rate": shrub_per,
    }


def _planting_note(planting: dict) -> str:
    if not planting or planting.get("required_trees") is None:
        return ""
    cat = planting.get("planting_zone_cat", "")
    trees = planting.get("required_trees", 0)
    shrubs = planting.get("required_shrubs", 0)
    t_rate = planting.get("planting_tree_rate", 0)
    s_rate = planting.get("planting_shrub_rate", 0)
    return (
        f"※ 고시 §7조: {cat} 기준 교목 {trees}주 이상({t_rate}/㎡)"
        f" · 관목 {shrubs}주 이상({s_rate}/㎡) 식재 필요."
    )


def _is_green_zone(zone_use: str) -> bool:
    """녹지지역 — 시행령 §27 ①항 1호 면제."""
    from services.zone_use_normalizer import category_of
    return category_of(zone_use) == "녹지"


def _is_conservation_or_management_zone(zone_use: str) -> bool:
    """자연환경보전·농림·관리지역 — 시행령 §27 ①항 9호 면제 (지구단위계획구역 제외)."""
    from services.zone_use_normalizer import category_of, normalize
    cat = category_of(zone_use)
    if cat == "관리":
        return True
    canonical = normalize(zone_use)
    return canonical in ("농림지역", "자연환경보전지역")


def _required_ratio(
    building_use: str,
    site_area: float,
    zone_use: str,
    std: dict,
) -> float | None:
    """의무 비율(%) 결정. by_use_override(시행령 직접 명시) 우선.

    by_zone/default 추정값 제거 (2026-05-20 시행령 §27 원문 대조).
    매칭 없으면 None 반환 → 조례 확인 필요.
    """
    by_use = std.get("by_use_override", {})
    for use_key, val in by_use.items():
        if use_key.startswith("_"):
            continue
        if use_key not in building_use and building_use not in use_key:
            continue
        # 면적 구간 (공장 등)
        if isinstance(val, dict) and "thresholds" in val:
            for t in val["thresholds"]:
                max_area = t.get("max_site_area")
                if max_area is None or site_area <= max_area:
                    return float(t["ratio"])
        elif isinstance(val, (int, float)):
            return float(val)

    # by_zone 추정값 제거됨. 조례 resolver가 limit_override 없이 여기 도달 = 조례 미확인.
    return None


def _notes(
    passed: bool,
    actual: float,
    required: float,
    deficit: float,
    zone: str,
) -> str:
    if not passed:
        return (
            f"[주의] 조경 {actual:.1f}% < 의무 {required:.0f}% "
            f"({deficit:.0f}㎡ 부족). 인허가 보완 필요."
        )
    margin = actual - required
    return (
        f"조경 {actual:.1f}% / 의무 {required:.0f}% "
        f"({margin:.1f}%p 여유, {zone} 기준). 지자체 조례 강화 여부 별도 확인."
    )


def _result(**kwargs) -> dict:
    """카테고리 결과 dict 빌더."""
    return {
        "category": "조경",
        "actual_pct": kwargs["actual_pct"],
        "required_pct": kwargs["required_pct"],
        "required_area_m2": kwargs["required_area"],
        "exempt": kwargs["exempt"],
        "pass": kwargs["passed"],
        "deficit_m2": kwargs["deficit"],
        "score": kwargs["score"],
        "confidence": kwargs["confidence"],
        "source": kwargs["source"],
        "law_refs": kwargs["law_refs"],
        "notes": kwargs["notes"],
        "rooftop_landscape_area_m2": kwargs.get("rooftop_landscape_area", 0.0),
        "rooftop_credit_m2": kwargs.get("rooftop_credit_m2", 0.0),
        # 고시 §7조 식재수량
        "required_trees": kwargs.get("required_trees"),
        "required_shrubs": kwargs.get("required_shrubs"),
        "planting_zone_cat": kwargs.get("planting_zone_cat"),
    }


def _law_refs() -> list[dict]:
    return [
        {
            "name": "건축법 제42조 (조경 등의 조치)",
            "url": "https://www.law.go.kr/법령/건축법/제42조",
        },
        {
            "name": "건축법 시행령 제27조 (대지의 조경)",
            "url": "https://www.law.go.kr/법령/건축법시행령/제27조",
        },
        {
            "name": "건축물 대지의 조경기준 (국토부 고시 제2021-1778호)",
            "url": "https://www.law.go.kr/행정규칙/건축물대지의조경기준",
        },
    ]
