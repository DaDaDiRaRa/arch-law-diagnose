"""중첩 지구·구역 검토 — 정보 카드 (가중치 0).

VWorld 또는 사용자 입력으로 받은 zone_district / zone_area 문자열을
키워드 매칭으로 파싱, 각 지구·구역별 행위 제한 개요를 반환한다.

설계 원칙:
- 특정 지구명 하드코딩 금지 — 키워드로 매칭하여 전국 범용으로 동작.
- 자동 판정 없음 (pass=None) — 행위 제한 세부 내용은 허가권자 확인 필수.
- 중첩 지구가 없으면 빈 items=[], pass=True (이 카드는 신호에 영향 없음).
"""
from __future__ import annotations

from typing import TypedDict


class _ZoneDef(TypedDict):
    keywords: list[str]        # zone_district/zone_area 문자열에서 매칭할 키워드 (OR 조건)
    display_name: str          # 카드에 표시할 지구·구역 명칭
    restriction_summary: str   # 행위 제한 개요 (1~2문장)
    law: str                   # 근거 법률
    url: str                   # 법령 링크


_ZONE_DEFS: list[_ZoneDef] = [
    {
        "keywords": ["교육환경보호"],
        "display_name": "교육환경보호구역",
        "restriction_summary": (
            "학교 경계로부터 절대보호구역(50m 이내) · 상대보호구역(200m 이내)으로 구분. "
            "절대보호구역은 유해시설 전면 금지, 상대보호구역은 교육감 심의를 거쳐 일부 허용."
        ),
        "law": "교육환경 보호에 관한 법률 §8·§9",
        "url": "https://www.law.go.kr/법령/교육환경보호에관한법률",
    },
    {
        "keywords": ["대공방어", "대공방어협조"],
        "display_name": "대공방어협조구역",
        "restriction_summary": (
            "국방부 고시 해발고도 제한 이하로 건축물 최고높이 규제. "
            "건물 높이(해발 기준) = 대지 지반고 + 건물 높이가 고시 해발고도 미만이어야 함. "
            "군사기지 및 군사시설 보호법에 의해 국방부장관 협의 필요."
        ),
        "law": "군사기지 및 군사시설 보호법 §13",
        "url": "https://www.law.go.kr/법령/군사기지및군사시설보호법",
    },
    {
        "keywords": ["가축사육제한"],
        "display_name": "가축사육제한구역",
        "restriction_summary": (
            "지자체 조례로 지정된 구역 내 축사·가축 사육 제한. "
            "공공업무·주거·교육 용도 건축물에는 통상 직접 영향 없으나, "
            "구역 내 임시가설 축사 설치 금지 확인 필요."
        ),
        "law": "가축분뇨의 관리 및 이용에 관한 법률 §8",
        "url": "https://www.law.go.kr/법령/가축분뇨의관리및이용에관한법률",
    },
    {
        "keywords": ["폐기물매립", "폐기물 매립", "매립시설 설치제한", "매립시설설치제한"],
        "display_name": "폐기물매립시설 설치제한지역",
        "restriction_summary": (
            "한강·낙동강·금강·영산강 수계 등 수변지역에 폐기물매립시설 설치 금지. "
            "건축물 자체에는 직접 제한 없으나, 공사 중 폐기물 처리 계획 및 "
            "지하수 오염 방지 대책 수립 필요. 인허가 시 환경부 협의 대상 여부 확인."
        ),
        "law": "폐기물처리시설 설치촉진 및 주변지역지원 등에 관한 법률 §5",
        "url": "https://www.law.go.kr/법령/폐기물처리시설설치촉진및주변지역지원등에관한법률",
    },
    {
        "keywords": ["문화재보호", "역사문화환경", "문화재현상변경"],
        "display_name": "문화재보호구역·역사문화환경보존지역",
        "restriction_summary": (
            "문화재 경계 500m(또는 고시 범위) 이내 건축 시 현상변경 허가 필요. "
            "높이·색채·외관 등에 심의 기준 적용. 문화재청(허가권자) 협의 필수."
        ),
        "law": "문화재보호법 §35 / 역사문화환경 보존지역 현상변경 기준",
        "url": "https://www.law.go.kr/법령/문화재보호법",
    },
    {
        "keywords": ["수변구역", "4대강수계", "한강수계", "낙동강수계", "금강수계", "영산강수계"],
        "display_name": "수변구역",
        "restriction_summary": (
            "한강·낙동강·금강·영산강 수계 수변구역 내 오염 유발 시설 설치 금지 및 제한. "
            "오폐수 배출 업종 입지 제한, 비점오염 방지 시설 의무 설치."
        ),
        "law": "한강수계 상수원수질개선 및 주민지원 등에 관한 법률 §5",
        "url": "https://www.law.go.kr/법령/한강수계상수원수질개선및주민지원등에관한법률",
    },
    {
        "keywords": ["특별대책지역", "환경정책기본법", "수도권정비"],
        "display_name": "특별대책지역·수도권정비권역",
        "restriction_summary": (
            "환경부 지정 특별대책지역 또는 수도권정비계획법 권역(과밀억제·성장관리·자연보전) 내 "
            "대규모 시설 입지 제한, 환경부·국토부 심의 필요."
        ),
        "law": "환경정책기본법 §38 / 수도권정비계획법 §7·§8",
        "url": "https://www.law.go.kr/법령/환경정책기본법",
    },
    {
        "keywords": ["고도지구", "최고고도", "최저고도"],
        "display_name": "고도지구",
        "restriction_summary": (
            "국토계획법에 의한 고도지구 지정 — 건축물 최고높이 또는 최저높이 제한. "
            "국토계획법 시행령 §79에 따라 허가권자가 세부 기준 고시."
        ),
        "law": "국토의 계획 및 이용에 관한 법률 §37 / 시행령 §79",
        "url": "https://www.law.go.kr/법령/국토의계획및이용에관한법률",
    },
    {
        "keywords": ["경관지구"],
        "display_name": "경관지구",
        "restriction_summary": (
            "국토계획법 경관지구 내 건축물의 건폐율·높이·형태·색채 등 추가 제한. "
            "지자체 경관 조례 세부 기준 확인 필요."
        ),
        "law": "국토의 계획 및 이용에 관한 법률 §37 / 시행령 §73",
        "url": "https://www.law.go.kr/법령/국토의계획및이용에관한법률",
    },
    {
        "keywords": ["미관지구"],
        "display_name": "미관지구",
        "restriction_summary": (
            "국토계획법 미관지구 내 건축물 외관·형태·재료에 관한 추가 기준 적용. "
            "서울시 등 일부 지자체는 경관지구로 통합 전환 중 — 조례 확인 필요."
        ),
        "law": "국토의 계획 및 이용에 관한 법률 §37",
        "url": "https://www.law.go.kr/법령/국토의계획및이용에관한법률",
    },
    {
        "keywords": ["방화지구"],
        "display_name": "방화지구",
        "restriction_summary": (
            "건축법 §51: 방화지구 내 건축물 주요구조부 및 외벽 내화구조 의무. "
            "지붕·처마 등 연소 우려 부분 불연 재료 사용 의무."
        ),
        "law": "건축법 §51 / 국토의 계획 및 이용에 관한 법률 §37",
        "url": "https://www.law.go.kr/법령/건축법/제51조",
    },
    {
        "keywords": ["가로구역최고높이", "가로구역 최고높이"],
        "display_name": "가로구역 최고높이제한구역",
        "restriction_summary": (
            "건축법 §60: 허가권자(시장·군수·구청장) 공고에 따른 가로구역별 최고높이 제한. "
            "진단 시 해당 구역 공고값이 자동 적용됩니다 (높이·일조 카드 참조)."
        ),
        "law": "건축법 §60 / 시행령 §82",
        "url": "https://www.law.go.kr/법령/건축법/제60조",
    },
]


def _collect_zone_strings(*zone_strs: str | None) -> list[str]:
    """여러 zone 문자열을 합쳐 비어있지 않은 항목 목록으로 반환."""
    result: list[str] = []
    for s in zone_strs:
        if not s:
            continue
        for part in s.split(","):
            part = part.strip()
            if part:
                result.append(part)
    return result


def calculate(
    *,
    zone_district: str | None = None,
    zone_area: str | None = None,
) -> dict:
    """중첩 지구·구역 검토 카드.

    Args:
        zone_district: VWorld 또는 사용자 입력 용도지구 문자열 (콤마 구분 가능).
        zone_area:     VWorld 용도구역 문자열 (콤마 구분 가능).

    Returns:
        카드 dict. items 는 매칭된 지구·구역별 행위제한 목록.
        매칭 없으면 items=[], pass=True.
    """
    zone_names = _collect_zone_strings(zone_district, zone_area)
    combined = " ".join(zone_names)  # 키워드 매칭용 통합 문자열

    items = []
    for zdef in _ZONE_DEFS:
        matched_zones = [
            z for z in zone_names
            if any(kw in z for kw in zdef["keywords"])
        ]
        if not matched_zones:
            # 통합 문자열에서도 한번 더 확인 (키워드가 zone_name 전체에 걸쳐 있을 때)
            if not any(kw in combined for kw in zdef["keywords"]):
                continue
            matched_zones = [combined]  # fallback

        items.append({
            "display_name": zdef["display_name"],
            "matched_zones": matched_zones,
            "restriction_summary": zdef["restriction_summary"],
            "law": zdef["law"],
            "url": zdef["url"],
            "needs_review": True,
        })

    if not items:
        return {
            "category": "중첩지구_구역",
            "pass": True,
            "score": 10,
            "confidence": 4,
            "source": "지역지구 키워드 파싱 (VWorld / 사용자 입력)",
            "notes": "특별 중첩 지구·구역 해당 없음 (입력된 용도지구 기준).",
            "items": [],
            "input_zones": zone_names,
        }

    notes_parts = [f"⚠ 중첩 지구·구역 {len(items)}종 확인됨 — 각 지구별 행위 제한 검토 필요."]
    for it in items:
        notes_parts.append(f"· {it['display_name']}: {it['restriction_summary'][:60]}…")

    return {
        "category": "중첩지구_구역",
        "pass": None,   # 자동 판정 불가 — 허가권자 확인 필수
        "score": 5,     # 중첩 지구 존재 자체는 YELLOW 신호 유발
        "confidence": 3,
        "source": "지역지구 키워드 파싱 (VWorld / 사용자 입력) — 세부 제한은 허가권자 확인 필수",
        "notes": " ".join(notes_parts),
        "items": items,
        "input_zones": zone_names,
    }
