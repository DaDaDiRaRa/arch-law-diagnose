"""토지이용계획 리졸버.

주소(또는 PNU) → 용도지역/지구/구역 + 행정구역코드를 통합 반환.
SQLite 캐시 우선 조회 → 미스 시 VWorld API 호출.
"""
from __future__ import annotations

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
        if pnu:
            cached = await self._cache.get_land_info(pnu)
            if cached and not cached.get("cache_stale"):
                logger.debug("캐시 hit: PNU=%s (age=%d일)", pnu, cached["cache_age_days"])
                cached["cache_hit"] = True
                return cached

        # 2. 좌표 확인 — 없으면 Geocoder 호출
        if lon is None or lat is None:
            geo = await self._vworld.geocode(address)
            if not geo:
                logger.warning("좌표 변환 실패: %s", address)
                return _empty_result(address, pnu)
            lon = geo["lon"]
            lat = geo["lat"]

        # 3. VWorld WFS로 용도지역 조회
        zone_info = await self._vworld.get_land_use(lon, lat)
        if not zone_info.get("zone_use"):
            logger.warning("용도지역 조회 결과 없음: lon=%.6f lat=%.6f", lon, lat)

        # 4. VWorld Data API로 공시지가·지목 조회
        land_extra = {}
        if pnu:
            land_extra = await self._vworld.get_land_info(pnu)

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
