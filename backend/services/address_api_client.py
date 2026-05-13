"""행안부 도로명주소 Open API 클라이언트.

주소 자동완성(search)과 PNU 구성에 사용.
API 문서: https://business.juso.go.kr/addrlink/openApi/guide.do
"""
from __future__ import annotations

import os
import logging
import math

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

JUSO_BASE = "https://business.juso.go.kr/addrlink/addrLinkApi.do"


class AddressApiClient:
    def __init__(self) -> None:
        self._key = os.getenv("JUSO_API_KEY", "")
        if not self._key:
            logger.warning("JUSO_API_KEY 미설정 — 주소 검색 불가")
        self._http = httpx.AsyncClient(timeout=10)

    async def close(self) -> None:
        await self._http.aclose()

    async def search(self, keyword: str, count: int = 10) -> list[dict]:
        """키워드로 도로명주소 목록 반환.

        Returns: [{road_addr, jibun_addr, zip_no, bd_mgt_sn, pnu, legal_dong_code, ...}]
        """
        if not self._key:
            return []

        params = {
            "confmKey": self._key,
            "currentPage": 1,
            "countPerPage": min(count, 100),
            "keyword": keyword,
            "resultType": "json",
        }
        try:
            r = await self._http.get(JUSO_BASE, params=params)
            r.raise_for_status()
            body = r.json()
        except Exception as e:
            logger.error("주소 API 오류: %s", e)
            return []

        items = body.get("results", {}).get("juso", []) or []
        return [self._parse_item(i) for i in items]

    # ─── 내부 헬퍼 ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_item(item: dict) -> dict:
        bd_mgt_sn: str = item.get("bdMgtSn", "") or ""
        mt_yn: str = item.get("mtYn", "0") or "0"
        lnbr_mnnm: str = item.get("lnbrMnnm", "0") or "0"
        lnbr_slno: str = item.get("lnbrSlno", "0") or "0"

        legal_dong_code = bd_mgt_sn[:10] if len(bd_mgt_sn) >= 10 else ""
        pnu = _build_pnu(legal_dong_code, mt_yn, lnbr_mnnm, lnbr_slno)

        return {
            "road_addr": item.get("roadAddr", ""),
            "jibun_addr": item.get("jibunAddr", ""),
            "zip_no": item.get("zipNo", ""),
            "si_nm": item.get("siNm", ""),
            "sgg_nm": item.get("sggNm", ""),
            "emd_nm": item.get("emdNm", ""),
            "bd_mgt_sn": bd_mgt_sn,
            "legal_dong_code": legal_dong_code,
            "mt_yn": mt_yn,
            "lnbr_mnnm": lnbr_mnnm,
            "lnbr_slno": lnbr_slno,
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
