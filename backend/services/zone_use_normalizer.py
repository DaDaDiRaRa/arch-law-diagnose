"""용도지역 표준명 정규화.

VWorld 반환값/조례 표기/사용자 입력의 다양한 변형을 zone_limits.json 의
표준명으로 변환. 명확하지 않은 입력은 None을 반환하여 호출부가
"확인필요"로 처리하도록 한다 (대충 매칭 금지 — 정확도 우선).
"""
from __future__ import annotations

# 국토계획법상 표준 용도지역명 (zone_limits.json 키와 일치)
CANONICAL_ZONES = (
    "제1종전용주거지역", "제2종전용주거지역",
    "제1종일반주거지역", "제2종일반주거지역", "제3종일반주거지역",
    "준주거지역",
    "중심상업지역", "일반상업지역", "근린상업지역", "유통상업지역",
    "전용공업지역", "일반공업지역", "준공업지역",
    "보전녹지지역", "생산녹지지역", "자연녹지지역",
    "보전관리지역", "생산관리지역", "계획관리지역",
    "농림지역", "자연환경보전지역",
)

# 카테고리 — 부분 정보로도 명확히 분류 가능한 군집
CATEGORY_ZONES: dict[str, str] = {
    "전용주거지역": "전용주거",
    "일반주거지역": "일반주거",
    "주거지역":     "주거",
    "상업지역":     "상업",
    "공업지역":     "공업",
    "녹지지역":     "녹지",
    "관리지역":     "관리",
}

# 명확한 별칭 (정확히 1개의 표준명에 매핑되는 변형들만 등록)
_ALIASES: dict[str, str] = {
    # "제" prefix 누락
    "1종전용주거지역": "제1종전용주거지역",
    "2종전용주거지역": "제2종전용주거지역",
    "1종일반주거지역": "제1종일반주거지역",
    "2종일반주거지역": "제2종일반주거지역",
    "3종일반주거지역": "제3종일반주거지역",

    # "지역" suffix 생략
    "제1종전용주거": "제1종전용주거지역",
    "제2종전용주거": "제2종전용주거지역",
    "제1종일반주거": "제1종일반주거지역",
    "제2종일반주거": "제2종일반주거지역",
    "제3종일반주거": "제3종일반주거지역",
    "준주거":        "준주거지역",
    "중심상업":      "중심상업지역",
    "일반상업":      "일반상업지역",
    "근린상업":      "근린상업지역",
    "유통상업":      "유통상업지역",
    "전용공업":      "전용공업지역",
    "일반공업":      "일반공업지역",
    "준공업":        "준공업지역",
    "보전녹지":      "보전녹지지역",
    "생산녹지":      "생산녹지지역",
    "자연녹지":      "자연녹지지역",
    "보전관리":      "보전관리지역",
    "생산관리":      "생산관리지역",
    "계획관리":      "계획관리지역",
    "농림":          "농림지역",
    "자연환경보전":  "자연환경보전지역",

    # 둘 다 생략
    "1종전용주거": "제1종전용주거지역",
    "2종전용주거": "제2종전용주거지역",
    "1종일반주거": "제1종일반주거지역",
    "2종일반주거": "제2종일반주거지역",
    "3종일반주거": "제3종일반주거지역",
}


def normalize(zone_use: str | None) -> str | None:
    """용도지역명 표준화.

    Returns:
      - 표준명 (CANONICAL_ZONES 의 한 값) — 명확히 매칭됨
      - None — 입력 비었거나 명확한 매칭 불가 (호출부에서 "확인필요" 처리)
    """
    if not zone_use:
        return None
    s = zone_use.strip()
    if not s:
        return None
    # 1. 정확 매칭
    if s in CANONICAL_ZONES:
        return s
    # 2. 별칭
    if s in _ALIASES:
        return _ALIASES[s]
    # 3. 부분 일치 — 표준명을 substring 으로 포함하는 경우만 (예: "서울특별시 제1종일반주거지역")
    matches = [c for c in CANONICAL_ZONES if c in s]
    if len(matches) == 1:
        return matches[0]
    return None


def category_of(zone_use: str | None) -> str | None:
    """대분류 카테고리 ('전용주거', '일반주거', '주거', '상업', '공업', '녹지', '관리', None).

    표준명이 명확하면 표준명에서 카테고리 추출, 아니면 입력 문자열에서 키워드 검색.
    """
    if not zone_use:
        return None
    canonical = normalize(zone_use) or zone_use.strip()

    # 더 구체적인 카테고리 우선 (전용주거 > 일반주거 > 주거)
    if "전용주거" in canonical:
        return "전용주거"
    if "일반주거" in canonical:
        return "일반주거"
    if "준주거" in canonical:
        return "주거"
    if "주거" in canonical:
        return "주거"
    if "상업" in canonical:
        return "상업"
    if "공업" in canonical:
        return "공업"
    if "녹지" in canonical:
        return "녹지"
    if "관리" in canonical:
        return "관리"
    return None


def lookup_limit(limits: dict, zone_use: str | None) -> float | None:
    """zone_limits 같은 dict에서 표준명 기반 안전 조회.

    부분 매칭은 사용하지 않음 — 명확한 매칭이 안 되면 None을 반환.
    호출부는 None을 "확인필요"로 처리해야 한다.
    """
    canonical = normalize(zone_use)
    if not canonical:
        return None
    val = limits.get(canonical)
    if val is None:
        return None
    return float(val)
