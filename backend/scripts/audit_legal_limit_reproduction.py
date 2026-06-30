"""법정 한도 재현 감사 (캘리브레이션 루프 진입점).

골든셋은 "조례를 주입하면 엔진이 정답을 재현함"을 고정한다. 하지만 실무에서
사용자가 조례값을 직접 넣어주는 경우는 드물다 — 엔진은 대개 **조례 미주입** 상태로
`zone_limits.json`(국토계획법 시행령 별표) 기본값을 쓴다. 그런데 지자체 조례는
시행령보다 한도를 **강화**(낮춤)하는 일이 많다. 그래서 비주입 엔진은 한도를
과대평가 → "통과시키면 안 되는 계획을 통과"시키는 침묵 과대평가 구멍이 생긴다.

이 감사는 각 골든 케이스에 대해:
  (A) 엔진을 **조례 미주입**으로 돌린 한도(= 시행령 폴백)
  (B) 그 인허가에 실제 적용된 법정 한도(= 케이스의 applied_ordinance)
의 갭을 정량화한다. 갭이 큰 (용도지역) = `ordinance_seed.json` 보강 1순위.

  실행:  .venv\\Scripts\\python.exe -m scripts.audit_legal_limit_reproduction

신호·점수 로직은 건드리지 않는다. 순수 측정 도구다.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Windows 콘솔(cp949)에서 em-dash·한글 깨짐 방지
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_GOLDEN_DIR = Path(__file__).resolve().parent.parent / "tests" / "golden"


def _build_engine_uninjected():
    """조례 리졸버 없이(=비주입) 엔진 생성 → zone_limits.json 시행령 폴백 경로."""
    from services.diagnose_engine import DiagnoseEngine

    resolver = MagicMock()
    cache = MagicMock()
    cache.save_history = AsyncMock()
    cache.lookup_street_block_height = AsyncMock(return_value=None)
    llm = MagicMock()
    llm.available = False
    return DiagnoseEngine(
        resolver, cache, llm,
        ordinance_resolver=None,  # ← 핵심: 조례 미주입
        luris=None, eum=None,
    )


def _build_req(inp: dict, label: str) -> dict:
    req = {
        "address": label,
        "building_use": inp["building_use"],
        "site_area": inp["site_area"],
        "building_area": inp["building_area"],
        "total_floor_area": inp["total_floor_area"],
        "floor_area_above": inp.get("floor_area_above", inp["total_floor_area"]),
        "floors_above": inp["floors_above"],
        "floors_below": inp.get("floors_below", 0),
        "height": inp.get("height") or round(inp["floors_above"] * 3.3, 1),
    }
    for opt in (
        "landscape_area", "provided_parking_spaces",
        "units", "unit_exclusive_area", "public_open_space_area",
    ):
        if inp.get(opt) is not None:
            req[opt] = inp[opt]
    return req


async def _audit_case(case: dict) -> dict | None:
    inp = case["input"]
    applied = case.get("applied_ordinance") or {}
    legal_bcr = applied.get("building_coverage_ratio")
    legal_far = applied.get("floor_area_ratio")
    if legal_bcr is None and legal_far is None:
        return None  # 비교할 실제 법정 한도가 없음

    engine = _build_engine_uninjected()
    land = {
        "zone_use": inp["zone_use"],
        "jurisdiction_code": "GOLD0",
        "jurisdiction_name": "(익명 지자체)",
    }
    result = await engine._diagnose(
        _build_req(inp, case.get("label", case["id"])),
        land, save_history=False, skip_ai=True,
    )
    res = result["results"]
    eng_bcr = res.get("건폐율", {}).get("limit_pct")
    eng_far = res.get("용적률", {}).get("limit_pct")

    def _gap(eng, legal):
        if eng is None or legal is None:
            return None
        return round(eng - legal, 2)  # +면 엔진이 과대평가(위험), -면 과소평가(보수)

    return {
        "id": case["id"],
        "zone": inp["zone_use"],
        "bcr_engine": eng_bcr, "bcr_legal": legal_bcr, "bcr_gap": _gap(eng_bcr, legal_bcr),
        "far_engine": eng_far, "far_legal": legal_far, "far_gap": _gap(eng_far, legal_far),
    }


async def _run() -> list[dict]:
    rows = []
    for path in sorted(_GOLDEN_DIR.glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        row = await _audit_case(case)
        if row:
            rows.append(row)
    return rows


def _fmt(v) -> str:
    return "—" if v is None else f"{v:g}"


def main() -> None:
    rows = asyncio.run(_run())
    if not rows:
        print("감사할 케이스 없음 (applied_ordinance 한도가 있는 케이스 필요).")
        return

    # 표 출력
    print("\n법정 한도 재현 감사 — 비주입 엔진(시행령 폴백) vs 실제 적용 법정 한도")
    print("  gap = 엔진한도 − 실제한도.  (+)면 과대평가=위험(통과 오판),  (−)면 과소평가=보수.\n")
    hdr = f"{'case':<42} {'zone':<14} {'BCR 엔진/법정/gap':<22} {'FAR 엔진/법정/gap':<24}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        bcr = f"{_fmt(r['bcr_engine'])}/{_fmt(r['bcr_legal'])}/{_fmt(r['bcr_gap'])}"
        far = f"{_fmt(r['far_engine'])}/{_fmt(r['far_legal'])}/{_fmt(r['far_gap'])}"
        print(f"{r['id']:<42} {r['zone']:<14} {bcr:<22} {far:<24}")

    # 용도지역별 최대 과대평가 집계 (보강 우선순위)
    print("\n── 용도지역별 최대 과대평가 갭 (조례 DB 보강 우선순위) ──")
    by_zone: dict[str, dict] = {}
    for r in rows:
        z = by_zone.setdefault(r["zone"], {"bcr": 0.0, "far": 0.0, "n": 0})
        z["n"] += 1
        if r["bcr_gap"] is not None:
            z["bcr"] = max(z["bcr"], r["bcr_gap"])
        if r["far_gap"] is not None:
            z["far"] = max(z["far"], r["far_gap"])
    ranked = sorted(by_zone.items(), key=lambda kv: kv[1]["far"], reverse=True)
    for zone, z in ranked:
        flag = "  ⚠ 과대평가" if (z["bcr"] > 0 or z["far"] > 0) else "  ✓ 보수적"
        print(f"  {zone:<16} (n={z['n']})  BCR 최대 +{z['bcr']:g}%p  FAR 최대 +{z['far']:g}%p{flag}")

    # 위험 요약
    over = [r for r in rows if (r["bcr_gap"] or 0) > 0 or (r["far_gap"] or 0) > 0]
    print(f"\n총 {len(rows)}건 중 비주입 과대평가(위험) {len(over)}건. "
          f"이 용도지역들이 조례 seed 보강 시 가장 큰 정확도 이득.")


if __name__ == "__main__":
    main()
