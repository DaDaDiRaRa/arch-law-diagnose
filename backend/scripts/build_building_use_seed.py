"""건축법 시행령 [별표 1] → config/building_use_seed.json 전사.

CLAUDE.md 가드레일: 자치구 고시 PDF 자동파싱은 금지지만, **법제처 DRF 현행 시행령
별표 PDF**(`별표서식PDF파일링크`)는 예외 — 추출값을 seed 로 전사하고 verify 로 전수
대조하는 조건이다. 이 스크립트가 전사, `verify_building_use_seed.py` 가 대조다.

파서는 `services.building_use_table.parse_byeolpyo1` 하나를 build·verify 가 공유한다.

실행 (LAW_API_KEY 필요):
    cd backend && .venv\Scripts\python.exe scripts\build_building_use_seed.py
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from services.building_use_table import parse_byeolpyo1  # noqa: E402

_BASE = "https://www.law.go.kr"
_SEED = Path(__file__).resolve().parent.parent / "config" / "building_use_seed.json"


async def fetch_byeolpyo1() -> tuple[str, str]:
    """별표1 PDF 텍스트 + 별표 제목. 별표 본문은 조문 XML 에 없고 PDF 로만 온다."""
    oc = os.getenv("LAW_API_KEY")
    if not oc:
        raise RuntimeError("LAW_API_KEY 없음")
    async with httpx.AsyncClient(timeout=90, follow_redirects=True) as c:
        r = await c.get(f"{_BASE}/DRF/lawSearch.do", params={
            "OC": oc, "target": "law", "type": "JSON",
            "query": "건축법 시행령", "display": 10})
        items = r.json().get("LawSearch", {}).get("law", [])
        if isinstance(items, dict):
            items = [items]
        exact = [it for it in items
                 if it.get("법령명한글", "").replace(" ", "") == "건축법시행령"]
        if not (exact or items):
            raise RuntimeError("건축법 시행령 검색 실패")
        mst = (exact or items)[0]["법령일련번호"]

        r = await c.get(f"{_BASE}/DRF/lawService.do", params={
            "OC": oc, "target": "law", "MST": mst, "type": "XML"})
        root = ET.fromstring(r.text)
        link = title = None
        for byp in root.iter("별표단위"):
            if (byp.findtext("별표번호") or "").strip() in ("1", "0001"):
                title = (byp.findtext("별표제목") or "").strip()
                link = (byp.findtext("별표서식PDF파일링크") or "").strip()
                break
        if not link:
            raise RuntimeError("별표1 PDF 링크를 찾지 못함")

        r = await c.get(f"{_BASE}{link}")
        import pdfplumber
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    return text, title or ""


def main() -> None:
    text, title = asyncio.run(fetch_byeolpyo1())
    parsed = parse_byeolpyo1(text)
    n = len(parsed["groups"])
    if n != 29:
        raise SystemExit(f"용도군 {n}개 — 29개가 아니면 별표 구조가 바뀐 것이다. 중단.")
    out = {
        "_comment": "건축법 시행령 [별표 1] 용도별 건축물의 종류 — 전사본. "
                    "직접 수정 금지, scripts/build_building_use_seed.py 로 재생성. "
                    "현행 대조는 scripts/verify_building_use_seed.py.",
        "_source": f"법제처 DRF 별표서식PDF파일링크 · {title}",
        **parsed,
    }
    _SEED.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    cond = set(parsed["conditional"])
    safe = sum(1 for k, v in parsed["names"].items() if len(v) == 1 and k not in cond)
    print(f"용도군 {n} · 시설명 {len(parsed['names'])} "
          f"(자동채움 {safe} · 조건부/모호 {len(parsed['names']) - safe}) → {_SEED}")


if __name__ == "__main__":
    main()
