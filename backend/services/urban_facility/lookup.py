"""대지 좌표 → 도시계획시설 저촉 검사 진입점."""
from __future__ import annotations

import functools
from typing import Any

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform as shp_transform

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
) -> dict[str, Any]:
    """대지 폴리곤(WGS84 GeoJSON) ∩ 도시계획시설 → 보정 면적.

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

    sido = sido_code or pnu_to_sido(pnu or "")
    if not sido:
        out["note"] = "시·도 코드 미확인"
        return out

    idx = get_index(sido)
    if idx is None:
        out["note"] = f"해당 시·도({sido}) SHP 데이터 없음"
        return out

    try:
        geom_wgs = shape(parcel_geometry)
    except Exception as e:
        out["note"] = f"폴리곤 파싱 실패: {e}"
        return out

    # WGS84 → EPSG:5174 변환
    tr = _wgs84_to_5174().transform
    parcel_5174 = shp_transform(tr, geom_wgs)
    out["parcel_area_m2"] = round(parcel_5174.area, 2)
    out["checked"] = True

    per_facility, union_area = idx.query_polygon(parcel_5174)
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
) -> dict[str, Any]:
    """좌표 + 시·도로 도시계획시설 저촉 여부 판정.

    반환 dict:
      - checked: bool      좌표/시도 정보가 부족하면 False
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

    sido = sido_code or pnu_to_sido(pnu or "")
    if not sido:
        out["note"] = "시·도 코드를 확인할 수 없어 시설 검사 생략"
        return out

    idx = get_index(sido)
    if idx is None:
        out["note"] = f"해당 시·도({sido}) SHP 데이터 없음"
        return out

    # WGS84 → EPSG:5174
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
