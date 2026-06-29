"""문화재 현상변경 — 지정문화재 근접 조회 (국가유산청 공간정보 Open API).

역사문화환경 보존지역 (국가유산기본법·문화재보호법 §13):
  지정문화재 외곽 100~500m 이내 건축물은 시·도지사 사전 허가(현상변경) 대상.
  (시·도별 행위기준 고시로 범위 차등)

데이터 출처: 국가유산 공간정보 Open API (gis-heritage.go.kr)
  - WFS spca.do — 종목코드(ccbaKdcd)별 전체 지정문화재 좌표 제공.
  - **인증키 불필요** (공개 엔드포인트).
  - 좌표계 = UTM-K(EPSG:5179), 종/횡 좌표. cnX/cnY가 문화재 실제 위치.

동작:
  앱 첫 조회 시 6개 종목(국보·보물·사적·명승·천연기념물·국가민속) 전체 좌표를
  1회 수확해 메모리에 캐시(약 2,560건). 이후 진단마다 질의 좌표(WGS84)를
  UTM-K로 변환해 반경 내 문화재를 거리순으로 반환.
  수확 실패 시 graceful degrade → None 반환(지역지구명 텍스트 단서로 판정).
"""
from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET

import httpx
from pyproj import Transformer

from services.http_retry import request_with_retry

logger = logging.getLogger(__name__)

_SPCA_URL = "https://gis-heritage.go.kr/openapi/xmlService/spca.do"

# 역사문화환경 보존지역(§13) 대상 종목.
#   국가무형유산(17)은 무형이라 현상변경 무관, 등록문화유산(79)은 §53 별도 → 제외.
_TARGET_KINDS = {
    "11": "국보",
    "12": "보물",
    "13": "사적",
    "15": "명승",
    "16": "천연기념물",
    "18": "국가민속문화유산",
}


class HeritageClient:
    def __init__(self) -> None:
        self._http = httpx.AsyncClient(timeout=20)
        # WGS84(lon, lat) → UTM-K(EPSG:5179) — always_xy: 입력 순서 (경도, 위도)
        self._to_utmk = Transformer.from_crs(
            "EPSG:4326", "EPSG:5179", always_xy=True
        )
        self._cache: list[dict] | None = None  # [{name, heritage_type, x, y}]
        self._lock = asyncio.Lock()

    async def close(self) -> None:
        await self._http.aclose()

    async def _load_all(self) -> list[dict] | None:
        """6개 종목 전체 좌표 수확(1회). 성공 시 캐시·반환, 전부 실패 시 None."""
        if self._cache is not None:
            return self._cache
        async with self._lock:
            if self._cache is not None:  # 락 대기 중 다른 코루틴이 적재
                return self._cache

            heritages: list[dict] = []
            for code, kind in _TARGET_KINDS.items():
                try:
                    r = await request_with_retry(
                        self._http, "GET", _SPCA_URL, params={"ccbaKdcd": code},
                    )
                    r.raise_for_status()
                    root = ET.fromstring(r.content)  # bytes → 선언된 인코딩 자동 처리
                except Exception as exc:
                    logger.warning("국가유산청 종목 %s(%s) 수확 실패: %s", code, kind, exc)
                    continue

                added = 0
                for spca in root.findall("spca"):
                    name = (spca.findtext("ccbaMnm") or "").strip()
                    try:
                        x = float(spca.findtext("cnX") or "")
                        y = float(spca.findtext("cnY") or "")
                    except (ValueError, TypeError):
                        continue  # 좌표 없는 항목(무형 등) skip
                    if name:
                        heritages.append(
                            {"name": name, "heritage_type": kind, "x": x, "y": y}
                        )
                        added += 1
                logger.debug("국가유산청 %s: %d건", kind, added)

            if not heritages:
                logger.warning("국가유산청 수확 0건 — degrade (다음 호출 재시도)")
                return None  # 캐시하지 않음 → 일시 장애면 다음 진단에서 재시도

            self._cache = heritages
            logger.info("국가유산청 지정문화재 %d건 메모리 캐시 완료", len(heritages))
            return self._cache

    async def find_nearby_heritages(
        self, lon: float, lat: float, radius_m: int = 500
    ) -> list[dict] | None:
        """반경 내 지정문화재 조회.

        Args:
            lon, lat: 질의 좌표 (WGS84 경도·위도).
            radius_m: 검색 반경(m). 기본 500m(역사문화환경 보존지역 최대 범위).

        Returns:
            [{name, heritage_type, distance_m}, ...] — 가까운 순.
            [] — 수확 성공, 반경 내 지정문화재 없음 → 추가 확인 불필요.
            None — 수확 실패 → degrade (지역지구명 텍스트 단서 판정 유지).
        """
        all_heritages = await self._load_all()
        if all_heritages is None:
            return None  # degrade

        try:
            qx, qy = self._to_utmk.transform(lon, lat)
        except Exception as exc:
            logger.warning("좌표 변환 실패(lon=%s, lat=%s): %s", lon, lat, exc)
            return None

        # UTM-K는 미터 단위 → 평면거리 = 실거리. 제곱비교로 sqrt 최소화.
        r2 = float(radius_m) * float(radius_m)
        hits: list[dict] = []
        for h in all_heritages:
            dx = h["x"] - qx
            dy = h["y"] - qy
            d2 = dx * dx + dy * dy
            if d2 <= r2:
                hits.append({
                    "name": h["name"],
                    "heritage_type": h["heritage_type"],
                    "distance_m": int(d2 ** 0.5),
                })
        hits.sort(key=lambda x: x["distance_m"])
        return hits
