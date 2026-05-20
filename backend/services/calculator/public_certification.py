"""공공기관 의무 인증 판정.

중앙행정기관·지방자치단체·공공기관·교육기관이 소유/관리하는 건축물에 적용.
근거법:
  - 녹색건축물 조성 지원법 §16·§17·§18 + 동법 시행령 §11조의3·§12
  - 신에너지 및 재생에너지 개발·이용·보급 촉진법 시행령 §15
  - 생태면적률: 광역시·도 조례 (지자체별 상이)

의무인증 적용 조건:
  [녹색건축 인증 §16, 시행령 §11조의3]
    - 대상 기관: 중앙행정기관·지방자치단체·공공기관·교육기관 (시행령 §9②)
    - 연면적 3,000㎡ 이상, 신축·재축·증축

  [제로에너지건축물 인증 §17, 시행령 §12④]
    - 위 대상 기관 + 연면적 1,000㎡ 이상
    - 제로에너지건축물 인증에 관한 규칙 §5조의2에 따른 용도:
      건축법 시행령 별표1 제5호~제16호, 제23호, 제24호, 제26호~제28호
      (별표1 원문 대조 2026-05-20: 제5=문화집회, 제6=종교, 제7=판매, 제8=운수,
       제9=의료, 제10=교육연구, 제11=노유자, 제12=수련, 제13=운동, 제14=업무,
       제15=숙박, 제16=위락, 제23=교정·군사, 제24=방송통신, 제26=묘지관련,
       제27=관광휴게, 제28=장례)

  [BEMS §18]
    - 위 대상 기관 + 연면적 3,000㎡ 이상 (§11조의3 기준 준용)
"""
from __future__ import annotations

# 녹색건축·BEMS 의무인증 최소 연면적 (시행령 §11조의3 제3호)
_MIN_GFA_GREEN_M2 = 3_000
# 제로에너지건축물 의무인증 최소 연면적 (시행령 §12조④제1호)
_MIN_GFA_ZEB_M2 = 1_000

# ZEB 의무 대상 용도 — 건축법 시행령 별표1 제5~16호, 23호, 24호, 26~28호
# (제로에너지건축물 인증에 관한 규칙 §5조의2, 2025.10.1 시행)
_ZEB_MANDATORY_USES: frozenset[str] = frozenset({
    # 제5호: 문화 및 집회시설
    "문화및집회시설", "공연장", "집회장", "관람장", "전시장", "동식물원",
    # 제6호: 종교시설
    "종교시설",
    # 제7호: 판매시설
    "판매시설", "도매시장", "소매시장",
    # 제8호: 운수시설
    "운수시설",
    # 제9호: 의료시설
    "의료시설", "병원", "격리병원",
    # 제10호: 교육연구시설
    "교육연구시설", "학교", "도서관", "연구소", "학원",
    # 제11호: 노유자시설
    "노유자시설",
    # 제12호: 수련시설
    "수련시설",
    # 제13호: 운동시설
    "운동시설", "골프연습장",
    # 제14호: 업무시설
    "업무시설", "오피스텔", "공공업무시설",
    # 제15호: 숙박시설
    "숙박시설", "관광숙박시설",
    # 제16호: 위락시설
    "위락시설",
    # 제23호: 교정시설 (2023.9.12 개정으로 교정 및 군사시설에서 분리됨)
    # ※ 제23호의2(국방·군사시설)는 §5조의2에 미포함 → ZEB 의무 아님
    "교정시설",
    # 제24호: 방송통신시설
    "방송통신시설",
    # 제26호: 묘지관련시설
    "묘지관련시설",
    # 제27호: 관광 휴게시설
    "관광휴게시설",
    # 제28호: 장례시설
    "장례시설", "장례식장",
})

# ZEB 의무 대상이 아닌 것으로 확인된 용도 (제1~4호, 17~22호, 25호)
_ZEB_EXEMPT_USES: frozenset[str] = frozenset({
    "단독주택", "다가구주택", "다중주택",          # 제1호
    "공동주택", "아파트", "연립주택", "다세대주택",  # 제2호
    "제1종근린생활시설", "제2종근린생활시설", "근린생활시설",  # 제3~4호
    "공장",                                         # 제17호
    "창고시설", "창고",                             # 제18호
    "위험물저장및처리시설",                          # 제19호
    "자동차관련시설",                                # 제20호
    "동물및식물관련시설", "동물 및 식물 관련 시설", # 제21호
    "발전시설",                                      # 제25호
})


def _get_renewable_ratio(permit_year: int) -> str:
    """연도별 신재생에너지 공급 의무비율 — 신에너지법 시행령 §15 별표 2.

    별표 2 원문 대조 완료 (개정 2020.9.29, 2026-05-20 확인):
      2020~2021: 30%, 2022~2023: 32%, 2024~2025: 34%,
      2026~2027: 36%, 2028~2029: 38%, 2030 이후: 40%
    """
    table = {
        2020: 30, 2022: 32, 2024: 34, 2026: 36, 2028: 38, 2030: 40,
    }
    ratio = max(v for y, v in table.items() if permit_year >= y)
    return f"{ratio}% (시행령 §15 별표 2, {permit_year}년 기준)"


def calculate(
    *,
    building_use: str,
    applicant_type: str,
    permit_year: int = 2026,
    gross_floor_area: float = 0,  # 연면적 (㎡) — 의무인증 여부 판정에 사용
) -> dict:
    """공공기관 의무 인증 카드.

    공공기관이 아니면 pass=True, score=10, items=[].
    공공기관이면 법정 의무 인증 목록 반환.
    """
    base = {
        "category": "공공시설 의무 인증",
        "actual_pct": None,
        "limit_pct": None,
        "pass": True,
        "excess_pct": 0.0,
        "score": 10.0,
        "confidence": 5,
        "source": "녹색건축물 조성 지원법 §16·§17·§18 / 동법 시행령 §11조의3·§12",
        "law_refs": _law_refs(),
        "notes": "공공기관 발주 아님 — 의무 인증 해당 없음.",
        "items": [],
    }

    if applicant_type != "공공기관":
        return base

    items = []
    zeb_use_status = _classify_zeb_use(building_use)

    # ① 녹색건축 인증: 연면적 3,000㎡ 이상 (시행령 §11조의3 제3호)
    if gross_floor_area >= _MIN_GFA_GREEN_M2:
        items.append({
            "name": "녹색건축물 인증",
            "required_level": "최우수",
            "law": "녹색건축물 조성 지원법 §16 / 동법 시행령 §11조의3",
            "url": "https://www.law.go.kr/법령/녹색건축물조성지원법/제16조",
        })

    # ② 제로에너지건축물 인증: 연면적 1,000㎡ 이상 + 의무 용도 (시행령 §12④ + 인증규칙 §5조의2)
    if gross_floor_area >= _MIN_GFA_ZEB_M2:
        if zeb_use_status == "mandatory":
            items.append({
                "name": "제로에너지건축물 인증",
                "required_level": "4등급 이상 (시행령 §12④제1호)",
                "law": "녹색건축물 조성 지원법 §17 / 동법 시행령 §12 / 제로에너지건축물 인증에 관한 규칙 §5조의2",
                "url": "https://www.law.go.kr/법령/녹색건축물조성지원법/제17조",
            })
        elif zeb_use_status == "unknown":
            items.append({
                "name": "제로에너지건축물 인증 (용도 확인 필요)",
                "required_level": "4등급 이상 해당 여부 — 용도가 건축법 시행령 별표1 제5~16호, 23·24·26~28호인지 확인",
                "law": "제로에너지건축물 인증에 관한 규칙 §5조의2",
                "url": "https://www.law.go.kr/법령/녹색건축물조성지원법/제17조",
            })
        # zeb_use_status == "exempt": ZEB 의무 미해당, 추가 안 함

    # ③ BEMS: 연면적 3,000㎡ 이상 (시행령 §11조의3 기준 준용)
    if gross_floor_area >= _MIN_GFA_GREEN_M2:
        items.append({
            "name": "건축물 에너지관리시스템 (BEMS)",
            "required_level": "구축",
            "law": "녹색건축물 조성 지원법 §18",
            "url": "https://www.law.go.kr/법령/녹색건축물조성지원법/제18조",
        })

    items.append({
        "name": "신재생에너지 공급의무비율",
        "required_level": _get_renewable_ratio(permit_year),
        "law": f"신에너지 및 재생에너지 개발·이용·보급 촉진법 시행령 §15 (공급의무비율, {permit_year}년 기준)",
        "url": "https://www.law.go.kr/법령/신에너지및재생에너지개발이용보급촉진법시행령/제15조",
    })
    items.append({
        "name": "생태면적률",
        "required_level": "기준 충족",
        "law": "서울시 생태면적률 운영지침 (광역시·도 조례)",
        "url": "",
    })

    base["pass"] = None  # 인증 완료 전까지 확인 필요
    base["score"] = 5.0
    base["confidence"] = 4

    if gross_floor_area == 0:
        base["notes"] = (
            "공공기관 발주 건축물 — 연면적 미입력으로 녹색건축 의무인증 대상 여부 판정 불가."
            f" 연면적 3,000㎡ 이상이면 아래 항목 이행 필요."
        )
    elif gross_floor_area < _MIN_GFA_ZEB_M2:
        base["notes"] = (
            f"공공기관 발주 건축물 (연면적 {gross_floor_area:,.0f}㎡, 1,000㎡ 미만)"
            " — 녹색건축·ZEB·BEMS 의무인증 대상 제외. 신재생에너지·생태면적률은 별도 확인."
        )
    elif gross_floor_area < _MIN_GFA_GREEN_M2:
        zeb_note = {
            "mandatory": "ZEB 4등급 이상 의무 (인증규칙 §5조의2 해당 용도)",
            "exempt": "ZEB 의무 미해당 용도",
            "unknown": "ZEB 의무 여부 — 용도(별표1 제5~16·23·24·26~28호 해당 여부) 확인 필요",
        }[zeb_use_status]
        base["notes"] = (
            f"공공기관 발주 건축물 (연면적 {gross_floor_area:,.0f}㎡, 1,000㎡ 이상 3,000㎡ 미만)"
            f" — 녹색건축·BEMS 의무 대상 아님. {zeb_note}."
        )
    else:
        zeb_note = {
            "mandatory": "ZEB 4등급 이상 의무 포함",
            "exempt": "ZEB 의무 미해당 용도 (별표1 제17~22호 등)",
            "unknown": "ZEB 의무 여부 별도 확인 필요 (건축법 시행령 별표1 용도 확인)",
        }[zeb_use_status]
        base["notes"] = (
            f"공공기관 발주 건축물 (연면적 {gross_floor_area:,.0f}㎡)"
            f" — 아래 {len(items)}종 의무 인증 이행 필요. {zeb_note}."
            " 인증 미완료 시 사용승인 반려 가능."
        )

    base["items"] = items
    return base


def _classify_zeb_use(building_use: str) -> str:
    """건축법 시행령 별표1 기준 ZEB 의무 적용 여부 판정.

    Returns:
      "mandatory" — §5조의2 해당 용도 (별표1 제5~16호, 23·24·26~28호)
      "exempt"    — 별표1 제1~4호, 17~22호, 25호 (ZEB 의무 대상 아님)
      "unknown"   — 목록에 없는 용도, 별표1 원문 확인 필요
    """
    if building_use in _ZEB_MANDATORY_USES:
        return "mandatory"
    if building_use in _ZEB_EXEMPT_USES:
        return "exempt"
    return "unknown"


def _law_refs() -> list[dict]:
    return [
        {
            "name": "녹색건축물 조성 지원법 §16 (녹색건축 인증)",
            "url": "https://www.law.go.kr/법령/녹색건축물조성지원법/제16조",
        },
        {
            "name": "녹색건축물 조성 지원법 §17 + 시행령 §12④ (ZEB 인증 의무)",
            "url": "https://www.law.go.kr/법령/녹색건축물조성지원법/제17조",
        },
        {
            "name": "제로에너지건축물 인증에 관한 규칙 §5조의2 (의무 대상 건축물 용도)",
            "url": "https://www.law.go.kr/법령/제로에너지건축물인증에관한규칙/제5조의2",
        },
        {
            "name": "녹색건축물 조성 지원법 §18 (BEMS)",
            "url": "https://www.law.go.kr/법령/녹색건축물조성지원법/제18조",
        },
        {
            "name": "신에너지 및 재생에너지 개발·이용·보급 촉진법 시행령 §15 (연도별 공급의무비율)",
            "url": "https://www.law.go.kr/법령/신에너지및재생에너지개발이용보급촉진법시행령/제15조",
        },
    ]
