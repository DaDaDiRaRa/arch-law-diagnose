"""2차 검증 — 1차에서 틀린 조문 위치를 본문 키워드 검색으로 다시 찾는다.

실행: python -m scripts.verify_relief_articles_v2
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


def _short(text: str, n: int = 500) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= n else t[:n] + " …"


async def search_law(client: httpx.AsyncClient, keyword: str) -> dict | None:
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
            return {"law_nm": it.get("법령명한글"),
                    "mst": it.get("법령일련번호") or "",
                    "ef_yd": it.get("시행일자")}
    if items:
        return {"law_nm": items[0].get("법령명한글"),
                "mst": items[0].get("법령일련번호") or "",
                "ef_yd": items[0].get("시행일자")}
    return None


async def get_law_articles(client: httpx.AsyncClient, mst: str) -> list[dict]:
    r = await client.get(f"{BASE}/lawService.do", params={
        "OC": OC, "target": "law", "MST": mst, "type": "XML",
    })
    r.raise_for_status()
    try:
        root = ET.fromstring(r.text)
    except ET.ParseError:
        return []

    articles: list[dict] = []
    for unit in root.iter("조문단위"):
        yn = (unit.findtext("조문여부") or "").strip()
        if yn != "조문":
            continue
        no = (unit.findtext("조문번호") or "").strip()
        gaj = (unit.findtext("조문가지번호") or "").strip()
        if gaj and gaj != "0":
            no = f"{no}의{gaj}"
        title = (unit.findtext("조문제목") or "").strip()
        content = (unit.findtext("조문내용") or "").strip()
        for hang in unit.iter("항"):
            hcontent = (hang.findtext("항내용") or "").strip()
            if hcontent:
                content += "\n  " + hcontent
            for ho in hang.iter("호"):
                hocontent = (ho.findtext("호내용") or "").strip()
                if hocontent:
                    content += "\n    " + hocontent
        articles.append({
            "no": no, "title": title, "content": content,
            "ef_yd": (unit.findtext("조문시행일자") or "").strip(),
        })
    return articles


def grep_articles(articles: list[dict], *patterns: str, max_hits: int = 8) -> list[dict]:
    """본문에 패턴 중 하나라도 포함된 조문 추리기."""
    rx = [re.compile(p) for p in patterns]
    hits = []
    for art in articles:
        text = (art.get("title", "") + " " + art.get("content", "")).replace(" ", "")
        for r in rx:
            if r.search(text):
                hits.append(art)
                break
        if len(hits) >= max_hits:
            break
    return hits


async def main() -> None:
    if not OC:
        print("LAW_API_KEY 미설정")
        return

    async with httpx.AsyncClient(timeout=30) as h:
        # 1. 친환경/에너지/지능형/장수명 용적률 완화 — 시행령에서 키워드 검색
        print("=" * 90)
        print("[1] 건축법 시행령 — 친환경/에너지/지능형/장수명 용적률 완화 조문 위치")
        print("=" * 90)
        law = await search_law(h, "건축법 시행령")
        arts = await get_law_articles(h, law["mst"])
        print(f"  (전체 조문 {len(arts)}건)")
        hits = grep_articles(
            arts,
            r"녹색건축인증",
            r"에너지효율등급",
            r"지능형건축물",
            r"장수명주택",
            r"녹색건축물조성지원법",
            max_hits=15,
        )
        for art in hits:
            print(f"\n  >> 제{art['no']}조  {art['title']}")
            print(f"     {_short(art['content'], 600)}")

        # 2. 시행령 §27 옥상조경
        print("\n" + "=" * 90)
        print("[2] 건축법 시행령 §27 — 옥상조경 인정 항호")
        print("=" * 90)
        for art in arts:
            if art["no"] == "27":
                print(f"\n  >> 제27조  {art['title']}")
                # 전체 본문 출력 (옥상조경 인정 항호 확인)
                print("  " + art["content"].replace("\n", "\n  "))
                break

        # 3. 도시재정비촉진법 — 용적률/건폐율 완화 조문
        print("\n" + "=" * 90)
        print("[3] 도시재정비촉진법 — 용적률/건폐율 완화 조문")
        print("=" * 90)
        law3 = await search_law(h, "도시재정비 촉진을 위한 특별법")
        arts3 = await get_law_articles(h, law3["mst"])
        print(f"  (전체 조문 {len(arts3)}건)")
        hits3 = grep_articles(arts3, r"용적률", r"건폐율", max_hits=10)
        for art in hits3:
            print(f"\n  >> 제{art['no']}조  {art['title']}")
            print(f"     {_short(art['content'], 600)}")

        # 4. 리모델링 활성화구역 — 건축법 + 시행령에서 검색
        print("\n" + "=" * 90)
        print("[4] 리모델링 활성화구역 관련 조문 (건축법 + 시행령)")
        print("=" * 90)
        law_b = await search_law(h, "건축법")
        arts_b = await get_law_articles(h, law_b["mst"])
        hits_b = grep_articles(arts_b, r"리모델링활성화구역", max_hits=10)
        print(f"  - 건축법 본문 매칭: {len(hits_b)}건")
        for art in hits_b:
            print(f"\n  >> [법] 제{art['no']}조  {art['title']}")
            print(f"     {_short(art['content'], 500)}")

        hits_d = grep_articles(arts, r"리모델링활성화구역", max_hits=10)
        print(f"\n  - 시행령 본문 매칭: {len(hits_d)}건")
        for art in hits_d:
            print(f"\n  >> [령] 제{art['no']}조  {art['title']}")
            print(f"     {_short(art['content'], 600)}")

        # 5. 건축법 §57 실제 내용
        print("\n" + "=" * 90)
        print("[5] 건축법 §57 실제 내용")
        print("=" * 90)
        for art in arts_b:
            if art["no"] in ("57", "57의2"):
                print(f"\n  >> 제{art['no']}조  {art['title']}")
                print(f"     {_short(art['content'], 600)}")

        # 6. 방재지구 건폐율 완화 — 국토계획법 시행령에 있을 가능성 큼
        print("\n" + "=" * 90)
        print("[6] 방재지구 건폐율 완화 — 국토계획법 시행령 검색")
        print("=" * 90)
        law_g = await search_law(h, "국토의 계획 및 이용에 관한 법률 시행령")
        if not law_g:
            print("  법령 검색 실패")
        else:
            print(f"  매칭: {law_g['law_nm']} (MST={law_g['mst']}, 시행 {law_g['ef_yd']})")
            arts_g = await get_law_articles(h, law_g["mst"])
            print(f"  (전체 조문 {len(arts_g)}건)")
            hits_g = grep_articles(arts_g, r"방재지구", max_hits=6)
            for art in hits_g:
                print(f"\n  >> 제{art['no']}조  {art['title']}")
                print(f"     {_short(art['content'], 500)}")


if __name__ == "__main__":
    asyncio.run(main())
