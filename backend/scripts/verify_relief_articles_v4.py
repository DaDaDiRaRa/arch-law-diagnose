"""4차 검증 — 건축법 시행령 §82 (건축물의 높이 제한) 조문 원문 확인.

height.py 주석에 "도로 너비 × N배 같은 일반 규정 없음"이라고 적혀 있는데
실제 법령 본문과 일치하는지 검증.

실행: python -m scripts.verify_relief_articles_v4
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


def _short(text: str, n: int = 1200) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= n else t[:n] + " ..."


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
        nm = (it.get("lmnNm") or it.get("법령명한글") or "").replace(" ", "")
        if nm == target_norm:
            return {"law_nm": it.get("lmnNm") or it.get("법령명한글"),
                    "mst": it.get("lmnMst") or it.get("법령일련번호") or "",
                    "ef_yd": it.get("efYd") or it.get("시행일자")}
    # 완전일치 없으면 첫 번째
    for it in items:
        nm = (it.get("lmnNm") or it.get("법령명한글") or "").replace(" ", "")
        if "건축법시행령" in nm or "건축법 시행령" in nm.replace("", " "):
            return {"law_nm": it.get("lmnNm") or it.get("법령명한글"),
                    "mst": it.get("lmnMst") or it.get("법령일련번호") or "",
                    "ef_yd": it.get("efYd") or it.get("시행일자")}
    if items:
        return {"law_nm": items[0].get("lmnNm") or items[0].get("법령명한글"),
                "mst": items[0].get("lmnMst") or items[0].get("법령일련번호") or "",
                "ef_yd": items[0].get("efYd") or items[0].get("시행일자")}
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
        articles.append({"no": no, "title": title, "content": content,
                         "ef_yd": (unit.findtext("조문시행일자") or "").strip()})
    return articles


async def main() -> None:
    if not OC:
        print("LAW_API_KEY 미설정")
        return

    async with httpx.AsyncClient(timeout=30) as h:
        print("=" * 90)
        print("[T1-5] 건축법 시행령 제82조 원문 검증")
        print("height.py 주석: '도로 너비 × N배 같은 일반 규정 없음'이 맞는지 확인")
        print("=" * 90)

        law = await search_law(h, "건축법 시행령")
        if not law or not law["mst"]:
            print("  [X] 건축법 시행령 검색 실패")
            return

        print(f"  매칭: {law['law_nm']} (MST={law['mst']}, 시행 {law['ef_yd']})")
        arts = await get_law_articles(h, law["mst"])
        print(f"  (전체 조문 {len(arts)}건 파싱)\n")

        # §82 전문 출력
        for art in arts:
            if art["no"] == "82":
                print(f">> 제82조  {art['title']}  (시행 {art['ef_yd']})")
                print()
                print(art["content"])
                break
        else:
            print("  [X] 제82조 — 본문에 없음")
            nearby = [a["no"] for a in arts if a["no"].startswith("8")][:8]
            print(f"  80번대 조문: {nearby}")

        # 주변 조문도 확인 (81, 83)
        print("\n" + "-" * 60)
        print("참고: 제81조, 제83조 제목 확인")
        for art in arts:
            if art["no"] in ("81", "83"):
                print(f"  제{art['no']}조 {art['title']}")

        # 도로폭 관련 키워드가 §82 주변에 있는지
        print("\n" + "-" * 60)
        print("[추가] '도로폭' / '도로의너비' 키워드가 포함된 조문 검색")
        rx = re.compile(r"도로.{0,3}(폭|너비|width)")
        hits = []
        for art in arts:
            text = (art["title"] + " " + art["content"]).replace(" ", "")
            if rx.search(text):
                hits.append(art)
        print(f"  매칭: {len(hits)}건")
        for art in hits[:5]:
            print(f"\n  >> 제{art['no']}조  {art['title']}")
            print(f"     {_short(art['content'], 500)}")


if __name__ == "__main__":
    asyncio.run(main())
