"""건폐율 계산기.

건폐율 = 건축면적 / 대지면적 × 100 (%)
한도: zone_limits.json 기반 (국토계획법 시행령 별표)
"""
from __future__ import annotations

import json
import os

_LIMITS: dict[str, float] = {}


def _load_limits() -> dict[str, float]:
    global _LIMITS
    if _LIMITS:
        return _LIMITS
    cfg = os.path.join(os.path.dirname(__file__), "../../config/zone_limits.json")
    cfg = os.path.abspath(cfg)
    with open(cfg, encoding="utf-8") as f:
        _LIMITS = json.load(f)["building_coverage_ratio"]
    return _LIMITS


def calculate(
    building_area: float,
    site_area: float,
    zone_use: str,
    limit_override: float | None = None,
    source_override: str | None = None,
) -> dict:
    """건폐율 진단 결과 반환.

    limit_override: OrdinanceResolver가 결정한 조례 수치 (없으면 zone_limits.json 사용).
    source_override: "조례" | "시행령" 레이블.

    Returns:
      {
        category, actual_pct, limit_pct, pass, excess_pct,
        score (0~10), confidence (1~5), source, notes
      }
    """
    limits = _load_limits()

    actual_pct = (building_area / site_area) * 100 if site_area > 0 else 0.0

    if limit_override is not None:
        limit_pct = float(limit_override)
    else:
        limit_pct = _get_limit(limits, zone_use)

    if limit_pct is None:
        return _unknown_result(actual_pct, zone_use)

    passed = actual_pct <= limit_pct
    excess_pct = max(0.0, actual_pct - limit_pct)

    # 점수: 한도의 90% 이하 → 10점, 100% → 6점, 초과 → 0점
    if not passed:
        score = 0.0
    else:
        ratio = actual_pct / limit_pct if limit_pct > 0 else 0
        if ratio <= 0.7:
            score = 10.0
        elif ratio <= 0.9:
            score = round(10.0 - (ratio - 0.7) / 0.2 * 2.0, 1)
        else:
            score = round(8.0 - (ratio - 0.9) / 0.1 * 2.0, 1)

    source = source_override or "국토계획법 시행령 별표 (기본값, 조례 미적용)"

    return {
        "category": "건폐율",
        "actual_pct": round(actual_pct, 2),
        "limit_pct": limit_pct,
        "pass": passed,
        "excess_pct": round(excess_pct, 2),
        "score": max(0.0, round(score, 1)),
        "confidence": 5,
        "source": source,
        "law_refs": _law_refs(),
        "provenance": {
            "inputs": {"building_area": building_area, "site_area_used": site_area},
            "formula": "건폐율(%) = 건축면적 ÷ 대지면적 × 100",
            "computed": {
                "actual_pct": round(actual_pct, 2),
                "limit_pct": limit_pct,
                "excess_pct": round(excess_pct, 2),
            },
            "basis": source,
        },
        "notes": _notes(passed, actual_pct, limit_pct, zone_use),
    }


def _get_limit(limits: dict, zone_use: str) -> float | None:
    """표준명 정규화 후 정확 매칭. 매칭 실패 시 None ('확인필요' 처리)."""
    from services.zone_use_normalizer import lookup_limit
    return lookup_limit(limits, zone_use)


def _notes(passed: bool, actual: float, limit: float, zone: str) -> str:
    if not passed:
        return (
            f"건폐율 {actual:.1f}%로 {zone} 한도 {limit}% 초과 "
            f"({actual - limit:.1f}%p 초과). 건축면적 축소 필요."
        )
    margin = limit - actual
    return f"건폐율 {actual:.1f}% / 한도 {limit}% ({margin:.1f}%p 여유)"


def _unknown_result(actual_pct: float, zone_use: str) -> dict:
    return {
        "category": "건폐율",
        "actual_pct": round(actual_pct, 2),
        "limit_pct": None,
        "pass": None,
        "excess_pct": 0.0,
        "score": None,
        "confidence": 1,
        "source": "용도지역 미확인",
        "law_refs": _law_refs(),
        "notes": f"용도지역 '{zone_use}'에 해당하는 건폐율 한도를 확인할 수 없습니다.",
    }


def _law_refs() -> list[dict]:
    return [
        {
            "name": "건축법 제55조 (건폐율)",
            "url": "https://www.law.go.kr/법령/건축법/제55조",
        },
        {
            "name": "국토계획법 시행령 제84조 (용도지역의 건폐율)",
            "url": "https://www.law.go.kr/법령/국토의계획및이용에관한법률시행령/제84조",
        },
    ]
