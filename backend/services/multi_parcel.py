"""합필(여러 필지) 진단 — 면적 안분 / 소규모 예외 처리.

국토계획법 제84조 + 시행령 제94조:
- 도시지역: 330㎡ 이하 → 큰 부분 기준 전체 적용
- 도시지역 내 노선상업지역(도로변 띠모양 상업지역): 660㎡
- 도시지역 외(관리/농림/자연환경보전지역): 1000㎡
- 위 임계치 초과 시: 면적 안분(가중평균)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_LIMITS_PATH = Path(__file__).parent.parent / "config" / "zone_limits.json"
_WEIGHTS_PATH = Path(__file__).parent.parent / "config" / "law_scoring_weights.json"

# 작은 부분 면적 임계치 (㎡) — 국토계획법 시행령 제94조
THRESHOLD_URBAN_M2 = 330.0        # 도시지역
THRESHOLD_ROADSIDE_COMMERCIAL_M2 = 660.0  # 노선상업지역(도로변 띠)
THRESHOLD_NON_URBAN_M2 = 1000.0   # 도시지역 외

# (구) 호환용 — 외부에서 import 하던 코드 보호
SMALL_PART_THRESHOLD_M2 = THRESHOLD_URBAN_M2


# 도시지역 카테고리 (국토계획법 §6)
_URBAN_KEYWORDS = ("주거지역", "상업지역", "공업지역", "녹지지역")
# 도시지역 외
_NON_URBAN_KEYWORDS = ("관리지역", "농림지역", "자연환경보전지역",
                       "보전관리", "생산관리", "계획관리")


def _is_urban_zone(zone_use: str) -> bool:
    """zone_use 한글명 → 도시지역 여부."""
    if not zone_use:
        return True  # 정보 부족 시 안전하게 도시(엄격한 임계치) 적용
    for kw in _NON_URBAN_KEYWORDS:
        if kw in zone_use:
            return False
    for kw in _URBAN_KEYWORDS:
        if kw in zone_use:
            return True
    return True


def _is_roadside_commercial(zone_district: str) -> bool:
    """지역지구 텍스트에 '노선상업' / '도로변 띠' 등 단서가 있는지."""
    if not zone_district:
        return False
    text = zone_district.replace(" ", "")
    return "노선상업" in text or "노선형상업" in text or "도로변띠" in text


def _resolve_threshold(
    smallest_zone: str,
    all_zones: list[str],
    is_roadside_commercial: bool = False,
) -> tuple[float, str]:
    """작은 부분 zone 기준 임계치 결정.

    반환: (임계치_m2, 적용근거_설명)
    """
    if is_roadside_commercial:
        return (
            THRESHOLD_ROADSIDE_COMMERCIAL_M2,
            "노선상업지역(도로변 띠) → 660㎡ (시행령 §94①1 단서)",
        )
    # 가장 작은 부분이 도시지역이고 그 외 부분도 모두 도시지역이면 도시 기준
    # (도시 + 비도시 혼재 시 보수적으로 도시 기준 적용)
    all_urban = all(_is_urban_zone(z) for z in all_zones)
    if all_urban:
        return (
            THRESHOLD_URBAN_M2,
            "도시지역 → 330㎡ (시행령 §94①1)",
        )
    if not _is_urban_zone(smallest_zone) and not any(_is_urban_zone(z) for z in all_zones):
        return (
            THRESHOLD_NON_URBAN_M2,
            "도시지역 외 → 1,000㎡ (시행령 §94①2)",
        )
    # 혼재 — 가장 작은 부분이 비도시지역이면 비도시 기준, 아니면 도시 기준
    if not _is_urban_zone(smallest_zone):
        return (
            THRESHOLD_NON_URBAN_M2,
            "작은 부분이 도시지역 외 → 1,000㎡ (시행령 §94①2)",
        )
    return (
        THRESHOLD_URBAN_M2,
        "도시지역 → 330㎡ (시행령 §94①1)",
    )

_LIMITS_CACHE: dict | None = None
_WEIGHTS_CACHE: dict | None = None


def _load_limits() -> dict:
    global _LIMITS_CACHE
    if _LIMITS_CACHE is None:
        with open(_LIMITS_PATH, encoding="utf-8") as f:
            _LIMITS_CACHE = json.load(f)
    return _LIMITS_CACHE


def _load_weights() -> dict:
    global _WEIGHTS_CACHE
    if _WEIGHTS_CACHE is None:
        with open(_WEIGHTS_PATH, encoding="utf-8") as f:
            _WEIGHTS_CACHE = json.load(f)["weights"]
    return _WEIGHTS_CACHE


def _get_zone_limit(zone_use: str, key: str) -> float | None:
    """zone_limits.json에서 zone별 한도 조회 (부분 매칭 지원)."""
    limits = _load_limits().get(key, {})
    if zone_use in limits and limits[zone_use] is not None:
        return float(limits[zone_use])
    for k, v in limits.items():
        if k.startswith("_") or v is None:
            continue
        if zone_use in k or k in zone_use:
            return float(v)
    return None


def aggregate_zones(
    parcels: list[dict],
    lands: list[dict],
    *,
    is_roadside_commercial: bool = False,
) -> dict:
    """필지별 용도지역 정보 → 합산 한도/모드 계산.

    Args:
      parcels: [{address, pnu, site_area, ...}]
      lands:   [{zone_use, zone_district, jurisdiction_name, ...}]
      is_roadside_commercial: 사용자가 노선상업지역(도로변 띠) 임을 명시한 경우 True

    Returns:
      {
        mode: "same_zone" | "small_part" | "weighted",
        primary_zone, total_site_area,
        zone_breakdown: [...],
        weighted_coverage_limit, weighted_far_limit,
        small_part_zone, threshold_m2, threshold_basis,
        calc_method, cross_jurisdiction, jurisdictions
      }
    """
    # zone별 면적 그룹화 (같은 zone은 합산)
    zone_areas: dict[str, float] = {}
    for parcel, land in zip(parcels, lands):
        zone = (land.get("zone_use") or "").strip()
        if not zone:
            continue
        zone_areas[zone] = zone_areas.get(zone, 0.0) + float(parcel["site_area"])

    if not zone_areas:
        raise ValueError("모든 필지의 용도지역 조회 실패")

    total_area = sum(zone_areas.values())

    # 시·도(jurisdiction) 추출
    sidos: set[str] = set()
    for land in lands:
        nm = (land.get("jurisdiction_name") or "").strip()
        if nm:
            sidos.add(nm.split()[0])
    cross_jur = len(sidos) > 1

    # 노선상업지역 자동 감지 — zone_district 텍스트에서 단서 검색
    if not is_roadside_commercial:
        for land in lands:
            if _is_roadside_commercial(land.get("zone_district", "")):
                is_roadside_commercial = True
                break

    sorted_zones = sorted(zone_areas.items(), key=lambda x: -x[1])
    primary_zone = sorted_zones[0][0]

    breakdown = [
        {
            "zone": z,
            "area": round(a, 2),
            "area_ratio": round(a / total_area, 4),
            "coverage_limit": _get_zone_limit(z, "building_coverage_ratio"),
            "far_limit": _get_zone_limit(z, "floor_area_ratio"),
            "is_urban": _is_urban_zone(z),
        }
        for z, a in sorted_zones
    ]

    # 모드 판정
    if len(zone_areas) == 1:
        return {
            "mode": "same_zone",
            "primary_zone": primary_zone,
            "total_site_area": round(total_area, 2),
            "zone_breakdown": breakdown,
            "weighted_coverage_limit": breakdown[0]["coverage_limit"],
            "weighted_far_limit": breakdown[0]["far_limit"],
            "small_part_zone": None,
            "threshold_m2": None,
            "threshold_basis": None,
            "calc_method": "동일 용도지역 단순 합산",
            "cross_jurisdiction": cross_jur,
            "jurisdictions": sorted(sidos),
        }

    smallest_zone, smallest_area = sorted_zones[-1]
    threshold, threshold_basis = _resolve_threshold(
        smallest_zone,
        list(zone_areas.keys()),
        is_roadside_commercial=is_roadside_commercial,
    )

    if smallest_area <= threshold:
        return {
            "mode": "small_part",
            "primary_zone": primary_zone,
            "total_site_area": round(total_area, 2),
            "zone_breakdown": breakdown,
            "weighted_coverage_limit": _get_zone_limit(primary_zone, "building_coverage_ratio"),
            "weighted_far_limit": _get_zone_limit(primary_zone, "floor_area_ratio"),
            "small_part_zone": smallest_zone,
            "threshold_m2": threshold,
            "threshold_basis": threshold_basis,
            "calc_method": (
                f"소규모 예외 (국토계획법 §84·시행령 §94) — 작은 부분 "
                f"{smallest_zone} {smallest_area:.0f}㎡ ≤ {threshold:.0f}㎡, "
                f"큰 부분 {primary_zone} 기준 전체 적용 [{threshold_basis}]"
            ),
            "cross_jurisdiction": cross_jur,
            "jurisdictions": sorted(sidos),
        }

    # 면적 안분 — 가중평균
    return {
        "mode": "weighted",
        "primary_zone": primary_zone,
        "total_site_area": round(total_area, 2),
        "zone_breakdown": breakdown,
        "weighted_coverage_limit": _weighted_avg(breakdown, "coverage_limit", total_area),
        "weighted_far_limit": _weighted_avg(breakdown, "far_limit", total_area),
        "small_part_zone": None,
        "threshold_m2": threshold,
        "threshold_basis": threshold_basis,
        "calc_method": (
            f"면적 안분 (국토계획법 §84·시행령 §94) — {len(zone_areas)}개 용도지역 "
            f"면적 가중평균 적용 (작은 부분 {smallest_area:.0f}㎡ > 임계치 {threshold:.0f}㎡)"
        ),
        "cross_jurisdiction": cross_jur,
        "jurisdictions": sorted(sidos),
    }


def _weighted_avg(breakdown: list[dict], key: str, total_area: float) -> float | None:
    """면적 가중평균 (한도 없는 zone 은 평균에서 제외하지 않고 0 으로 처리되지 않게 valid_area 기준)."""
    weighted_sum = 0.0
    valid_area = 0.0
    for b in breakdown:
        v = b.get(key)
        if v is None:
            continue
        weighted_sum += b["area"] * v
        valid_area += b["area"]
    if valid_area == 0:
        return None
    return round(weighted_sum / valid_area, 2)


def apply_weighted_limits(diag_result: dict, agg_info: dict) -> dict:
    """진단 결과에 가중평균 한도 적용 (in-place + return).

    mode == "same_zone": 변경 없음 (단순 합산이라 기존 진단 그대로 사용 가능).
    mode == "small_part": 큰 부분 zone 으로 진단된 결과 그대로 사용 (이미 큰 zone 기준).
    mode == "weighted":   건폐율/용적률 한도를 가중평균으로 교체 + 점수/신호 재계산.
    """
    mode = agg_info["mode"]

    if mode == "same_zone":
        return diag_result

    results = diag_result.get("results", {})

    if mode == "weighted":
        # 건폐율
        cov_card = results.get("건폐율")
        cov_limit = agg_info.get("weighted_coverage_limit")
        if cov_card and cov_limit is not None:
            _override_card(cov_card, cov_limit, "건폐율", agg_info)
        # 용적률
        far_card = results.get("용적률")
        far_limit = agg_info.get("weighted_far_limit")
        if far_card and far_limit is not None:
            _override_card(far_card, far_limit, "용적률", agg_info)
    elif mode == "small_part":
        # 큰 zone 기준 그대로지만, notes/source 에 예외 적용 사실 명시
        for cat in ("건폐율", "용적률"):
            card = results.get(cat)
            if not card:
                continue
            _annotate_small_part(card, cat, agg_info)

    # 종합 점수·신호 재계산
    overall = _recalc_overall(results)
    diag_result["overall_score"] = overall
    diag_result["risks"] = [
        {"category": k, "reason": v.get("notes", "")}
        for k, v in results.items()
        if v.get("pass") is False
    ]
    diag_result["warnings"] = [
        {"category": k, "reason": v.get("notes", "")}
        for k, v in results.items()
        if v.get("pass") is None
    ]
    if diag_result["risks"]:
        diag_result["signal"] = "RED"
    elif diag_result["warnings"] or (overall is not None and overall < 7.0):
        diag_result["signal"] = "YELLOW"
    else:
        diag_result["signal"] = "GREEN"

    return diag_result


def _override_card(card: dict, new_limit: float, category: str, agg_info: dict) -> None:
    """건폐율/용적률 카드의 한도를 가중평균으로 교체."""
    actual = card.get("actual_pct", 0) or 0
    card["limit_pct"] = new_limit
    passed = actual <= new_limit
    card["pass"] = passed
    card["excess_pct"] = round(max(0.0, actual - new_limit), 2)

    # 점수 재계산 (coverage.py / far.py 와 동일 곡선)
    if not passed:
        card["score"] = 0.0
    else:
        ratio = actual / new_limit if new_limit > 0 else 0
        if ratio <= 0.7:
            score = 10.0
        elif ratio <= 0.9:
            score = 10.0 - (ratio - 0.7) / 0.2 * 2.0
        else:
            score = 8.0 - (ratio - 0.9) / 0.1 * 2.0
        card["score"] = max(0.0, round(score, 1))

    # notes
    breakdown = agg_info["zone_breakdown"]
    key = "coverage_limit" if category == "건폐율" else "far_limit"
    parts = ", ".join(
        f"{b['zone']} {b['area']:.0f}㎡ ({b.get(key) if b.get(key) is not None else '?'}%)"
        for b in breakdown
    )
    status = "적합" if passed else f"{actual - new_limit:.1f}%p 초과"
    card["notes"] = (
        f"{category} 가중평균 한도 {new_limit}% 적용 (면적 안분, 국토계획법 제84조). "
        f"실제 {actual}%, {status}. 내역: {parts}"
    )
    card["source"] = "🔗 합필 — 면적 안분 (국토계획법 제84조)"
    card["confidence"] = min(card.get("confidence", 5), 4)


def _annotate_small_part(card: dict, category: str, agg_info: dict) -> None:
    """소규모 예외 — 한도는 그대로지만 notes 에 적용 사실 명시."""
    limit = card.get("limit_pct")
    actual = card.get("actual_pct", 0)
    passed = card.get("pass")
    threshold = agg_info.get("threshold_m2") or THRESHOLD_URBAN_M2
    status = (
        "적합" if passed is True
        else f"{actual - (limit or 0):.1f}%p 초과" if passed is False
        else "확인 필요"
    )
    card["notes"] = (
        f"{category} 한도 {limit}% 적용 — 소규모 예외 (작은 부분 "
        f"{agg_info['small_part_zone']}이 {threshold:.0f}㎡ 이하라 큰 부분 "
        f"{agg_info['primary_zone']} 기준 전체 적용). "
        f"실제 {actual}%, {status}."
    )
    card["source"] = (card.get("source") or "") + " · 🔗 합필 소규모 예외 (제84조)"


def _recalc_overall(results: dict) -> float | None:
    """종합 점수 가중평균 재계산 (diagnose_engine._weighted_score 와 동일 로직)."""
    weights = _load_weights()
    total_w = 0.0
    weighted_sum = 0.0
    for k, r in results.items():
        score = r.get("score")
        w = weights.get(k, 0)
        if score is None or w == 0:
            continue
        weighted_sum += score * w
        total_w += w
    if total_w == 0:
        return None
    return round(weighted_sum / total_w, 2)
