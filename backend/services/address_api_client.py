"""카카오 로컬 API 주소 검색 클라이언트.

주소 자동완성(search)과 PNU 구성에 사용.
API 문서: https://developers.kakao.com/docs/latest/ko/local/dev-guide#address-coord
"""
from __future__ import annotations

import os
import logging

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

KAKAO_BASE = "https://dapi.kakao.com/v2/local/search/address.json"


class AddressApiClient:
    def __init__(self) -> None:
        self._key = os.getenv("KAKAO_API_KEY", "")
        if not self._key:
            logger.warning("KAKAO_API_KEY 미설정 — 주소 검색 불가")
        self._http = httpx.AsyncClient(
            timeout=10,
            headers={"Authorization": f"KakaoAK {self._key}"},
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def search(self, keyword: str, count: int = 10) -> list[dict]:
        """키워드로 주소 목록 반환 (도로명 + 지번 모두 지원).

        Returns: [{road_addr, jibun_addr, zip_no, pnu, legal_dong_code, ...}]
        """
        if not self._key:
            return []

        params = {
            "query": keyword,
            "analyze_type": "similar",
            "page": 1,
            "size": min(count, 30),
        }
        try:
            r = await self._http.get(KAKAO_BASE, params=params)
            r.raise_for_status()
            body = r.json()
        except Exception as e:
            logger.error("카카오 주소 API 오류: %s", e)
            return []

        documents = body.get("documents", []) or []
        return [self._parse_item(d) for d in documents]

    # ─── 내부 헬퍼 ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_item(doc: dict) -> dict:
        addr = doc.get("address") or {}
        road = doc.get("road_address") or {}

        b_code: str = addr.get("b_code", "") or ""
        mountain_yn: str = addr.get("mountain_yn", "N") or "N"
        main_no: str = addr.get("main_address_no", "0") or "0"
        sub_no: str = addr.get("sub_address_no", "0") or "0"

        mt_yn = "1" if mountain_yn == "Y" else "0"
        legal_dong_code = b_code[:10] if len(b_code) >= 10 else b_code
        pnu = _build_pnu(legal_dong_code, mt_yn, main_no, sub_no)

        jibun_addr = addr.get("address_name", "")
        road_addr = road.get("address_name", "")

        return {
            "road_addr": road_addr,
            "jibun_addr": jibun_addr,
            "zip_no": road.get("zone_no", "") or addr.get("zip_code", ""),
            "si_nm": addr.get("region_1depth_name", ""),
            "sgg_nm": addr.get("region_2depth_name", ""),
            "emd_nm": addr.get("region_3depth_name", ""),
            "legal_dong_code": legal_dong_code,
            "mt_yn": mt_yn,
            "lnbr_mnnm": main_no,
            "lnbr_slno": sub_no,
            "pnu": pnu,
        }


def _build_pnu(legal_dong_code: str, mt_yn: str, mnnm: str, slno: str) -> str:
    """PNU 19자리 조합: 법정동코드(10) + 산여부(1) + 본번(4) + 부번(4)."""
    if not legal_dong_code or len(legal_dong_code) < 10:
        return ""
    try:
        main = str(int(mnnm)).zfill(4)
        sub = str(int(slno)).zfill(4)
    except (ValueError, TypeError):
        main, sub = "0000", "0000"
    return f"{legal_dong_code}{mt_yn}{main}{sub}"
