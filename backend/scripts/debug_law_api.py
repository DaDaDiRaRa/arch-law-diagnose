"""법제처 API 디버그 — 원본 요청/응답 확인."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from dotenv import load_dotenv

load_dotenv()
OC = os.getenv("LAW_API_KEY", "")
BASE = "https://www.law.go.kr/DRF"


async def main() -> None:
    async with httpx.AsyncClient(timeout=20) as h:
        # 1. 건축법 검색 — 왜 실패하는지
        for q in ["건축법", "건축법시행령", "건축법 시행령"]:
            try:
                r = await h.get(f"{BASE}/lawSearch.do", params={
                    "OC": OC, "target": "law", "type": "JSON",
                    "query": q, "display": 5, "page": 1,
                })
                print(f"\n--- search '{q}' (status {r.status_code}) ---")
                body = r.json()
                items = body.get("LawSearch", {}).get("law", []) or []
                if isinstance(items, dict):
                    items = [items]
                for it in items[:3]:
                    print(f"  · {it.get('법령명한글')} / MST={it.get('법령일련번호')} / 시행={it.get('시행일자')}")
            except Exception as e:
                print(f"\n--- search '{q}' EXCEPTION: {type(e).__name__}: {e!r} ---")
                print(f"    text head: {r.text[:300] if 'r' in dir() else 'n/a'}")

        # 2. 도시재정비촉진법 본문 — 왜 조문 1건만 잡히는지
        r = await h.get(f"{BASE}/lawService.do", params={
            "OC": OC, "target": "law", "MST": "257351", "type": "XML",
        })
        print(f"\n--- lawService MST=257351 (status {r.status_code}, len {len(r.text)}) ---")
        print(r.text[:2000])


if __name__ == "__main__":
    asyncio.run(main())
