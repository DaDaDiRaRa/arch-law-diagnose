"""범죄예방 건축기준 적용 대상 판정.

근거: 건축법 §53의2 + 시행령 §63의7 + 국토교통부 고시 제2021-930호
"""
from __future__ import annotations

_TARGET_USES = (
    "다가구주택", "공동주택", "다중주택", "기숙사",
    "문화및집회시설", "교육연구시설", "노유자시설", "수련시설",
    "업무시설", "숙박시설",
)

_CHECKS = [
    "출입구 조명·CCTV 설치",
    "필로티·주차장 조명 확보",
    "옥상·계단실 출입 통제",
    "외부 시야 확보 (사각지대 최소화)",
]


def calculate(*, building_use: str) -> dict:
    """범죄예방 건축기준 카드."""
    base = {
        "category": "범죄예방 건축기준",
        "actual_pct": None,
        "limit_pct": None,
        "pass": True,
        "excess_pct": 0.0,
        "score": 10.0,
        "confidence": 5,
        "source": "건축법 §53의2 + 국토교통부 고시 제2021-930호",
        "law_refs": _law_refs(),
        "notes": "범죄예방 건축기준 적용 대상 아님.",
        "checks": [],
    }

    is_target = any(u in building_use for u in _TARGET_USES)
    if not is_target:
        return base

    base["pass"] = None
    base["score"] = 5.0
    base["confidence"] = 4
    base["checks"] = _CHECKS
    base["notes"] = (
        "범죄예방 건축기준 적용 대상 — 설계 시 아래 항목 반영 필요."
        " 국토교통부 고시 제2021-930호 기준 준수."
    )
    return base


def _law_refs() -> list[dict]:
    return [
        {
            "name": "건축법 §53의2 (범죄예방 건축기준)",
            "url": "https://www.law.go.kr/법령/건축법/제53조의2",
        },
        {
            "name": "건축법 시행령 §63의7",
            "url": "https://www.law.go.kr/법령/건축법시행령/제63조의7",
        },
        {
            "name": "국토교통부 고시 제2021-930호 (범죄예방 건축기준)",
            "url": "https://www.law.go.kr/행정규칙/범죄예방건축기준",
        },
    ]
