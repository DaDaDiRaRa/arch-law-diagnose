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
        # VWorld WFS는 등록된 서비스 URL과 Referer 헤더가 일치해야 인증됨
        service_url = os.getenv("SERVICE_URL", "http://localhost:8000")
        self._wfs_headers = {"Referer": service_url}
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

    # 용도지역 판별: 국토계획법상 지역명 suffix
    _ZONE_USE_SUFFIXES = ("주거지역", "상업지역", "공업지역", "녹지지역")
    # 용도구역 판별
    _ZONE_AREA_KEYWORDS = ("개발제한", "시가화조정", "수산자원보호", "도시자연공원")

    async def get_land_use(self, lon: float, lat: float) -> dict:
        """좌표 → 용도지역/지구/구역 정보.

        VWorld Data API LT_C_UQ111 레이어 (geomFilter=POINT 방식).
        WFS CQL 공간필터 오동작 문제 우회.
        Returns {} if unavailable.
        """
        if not self._key:
            return {}

        params = {
            "service": "data",
            "request": "GetFeature",
            "data": "LT_C_UQ111",
            "key": self._key,
            "format": "json",
            "size": 10,
            "page": 1,
            "geometry": "false",
            "attribute": "true",
            "crs": "EPSG:4326",
            "geomFilter": f"POINT({lon} {lat})",
        }
        try:
            r = await self._http.get(DATA_URL, params=params, headers=self._wfs_headers)
            r.raise_for_status()
            body = r.json()
        except Exception as e:
            logger.error("VWorld Data API 토지이용계획 오류: %s", e)
            return {}

        status = body.get("response", {}).get("status", "")
        logger.info("VWorld Data API status=%s geomFilter=POINT(%s %s)", status, lon, lat)
        if status != "OK":
            logger.warning("VWorld Data API 응답 status=%s body=%s", status, str(body)[:300])
            return {}

        features = (
            body.get("response", {})
            .get("result", {})
            .get("featureCollection", {})
            .get("features", [])
        )
        if not features:
            return {}

        zone_use = ""
        zone_districts: list[str] = []
        zone_areas: list[str] = []

        for feat in features:
            props = feat.get("properties", {})
            uname = (props.get("uname") or "").strip()
            if not uname:
                continue
            if uname.endswith(self._ZONE_USE_SUFFIXES):
                if not zone_use:
                    zone_use = uname
            elif any(kw in uname for kw in self._ZONE_AREA_KEYWORDS):
                zone_areas.append(uname)
            else:
                zone_districts.append(uname)

        # fallback: 첫 non-empty uname
        if not zone_use and features:
            for feat in features:
                uname = (feat.get("properties", {}).get("uname") or "").strip()
                if uname:
                    zone_use = uname
                    break

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

    # ─── 지적 폴리곤 (연속지적도) ────────────────────────────────────────

    async def get_parcel_polygon(self, lon: float, lat: float) -> dict | None:
        """좌표 → 해당 점을 포함하는 지적 필지의 폴리곤 (GeoJSON).

        VWorld LP_PA_CBND_BUBUN (연속지적도) — geomFilter=POINT 방식.
        반환: { "type": "Polygon" | "MultiPolygon", "coordinates": [...] } + properties
        없으면 None.
        """
        if not self._key:
            return None
        params = {
            "service": "data",
            "request": "GetFeature",
            "data": "LP_PA_CBND_BUBUN",
            "key": self._key,
            "format": "json",
            "size": 1,
            "geometry": "true",
            "attribute": "true",
            "crs": "EPSG:4326",
            "geomFilter": f"POINT({lon} {lat})",
        }
        try:
            r = await self._http.get(DATA_URL, params=params, headers=self._wfs_headers)
            r.raise_for_status()
            body = r.json()
        except Exception as e:
            logger.error("VWorld 지적 폴리곤 조회 오류: %s", e)
            return None

        if body.get("response", {}).get("status") != "OK":
            return None
        feats = (
            body.get("response", {})
            .get("result", {})
            .get("featureCollection", {})
            .get("features", [])
        )
        if not feats:
            return None
        f = feats[0]
        return {
            "geometry": f.get("geometry"),
            "properties": f.get("properties", {}),
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
