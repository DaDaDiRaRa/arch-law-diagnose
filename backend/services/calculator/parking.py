"""주차 계산기.

주차장법 시행령 별표 1 기준 부설주차 산정.
실제 지자체 조례는 더 엄격할 수 있음.

count_based 타입 (별표 1 제6호):
  - 골프장: 홀 수 × 10대
  - 골프연습장: 타석 수 × 1대
  - 옥외수영장: 정원 ÷ 15 대 (올림)
  - 관람장: 정원 ÷ 100 대 (올림)
  → capacity 파라미터로 홀/타석/정원 수 전달.
"""
from __future__ import annotations

import json
import math
import os
import re

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


def _norm(s: str) -> str:
    """공백·특수문자 제거 후 소문자화 — 매칭 정규화."""
    return re.sub(r"[\s ·\-]", "", s).lower()


def calculate(
    building_use: str,
    total_floor_area: float,
    provided_spaces: int | None = None,
    units: int | None = None,
    unit_exclusive_area: float | None = None,
    capacity: int | None = None,
) -> dict:
    """주차 진단 결과.

    Args:
      building_use: 건축물 용도
      total_floor_area: 연면적 (㎡)
      provided_spaces: 계획 주차 대수 (미입력 시 None → 법정 최소만 계산)
      units: 세대수 (공동주택)
      unit_exclusive_area: 세대 평균 전용면적 (공동주택)
      capacity: 홀 수(골프장) / 타석 수(골프연습장) / 정원(옥외수영장·관람장)

    Returns:
      {category, required_spaces, provided_spaces, pass, deficit,
       score, confidence, source, notes}
    """
    standards = _load_standards()

    # 버그3: 법령상 제외 항목 먼저 체크 — 별도 기준 미확인 상태
    excluded_msg = _check_excluded(building_use, standards)
    if excluded_msg:
        return {
            "category": "주차",
            "required_spaces": None,
            "provided_spaces": provided_spaces,
            "pass": None,
            "deficit": None,
            "score": None,
            "confidence": 2,
            "source": "📋 주차장법 시행령 별표 1",
            "law_refs": _law_refs(),
            "notes": f"[확인필요] {excluded_msg}",
        }

    std = _find_standard(building_use, standards)

    # count_based (골프장·골프연습장·옥외수영장·관람장): capacity 미입력 시 계산 불가
    if std["type"] == "count_based" and not capacity:
        count_unit = std.get("count_unit", "단위")
        return {
            "category": "주차",
            "required_spaces": None,
            "provided_spaces": provided_spaces,
            "pass": None,
            "deficit": None,
            "score": None,
            "confidence": 2,
            "source": "📋 주차장법 시행령 별표 1",
            "law_refs": _law_refs(),
            "notes": (
                f"{count_unit} 기반 주차 산정 — {count_unit} 수 미입력으로 계산 불가. "
                f"{count_unit} 수를 입력해주세요. ({std.get('note', '')})"
            ),
        }

    # 버그1: 세대 기반 용도인데 세대수 미입력 → 면적 기반으로 잘못 계산되는 오류 방지
    if std["type"] == "unit_based" and not units:
        return {
            "category": "주차",
            "required_spaces": None,
            "provided_spaces": provided_spaces,
            "pass": None,
            "deficit": None,
            "score": None,
            "confidence": 2,
            "source": "📋 주차장법 시행령 별표 1",
            "law_refs": _law_refs(),
            "notes": (
                f"세대 기반 주차 산정 — 세대수 미입력으로 계산 불가. "
                f"세대수와 세대 평균 전용면적을 입력해주세요. ({std.get('note', '')})"
            ),
        }

    required = _calc_required(building_use, total_floor_area, std, units, unit_exclusive_area, capacity)

    provenance = {
        "inputs": {
            "building_use": building_use,
            "total_floor_area": total_floor_area,
            "units": units,
            "unit_exclusive_area": unit_exclusive_area,
            "capacity": capacity,
        },
        "formula": f"주차장법 시행령 별표1 부설주차 산정 — {std.get('note', '')}",
        "computed": {"required_spaces": required, "provided_spaces": provided_spaces},
        "basis": "주차장법 시행령 별표 1",
    }

    if provided_spaces is None:
        return {
            "category": "주차",
            "required_spaces": required,
            "provided_spaces": None,
            "pass": None,
            "deficit": None,
            "score": None,
            "confidence": 3,
            "source": "📋 주차장법 시행령 별표 1",
            "law_refs": _law_refs(),
            "provenance": provenance,
            "notes": (
                f"법정 최소 주차 {required}대 필요 "
                f"({std.get('note', '')}). 계획 대수 입력 시 적합 여부 판정. "
                f"※ 지자체 조례로 강화 가능 — 자치법규 확인 권장."
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
        "source": "📋 주차장법 시행령 별표 1",
        "law_refs": _law_refs(),
        "provenance": provenance,
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


def _check_excluded(building_use: str, standards: dict) -> str | None:
    """법령상 '제외' 항목이면 사유 메시지 반환, 아니면 None."""
    excluded = standards.get("excluded_uses", {})
    use_norm = _norm(building_use)
    for key, msg in excluded.items():
        if _norm(key) in use_norm or use_norm in _norm(key):
            return msg
    return None


def _find_standard(building_use: str, standards: dict) -> dict:
    s = standards.get("standards", {})
    aliases = standards.get("aliases", {})
    default = standards.get("default", {"type": "area_based", "unit_area": 300, "note": "기타(추정)"})

    # 1단계: 정확 매칭
    if building_use in s:
        return s[building_use]

    # 2단계: alias 매칭 (공백 정규화 포함)
    use_norm = _norm(building_use)
    for alias, canonical in aliases.items():
        if use_norm == _norm(alias):
            return s.get(canonical, default)

    # 3단계: 정규화 정확 매칭 (공백·특수문자 무시)
    for key, val in s.items():
        if _norm(key) == use_norm:
            return val

    # 4단계: alias의 정규화 매칭
    for alias, canonical in aliases.items():
        if _norm(alias) in use_norm or use_norm in _norm(alias):
            return s.get(canonical, default)

    # 5단계: 정규화 부분 매칭 — 가장 긴 키 우선
    best_key, best_val = "", None
    for key, val in s.items():
        key_norm = _norm(key)
        if (use_norm in key_norm or key_norm in use_norm) and len(key) > len(best_key):
            best_key, best_val = key, val
    if best_val is not None:
        return best_val

    return default


def _calc_required(
    building_use: str,
    total_floor_area: float,
    std: dict,
    units: int | None,
    unit_exclusive_area: float | None,
    capacity: int | None = None,
) -> int:
    # count_based — 별표 1 제6호 (골프장·골프연습장·옥외수영장·관람장)
    if std["type"] == "count_based" and capacity:
        rate = std.get("rate", 1)
        rate_per = std.get("rate_per", 1)
        return math.ceil(capacity / rate_per * rate)

    # 단독주택 누적식 — 시행령 별표 1
    if std["type"] == "cumulative":
        exempt = std.get("exempt_max_m2", 50)         # 50㎡ 이하 면제
        single = std.get("single_unit_max_m2", 150)   # 150㎡ 이하 1대
        incr = std.get("incremental_unit_m2", 100)    # 150㎡ 초과분 100㎡당 +1
        if total_floor_area <= exempt:
            return 0
        if total_floor_area <= single:
            return 1
        return 1 + math.ceil((total_floor_area - single) / incr)

    # 공동주택 등 세대 기반 — 주택건설기준규정 §27
    if std["type"] == "unit_based" and units:
        thresholds = std.get("thresholds", [])
        ea = unit_exclusive_area or 85.0  # 미입력 시 85㎡ 가정 (전용면적 60㎡ 초과 분기)
        ratio = 1.0
        for t in thresholds:
            max_ea = t.get("max_exclusive_area")
            if max_ea is None or ea <= max_ea:
                ratio = t["ratio"]
                break
        return math.ceil(units * ratio)

    # 면적 기반 — 시행령 별표 1
    unit_area = std.get("unit_area", 300)
    min_units = std.get("min_units", 0)
    if total_floor_area <= 0:
        return 0
    return max(min_units, math.ceil(total_floor_area / unit_area))


def _notes(passed: bool, required: int, provided: int, deficit: int, std: dict) -> str:
    suffix = " ※ 지자체 조례로 강화 가능 — 자치법규 확인 권장."
    if not passed:
        return (
            f"[주의] 주차 부족: 법정 {required}대 필요, 계획 {provided}대 ({deficit}대 부족). "
            f"인허가 불가. ({std.get('note', '')}){suffix}"
        )
    return (
        f"주차 적합: 법정 {required}대 / 계획 {provided}대 "
        f"({provided - required}대 여유). ({std.get('note', '')}){suffix}"
    )
