"""arch-law-diagnose MCP 서버 — Claude Code 등 AI 에이전트가 법규 진단을 직접 호출.

backend/main.py 가 이 파일의 `mcp` 를 `/mcp` 로 mount 한다(kunwon-ops 저장소
docs/plan-mcp-gateway.md §9 의 패턴 재사용 — stateless_http・streamable_http_path="/"・
DNS 리바인딩 방지 끄기). 도구 함수 안에서 `main` 모듈을 지연 import 하는 이유: main.py 가
이 파일을 mount 하므로 모듈 레벨에서 서로를 import 하면 순환참조가 된다 — 함수 호출
시점(런타임)까지 미루면 main.py 가 이미 완전히 로드된 뒤라 문제없다.

로컬 stdio 실행(선택): claude mcp add arch-law-diagnose python d:/APPS/arch-law-diagnose/backend/mcp_server/server.py

## 노출 도구
- land_info : 주소/PNU → 토지이용계획(용도지역·지구·구역·공시지가 등). 다른 형제앱
              (arch-law-graph·law-qa)도 이미 REST 로 이 로직을 재사용 중(단일 소스).
- diagnose  : 주소 + 건물정보 → 법규 6개 카테고리 종합 진단(건폐율·용적률·주차·높이·
              조경·설비소방). Claude API 호출 포함 65~110초 — 비용이 커서 인증 필요.
"""

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

mcp = FastMCP(
    "arch-law-diagnose",
    stateless_http=True,
    streamable_http_path="/",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


@mcp.tool()
async def land_info(
    address: str = "",
    pnu: str = "",
    lat: float | None = None,
    lon: float | None = None,
) -> dict:
    """주소/PNU 로 토지이용계획 즉시 조회 — 용도지역·지역지구·지목·공시지가 자동 채움.

    address · pnu · (lat,lon) 중 하나는 필수. lat/lon 을 주면 지오코딩을 생략하고
    그 좌표를 그대로 쓴다(상위에서 이미 좌표를 아는 경우 — 예: 다른 지오코더 결과 재사용).
    """
    from main import land_resolver

    if land_resolver is None:
        return {"error": "서비스 초기화 중"}
    if not address and not pnu and (lat is None or lon is None):
        return {"error": "address · pnu · (lat,lon) 중 하나는 필수"}
    return await land_resolver.resolve(address, pnu=pnu, lon=lon, lat=lat)


@mcp.tool()
async def diagnose(
    address: str,
    building_use: str,
    site_area: float,
    building_area: float,
    floor_area_above: float,
    floors_above: int,
    height: float,
    pnu: str = "",
    floor_area_below: float | None = None,
    floors_below: int = 0,
    zone_district: str = "",
    road_width: float | None = None,
    landscape_area: float | None = None,
    provided_parking_spaces: int | None = None,
    units: int | None = None,
) -> dict:
    """대지 주소 + 건물 정보 → 건폐율·용적률·주차·높이·조경·설비소방 6개 카테고리 종합 진단.

    용도지역은 VWorld 자동 조회(zone_district 로 지역지구를 직접 지정할 수도 있음).
    진단 1건에 Claude API 호출이 포함돼 65~110초 정도 걸린다 — 여유 있게 기다릴 것.
    """
    from main import engine
    from schemas import DiagnoseRequest

    if engine is None:
        return {"error": "서비스 초기화 중"}
    req = DiagnoseRequest(
        address=address, pnu=pnu or None, building_use=building_use,
        zone_district=zone_district or None,
        site_area=site_area, building_area=building_area,
        floor_area_above=floor_area_above, floor_area_below=floor_area_below,
        floors_above=floors_above, floors_below=floors_below,
        height=height, units=units,
        road_width=road_width, landscape_area=landscape_area,
        provided_parking_spaces=provided_parking_spaces,
    )
    payload = req.model_dump()
    above = float(payload.get("floor_area_above") or 0)
    below = float(payload.get("floor_area_below") or 0)
    payload["total_floor_area"] = above + below
    return await engine.run(payload)


if __name__ == "__main__":
    mcp.run("stdio")
