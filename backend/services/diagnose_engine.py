"""진단 엔진 — Phase 3.

흐름:
  1. 주소 → PNU (행안부 API, input에서 전달받음)
  2. PNU + 좌표 → 용도지역/지구 (VWorld, Lazy Cache)
  3. 카테고리 계산 6개
     - 정량 4: 건폐율, 용적률, 높이, 주차
     - 정량+조례 1: 조경
     - 정성(AI) 1: 설비_소방
  4. 가중치 적용 종합 점수
  5. 진단 이력 저장

Phase 3 추가:
  - diagnose_fast(): 토지 조회 생략. What-if·시나리오 비교용.
  - skip_ai=True: 설비_소방 AI 호출 생략 (캐시된 결과 재사용).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from services.cache_manager import CacheManager
from services.calculator import coverage, far, fire_safety, height, landscape, parking
from services.land_use_resolver import LandUseResolver
from services.llm_client import LLMClient

logger = logging.getLogger(__name__)

_WEIGHTS_PATH = Path(__file__).parent.parent / "config" / "law_scoring_weights.json"


def _load_weights() -> dict[str, float]:
    with open(_WEIGHTS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["weights"]


class DiagnoseEngine:
    def __init__(
        self,
        land_resolver: LandUseResolver,
        cache: CacheManager,
        llm: LLMClient,
    ) -> None:
        self._resolver = land_resolver
        self._cache = cache
        self._llm = llm

    async def run(self, req: dict) -> dict:
        """전체 진단 — 토지 조회 + 6개 카테고리 + 이력 저장."""
        address: str = req["address"]
        pnu: str = req.get("pnu") or ""

        land = await self._resolver.resolve(address, pnu=pnu)
        return await self._diagnose(req, land, save_history=True, skip_ai=False)

    async def diagnose_fast(
        self,
        req: dict,
        zone_use: str,
        land_info: dict | None = None,
        *,
        skip_ai: bool = False,
        cached_fire_safety: dict | None = None,
    ) -> dict:
        """토지 조회 생략 — What-if/시나리오 비교에서 사용.

        Args:
          zone_use: 기존 진단에서 받은 용도지역 (재조회 안 함).
          land_info: 전체 토지 정보 dict. 없으면 zone_use만 반영된 최소 dict 사용.
          skip_ai: True 시 설비_소방 AI 호출 생략.
          cached_fire_safety: skip_ai=True일 때 기존 결과 재활용.
        """
        land = land_info if land_info else {"zone_use": zone_use}
        if "zone_use" not in land:
            land["zone_use"] = zone_use
        return await self._diagnose(
            req,
            land,
            save_history=False,
            skip_ai=skip_ai,
            cached_fire_safety=cached_fire_safety,
        )

    async def _diagnose(
        self,
        req: dict,
        land: dict,
        *,
        save_history: bool,
        skip_ai: bool = False,
        cached_fire_safety: dict | None = None,
    ) -> dict:
        """공통 진단 본체 — 6개 계산기 + 점수 + 신호 + 응답 빌드."""
        address: str = req["address"]
        building_use: str = req["building_use"]
        site_area: float = req["site_area"]
        building_area: float = req["building_area"]
        total_floor_area: float = req["total_floor_area"]
        floors_above: int = req["floors_above"]
        floors_below: int = req.get("floors_below", 0)
        h: float = req["height"]
        units: int | None = req.get("units")
        road_width: float | None = req.get("road_width")
        landscape_area: float | None = req.get("landscape_area")
        pnu: str = req.get("pnu") or ""

        zone_use: str = land.get("zone_use", "")
        if not zone_use:
            logger.warning("용도지역 미확인: 기본 계산 진행 (점수 신뢰도 낮음)")

        # 정량 5개 (동기)
        r_coverage = coverage.calculate(building_area, site_area, zone_use)
        r_far = far.calculate(total_floor_area, site_area, zone_use, floors_below)
        r_height = height.calculate(h, floors_above, zone_use, road_width)
        r_parking = parking.calculate(building_use, total_floor_area, units=units)
        r_landscape = landscape.calculate(landscape_area, site_area, zone_use, building_use)

        # 설비_소방 — AI 호출 (선택적 스킵)
        if skip_ai and cached_fire_safety is not None:
            r_fire = {
                **cached_fire_safety,
                "notes": (cached_fire_safety.get("notes", "") + " [What-if: 기본 진단 결과 재사용]").strip(),
            }
        elif skip_ai:
            r_fire = fire_safety.skipped_result(
                "What-if 모드 — AI 재판단 생략. 기본 진단 결과 참조."
            )
        else:
            r_fire = await fire_safety.calculate(
                self._llm,
                building_use=building_use,
                floors_above=floors_above,
                floors_below=floors_below,
                height=h,
                total_floor_area=total_floor_area,
                units=units,
            )

        results = {
            "건폐율": r_coverage,
            "용적률": r_far,
            "높이_일조": r_height,
            "주차": r_parking,
            "조경": r_landscape,
            "설비_소방": r_fire,
        }

        overall, _confidence_min = _weighted_score(results)

        risks = [
            {"category": k, "reason": v["notes"]}
            for k, v in results.items()
            if v.get("pass") is False
        ]
        warnings = [
            {"category": k, "reason": v["notes"]}
            for k, v in results.items()
            if v.get("pass") is None
        ]

        if risks:
            signal = "RED"
        elif warnings or (overall is not None and overall < 7.0):
            signal = "YELLOW"
        else:
            signal = "GREEN"

        response = {
            "address": address,
            "land_info": {
                "zone_use": zone_use,
                "zone_district": land.get("zone_district", ""),
                "zone_area": land.get("zone_area", ""),
                "land_category": land.get("land_category", ""),
                "official_price": land.get("official_price"),
                "lon": land.get("lon"),
                "lat": land.get("lat"),
                "pnu": land.get("pnu", pnu),
                "cache_hit": land.get("cache_hit", False),
                "cache_age_days": land.get("cache_age_days", 0),
                "cache_stale": land.get("cache_stale", False),
            },
            "results": results,
            "overall_score": overall,
            "signal": signal,
            "risks": risks,
            "warnings": warnings,
            "phase": "Phase3",
        }

        if save_history:
            try:
                await self._cache.save_history(address, pnu, req, response)
            except Exception as e:
                logger.warning("이력 저장 실패: %s", e)

        return response


def _weighted_score(results: dict) -> tuple[float | None, int]:
    """가중평균 종합 점수. 점수 미확인 항목 제외."""
    weights = _load_weights()
    total_w = 0.0
    weighted_sum = 0.0
    min_confidence = 5

    for category, r in results.items():
        score = r.get("score")
        conf = r.get("confidence", 1)
        w = weights.get(category, 0)

        if score is None or w == 0:
            continue

        weighted_sum += score * w
        total_w += w
        if conf < min_confidence:
            min_confidence = conf

    if total_w == 0:
        return None, 1

    return round(weighted_sum / total_w, 2), min_confidence
