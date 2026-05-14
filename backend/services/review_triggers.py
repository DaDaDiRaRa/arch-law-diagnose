"""건축 인허가 8개 심의 자동 트리거 판정.

입력값(연면적·층수·세대수·용도·지역지구 등) + 진단 결과 →
어떤 심의가 필요한지 자동 안내. 좌표 기반 심의(교육환경·문화재)는
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

# 대규모 건축물 정의 (건축법 §2-1-19: 다중이용건축물)
_MULTI_USE_USES = (
    "종합병원", "관광숙박", "관광객이용시설", "여객", "운수",
    "판매시설", "위락시설", "장례식장",
)


# ───────────────────────────────────────────────────────────────────────
# 1. 건축위원회 심의 — 건축법 §4-2, 시행령 §5-5
# ───────────────────────────────────────────────────────────────────────
def _eval_building_committee(req: dict, land: dict) -> dict:
    floors = int(req.get("floors_above") or 0)
    total = float(req.get("total_floor_area") or 0)
    use = (req.get("building_use") or "")
    is_multi_use = any(u in use for u in _MULTI_USE_USES)

    triggered = False
    reasons: list[str] = []

    # 다중이용건축물 (16층 이상 + 연면적 5천㎡ 이상)
    if floors >= 16 and total >= 5000:
        triggered = True
        reasons.append(f"16층 이상({floors}F) + 연면적 5,000㎡ 이상({total:,.0f}㎡)")
    # 분양 사업 — 21층 이상 또는 연면적 10만㎡ 이상
    if floors >= 21 or total >= 100000:
        triggered = True
        reasons.append(f"21층 이상 또는 연면적 100,000㎡ 이상")
    # 특정 용도 다중이용
    if is_multi_use and total >= 5000:
        triggered = True
        reasons.append(f"다중이용 용도({use}) + 연면적 5,000㎡ 이상")

    severity = "REQUIRED" if triggered else "MAYBE" if (
        floors >= 11 or total >= 3000
    ) else "NONE"

    return {
        "name": "건축위원회 심의",
        "severity": severity,
        "triggered_reasons": reasons,
        "law_ref": "건축법 §4-2, 시행령 §5-5",
        "law_ref_url": "https://www.law.go.kr/법령/건축법/제4조의2",
        "note": (
            "지자체별 건축조례에 별도 심의 대상 규정 있음 — 해당 시·군·구 조례 확인 필요."
            if not triggered else
            "다중이용건축물 — 시·도 건축위원회 사전심의 대상. 설계 전 사전심의 신청 필요."
        ),
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
    site = float(req.get("site_area") or 0)
    triggered = site >= 5000
    severity = "REQUIRED" if triggered else "MAYBE" if site >= 3000 else "NONE"
    return {
        "name": "사전재해영향성검토",
        "severity": severity,
        "triggered_reasons": (
            [f"개발면적 5,000㎡ 이상({site:,.0f}㎡)"] if triggered else []
        ),
        "law_ref": "자연재해대책법 §4, 시행령 §6",
        "law_ref_url": "https://www.law.go.kr/법령/자연재해대책법/제4조",
        "note": (
            "자연재해위험지구·산사태위험지구 등 위험지역 내라면 면적 기준 미만이어도 검토 필요."
        ),
    }


# ───────────────────────────────────────────────────────────────────────
# 5. 교육환경평가 — 교육환경법 §6
# ───────────────────────────────────────────────────────────────────────
def _eval_education(req: dict, land: dict) -> dict:
    # 좌표 기반 학교 거리 검사는 별도 데이터 필요 (DB 미보유)
    # → 일단 단서 추출 위주: 사용자 안내
    total = float(req.get("total_floor_area") or 0)
    use = req.get("building_use") or ""
    # 교육환경법 대상 건축물: 21층 이상 OR 연면적 10만㎡ OR 특정 시설(숙박/주류 등)
    is_target = (total >= 100000) or any(
        kw in use for kw in ("숙박", "유흥", "노래연습장", "단란주점", "PC방")
    )
    return {
        "name": "교육환경평가",
        "severity": "MAYBE",  # 좌표 기반 확정 필요
        "triggered_reasons": (
            [f"대상 용도/규모 — {use}"] if is_target else []
        ),
        "law_ref": "교육환경 보호에 관한 법률 §6, §7",
        "law_ref_url": "https://www.law.go.kr/법령/교육환경보호에관한법률/제6조",
        "note": (
            "학교 경계 200m 이내(절대보호구역 50m·상대보호구역 200m)인 경우 평가 대상. "
            "교육청 또는 토지이음에서 학교환경위생 정화구역 확인 필요."
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
# 진입점
# ───────────────────────────────────────────────────────────────────────
def evaluate_reviews(req: dict, land: dict | None = None) -> dict[str, Any]:
    """8개 심의 일괄 평가.

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
    ]
    required = sum(1 for x in items if x["severity"] == "REQUIRED")
    maybe = sum(1 for x in items if x["severity"] == "MAYBE")
    return {
        "items": items,
        "required_count": required,
        "maybe_count": maybe,
    }
