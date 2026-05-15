"""높이·일조 계산기.

근거 (법제처 API 확인, 2026 현행):
- 건축법 제60조: 가로구역별 최고높이는 허가권자가 지정·공고
  - 시행령 §82: 도로 너비, 도시미관 등 고려해 결정. **"도로 너비 × N배" 같은 일반 규정 없음**
- 건축법 제61조 + 시행령 §86 (2023.9.12 개정 현행):
  ① 전용·일반주거지역: 정북방향 인접 대지경계선으로부터
     1. 높이 10m 이하 부분: 1.5m 이상 이격
     2. 높이 10m 초과 부분: 해당 부분 높이의 1/2 이상 이격
  ② 적용 제외:
     1. 너비 20m 이상 도로 접한 대지 상호간 (특정 구역)
     2. 건축협정구역 안 대지 상호간 (협정에 일정거리 띄움 포함 시)
     3. 정북방향 인접 대지가 비주거지역인 경우
  ③ 공동주택: 채광창 벽면 → 인접 대지경계선 수평거리의 2배
     (근린상업·준주거 4배) 이하로 높이 제한 + 동간거리

V1 한계:
- 대지 인접 조건(인접대지가 어느 용도지역인지, 도로 폭, 정북방향) 입력 없음
  → 실제 위반 판정은 도면 검토 필요
- 사선식 자동 산정 대신 적용 대상 여부 + 정확한 §86 본문 안내만 제공
"""
from __future__ import annotations


def calculate(
    height: float,
    floors_above: int,
    zone_use: str,
    road_width: float | None = None,
) -> dict:
    """높이·일조 진단 결과.

    Returns:
      {category, actual_height_m, floors_above, road_width_m,
       shadow_applies, pass, score, confidence, source, notes}
    """
    shadow_applies = _shadow_applies(zone_use)

    notes: list[str] = []
    notes.append(f"건물 높이 {height}m / 지상 {floors_above}층")
    if road_width:
        notes.append(
            f"전면도로 폭 {road_width}m — 가로구역별 최고높이가 지정된 구역인지 별도 확인 "
            f"(건축법 §60, 시행령 §82). 일반 '도로폭 × N배' 자동 산정 규정은 없음."
        )
    else:
        notes.append("전면도로 폭 미입력")

    if shadow_applies:
        notes.append(
            "정북 일조 사선 적용 대상 (전용·일반주거지역, 시행령 §86 ①항). "
            "높이 10m 이하 부분은 인접 대지경계선으로부터 1.5m 이상, "
            "10m 초과 부분은 해당 부분 높이의 1/2 이상 이격해야 함. "
            "단, ②항(너비 20m+ 도로 접한 대지 등) 또는 정북 인접 대지가 "
            "비주거지역이면 적용 제외 — 도면 별도 검토 필요."
        )
    else:
        notes.append(
            "정북 일조 사선 미적용 용도지역. 공동주택은 §86 ③항 인동거리 별도 검토 "
            "(채광창 벽면→인접대지경계선 수평거리의 2배, 근린상업·준주거 4배 이하)."
        )

    # 높이 10m 초과 시 §86 ①항 2호 사선 비율이 더 까다로워짐을 안내
    if shadow_applies and height > 10:
        notes.append(
            f"※ 건물 높이 {height}m로 10m 초과 — 정북 인접대지경계선까지 "
            f"최소 {height / 2:.1f}m 이상 이격 필요 (시행령 §86 ①항 2호)."
        )

    return {
        "category": "높이_일조",
        "actual_height_m": height,
        "floors_above": floors_above,
        "road_width_m": road_width,
        "shadow_applies": shadow_applies,
        "shadow_min_setback_m": (round(max(1.5, height / 2), 2) if shadow_applies else None),
        # 자동 한도 비활성화 — 인접 조건 없이 위반 판정 불가
        "road_height_limit_m": None,
        "pass": None,
        "score": None,
        "confidence": 2,
        "source": "건축법 §60·§61 + 시행령 §82·§86 (인접 조건 없어 자동 판정 미적용)",
        "law_refs": _law_refs(),
        "notes": " | ".join(notes),
    }


def _shadow_applies(zone_use: str) -> bool:
    """정북 일조 사선 적용 여부 — 시행령 §86 ①항 전용·일반주거지역 한정."""
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
            "name": "건축법 시행령 제82조 (건축물의 높이 제한)",
            "url": "https://www.law.go.kr/법령/건축법시행령/제82조",
        },
        {
            "name": "건축법 시행령 제86조 (일조 등의 확보를 위한 건축물의 높이 제한)",
            "url": "https://www.law.go.kr/법령/건축법시행령/제86조",
        },
    ]
