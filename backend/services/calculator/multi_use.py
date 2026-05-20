"""다중이용건축물 / 준다중이용건축물 분류기.

건축법 시행령 §2 제17호 (다중이용) · 제17조의2 (준다중이용).

다중이용건축물 (§2-17):
  가목: 바닥면적 합계 5,000㎡ 이상
    - 문화및집회시설 (동물원·식물원 제외)
    - 종교시설
    - 판매시설
    - 운수시설 중 여객용 시설
    - 의료시설 중 종합병원
    - 숙박시설 중 관광숙박시설
  나목: 16층 이상인 건축물 (용도 무관)

준다중이용건축물 (§2-17의2):
  다중이용건축물 외 + 바닥면적 합계 1,000㎡ 이상
    - 위 가목 6가지 용도
    - 교육연구시설, 노유자시설, 운동시설,
      위락시설, 관광 휴게시설, 장례시설
"""
from __future__ import annotations

import re

# ── 다중이용건축물 용도 (§2-17 가목, 면적 5,000㎡ 이상 조건과 함께)
_MULTI_USES: tuple[str, ...] = (
    "문화및집회시설",
    "종교시설",
    "판매시설",
    "운수시설",       # 여객용 시설 한정; 세부 용도 미입력 시 보수적 적용
    "종합병원",       # 의료시설 중 종합병원
    "관광숙박시설",   # 숙박시설 중 관광숙박시설
)

# ── 준다중이용 추가 용도 (§2-17의2, 다중이용 6가지 + 아래 6가지)
_QUASI_EXTRA: tuple[str, ...] = (
    "교육연구시설",
    "노유자시설",
    "운동시설",
    "위락시설",
    "관광휴게시설",
    "장례시설",
)

_QUASI_USES: tuple[str, ...] = _MULTI_USES + _QUASI_EXTRA


def _norm(s: str) -> str:
    return re.sub(r"[\s·\-]", "", s).lower()


def _matches(building_use: str, candidates: tuple[str, ...]) -> bool:
    use_n = _norm(building_use)
    return any(_norm(c) in use_n or use_n in _norm(c) for c in candidates)


def classify(
    building_use: str,
    total_floor_area: float,
    floors_above: int,
) -> dict:
    """다중이용 / 준다중이용 분류 결과 반환.

    Returns:
      {
        category, classification, pass, score, confidence,
        source, law_refs, notes,
        required_spaces (None — 정보 카드),
      }
    """
    use_n = _norm(building_use)

    is_multi_use_by_use = _matches(building_use, _MULTI_USES)
    is_multi_use = (
        (is_multi_use_by_use and total_floor_area >= 5000)
        or floors_above >= 16
    )
    is_quasi = (
        not is_multi_use
        and _matches(building_use, _QUASI_USES)
        and total_floor_area >= 1000
    )

    # 부가 주석 — 보수적 적용 안내
    caveats: list[str] = []
    if _norm("운수시설") in use_n and is_multi_use_by_use:
        caveats.append(
            "운수시설 중 여객용 시설만 해당 — 여객 이외 화물·창고 기능 중심이라면 제외 가능."
        )
    if _norm("의료시설") in use_n and not _norm("종합병원") in use_n:
        caveats.append(
            "의료시설 중 종합병원만 해당 — 병원·의원·요양병원 등은 해당 없음."
        )
    if _norm("숙박시설") in use_n and not _norm("관광숙박") in use_n:
        caveats.append(
            "숙박시설 중 관광숙박시설(호텔·콘도 등)만 해당 — 일반 숙박시설은 제외."
        )

    if is_multi_use:
        classification = "다중이용건축물"
        basis_parts: list[str] = []
        if floors_above >= 16:
            basis_parts.append(f"16층 이상 ({floors_above}층)")
        if is_multi_use_by_use and total_floor_area >= 5000:
            basis_parts.append(f"{building_use} + 바닥면적 {total_floor_area:,.0f}㎡ ≥ 5,000㎡")
        basis = " / ".join(basis_parts)
        implications = [
            "건축위원회 사전심의 대상 (건축법 §4의2)",
            "피난·방화시설 강화 적용 (시행령 §34, §39, §56)",
            "정기점검(2년마다) 의무 (건축법 §35)",
        ]
        notes = (
            f"[다중이용건축물] {basis}. "
            + "설계 단계부터 피난·방화 계획 강화 및 건축위원회 심의 일정 사전 반영 필요."
        )
        confidence = 4
    elif is_quasi:
        classification = "준다중이용건축물"
        notes = (
            f"[준다중이용건축물] {building_use}, 바닥면적 {total_floor_area:,.0f}㎡ ≥ 1,000㎡. "
            "피난·방화시설 점검 의무 (건축법 §35의2) 및 관련 기준 확인 필요."
        )
        implications = [
            "피난·방화시설 정기점검 의무 (건축법 §35의2)",
            "범죄예방 건축기준 적용 여부 확인 (건축법 §53의2)",
        ]
        confidence = 4
    else:
        classification = "해당없음"
        notes = (
            f"다중이용·준다중이용건축물 해당 없음 "
            f"({building_use}, {total_floor_area:,.0f}㎡, {floors_above}층)."
        )
        implications = []
        confidence = 4

    if caveats:
        notes += " ※ " + " / ".join(caveats)

    return {
        "category": "다중이용건축물",
        "classification": classification,
        "pass": None,      # 정보 카드 — pass 개념 없음
        "score": None,
        "confidence": confidence,
        "source": "📋 건축법 시행령 §2-17·17의2",
        "law_refs": [
            {
                "name": "건축법 시행령 §2 제17호 (다중이용건축물)",
                "url": "https://www.law.go.kr/법령/건축법시행령/제2조",
            },
            {
                "name": "건축법 시행령 §2 제17조의2 (준다중이용건축물)",
                "url": "https://www.law.go.kr/법령/건축법시행령/제2조",
            },
        ],
        "implications": implications,
        "notes": notes,
    }
