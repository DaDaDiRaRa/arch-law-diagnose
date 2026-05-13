"""법제처 국가법령정보 공동활용 DRF API 클라이언트.

API 문서: https://open.law.go.kr/LSO/openApi/openApiInfo.do
환경변수: LAW_API_KEY

주요 엔드포인트:
  - 법령 목록 조회: /law/lawSearch.do
  - 법령 본문 조회: /law/law.do (법령 ID 기반)
  - 자치법규 조회:  /law/lawSearch.do?type=CST (조례)
"""
from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET

import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

BASE = "https://open.law.go.kr/LSO/openApi/rest"


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
        Returns: [{law_id, law_nm, efYd, ...}, ...]
        """
        if not self._key:
            return []
        params = {
            "OC": self._key,
            "target": "law",
            "type": "JSON",
            "query": keyword,
            "display": 10,
            "page": 1,
        }
        if law_type == "CST":
            params["target"] = "ordin"  # 자치법규

        url = f"{BASE}/{'ordin' if law_type == 'CST' else 'law'}/lawSearch.do"
        try:
            r = await self._http.get(url, params=params)
            r.raise_for_status()
            body = r.json()
        except Exception as e:
            logger.error("법령 검색 오류 (%s): %s", keyword, e)
            return []

        laws = body.get("LawSearch", {}).get("law", []) or []
        if isinstance(laws, dict):
            laws = [laws]
        return [
            {
                "law_id": l.get("법령ID") or l.get("자치법규ID", ""),
                "law_nm": l.get("법령명한글") or l.get("자치법규명", ""),
                "ef_yd": l.get("시행일자", ""),
                "law_type": law_type,
            }
            for l in laws
        ]

    # ─── 법령 본문 조회 ───────────────────────────────────────────────────

    async def get_law_articles(self, law_id: str, law_type: str = "LAW") -> list[dict]:
        """법령 ID로 전체 조문 목록 반환.

        Returns: [{article_no, title, content}, ...]
        """
        if not self._key or not law_id:
            return []

        target = "ordin" if law_type == "CST" else "law"
        url = f"{BASE}/{target}/law.do"
        params = {"OC": self._key, "target": target, "ID": law_id, "type": "XML"}
        try:
            r = await self._http.get(url, params=params)
            r.raise_for_status()
            xml_text = r.text
        except Exception as e:
            logger.error("법령 본문 조회 오류 (ID=%s): %s", law_id, e)
            return []

        return _parse_law_xml(xml_text)

    # ─── 조례 빠른 조회 (지역명 + 법령유형) ─────────────────────────────

    async def fetch_ordinance(
        self, region_name: str, law_keyword: str
    ) -> list[dict]:
        """예: region_name='서울특별시', law_keyword='도시계획조례' → 조문 목록."""
        query = f"{region_name} {law_keyword}"
        laws = await self.search_law(query, law_type="CST")
        if not laws:
            # 국가 법률로 fallback
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
    articles: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.error("법령 XML 파싱 오류: %s", e)
        return []

    # 조문 태그 탐색 (조문번호, 조문제목, 조문내용)
    for jo in root.iter("조문"):
        no_el = jo.find("조문번호")
        title_el = jo.find("조문제목")
        content_el = jo.find("조문내용")
        articles.append(
            {
                "article_no": no_el.text.strip() if no_el is not None and no_el.text else "",
                "title": title_el.text.strip() if title_el is not None and title_el.text else "",
                "content": content_el.text.strip() if content_el is not None and content_el.text else "",
            }
        )

    # XML 구조가 다를 경우 폴백: 전체 텍스트 하나의 아티클로
    if not articles and xml_text.strip():
        articles = [{"article_no": "", "title": "전문", "content": ET.tostring(root, encoding="unicode")}]

    return articles
