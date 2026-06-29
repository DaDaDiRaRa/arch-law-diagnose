"""HeritageClient 오프라인 모킹 테스트 (respx).

국가유산 공간정보 Open API(spca.do)를 모킹해 좌표 수확·UTM-K 거리 계산·
캐시·graceful degrade 동작을 네트워크 없이 검증한다.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from services.heritage_client import HeritageClient

_SPCA = "https://gis-heritage.go.kr/openapi/xmlService/spca.do"

# 흥인지문 UTM-K(EPSG:5179) 좌표 = WGS84 약 (127.0096, 37.5712)
_HEUNGIN_X = 956694.35
_HEUNGIN_Y = 1952535.60


def _spca_xml(rows: list[dict]) -> str:
    """spca.do 응답 XML 생성. rows: [{name, x, y}]."""
    body = "".join(
        f"<spca><ccbaMnm>{r['name']}</ccbaMnm>"
        f"<cnX>{r['x']}</cnX><cnY>{r['y']}</cnY></spca>"
        for r in rows
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<ns2:response xmlns:ns2="http://gis-heritage.go.kr/">'
        f"{body}</ns2:response>"
    )


def _mock_all(rows_by_code: dict | None = None, *, fail: bool = False):
    """6개 종목 엔드포인트 모킹. 기본은 보물(12)에만 흥인지문 1건."""
    if fail:
        respx.get(_SPCA).mock(return_value=httpx.Response(500))
        return
    default_rows = rows_by_code or {
        "12": [{"name": "서울 흥인지문", "x": _HEUNGIN_X, "y": _HEUNGIN_Y}],
    }

    def _side_effect(request: httpx.Request) -> httpx.Response:
        code = request.url.params.get("ccbaKdcd", "")
        rows = default_rows.get(code, [])
        return httpx.Response(200, text=_spca_xml(rows))

    respx.get(_SPCA).mock(side_effect=_side_effect)


@pytest.mark.asyncio
async def test_nearby_found_with_distance():
    """문화재 좌표 바로 옆 질의 → 반경 내, 거리 작게."""
    async with respx.mock:
        _mock_all()
        c = HeritageClient()
        hits = await c.find_nearby_heritages(127.0096, 37.5712, radius_m=500)
        await c.close()

    assert hits is not None
    assert len(hits) == 1
    assert hits[0]["name"] == "서울 흥인지문"
    assert hits[0]["heritage_type"] == "보물"
    assert hits[0]["distance_m"] < 100  # 본인 좌표 근방


@pytest.mark.asyncio
async def test_outside_radius_returns_empty():
    """반경 밖(먼 좌표) 질의 → 빈 리스트(수확 성공·근접 없음)."""
    async with respx.mock:
        _mock_all()
        c = HeritageClient()
        hits = await c.find_nearby_heritages(128.5, 37.8, radius_m=500)
        await c.close()

    assert hits == []


@pytest.mark.asyncio
async def test_radius_filtering():
    """반경을 좁히면 경계 밖 문화재가 빠진다 (약 300m 떨어진 항목)."""
    rows = {
        "12": [
            {"name": "가까운보물", "x": _HEUNGIN_X, "y": _HEUNGIN_Y},
            {"name": "300m보물", "x": _HEUNGIN_X + 300, "y": _HEUNGIN_Y},
        ],
    }
    async with respx.mock:
        _mock_all(rows)
        c = HeritageClient()
        wide = await c.find_nearby_heritages(127.0096, 37.5712, radius_m=500)
        narrow = await c.find_nearby_heritages(127.0096, 37.5712, radius_m=100)
        await c.close()

    assert {h["name"] for h in wide} == {"가까운보물", "300m보물"}
    assert {h["name"] for h in narrow} == {"가까운보물"}
    # 가까운 순 정렬
    assert wide[0]["name"] == "가까운보물"


@pytest.mark.asyncio
async def test_all_fetch_fail_degrades_to_none():
    """6개 종목 전부 실패 → None (degrade 신호)."""
    async with respx.mock:
        _mock_all(fail=True)
        c = HeritageClient()
        hits = await c.find_nearby_heritages(127.0096, 37.5712)
        await c.close()

    assert hits is None


@pytest.mark.asyncio
async def test_cache_reused_across_calls():
    """첫 호출에서 수확 후 캐시 — 2번째 호출은 추가 네트워크 없음."""
    async with respx.mock:
        route = respx.get(_SPCA).mock(
            side_effect=lambda req: httpx.Response(
                200,
                text=_spca_xml(
                    [{"name": "서울 흥인지문", "x": _HEUNGIN_X, "y": _HEUNGIN_Y}]
                    if req.url.params.get("ccbaKdcd") == "12" else []
                ),
            )
        )
        c = HeritageClient()
        await c.find_nearby_heritages(127.0096, 37.5712)
        calls_after_first = route.call_count
        await c.find_nearby_heritages(127.0096, 37.5712, radius_m=200)
        calls_after_second = route.call_count
        await c.close()

    # 6개 종목 1회씩만 호출, 2번째 진단은 호출 증가 없음
    assert calls_after_first == 6
    assert calls_after_second == 6
