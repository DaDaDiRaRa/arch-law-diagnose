"""주차 계산기.

주차장법 시행령 별표 1 기준 부설주차 산정.
실제 지자체 조례는 더 엄격할 수 있음.
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
        os.path.join(os.path.dirname(__file__), "../../config/parking_standards.json")
    )
    with open(cfg, encoding="utf-8") as f:
        _STANDARDS = json.load(f)
    return _STANDARDS


def calculate(
    building_use: str,
    total_floor_area: float,
    provided_spaces: int | None = None,
    units: int | None = None,
    unit_exclusive_area: float | None = None,
) -> dict:
    """주차 진단 결과.

    Args:
      building_use: 건축물 용도
      total_floor_area: 연면적 (㎡)
      provided_spaces: 계획 주차 대수 (미입력 시 None → 법정 최소만 계산)
      units: 세대수 (공동주택)
      unit_exclusive_area: 세대 평균 전용면적 (공동주택)

    Returns:
      {category, required_spaces, provided_spaces, pass, deficit,
       score, confidence, source, notes}
    """
    standards = _load_standards()
    std = _find_standard(building_use, standards)

    required = _calc_required(building_use, total_floor_area, std, units, unit_exclusive_area)

    if provided_spaces is None:
        # 제공 대수 미입력: 요건만 표시
        return {
            "category": "주차",
            "required_spaces": required,
            "provided_spaces": None,
            "pass": None,
            "deficit": None,
            "score": None,
            "confidence": 3,
            "source": "주차장법 시행령 별표 1",
            "law_refs": _law_refs(),
            "notes": (
                f"법정 최소 주차 {required}대 필요 "
                f"({std.get('note', '')}). 계획 대수 입력 시 적합 여부 판정."
            ),
        }

    passed = provided_spaces >= required
    deficit = max(0, required - provided_spaces)

    if not passed:
        score = 0.0
    else:
        excess = provided_spaces - required
        ratio = excess / required if required > 0 else 1
        score = min(10.0, 7.0 + ratio * 3.0)

    return {
        "category": "주차",
        "required_spaces": required,
        "provided_spaces": provided_spaces,
        "pass": passed,
        "deficit": deficit,
        "score": round(score, 1),
        "confidence": 4,
        "source": "주차장법 시행령 별표 1",
        "law_refs": _law_refs(),
        "notes": _notes(passed, required, provided_spaces, deficit, std),
    }


def _law_refs() -> list[dict]:
    return [
        {
            "name": "주차장법 제19조 (부설주차장의 설치·관리)",
            "url": "https://www.law.go.kr/법령/주차장법/제19조",
        },
        {
            "name": "주차장법 시행령 별표 1 (부설주차장 설치기준)",
            "url": "https://www.law.go.kr/법령/주차장법시행령",
        },
    ]


def _find_standard(building_use: str, standards: dict) -> dict:
    s = standards.get("standards", {})
    if building_use in s:
        return s[building_use]
    # 부분 매칭
    for key, val in s.items():
        if building_use in key or key in building_use:
            return val
    return standards.get("default", {"type": "area_based", "unit_area": 200, "note": "기타(추정)"})


def _calc_required(
    building_use: str,
    total_floor_area: float,
    std: dict,
    units: int | None,
    unit_exclusive_area: float | None,
) -> int:
    if std["type"] == "unit_based" and units:
        # 공동주택 세대 기반
        thresholds = std.get("thresholds", [])
        ea = unit_exclusive_area or 85.0  # 미입력 시 85㎡ 가정
        ratio = 1.0
        for t in thresholds:
            max_ea = t.get("max_exclusive_area")
            if max_ea is None or ea <= max_ea:
                ratio = t["ratio"]
                break
        return math.ceil(units * ratio)

    # 면적 기반
    unit_area = std.get("unit_area", 200)
    min_units = std.get("min_units", 0)
    if total_floor_area <= unit_area and min_units == 0:
        return 0
    return max(min_units, math.ceil(total_floor_area / unit_area))


def _notes(passed: bool, required: int, provided: int, deficit: int, std: dict) -> str:
    if not passed:
        return (
            f"[주의] 주차 부족: 법정 {required}대 필요, 계획 {provided}대 ({deficit}대 부족). "
            f"인허가 불가. ({std.get('note', '')})"
        )
    return (
        f"주차 적합: 법정 {required}대 / 계획 {provided}대 "
        f"({provided - required}대 여유). ({std.get('note', '')})"
    )
