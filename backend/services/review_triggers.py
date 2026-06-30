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

import json
import os
from typing import Any

# 교통영향평가 용도별 임계값 seed (도시교통정비촉진법 시행령 별표1, 법제처 PDF 검증).
_TRAFFIC_SEED: dict | None = None


def _traffic_thresholds() -> dict:
    global _TRAFFIC_SEED
    if _TRAFFIC_SEED is None:
        path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "config", "traffic_impact_thresholds.json")
        )
        with open(path, encoding="utf-8") as f:
            _TRAFFIC_SEED = json.load(f)
    return _TRAFFIC_SEED


def _resolve_traffic_use(building_use: str, seed: dict) -> tuple[str, dict] | None:
    """건축물 용도 → 별표1 용도 키 + 임계값. 미해결 시 None."""
    by_use = seed["by_use"]
    aliases = seed.get("use_aliases", {})
    if building_use in by_use:
        return building_use, by_use[building_use]
    if building_use in aliases and aliases[building_use] in by_use:
        return aliases[building_use], by_use[aliases[building_use]]
    # 부분 매칭 — 가장 긴 키 우선
    best = None
    for k in by_use:
        if (k in building_use or building_use in k) and (best is None or len(k) > len(best)):
            best = k
    if best:
        return best, by_use[best]
    for a, canon in aliases.items():
        if (a in building_use or building_use in a) and canon in by_use:
            return canon, by_use[canon]
    return None


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
    use = req.get("building_use") or ""
    address = req.get("address") or land.get("jurisdiction_name", "")
    in_urban = any(area in address for area in _URBAN_TRAFFIC_AREAS)

    # 용도별 임계값 — 도시교통정비촉진법 시행령 별표1 (법제처 PDF 검증, 전국 적용).
    seed = _traffic_thresholds()
    col = "urban" if in_urban else "region"          # 도시교통정비지역 / 교통권역
    zone_label = seed["columns"][col]
    resolved = _resolve_traffic_use(use, seed)
    threshold = resolved[1][col] if resolved else None
    use_key = resolved[0] if resolved else None

    triggered = False
    reasons: list[str] = []

    if threshold is not None and total >= threshold:
        triggered = True
        reasons.append(
            f"{zone_label} {use_key} 연면적 {threshold:,}㎡ 이상 기준 충족"
            f"({total:,.0f}㎡) — 시행령 별표1"
        )
    # 공동주택 세대수 보수 트리거 (별표 외, 안전측 유지)
    if units >= 1000:
        triggered = True
        reasons.append(f"공동주택 1,000세대 이상({units}세대)")

    if triggered:
        severity = "REQUIRED"
    elif threshold is not None and total >= threshold * 0.8:
        severity = "MAYBE"                            # 임계 80% 근접
    elif threshold is None and (total >= 30000 or units >= 500):
        severity = "MAYBE"                            # 용도 미해결 시 규모 기준 보수
    else:
        severity = "NONE"

    if triggered:
        note = (
            "교통영향평가서 제출 → 심의위원회 통과 후 인허가 가능. 보통 6~12개월 소요."
            f" (적용 기준: {use_key} {zone_label} {threshold:,}㎡)" if use_key else
            "교통영향평가서 제출 → 심의위원회 통과 후 인허가 가능. 보통 6~12개월 소요."
        )
    elif threshold is not None:
        note = (
            f"현재 규모는 {use_key} {zone_label} 단일용도 기준({threshold:,}㎡) 미만. "
            "단, 복합용도(각 용도 연면적÷용도별 최소기준의 합 ≥ 1)면 대상일 수 있어 "
            "별표1 복합용도 규칙 확인 필요."
        )
    else:
        note = (
            f"용도 '{use}'가 별표1 대상 용도표에 매칭되지 않음 — 대상 여부 별도 확인 필요."
            if use else "용도 미입력 — 교통영향평가 대상 여부 확인 불가."
        )

    return {
        "name": "교통영향평가",
        "severity": severity,
        "triggered_reasons": reasons,
        "law_ref": "도시교통정비촉진법 §15, 시행령 제13조의2, 별표 1",
        "law_ref_url": "https://www.law.go.kr/법령/도시교통정비촉진법/제15조",
        "note": note,
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


# 교육환경법 §7 — 상대보호구역 내 제한 용도 키워드
_EDU_RESTRICTED_USES = ("숙박", "유흥", "노래연습장", "단란주점", "PC방", "위락")

# ───────────────────────────────────────────────────────────────────────
# 5. 교육환경평가 — 교육환경법 §6
# ───────────────────────────────────────────────────────────────────────
def _eval_education(
    req: dict, land: dict, nearby_schools: list[dict] | None = None
) -> dict:
    """교육환경보호구역 판정.

    nearby_schools:
      None  — API 미조회(키 없음·실패) → MAYBE 유지 (기존 동작)
      []    — 200m 내 학교 없음 → NONE
      [...] — 학교 있음, 거리 기반 판정
    """
    use = req.get("building_use") or ""
    restricted_use = any(kw in use for kw in _EDU_RESTRICTED_USES)

    law_ref = "교육환경 보호에 관한 법률 §6, §7"
    law_ref_url = "https://www.law.go.kr/법령/교육환경보호에관한법률/제6조"

    if nearby_schools is None:
        # API 미조회 → 기존 MAYBE 동작
        return {
            "name": "교육환경평가",
            "severity": "MAYBE",
            "triggered_reasons": (
                [f"보호구역 내 제한 가능 용도 포함 — {use} (§7 행위 제한 목록 확인 필요)"]
                if restricted_use else []
            ),
            "law_ref": law_ref,
            "law_ref_url": law_ref_url,
            "note": (
                "교육환경보호구역(절대보호구역 50m·상대보호구역 200m) 이내 여부는 학교 경계와의 거리로 결정됨."
                " 토지이음 또는 관할 교육지원청에서 해당 필지의 보호구역 포함 여부를 직접 확인 필요."
                " 숙박·유흥·위락 등 §7 제한 시설은 상대보호구역 내 설치 불가."
            ),
        }

    if not nearby_schools:
        # 200m 내 학교 없음 — 보호구역 외부 확정
        return {
            "name": "교육환경평가",
            "severity": "NONE",
            "triggered_reasons": [],
            "law_ref": law_ref,
            "law_ref_url": law_ref_url,
            "note": "반경 200m 내 교육환경보호구역 대상 학교 없음 (Kakao Places 조회 확인).",
        }

    # 학교 있음 — 절대/상대 구분
    abs_zone = [s for s in nearby_schools if s["distance_m"] <= 50]
    nearest = min(nearby_schools, key=lambda s: s["distance_m"])
    school_list = ", ".join(
        f"{s['name']}({s['distance_m']}m)" for s in nearby_schools[:3]
    )

    if abs_zone:
        abs_list = ", ".join(
            f"{s['name']}({s['distance_m']}m)" for s in abs_zone
        )
        return {
            "name": "교육환경평가",
            "severity": "REQUIRED",
            "triggered_reasons": [
                f"절대보호구역(50m 이내) — {abs_list}"
            ],
            "law_ref": law_ref,
            "law_ref_url": law_ref_url,
            "note": (
                "절대보호구역(학교출입문 50m 이내): 교육환경법 §6 금지행위 전면 불가."
                " 관할 교육지원청 사전 협의 필수."
            ),
        }

    # 상대보호구역 (50m 초과 ~ 200m 이내)
    severity = "REQUIRED" if restricted_use else "MAYBE"
    reasons = [f"상대보호구역(200m 이내) — {school_list}"]
    if restricted_use:
        reasons.append(f"§7 제한 용도 포함 — {use}")
    note = (
        f"상대보호구역(200m 이내, 최근접 학교 {nearest['name']} {nearest['distance_m']}m)."
        + (" 숙박·유흥·위락 등 §7 제한 시설 설치 불가 — 교육지원청 확인 필요."
           if restricted_use else
           " §7 제한 용도(숙박·유흥·위락 등) 해당 시 설치 불가 — 교육지원청 확인 필요.")
    )
    return {
        "name": "교육환경평가",
        "severity": severity,
        "triggered_reasons": reasons,
        "law_ref": law_ref,
        "law_ref_url": law_ref_url,
        "note": note,
    }


# ───────────────────────────────────────────────────────────────────────
# 6. 문화재 현상변경 — 문화재보호법 §13
# ───────────────────────────────────────────────────────────────────────
def _eval_cultural_heritage(
    req: dict, land: dict, nearby_heritages: list[dict] | None = None
) -> dict:
    """역사문화환경 보존지역 판정.

    nearby_heritages:
      None  — API 미조회(키 없음·실패) → 지역지구명 텍스트 단서 기반 기존 동작
      []    — API 성공, 500m 내 지정문화재 없음 → 텍스트 단서만으로 최종 판정
      [...] — 지정문화재 있음 → REQUIRED
    """
    district = (land.get("zone_district") or "") + " " + (req.get("zone_district") or "")
    has_signal = any(kw in district for kw in ("문화재", "역사문화", "보존지역"))

    law_ref = "국가유산기본법, 문화재보호법 §13, 시행령 §21-2"
    law_ref_url = "https://www.law.go.kr/법령/문화재보호법/제13조"
    base_note = (
        "지정문화재 외곽 100~500m(역사문화환경 보존지역) 내 건축 시 시·도지사 사전 허가 대상. "
        "국가유산청 또는 시·도 문화재과에서 지정구역 확인 필요."
    )

    if nearby_heritages:
        # API 확인: 500m 내 지정문화재 존재 → REQUIRED
        nearest = min(nearby_heritages, key=lambda h: h["distance_m"])
        heritage_list = ", ".join(
            f"{h['name']}({h['distance_m']}m)" for h in nearby_heritages[:3]
        )
        return {
            "name": "문화재 현상변경 허가",
            "severity": "REQUIRED",
            "triggered_reasons": [
                f"역사문화환경 보존지역(500m 이내) — {heritage_list}"
            ],
            "law_ref": law_ref,
            "law_ref_url": law_ref_url,
            "note": (
                f"지정문화재 {nearest['name']}까지 {nearest['distance_m']}m."
                " 역사문화환경 보존지역 내 건축 행위기준 고시 확인 후 시·도지사 허가 신청 필요."
            ),
        }

    if nearby_heritages is not None and not nearby_heritages:
        # API 성공, 500m 내 없음 — 텍스트 단서만 남음
        if has_signal:
            return {
                "name": "문화재 현상변경 허가",
                "severity": "REQUIRED",
                "triggered_reasons": [f"지역지구에 문화재 관련 단서 — {district.strip()}"],
                "law_ref": law_ref,
                "law_ref_url": law_ref_url,
                "note": base_note,
            }
        return {
            "name": "문화재 현상변경 허가",
            "severity": "NONE",
            "triggered_reasons": [],
            "law_ref": law_ref,
            "law_ref_url": law_ref_url,
            "note": "반경 500m 내 지정문화재 없음 (국가유산청 API 확인).",
        }

    # nearby_heritages is None → degrade: 기존 텍스트 단서 판정
    return {
        "name": "문화재 현상변경 허가",
        "severity": "REQUIRED" if has_signal else "MAYBE",
        "triggered_reasons": (
            [f"지역지구에 문화재 관련 단서 — {district.strip()}"] if has_signal else []
        ),
        "law_ref": law_ref,
        "law_ref_url": law_ref_url,
        "note": base_note,
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
def evaluate_reviews(
    req: dict,
    land: dict | None = None,
    *,
    nearby_schools: list[dict] | None = None,
    nearby_heritages: list[dict] | None = None,
) -> dict[str, Any]:
    """심의·영향평가 일괄 평가 (11개 항목).

    nearby_schools / nearby_heritages:
      None  → 해당 API 미조회 (degrade, 기존 동작)
      []    → 조회 성공, 결과 없음
      [...] → 조회 성공, 결과 있음

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
        _eval_education(req, land, nearby_schools),
        _eval_cultural_heritage(req, land, nearby_heritages),
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
