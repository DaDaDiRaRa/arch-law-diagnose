"""높이·일조 계산기 (V1 간이 버전).

건축법 제60조: 가로구역별 최고높이 (도로 폭 기반)
건축법 제61조: 일조권 사선제한
  - 전용/일반주거지역: 정북방향 인접대지경계선 9m + 1:1.25 사선
  - 기타(공동주택 등): 정남방향 인접 4m + 1:0.5 사선

V1 제약: 대지 형상·인접 건물 정보 없음 → 이론 최고높이만 계산
"""
from __future__ import annotations

import json
import math
import os


def calculate(
    height: float,
    floors_above: int,
    zone_use: str,
    road_width: float | None = None,
) -> dict:
    """높이·일조 진단 결과.

    Returns:
      {
        category, actual_height_m, floors_above,
        road_height_limit_m, shadow_applies, shadow_slope,
        pass, score, confidence, source, notes
      }
    """
    # 도로 폭 기반 높이 한도 (건축법 제60조 — 1.5배 기준, 서울 기준)
    road_limit = _road_height_limit(road_width, zone_use)

    # 일조권 사선 적용 여부
    shadow_applies, shadow_slope = _shadow_info(zone_use)

    # 패스/실패 판정
    road_pass: bool | None = None
    if road_limit is not None:
        road_pass = height <= road_limit

    # 종합 판정
    if road_limit is not None:
        passed = road_pass
    else:
        passed = None  # 정보 부족

    # 점수 계산
    if passed is False:
        score = 0.0
    elif passed is True and road_limit:
        ratio = height / road_limit
        if ratio <= 0.7:
            score = 10.0
        elif ratio <= 0.9:
            score = round(10.0 - (ratio - 0.7) / 0.2 * 2.0, 1)
        else:
            score = round(8.0 - (ratio - 0.9) / 0.1 * 2.0, 1)
    else:
        score = None

    # 확신도: 도로 폭 미입력 시 낮음
    confidence = 3 if road_width else 2

    return {
        "category": "높이_일조",
        "actual_height_m": height,
        "floors_above": floors_above,
        "road_height_limit_m": road_limit,
        "shadow_applies": shadow_applies,
        "shadow_slope": shadow_slope,
        "pass": passed,
        "score": max(0.0, round(score, 1)) if score is not None else None,
        "confidence": confidence,
        "source": "건축법 제60조·제61조 (도로폭 기반 간이 계산)",
        "law_refs": _law_refs(),
        "notes": _notes(height, road_limit, shadow_applies, shadow_slope, road_width, zone_use),
    }


def _law_refs() -> list[dict]:
    return [
        {
            "name": "건축법 제60조 (건축물의 높이 제한)",
            "url": "https://www.law.go.kr/법령/건축법/제60조",
        },
        {
            "name": "건축법 제61조 (일조 등의 확보를 위한 높이 제한)",
            "url": "https://www.law.go.kr/법령/건축법/제61조",
        },
    ]


def _road_height_limit(road_width: float | None, zone_use: str) -> float | None:
    """건축법 제60조: 전면도로 폭 × 배율."""
    if not road_width:
        return None
    # 주거지역 1.5배, 기타 4배 (서울시 조례 기준 간략화)
    if any(k in zone_use for k in ["전용주거", "일반주거", "준주거"]):
        multiplier = 1.5
    else:
        multiplier = 4.0
    return round(road_width * multiplier, 1)


def _shadow_info(zone_use: str) -> tuple[bool, str]:
    """일조권 사선 적용 여부 + 기울기."""
    residential = any(k in zone_use for k in ["전용주거", "일반주거"])
    if residential:
        # 정북방향 인접대지경계선 9m + 1:1.25
        return True, "1:1.25 (정북 9m + 높이)"
    return False, ""


def _notes(
    height: float,
    road_limit: float | None,
    shadow: bool,
    slope: str,
    road_width: float | None,
    zone: str,
) -> str:
    parts: list[str] = []
    if road_limit:
        if height <= road_limit:
            parts.append(f"도로높이 제한 {road_limit}m 이하 충족 (실제 {height}m)")
        else:
            parts.append(f"[주의] 도로높이 제한 {road_limit}m 초과 (실제 {height}m, 초과 {height - road_limit:.1f}m)")
    else:
        parts.append(
            f"전면도로 폭 미입력 — 건축법 제60조 검토 불가 (도로 폭 입력 시 자동 계산)"
        )

    if shadow:
        parts.append(f"일조권 사선 적용 ({slope}). 정북 이격 거리 실측 검토 필요.")
    else:
        parts.append("일조권 사선 미적용 용도지역.")

    return " | ".join(parts)
