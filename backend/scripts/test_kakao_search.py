"""카카오 주소 API 빠른 테스트."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.address_api_client import AddressApiClient


async def main():
    c = AddressApiClient()
    for q in ["용인시 수지구 성복동 40", "서울 강남구 테헤란로 152"]:
        print(f"\n=== '{q}' ===")
        results = await c.search(q, count=3)
        print(f"결과 {len(results)}건")
        for r in results[:3]:
            print(f"  지번: {r['jibun_addr']}")
            print(f"  도로명: {r['road_addr']}")
            print(f"  PNU: {r['pnu']}")
    await c.close()


asyncio.run(main())
