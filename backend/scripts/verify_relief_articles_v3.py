"""3차 검증 — 친환경 인증 용적률 완화의 진짜 근거 + 리모델링 활성화구역.

실행: python -m scripts.verify_relief_articles_v3
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


def _short(text: str, n: int = 700) -> str:
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
        articles.append({"no": no, "title": title, "content": content,
                         "ef_yd": (unit.findtext("조문시행일자") or "").strip()})
    return articles


def grep_articles(articles: list[dict], *patterns: str, max_hits: int = 12) -> list[dict]:
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


async def dump_full(client, label, law_name, *grep_patterns):
    """법령 가져와 키워드 매칭 조문 전부 출력."""
    print("\n" + "=" * 90)
    print(f"[{label}] {law_name}")
    print("=" * 90)
    law = await search_law(client, law_name)
    if not law or not law["mst"]:
        print("  법령 검색 실패")
        return []
    print(f"  매칭: {law['law_nm']} (MST={law['mst']}, 시행 {law['ef_yd']})")
    arts = await get_law_articles(client, law["mst"])
    print(f"  (전체 조문 {len(arts)}건)")
    hits = grep_articles(arts, *grep_patterns)
    print(f"  키워드 매칭: {len(hits)}건")
    for art in hits:
        print(f"\n  >> 제{art['no']}조  {art['title']}  (시행 {art['ef_yd']})")
        print(f"     {_short(art['content'])}")
    return arts


async def main() -> None:
    if not OC:
        print("LAW_API_KEY 미설정")
        return

    async with httpx.AsyncClient(timeout=30) as h:
        # ─── 1. 녹색건축물 조성 지원법 ─────────────────────────────────
        await dump_full(h, "1A", "녹색건축물 조성 지원법",
                        r"용적률", r"건폐율", r"인센티브", r"완화")

        # ─── 2. 녹색건축물 조성 지원법 시행령 ─────────────────────────
        await dump_full(h, "1B", "녹색건축물 조성 지원법 시행령",
                        r"용적률", r"건폐율", r"완화")

        # ─── 3. 건축법 시행령 — '완화' '인증' '에너지' 광범위 키워드 ───
        print("\n" + "=" * 90)
        print("[1C] 건축법 시행령 — 완화/인증/에너지 키워드 광범위 검색")
        print("=" * 90)
        law_d = await search_law(h, "건축법 시행령")
        arts_d = await get_law_articles(h, law_d["mst"])
        print(f"  (전체 {len(arts_d)}건)")
        # 띄어쓰기 변형 + 짧은 키워드
        hits_d = grep_articles(
            arts_d,
            r"녹색건축",
            r"에너지효율",
            r"지능형건축",
            r"장수명",
            r"용적률.{0,10}완화",
            max_hits=20,
        )
        for art in hits_d:
            print(f"\n  >> 제{art['no']}조  {art['title']}")
            print(f"     {_short(art['content'], 700)}")

        # ─── 4. 주택건설기준 등에 관한 규정 ─────────────────────────
        await dump_full(h, "1D", "주택건설기준 등에 관한 규정",
                        r"용적률", r"인센티브", r"완화", r"장수명")

        # ─── 5. 건축법 시행령 §6 — 리모델링 등 적용완화 ───────────────
        print("\n" + "=" * 90)
        print("[2A] 건축법 시행령 §6 — '적용의 완화' 전문")
        print("=" * 90)
        for art in arts_d:
            if art["no"] == "6":
                print(f"\n  >> 제6조  {art['title']}")
                print("  " + art["content"].replace("\n", "\n  "))
                break

        # ─── 6. 건축법 시행령 — '리모델링' 전체 매칭 ────────────────
        print("\n" + "=" * 90)
        print("[2B] 건축법 시행령 — '리모델링' 키워드 매칭 전체")
        print("=" * 90)
        hits_rm = grep_articles(arts_d, r"리모델링", max_hits=15)
        for art in hits_rm:
            print(f"\n  >> 제{art['no']}조  {art['title']}")
            print(f"     {_short(art['content'], 600)}")


if __name__ == "__main__":
    asyncio.run(main())
