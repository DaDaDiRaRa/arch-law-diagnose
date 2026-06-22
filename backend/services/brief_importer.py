"""공모지침 분석 결과(_brief.json) → 사전 사업성 입력 매핑.

외부 앱 "Competition Analyzer"가 PDF/DOCX를 추출해 저장한 `_brief.json`을 읽어
사업성 모드의 target_* 입력으로 변환한다.

전송 방식: 공유 디렉터리(BRIEF_DIR) 직접 읽기.
  - Cloud Run에서는 brief 앱의 GCS 버킷(_briefs/)을 GCSFUSE로 마운트한 경로를 지정.
  - 로컬에서는 _brief.json 파일을 모아둔 폴더를 지정.

매핑 원칙:
  - brief_project_info.sites[]가 핵심 — 부지별 면적·건폐율·용적률·높이·공개공지.
  - address/zoning은 brief에 없을 수 있음(null) → 사업성 모드에서 사용자가 주소 입력.
  - facility_use는 건축법 19용도 매핑표가 아직 없으므로 자동 채우지 않고 힌트만 제공.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _resolve_brief_dir() -> Path:
    raw = os.getenv("BRIEF_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    # 기본값 — 프로젝트 루트/data/briefs
    project_root = Path(__file__).resolve().parents[2]
    return (project_root / "data" / "briefs").resolve()


def _to_num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _map_site(site: dict) -> dict:
    """brief sites[] 한 건 → 사업성 prefill."""
    facilities = site.get("facilities") or []
    return {
        "site_id": site.get("site_id") or "",
        "address": site.get("address") or "",
        "zoning": site.get("zoning") or "",
        "facility_hint": ", ".join(f for f in facilities if f) or "",
        "site_area_sqm": _to_num(site.get("site_area_sqm")),
        "target_floor_area_sqm": _to_num(site.get("floor_area_sqm")),
        "target_building_coverage_pct": _to_num(site.get("building_coverage_pct")),
        "target_far_pct": _to_num(site.get("floor_area_ratio_pct")),
        "target_max_height_m": _to_num(site.get("max_height_m")),
        "target_open_space_sqm": _to_num(site.get("open_space_sqm")),
        "open_space_notes": site.get("open_space_notes") or "",
    }


def map_brief(brief: dict) -> dict:
    """_brief.json 전체 → 사업성 prefill 구조.

    Returns:
      {brief_id, competition_name, facility_type, source_format, analyzed_at,
       sites: [ {site_id, address, facility_hint, site_area_sqm,
                 target_floor_area_sqm, target_building_coverage_pct,
                 target_far_pct, target_max_height_m, target_open_space_sqm,
                 open_space_notes} ]}
    """
    meta = brief.get("_brief_meta") or {}
    pinfo = brief.get("brief_project_info") or {}

    sites_raw = pinfo.get("sites") or []
    sites = [_map_site(s) for s in sites_raw if isinstance(s, dict)]

    # 부지 정보가 없으면 _quantitative의 총 연면적으로 단일 부지 합성
    if not sites:
        quant = brief.get("_quantitative") or {}
        tfa = _to_num(quant.get("total_floor_area_sqm"))
        if tfa:
            sites = [{
                "site_id": "전체",
                "address": "",
                "zoning": "",
                "facility_hint": meta.get("facility_type") or "",
                "site_area_sqm": None,
                "target_floor_area_sqm": tfa,
                "target_building_coverage_pct": None,
                "target_far_pct": None,
                "target_max_height_m": None,
                "target_open_space_sqm": None,
                "open_space_notes": "",
            }]

    return {
        "brief_id": meta.get("brief_id") or "",
        "competition_name": pinfo.get("competition_name") or meta.get("brief_name") or "",
        "facility_type": meta.get("facility_type") or "",
        "source_format": meta.get("source_format") or "",
        "analyzed_at": meta.get("analyzed_at") or "",
        "sites": sites,
    }


def _safe_path(file_id: str, base: Path) -> Path:
    """경로 조작 방지 — file_id는 파일명 stem만 허용."""
    name = Path(file_id).name  # 디렉터리 구분자 제거
    candidate = (base / f"{name}.json").resolve()
    if base not in candidate.parents and candidate.parent != base:
        raise ValueError("잘못된 brief 경로")
    return candidate


def list_briefs() -> list[dict]:
    """BRIEF_DIR의 *.json을 스캔해 요약 목록 반환 (최신순)."""
    base = _resolve_brief_dir()
    if not base.is_dir():
        logger.warning("[brief] 디렉터리 없음: %s", base)
        return []

    items: list[dict] = []
    for path in base.glob("*.json"):
        try:
            brief = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("[brief] 읽기 실패 %s: %s", path.name, e)
            continue
        if not isinstance(brief, dict):
            continue
        # brief 파일인지 최소 검증
        if "brief_project_info" not in brief and "_brief_meta" not in brief:
            continue
        meta = brief.get("_brief_meta") or {}
        pinfo = brief.get("brief_project_info") or {}
        sites = pinfo.get("sites") or []
        items.append({
            "file_id": path.stem,
            "brief_id": meta.get("brief_id") or path.stem,
            "competition_name": pinfo.get("competition_name") or meta.get("brief_name") or path.stem,
            "facility_type": meta.get("facility_type") or "",
            "analyzed_at": meta.get("analyzed_at") or "",
            "site_count": len(sites),
        })
    items.sort(key=lambda x: x.get("analyzed_at") or "", reverse=True)
    return items


def get_brief_mapped(file_id: str) -> dict:
    """file_id의 _brief.json을 읽어 사업성 prefill로 매핑."""
    base = _resolve_brief_dir()
    path = _safe_path(file_id, base)
    if not path.is_file():
        raise FileNotFoundError(f"brief 파일 없음: {file_id}")
    brief = json.loads(path.read_text(encoding="utf-8"))
    return map_brief(brief)
