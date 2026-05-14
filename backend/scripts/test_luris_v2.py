"""LURIS v2 — 매핑 수정 후 실용 케이스 검증."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.luris_client import LurisClient

_MAPPING_PATH = Path(__file__).parent.parent / "config" / "ucode_mapping.json"
with open(_MAPPING_PATH, encoding="utf-8") as f:
    MAPPING = json.load(f)

ZONE_TO_UCODE = MAPPING["zone_use_to_ucode"]
USE_TO_LAND = MAPPING["building_use_to_land_use_nm"]


async def main():
    client = LurisClient()

    cases = [
        ("11680", "제2종일반주거지역", "공동주택", "✓ 정상"),
        ("11680", "일반상업지역",      "공동주택", "△ 상업지역 공동주택 제한 있음"),
        ("11680", "일반상업지역",      "업무시설", "✓ 정상"),
        ("11680", "제2종일반주거지역", "위락시설", "✗ 불가"),
        ("11680", "자연녹지지역",      "단독주택", "✓ 정상"),
        ("11680", "자연녹지지역",      "공장",     "✗ 불가"),
        ("41135", "제3종일반주거지역", "공공업무시설", "△"),
    ]

    print(f"{'케이스':<55} {'verdict':<20} {'요약'}")
    print("-" * 110)
    for area, zone, use, expected in cases:
        ucode = ZONE_TO_UCODE.get(zone, "")
        land_nm = USE_TO_LAND.get(use, use)
        info = await client.get_act_info(area, ucode, land_nm)
        label = f"{area} {zone[:8]} + {use}"
        if not info:
            print(f"{label:<55} {'(응답 없음)':<20}")
            continue
        s = info["summary"]
        verdict = s["verdict"]
        summary_txt = f"허용 {s['allowed_count']} / 금지 {s['forbidden_count']} (총 {s['total_items']}건)"
        print(f"{label:<55} {verdict:<20} {summary_txt}  | 기대: {expected}")

        # 한 케이스 깊게 들여다보기 — 공동주택 강남 2종주거
        if zone == "제2종일반주거지역" and use == "공동주택":
            print("    상세:")
            for act in info["acts"][:1]:
                print(f"      [{act['name']}] {act['allowed']}")
                for it in act["items"][:3]:
                    print(f"        · {it['name']} ({it['law_ref']})")

    await client.close()


asyncio.run(main())
