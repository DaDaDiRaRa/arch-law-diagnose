"""도시계획시설 저촉 진단 카테고리.

대지 좌표 + PNU(시·도 추정용) → SHP 폴리곤 교차 검사 →
다른 카테고리(건폐율/용적률 등)와 동일한 카드 구조로 변환.

판정:
  저촉 없음      → pass=True, score=10, confidence=5
  YELLOW 저촉   → pass=None, score=5, confidence=3 (검토 필요)
  RED 저촉      → pass=False, score=0, confidence=5
  좌표 없음     → pass=None, score=null, confidence=1
"""
from __future__ import annotations

import logging

from services.urban_facility import check_facility_conflict

logger = logging.getLogger(__name__)


def calculate(
    *,
    lat: float | None,
    lng: float | None,
    pnu: str | None = None,
    decision_notice_confirmed: bool = False,
    facilities: list[dict] | None = None,
) -> dict:
    """도시계획시설 저촉 카드.

    facilities(VWorld WFS 실시간 시설 목록)가 있으면 그것을, 없으면 로컬 SHP를 사용.
    """
    base = {
        "category": "도시계획시설",
        "actual_pct": None,
        "limit_pct": None,
        "pass": None,
        "excess_pct": 0.0,
        "score": None,
        "confidence": 1,
        "source": (
            "🗺 VWorld 도시계획시설 WFS (실시간)" if facilities is not None
            else "🗺 도시계획 결정도형 (SHP)"
        ),
        "law_refs": _law_refs(),
        "notes": "",
        "conflicts": [],
    }

    try:
        result = check_facility_conflict(lat=lat, lng=lng, pnu=pnu, facilities=facilities)
    except Exception as e:
        logger.warning("도시계획시설 검사 실패: %s", e)
        base["notes"] = "도시계획시설 조회 실패 — 별도 확인 필요"
        return base

    if not result["checked"]:
        base["notes"] = result["note"]
        return base

    severity = result["severity"]
    conflicts = result["conflicts"]
    base["conflicts"] = conflicts

    if severity == "GREEN":
        base["pass"] = True
        base["score"] = 10.0
        base["confidence"] = 5
        base["notes"] = "도시계획시설 저촉 없음 — 대지에 도시·군계획시설 부지가 포함되지 않음."
    elif severity == "YELLOW":
        base["pass"] = None
        base["score"] = 5.0
        base["confidence"] = 3
        base["notes"] = result["note"]
    else:  # RED
        if decision_notice_confirmed:
            base["pass"] = None
            base["score"] = 7.0
            base["confidence"] = 3
            base["notes"] = (
                result["note"]
                + " · 결정고시 확인됨 — 도시·군계획시설 실시계획 수립 및 시행 절차 진행 조건으로 조건부 처리"
                " (국토계획법 §64·§65). ⚠ 실시계획 인가·고시 전 착공 불가."
            )
        else:
            base["pass"] = False
            base["score"] = 0.0
            base["confidence"] = 5
            base["notes"] = result["note"]

    return base


def _law_refs() -> list[dict]:
    return [
        {
            "name": "국토계획법 제47조 (매수청구)",
            "url": "https://www.law.go.kr/법령/국토의계획및이용에관한법률/제47조",
        },
        {
            "name": "국토계획법 제64조 (도시·군계획시설부지에서의 개발행위)",
            "url": "https://www.law.go.kr/법령/국토의계획및이용에관한법률/제64조",
        },
        {
            "name": "국토계획법 제65조 (시행자의 매수)",
            "url": "https://www.law.go.kr/법령/국토의계획및이용에관한법률/제65조",
        },
    ]
