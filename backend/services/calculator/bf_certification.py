"""장애 없는 생활환경(BF) 인증 의무 판정.

근거: 장애인·노인·임산부 등의 편의증진 보장에 관한 법률 §10의2
"""
from __future__ import annotations

_MANDATORY_USES = (
    "공공업무시설", "공공업무", "청사", "관공서",
    "교육연구시설", "노유자시설", "의료시설",
    "운동시설", "문화및집회시설",
)


def calculate(
    *,
    building_use: str,
    applicant_type: str,
) -> dict:
    """BF 인증 의무 카드."""
    base = {
        "category": "BF 인증",
        "actual_pct": None,
        "limit_pct": None,
        "pass": True,
        "excess_pct": 0.0,
        "score": 10.0,
        "confidence": 5,
        "source": "장애인편의법 §10의2",
        "law_refs": _law_refs(),
        "notes": "BF 인증 의무 해당 없음.",
        "required_level": None,
        "guidelines": {},
    }

    is_public = applicant_type == "공공기관"
    is_mandatory_use = any(u in building_use for u in _MANDATORY_USES)

    if not (is_public or is_mandatory_use):
        return base

    required_level = "우수 (Excellent)" if is_public else "일반 (Certified)"
    guidelines = _get_bf_guidelines(building_use)

    base["pass"] = None
    base["score"] = 5.0
    base["confidence"] = 4
    base["required_level"] = required_level
    base["guidelines"] = guidelines
    base["notes"] = (
        f"BF 인증 의무 대상 — {required_level} 등급 이상 취득 필요."
        " 사용승인 전 인증서 제출."
    )
    return base


def _get_bf_guidelines(building_use: str) -> dict:
    guides: dict[str, str] = {
        "공통": "서울시 유니버설디자인 적용지침 + 행안부 공공부문 공간혁신",
    }
    if any(kw in building_use for kw in ("어린이집", "보육")):
        guides["어린이집"] = "서울시 복지시설 유니버설디자인 가이드라인"
    if "민원" in building_use:
        guides["민원실"] = "행안부 국민행복민원실 평가기준"
    return guides


def _law_refs() -> list[dict]:
    return [
        {
            "name": "장애인·노인·임산부 편의증진 보장에 관한 법률 §10의2 (BF 인증)",
            "url": "https://www.law.go.kr/법령/장애인노인임산부등의편의증진보장에관한법률/제10조의2",
        },
    ]
