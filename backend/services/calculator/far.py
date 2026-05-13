"""용적률 계산기.

용적률 = 지상층 연면적 합계 / 대지면적 × 100 (%)
※ 지하층, 주차장, 피로티 등은 용적률 산정 제외 (건축법 시행령 제119조)
  → V1에서는 사용자 입력 total_floor_area를 그대로 사용 (제외 면적 별도 입력 미구현)
"""
from __future__ import annotations

import json
import os

_LIMITS: dict[str, float] = {}


def _load_limits() -> dict[str, float]:
    global _LIMITS
    if _LIMITS:
        return _LIMITS
    cfg = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../config/zone_limits.json")
    )
    with open(cfg, encoding="utf-8") as f:
        _LIMITS = json.load(f)["floor_area_ratio"]
    return _LIMITS


def calculate(
    total_floor_area: float,
    site_area: float,
    zone_use: str,
    floors_below: int = 0,
) -> dict:
    """용적률 진단 결과.

    Returns:
      {
        category, actual_pct, limit_pct, pass, excess_pct,
        score, confidence, source, notes
      }
    """
    limits = _load_limits()
    actual_pct = (total_floor_area / site_area) * 100 if site_area > 0 else 0.0
    limit_pct = _get_limit(limits, zone_use)

    if limit_pct is None:
        return _unknown_result(actual_pct, zone_use)

    passed = actual_pct <= limit_pct
    excess_pct = max(0.0, actual_pct - limit_pct)

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

    note_extra = ""
    if floors_below > 0:
        note_extra = f" (지하 {floors_below}층 면적은 용적률 제외 대상이나 V1에서는 미분리)"

    return {
        "category": "용적률",
        "actual_pct": round(actual_pct, 2),
        "limit_pct": limit_pct,
        "pass": passed,
        "excess_pct": round(excess_pct, 2),
        "score": max(0.0, round(score, 1)),
        "confidence": 5,
        "source": "국토계획법 시행령 별표 (기본값, 조례 미적용)",
        "law_refs": _law_refs(),
        "notes": _notes(passed, actual_pct, limit_pct, zone_use) + note_extra,
    }


def _get_limit(limits: dict, zone_use: str) -> float | None:
    if zone_use in limits:
        return float(limits[zone_use])
    for key, val in limits.items():
        if zone_use in key or key in zone_use:
            return float(val)
    return None


def _notes(passed: bool, actual: float, limit: float, zone: str) -> str:
    if not passed:
        return (
            f"용적률 {actual:.1f}%로 {zone} 한도 {limit}% 초과 "
            f"({actual - limit:.1f}%p 초과). 연면적 축소 또는 지하층 전환 검토."
        )
    margin = limit - actual
    utilization = (actual / limit * 100) if limit > 0 else 0
    return (
        f"용적률 {actual:.1f}% / 한도 {limit}% "
        f"(활용률 {utilization:.0f}%, {margin:.1f}%p 여유)"
    )


def _unknown_result(actual_pct: float, zone_use: str) -> dict:
    return {
        "category": "용적률",
        "actual_pct": round(actual_pct, 2),
        "limit_pct": None,
        "pass": None,
        "excess_pct": 0.0,
        "score": None,
        "confidence": 1,
        "source": "용도지역 미확인",
        "law_refs": _law_refs(),
        "notes": f"용도지역 '{zone_use}'에 해당하는 용적률 한도를 확인할 수 없습니다.",
    }


def _law_refs() -> list[dict]:
    return [
        {
            "name": "건축법 제56조 (용적률)",
            "url": "https://www.law.go.kr/법령/건축법/제56조",
        },
        {
            "name": "건축법 시행령 제119조 (면적 등의 산정방법)",
            "url": "https://www.law.go.kr/법령/건축법시행령/제119조",
        },
        {
            "name": "국토계획법 시행령 제85조 (용도지역의 용적률)",
            "url": "https://www.law.go.kr/법령/국토의계획및이용에관한법률시행령/제85조",
        },
    ]
