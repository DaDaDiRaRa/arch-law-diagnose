"""대지 좌표 → 도시계획시설 저촉 검사 진입점."""
from __future__ import annotations

import functools
from typing import Any

from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform as shp_transform
from shapely.ops import unary_union

from services.urban_facility.categories import (
    category_label,
    category_severity,
)
from services.urban_facility.indexer import get_index
from services.urban_facility.sido import pnu_to_sido


@functools.lru_cache(maxsize=1)
def _wgs84_to_5174() -> Transformer:
    return Transformer.from_crs("EPSG:4326", "EPSG:5174", always_xy=True)


def compute_facility_overlap(
    *,
    parcel_geometry: dict | None,
    pnu: str | None = None,
    sido_code: str | None = None,
    facilities: list[dict] | None = None,
) -> dict[str, Any]:
    """대지 폴리곤(WGS84 GeoJSON) ∩ 도시계획시설 → 보정 면적.

    facilities(VWorld WFS 실시간 시설 목록)가 주어지면 그것을, 아니면 로컬 SHP를 사용.

    Returns:
      {
        checked: bool,
        parcel_area_m2: float | None,
        overlap_area_m2: float,                  # 시설 저촉 면적 합계
        overlap_ratio: float,                    # overlap / parcel
        by_facility: [{uq_code, category, facility_name, area_m2, severity}],
        severity: GREEN | YELLOW | RED | None,
        note: str,
      }
    """
    out: dict[str, Any] = {
        "checked": False,
        "parcel_area_m2": None,
        "overlap_area_m2": 0.0,
        "overlap_ratio": 0.0,
        "by_facility": [],
        "severity": None,
        "note": "",
    }
    if not parcel_geometry:
        out["note"] = "대지 폴리곤 정보 없음 — 면적 보정 검사 미수행"
        return out

    try:
        geom_wgs = shape(parcel_geometry)
    except Exception as e:
        out["note"] = f"폴리곤 파싱 실패: {e}"
        return out

    # WGS84 → EPSG:5174 변환
    tr = _wgs84_to_5174().transform
    parcel_5174 = shp_transform(tr, geom_wgs)

    # 시설 소스: VWorld 실시간(우선) → 로컬 SHP(폴백)
    if facilities is not None:
        per_facility, union_area = _facilities_overlap_5174(facilities, parcel_5174, tr)
    else:
        sido = sido_code or pnu_to_sido(pnu or "")
        if not sido:
            out["note"] = "시·도 코드 미확인"
            return out
        idx = get_index(sido)
        if idx is None:
            out["note"] = f"해당 시·도({sido}) 시설 데이터 없음 (VWorld·SHP 모두 미확보)"
            return out
        per_facility, union_area = idx.query_polygon(parcel_5174)

    out["parcel_area_m2"] = round(parcel_5174.area, 2)
    out["checked"] = True

    if not per_facility:
        out["severity"] = "GREEN"
        out["note"] = "도시계획시설 저촉 없음 — 보정 불필요"
        return out

    worst = "YELLOW"
    by_fac = []
    for rec, area in per_facility:
        uq = rec.get("_uq", "")
        sev = category_severity(uq)
        if sev == "RED":
            worst = "RED"
        by_fac.append({
            "uq_code": uq,
            "category": category_label(uq),
            "severity": sev,
            "facility_name": rec.get("dgm_nm") or rec.get("alias") or "",
            "area_m2": round(area, 2),
            "decision_no": rec.get("wtnnc_sn", ""),
        })

    # union 기준 보정 면적 (대지면적 초과 방지 — clamp)
    overlap = min(union_area, parcel_5174.area)
    out["severity"] = worst
    out["overlap_area_m2"] = round(overlap, 2)
    out["overlap_ratio"] = (
        round(overlap / parcel_5174.area, 4) if parcel_5174.area > 0 else 0.0
    )
    out["by_facility"] = by_fac

    pct = out["overlap_ratio"] * 100
    out["note"] = (
        f"도시계획시설 {len(by_fac)}건 저촉 — 총 {out['overlap_area_m2']:,.1f}㎡ "
        f"({pct:.1f}%). 시행령 §3에 따라 시설부지 면적은 대지면적에서 제외 산정."
    )
    return out


def check_facility_conflict(
    *,
    lat: float | None,
    lng: float | None,
    pnu: str | None = None,
    sido_code: str | None = None,
    facilities: list[dict] | None = None,
) -> dict[str, Any]:
    """좌표로 도시계획시설 저촉 여부 판정.

    facilities(VWorld WFS 실시간 시설 목록)가 주어지면 그것을, 아니면 로컬 SHP를 사용.

    반환 dict:
      - checked: bool      좌표/데이터가 부족하면 False
      - conflicts: [...]   저촉 시설 목록 (UQ코드, 카테고리명, 시설명, 면적 등)
      - severity: GREEN/YELLOW/RED   최상위 신호
      - note: str          사용자 설명
    """
    out: dict[str, Any] = {
        "checked": False,
        "conflicts": [],
        "severity": None,
        "note": "",
    }

    if lat is None or lng is None:
        out["note"] = "좌표 정보 없음 — 도시계획시설 저촉 검사 미수행"
        return out

    # 시설 소스: VWorld 실시간(우선) → 로컬 SHP(폴백)
    if facilities is not None:
        hits = _facilities_at_point(facilities, lng, lat)
    else:
        sido = sido_code or pnu_to_sido(pnu or "")
        if not sido:
            out["note"] = "시·도 코드를 확인할 수 없어 시설 검사 생략"
            return out
        idx = get_index(sido)
        if idx is None:
            out["note"] = f"해당 시·도({sido}) 시설 데이터 없음 (VWorld·SHP 모두 미확보)"
            return out
        x, y = _wgs84_to_5174().transform(lng, lat)
        hits = idx.query(x, y)
    out["checked"] = True

    if not hits:
        out["severity"] = "GREEN"
        out["note"] = "도시계획시설 저촉 없음"
        return out

    # 신호 강도: RED > YELLOW > GREEN
    worst = "YELLOW"
    conflicts = []
    for rec in hits:
        uq = rec.get("_uq", "")
        sev = category_severity(uq)
        if sev == "RED":
            worst = "RED"
        conflicts.append({
            "uq_code": uq,
            "category": category_label(uq),
            "severity": sev,
            "facility_name": rec.get("dgm_nm") or rec.get("alias") or "",
            "alias": rec.get("alias", ""),
            "area_sqm": _parse_float(rec.get("dgm_ar")),
            "decision_no": rec.get("wtnnc_sn", ""),
            "notice_date": rec.get("ntfdate") or rec.get("create_dat", ""),
            "lclas_cd": rec.get("lclas_cl", ""),
            "execution_status": rec.get("excut_se", ""),
        })

    out["severity"] = worst
    out["conflicts"] = conflicts
    out["note"] = _build_note(conflicts, worst)
    return out


def detect_district_unit(
    plans: list[dict] | None,
    *,
    lat: float | None,
    lng: float | None,
) -> dict[str, Any]:
    """좌표가 지구단위계획구역 폴리곤 내부인지 판정 (정보성).

    Args:
        plans: VWorld lt_c_upisuq161 피처 리스트 (None=조회 실패/미수행).
        lat, lng: 대지 좌표(WGS84).

    Returns:
      {
        checked: bool,          # 좌표·데이터가 있어 실제 판정했는지
        inside: bool,           # 지구단위계획구역 내부 여부
        names: [str],           # 해당 구역명(dgm_nm) 목록
        note: str,
      }
    """
    out: dict[str, Any] = {"checked": False, "inside": False, "names": [], "note": ""}
    if plans is None or lat is None or lng is None:
        return out
    out["checked"] = True
    hits = _facilities_at_point(plans, lng, lat)
    if not hits:
        out["note"] = "지구단위계획구역 해당 없음"
        return out
    names = []
    for rec in hits:
        nm = rec.get("dgm_nm") or rec.get("alias") or "지구단위계획구역"
        if nm not in names:
            names.append(nm)
    out["inside"] = True
    out["names"] = names
    out["note"] = (
        f"지구단위계획구역 내 — {', '.join(names)}. "
        "건폐율·용적률·높이·용도는 지구단위계획 결정조서(시행지침)가 별도로 정하므로 "
        "본 진단값과 다를 수 있음. 결정조서 확인 및 도시·군관리계획 적합성 검토 필요."
    )
    return out


def _facilities_at_point(facilities: list[dict], lng: float, lat: float) -> list[dict]:
    """VWorld 시설(WGS84 GeoJSON) 중 점을 포함하는 것 — 점 포함은 좌표계 무관."""
    pt = Point(lng, lat)
    hits = []
    for fac in facilities:
        g = fac.get("geometry")
        if not g:
            continue
        try:
            geom = shape(g)
        except Exception:
            continue
        if geom.covers(pt):
            hits.append(fac)
    return hits


def _facilities_overlap_5174(
    facilities: list[dict], parcel_5174, tr
) -> tuple[list, float]:
    """VWorld 시설 ∩ 대지(EPSG:5174) → ([(rec, area)], union_area). 면적은 5174 기준."""
    per: list = []
    inter_geoms: list = []
    for fac in facilities:
        g = fac.get("geometry")
        if not g:
            continue
        try:
            fac_5174 = shp_transform(tr, shape(g))
        except Exception:
            continue
        inter = fac_5174.intersection(parcel_5174)
        if inter.is_empty or inter.area <= 0:
            continue
        per.append((fac, inter.area))
        inter_geoms.append(inter)
    union_area = unary_union(inter_geoms).area if inter_geoms else 0.0
    return per, union_area


def _parse_float(v: Any) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _build_note(conflicts: list[dict], severity: str) -> str:
    n = len(conflicts)
    cats = sorted({c["category"] for c in conflicts})
    head = (
        f"⛔ 도시계획시설 {n}건 저촉 ({', '.join(cats)})"
        if severity == "RED"
        else f"⚠ 도시계획시설 {n}건 인접/저촉 가능 ({', '.join(cats)})"
    )
    names = ", ".join(f"{c['facility_name'] or c['category']}" for c in conflicts[:3])
    if n > 3:
        names += f" 외 {n - 3}건"
    return f"{head} — {names}. 결정고시 확인 및 매수청구·실시계획 검토 필요."
