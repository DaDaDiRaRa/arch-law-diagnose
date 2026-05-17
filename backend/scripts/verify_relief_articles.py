"""제가 인용한 완화 관련 조문들을 법제처 API 로 실제 가져와 검증.

법령(LAW) XML 스키마는 <조문단위> 라 기존 law_go_kr_client._parse_law_xml(<조>) 와 다름.
이 스크립트는 검증용으로 별도 파서 사용.

실행: python -m scripts.verify_relief_articles
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from dotenv import load_dotenv

load_dotenv()
OC = os.getenv("LAW_API_KEY", "")
BASE = "https://www.law.go.kr/DRF"


# (법령명, [확인할 조문번호 또는 '조-항-호'])
TARGETS: list[tuple[str, list[str]]] = [
    ("건축법", [
        "5",        # 적용 제외 등 (리모델링 관련?)
        "57의2",    # 대지의 분할 제한 관련
        "60",       # 가로구역별 최고높이
        "61",       # 일조 등 확보
        "72",       # 특별건축구역 지정
        "73",       # 특별건축구역 특례
        "75의2",    # 특별가로구역
        "77의4",    # 건축협정 (?)
        "77의11",   # 건축협정 통합 적용
        "77의13",   # 건축협정에 따른 특례
        "77의15",   # 결합건축
    ]),
    ("건축법 시행령", [
        "3의3",     # 대지의 범위
        "27",       # 대지 안의 조경 (옥상조경?)
        "27의2",    # 공개 공지등의 확보
        "61의2",    # 친환경 등 용적률 완화
        "84의2",    # 방재지구 건폐율
        "86",       # 일조권
        "119",      # 면적 등의 산정방법
    ]),
    ("도시재정비 촉진을 위한 특별법", ["21"]),  # 재정비촉진지구 용적률 완화
    ("도시재생 활성화 및 지원에 관한 특별법", ["32"]),  # 도시재생활성화지역 특례
    ("민간임대주택에 관한 특별법", ["21"]),  # 임대주택 용적률 인센티브
]


def _short(text: str, n: int = 400) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= n else t[:n] + " …"


def _normalize_article_no(raw: str) -> str:
    """'1', '57', '57의2' 등을 정규화 — 공백·하이픈 제거."""
    return raw.replace(" ", "").replace("-", "")


async def search_law(client: httpx.AsyncClient, keyword: str) -> dict | None:
    """법령명 정확 일치 검색."""
    r = await client.get(f"{BASE}/lawSearch.do", params={
        "OC": OC, "target": "law", "type": "JSON",
        "query": keyword, "display": 10, "page": 1,
    })
    r.raise_for_status()
    body = r.json()
    items = body.get("LawSearch", {}).get("law", []) or []
    if isinstance(items, dict):
        items = [items]
    target_norm = keyword.replace(" ", "")
    for it in items:
        nm = (it.get("법령명한글") or "").replace(" ", "")
        if nm == target_norm:
            return {
                "law_nm": it.get("법령명한글"),
                "mst": it.get("법령일련번호") or "",
                "ef_yd": it.get("시행일자"),
            }
    if items:
        return {
            "law_nm": items[0].get("법령명한글"),
            "mst": items[0].get("법령일련번호") or "",
            "ef_yd": items[0].get("시행일자"),
        }
    return None


async def get_law_articles(client: httpx.AsyncClient, mst: str) -> list[dict]:
    """법령 본문 — <조문단위> 스키마 파싱."""
    r = await client.get(f"{BASE}/lawService.do", params={
        "OC": OC, "target": "law", "MST": mst, "type": "XML",
    })
    r.raise_for_status()
    try:
        root = ET.fromstring(r.text)
    except ET.ParseError as e:
        print(f"  XML 파싱 오류: {e}")
        return []

    articles: list[dict] = []
    for unit in root.iter("조문단위"):
        yn = (unit.findtext("조문여부") or "").strip()
        if yn != "조문":  # '전문' 은 장/절 표제, '조문' 만 추림
            continue
        no = (unit.findtext("조문번호") or "").strip()
        gaj = (unit.findtext("조문가지번호") or "").strip()  # '의X' 의 X
        if gaj and gaj != "0":
            no = f"{no}의{gaj}"
        title = (unit.findtext("조문제목") or "").strip()
        content = (unit.findtext("조문내용") or "").strip()

        # 항·호 본문도 합쳐서 보여주기
        for hang in unit.iter("항"):
            hno = (hang.findtext("항번호") or "").strip()
            hcontent = (hang.findtext("항내용") or "").strip()
            if hcontent:
                content += f"\n  {hcontent}"
            for ho in hang.iter("호"):
                hono = (ho.findtext("호번호") or "").strip()
                hocontent = (ho.findtext("호내용") or "").strip()
                if hocontent:
                    content += f"\n    {hocontent}"

        articles.append({
            "no": _normalize_article_no(no),
            "title": title,
            "content": content,
            "ef_yd": (unit.findtext("조문시행일자") or "").strip(),
        })
    return articles


async def main() -> None:
    if not OC:
        print("LAW_API_KEY 미설정")
        return

    async with httpx.AsyncClient(timeout=30) as h:
        for law_name, wanted in TARGETS:
            print("\n" + "=" * 90)
            print(f"[LAW] {law_name}")
            print("=" * 90)

            try:
                law = await search_law(h, law_name)
            except Exception as e:
                print(f"  [X] 검색 오류: {type(e).__name__}: {e}")
                continue
            if not law or not law["mst"]:
                print("  [X] 검색 결과 없음")
                continue

            print(f"  -> 매칭: {law['law_nm']} (MST={law['mst']}, 시행 {law['ef_yd']})")

            try:
                articles = await get_law_articles(h, law["mst"])
            except Exception as e:
                print(f"  [X] 본문 조회 오류: {e}")
                continue
            print(f"  -> 조문 {len(articles)}건 파싱")

            by_no = {a["no"]: a for a in articles}
            for w in wanted:
                key = _normalize_article_no(w)
                hit = by_no.get(key)
                if hit:
                    print(f"\n  [O] 제{w}조  {hit['title']}  (시행 {hit['ef_yd']})")
                    print(f"      {_short(hit['content'], 500)}")
                else:
                    print(f"\n  [X] 제{w}조  — 본문에 없음")
                    # 비슷한 번호 추천
                    similar = [a["no"] for a in articles if a["no"].startswith(key[:2])][:5]
                    if similar:
                        print(f"      (비슷한 번호: {similar})")


if __name__ == "__main__":
    asyncio.run(main())
