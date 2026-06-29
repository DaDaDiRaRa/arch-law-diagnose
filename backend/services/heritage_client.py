"""문화재 현상변경 — 지정문화재 근접 조회 (국가유산청 OpenAPI).

역사문화환경 보존지역 (국가유산기본법·문화재보호법 §13):
  지정문화재 외곽 500m 이내 건축물은 시·도지사 사전 허가 대상.
  (시·도별 행위기준 고시로 범위 차등)

HERITAGE_API_KEY: 국가유산청 공공데이터 포털 API 키
  가입: https://www.heritage.go.kr → 공공데이터 → API 신청 (무료)
키 미설정 시 graceful degrade → 지역지구명 텍스트 단서만 사용.
"""
from __future__ import annotations

import logging
import os

import httpx
from dotenv import load_dotenv

from services.http_retry import request_with_retry

load_dotenv()
logger = logging.getLogger(__name__)

_HERITAGE_GPS_URL = (
    "https://www.khs.go.kr/cha/openapi/selectOpenApiDetailListByGPS.do"
)


class HeritageClient:
    def __init__(self) -> None:
        self._key = os.getenv("HERITAGE_API_KEY", "")
        if not self._key:
            logger.info("HERITAGE_API_KEY 미설정 — 국가유산청 API 비활성, 지역지구명 단서만 사용")
        self._http = httpx.AsyncClient(timeout=15)

    async def close(self) -> None:
        await self._http.aclose()

    async def find_nearby_heritages(
        self, lon: float, lat: float, radius_m: int = 500
    ) -> list[dict] | None:
        """반경 내 지정문화재 조회.

        Returns:
            [{name, heritage_type, distance_m}, ...] — 결과 있으면 REQUIRED 판정.
            [] — API 성공, 문화재 없음 → 추가 확인 불필요.
            None — API 실패·키 미설정 → degrade (기존 텍스트 단서 판정 유지).
        """
        if not self._key:
            return None  # degrade

        try:
            params = {
                "ServiceKey": self._key,
                "gpsX": str(lon),
                "gpsY": str(lat),
                "radius": str(radius_m),
                "pageUnit": 10,
                "pageIndex": 1,
                "type": "json",
            }
            r = await request_with_retry(
                self._http, "GET", _HERITAGE_GPS_URL, params=params,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            logger.warning("국가유산청 API 조회 실패: %s", exc)
            return None  # degrade

        # 응답 구조: {"response": {"body": {"items": {"item": [...]}}}}
        # 또는 단순: {"items": [...]}
        try:
            body = data.get("response", {}).get("body", data)
            raw_items = body.get("items") or []
            if isinstance(raw_items, dict):
                raw_items = raw_items.get("item") or []
            if isinstance(raw_items, dict):
                raw_items = [raw_items]  # 단일 결과를 dict으로 감싸는 경우
        except Exception:
            raw_items = []

        results: list[dict] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            name = item.get("ccbaMnm1") or item.get("name", "")
            htype = item.get("ccbaKdcd") or item.get("type", "")
            try:
                dist = int(float(item.get("distance", 9999)))
            except (ValueError, TypeError):
                dist = 9999
            if name:
                results.append({"name": name, "heritage_type": htype, "distance_m": dist})

        return results
