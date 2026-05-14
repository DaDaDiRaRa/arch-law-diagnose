"""도시계획시설 분류코드 매핑.

UQ151~UQ159: 도시계획시설 대분류 (국토교통부 표준)
저촉 시 효과: 건축 제한 또는 매수청구 대상 (국토계획법 §47).
"""

# 대분류 (lclas_cl 코드 = UQS/UQT/UQU/UQV/UQW/UQX/UQY 패턴 기반 추정)
CATEGORY_NAMES: dict[str, str] = {
    "UQ151": "교통시설",            # UQS — 도로/철도/주차장
    "UQ152": "공간시설",            # 광장/공원/녹지/유원지
    "UQ153": "유통·공급시설",       # UQT — 수도/가스/전기/통신
    "UQ154": "공공시설",            # 일반 공공시설
    "UQ155": "공공·문화체육시설",   # UQV — 학교/청사/도서관/체육
    "UQ156": "방재시설",            # UQW — 하천/유수지
    "UQ157": "보건위생시설",        # UQX — 화장시설/공동묘지
    "UQ158": "환경기초시설",        # UQY — 하수/폐기물처리
    "UQ159": "기타시설",
}

# 저촉 시 진단 신호 (대부분 RED — 건축 자체가 막힘)
CATEGORY_SEVERITY: dict[str, str] = {
    "UQ151": "RED",
    "UQ152": "RED",
    "UQ153": "YELLOW",  # 공급시설은 부지 일부만 차지하는 경우 있음
    "UQ154": "RED",
    "UQ155": "RED",
    "UQ156": "RED",
    "UQ157": "YELLOW",
    "UQ158": "YELLOW",
    "UQ159": "YELLOW",
}


def category_label(uq_code: str) -> str:
    return CATEGORY_NAMES.get(uq_code, uq_code)


def category_severity(uq_code: str) -> str:
    return CATEGORY_SEVERITY.get(uq_code, "YELLOW")
