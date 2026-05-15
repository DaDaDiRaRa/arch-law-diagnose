"""토지이용계획 리졸버.

주소(또는 PNU) → 용도지역/지구/구역 + 행정구역코드를 통합 반환.
SQLite 캐시 우선 조회 → 미스 시 VWorld API 호출.
"""
from __future__ import annotations

import asyncio
import logging
import re

from services.cache_manager import CacheManager
from services.vworld_client import VWorldClient

logger = logging.getLogger(__name__)

_SIDO_RE = re.compile(
    r"^(서울특별시|부산광역시|대구광역시|인천광역시|광주광역시|대전광역시|울산광역시"
    r"|세종특별자치시|경기도|강원도|충청북도|충청남도|전라북도|전라남도|경상북도|경상남도|제주특별자치도)"
)


def _parse_sido(address: str) -> str:
    """주소 문자열에서 시도명 추출. 실패 시 빈 문자열."""
    m = _SIDO_RE.match(address.strip())
    return m.group(1) if m else ""


class LandUseResolver:
    def __init__(self, vworld: VWorldClient, cache: CacheManager) -> None:
        self._vworld = vworld
        self._cache = cache

    async def resolve(
        self,
        address: str,
        pnu: str = "",
        lon: float | None = None,
        lat: float | None = None,
    ) -> dict:
        """토지이용계획 정보 반환.

        캐시 hit → 즉시 반환.
        캐시 miss → VWorld 조회 → 캐시 저장.

        Returns:
          {
            zone_use, zone_district, zone_area,
            land_category, official_price, lon, lat,
            pnu, jurisdiction_code,
            cache_hit, cache_age_days, cache_stale
          }
        """
        # 1. PNU 기반 캐시 조회
        stale_cached: dict | None = None
        if pnu:
            cached = await self._cache.get_land_info(pnu)
            if cached:
                if not cached.get("cache_stale"):
                    # 캐시 hit — 단, 구버전 캐시에 road_width_auto 없으면 도로폭만 추가 조회 후 갱신
                    if (
                        cached.get("road_width_auto") is None
                        and cached.get("lon") is not None
                        and cached.get("lat") is not None
                    ):
                        logger.info("캐시 hit이지만 road_width_auto 누락 — VWorld 도로폭만 보충 조회")
                        road = await self._vworld.get_road_width(
                            float(cached["lon"]), float(cached["lat"])
                        )
                        if road:
                            cached["road_width_auto"] = road["road_width_m"]
                            cached["road_width_source"] = road["source"]
                            try:
                                await self._cache.set_land_info(pnu, address, cached)
                            except Exception as e:
                                logger.warning("캐시 갱신 실패 (road_width): %s", e)
                    logger.debug("캐시 hit: PNU=%s (age=%d일)", pnu, cached["cache_age_days"])
                    cached["cache_hit"] = True
                    return cached
                else:
                    stale_cached = cached  # 재조회 실패 시 fallback용

        # 2. 좌표 확인 — 없으면 Geocoder 호출
        if lon is None or lat is None:
            geo = await self._vworld.geocode(address)
            if not geo:
                logger.warning("좌표 변환 실패: %s", address)
                if stale_cached:
                    logger.warning(
                        "VWorld 조회 실패 — stale 캐시 사용 (PNU=%s, age=%d일)",
                        pnu, stale_cached["cache_age_days"],
                    )
                    stale_cached["cache_hit"] = True
                    return stale_cached
                return _empty_result(address, pnu)
            lon = geo["lon"]
            lat = geo["lat"]

        # 3·4. 용도지역 + 공시지가·지목 + 지적 폴리곤 + 도로폭 — 병렬 호출
        zone_task = self._vworld.get_land_use(lon, lat)
        info_task = self._vworld.get_land_info(pnu) if pnu else asyncio.sleep(0, result={})
        parcel_task = self._vworld.get_parcel_polygon(lon, lat)
        road_task = self._vworld.get_road_width(lon, lat)
        zone_info, land_extra, parcel, road = await asyncio.gather(
            zone_task, info_task, parcel_task, road_task, return_exceptions=False
        )
        if not zone_info.get("zone_use"):
            logger.warning("용도지역 조회 결과 없음: lon=%.6f lat=%.6f", lon, lat)
            if stale_cached:
                logger.warning(
                    "용도지역 조회 실패 — stale 캐시 사용 (PNU=%s, age=%d일)",
                    pnu, stale_cached["cache_age_days"],
                )
                stale_cached["cache_hit"] = True
                return stale_cached
        parcel_geometry = parcel.get("geometry") if parcel else None
        # PNU 보정 — 사용자가 비워서 보내도 폴리곤 props 에서 추출 가능
        if not pnu and parcel:
            pnu = (parcel.get("properties", {}).get("pnu") or "").strip() or pnu

        # 5. 결합
        result: dict = {
            "zone_use": zone_info.get("zone_use", ""),
            "zone_district": zone_info.get("zone_district", ""),
            "zone_area": zone_info.get("zone_area", ""),
            "land_category": land_extra.get("land_category", ""),
            "official_price": land_extra.get("official_price"),
            "district_plan": "",
            "urban_facility": "",
            "lon": lon,
            "lat": lat,
            "pnu": pnu,
            "parcel_geometry": parcel_geometry,
            "road_width_auto": (road or {}).get("road_width_m"),
            "road_width_source": (road or {}).get("source"),
            "jurisdiction_code": pnu[:5] if len(pnu) >= 5 else "",
            "jurisdiction_name": _parse_sido(address),
            "cache_hit": False,
            "cache_age_days": 0,
            "cache_stale": False,
        }

        # 6. 캐시 저장
        if pnu:
            await self._cache.set_land_info(pnu, address, result)

        return result


def _empty_result(address: str, pnu: str) -> dict:
    return {
        "zone_use": "",
        "zone_district": "",
        "zone_area": "",
        "land_category": "",
        "official_price": None,
        "district_plan": "",
        "urban_facility": "",
        "lon": None,
        "lat": None,
        "pnu": pnu,
        "jurisdiction_code": "",
        "jurisdiction_name": _parse_sido(address),
        "cache_hit": False,
        "cache_age_days": 0,
        "cache_stale": False,
        "error": f"좌표 변환 실패: {address}",
    }
