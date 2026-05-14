"""높이·일조 계산기 — V1 안전 모드.

⚠ 출처 검증 중 (2026-05-14):
- 건축법 제60조: 가로구역 단위 최고높이는 허가권자가 지정·공고 (일반 "도로 너비 × N배" 규정 없음 — 추후 자료 확인 필요).
- 건축법 제61조·시행령 제86조: 정북방향 일조권 / 공동주택 인동거리 — 정확한 사선식 §86 본문 확인 후 보강 예정.

V1 안전 모드:
- 도로폭 기반 자동 한도 산정 비활성화 (가로구역 별도 지정 시에만 적용 가능)
- 일조권 사선 적용 여부만 표시 (정북 9m + 1/2 비율은 §86 원문 확인 후 정밀화)
- pass 판정은 정보 부족(None) — 도면·인접대지 조건 미확보
"""
from __future__ import annotations


def calculate(
    height: float,
    floors_above: int,
    zone_use: str,
    road_width: float | None = None,
) -> dict:
    """높이·일조 진단 결과 (안전 모드).

    Returns:
      {category, actual_height_m, floors_above, road_width_m,
       shadow_applies, pass, score, confidence, source, notes}
    """
    shadow_applies = _shadow_applies(zone_use)

    notes: list[str] = []
    notes.append(f"건물 높이 {height}m / 지상 {floors_above}층")
    if road_width:
        notes.append(
            f"전면도로 폭 {road_width}m — 가로구역별 최고높이가 지정된 구역인지 별도 확인 필요 "
            f"(건축법 §60). 일반 '도로폭 × N배' 자동 산정 룰은 적용하지 않음."
        )
    else:
        notes.append("전면도로 폭 미입력")

    if shadow_applies:
        notes.append(
            "일조권 사선 적용 대상 (전용·일반주거지역, 건축법 §61 / 시행령 §86 ①). "
            "정북방향 인접대지경계선 이격거리는 도면·인접대지 조건으로 별도 검토."
        )
    else:
        notes.append(
            "정북방향 일조권 사선 미적용 용도지역. 공동주택은 §86 ② 인동거리 별도 검토."
        )

    return {
        "category": "높이_일조",
        "actual_height_m": height,
        "floors_above": floors_above,
        "road_width_m": road_width,
        "shadow_applies": shadow_applies,
        # 자동 한도 비활성화 — 룰 검증 완료 시 보강
        "road_height_limit_m": None,
        "shadow_slope": None,
        "pass": None,
        "score": None,
        "confidence": 2,
        "source": "건축법 §60·§61 + 시행령 §82·§86 (자동 산정 미적용, 도면 별도 검토)",
        "law_refs": _law_refs(),
        "notes": " | ".join(notes),
    }


def _shadow_applies(zone_use: str) -> bool:
    """정북 일조 사선 적용 여부 — 시행령 §86 ① 전용/일반주거지역 한정."""
    if not zone_use:
        return False
    return ("전용주거" in zone_use) or ("일반주거" in zone_use)


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
        {
            "name": "건축법 시행령 제82조 (가로구역의 높이 지정)",
            "url": "https://www.law.go.kr/법령/건축법시행령/제82조",
        },
        {
            "name": "건축법 시행령 제86조 (일조 등의 확보를 위한 건축물의 높이 제한)",
            "url": "https://www.law.go.kr/법령/건축법시행령/제86조",
        },
    ]
