"""교통영향평가 임계값 seed 검증 (법제처 별표 PDF 대조).

`config/traffic_impact_thresholds.json` 의 용도별 임계값이 도시교통정비촉진법
시행령 [별표 1] 원문(법제처 DRF 별표 PDF)에 실제로 존재하는지 재다운로드해 대조한다.
법 개정으로 값이 바뀌면 여기서 불일치로 잡힌다 → 캘리브레이션 회귀 게이트.

  실행:  .venv\\Scripts\\python.exe -m scripts.verify_traffic_thresholds

별표 PDF 링크는 lawService.do 응답의 <별표서식PDF파일링크> 에서 얻는다
(별표 본문은 조문 XML 에 텍스트로 없고 첨부 PDF/HWP 로만 제공됨 — 사용자 제보 반영).
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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parent.parent
_SEED = _ROOT / "config" / "traffic_impact_thresholds.json"
_BASE = "https://www.law.go.kr"


async def _fetch_byp1_pdf_text() -> str:
    from dotenv import load_dotenv
    load_dotenv()
    oc = os.getenv("LAW_API_KEY")
    if not oc:
        raise RuntimeError("LAW_API_KEY 없음")

    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as c:
        # 1) 시행령 MST 검색
        r = await c.get(f"{_BASE}/DRF/lawSearch.do", params={
            "OC": oc, "target": "law", "type": "JSON",
            "query": "도시교통정비촉진법 시행령", "display": 10})
        items = r.json().get("LawSearch", {}).get("law", [])
        if isinstance(items, dict):
            items = [items]
        exact = [it for it in items
                 if it.get("법령명한글", "").replace(" ", "") == "도시교통정비촉진법시행령"]
        mst = (exact or items)[0]["법령일련번호"]

        # 2) 본문 XML → 별표1 PDF 링크
        r = await c.get(f"{_BASE}/DRF/lawService.do", params={
            "OC": oc, "target": "law", "MST": mst, "type": "XML"})
        root = ET.fromstring(r.text)
        pdf_link = None
        for byp in root.iter("별표단위"):
            no = (byp.findtext("별표번호") or "").strip()
            if no in ("1", "0001"):
                pdf_link = (byp.findtext("별표서식PDF파일링크") or "").strip()
                break
        if not pdf_link:
            raise RuntimeError("별표1 PDF 링크를 찾지 못함")

        # 3) PDF 다운로드 → 텍스트
        r = await c.get(f"{_BASE}{pdf_link}")
        import pdfplumber
        with pdfplumber.open(io.BytesIO(r.content)) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages)


def main() -> None:
    seed = json.loads(_SEED.read_text(encoding="utf-8"))
    text = asyncio.run(_fetch_byp1_pdf_text())
    # 숫자 표기 정규화 — PDF 는 "25,000㎡", seed 는 25000
    norm = text.replace(",", "")

    print("교통영향평가 임계값 seed ↔ 별표1 PDF 대조\n")
    ok = miss = 0
    for use, v in seed["by_use"].items():
        for col in ("urban", "region"):
            val = v[col]
            if f"{val}㎡" in norm:
                ok += 1
            else:
                miss += 1
                print(f"  ✗ {use} {col}={val}㎡ — PDF 원문에서 미발견")
    total = ok + miss
    print(f"\n  대조 {total}건 중 일치 {ok}, 불일치 {miss}")
    if miss == 0:
        print("  ✓ seed 전 값이 별표1 원문에 존재 — 정합.")
    else:
        print("  ⚠ 불일치 발견 — 법 개정 또는 seed 오기 가능. 수동 확인 필요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
