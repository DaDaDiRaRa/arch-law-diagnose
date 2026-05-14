"""LurisClient + ucode 매핑 통합 테스트."""
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

    # 테스트 케이스: (시군구코드, 용도지역, 건물용도)
    cases = [
        ("11110", "자연녹지지역",      "단독주택"),   # 종로구 자연녹지에 단독주택?
        ("11110", "일반상업지역",      "업무시설"),   # 종로구 일반상업에 업무시설?
        ("11680", "제2종일반주거지역", "공동주택"),   # 강남구 2종주거에 공동주택?
        ("41135", "제3종일반주거지역", "위락시설"),   # 성남시 분당구 3종주거에 위락시설? (보통 불가)
    ]

    for area_cd, zone, use in cases:
        ucode = ZONE_TO_UCODE.get(zone, "")
        land_nm = USE_TO_LAND.get(use, use)
        print(f"\n=== {area_cd} {zone}({ucode}) — {use}(={land_nm}) ===")
        info = await client.get_act_info(area_cd, ucode, land_nm)
        if not info:
            print("  (응답 없음 또는 조회 실패)")
            continue
        s = info["summary"]
        print(f"  지역지구: {info['zone_name']} ({info['zone_code']})")
        print(f"  허가 가능 세부행위 수: {s['buildable_count']}/{s['total_items']}")
        for act in info["acts"][:2]:  # 최대 2개만
            print(f"  [{act['name']}] {act['allowed']}")
            for it in act["items"][:3]:
                print(f"    · {it['name']} ({it['law_ref']})")

    # 행위명 검색 테스트
    print("\n=== 행위명 검색: '아파트' ===")
    results = await client.search_action("아파트", rows=5)
    for r in results:
        print(f"  · {r['name']} ({r['code']})")

    await client.close()


asyncio.run(main())
