"""VWorldClient 오프라인 모킹 테스트 (respx).

respx 가 httpx.AsyncClient 의 기본 transport 를 대체하므로
클라이언트를 mock 컨텍스트 내부에서 생성하면 실제 네트워크 호출 없이 동작한다.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from services.vworld_client import VWorldClient


# ─── 공통 픽스처 ─────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _vworld_env(monkeypatch):
    monkeypatch.setenv("VWORLD_API_KEY", "test-key")
    monkeypatch.setenv("SERVICE_URL", "http://localhost:8000")


# ─── 응답 픽스처 헬퍼 ────────────────────────────────────────────────────────

def _geocode_resp(status: str = "OK", x: str = "126.9784", y: str = "37.5660",
                  text: str = "서울특별시 영등포구 여의대로 24") -> dict:
    if status != "OK":
        return {"response": {"status": status}}
    return {
        "response": {
            "status": "OK",
            "result": {
                "point": {"x": x, "y": y},
                "refined": {"text": text},
            },
        }
    }


def _data_resp(features: list, status: str = "OK") -> dict:
    if status != "OK":
        return {"response": {"status": status}}
    return {
        "response": {
            "status": "OK",
            "result": {"featureCollection": {"features": features}},
        }
    }


# ─── geocode ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_geocode_road_success():
    async with respx.mock:
        respx.get("https://api.vworld.kr/req/address").mock(
            return_value=httpx.Response(200, json=_geocode_resp())
        )
        client = VWorldClient()
        result = await client.geocode("서울특별시 영등포구 여의대로 24")
        await client.close()

    assert result is not None
    assert abs(result["lon"] - 126.9784) < 0.001
    assert abs(result["lat"] - 37.5660) < 0.001
    assert "영등포" in result["refined_address"]


@pytest.mark.asyncio
async def test_geocode_parcel_fallback():
    """도로명 실패 → 지번 재시도 성공 케이스."""
    def _side_effect(request: httpx.Request) -> httpx.Response:
        if "type=road" in str(request.url):
            return httpx.Response(200, json=_geocode_resp(status="ERROR"))
        return httpx.Response(200, json=_geocode_resp())

    async with respx.mock:
        respx.get("https://api.vworld.kr/req/address").mock(side_effect=_side_effect)
        client = VWorldClient()
        result = await client.geocode("서울특별시 영등포구 여의대로 24")
        await client.close()

    assert result is not None
    assert abs(result["lon"] - 126.9784) < 0.001


@pytest.mark.asyncio
async def test_geocode_both_fail():
    """도로명·지번 모두 실패 → None 반환."""
    async with respx.mock:
        respx.get("https://api.vworld.kr/req/address").mock(
            return_value=httpx.Response(200, json=_geocode_resp(status="ERROR"))
        )
        client = VWorldClient()
        result = await client.geocode("없는주소")
        await client.close()

    assert result is None


@pytest.mark.asyncio
async def test_geocode_no_key(monkeypatch):
    """API 키 없으면 HTTP 호출 없이 None 반환."""
    monkeypatch.delenv("VWORLD_API_KEY", raising=False)
    async with respx.mock:
        client = VWorldClient()
        result = await client.geocode("서울")
        call_count = respx.calls.call_count
        await client.close()

    assert result is None
    assert call_count == 0


@pytest.mark.asyncio
async def test_geocode_http_error():
    """HTTP 5xx → None 반환 (http_retry 소진 후)."""
    async with respx.mock:
        respx.get("https://api.vworld.kr/req/address").mock(
            return_value=httpx.Response(503)
        )
        client = VWorldClient()
        result = await client.geocode("서울")
        await client.close()

    assert result is None


# ─── get_land_use ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_land_use_zone_and_district():
    features = [
        {"properties": {"uname": "제2종일반주거지역"}},
        {"properties": {"uname": "지구단위계획구역"}},
    ]
    async with respx.mock:
        respx.get("https://api.vworld.kr/req/data").mock(
            return_value=httpx.Response(200, json=_data_resp(features))
        )
        client = VWorldClient()
        result = await client.get_land_use(126.97, 37.56)
        await client.close()

    assert result["zone_use"] == "제2종일반주거지역"
    assert "지구단위계획구역" in result["zone_district"]
    assert result["zone_area"] == ""


@pytest.mark.asyncio
async def test_get_land_use_zone_area():
    """개발제한구역은 zone_area 에 분류되어야 한다."""
    features = [
        {"properties": {"uname": "개발제한구역"}},
        {"properties": {"uname": "일반상업지역"}},
    ]
    async with respx.mock:
        respx.get("https://api.vworld.kr/req/data").mock(
            return_value=httpx.Response(200, json=_data_resp(features))
        )
        client = VWorldClient()
        result = await client.get_land_use(126.97, 37.56)
        await client.close()

    assert "개발제한구역" in result["zone_area"]
    assert result["zone_use"] == "일반상업지역"


@pytest.mark.asyncio
async def test_get_land_use_empty_features():
    async with respx.mock:
        respx.get("https://api.vworld.kr/req/data").mock(
            return_value=httpx.Response(200, json=_data_resp([]))
        )
        client = VWorldClient()
        result = await client.get_land_use(126.97, 37.56)
        await client.close()

    assert result == {}


@pytest.mark.asyncio
async def test_get_land_use_api_error():
    """응답 status != OK → {} 반환."""
    async with respx.mock:
        respx.get("https://api.vworld.kr/req/data").mock(
            return_value=httpx.Response(200, json=_data_resp([], status="ERROR"))
        )
        client = VWorldClient()
        result = await client.get_land_use(126.97, 37.56)
        await client.close()

    assert result == {}


# ─── get_road_width ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_road_width_success():
    features = [{"properties": {"wdth": "12.0"}}]
    async with respx.mock:
        respx.get("https://api.vworld.kr/req/data").mock(
            return_value=httpx.Response(200, json=_data_resp(features))
        )
        client = VWorldClient()
        result = await client.get_road_width(126.97, 37.56)
        await client.close()

    assert result is not None
    assert result["road_width_m"] == 12.0
    assert result["source"] == "VWorld"
    assert result["candidate_count"] == 1


@pytest.mark.asyncio
async def test_get_road_width_no_features():
    async with respx.mock:
        respx.get("https://api.vworld.kr/req/data").mock(
            return_value=httpx.Response(200, json=_data_resp([]))
        )
        client = VWorldClient()
        result = await client.get_road_width(126.97, 37.56)
        await client.close()

    assert result is None


@pytest.mark.asyncio
async def test_get_road_width_no_width_field():
    """features 있지만 폭 속성 없음 → None."""
    features = [{"properties": {"road_id": "12345"}}]
    async with respx.mock:
        respx.get("https://api.vworld.kr/req/data").mock(
            return_value=httpx.Response(200, json=_data_resp(features))
        )
        client = VWorldClient()
        result = await client.get_road_width(126.97, 37.56)
        await client.close()

    assert result is None


# ─── get_land_info ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_land_info_success():
    features = [
        {
            "properties": {
                "pblntfPclnd": "5000000",
                "lndcgr": "대",
                "lndpclAr": "350.5",
            }
        }
    ]
    async with respx.mock:
        respx.get("https://api.vworld.kr/req/data").mock(
            return_value=httpx.Response(200, json=_data_resp(features))
        )
        client = VWorldClient()
        result = await client.get_land_info("1168011700100010000")
        await client.close()

    assert result["official_price"] == 5000000
    assert result["land_category"] == "대"
    assert abs(result["area"] - 350.5) < 0.01


@pytest.mark.asyncio
async def test_get_land_info_invalid_pnu():
    """PNU 19자리 아님 → HTTP 호출 없이 {} 반환."""
    async with respx.mock:
        client = VWorldClient()
        result = await client.get_land_info("12345")
        call_count = respx.calls.call_count
        await client.close()

    assert result == {}
    assert call_count == 0


# ─── get_parcel_polygon ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_parcel_polygon_success():
    geom = {"type": "Polygon", "coordinates": [[[126.97, 37.56], [126.98, 37.56],
                                                  [126.97, 37.57], [126.97, 37.56]]]}
    features = [{"geometry": geom, "properties": {"pnu": "1168011700100010000"}}]
    async with respx.mock:
        respx.get("https://api.vworld.kr/req/data").mock(
            return_value=httpx.Response(200, json=_data_resp(features))
        )
        client = VWorldClient()
        result = await client.get_parcel_polygon(126.97, 37.56)
        await client.close()

    assert result is not None
    assert result["geometry"]["type"] == "Polygon"
    assert result["properties"]["pnu"] == "1168011700100010000"


@pytest.mark.asyncio
async def test_get_parcel_polygon_not_found():
    async with respx.mock:
        respx.get("https://api.vworld.kr/req/data").mock(
            return_value=httpx.Response(200, json=_data_resp([]))
        )
        client = VWorldClient()
        result = await client.get_parcel_polygon(126.97, 37.56)
        await client.close()

    assert result is None


# ─── get_district_unit_plans (lt_c_upisuq161, WFS) ────────────────────────────

def _wfs_resp(features: list) -> dict:
    return {"type": "FeatureCollection", "features": features}


@pytest.mark.asyncio
async def test_get_district_unit_plans_success():
    geom = {"type": "Polygon", "coordinates": [[[126.97, 37.56], [126.99, 37.56],
                                                 [126.99, 37.58], [126.97, 37.58],
                                                 [126.97, 37.56]]]}
    features = [{"geometry": geom, "properties": {"dgm_nm": "운현궁주변 지구단위계획구역",
                                                  "wtnnc_sn": "11000UTZ..."}}]
    async with respx.mock:
        respx.get("https://api.vworld.kr/req/wfs").mock(
            return_value=httpx.Response(200, json=_wfs_resp(features))
        )
        client = VWorldClient()
        result = await client.get_district_unit_plans(126.98, 37.57)
        await client.close()

    assert result is not None
    assert len(result) == 1
    assert result[0]["_uq"] == "UQ161"
    assert result[0]["dgm_nm"] == "운현궁주변 지구단위계획구역"
    assert result[0]["geometry"]["type"] == "Polygon"


@pytest.mark.asyncio
async def test_get_district_unit_plans_empty():
    """구역 없음 → 빈 리스트 (None 아님)."""
    async with respx.mock:
        respx.get("https://api.vworld.kr/req/wfs").mock(
            return_value=httpx.Response(200, json=_wfs_resp([]))
        )
        client = VWorldClient()
        result = await client.get_district_unit_plans(126.98, 37.57)
        await client.close()

    assert result == []


@pytest.mark.asyncio
async def test_get_district_unit_plans_no_key(monkeypatch):
    monkeypatch.delenv("VWORLD_API_KEY", raising=False)
    async with respx.mock:
        client = VWorldClient()
        result = await client.get_district_unit_plans(126.98, 37.57)
        call_count = respx.calls.call_count
        await client.close()

    assert result is None
    assert call_count == 0


@pytest.mark.asyncio
async def test_get_district_unit_plans_layer_error():
    """ServiceException(XML) → JSONDecodeError → None (graceful degrade)."""
    async with respx.mock:
        respx.get("https://api.vworld.kr/req/wfs").mock(
            return_value=httpx.Response(200, text="<ServiceException>err</ServiceException>")
        )
        client = VWorldClient()
        result = await client.get_district_unit_plans(126.98, 37.57)
        await client.close()

    assert result is None
