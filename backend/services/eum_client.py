"""토지이음(eum.go.kr) 표준연계모듈 클라이언트.

토지이음 API 7개 메서드 (5개 메인 + 2개 공통 헬퍼).
- 인증: id + key URL 파라미터
- 응답: XML (3.8 개발 인허가만 JSON)
- 환경변수: EUM_ID, EUM_KEY

명세: eum_api_manual_v1.1 (2025.01)
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

EUM_BASE = "https://api.eum.go.kr/web/Rest"


class EumClient:
    """토지이음 표준연계 API 클라이언트 (Async).

    id/key 미설정 시 available=False — 모든 메서드가 빈 결과 반환 (graceful degrade).
    """

    def __init__(self, cache: "CacheManager | None" = None) -> None:
        self._id = os.getenv("EUM_ID", "")
        self._key = os.getenv("EUM_KEY", "")
        if not self._id or not self._key:
            logger.warning("EUM_ID / EUM_KEY 미설정 — 토지이음 API 비활성")
        self._http = httpx.AsyncClient(timeout=15)
        # zone_code 메모리 캐시: (area_cd, uname) → [matched_ucodes]
        self._zone_code_cache: dict[tuple[str, str], list[dict]] = {}
        self._cache = cache
        # 행위제한 캐시 통계
        self.act_cache_hits = 0
        self.act_cache_misses = 0

    @property
    def available(self) -> bool:
        return bool(self._id and self._key)

    async def close(self) -> None:
        await self._http.aclose()

    # ─── 내부 공통 ─────────────────────────────────────────────────────────

    async def _get_xml(self, path: str, params: dict) -> ET.Element | None:
        """XML 응답 파싱 + 오류코드 검출. 실패 시 None."""
        if not self.available:
            return None
        full_params = {"id": self._id, "key": self._key, **params}
        try:
            r = await self._http.get(f"{EUM_BASE}/{path}", params=full_params)
            r.raise_for_status()
        except Exception as e:
            logger.error("토지이음 API 오류 (%s): %s", path, e)
            return None
        try:
            root = ET.fromstring(r.text)
        except ET.ParseError as e:
            logger.warning(
                "토지이음 XML 파싱 실패 (%s): %s — 응답 앞 200자: %s",
                path, e, r.text[:200],
            )
            return None
        # 오류 코드 체크 (ERR-001 필수정보 누락, ERR-002 권한, ERR-003 호출횟수, ERR-004, ERR-005)
        err_code = root.findtext("ERROR_CODE")
        if err_code:
            err_msg = root.findtext("ERROR_MSG", "") or ""
            logger.warning(
                "토지이음 API 오류 응답 (%s): [%s] %s", path, err_code, err_msg.strip(),
            )
            return None
        return root

    async def _get_json(self, path: str, params: dict) -> dict | None:
        """JSON 응답 파싱 (3.8 개발인허가 전용)."""
        if not self.available:
            return None
        full_params = {"id": self._id, "key": self._key, **params}
        try:
            r = await self._http.get(f"{EUM_BASE}/{path}", params=full_params)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error("토지이음 API 오류 (%s): %s", path, e)
            return None

    # ─── 3.1 시군구 코드 조회 ─────────────────────────────────────────────

    async def search_area_codes(self) -> list[dict]:
        """모든 시군구 코드/명 반환. 캐시해두고 사용 권장."""
        root = await self._get_xml("OP/searchArea", {})
        if root is None:
            return []
        return [
            {
                "area_cd": (a.findtext("AREA_CD", "") or "").strip(),
                "area_nm": (a.findtext("AREA_NM", "") or "").strip(),
            }
            for a in root.findall("AreaCd")
        ]

    # ─── 헬퍼 — zone_use 한글명 → UCODE 변환 ─────────────────────────────

    async def resolve_zone_ucodes(
        self, area_cd: str, names: list[str]
    ) -> list[dict]:
        """지역지구 한글명 목록 → UCODE 매핑 (메모리 캐시 사용).

        같은 (area_cd, name) 쿼리는 첫 호출 결과를 재사용. 정확 매칭(uname == name)
        결과를 우선 반환, 없으면 부분 매칭 결과 그대로.

        Args:
            area_cd: 시군구코드 (5자리)
            names: 한글명 리스트 (예: ["제2종일반주거지역", "지구단위계획구역"])

        Returns:
            [{ucode, uname, law_cd, law_nm}] — 중복 ucode 제거됨
        """
        seen_ucodes: set[str] = set()
        results: list[dict] = []
        for raw_name in names:
            name = (raw_name or "").strip()
            if not name:
                continue
            cache_key = (area_cd, name)
            if cache_key in self._zone_code_cache:
                matched = self._zone_code_cache[cache_key]
            else:
                zones = await self.search_zone_codes(area_cd, uname=name)
                exact = [z for z in zones if z["uname"] == name]
                matched = exact if exact else zones
                self._zone_code_cache[cache_key] = matched
            for z in matched:
                if z["ucode"] and z["ucode"] not in seen_ucodes:
                    seen_ucodes.add(z["ucode"])
                    results.append(z)
        return results

    # ─── 3.2 지역·지구 코드 조회 ──────────────────────────────────────────

    async def search_zone_codes(
        self, area_cd: str, type_: str = "S", uname: str | None = None
    ) -> list[dict]:
        """시군구의 지역지구 UCODE 목록.

        Args:
            area_cd: 시군구코드 (5자리)
            type_: 검색타입 ('S' 고정)
            uname: 지역지구명 (선택, 부분 매칭). 예: "주거지역"

        Returns:
            [{ucode, uname, law_cd, law_nm}]
        """
        params: dict = {"areaCd": area_cd, "type": type_}
        if uname:
            params["uname"] = uname
        root = await self._get_xml("OP/searchZone", params)
        if root is None:
            return []
        return [
            {
                "ucode": (z.findtext("UCODE", "") or "").strip(),
                "uname": (z.findtext("UNAME", "") or "").strip(),
                "law_cd": (z.findtext("LAW_CD", "") or "").strip(),
                "law_nm": (z.findtext("LAW_NM", "") or "").strip(),
            }
            for z in root.findall("ZoneCd")
        ]

    # ─── 3.3 토지이용규제 법령정보 ────────────────────────────────────────

    async def get_law_info(self, area_cd: str, ucode_list: list[str]) -> list[dict]:
        """지역지구별 법령 본문 조회.

        Args:
            area_cd: 시군구코드
            ucode_list: 지역지구코드 목록

        Returns:
            [{ucode, uname, law_contents, law_level (0=조, 1=항, 2=호, 3=목), law_full_cd}]
        """
        if not ucode_list:
            return []
        params = {"areaCd": area_cd, "ucodeList": ",".join(ucode_list)}
        root = await self._get_xml("OP/iuLawInfo", params)
        if root is None:
            return []
        results = []
        for law in root.findall("EumLaw"):
            results.append({
                "ucode": (law.findtext("UCODE", "") or "").strip(),
                "uname": (law.findtext("UNAME", "") or "").strip(),
                "law_contents": (law.findtext("LAW_CONTENTS", "") or "").strip(),
                "law_level": _to_int(law.findtext("LAW_LEVEL", "0")),
                "law_full_cd": (law.findtext("LAW_FULL_CD", "") or "").strip(),
            })
        return results

    # ─── 3.4 토지이용행위명 ───────────────────────────────────────────────

    async def search_lun_codes(self, land_use_nm: str, page_no: int = 1) -> dict:
        """토지이용행위명 검색 (페이지당 10건).

        Returns:
            {total_size, total_page, list_size, page_no, items: [{lun_nm, lun_cd, rnum}]}
        """
        params = {"landUseNm": land_use_nm, "pageNo": page_no}
        root = await self._get_xml("OP/searchLunCd", params)
        if root is None:
            return _empty_paged(page_no)
        items = [
            {
                "lun_nm": (l.findtext("LUN_NM", "") or "").strip(),
                "lun_cd": (l.findtext("LUN_CD", "") or "").strip(),
                "rnum": _to_int(l.findtext("RNUM", "0")),
            }
            for l in root.findall("LunCd")
        ]
        return _paged(root, page_no, items)

    # ─── 3.5 토지이용규제 행위제한정보 ────────────────────────────────────

    async def get_act_restriction(
        self,
        area_cd: str,
        ucode_list: list[str],
        land_use_nm: str | None = None,
        lun_cds: list[str] | None = None,
    ) -> list[dict]:
        """지역지구·행위별 가능여부.

        Returns:
            [{ucode, uname, ucode_ref_law_cd, ucode_ref_law_nm,
              act_reg_list: [{act_nm, reg_nm, qnode_conds, lu_info_list}],
              qnode_conds: [{qnode_desc, rnum}]}]
        """
        if not ucode_list:
            return []
        params: dict = {"areaCd": area_cd, "ucodeList": ",".join(ucode_list)}
        if land_use_nm:
            params["landUseNm"] = land_use_nm
        if lun_cds:
            params["lunCds"] = ",".join(lun_cds)
        root = await self._get_xml("OP/arLandUseInfo", params)
        if root is None:
            return []
        results = []
        for act_reg in root.findall("ActReg"):
            act_reg_list = []
            for item in act_reg.findall("actRegList"):
                conds = [
                    (c.text or "").strip()
                    for c in item.findall("QNODE_CONDS/item")
                ]
                lu_info = [
                    {
                        "node_desc": (li.findtext("NODE_DESC", "") or "").strip(),
                        "lu_ref_law_nm1": (li.findtext("LU_REF_LAW_NM1", "") or "").strip(),
                        "lu_ref_law_nm2": (li.findtext("LU_REF_LAW_NM2", "") or "").strip(),
                        "lu_ref_law_nm3": (li.findtext("LU_REF_LAW_NM3", "") or "").strip(),
                        "def_ref": (li.findtext("DEF_REF", "") or "").strip(),
                    }
                    for li in item.findall("luInfoList")
                ]
                act_reg_list.append({
                    "act_nm": (item.findtext("ACT_NM", "") or "").strip(),
                    "reg_nm": (item.findtext("REG_NM", "") or "").strip(),
                    "qnode_conds": conds,
                    "lu_info_list": lu_info,
                })
            qnode_conds = [
                {
                    "qnode_desc": (qc.findtext("QNODE_DESC", "") or "").strip(),
                    "rnum": _to_int(qc.findtext("RNUM", "0")),
                }
                for qc in act_reg.findall("QnodeCond")
            ]
            results.append({
                "ucode": (act_reg.findtext("UCODE", "") or "").strip(),
                "uname": (act_reg.findtext("UNAME", "") or "").strip(),
                "ucode_ref_law_cd": (act_reg.findtext("UCODE_REF_LAW_CD", "") or "").strip(),
                "ucode_ref_law_nm": (act_reg.findtext("UCODE_REF_LAW_NM", "") or "").strip(),
                "act_reg_list": act_reg_list,
                "qnode_conds": qnode_conds,
            })
        return results

    # ─── 3.5-b 행위제한 캐시 wrapper (단일 ucode + landUseNm 조회) ─────

    async def get_act_restriction_cached(
        self,
        area_cd: str,
        ucode: str,
        land_use_nm: str,
    ) -> list[dict] | None:
        """LURIS와 동일한 시그니처로 단일 ucode 행위제한을 캐시 포함 조회.

        Returns:
          - list[dict]: act_reg 결과 (빈 list 가능)
          - None: API 미응답 (네트워크/한도 등) — 호출자가 결정
        """
        if not self.available or not area_cd or not ucode or not land_use_nm:
            return None

        if self._cache is not None:
            hit, cached = await self._cache.get_eum_act_restriction(area_cd, ucode, land_use_nm)
            if hit:
                self.act_cache_hits += 1
                logger.debug("EUM 행위제한 캐시 적중: %s/%s/%s", area_cd, ucode, land_use_nm)
                return cached if cached is not None else []
            self.act_cache_misses += 1

        try:
            data = await self.get_act_restriction(area_cd, [ucode], land_use_nm=land_use_nm)
        except Exception as e:
            logger.error("EUM 행위제한 조회 오류: %s", e)
            return None

        if self._cache is not None:
            try:
                await self._cache.set_eum_act_restriction(
                    area_cd, ucode, land_use_nm, data if data else None,
                )
            except Exception as e:
                logger.warning("EUM 행위제한 캐시 저장 실패: %s", e)
        return data

    # ─── 3.6 고시정보 ─────────────────────────────────────────────────────

    async def get_notices(
        self, area_cd: str, start_dt: str, end_dt: str, page_no: int = 1
    ) -> dict:
        """해당 시군구의 최근 고시 목록.

        Args:
            area_cd: 시군구코드
            start_dt: 조회 시작일 (YYYYMMDD)
            end_dt: 조회 종료일 (YYYYMMDD)

        Returns:
            {total_size, total_page, list_size, page_no, items: [{title, author, ntc_date, link, summary}]}
        """
        params = {
            "areaCd": area_cd,
            "startDt": start_dt,
            "endDt": end_dt,
            "PageNo": page_no,
        }
        root = await self._get_xml("OP/arMapList", params)
        if root is None:
            return _empty_paged(page_no)
        items = [
            {
                "title": (a.findtext("TITLE", "") or "").strip(),
                "author": (a.findtext("AUTHOR", "") or "").strip(),
                "ntc_date": (a.findtext("NTC_DATE", "") or "").strip(),
                "link": (a.findtext("LINK", "") or "").strip(),
                "summary": (a.findtext("SUMMARY", "") or "").strip(),
            }
            for a in root.findall("ArMap")
        ]
        return _paged(root, page_no, items)

    # ─── 3.7 쉬운규제안내서 ───────────────────────────────────────────────

    async def get_guide_book(self) -> list[dict]:
        """쉬운규제안내서 전체 목록.

        Returns:
            [{cate_cd, cate_nm, facil_cd, facil_nm, description, access_url}]
        """
        root = await self._get_xml("OP/ebGuideBookList", {})
        if root is None:
            return []
        return [
            {
                "cate_cd": (g.findtext("CATE_CD", "") or "").strip(),
                "cate_nm": (g.findtext("CATE_NM", "") or "").strip(),
                "facil_cd": (g.findtext("FACIL_CD", "") or "").strip(),
                "facil_nm": (g.findtext("FACIL_NM", "") or "").strip(),
                "description": (g.findtext("DESCRIPTION", "") or "").strip(),
                "access_url": (g.findtext("ACCESS_URL", "") or "").strip(),
            }
            for g in root.findall("GuideBook")
        ]

    # ─── 3.8 개발 인허가 목록 조회 (JSON) ─────────────────────────────────

    async def get_dev_permits(
        self, area_cd: str, prmisn_de: str, page_no: int = 1
    ) -> dict:
        """해당 시군구의 개발 인허가 목록.

        Args:
            area_cd: 시군구코드
            prmisn_de: 허가일자 (YYYYMMDD, 8자리)
            page_no: 페이지 (1페이지당 30건)

        Returns:
            {site_code, page_no, total_page, cnt, list: [...]}
        """
        params = {
            "areaCd": area_cd,
            "prmisnDe": prmisn_de,
            "PageNo": page_no,
        }
        body = await self._get_json("OP/sDevList", params)
        if body is None:
            return {"site_code": "", "page_no": page_no, "total_page": 0, "cnt": 0, "list": []}
        return {
            "site_code": body.get("siteCode", "") or "",
            "page_no": _to_int(str(body.get("pageNo", page_no))),
            "total_page": _to_int(str(body.get("totalPage", 0))),
            "cnt": _to_int(str(body.get("cnt", 0))),
            "list": body.get("list", []) or [],
        }


# ─── 모듈 헬퍼 ─────────────────────────────────────────────────────────────


def _to_int(s, default: int = 0) -> int:
    try:
        return int(str(s).strip())
    except (ValueError, TypeError):
        return default


def _empty_paged(page_no: int) -> dict:
    return {"total_size": 0, "total_page": 0, "list_size": 0, "page_no": page_no, "items": []}


def _paged(root: ET.Element, page_no: int, items: list[dict]) -> dict:
    return {
        "total_size": _to_int(root.findtext("totalSize", "0")),
        "total_page": _to_int(root.findtext("totalPage", "0")),
        "list_size": _to_int(root.findtext("listSize", "0")),
        "page_no": _to_int(root.findtext("pageNo", str(page_no))),
        "items": items,
    }
