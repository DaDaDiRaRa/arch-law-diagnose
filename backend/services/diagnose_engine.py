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
  - diagnose_fast(): 토지 조회 생략. 합필 진단에서 재사용.
  - skip_ai=True: 설비_소방 AI 호출 생략 (캐시된 결과 재사용).
"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.eum_client import EumClient
from pathlib import Path

from services.cache_manager import CacheManager
from services.calculator import (
    bf_certification,
    coverage,
    crime_prevention,
    far,
    fire_safety,
    height,
    land_use_act,
    landscape,
    multi_use,
    parking,
    public_certification,
    railway_protection,
    urban_facility,
    zone_overlap,
)
from services import building_agreement
from services.far_relief import build_relief_note, compute_relief
from services.land_use_resolver import LandUseResolver, _parse_sido as _extract_sido
from services.llm_client import LLMClient
from services.luris_client import LurisClient
from services.ordinance_resolver import OrdinanceResolver
from services.review_triggers import evaluate_reviews
from services.urban_facility import compute_facility_overlap

logger = logging.getLogger(__name__)

_WEIGHTS_PATH = Path(__file__).parent.parent / "config" / "law_scoring_weights.json"


def _load_weights() -> dict[str, float]:
    with open(_WEIGHTS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["weights"]


_ZONE_LIMITS_PATH = Path(__file__).parent.parent / "config" / "zone_limits.json"
_FAR_DEFAULTS_CACHE: dict | None = None
_COV_DEFAULTS_CACHE: dict | None = None


def _get_default_far_limit(zone_use: str) -> float | None:
    """zone_limits.json 의 floor_area_ratio 기본 한도 조회 (완화 계산 기준)."""
    global _FAR_DEFAULTS_CACHE
    if _FAR_DEFAULTS_CACHE is None:
        with open(_ZONE_LIMITS_PATH, encoding="utf-8") as f:
            _FAR_DEFAULTS_CACHE = json.load(f).get("floor_area_ratio", {})
    from services.zone_use_normalizer import lookup_limit
    return lookup_limit(_FAR_DEFAULTS_CACHE, zone_use)


def _get_default_cov_limit(zone_use: str) -> float | None:
    """zone_limits.json 의 building_coverage_ratio 법정 상한 조회."""
    global _COV_DEFAULTS_CACHE
    if _COV_DEFAULTS_CACHE is None:
        with open(_ZONE_LIMITS_PATH, encoding="utf-8") as f:
            _COV_DEFAULTS_CACHE = json.load(f).get("building_coverage_ratio", {})
    from services.zone_use_normalizer import lookup_limit
    return lookup_limit(_COV_DEFAULTS_CACHE, zone_use)


class DiagnoseEngine:
    def __init__(
        self,
        land_resolver: LandUseResolver,
        cache: CacheManager,
        llm: LLMClient,
        ordinance_resolver: OrdinanceResolver | None = None,
        luris: LurisClient | None = None,
        eum: "EumClient | None" = None,
    ) -> None:
        self._resolver = land_resolver
        self._cache = cache
        self._llm = llm
        self._ordinance = ordinance_resolver
        self._luris = luris
        self._eum = eum

    async def run(self, req: dict) -> dict:
        """전체 진단 — 토지 조회 + 6개 카테고리 + 이력 저장."""
        address: str = req["address"]
        pnu: str = req.get("pnu") or ""

        land = await self._resolver.resolve(address, pnu=pnu)
        # 사용자가 zone_use 직접 지정한 경우 VWorld 결과 override
        if req.get("zone_use_override"):
            land["zone_use"] = req["zone_use_override"]
        # 사용자가 zone_district 직접 지정한 경우 override
        if req.get("zone_district"):
            land["zone_district"] = req["zone_district"]
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
        """토지 조회 생략 — 합필 진단(/api/diagnose/multi)에서 사용.

        Args:
          zone_use: 기존 진단에서 받은 용도지역 (재조회 안 함).
          land_info: 전체 토지 정보 dict. 없으면 zone_use만 반영된 최소 dict 사용.
          skip_ai: True 시 설비_소방 AI 호출 생략.
          cached_fire_safety: skip_ai=True일 때 기존 결과 재활용.
        """
        land = land_info if land_info else {"zone_use": zone_use}
        if "zone_use" not in land:
            land["zone_use"] = zone_use
        # 사용자가 zone_district 지정 시 override
        if req.get("zone_district"):
            land["zone_district"] = req["zone_district"]
        # VWorld WFS 없이 호출될 때 jurisdiction_name을 주소에서 보완
        if not land.get("jurisdiction_name"):
            land["jurisdiction_name"] = _extract_sido(req.get("address", ""))
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
        site_area_input: float = req["site_area"]
        building_area: float = req["building_area"]
        total_floor_area: float = req["total_floor_area"]
        # 용적률 산정용 — 지상 연면적에서 부속용도 주차장 + 피난안전구역 + 경사지붕 대피공간 제외
        # (건축법 시행령 제119조)
        floor_area_above: float = req.get("floor_area_above", total_floor_area)
        parking_above: float = float(req.get("floor_area_parking_above") or 0)
        refuge_area: float = float(req.get("floor_area_refuge") or 0)
        attic_refuge_area: float = float(req.get("floor_area_attic_refuge") or 0)
        floor_area_for_far: float = max(
            0.0,
            floor_area_above - parking_above - refuge_area - attic_refuge_area,
        )
        floors_above: int = req["floors_above"]
        floors_below: int = req.get("floors_below", 0)
        h: float = req["height"]
        units: int | None = req.get("units")
        road_width: float | None = req.get("road_width")
        # 자동 도로폭 fallback — 사용자 미입력 + 토지정보에 자동조회 값 있으면 사용
        road_width_source: str = "user"
        if road_width is None and land.get("road_width_auto"):
            road_width = float(land["road_width_auto"])
            road_width_source = land.get("road_width_source") or "auto"
        landscape_area: float | None = req.get("landscape_area")
        rooftop_landscape_area: float | None = req.get("rooftop_landscape_area")
        pnu: str = req.get("pnu") or ""

        zone_use: str = land.get("zone_use", "")
        if not zone_use:
            logger.warning("용도지역 미확인: 기본 계산 진행 (점수 신뢰도 낮음)")

        jurisdiction_code: str = land.get("jurisdiction_code", "") or (pnu[:5] if len(pnu) >= 5 else "")
        jurisdiction_name: str = land.get("jurisdiction_name", "")

        # ─── 대지면적 자동 보정 (시행령 §3) ────────────────────────────────
        # 도시계획시설 부지는 대지면적에서 제외.
        # 우선순위: 사용자 수동 override > 자동(폴리곤 교차) > 미보정
        site_correction: dict = {
            "applied": False,
            "original_m2": site_area_input,
            "excluded_m2": 0.0,
            "effective_m2": site_area_input,
            "source": None,  # "manual" | "auto" | None
            "overlap_info": None,
            "by_facility": [],
            "note": "",
        }
        manual_excl = req.get("urban_facility_exclude_area")
        if manual_excl not in (None, "", 0):
            try:
                v = float(manual_excl)
                if v > 0:
                    site_correction["applied"] = True
                    site_correction["excluded_m2"] = v
                    site_correction["effective_m2"] = max(0.0, site_area_input - v)
                    site_correction["source"] = "manual"
                    site_correction["note"] = (
                        f"사용자 입력 시설부지 {v:,.1f}㎡ 제외 (시행령 §3)"
                    )
            except (TypeError, ValueError):
                pass

        if not site_correction["applied"] and land.get("parcel_geometry"):
            overlap = compute_facility_overlap(
                parcel_geometry=land["parcel_geometry"],
                pnu=pnu or land.get("pnu"),
            )
            site_correction["overlap_info"] = {
                "checked": overlap["checked"],
                "parcel_area_m2": overlap["parcel_area_m2"],
                "overlap_area_m2": overlap["overlap_area_m2"],
                "overlap_ratio": overlap["overlap_ratio"],
            }
            site_correction["by_facility"] = overlap.get("by_facility", [])
            if overlap["checked"] and overlap["overlap_area_m2"] > 0:
                excl = overlap["overlap_area_m2"]
                # 사용자 입력 site_area보다 더 큰 보정값이 나오면 안 됨 — clamp
                excl = min(excl, site_area_input * 0.999)
                site_correction["applied"] = True
                site_correction["excluded_m2"] = round(excl, 2)
                site_correction["effective_m2"] = round(site_area_input - excl, 2)
                site_correction["source"] = "auto"
                site_correction["note"] = (
                    f"도시계획시설 저촉 {len(overlap['by_facility'])}건 — "
                    f"VWorld 지적도 ∩ 시설 SHP 자동 산정 {excl:,.1f}㎡ 제외 "
                    f"(전체 {overlap['parcel_area_m2']:,.1f}㎡의 "
                    f"{overlap['overlap_ratio']*100:.1f}%) [시행령 §3]"
                )

        site_area: float = site_correction["effective_m2"]

        # 조례 수치 사전 조회 (OrdinanceResolver 있을 때만)
        cov_limit: float | None = None
        cov_source: str | None = None
        far_limit: float | None = None
        far_source: str | None = None
        landscape_limit: float | None = None
        landscape_source: str | None = None
        landscape_is_estimate: bool = False
        if self._ordinance and (jurisdiction_code or jurisdiction_name) and zone_use:
            cov_res = await self._ordinance.resolve(
                jurisdiction_code, jurisdiction_name, zone_use, "building_coverage_ratio"
            )
            far_res = await self._ordinance.resolve(
                jurisdiction_code, jurisdiction_name, zone_use, "floor_area_ratio"
            )
            landscape_res = await self._ordinance.resolve(
                jurisdiction_code, jurisdiction_name, zone_use, "landscape_ratio"
            )
            cov_limit = cov_res.get("value")
            cov_source = _fmt_source(cov_res)
            far_limit = far_res.get("value")
            far_source = _fmt_source(far_res)
            # 조경: 조례 출처 또는 시도 평균 추정값(seed)일 때 override.
            # 순수 시행령 fallback(zone_limits.json)은 calculator 내부에서 처리.
            if landscape_res.get("is_ordinance") or landscape_res.get("is_estimate"):
                landscape_limit = landscape_res.get("value")
                landscape_source = _fmt_source(landscape_res)
                landscape_is_estimate = bool(landscape_res.get("is_estimate"))

        # ─── T3 특례 토글 — cov_limit / far_limit 사전 조정 ───────────────────
        # T3-2: 재정비촉진지구 (도시재정비촉진법 §19)
        #   건폐율: 법정 상한(zone_limits)까지 완화
        #   용적률: 법정 상한 × 1.2배 (단, §19 ②항 3호 명시 상한)
        if req.get("rema_zone"):
            legal_cov = _get_default_cov_limit(zone_use)
            legal_far = _get_default_far_limit(zone_use)
            if legal_cov and (cov_limit is None or cov_limit < legal_cov):
                cov_limit = legal_cov
                cov_source = "재정비촉진지구 특례 — 법정 상한까지 완화 (도시재정비촉진법 §19 ②항 2호)"
            if legal_far:
                far_rema = round(legal_far * 1.2, 2)
                if far_limit is None or far_limit < far_rema:
                    far_limit = far_rema
                    far_source = f"재정비촉진지구 특례 — 법정 상한 {legal_far}% × 1.2 = {far_rema}% (§19 ②항 3호)"

        # T3-3: 리모델링이 쉬운 구조 (건축법 시행령 §6의5 ②항, 공동주택 한정)
        #   용적률 한도 × 1.2배
        if req.get("easy_remodel") and building_use == "공동주택":
            base = far_limit or _get_default_far_limit(zone_use) or 0
            if base > 0:
                far_remodel = round(base * 1.2, 2)
                far_limit = far_remodel
                far_source = f"리모델링이 쉬운 구조 특례 — 기본 한도 {base}% × 1.2 = {far_remodel}% (시행령 §6의5 ②항)"

        # T3-4: 공공지원민간임대주택 (민간임대주택특별법 §21)
        #   건폐율·용적률 → 조례 상한 초과, 법정 상한까지 완화
        #   조건: 공공지원민간임대 연면적 비율 50% 이상
        if req.get("public_rental"):
            legal_cov = _get_default_cov_limit(zone_use)
            legal_far = _get_default_far_limit(zone_use)
            if legal_cov and (cov_limit is None or cov_limit < legal_cov):
                cov_limit = legal_cov
                cov_source = "공공지원민간임대 특례 — 법정 상한까지 완화 (민간임대주택법 §21 1호)"
            if legal_far and (far_limit is None or far_limit < legal_far):
                far_limit = legal_far
                far_source = "공공지원민간임대 특례 — 법정 상한까지 완화 (민간임대주택법 §21 2호)"

        # 행위제한 (LURIS + EUM 교차검증) — zone_use + building_use 적합성
        r_land_use_act = await land_use_act.calculate(
            self._luris,
            zone_use=zone_use,
            building_use=building_use,
            jurisdiction_code=jurisdiction_code,
            eum=self._eum,
        )

        # 신청 주체 — 공공기관 여부에 따라 의무 인증·BF 판정
        applicant_type: str = req.get("applicant_type") or "개인"

        # 결정고시 입력값 — 도시계획시설 저촉 해소 + 건폐율/용적률/높이 한도 우선 적용
        decision_notice_confirmed: bool = bool(req.get("decision_notice_confirmed"))
        decision_far_limit: float | None = (
            float(req["decision_far_limit"]) if req.get("decision_far_limit") else None
        )
        decision_cov_limit: float | None = (
            float(req["decision_cov_limit"]) if req.get("decision_cov_limit") else None
        )
        decision_height_limit: float | None = (
            float(req["decision_height_limit"]) if req.get("decision_height_limit") else None
        )
        if decision_notice_confirmed and decision_cov_limit:
            cov_limit = decision_cov_limit
            cov_source = f"도시계획시설 결정고시 건폐율 한도 {decision_cov_limit}% (국토계획법 §64)"

        # 발주처 지침서 조건 — 법규/조례보다 엄격한 경우에만 덮어씀
        brief: dict = req.get("brief_conditions") or {}
        brief_cov = brief.get("max_bcr_pct")
        brief_far = brief.get("max_far_pct")
        brief_height = brief.get("max_height_m")
        brief_landscape = brief.get("min_landscape_pct")
        if brief_cov and (cov_limit is None or float(brief_cov) < cov_limit):
            cov_limit = float(brief_cov)
            cov_source = f"발주처 지침서 건폐율 한도 {brief_cov}% (법규보다 엄격)"
        if brief_far and (far_limit is None or float(brief_far) < far_limit):
            far_limit = float(brief_far)
            far_source = f"발주처 지침서 용적률 한도 {brief_far}% (법규보다 엄격)"
        if brief_landscape and (landscape_limit is None or float(brief_landscape) > landscape_limit):
            landscape_limit = float(brief_landscape)

        # 도시계획시설 저촉 (SHP 공간 검사)
        r_urban_facility = urban_facility.calculate(
            lat=land.get("lat"),
            lng=land.get("lon"),
            pnu=pnu or land.get("pnu"),
            decision_notice_confirmed=decision_notice_confirmed,
        )

        # 정량 5개 (동기)
        r_coverage = coverage.calculate(building_area, site_area, zone_use, cov_limit, cov_source)

        # 용적률 한도에 완화 적용 (공개공지, 친환경 인증 등 + 사용자 수동 입력)
        base_far_limit = far_limit  # 조례 우선, 없으면 None → far.py 내부에서 zone_limits.json
        if base_far_limit is None:
            # zone_limits.json 기본값을 미리 가져와 완화 계산에 사용
            base_far_limit = _get_default_far_limit(zone_use)
        public_open_space = req.get("public_open_space_area")
        relief = compute_relief(
            base_limit_pct=base_far_limit,
            zone_use=zone_use,
            building_use=building_use,
            site_area=site_area,
            public_open_space_area=public_open_space,
            green_grade=req.get("green_grade"),
            zero_energy_grade=req.get("zero_energy_grade") or req.get("energy_grade"),
            pilot_project=bool(req.get("pilot_project")),
            smart_grade=req.get("smart_grade"),
            long_life_grade=req.get("long_life_grade"),
            far_limit_manual_override=(
                decision_far_limit if (decision_notice_confirmed and decision_far_limit)
                else req.get("far_limit_manual_override")
            ),
            relief_reason_manual=(
                f"도시계획시설 결정고시 용적률 한도 {decision_far_limit}% (국토계획법 §64)"
                if (decision_notice_confirmed and decision_far_limit)
                else req.get("relief_reason_manual")
            ),
        )
        # 완화가 적용되면 final_limit_pct를 far.py 에 전달
        far_limit_effective = relief["final_limit_pct"] if relief["applied"] else far_limit
        far_source_effective = far_source
        if relief["applied"]:
            far_source_effective = (
                "🌿 완화 적용 (자동 추정)"
                if not relief["manual_used"]
                else "✋ 사용자 수동 한도 (심의 결정 등)"
            )

        # 용적률: 지상 연면적 - 부속용도 주차장 - 피난안전구역 - 경사지붕 대피공간 (건축법 시행령 제119조)
        r_far = far.calculate(
            floor_area_for_far, site_area, zone_use, floors_below,
            far_limit_effective, far_source_effective,
            parking_excluded=parking_above,
            refuge_excluded=refuge_area,
            attic_refuge_excluded=attic_refuge_area,
        )
        # notes 끝에 완화 내역 + 면책 문구 추가
        relief_note = build_relief_note(relief)
        if relief_note:
            r_far["notes"] = (r_far.get("notes") or "") + relief_note
            r_far["relief_info"] = relief  # 프론트엔드에서 상세 표시용
        # §60 가로구역별 최고높이 — 사용자 입력 우선, 없으면 DB lookup (좌표 bbox)
        sb_height_m = req.get("street_block_max_height_m")
        sb_source: str | None = None
        if sb_height_m is None or sb_height_m == 0:
            lon = land.get("lon")
            lat = land.get("lat")
            if lon is not None and lat is not None:
                try:
                    sb_hit = await self._cache.lookup_street_block_height(
                        float(lon), float(lat), jurisdiction_code or None,
                    )
                except Exception as e:
                    logger.warning("가로구역 최고높이 lookup 실패: %s", e)
                    sb_hit = None
                if sb_hit:
                    sb_height_m = sb_hit["max_height_m"]
                    block_label = sb_hit.get("block_name") or "가로구역"
                    sb_source = sb_hit.get("source") or block_label

        # 결정고시 높이 한도 — 가로구역 최고높이보다 우선 (명시적 결정고시는 더 구체적)
        if decision_notice_confirmed and decision_height_limit:
            sb_height_m = decision_height_limit
            sb_source = f"도시계획시설 결정고시 높이 한도 {decision_height_limit}m (국토계획법 §64)"

        # 발주처 지침서 높이 한도 — 법규/결정고시보다 엄격한 경우에만 적용
        if brief_height and (sb_height_m is None or float(brief_height) < sb_height_m):
            sb_height_m = float(brief_height)
            sb_source = f"발주처 지침서 높이 한도 {brief_height}m (법규보다 엄격)"

        r_height = height.calculate(
            h, floors_above, zone_use, road_width,
            north_setback_m=req.get("north_setback_m"),
            adjacent_zone_north=req.get("adjacent_zone_north"),
            road_20m_adjacent=req.get("road_20m_adjacent"),
            street_block_max_height_m=sb_height_m,
            parcel_geometry=land.get("parcel_geometry"),
        )
        if sb_source:
            r_height["notes"] = (
                (r_height.get("notes") or "")
                + f"\n📋 가로구역 최고높이 자동 적용: {sb_source}"
            )
            r_height["street_block_source"] = sb_source
        provided_parking = req.get("provided_parking_spaces")
        unit_exclusive_area = req.get("unit_exclusive_area")
        parking_capacity = req.get("parking_capacity")
        r_parking = parking.calculate(
            building_use,
            total_floor_area,
            units=units,
            unit_exclusive_area=unit_exclusive_area,
            provided_spaces=provided_parking,
            capacity=parking_capacity,
        )
        r_landscape = landscape.calculate(
            landscape_area, site_area, zone_use, building_use,
            limit_override=landscape_limit, source_override=landscape_source,
            is_estimate_override=landscape_is_estimate,
            rooftop_landscape_area=rooftop_landscape_area,
        )

        # ─── 건축협정 §110의7 완화 사후 적용 ─────────────────────────────────
        agreement_on = bool(req.get("building_agreement"))
        if agreement_on:
            agreement_landscape_road = bool(req.get("agreement_landscape_road_facing"))
            r_coverage = building_agreement.apply_to_coverage(
                r_coverage, applied=True, zone_use=zone_use,
            )
            r_far = building_agreement.apply_to_far(
                r_far, applied=True, zone_use=zone_use,
            )
            r_landscape = building_agreement.apply_to_landscape(
                r_landscape, applied=True,
                road_facing_integrated=agreement_landscape_road,
            )
            r_height = building_agreement.apply_to_height(
                r_height, applied=True, road_width=road_width,
            )
            # §86 ③항 인동거리(공동주택 한정) 완화는 현재 진단 외 — 안내만
            if (building_use or "") == "공동주택":
                r_height["notes"] = (
                    (r_height.get("notes") or "")
                    + " · ℹ️ 공동주택은 건축협정 시 §86 ③항 인동거리도 1.2배 완화 가능 "
                    "(§110의7 5호 — 현재 자동 진단 외)"
                )

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

        # 공공기관 의무 인증 3종 카드 (가중치 0 → 종합점수 무영향)
        r_public_cert = public_certification.calculate(
            building_use=building_use,
            applicant_type=applicant_type,
            gross_floor_area=total_floor_area,
        )
        r_bf = bf_certification.calculate(
            building_use=building_use,
            applicant_type=applicant_type,
        )
        r_crime_prev = crime_prevention.calculate(building_use=building_use)
        r_multi_use = multi_use.classify(
            building_use=building_use,
            total_floor_area=total_floor_area,
            floors_above=int(req.get("floors_above") or 0),
        )
        r_zone_overlap = zone_overlap.calculate(
            zone_district=land.get("zone_district") or req.get("zone_district"),
            zone_area=land.get("zone_area"),
        )
        r_railway = railway_protection.calculate(
            lat=lat,
            lng=land.get("lon"),
        )

        results = {
            "행위제한": r_land_use_act,
            "도시계획시설": r_urban_facility,
            "건폐율": r_coverage,
            "용적률": r_far,
            "높이_일조": r_height,
            "주차": r_parking,
            "조경": r_landscape,
            "설비_소방": r_fire,
            "공공시설_의무인증": r_public_cert,
            "BF_인증": r_bf,
            "범죄예방_건축기준": r_crime_prev,
            "다중이용건축물": r_multi_use,
            "중첩지구_구역": r_zone_overlap,
            "철도보호지구": r_railway,
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

        # B4: 8개 심의 자동 트리거
        applicable_reviews = evaluate_reviews(req, land)

        # ─── 데이터 품질 요약 ──────────────────────────────────────────────
        dq_issues: list[dict] = []

        from services.zone_use_normalizer import normalize as _norm_zone
        canonical_zone = _norm_zone(zone_use)
        if not zone_use:
            dq_issues.append({
                "level": "error",
                "code": "NO_ZONE_USE",
                "msg": "용도지역 미확인 — 건폐율·용적률·높이 결과 신뢰도 매우 낮음",
            })
        elif canonical_zone is None:
            dq_issues.append({
                "level": "error",
                "code": "ZONE_UNRECOGNIZED",
                "msg": f"용도지역 '{zone_use}' 표준명 매칭 실패 — 한도 자동 조회 불가, 직접 확인 필요",
            })
        elif req.get("zone_use_override"):
            dq_issues.append({
                "level": "info",
                "code": "ZONE_USER_OVERRIDE",
                "msg": f"용도지역 사용자 직접 지정 ({canonical_zone}) — VWorld 자동 조회 미사용",
            })

        if land.get("cache_stale"):
            age = land.get("cache_age_days", 0)
            dq_issues.append({
                "level": "warn",
                "code": "STALE_CACHE",
                "msg": f"토지 정보가 {age}일 전 캐시 데이터입니다 — VWorld 재조회 실패. 용도지역이 변경됐을 수 있습니다.",
            })

        ordinance_used = cov_source is not None and "조례" in cov_source
        if not ordinance_used:
            dq_issues.append({
                "level": "warn",
                "code": "NO_ORDINANCE",
                "msg": "조례 수치 미조회 — 국토계획법 시행령 기본값 사용 (지자체 강화 조례 미반영 가능)",
            })

        if not self._llm.available:
            dq_issues.append({
                "level": "warn",
                "code": "NO_LLM",
                "msg": "AI(Claude) 미설정 — 설비·소방 항목 자동 판단 불가, 수동 검토 필요",
            })

        if self._luris and not self._luris._key:
            dq_issues.append({
                "level": "warn",
                "code": "NO_LURIS",
                "msg": "LURIS 미설정 — 행위제한 적합성 자동 조회 불가 (API 키 확인 필요)",
            })

        if road_width_source == "auto" and road_width:
            dq_issues.append({
                "level": "info",
                "code": "ROAD_WIDTH_AUTO",
                "msg": f"전면도로 폭 {road_width}m 자동 조회됨 (VWorld) — 실제와 다르면 수동 입력으로 override",
            })

        data_quality = {
            "issues": dq_issues,
            "ordinance_used": ordinance_used,
            "llm_used": self._llm.available,
            "luris_used": bool(self._luris and self._luris._key),
            "zone_use_source": (
                "user" if req.get("zone_use_override")
                else ("vworld" if zone_use else "unknown")
            ),
            "road_width_source": road_width_source,
            "road_width_used": road_width,
            "land_cache_stale": land.get("cache_stale", False),
            "land_cache_age_days": land.get("cache_age_days", 0),
        }

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
            "building_use_detail": req.get("building_use_detail"),
            "public_open_space_area": req.get("public_open_space_area"),
            "site_correction": site_correction,
            "applicable_reviews": applicable_reviews,
            "results": results,
            "overall_score": overall,
            "signal": signal,
            "risks": risks,
            "warnings": warnings,
            "data_quality": data_quality,
            "phase": "Phase3",
        }

        if save_history:
            try:
                await self._cache.save_history(address, pnu, req, response)
            except Exception as e:
                logger.warning("이력 저장 실패: %s", e)

        return response


def _fmt_source(res: dict) -> str | None:
    """OrdinanceResolver 결과 → source 문자열."""
    if not res or res.get("value") is None:
        return None
    if res.get("is_estimate"):
        detail = res.get("source_detail") or "시행령 평균 추정값"
        return f"⚠ 추정값 — {detail}"
    if res.get("is_ordinance"):
        detail = res.get("source_detail") or ""
        tag = "🏛 조례"
        return f"{tag} — {detail}" if detail else tag
    detail = res.get("source_detail") or "국토계획법 시행령 별표"
    return f"📋 시행령 — {detail}"


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
