import asyncio, sys, os
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

import httpx

async def main():
    key = os.getenv("VWORLD_API_KEY", "")
    print(f"Key: {key}")

    # 1) WFS JSON 시도
    cql = "INTERSECTS(geom,POINT(127.036514 37.500029))"
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": "lt_c_lhblpn",
        "key": key,
        "output": "application/json",
        "count": 3,
        "CQL_FILTER": cql,
    }
    headers = {"Referer": "http://localhost:8000"}
    lon, lat = 127.036514, 37.500029

    async with httpx.AsyncClient(timeout=15) as http:
        # WGS84 → EPSG:3857 (Web Mercator) 변환
        import math
        x3857 = lon * 20037508.342789244 / 180.0
        y3857 = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * 6378137.0
        print(f"EPSG:3857 좌표: x={x3857:.1f}, y={y3857:.1f}")
        print()

        # lt_c_uq111 — uname/ucode 필드가 있는 용도지역 레이어
        for layer in ["lt_c_uq111", "lt_c_lhzone"]:
            p = {
                "service": "WFS", "version": "2.0.0", "request": "GetFeature",
                "typeName": layer, "key": key,
                "output": "application/json", "count": 5,
                "CQL_FILTER": f"INTERSECTS(geom,POINT({x3857} {y3857}))",
            }
            r = await http.get("https://api.vworld.kr/req/wfs", params=p, headers=headers)
            try:
                body = r.json()
                feats = body.get("features", [])
                print(f"[{layer}] features={len(feats)}")
                for f in feats[:3]:
                    print(f"  props: {f.get('properties')}")
            except:
                print(f"[{layer}] non-JSON: {r.text[:200]}")
            print()
        # 1) Data API — LT_C_LHBLPN (토지이용계획)
        p = {
            "service": "data", "request": "GetFeature",
            "data": "LT_C_LHBLPN",
            "key": key, "format": "json", "size": 5, "page": 1,
            "geometry": "true", "attribute": "true",
            "crs": "EPSG:4326",
            "bbox": f"{lon-0.001},{lat-0.001},{lon+0.001},{lat+0.001},EPSG:4326",
        }
        r = await http.get("https://api.vworld.kr/req/data", params=p, headers=headers)
        print("=== Data API LT_C_LHBLPN ===")
        try:
            body = r.json()
            status = body.get("response", {}).get("status")
            feats = body.get("response", {}).get("result", {}).get("featureCollection", {}).get("features", [])
            print(f"  status={status}, features={len(feats)}")
            for f in feats[:3]:
                print(f"  props: {f.get('properties')}")
        except Exception as e:
            print(f"  error: {e} | {r.text[:200]}")

        print()
        # 2) WFS — BBOX 방식 (CQL 대신)
        bbox_5179_approx = "14113000,4492000,14115000,4493000"  # 강남구 근처 EPSG:5179 근사값
        p2 = {
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeName": "lt_c_lhblpn", "key": key,
            "output": "application/json", "count": 5,
            "BBOX": bbox_5179_approx,
        }
        r2 = await http.get("https://api.vworld.kr/req/wfs", params=p2, headers=headers)
        print("=== WFS BBOX EPSG:5179 ===")
        try:
            body2 = r2.json()
            feats2 = body2.get("features", [])
            print(f"  features={len(feats2)}")
            for f in feats2[:3]:
                print(f"  props: {f.get('properties')}")
        except Exception as e:
            print(f"  error: {e} | {r2.text[:200]}")

asyncio.run(main())
