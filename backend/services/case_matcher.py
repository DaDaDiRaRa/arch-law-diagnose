"""사내 케이스 매칭 — Competition Analyzer DB 연계.

KUNWON_DB/cases/*.json 디렉토리 스캔 → 같은 용도+지역 케이스 추천.

케이스 JSON 스키마(권장):
  {
    "project_name": "...",
    "address": "...",
    "jurisdiction": "영등포구",
    "building_use": "근린생활시설",
    "zone_use": "제2종일반주거지역",
    "site_area": 500,
    "building_area": 250,
    "total_floor_area": 1500,
    "floors_above": 5,
    "floors_below": 1,
    "height": 18,
    "year": 2024,
    "result": "approved",         // approved | rejected | pending
    "internal_url": "...",         // 사내 PMS 링크 (선택)
    "tags": ["주차완화", "사선검토"]
  }
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _resolve_db_path() -> Path:
    """ENV CASE_DB_PATH → 절대 경로. 기본: 프로젝트 루트의 KUNWON_DB/cases/"""
    raw = os.getenv("CASE_DB_PATH")
    if raw:
        return Path(raw).expanduser().resolve()
    # backend/ 의 부모 = 프로젝트 루트
    project_root = Path(__file__).resolve().parents[2]
    return project_root / "KUNWON_DB" / "cases"


class CaseMatcher:
    def __init__(self) -> None:
        self._db_path = _resolve_db_path()
        self._cases: list[dict] = []
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Lazy 로드. 디렉토리 변경 시 재기동 필요."""
        if self._loaded:
            return
        self._cases = self._scan(self._db_path)
        self._loaded = True
        logger.info("케이스 DB 로드: %s (%d건)", self._db_path, len(self._cases))

    def reload(self) -> int:
        """수동 재로드."""
        self._cases = self._scan(self._db_path)
        self._loaded = True
        return len(self._cases)

    @staticmethod
    def _scan(path: Path) -> list[dict]:
        if not path.exists():
            logger.warning("케이스 DB 디렉토리 없음: %s (빈 결과 반환)", path)
            return []
        cases: list[dict] = []
        for f in path.glob("*.json"):
            try:
                with open(f, encoding="utf-8") as fp:
                    data = json.load(fp)
                if isinstance(data, list):
                    cases.extend([c for c in data if isinstance(c, dict)])
                elif isinstance(data, dict):
                    data["_source_file"] = f.name
                    cases.append(data)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("케이스 파일 파싱 실패 %s: %s", f.name, e)
        return cases

    def match(
        self,
        building_use: str,
        zone_use: str,
        site_area: float | None = None,
        jurisdiction: str | None = None,
        limit: int = 5,
    ) -> dict:
        """유사 케이스 검색.

        Returns:
          {
            "db_path": "...",
            "total_loaded": N,
            "matches": [{score, case, reasons}, ...]
          }
        """
        self._ensure_loaded()

        scored: list[tuple[float, dict, list[str]]] = []
        for c in self._cases:
            score, reasons = _score_case(c, building_use, zone_use, site_area, jurisdiction)
            if score > 0:
                scored.append((score, c, reasons))

        scored.sort(key=lambda x: x[0], reverse=True)
        matches = [
            {"score": round(s, 1), "case": _summarize_case(c), "reasons": r}
            for s, c, r in scored[:limit]
        ]

        return {
            "db_path": str(self._db_path),
            "db_exists": self._db_path.exists(),
            "total_loaded": len(self._cases),
            "matches": matches,
        }


def _score_case(
    case: dict,
    building_use: str,
    zone_use: str,
    site_area: float | None,
    jurisdiction: str | None,
) -> tuple[float, list[str]]:
    """가중 점수 + 매칭 이유 문자열 리스트."""
    score = 0.0
    reasons: list[str] = []

    c_use = (case.get("building_use") or "").strip()
    c_zone = (case.get("zone_use") or "").strip()
    c_jur = (case.get("jurisdiction") or "").strip()
    c_site = case.get("site_area")

    # 용도 매칭 (가장 중요)
    if c_use and building_use:
        if c_use == building_use:
            score += 50
            reasons.append(f"동일 용도({c_use})")
        elif c_use in building_use or building_use in c_use:
            score += 30
            reasons.append(f"유사 용도({c_use})")

    # 용도지역 매칭
    if c_zone and zone_use:
        if c_zone == zone_use:
            score += 30
            reasons.append(f"동일 용도지역({c_zone})")
        elif c_zone in zone_use or zone_use in c_zone:
            score += 20
            reasons.append(f"유사 용도지역({c_zone})")

    # 대지면적 유사도 (±10% / ±30%)
    if site_area and isinstance(c_site, (int, float)) and c_site > 0:
        ratio = abs(c_site - site_area) / site_area
        if ratio <= 0.10:
            score += 20
            reasons.append(f"대지면적 ±10% 이내({c_site}㎡)")
        elif ratio <= 0.30:
            score += 10
            reasons.append(f"대지면적 ±30% 이내({c_site}㎡)")

    # 관할 구역
    if jurisdiction and c_jur:
        if c_jur == jurisdiction or c_jur in jurisdiction or jurisdiction in c_jur:
            score += 10
            reasons.append(f"동일 관할({c_jur})")

    return score, reasons


def _summarize_case(case: dict) -> dict:
    """프론트 노출용 케이스 요약."""
    return {
        "project_name": case.get("project_name", "(이름 없음)"),
        "address": case.get("address", ""),
        "jurisdiction": case.get("jurisdiction", ""),
        "building_use": case.get("building_use", ""),
        "zone_use": case.get("zone_use", ""),
        "site_area": case.get("site_area"),
        "building_area": case.get("building_area"),
        "total_floor_area": case.get("total_floor_area"),
        "floors_above": case.get("floors_above"),
        "floors_below": case.get("floors_below"),
        "height": case.get("height"),
        "year": case.get("year"),
        "result": case.get("result"),
        "internal_url": case.get("internal_url"),
        "tags": case.get("tags", []),
    }
