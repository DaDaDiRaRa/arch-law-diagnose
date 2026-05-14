"""국토교통부 토지이용규제정보서비스 (LURIS) API 클라이언트.

공공데이터포털 API ID: 1613000/arLandUseInfoService
- /DTarLandUseInfo: 시군구 + 지역지구 + 행위명 → 행위 가능여부 + 세부 토지이용정보 + 참조법령
- /DTsearchLunCd: 행위명 → 행위코드 검색

응답 인코딩: EUC-KR (디코딩 처리 필요)
명세서: info_arLandUseInfoService (토지이음 표준연계모듈 연계 가이드, 2024.02)
"""
from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

import httpx
from dotenv import load_dotenv

if TYPE_CHECKING:
    from services.cache_manager import CacheManager

load_dotenv()
logger = logging.getLogger(__name__)

LURIS_BASE = "https://apis.data.go.kr/1613000/arLandUseInfoService"


class LurisClient:
    """LURIS 행위제한정보 클라이언트 (Async)."""

    def __init__(self, cache: "CacheManager | None" = None) -> None:
        # LURIS_API_KEY 우선, 없으면 DATA_GO_KR_API_KEY 재사용 (공공데이터포털은 사용자당 키 1개)
        self._key = os.getenv("LURIS_API_KEY") or os.getenv("DATA_GO_KR_API_KEY", "")
        if not self._key:
            logger.warning("LURIS_API_KEY/DATA_GO_KR_API_KEY 미설정 — 행위제한 조회 불가")
        self._http = httpx.AsyncClient(timeout=15)
        self._cache = cache
        # 통계 — /api/luris_stats 등에서 확인용
        self.cache_hits = 0
        self.cache_misses = 0

    async def close(self) -> None:
        await self._http.aclose()

    # ─── /DTsearchLunCd — 행위명 → 코드 ──────────────────────────────────

    async def search_action(
        self, name: str, page: int = 1, rows: int = 10
    ) -> list[dict]:
        """토지이용행위명으로 코드 검색.

        예: '공장' → [{'name': '공장', 'code': '03666'}, {'name': '금은세공업 공장', 'code': '02079'}, ...]
        """
        if not self._key:
            return []
        params = {
            "serviceKey": self._key,
            "pageNum": page,
            "numOfRows": rows,
            "landUseNm": name,
        }
        try:
            r = await self._http.get(f"{LURIS_BASE}/DTsearchLunCd", params=params)
            r.raise_for_status()
            text = r.content.decode("euc-kr", errors="replace")
        except Exception as e:
            logger.error("LURIS search_action 오류: %s", e)
            return []
        return self._parse_action_list(text)

    # ─── /DTarLandUseInfo — 행위제한 본 조회 ─────────────────────────────

    async def get_act_info(
        self,
        area_cd: str,
        ucode: str,
        land_use_nm: str,
    ) -> dict | None:
        """시군구 + 지역지구 + 행위명 → 행위제한 정보.

        Args:
          area_cd: 시군구코드 5자리 (예: '11110' = 서울 종로구)
          ucode: 지역지구코드 (예: 'UQA430' = 자연녹지지역)
          land_use_nm: 행위명 (예: '주택', '업무시설', '근린생활시설')

        Returns:
          {
            zone_name: 지역지구명,
            zone_code: 지역지구코드,
            law_code: 지역지구 법령코드,
            acts: [
              {
                name: 행위(예: '건축'),
                allowed: '가능' | '불가능' | '조건부' 등,
                items: [
                  {name, law_ref, definition}, ...   # 세부 토지이용
                ],
              }, ...
            ],
            summary: {
              has_buildable: bool,   # 어떤 행위든 '가능' 있으면 True
              buildable_count: int,
              total_items: int,
            },
          } | None
        """
        if not self._key or not area_cd or not ucode or not land_use_nm:
            return None

        # 1) 캐시 우선
        if self._cache is not None:
            hit, cached = await self._cache.get_luris_act_info(area_cd, ucode, land_use_nm)
            if hit:
                self.cache_hits += 1
                logger.debug("LURIS 캐시 적중: %s/%s/%s", area_cd, ucode, land_use_nm)
                return cached
            self.cache_misses += 1

        # 2) API 호출
        params = {
            "serviceKey": self._key,
            "areaCd": area_cd,
            "ucodeList": ucode,
            "landUseNm": land_use_nm,
        }
        try:
            r = await self._http.get(f"{LURIS_BASE}/DTarLandUseInfo", params=params)
            r.raise_for_status()
            text = r.content.decode("euc-kr", errors="replace")
        except Exception as e:
            # 네트워크/HTTP 에러는 캐싱하지 않음 — 다음 호출 시 재시도
            logger.error("LURIS get_act_info 오류: %s", e)
            return None

        info = self._parse_act_info(text)

        # 3) 결과 캐싱 (None도 저장 — 한도 절약)
        if self._cache is not None:
            try:
                await self._cache.set_luris_act_info(area_cd, ucode, land_use_nm, info)
            except Exception as e:
                logger.warning("LURIS 캐시 저장 실패: %s", e)

        return info

    # ─── 내부 파서 ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_action_list(xml_text: str) -> list[dict]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.error("LURIS XML parse 오류: %s", e)
            return []
        # 에러 응답
        if root.find("ERROR_CODE") is not None:
            msg = root.findtext("ERROR_MSG", "")
            logger.warning("LURIS 에러 응답: %s", msg)
            return []
        results = []
        for item in root.findall(".//item"):
            nm = (item.findtext("LUN_NM") or "").strip()
            cd = (item.findtext("LUN_CD") or "").strip()
            if nm and cd:
                results.append({"name": nm, "code": cd})
        return results

    @staticmethod
    def _parse_act_info(xml_text: str) -> dict | None:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.error("LURIS XML parse 오류: %s", e)
            return None
        if root.find("ERROR_CODE") is not None:
            logger.warning("LURIS 에러: %s", root.findtext("ERROR_MSG", ""))
            return None
        item = root.find(".//item")
        if item is None:
            return None

        acts: list[dict] = []
        allowed_count = 0
        forbidden_count = 0
        total_items = 0
        has_real_data = False
        for act in item.findall("actRegList"):
            allowed = (act.findtext("REG_NM") or "").strip()
            items: list[dict] = []
            for lu in act.findall("luInfoList"):
                node_name = (lu.findtext("NODE_DESC") or "").strip()
                # "관련내용 없음" 플레이스홀더는 데이터 부족 신호
                if node_name == "관련내용 없음":
                    continue
                has_real_data = True
                items.append({
                    "name": node_name,
                    "law_ref": (lu.findtext("LU_REF_LAW_NM1") or "").strip(),
                    "law_ref2": (lu.findtext("LU_REF_LAW_NM2") or "").strip(),
                    "law_ref3": (lu.findtext("LU_REF_LAW_NM3") or "").strip(),
                    "definition": (lu.findtext("DEF_REF") or "").strip(),
                })
            if not items and not allowed:
                continue  # 빈 actRegList 스킵
            total_items += len(items)
            if "가능" in allowed:
                allowed_count += len(items) or 1
            elif "금지" in allowed or "불가" in allowed:
                forbidden_count += len(items) or 1
            acts.append({
                "name": (act.findtext("ACT_NM") or "").strip(),
                "allowed": allowed,
                "items": items,
            })

        # 종합 판정: data 부족 / 허용 / 금지 / 혼재
        if not has_real_data:
            verdict = "DATA_INSUFFICIENT"  # 회색
        elif forbidden_count > 0 and allowed_count == 0:
            verdict = "FORBIDDEN"          # 빨강
        elif allowed_count > 0 and forbidden_count == 0:
            verdict = "ALLOWED"            # 녹색
        else:
            verdict = "MIXED"              # 노랑 — 일부 가능 일부 금지

        return {
            "zone_name": (item.findtext("UNAME") or "").strip(),
            "zone_code": (item.findtext("UCODE") or "").strip(),
            "law_code": (item.findtext("UCODE_REF_LAW_CD") or "").strip(),
            "acts": acts,
            "summary": {
                "verdict": verdict,
                "allowed_count": allowed_count,
                "forbidden_count": forbidden_count,
                "total_items": total_items,
                "has_real_data": has_real_data,
            },
        }
