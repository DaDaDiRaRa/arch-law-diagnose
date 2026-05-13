"""VWorld OpenAPI 클라이언트.

1. Geocoder   : 주소 → (lon, lat) + 법정동코드
2. 토지이용계획 : PNU 또는 좌표 → 용도지역/지구/구역
   - WFS endpoint: api.vworld.kr/req/wfs (lt_c_lhblpn 레이어)
   - 또는 Data API: api.vworld.kr/req/data

API 키: VWORLD_API_KEY (.env)
"""
from __future__ import annotations

import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GEOCODE_URL = "https://api.vworld.kr/req/address"
WFS_URL = "https://api.vworld.kr/req/wfs"
DATA_URL = "https://api.vworld.kr/req/data"


class VWorldClient:
    def __init__(self) -> None:
        self._key = os.getenv("VWORLD_API_KEY", "")
        if not self._key:
            logger.warning("VWORLD_API_KEY 미설정 — VWorld 조회 불가")
        self._http = httpx.AsyncClient(timeout=15)

    async def close(self) -> None:
        await self._http.aclose()

    # ─── Geocoder ─────────────────────────────────────────────────────────

    async def geocode(self, address: str) -> dict | None:
        """주소 → {lon, lat, legal_dong_code, address_info}.

        Returns None on failure.
        """
        if not self._key:
            return None

        params = {
            "service": "address",
            "request": "getcoord",
            "version": "2.0",
            "crs": "epsg:4326",
            "address": address,
            "refine": "true",
            "simple": "false",
            "format": "json",
            "type": "road",
            "key": self._key,
        }
        try:
            r = await self._http.get(GEOCODE_URL, params=params)
            r.raise_for_status()
            body = r.json()
        except Exception as e:
            logger.error("VWorld Geocoder 오류: %s", e)
            return None

        status = body.get("response", {}).get("status", "")
        if status != "OK":
            # 도로명 실패 시 지번 재시도
            params["type"] = "parcel"
            try:
                r = await self._http.get(GEOCODE_URL, params=params)
                r.raise_for_status()
                body = r.json()
            except Exception as e:
                logger.error("VWorld Geocoder (지번) 오류: %s", e)
                return None
            if body.get("response", {}).get("status", "") != "OK":
                logger.warning("주소 좌표 변환 실패: %s", address)
                return None

        result = body["response"].get("result", {})
        point = result.get("point", {})
        try:
            lon = float(point.get("x", 0))
            lat = float(point.get("y", 0))
        except (TypeError, ValueError):
            return None

        # 법정동코드는 Geocoder 응답에 직접 포함되지 않아 주소 파싱으로 추출
        return {
            "lon": lon,
            "lat": lat,
            "refined_address": result.get("refined", {}).get("text", address),
        }

    # ─── 토지이용계획 (용도지역·지구·구역) ──────────────────────────────

    async def get_land_use(self, lon: float, lat: float) -> dict:
        """좌표 → 용도지역/지구/구역 정보.

        Uses VWorld WFS with lt_c_lhblpn layer.
        Returns {} if unavailable.
        """
        if not self._key:
            return {}

        # CQL 필터로 포인트 내 용도지역 레이어 조회
        cql = f"INTERSECTS(geom,POINT({lon} {lat}))"
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeName": "lt_c_lhblpn",
            "key": self._key,
            "output": "application/json",
            "count": 5,
            "CQL_FILTER": cql,
        }
        try:
            r = await self._http.get(WFS_URL, params=params)
            r.raise_for_status()
            body = r.json()
        except Exception as e:
            logger.error("VWorld WFS 토지이용계획 오류: %s", e)
            return {}

        features = body.get("features", [])
        if not features:
            return {}

        # 여러 레코드(지구 중복 지정) 집계
        zone_use = ""
        zone_districts: list[str] = []
        zone_areas: list[str] = []

        for feat in features:
            props = feat.get("properties", {})
            utype = props.get("uname", "") or props.get("prp_type_nm", "") or ""
            ucode = props.get("ucode", "") or ""
            # 용도지역 코드 100번대
            if ucode.startswith("100") and not zone_use:
                zone_use = utype
            # 용도지구 코드 200번대
            elif ucode.startswith("200") and utype:
                zone_districts.append(utype)
            # 용도구역 코드 300번대
            elif ucode.startswith("300") and utype:
                zone_areas.append(utype)

        # fallback: 첫 feature에서 zone 추출
        if not zone_use and features:
            props = features[0].get("properties", {})
            zone_use = props.get("uname", "") or props.get("prp_type_nm", "")

        return {
            "zone_use": zone_use,
            "zone_district": ", ".join(zone_districts) if zone_districts else "",
            "zone_area": ", ".join(zone_areas) if zone_areas else "",
        }

    # ─── 토지 기본 정보 (공시지가, 지목 등) ─────────────────────────────

    async def get_land_info(self, pnu: str) -> dict:
        """PNU → 공시지가 + 지목 등 토지기본정보.

        Uses VWorld Data API (LT_C_LHPNSPPCE layer 또는 공시지가 레이어).
        Returns {} if unavailable.
        """
        if not self._key or not pnu:
            return {}

        params = {
            "service": "data",
            "request": "GetFeature",
            "data": "LT_C_LHPNSPPCE",
            "key": self._key,
            "format": "json",
            "geometry": "false",
            "attribute": "true",
            "filter": f"pnu='{pnu}'",
        }
        try:
            r = await self._http.get(DATA_URL, params=params)
            r.raise_for_status()
            body = r.json()
        except Exception as e:
            logger.error("VWorld Data API 공시지가 오류: %s", e)
            return {}

        features = (
            body.get("response", {})
            .get("result", {})
            .get("featureCollection", {})
            .get("features", [])
        )
        if not features:
            return {}

        props = features[0].get("properties", {})
        return {
            "official_price": _safe_int(props.get("pblntfPclnd")),
            "land_category": props.get("lndcgr", ""),
            "area": _safe_float(props.get("lndpclAr")),
        }


def _safe_int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _safe_float(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
