"""행위제한 통합 진단 — 실제 진단 흐름 검증.

3개 케이스:
1. 강남 2종주거 + 공동주택 → 행위제한 ALLOWED (정상 사업)
2. 강남 일반상업 + 공동주택 → 행위제한 FORBIDDEN (위반)
3. 종로 자연녹지 + 공장 → 행위제한 ALLOWED (놀랍지만 일부 가능)
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.calculator import land_use_act
from services.luris_client import LurisClient


async def main():
    luris = LurisClient()

    cases = [
        ("11680", "제2종일반주거지역", "공동주택", "정상 사업 (ALLOWED 기대)"),
        ("11680", "일반상업지역",      "공동주택", "위반 (FORBIDDEN 기대)"),
        ("11680", "일반상업지역",      "업무시설", "DATA_INSUFFICIENT 가능"),
        ("11110", "자연녹지지역",      "단독주택", "정상 (ALLOWED 기대)"),
    ]

    for area, zone, use, label in cases:
        result = await land_use_act.calculate(
            luris,
            zone_use=zone,
            building_use=use,
            jurisdiction_code=area + "00000",  # PNU 19자리 시뮬레이션
        )
        print(f"\n=== {area} {zone} + {use} === ({label})")
        print(f"  category: {result['category']}")
        print(f"  pass:     {result['pass']}")
        print(f"  score:    {result['score']}")
        print(f"  conf:     {result['confidence']}")
        print(f"  source:   {result['source']}")
        print(f"  notes:    {result['notes']}")
        print(f"  law_refs: {len(result['law_refs'])}건")

    await luris.close()
    print("\n✅ 통합 테스트 완료")


asyncio.run(main())
