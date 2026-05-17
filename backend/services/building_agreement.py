"""건축협정 §110의7 완화 적용 헬퍼.

건축법 시행령 제110조의7(건축협정에 따른 특례) 5개 카테고리:
  1호. 조경 (§42): 도로면 통합 조성 한정 — 의무 면적기준 100분의 20 완화
  2호. 건폐율 (§55): 무조건 — 한도 100분의 20 완화. 국계법 시행령 §84 캡
  3호. 용적률 (§56): 무조건 — 한도 100분의 20 완화. 국계법 시행령 §85 캡
  4호. 높이 §60: 너비 6미터 이상 도로 한정 — 가로구역 최고높이 100분의 20 완화
  5호. 일조 §61: 공동주택 + §86 ③항 인동거리 한정 — 현재 진단 외 (안내만)

설계: 각 calculator는 그대로 두고, 진단 엔진이 결과 dict를 받아서
이 모듈의 apply_* 함수로 사후 보정. 점수·pass 여부·notes 갱신.
"""
from __future__ import annotations

import json
from pathlib import Path

_LIMITS_PATH = Path(__file__).parent.parent / "config" / "zone_limits.json"
_LIMITS_CACHE: dict | None = None

_AGREEMENT_RATIO = 1.20  # 100분의 20 완화 = 1.2배
_LANDSCAPE_RATIO = 0.80  # 의무 100분의 20 완화 = 0.8배


def _load_legal_caps() -> dict:
    """국계법 시행령 §84/§85 법정 상한 — zone_limits.json 값."""
    global _LIMITS_CACHE
    if _LIMITS_CACHE is None:
        with open(_LIMITS_PATH, encoding="utf-8") as f:
            _LIMITS_CACHE = json.load(f)
    return _LIMITS_CACHE


def _zone_cap(category: str, zone_use: str) -> float | None:
    from services.zone_use_normalizer import lookup_limit
    data = _load_legal_caps().get(category, {})
    return lookup_limit(data, zone_use)


def apply_to_coverage(result: dict, *, applied: bool, zone_use: str) -> dict:
    """건폐율 결과에 협정 완화 (1.2배, 국계법 §84 캡)."""
    if not applied or result.get("limit_pct") is None:
        return result
    base = float(result["limit_pct"])
    legal_cap = _zone_cap("building_coverage_ratio", zone_use)
    new_limit = round(min(base * _AGREEMENT_RATIO, legal_cap or base * _AGREEMENT_RATIO), 2)
    if new_limit <= base:
        return result  # 이미 법정 상한 — 추가 완화 없음

    actual = float(result.get("actual_pct") or 0)
    passed = actual <= new_limit
    excess = max(0.0, actual - new_limit)
    score = _recalc_pct_score(actual, new_limit, passed)
    capped = base * _AGREEMENT_RATIO > new_limit

    note_extra = (
        f" · 🤝 건축협정 적용: 한도 {base}% → {new_limit}% "
        f"(시행령 §110의7 1호, 1.2배)"
    )
    if capped:
        note_extra += f" · 국계법 시행령 §84 상한 {legal_cap}%로 캡"

    return {
        **result,
        "limit_pct": new_limit,
        "pass": passed,
        "excess_pct": round(excess, 2),
        "score": max(0.0, round(score, 1)),
        "agreement_applied": True,
        "agreement_base_limit_pct": base,
        "agreement_legal_cap_pct": legal_cap,
        "notes": (result.get("notes") or "") + note_extra,
    }


def apply_to_far(result: dict, *, applied: bool, zone_use: str) -> dict:
    """용적률 결과에 협정 완화 (1.2배, 국계법 §85 캡).

    인증 완화(compute_relief)와 별도 — 협정은 추가 완화 항목.
    relief_info가 있어도 그 위에 1.2배 적용한 뒤 §85 캡으로 클램프.
    """
    if not applied or result.get("limit_pct") is None:
        return result
    base = float(result["limit_pct"])
    legal_cap = _zone_cap("floor_area_ratio", zone_use)
    new_limit = round(min(base * _AGREEMENT_RATIO, legal_cap or base * _AGREEMENT_RATIO), 2)
    if new_limit <= base:
        return result

    actual = float(result.get("actual_pct") or 0)
    passed = actual <= new_limit
    excess = max(0.0, actual - new_limit)
    score = _recalc_pct_score(actual, new_limit, passed)
    capped = base * _AGREEMENT_RATIO > new_limit

    note_extra = (
        f" · 🤝 건축협정 적용: 한도 {base}% → {new_limit}% "
        f"(시행령 §110의7 2호, 1.2배)"
    )
    if capped:
        note_extra += f" · 국계법 시행령 §85 상한 {legal_cap}%로 캡"

    return {
        **result,
        "limit_pct": new_limit,
        "pass": passed,
        "excess_pct": round(excess, 2),
        "score": max(0.0, round(score, 1)),
        "agreement_applied": True,
        "agreement_base_limit_pct": base,
        "agreement_legal_cap_pct": legal_cap,
        "notes": (result.get("notes") or "") + note_extra,
    }


def apply_to_landscape(
    result: dict, *, applied: bool, road_facing_integrated: bool
) -> dict:
    """조경 결과에 협정 완화 (의무 비율 0.8배).

    조건: 대지 조경을 '도로에 면하여 통합적으로 조성'할 때만 — §110의7 1호.
    면제 대상은 적용 불가.
    """
    if not applied:
        return result
    if not road_facing_integrated:
        return {
            **result,
            "notes": (result.get("notes") or "")
            + " · ℹ️ 건축협정 조경 완화는 도로면 통합 조성 시에만 적용 가능 (§110의7 1호)",
        }
    if result.get("exempt") or result.get("required_pct") in (None, 0):
        return result
    base_pct = float(result["required_pct"])
    new_pct = round(base_pct * _LANDSCAPE_RATIO, 2)
    site_area_inferred = None
    if result.get("required_area_m2") and base_pct > 0:
        # required_area = site * base_pct / 100
        site_area_inferred = float(result["required_area_m2"]) * 100 / base_pct
    new_required_area = round(site_area_inferred * new_pct / 100, 2) if site_area_inferred else None

    actual_pct = float(result.get("actual_pct") or 0)
    passed = actual_pct >= new_pct
    deficit = (
        max(0.0, (new_required_area or 0) - (site_area_inferred or 0) * actual_pct / 100)
        if site_area_inferred else None
    )
    # score: pass면 10, 아니면 0 (단순화 — 기존 점수 곡선 재계산은 calculator 의존성 큼)
    score = 10.0 if passed else 0.0

    note_extra = (
        f" · 🤝 건축협정 적용: 의무 조경 {base_pct}% → {new_pct}% "
        f"(시행령 §110의7 1호, 0.8배 — 도로면 통합 조성)"
    )

    return {
        **result,
        "required_pct": new_pct,
        "required_area_m2": new_required_area if new_required_area is not None else result.get("required_area_m2"),
        "pass": passed,
        "deficit_m2": round(deficit, 2) if deficit is not None else result.get("deficit_m2"),
        "score": score,
        "agreement_applied": True,
        "agreement_base_required_pct": base_pct,
        "notes": (result.get("notes") or "") + note_extra,
    }


def apply_to_height(
    result: dict, *, applied: bool, road_width: float | None
) -> dict:
    """높이 결과에 협정 완화 (가로구역 최고높이 1.2배).

    조건: 너비 6미터 이상 도로 접함 — §110의7 4호.
    가로구역 최고높이가 지정된 경우(§60)에만 의미 — 미지정 시 안내만.
    """
    if not applied:
        return result

    if road_width is None or road_width < 6.0:
        return {
            **result,
            "notes": (result.get("notes") or "")
            + " · ℹ️ 건축협정 높이 완화는 너비 6m 이상 도로 접함 시에만 적용 (§110의7 4호)",
        }

    base_h = result.get("street_block_max_height_m")
    if base_h is None or base_h <= 0:
        return {
            **result,
            "notes": (result.get("notes") or "")
            + " · ℹ️ 건축협정 높이 완화는 가로구역 최고높이가 지정된 경우에만 의미 (§60·§110의7 4호)",
        }

    base_h = float(base_h)
    new_h = round(base_h * _AGREEMENT_RATIO, 2)
    actual = float(result.get("actual_height_m") or 0)
    passed = actual <= new_h

    # pass 재판정 후 score 단순 재산정
    score = 10.0 if passed else 0.0

    note_extra = (
        f" · 🤝 건축협정 적용: 가로구역 최고높이 {base_h}m → {new_h}m "
        f"(시행령 §110의7 4호, 1.2배)"
    )

    return {
        **result,
        "street_block_max_height_m": new_h,
        "road_height_limit_m": new_h,
        "pass": passed if result.get("pass") is not None else result.get("pass"),
        "score": score if result.get("score") is not None else result.get("score"),
        "agreement_applied": True,
        "agreement_base_height_m": base_h,
        "notes": (result.get("notes") or "") + note_extra,
    }


def _recalc_pct_score(actual: float, limit: float, passed: bool) -> float:
    """건폐율/용적률 공통 점수 곡선 — calculator와 동일 로직."""
    if not passed:
        return 0.0
    if limit <= 0:
        return 0.0
    ratio = actual / limit
    if ratio <= 0.7:
        return 10.0
    if ratio <= 0.9:
        return 10.0 - (ratio - 0.7) / 0.2 * 2.0
    return 8.0 - (ratio - 0.9) / 0.1 * 2.0
