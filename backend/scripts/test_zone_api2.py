"""zone_use 조회 대안 경로 테스트 v2:
  1. JUSO API → PNU
  2. LURIS API (molit) — 용도지역 직접 조회
  3. data.go.kr 토지이용규제 (여러 endpoint 시도)
"""
import asyncio, sys, os, json, urllib.parse
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

import httpx

JUSO_KEY = os.getenv("JUSO_API_KEY", "")
DATA_KEY = os.getenv("DATA_GO_KR_API_KEY", "")
ADDRESS = "서울특별시 강남구 테헤란로 152"

print(f"JUSO_KEY: {JUSO_KEY[:10]}...")
print(f"DATA_KEY: {DATA_KEY[:20]}...")

async def main():
    async with httpx.AsyncClient(timeout=15, verify=False) as http:

        # ── 1. JUSO API: 주소 → PNU ──────────────────────────────────
        print("\n=== 1. JUSO API ===")
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
        pnu, adm_cd = "", ""
        try:
            body = r.json()
            items = body.get("results", {}).get("juso", []) or []
            print(f"결과 {len(items)}건")
            for it in items[:3]:
                print(f"  admCd={it.get('admCd')} bdMgtSn={it.get('bdMgtSn')} jibunAddr={it.get('jibunAddr')}")
            pnu = items[0].get("bdMgtSn", "")[:19] if items else ""
            adm_cd = items[0].get("admCd", "") if items else ""
            print(f"  → PNU={pnu}, admCd={adm_cd}")
        except Exception as e:
            print(f"오류: {e} | {r.text[:200]}")

        if not pnu:
            print("PNU 없음 — 이후 테스트 생략")
            return

        # ── 2. LURIS API (국토부 토지이용규제정보시스템) ─────────────
        print("\n=== 2. LURIS (molit.go.kr) ===")
        luris_endpoints = [
            ("lrUseInfoDtlList", "https://luris.molit.go.kr/web/api/lrUseInfoDtlList.do"),
            ("lrUseInfo", "https://luris.molit.go.kr/web/api/lrUseInfo.do"),
        ]
        for name, url in luris_endpoints:
            r2 = await http.get(url, params={"pnuCd": pnu, "pageNo": 1, "numOfRows": 10},
                                follow_redirects=True)
            print(f"[{name}] Status: {r2.status_code}")
            print(f"  Final URL: {r2.url}")
            print(f"  Response: {r2.text[:600]}")
            print()

        # ── 3. data.go.kr 토지이용계획확인 (여러 endpoint) ──────────
        # 일부 API는 serviceKey를 URL-decode 없이 raw hex로 전달
        # 일부는 + / = 포함된 base64를 그대로 전달
        print("=== 3. data.go.kr endpoints ===")

        # data.go.kr 기본 URL 패턴들
        endpoints = [
            # 국토이용정보체계 (1613000) — 토지이용계획
            ("EnsLandUse_v1", "http://apis.data.go.kr/1613000/nsdi/EnsLandUseService/v1/getLandUse",
             {"pnu": pnu}),
            ("EnsLandUse_attr", "http://apis.data.go.kr/1613000/nsdi/EnsLandUseService/v1/getLandUseAttr",
             {"pnu": pnu}),
            # 토지 특성 정보 (1611000)
            ("LandCharacter", "http://apis.data.go.kr/1611000/nsdi/EnsLandCharacterServiceV1/wfs/getLandCharacterWFS",
             {"pnu": pnu}),
            # 건축행위허용정보 (1613000)
            ("BuildingAllow", "http://apis.data.go.kr/1613000/nsdi/EnsLandUseService/v1/getAllowBuild",
             {"pnu": pnu}),
            # 토지이용계획확인서 JSON
            ("LandUsePlan_json", "http://apis.data.go.kr/1613000/nsdi/EnsLandUseService/v1/getLandUsePlan",
             {"pnuCd": pnu}),
        ]
        for name, url, extra_params in endpoints:
            params = {
                "serviceKey": DATA_KEY,
                "numOfRows": 5,
                "pageNo": 1,
                **extra_params,
            }
            try:
                r3 = await http.get(url, params=params)
                print(f"[{name}] Status: {r3.status_code}")
                print(f"  URL: {r3.url}")
                print(f"  Response: {r3.text[:300]}")
            except Exception as e:
                print(f"[{name}] Error: {e}")
            print()

        # ── 4. VWorld Data API — 용도지역 레이어 직접 ───────────────
        print("=== 4. VWorld Data API ===")
        VWORLD_KEY = os.getenv("VWORLD_API_KEY", "")
        lon, lat = 127.036514, 37.500029

        for data_layer in ["LT_C_UQ111", "LT_C_LHBLPN"]:
            # geomFilter — POINT(lon lat), EPSG:4326
            for gf in [
                f"POINT({lon} {lat})",
                f'{{"type":"Point","coordinates":[{lon},{lat}]}}',
            ]:
                r4 = await http.get(
                    "https://api.vworld.kr/req/data",
                    params={
                        "service": "data",
                        "request": "GetFeature",
                        "data": data_layer,
                        "key": VWORLD_KEY,
                        "format": "json",
                        "size": 5,
                        "page": 1,
                        "geometry": "false",
                        "attribute": "true",
                        "crs": "EPSG:4326",
                        "geomFilter": gf,
                    },
                    headers={"Referer": "http://localhost:8000"},
                )
                print(f"[{data_layer}] geomFilter={gf[:30]}... Status: {r4.status_code}")
                try:
                    body4 = r4.json()
                    status = body4.get("response", {}).get("status")
                    feats = body4.get("response", {}).get("result", {}).get("featureCollection", {}).get("features", [])
                    print(f"  status={status}, features={len(feats)}")
                    for f in feats[:3]:
                        print(f"  props: {f.get('properties')}")
                    if status == "ERROR":
                        err = body4.get("response", {}).get("error", {})
                        print(f"  error: {err.get('text','')[:200]}")
                except Exception as e:
                    print(f"  parse error: {e} | {r4.text[:300]}")
                print()

asyncio.run(main())
