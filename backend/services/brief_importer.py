"""공모지침 분석 결과(_brief.json) → 사전 사업성 입력 매핑.

외부 앱 "Competition Analyzer"가 PDF/DOCX를 추출해 저장한 `_brief.json`을 읽어
사업성 모드의 target_* 입력으로 변환한다.

전송 방식: 공유 디렉터리(BRIEF_DIR) 직접 읽기.
  - Cloud Run에서는 brief 앱의 GCS 버킷(_briefs/)을 GCSFUSE로 마운트한 경로를 지정.
  - 로컬에서는 _brief.json 파일을 모아둔 폴더를 지정.

매핑 원칙:
  - brief_project_info.sites[]가 핵심 — 부지별 면적·건폐율·용적률·높이·공개공지.
  - 주소는 brief_site[]의 "(부지N)" 표기를 부지별로 분해해 자동 채움(E1 강화).
  - 인증 요구(녹색건축·제로에너지)는 완화 레버로, 발주처(공공기관)는 신청주체로 자동 채움.
  - facility_use는 건축법 19용도 매핑표가 아직 없으므로 자동 채우지 않고 힌트만 제공.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# "서울특별시 영등포구" 같은 행정 접두(시·도 + 시·군·구)
_ADMIN_PREFIX_RE = re.compile(
    r"((?:[가-힣]+(?:특별자치시|특별자치도|특별시|광역시|도))\s+[가-힣]+(?:시|군|구))"
)
# "당산동3가 385(부지1)" 처럼 주소부분 + (부지N)
_SITE_ADDR_RE = re.compile(r"([^,()]+?)\s*\(\s*(부지\s*\d+)\s*\)")

# brief 파일명 패턴: "20260619_050919_public" → (날짜8, 시각6, 카테고리)
# 파일을 열지 않고도 날짜·카테고리를 얻기 위해 사용(목록 정렬·필터).
_FNAME_RE = re.compile(r"^(\d{8})_(\d{6})_(.+)$")

# list_briefs 요약 캐시 — {stem: {"mtime": float, "summary": dict | None}}
# 같은 파일(이름+수정시각)은 재파싱하지 않는다. 879KB×수백건을 매번 읽는 비용 방지.
_LIST_CACHE: dict[str, dict] = {}


def _parse_fname(stem: str) -> tuple[str, str]:
    """파일명 stem → (정렬용 타임스탬프 'YYYYMMDDHHMMSS', 카테고리).

    패턴 불일치 시 ('', '') — 정렬에서 뒤로 밀리고 카테고리 필터에 안 걸린다.
    """
    m = _FNAME_RE.match(stem)
    if not m:
        return "", ""
    return m.group(1) + m.group(2), m.group(3)


def _fname_analyzed_at(stem: str) -> str:
    """파일명에서 analyzed_at 폴백(ISO) 생성. 메타가 비었을 때만 사용."""
    m = _FNAME_RE.match(stem)
    if not m:
        return ""
    d, t = m.group(1), m.group(2)
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}T{t[0:2]}:{t[2:4]}:{t[4:6]}"


def _norm_site_id(s: str) -> str:
    """'부지 1' / '부지1' 표기 차이를 흡수."""
    return re.sub(r"\s+", "", s or "")


# 건축법 시설용도 — 사업성 폼 드롭다운과 동일. 자동 채움 후보 판별용.
# 구체적인 용도를 앞에 둬서, 한 항목당 가장 구체적인 1개만 매칭(예: '제1종근린생활시설'이
# '근린생활시설'보다 먼저). 매핑표 부재로 '주민편의시설' 등 비표준 용어는 의도적으로 제외.
_BUILDING_USES = [
    "제1종근린생활시설", "제2종근린생활시설", "근린생활시설",
    "공동주택", "단독주택",
    "공공업무시설", "업무시설",
    "판매시설", "숙박시설", "의료시설", "교육연구시설",
    "문화및집회시설", "종교시설", "운동시설", "노유자시설",
    "위락시설", "공장", "창고시설",
]


def _detect_building_uses(facilities: list[str]) -> list[str]:
    """facilities 괄호표기에서 건축법 시설용도 후보 추출(중복 제거·순서 유지).

    예) ['어린이집(노유자시설)', '부설주차장'] → ['노유자시설']
        ['…(주민편의시설)', '부설주차장'] → []  (주민편의시설은 19용도 아님)
    괄호가 있으면 괄호 안만, 없으면 항목 전체에서 탐색. 한 항목당 가장 구체적 1개.
    """
    found: list[str] = []
    for f in facilities or []:
        if not f:
            continue
        inner = re.findall(r"\(([^)]*)\)", f)
        targets = inner if inner else [f]
        for t in targets:
            for use in _BUILDING_USES:
                if use in t:
                    if use not in found:
                        found.append(use)
                    break  # 한 항목당 가장 구체적 용도 1개만
    return found


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


def _parse_site_addresses(brief: dict) -> dict[str, str]:
    """brief_site[].address의 '(부지N)' 표기를 부지별 주소로 분해.

    예) '서울특별시 영등포구 당산동3가 385(부지1), 당산동3가 370-4(부지2)'
        → {'부지1': '서울특별시 영등포구 당산동3가 385',
           '부지2': '서울특별시 영등포구 당산동3가 370-4'}
    뒤 부지에 시·도·구 접두가 생략되면 앞 부지의 접두를 이어 붙인다.
    """
    sites = brief.get("brief_site")
    if not isinstance(sites, list):
        return {}
    out: dict[str, str] = {}
    prefix = ""
    for entry in sites:
        if not isinstance(entry, dict):
            continue
        raw = (entry.get("address") or "").strip()
        if not raw:
            continue
        for addr_part, site_label in _SITE_ADDR_RE.findall(raw):
            addr_part = addr_part.strip(" ,")
            sid = _norm_site_id(site_label)
            if not sid or not addr_part:
                continue
            m = _ADMIN_PREFIX_RE.match(addr_part)
            if m:
                prefix = m.group(1)  # 이후 부지 주소에 재사용
            elif prefix and not _ADMIN_PREFIX_RE.search(addr_part):
                addr_part = f"{prefix} {addr_part}"
            out.setdefault(sid, addr_part)
    return out


def _map_relief(brief: dict) -> dict:
    """공모지침의 인증 요구 → 사업성 완화 레버 값.

    녹색건축('우수'/'최우수')·제로에너지(ZEB 1~5등급)는 What-If 레버로 직결,
    신재생 비율·BF 등급은 정보 표시용.
    """
    ds = brief.get("brief_design_sustain") or {}
    certs = ds.get("required_certifications") or []
    green = ""
    energy = ""
    labels: list[str] = []
    for c in certs:
        if not isinstance(c, dict):
            continue
        name = (c.get("name") or "").strip()
        grade = (c.get("required_grade") or "").strip()
        if name or grade:
            labels.append(" ".join(x for x in (name, grade) if x))
        blob = f"{name} {grade}"
        if "녹색" in name:
            if "최우수" in blob:
                green = "최우수"
            elif "우수" in blob:
                green = "우수"
        if "제로에너지" in name or "ZEB" in name.upper():
            mz = re.search(r"([1-5])\s*등급", blob)
            if mz:
                energy = mz.group(1)
    # BF 등급 — design_special 자유문장에서 힌트만 추출(레버 아님)
    bf = ""
    dsp = brief.get("brief_design_special") or {}
    mbf = re.search(
        r"(?:BF|장애물\s*없는|배리어[ -]?프리)[^.]{0,20}?(최우수|우수)등급",
        json.dumps(dsp, ensure_ascii=False),
    )
    if mbf:
        bf = mbf.group(1)
    return {
        "green_grade": green,
        "energy_grade": energy,
        "renewable_pct": _to_num(ds.get("renewable_energy_min_pct")),
        "bf_grade": bf,
        "certifications": labels,
    }


def _detect_applicant_type(brief: dict, meta: dict, pinfo: dict) -> str:
    """발주처가 공공기관이면 '공공기관', 아니면 ''(사용자 판단에 맡김)."""
    if (meta.get("facility_type") or "").strip().lower() == "public":
        return "공공기관"
    org = (pinfo.get("organizer") or "").strip()
    if not org:
        ov = brief.get("brief_overview")
        if isinstance(ov, list) and ov and isinstance(ov[0], dict):
            org = (ov[0].get("organizer") or "").strip()
    if org and re.search(r"(구청|시청|도청|군청|교육청|공사|공단|진흥원|정부|청$)", org):
        return "공공기관"
    return ""


def _map_site(site: dict, addr_map: dict[str, str] | None = None) -> dict:
    """brief sites[] 한 건 → 사업성 prefill."""
    facilities = site.get("facilities") or []
    sid = site.get("site_id") or ""
    address = (site.get("address") or "").strip()
    if not address and addr_map:
        address = addr_map.get(_norm_site_id(sid), "")
    # 건축법 시설용도 자동 감지 — 후보가 정확히 1개일 때만 자동 채움(복합·불명은 사용자 선택)
    use_candidates = _detect_building_uses(facilities)
    facility_use = use_candidates[0] if len(use_candidates) == 1 else ""
    return {
        "site_id": sid,
        "address": address,
        "zoning": site.get("zoning") or "",
        "facility_use": facility_use,
        "facility_use_candidates": use_candidates,
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

    addr_map = _parse_site_addresses(brief)
    sites_raw = pinfo.get("sites") or []
    sites = [_map_site(s, addr_map) for s in sites_raw if isinstance(s, dict)]

    # 단일 부지인데 '(부지N)' 표기가 없으면 brief_site 첫 주소를 사용
    if len(sites) == 1 and not sites[0]["address"]:
        bs = brief.get("brief_site")
        if isinstance(bs, list):
            for e in bs:
                if isinstance(e, dict) and (e.get("address") or "").strip():
                    sites[0]["address"] = (e.get("address") or "").strip()
                    break

    # 부지 정보가 없으면 _quantitative의 총 연면적으로 단일 부지 합성
    if not sites:
        quant = brief.get("_quantitative") or {}
        tfa = _to_num(quant.get("total_floor_area_sqm"))
        if tfa:
            sites = [{
                "site_id": "전체",
                "address": "",
                "zoning": "",
                "facility_use": "",
                "facility_use_candidates": [],
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
        "applicant_type": _detect_applicant_type(brief, meta, pinfo),
        "relief": _map_relief(brief),
        "sites": sites,
    }


def _safe_path(file_id: str, base: Path) -> Path:
    """경로 조작 방지 — file_id는 파일명 stem만 허용."""
    name = Path(file_id).name  # 디렉터리 구분자 제거
    candidate = (base / f"{name}.json").resolve()
    if base not in candidate.parents and candidate.parent != base:
        raise ValueError("잘못된 brief 경로")
    return candidate


def _read_summary(path: Path) -> dict | None:
    """brief 파일 1건 → 요약 dict. brief가 아니거나 읽기 실패 시 None.

    파일을 열어야만 얻는 값(공모명·부지수)을 위해 전체 파싱한다.
    (날짜·카테고리는 호출부가 파일명에서 채우므로 여기서 신경 안 씀.)
    """
    stem = path.stem
    try:
        brief = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("[brief] 읽기 실패 %s: %s", path.name, e)
        return None
    if not isinstance(brief, dict):
        return None
    # brief 파일인지 최소 검증
    if "brief_project_info" not in brief and "_brief_meta" not in brief:
        return None
    meta = brief.get("_brief_meta") or {}
    pinfo = brief.get("brief_project_info") or {}
    sites = pinfo.get("sites") or []
    return {
        "file_id": stem,
        "brief_id": meta.get("brief_id") or stem,
        "competition_name": pinfo.get("competition_name") or meta.get("brief_name") or stem,
        "facility_type": meta.get("facility_type") or _parse_fname(stem)[1],
        "analyzed_at": meta.get("analyzed_at") or _fname_analyzed_at(stem),
        "site_count": len(sites),
    }


def _summary_cached(path: Path) -> dict | None:
    """(stem, mtime) 키 캐시 — 변경 없는 파일은 재파싱 생략."""
    stem = path.stem
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    hit = _LIST_CACHE.get(stem)
    if hit is not None and hit["mtime"] == mtime:
        return hit["summary"]
    summary = _read_summary(path)
    _LIST_CACHE[stem] = {"mtime": mtime, "summary": summary}
    return summary


def list_briefs(limit: int = 100, category: str | None = None) -> list[dict]:
    """BRIEF_DIR의 *.json을 스캔해 요약 목록 반환 (최신순).

    성능: 파일명(`YYYYMMDD_HHMMSS_카테고리`)으로 먼저 정렬·필터해(파일 오픈 0건),
    최근 `limit`건만 본문을 읽는다. 읽은 결과는 (이름, 수정시각) 캐시 → 다음 호출 땐
    새/변경 파일만 다시 읽는다. (879KB×수백건 매번 재파싱 방지)

    Args:
      limit: 본문을 읽어 상세를 채울 최대 건수(최근순). 0 이하면 전부.
      category: 파일명 카테고리(public·residential 등)로 필터. None이면 전체.
    """
    base = _resolve_brief_dir()
    if not base.is_dir():
        logger.warning("[brief] 디렉터리 없음: %s", base)
        return []

    # 1) 파일명만으로 정렬·필터 (오픈 0건)
    cands: list[Path] = []
    for path in base.glob("*.json"):
        if category and _parse_fname(path.stem)[1] != category:
            continue
        cands.append(path)
    cands.sort(key=lambda p: _parse_fname(p.stem)[0] or p.stem, reverse=True)

    total = len(cands)
    if limit and limit > 0 and total > limit:
        logger.info("[brief] %d건 중 최근 %d건만 상세 로드 (limit)", total, limit)
        cands = cands[:limit]

    # 2) 최근 N건만 본문 읽기(캐시 경유)
    items = [s for s in (_summary_cached(p) for p in cands) if s is not None]
    return items


def get_brief_mapped(file_id: str) -> dict:
    """file_id의 _brief.json을 읽어 사업성 prefill로 매핑."""
    base = _resolve_brief_dir()
    path = _safe_path(file_id, base)
    if not path.is_file():
        raise FileNotFoundError(f"brief 파일 없음: {file_id}")
    brief = json.loads(path.read_text(encoding="utf-8"))
    return map_brief(brief)
