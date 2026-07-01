"""환경영향평가 임계값 seed 검증 (법제처 별표 PDF 대조).

`config/environmental_assessment_thresholds.json` 의 소규모환경영향평가(별표4)
용도지역별 면적 임계가 환경영향평가법 시행령 [별표 4] 원문 PDF에 실제로 존재하는지
재다운로드해 대조한다. 법 개정으로 값이 바뀌면 불일치로 잡힘 → 회귀 게이트.

  실행:  .venv\\Scripts\\python.exe -m scripts.verify_environmental_thresholds
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parent.parent
_SEED = _ROOT / "config" / "environmental_assessment_thresholds.json"
_BASE = "https://www.law.go.kr"


async def _fetch_byp4_text() -> str:
    from dotenv import load_dotenv
    load_dotenv()
    oc = os.getenv("LAW_API_KEY")
    if not oc:
        raise RuntimeError("LAW_API_KEY 없음")
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as c:
        r = await c.get(f"{_BASE}/DRF/lawSearch.do", params={
            "OC": oc, "target": "law", "type": "JSON",
            "query": "환경영향평가법 시행령", "display": 5})
        items = r.json().get("LawSearch", {}).get("law", [])
        if isinstance(items, dict):
            items = [items]
        mst = [it for it in items
               if it.get("법령명한글") == "환경영향평가법 시행령"][0]["법령일련번호"]
        r = await c.get(f"{_BASE}/DRF/lawService.do", params={
            "OC": oc, "target": "law", "MST": mst, "type": "XML"})
        root = ET.fromstring(r.text)
        for byp in root.iter("별표단위"):
            no = (byp.findtext("별표번호") or "").strip()
            ga = (byp.findtext("별표가지번호") or "").strip()
            if (no, ga) == ("0004", "00"):
                pdf = (byp.findtext("별표서식PDF파일링크") or "").strip()
                rr = await c.get(f"{_BASE}{pdf}")
                import pdfplumber
                with pdfplumber.open(io.BytesIO(rr.content)) as pdf_o:
                    return "\n".join((p.extract_text() or "") for p in pdf_o.pages)
    raise RuntimeError("별표4 PDF 링크 미발견")


def main() -> None:
    seed = json.loads(_SEED.read_text(encoding="utf-8"))
    text = asyncio.run(_fetch_byp4_text())
    # 콤마 제거만 — 줄바꿈은 남겨 근접(re.DOTALL) 매칭에 활용.
    norm = text.replace(",", "")

    print("소규모환경영향평가 임계값 seed ↔ 별표4 PDF 대조\n")
    ok = miss = 0
    for cat, val in seed["small_scale"]["by_zone_category"].items():
        # PDF 표가 2열을 섞어 추출해 "6만…제곱미터" 처럼 단위 접미사가 끊길 수 있다.
        # 그래서 수치 토큰(아라비아 또는 한글 만/천, 숫자 경계 보장) 뒤 30자 이내에
        # "제곱미터"가 나오는지로 판정 — 단순 부분열 포함(예: "5000"⊂"25000")을 피한다.
        tokens = [str(val)]
        if val % 10000 == 0:
            tokens.append(f"{val // 10000}만")
        elif val % 1000 == 0 and val < 10000:
            tokens.append(f"{val // 1000}천")
        found = False
        for tok in tokens:
            pattern = rf"(?<!\d){re.escape(tok)}(?!\d)[^0-9]{{0,30}}?제곱미터"
            if re.search(pattern, norm, re.DOTALL):
                found = True
                break
        if found:
            ok += 1
        else:
            miss += 1
            print(f"  ✗ {cat}={val}㎡ — PDF 원문에서 근접 매칭 실패 (검색 토큰: {tokens})")
    print(f"\n  대조 {ok + miss}건 중 일치 {ok}, 불일치 {miss}")
    if miss:
        print("  ⚠ 불일치 — 법 개정 또는 seed 오기 가능. 수동 확인 필요.")
        sys.exit(1)
    print("  ✓ seed 전 값이 별표4 원문에 존재 — 정합.")


if __name__ == "__main__":
    main()
