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

        Kakao API 의 지번주소 검색이 공백/동명에 민감해서, 1차 결과가 빈 경우
        query 변형(공백 정규화·번지 분리 등)으로 재시도하고 결과를 합친다.

        Returns: [{road_addr, jibun_addr, zip_no, pnu, legal_dong_code, ...}]
        """
        if not self._key:
            return []

        # 1차 — 사용자 입력 그대로
        items = await self._search_once(keyword, count)
        if items:
            return items

        # 2차 — 변형 query 들로 재시도
        variants = _generate_query_variants(keyword)
        seen_pnu: set[str] = set()
        merged: list[dict] = []
        for v in variants:
            if v == keyword:
                continue
            extra = await self._search_once(v, count)
            for it in extra:
                key = it.get("pnu") or it.get("jibun_addr") or it.get("road_addr")
                if key and key not in seen_pnu:
                    seen_pnu.add(key)
                    merged.append(it)
            if len(merged) >= count:
                break
        if merged:
            logger.info("주소 검색 fallback 성공: '%s' → %d건 (변형 query 사용)", keyword, len(merged))
        return merged

    async def _search_once(self, keyword: str, count: int) -> list[dict]:
        """단일 query → Kakao API 호출."""
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
            logger.error("카카오 주소 API 오류 (query='%s'): %s", keyword, e)
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


def _generate_query_variants(keyword: str) -> list[str]:
    """Kakao 지번주소 검색 실패 시 시도할 query 변형 목록.

    핵심 변형:
        - 끝에 공백 추가 (Kakao analyze_type=similar 의 본번 완성 인식 트릭)
        - 동·번지 공백 정규화
        - 시도 prefix 제거
        - "번지" 접미사

    예: "영등포구 당산동3가 385" →
        - "영등포구 당산동3가 385 "  (trailing space — 가장 자주 작동)
        - "영등포구 당산동3가385"     (동·번지 붙이기)
        - "영등포구 당산동 3가 385"   (가 분리)
        - "영등포구 당산동3가 385번지"
        - "당산동3가 385"              (앞부분 제거)
    """
    import re
    s = keyword.strip()
    variants: list[str] = []

    # 0. ⭐ trailing space — Kakao 의 알려진 quirk. 지번주소에서 가장 자주 통함
    variants.append(s + " ")

    # 1. 공백 정규화 (다중 공백 → 단일)
    normalized = re.sub(r"\s+", " ", s)
    if normalized != s:
        variants.append(normalized)
        variants.append(normalized + " ")  # 정규화 + trailing space

    # 2. 동명 뒤 번지 사이 공백 제거: "당산동3가 385" → "당산동3가385"
    no_space_lot = re.sub(r"([가-힣]+(?:동|가)\d*)\s+(\d)", r"\1\2", normalized)
    if no_space_lot != normalized:
        variants.append(no_space_lot)

    # 3. 동·가 분리: "당산동3가" → "당산동 3가"
    split_ga = re.sub(r"([가-힣]+동)(\d+가)", r"\1 \2", normalized)
    if split_ga != normalized:
        variants.append(split_ga)
        variants.append(split_ga + " ")

    # 4. "번지" 접미사 추가
    if re.search(r"\d+(-\d+)?\s*$", normalized):
        variants.append(normalized + "번지")

    # 5. 시·도 prefix 제거 시도 (시/구 단위만 유지)
    parts = normalized.split()
    if len(parts) > 2:
        variants.append(" ".join(parts[1:]))   # 첫 토큰 빼기 (시도 제거)
        variants.append(" ".join(parts[1:]) + " ")
        if len(parts) > 3:
            variants.append(" ".join(parts[2:]))  # 시군구만 유지

    return variants


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
