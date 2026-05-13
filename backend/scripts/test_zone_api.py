"""zone_use 조회 대안 경로 테스트: JUSO API → data.go.kr 토지이용규제서비스"""
import asyncio, sys, os, json
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

import httpx

JUSO_KEY = os.getenv("JUSO_API_KEY", "")
DATA_KEY = os.getenv("DATA_GO_KR_API_KEY", "")
ADDRESS = "서울특별시 강남구 테헤란로 152"

async def main():
    async with httpx.AsyncClient(timeout=15) as http:

        # ── 1. JUSO API: 주소 → PNU(admCd + parcel) ──────────────────────
        print("=== 1. JUSO API ===")
        r = await http.get(
            "https://www.juso.go.kr/addrlink/addrLinkApi.do",
            params={
                "confmKey": JUSO_KEY,
                "currentPage": 1,
                "countPerPage": 5,
                "keyword": ADDRESS,
                "resultType": "json",
            }
        )
        try:
            body = r.json()
            items = body.get("results", {}).get("juso", []) or []
            print(f"결과 {len(items)}건")
            for it in items[:3]:
                print(f"  admCd={it.get('admCd')} bdMgtSn={it.get('bdMgtSn')} jibunAddr={it.get('jibunAddr')}")
            pnu = items[0].get("bdMgtSn", "")[:19] if items else ""
            adm_cd = items[0].get("admCd", "") if items else ""
            print(f"  → PNU(bdMgtSn[:19])={pnu}, admCd={adm_cd}")
        except Exception as e:
            print(f"오류: {e} | {r.text[:200]}")
            pnu, adm_cd = "", ""

        # ── 2. 토지이용규제서비스 여러 엔드포인트 시도 ────────────────────
        if pnu:
            endpoints = [
                ("국토이용계획확인", "http://apis.data.go.kr/1613000/nsdi/EnsLandUseService/wfs/getLandUse"),
                ("토지특성정보", "http://apis.data.go.kr/1611000/LandInfoService/getLandInfo"),
                ("개별공시지가", "http://apis.data.go.kr/1611000/nsdi/EnsLandCharacterServiceV1/wfs/getLandCharacterWFS"),
            ]
            for name, url in endpoints:
                print(f"\n=== 2. {name} ===")
                r2 = await http.get(url, params={
                    "serviceKey": DATA_KEY,
                    "pnu": pnu,
                    "numOfRows": 5,
                    "pageNo": 1,
                })
                print(f"Status: {r2.status_code}")
                print(f"Response: {r2.text[:300]}")

asyncio.run(main())
