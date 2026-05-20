"""건축 인허가 심의 자동 트리거 판정.

입력값(연면적·층수·세대수·용도·지역지구 등) + 진단 결과 →
어떤 심의·영향평가가 필요한지 자동 안내. 좌표 기반 심의(교육환경·문화재)는
단서 추출 위주이며, 정확한 판정은 사용자 도면 확인 필요.

판정 결과:
  REQUIRED  : 명확히 트리거 (가장 보수적인 기준 충족)
  MAYBE     : 일부 조건 만족 — 지자체 조례 또는 추가 검토 필요
  NONE      : 트리거 없음
"""
from __future__ import annotations

from typing import Any

# 도시교통정비지역 — 특·광역시 + 일부 광역도시권
_URBAN_TRAFFIC_AREAS = (
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "수원", "성남", "고양", "용인", "안산",  # 경기 인구 50만 이상
)

# 다중이용건축물 — 건축법 시행령 §2-17
#   가목: 바닥면적 합계 5,000㎡ 이상 + 아래 용도
#   나목: 16층 이상 건축물 (용도 무관)
_MULTI_USE_USES = (
    "문화및집회시설",   # 동물원·식물원 제외
    "종교시설",
    "판매시설",
    "운수시설",         # 여객용 시설 한정 (보수적 적용)
    "종합병원",         # 의료시설 중 종합병원만 해당
    "관광숙박시설",     # 숙박시설 중 관광숙박시설만 해당
)

# 준다중이용건축물 — 건축법 시행령 §2-17의2
#   다중이용 외 + 바닥면적 합계 1,000㎡ 이상 + 아래 용도
#   (다중이용 6가지 용도 포함 + 추가 6가지)
_QUASI_MULTI_USE_USES = (
    "문화및집회시설", "종교시설", "판매시설", "운수시설",
    "종합병원", "관광숙박시설",
    "교육연구시설", "노유자시설", "운동시설",
    "위락시설", "관광휴게시설", "장례시설",
)


# ───────────────────────────────────────────────────────────────────────
# 1. 건축위원회 심의 — 건축법 §4-2, 시행령 §5-5
# ───────────────────────────────────────────────────────────────────────
def _eval_building_committee(req: dict, land: dict) -> dict:
    floors = int(req.get("floors_above") or 0)
    total = float(req.get("total_floor_area") or 0)
    use = (req.get("building_use") or "")

    # 다중이용건축물 (시행령 §2-17):
    #   가목: 특정 용도 + 5,000㎡ 이상
    #   나목: 16층 이상 건축물 (용도 무관)
    is_multi_use_by_use = any(u in use for u in _MULTI_USE_USES) and total >= 5000
    is_multi_use = is_multi_use_by_use or floors >= 16
    # 준다중이용건축물 (시행령 §2-17의2): 다중이용 외 + 확장 용도 + 1,000㎡ 이상
    is_quasi_multi = (
        not is_multi_use
        and any(u in use for u in _QUASI_MULTI_USE_USES)
        and total >= 1000
    )

    triggered = False
    reasons: list[str] = []

    # 다중이용건축물 자체가 심의 대상
    if is_multi_use:
        triggered = True
        reasons.append(f"다중이용건축물 ({use}, 연면적 {total:,.0f}㎡ ≥ 5,000㎡)")
    # 16층 이상 + 연면적 5천㎡ 이상
    if floors >= 16 and total >= 5000:
        triggered = True
        reasons.append(f"16층 이상({floors}F) + 연면적 5,000㎡ 이상({total:,.0f}㎡)")
    # 21층 이상 또는 연면적 10만㎡ 이상
    if floors >= 21 or total >= 100000:
        triggered = True
        reasons.append("21층 이상 또는 연면적 100,000㎡ 이상")

    if triggered:
        severity = "REQUIRED"
        note = "다중이용건축물 — 시·도 건축위원회 사전심의 대상. 설계 전 사전심의 신청 필요."
    elif is_quasi_multi or floors >= 11 or total >= 3000:
        severity = "MAYBE"
        note = (
            f"준다중이용건축물 해당({use}, {total:,.0f}㎡) — 지자체 조례 심의 확인 필요."
            if is_quasi_multi else
            "규모 기준 미달이나 임박 — 지자체별 건축조례 심의 대상 여부 확인 필요."
        )
    else:
        severity = "NONE"
        note = "지자체별 건축조례에 별도 심의 대상 규정 있음 — 해당 시·군·구 조례 확인 필요."

    return {
        "name": "건축위원회 심의",
        "severity": severity,
        "triggered_reasons": reasons,
        "law_ref": "건축법 §4-2, §2-1-17·17의2, 시행령 §5-5",
        "law_ref_url": "https://www.law.go.kr/법령/건축법/제4조의2",
        "note": note,
    }


# ───────────────────────────────────────────────────────────────────────
# 2. 교통영향평가 — 도시교통정비촉진법 §15, 시행령 §13-2
# ───────────────────────────────────────────────────────────────────────
def _eval_traffic_impact(req: dict, land: dict) -> dict:
    total = float(req.get("total_floor_area") or 0)
    units = int(req.get("units") or 0)
    address = req.get("address") or land.get("jurisdiction_name", "")
    in_urban = any(area in address for area in _URBAN_TRAFFIC_AREAS)

    triggered = False
    reasons: list[str] = []

    # 도시교통정비지역
    if in_urban and total >= 50000:
        triggered = True
        reasons.append(f"도시교통정비지역 + 연면적 50,000㎡ 이상({total:,.0f}㎡)")
    elif not in_urban and total >= 70000:
        triggered = True
        reasons.append(f"기타지역 + 연면적 70,000㎡ 이상({total:,.0f}㎡)")

    # 주택 세대수 기준
    if units >= 1000:
        triggered = True
        reasons.append(f"공동주택 1,000세대 이상({units}세대)")

    severity = "REQUIRED" if triggered else "MAYBE" if (
        total >= 30000 or units >= 500
    ) else "NONE"

    return {
        "name": "교통영향평가",
        "severity": severity,
        "triggered_reasons": reasons,
        "law_ref": "도시교통정비촉진법 §15, 시행령 §13-2",
        "law_ref_url": "https://www.law.go.kr/법령/도시교통정비촉진법/제15조",
        "note": (
            "교통영향평가서 제출 → 심의위원회 통과 후 인허가 가능. 보통 6~12개월 소요."
            if triggered else
            "규모 임박 시 조기 협의 권장."
        ),
    }


# ───────────────────────────────────────────────────────────────────────
# 3. 경관심의 — 경관법 §27, 시행령 §22
# ───────────────────────────────────────────────────────────────────────
def _eval_landscape(req: dict, land: dict) -> dict:
    floors = int(req.get("floors_above") or 0)
    total = float(req.get("total_floor_area") or 0)
    height = float(req.get("height") or 0)
    district = (land.get("zone_district") or "") + " " + (req.get("zone_district") or "")
    in_landscape_zone = "경관" in district

    triggered = False
    reasons: list[str] = []

    if in_landscape_zone:
        triggered = True
        reasons.append(f"경관지구/중점경관관리구역({district.strip()})")
    if floors >= 16 or total >= 50000:
        triggered = True
        reasons.append(f"16층 이상 또는 연면적 50,000㎡ 이상")
    if height >= 60:
        triggered = True
        reasons.append(f"높이 60m 이상({height}m)")

    severity = "REQUIRED" if triggered else "MAYBE" if (
        floors >= 11 or total >= 20000 or height >= 30
    ) else "NONE"

    return {
        "name": "경관심의",
        "severity": severity,
        "triggered_reasons": reasons,
        "law_ref": "경관법 §27, 시행령 §22",
        "law_ref_url": "https://www.law.go.kr/법령/경관법/제27조",
        "note": (
            "서울 등 일부 지자체는 더 엄격한 조례 기준 운영 (서울 7층/2천㎡ 등). 시·도 조례 확인 필요."
        ),
    }


# ───────────────────────────────────────────────────────────────────────
# 4. 사전재해영향성검토 — 자연재해대책법 §4
# ───────────────────────────────────────────────────────────────────────
def _eval_disaster_impact(req: dict, land: dict) -> dict:
    # 법 기준 면적은 '개발행위 면적'임. 입력값 site_area(대지면적)를 개발면적으로 간주하여 사용.
    # 대지면적 ≠ 개발면적인 경우(분할 개발·단계 시행 등) 실제 개발면적으로 별도 확인 필요.
    site = float(req.get("site_area") or 0)
    triggered = site >= 5000
    severity = "REQUIRED" if triggered else "MAYBE" if site >= 3000 else "NONE"
    return {
        "name": "사전재해영향성검토",
        "severity": severity,
        "triggered_reasons": (
            [f"개발행위 면적 5,000㎡ 이상({site:,.0f}㎡)"] if triggered else []
        ),
        "law_ref": "자연재해대책법 §4, 시행령 §6",
        "law_ref_url": "https://www.law.go.kr/법령/자연재해대책법/제4조",
        "note": (
            "법 기준은 '개발행위 면적' 5,000㎡ 이상. 여기서는 입력된 대지면적으로 판단하며,"
            " 실제 개발면적이 다를 경우 별도 확인 필요."
            " 자연재해위험지구·산사태위험지구 등 위험지역 내라면 면적 기준 미만이어도 검토 대상."
        ),
    }


# ───────────────────────────────────────────────────────────────────────
# 5. 교육환경평가 — 교육환경법 §6
# ───────────────────────────────────────────────────────────────────────
def _eval_education(req: dict, land: dict) -> dict:
    # 교육환경보호구역(절대 50m·상대 200m) 해당 여부는 학교와의 거리(좌표) 기반 판정이 필요.
    # 현재 좌표 데이터 미보유 → MAYBE 고정, 사용자 직접 확인 안내.
    use = req.get("building_use") or ""
    restricted_hint = any(
        kw in use for kw in ("숙박", "유흥", "노래연습장", "단란주점", "PC방", "위락")
    )
    return {
        "name": "교육환경평가",
        "severity": "MAYBE",  # 학교 거리 좌표 데이터 없이 확정 불가
        "triggered_reasons": (
            [f"보호구역 내 제한 가능 용도 포함 — {use} (§7 행위 제한 목록 확인 필요)"]
            if restricted_hint else []
        ),
        "law_ref": "교육환경 보호에 관한 법률 §6, §7",
        "law_ref_url": "https://www.law.go.kr/법령/교육환경보호에관한법률/제6조",
        "note": (
            "교육환경보호구역(절대보호구역 50m·상대보호구역 200m) 이내 여부는 학교 경계와의 거리로 결정됨."
            " 토지이음 또는 관할 교육지원청에서 해당 필지의 보호구역 포함 여부를 직접 확인 필요."
            " 숙박·유흥·위락 등 §7 제한 시설은 상대보호구역 내 설치 불가."
        ),
    }


# ───────────────────────────────────────────────────────────────────────
# 6. 문화재 현상변경 — 문화재보호법 §13
# ───────────────────────────────────────────────────────────────────────
def _eval_cultural_heritage(req: dict, land: dict) -> dict:
    # 좌표 기반 검색 필요 — 별도 데이터(국가유산 보호구역 SHP) 없으므로 단순 안내
    district = (land.get("zone_district") or "") + " " + (req.get("zone_district") or "")
    has_signal = any(kw in district for kw in ("문화재", "역사문화", "보존지역"))
    return {
        "name": "문화재 현상변경 허가",
        "severity": "REQUIRED" if has_signal else "MAYBE",
        "triggered_reasons": (
            [f"지역지구에 문화재 관련 단서 — {district.strip()}"] if has_signal else []
        ),
        "law_ref": "국가유산기본법, 문화재보호법 §13, 시행령 §21-2",
        "law_ref_url": "https://www.law.go.kr/법령/문화재보호법/제13조",
        "note": (
            "지정문화재 외곽 100~500m(역사문화환경 보존지역) 내 건축 시 시·도지사 사전 허가 대상. "
            "국가유산청 또는 시·도 문화재과에서 지정구역 확인 필요."
        ),
    }


# ───────────────────────────────────────────────────────────────────────
# 7. 환경영향평가 / 소규모환경영향평가 — 환경영향평가법
# ───────────────────────────────────────────────────────────────────────
def _eval_environmental(req: dict, land: dict) -> dict:
    site = float(req.get("site_area") or 0)
    zone = land.get("zone_use") or ""
    is_non_urban = any(kw in zone for kw in ("관리지역", "농림지역", "자연환경보전지역"))

    # 단일 건축물은 통상 평가 대상 아님. 도시개발사업 25만㎡ 이상이 일반 환영.
    # 소규모환경영향평가는 보전·관리지역에서 7,500~30,000㎡
    triggered = False
    reasons: list[str] = []
    if site >= 250000:
        triggered = True
        reasons.append(f"개발면적 25만㎡ 이상({site:,.0f}㎡) — 환경영향평가")
    elif is_non_urban and site >= 7500:
        triggered = True
        reasons.append(f"{zone} + 면적 7,500㎡ 이상({site:,.0f}㎡) — 소규모환경영향평가")

    severity = "REQUIRED" if triggered else "NONE"
    return {
        "name": "환경영향평가",
        "severity": severity,
        "triggered_reasons": reasons,
        "law_ref": "환경영향평가법 §22, §43, 시행령 별표 3·4",
        "law_ref_url": "https://www.law.go.kr/법령/환경영향평가법/제22조",
        "note": (
            "단순 건축물 인허가는 통상 평가 대상 아님. "
            "도시개발·산단·관광단지 등 대규모 개발사업이거나 보전지역·관리지역에서 일정 규모 시 해당."
        ),
    }


# ───────────────────────────────────────────────────────────────────────
# 8. 도시계획위원회 심의 — 국토계획법 §113
# ───────────────────────────────────────────────────────────────────────
def _eval_urban_planning(req: dict, land: dict) -> dict:
    district = (land.get("zone_district") or "") + " " + (req.get("zone_district") or "")
    has_dup = "지구단위" in district

    triggered = has_dup  # 지구단위계획구역 내 건축은 결정사항 일치 검증 필요
    return {
        "name": "도시계획위원회 심의",
        "severity": "REQUIRED" if triggered else "NONE",
        "triggered_reasons": (
            [f"지구단위계획구역 — {district.strip()}"] if triggered else []
        ),
        "law_ref": "국토계획법 §113, §50, §52",
        "law_ref_url": "https://www.law.go.kr/법령/국토의계획및이용에관한법률/제113조",
        "note": (
            "지구단위계획구역 내 건축물은 결정사항(높이·용도·배치 등)과 일치해야 하며, "
            "변경 사항이 있으면 도시·군관리계획 변경 → 도시계획위원회 심의 필요."
        ),
    }


# ───────────────────────────────────────────────────────────────────────
# 9. 지하안전영향평가 — 지하안전관리에 관한 특별법 §14, 시행령 §14
# ───────────────────────────────────────────────────────────────────────
def _eval_underground_safety(req: dict, land: dict) -> dict:
    """지하안전영향평가 · 소규모 지하안전영향평가.

    법 기준 (시행령 §14): 실제 굴착 깊이
      - 제1종 (영향평가): 굴착 깊이 20m 이상
      - 제2종 (소규모): 굴착 깊이 10m 이상 20m 미만
    실제 굴착 깊이 미입력 시 floors_below × 3.5m 로 추정 (층당 높이는 지반·구조에 따라 상이).
    """
    floors_below = int(req.get("floors_below") or 0)
    est_depth = floors_below * 3.5  # 층당 3.5m 추정값 — 실제 굴착 깊이와 다를 수 있음

    triggered_1 = floors_below >= 6   # ≈ 21m+ → 제1종
    triggered_2 = floors_below >= 3   # ≈ 10.5m+ → 소규모(제2종)
    maybe = floors_below >= 2

    reasons: list[str] = []
    if triggered_1:
        reasons.append(
            f"지하 {floors_below}층 (굴착 깊이 ≈{est_depth:.0f}m 추정) — 제1종 지하안전영향평가"
        )
    elif triggered_2:
        reasons.append(
            f"지하 {floors_below}층 (굴착 깊이 ≈{est_depth:.0f}m 추정) — 소규모 지하안전영향평가"
        )

    if triggered_1 or triggered_2:
        severity = "REQUIRED"
        note = (
            "법 기준은 실제 굴착 깊이(20m/10m). 여기서는 지하층수 × 3.5m 로 추정하였으므로,"
            " 구조설계 확정 후 실제 굴착 깊이로 재확인 필요."
            " 착공 전 지하안전영향평가서 제출 → 승인 후 착공 가능."
        )
    elif maybe:
        severity = "MAYBE"
        note = (
            "지하 2층 계획 — 실제 굴착 깊이(층당 높이·지반 조건)에 따라 소규모 지하안전영향평가 해당 가능."
            " 구조설계 확정 후 실제 굴착 깊이로 확인 필요."
        )
    else:
        severity = "NONE"
        note = ""

    return {
        "name": "지하안전영향평가",
        "severity": severity,
        "triggered_reasons": reasons,
        "law_ref": "지하안전관리에 관한 특별법 §14, 시행령 §14",
        "law_ref_url": "https://www.law.go.kr/법령/지하안전관리에관한특별법/제14조",
        "note": note,
    }


# ───────────────────────────────────────────────────────────────────────
# 10. 건축물 안전영향평가 — 건축법 §13조의2, 시행령 §10조의3
# ───────────────────────────────────────────────────────────────────────
def _eval_building_safety(req: dict, land: dict) -> dict:
    """건축물 안전영향평가 (건축법 §13조의2).

    시행령 §10조의3 대상:
      1호: 초고층 건축물 (건축법 §2①19호 — 50층 이상 or 높이 200m 이상)
      2호: 연면적 10만㎡ 이상(가목) AND 16층 이상(나목) — 두 조건 모두 충족
    """
    floors = int(req.get("floors_above") or 0)
    total = float(req.get("total_floor_area") or 0)
    height = float(req.get("height") or 0)

    reasons: list[str] = []

    # 1호: 초고층 건축물
    is_super_high = floors >= 50 or height >= 200
    if is_super_high:
        parts: list[str] = []
        if floors >= 50:
            parts.append(f"{floors}층 ≥ 50층")
        if height >= 200:
            parts.append(f"높이 {height}m ≥ 200m")
        reasons.append(f"초고층 건축물 ({' / '.join(parts)})")

    # 2호: 연면적 10만㎡ 이상 AND 16층 이상
    is_large_mid = total >= 100000 and floors >= 16
    if is_large_mid:
        reasons.append(
            f"연면적 {total:,.0f}㎡ ≥ 10만㎡ AND {floors}층 ≥ 16층"
        )

    triggered = bool(reasons)
    severity = "REQUIRED" if triggered else "NONE"

    return {
        "name": "건축물 안전영향평가",
        "severity": severity,
        "triggered_reasons": reasons,
        "law_ref": "건축법 §13조의2, 시행령 §10조의3",
        "law_ref_url": "https://www.law.go.kr/법령/건축법/제13조의2",
        "note": (
            "건축허가 신청 전 안전영향평가 의뢰 필요 (건축법 §13조의2②). "
            "평가 기관은 설계 기준·하중·지반조사 결과 등을 검토하며 30일 이내(연장 가능) 결과 제출."
            if triggered else ""
        ),
    }


# ───────────────────────────────────────────────────────────────────────
# 11. 범죄예방 건축기준 — 건축법 §53의2
# ───────────────────────────────────────────────────────────────────────
_CRIME_PREV_USES = (
    "다가구주택", "공동주택", "다중주택", "기숙사",
    "문화및집회시설", "교육연구시설", "노유자시설", "수련시설",
    "업무시설", "숙박시설",
)


def _eval_crime_prevention(req: dict, land: dict) -> dict:
    use = req.get("building_use") or ""
    triggered = any(u in use for u in _CRIME_PREV_USES)
    return {
        "name": "범죄예방 건축기준",
        "severity": "REQUIRED" if triggered else "NONE",
        "triggered_reasons": (
            [f"적용 대상 용도 — {use}"] if triggered else []
        ),
        "law_ref": "건축법 §53의2, 시행령 §63의7, 국토부 고시 제2021-930호",
        "law_ref_url": "https://www.law.go.kr/법령/건축법/제53조의2",
        "note": (
            "설계 단계에서 CCTV·조명·출입 통제 등 범죄예방 설계 기준 반영 필요."
            if triggered else ""
        ),
    }


# ───────────────────────────────────────────────────────────────────────
# 진입점
# ───────────────────────────────────────────────────────────────────────
def evaluate_reviews(req: dict, land: dict | None = None) -> dict[str, Any]:
    """심의·영향평가 일괄 평가 (11개 항목).

    Returns:
      {
        items: [{name, severity, triggered_reasons, law_ref, note}, ...],
        required_count: int,
        maybe_count: int,
      }
    """
    land = land or {}
    items = [
        _eval_building_committee(req, land),
        _eval_traffic_impact(req, land),
        _eval_landscape(req, land),
        _eval_disaster_impact(req, land),
        _eval_education(req, land),
        _eval_cultural_heritage(req, land),
        _eval_environmental(req, land),
        _eval_urban_planning(req, land),
        _eval_underground_safety(req, land),
        _eval_building_safety(req, land),
        _eval_crime_prevention(req, land),
    ]
    required = sum(1 for x in items if x["severity"] == "REQUIRED")
    maybe = sum(1 for x in items if x["severity"] == "MAYBE")
    return {
        "items": items,
        "required_count": required,
        "maybe_count": maybe,
    }
