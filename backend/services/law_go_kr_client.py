"""법제처 국가법령정보 공동활용(DRF) API 클라이언트.

API 문서: https://open.law.go.kr/LSO/openApi/openApiInfo.do
환경변수: LAW_API_KEY  (사이트 표기: OC 인증키)

엔드포인트:
  - 법령/조례 목록: GET /DRF/lawSearch.do
  - 법령/조례 본문: GET /DRF/lawService.do
"""
from __future__ import annotations

import logging
import os
import re
import xml.etree.ElementTree as ET

import httpx
from dotenv import load_dotenv

from services.http_retry import request_with_retry

load_dotenv()
logger = logging.getLogger(__name__)

BASE = "https://www.law.go.kr/DRF"


class LawGoKrClient:
    def __init__(self) -> None:
        self._key = os.getenv("LAW_API_KEY", "")
        if not self._key:
            logger.warning("LAW_API_KEY 미설정 — 법제처 API 조회 불가")
        self._http = httpx.AsyncClient(timeout=20)

    async def close(self) -> None:
        await self._http.aclose()

    # ─── 법령 검색 ────────────────────────────────────────────────────────

    async def search_law(self, keyword: str, law_type: str = "LAW") -> list[dict]:
        """법령 키워드 검색.

        law_type: 'LAW' (법률) | 'CST' (자치법규/조례)
        Returns: [{law_id, law_nm, ef_yd, law_type}, ...]
        """
        if not self._key:
            return []

        target = "ordin" if law_type == "CST" else "law"
        params = {
            "OC": self._key,
            "target": target,
            "type": "JSON",
            "query": keyword,
            "display": 10,
            "page": 1,
        }

        try:
            r = await request_with_retry(self._http, "GET",f"{BASE}/lawSearch.do", params=params)
            r.raise_for_status()
            body = r.json()
        except Exception as e:
            logger.error("법령 검색 오류 (%s): %s", keyword, e)
            return []

        if law_type == "CST":
            items = body.get("OrdinSearch", {}).get("law", []) or []
        else:
            items = body.get("LawSearch", {}).get("law", []) or []

        if isinstance(items, dict):
            items = [items]

        result = []
        for item in items:
            if law_type == "CST":
                law_id = item.get("자치법규일련번호", "")
                law_nm = item.get("자치법규명", "")
                # 상세링크에서 MST 번호 추출 (백업)
                if not law_id:
                    link = item.get("자치법규상세링크", "")
                    m = re.search(r"MST=(\d+)", link)
                    law_id = m.group(1) if m else ""
            else:
                # 법령ID(통합 ID)가 아니라 법령일련번호(MST)를 사용해야 lawService.do 가 동작.
                # 상세링크 fallback 으로 MST 추출하기도 함.
                law_id = item.get("법령일련번호", "")
                if not law_id:
                    link = item.get("법령상세링크", "")
                    m = re.search(r"MST=(\d+)", link)
                    law_id = m.group(1) if m else ""
                law_nm = item.get("법령명한글", "")

            if law_id and law_nm:
                result.append({
                    "law_id": law_id,
                    "law_nm": law_nm,
                    "ef_yd": item.get("시행일자", ""),
                    "law_type": law_type,
                    "org": item.get("지자체기관명", ""),
                })

        return result

    # ─── 법령 본문 조회 ───────────────────────────────────────────────────

    async def get_law_articles(self, law_id: str, law_type: str = "LAW") -> list[dict]:
        """법령 ID(MST)로 전체 조문 목록 반환.

        Returns: [{article_no, title, content}, ...]
        """
        if not self._key or not law_id:
            return []

        target = "ordin" if law_type == "CST" else "law"
        params = {"OC": self._key, "target": target, "MST": law_id, "type": "XML"}
        try:
            r = await request_with_retry(self._http, "GET",f"{BASE}/lawService.do", params=params)
            r.raise_for_status()
            xml_text = r.text
        except Exception as e:
            logger.error("법령 본문 조회 오류 (MST=%s): %s", law_id, e)
            return []

        return _parse_law_xml(xml_text)

    # ─── org 필터 검색 (시도 직제 조례 우선) ────────────────────────────

    async def _search_with_org_filter(
        self, keyword: str, org_name: str, law_type: str = "CST",
        law_nm_keyword: str = "",
    ) -> list[dict]:
        """최대 3페이지 검색해 org_name + 조례명 키워드가 일치하는 조례를 반환.

        law_nm_keyword: 조례명에 반드시 포함되어야 할 핵심어 (예: '도시계획')
        정확 일치가 없으면 page 1의 첫 번째 결과를 반환.
        """
        fallback: list[dict] = []
        target = "ordin" if law_type == "CST" else "law"
        # 조례명 필터: 공백 제거 버전으로 비교 (예: '도시계획 조례' → '도시계획')
        nm_filter = law_nm_keyword.replace(" ", "") if law_nm_keyword else ""

        for page in range(1, 4):
            params = {
                "OC": self._key,
                "target": target,
                "type": "JSON",
                "query": keyword,
                "display": 10,
                "page": page,
            }
            try:
                r = await request_with_retry(self._http, "GET",f"{BASE}/lawSearch.do", params=params)
                r.raise_for_status()
                body = r.json()
            except Exception as e:
                logger.error("법령 검색(page=%s) 오류: %s", page, e)
                break

            raw = body.get("OrdinSearch", {}).get("law", []) or []
            if isinstance(raw, dict):
                raw = [raw]
            if not raw:
                break

            for item in raw:
                law_id = item.get("자치법규일련번호", "")
                law_nm = item.get("자치법규명", "")
                if not law_id:
                    m = re.search(r"MST=(\d+)", item.get("자치법규상세링크", ""))
                    law_id = m.group(1) if m else ""
                org = item.get("지자체기관명", "")
                entry = {
                    "law_id": law_id,
                    "law_nm": law_nm,
                    "ef_yd": item.get("시행일자", ""),
                    "law_type": law_type,
                    "org": org,
                }
                nm_match = (nm_filter in law_nm.replace(" ", "")) if nm_filter else True
                if law_id and law_nm and org == org_name and nm_match:
                    logger.debug("org+조례명 정확 매칭: %s (%s)", law_nm, org)
                    return [entry]
                if page == 1 and law_id and law_nm and not fallback:
                    fallback = [entry]

        return fallback

    # ─── 조례 빠른 조회 (지역명 + 법령유형) ─────────────────────────────

    async def fetch_ordinance(
        self, region_name: str, law_keyword: str
    ) -> list[dict]:
        """예: region_name='서울특별시', law_keyword='도시계획 조례' → 조문 목록.

        지자체기관명이 region_name과 정확히 일치하는 조례를 우선 선택.
        page 1~3까지 검색해 정확 일치를 찾은 뒤 없으면 첫 번째 결과 사용.
        """
        query = f"{region_name} {law_keyword}"
        # 공백 제거한 전체 키워드를 조례명 필터로 사용 (예: '도시계획 조례' → '도시계획조례')
        nm_key = law_keyword.replace(" ", "") if law_keyword else ""
        laws = await self._search_with_org_filter(
            query, region_name, law_type="CST", law_nm_keyword=nm_key
        )
        if not laws:
            laws = await self.search_law(law_keyword, law_type="LAW")
        if not laws:
            logger.warning("법령 검색 결과 없음: %s", query)
            return []

        law = laws[0]
        articles = await self.get_law_articles(law["law_id"], law["law_type"])
        for art in articles:
            art["law_nm"] = law["law_nm"]
            art["law_id"] = law["law_id"]
            art["source_url"] = f"https://www.law.go.kr/법령/{law['law_nm']}"
        return articles


# ─── XML 파싱 ─────────────────────────────────────────────────────────────


def _parse_law_xml(xml_text: str) -> list[dict]:
    """DRF 자치법규 XML 조문 파싱.

    실제 응답 스키마 (확인됨 2026-05-15, target=ordin):
      <LawService>
        <조문>
          <조 조문번호="000100">
            <조문번호>000100</조문번호>
            <조문여부>Y</조문여부>          # Y=조문, N=장/절 구분자
            <조제목><![CDATA[목적]]></조제목>
            <조내용><![CDATA[제1조(목적) ...
              ① ...
              1. ...]]></조내용>           # 항·호는 본문에 인라인
          </조>
          ...
        </조문>
        <별표> ... </별표>                  # 첨부파일(hwp) 참조라 텍스트 없음 — 파싱 안 함
      </LawService>
    """
    articles: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.error("법령 XML 파싱 오류: %s", e)
        return []

    for jo in root.iter("조"):
        if (jo.findtext("조문여부") or "").strip() != "Y":
            continue

        no_text = (jo.findtext("조문번호") or "").strip()
        title_text = (jo.findtext("조제목") or "").strip()
        content_text = (jo.findtext("조내용") or "").strip()

        if content_text:
            articles.append({
                "article_no": no_text,
                "title": title_text,
                "content": content_text,
            })

    # 별표 — 본문은 hwp 첨부라 비어있지만 제목·URL 은 article 로 보존
    # (진단 시 "별표 N 참조 필요" 신호로 사용)
    for byp in root.iter("별표단위"):
        bp_title = (byp.findtext("별표제목") or "").strip()
        if not bp_title:
            continue
        bp_no = (byp.findtext("별표번호") or "").strip()
        bp_url = (byp.findtext("별표첨부파일명") or "").strip()
        content = "본문은 별도 첨부파일(hwp) 참조 — 자동 추출 불가."
        if bp_url:
            content += f"\n첨부: {bp_url}"
        articles.append({
            "article_no": f"별표{bp_no}".strip(),
            "title": bp_title,
            "content": content,
        })

    # 폴백 — 파싱 0건일 때 전체 XML 통째 (예전 스키마 또는 응답 이상 대응)
    if not articles and xml_text.strip():
        try:
            articles = [{
                "article_no": "",
                "title": "전문",
                "content": ET.tostring(root, encoding="unicode"),
            }]
        except Exception:
            pass

    return articles
