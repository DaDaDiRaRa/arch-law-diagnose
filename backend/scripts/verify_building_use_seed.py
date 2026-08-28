"""building_use_seed.json ↔ 현행 별표1 전수 대조.

가드레일 조건("전사 + verify 전수 대조")의 검증 쪽. 별표가 개정되면 여기서 먼저
깨지고, 그때 build 를 다시 돌려 전사본을 갱신한다.

build 와 **같은 파서**(`services.building_use_table.parse_byeolpyo1`)를 쓴다 —
검증용 파서를 따로 두면 둘이 같이 틀려도 통과한다.

실행 (LAW_API_KEY 필요 · 네트워크):
    cd backend && .venv\Scripts\python.exe scripts\verify_building_use_seed.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build_building_use_seed import fetch_byeolpyo1  # noqa: E402
from services.building_use_table import parse_byeolpyo1  # noqa: E402

_SEED = Path(__file__).resolve().parent.parent / "config" / "building_use_seed.json"


def main() -> int:
    seed = json.loads(_SEED.read_text(encoding="utf-8"))
    text, title = asyncio.run(fetch_byeolpyo1())
    live = parse_byeolpyo1(text)

    print(f"현행: {title}\n")
    fail = 0

    sg, lg = seed.get("groups", {}), live["groups"]
    if sg == lg:
        print(f"[PASS] 용도군 {len(lg)}개 일치")
    else:
        fail += 1
        print(f"[FAIL] 용도군 불일치 — seed {len(sg)} vs 현행 {len(lg)}")
        for k in sorted(set(sg) | set(lg), key=lambda x: int(x)):
            if sg.get(k) != lg.get(k):
                print(f"        {k}: seed={sg.get(k)!r} 현행={lg.get(k)!r}")

    sn, ln = seed.get("names", {}), live["names"]
    only_seed, only_live = set(sn) - set(ln), set(ln) - set(sn)
    changed = {k for k in set(sn) & set(ln) if sn[k] != ln[k]}
    if not (only_seed or only_live or changed):
        print(f"[PASS] 시설명 {len(ln)}종 전수 일치")
    else:
        fail += 1
        print(f"[FAIL] 시설명 차이 — seed에만 {len(only_seed)} · 현행에만 {len(only_live)} "
              f"· 용도군 바뀜 {len(changed)}")
        for k in sorted(only_seed)[:15]:
            print(f"        seed에만: {k} ({sn[k]})")
        for k in sorted(only_live)[:15]:
            print(f"        현행에만: {k} ({ln[k]})")
        for k in sorted(changed)[:15]:
            print(f"        바뀜: {k} {sn[k]} → {ln[k]}")

    sc, lc = set(seed.get("conditional", [])), set(live["conditional"])
    if sc == lc:
        print(f"[PASS] 조건부 {len(lc)}종 일치")
    else:
        fail += 1
        print(f"[FAIL] 조건부 차이 — seed에만 {sorted(sc - lc)[:10]} "
              f"현행에만 {sorted(lc - sc)[:10]}")

    print("\n" + ("전수 일치 — seed 유효" if not fail
                  else f"{fail}개 항목 불일치 — build 를 다시 돌려 전사본을 갱신할 것"))
    return 0 if not fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
