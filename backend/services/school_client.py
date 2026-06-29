"""교육환경평가 — 학교 위치 조회 (Kakao Places API).

교육환경 보호에 관한 법률 §6 보호구역:
  절대보호구역 : 학교출입문으로부터 직선거리 50m 이내
  상대보호구역 : 학교경계로부터 직선거리 200m 이내 (절대 제외)

Kakao Places API category SC4(학교)로 반경 200m 내 학교 조회.
대학교·대학원·전문대학은 교육환경법 적용 대상 아님 → 필터 제외.
KAKAO_API_KEY 재사용 — 추가 키 불필요.
"""
from __future__ import annotations

import logging
import os

import httpx
from dotenv import load_dotenv

from services.http_retry import request_with_retry

load_dotenv()
logger = logging.getLogger(__name__)

_KAKAO_PLACES_URL = "https://dapi.kakao.com/v2/local/search/category.json"

# 교육환경보호구역 적용 제외 (고등교육법 기관)
_EXCLUDE_KEYWORDS = ("대학교", "대학원", "전문대학")


class SchoolClient:
    def __init__(self) -> None:
        self._key = os.getenv("KAKAO_API_KEY", "")
        if not self._key:
            logger.warning("KAKAO_API_KEY 미설정 — 학교 근접 조회 불가")
        self._http = httpx.AsyncClient(timeout=10)

    async def close(self) -> None:
        await self._http.aclose()

    async def find_nearby_schools(
        self, lon: float, lat: float, radius_m: int = 200
    ) -> list[dict]:
        """반경 내 유치원·초중고·특수학교 조회.

        Returns:
            [{name, distance_m, address}, ...] — 거리 오름차순.
            빈 리스트: 보호구역 외부 (확정).
            None: API 실패 → degrade (MAYBE 유지).
        """
        if not self._key:
            return None  # type: ignore[return-value]  # degrade signal
        try:
            headers = {"Authorization": f"KakaoAK {self._key}"}
            params = {
                "category_group_code": "SC4",
                "x": str(lon),
                "y": str(lat),
                "radius": str(radius_m),
                "sort": "distance",
                "size": 15,
            }
            r = await request_with_retry(
                self._http, "GET", _KAKAO_PLACES_URL,
                params=params, headers=headers,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            logger.warning("학교 근접 조회 실패: %s", exc)
            return None  # type: ignore[return-value]

        results: list[dict] = []
        for place in data.get("documents", []):
            name: str = place.get("place_name", "")
            if any(kw in name for kw in _EXCLUDE_KEYWORDS):
                continue
            try:
                dist = int(float(place.get("distance", 9999)))
            except (ValueError, TypeError):
                dist = 9999
            results.append({
                "name": name,
                "distance_m": dist,
                "address": place.get("road_address_name") or place.get("address_name", ""),
            })
        return results
