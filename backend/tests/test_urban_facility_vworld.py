"""도시계획시설 VWorld WFS 실시간 경로 테스트 (SHP 없이).

- lookup: facilities 인자(VWorld GeoJSON)로 점 저촉/면적 교차 판정 (네트워크 없음)
- vworld_client.get_urban_facilities: WFS GetFeature respx 모킹
"""
from __future__ import annotations

import httpx
import pytest
import respx

from services.urban_facility import (
    check_facility_conflict,
    compute_facility_overlap,
    detect_district_unit,
)
from services.vworld_client import VWorldClient


# 점 (127.005, 37.505)를 포함하는 시설 폴리곤
def _facility(uq="UQ151", name="테스트도로",
              ring=((127.0, 37.5), (127.01, 37.5), (127.01, 37.51), (127.0, 37.51), (127.0, 37.5))):
    return {
        "_uq": uq,
        "geometry": {"type": "Polygon", "coordinates": [[list(p) for p in ring]]},
        "dgm_nm": name,
        "wtnnc_sn": "11000URZ0001",
        "dgm_ar": "1234",
    }


# ─── lookup: 점 저촉 (check_facility_conflict, facilities=) ───────────────────

def test_conflict_point_inside_facility():
    res = check_facility_conflict(lat=37.505, lng=127.005, facilities=[_facility()])
    assert res["checked"] is True
    assert res["severity"] in ("RED", "YELLOW")  # 시설 저촉 → GREEN 아님
    assert res["conflicts"][0]["facility_name"] == "테스트도로"
    assert res["conflicts"][0]["uq_code"] == "UQ151"


def test_conflict_point_outside_facility():
    res = check_facility_conflict(lat=38.0, lng=128.0, facilities=[_facility()])
    assert res["checked"] is True
    assert res["severity"] == "GREEN"
    assert res["conflicts"] == []


def test_conflict_empty_facilities_is_green():
    """VWorld 정상 응답·시설 0건 → GREEN (degrade 아님)."""
    res = check_facility_conflict(lat=37.5, lng=127.0, facilities=[])
    assert res["checked"] is True
    assert res["severity"] == "GREEN"


# ─── lookup: 면적 교차 (compute_facility_overlap, facilities=) ────────────────

def test_overlap_with_facilities():
    parcel = {"type": "Polygon", "coordinates": [[
        [127.004, 37.504], [127.008, 37.504],
        [127.008, 37.508], [127.004, 37.508], [127.004, 37.504],
    ]]}
    res = compute_facility_overlap(parcel_geometry=parcel, facilities=[_facility()])
    assert res["checked"] is True
    assert res["overlap_area_m2"] > 0
    assert res["overlap_ratio"] > 0
    assert res["by_facility"][0]["facility_name"] == "테스트도로"


def test_overlap_no_facilities_is_green():
    parcel = {"type": "Polygon", "coordinates": [[
        [127.0, 37.5], [127.001, 37.5], [127.001, 37.501], [127.0, 37.501], [127.0, 37.5],
    ]]}
    res = compute_facility_overlap(parcel_geometry=parcel, facilities=[])
    assert res["checked"] is True
    assert res["overlap_area_m2"] == 0.0
    assert res["severity"] == "GREEN"


# ─── detect_district_unit (지구단위계획구역 좌표 판정) ────────────────────────

def _district_plan(name="운현궁주변 지구단위계획구역",
                   ring=((127.0, 37.5), (127.01, 37.5), (127.01, 37.51),
                         (127.0, 37.51), (127.0, 37.5))):
    return {
        "_uq": "UQ161",
        "geometry": {"type": "Polygon", "coordinates": [[list(p) for p in ring]]},
        "dgm_nm": name,
    }


def test_district_unit_inside():
    res = detect_district_unit([_district_plan()], lat=37.505, lng=127.005)
    assert res["checked"] is True
    assert res["inside"] is True
    assert res["names"] == ["운현궁주변 지구단위계획구역"]
    assert "지구단위계획구역" in res["note"]


def test_district_unit_outside():
    res = detect_district_unit([_district_plan()], lat=38.0, lng=128.0)
    assert res["checked"] is True
    assert res["inside"] is False
    assert res["names"] == []


def test_district_unit_empty_checked_true():
    """VWorld 정상·구역 0건 → checked True, inside False."""
    res = detect_district_unit([], lat=37.5, lng=127.0)
    assert res["checked"] is True
    assert res["inside"] is False


def test_district_unit_degrade_when_none():
    """조회 실패(None) → checked False (graceful degrade)."""
    res = detect_district_unit(None, lat=37.5, lng=127.0)
    assert res["checked"] is False
    assert res["inside"] is False


def test_district_unit_no_coords():
    res = detect_district_unit([_district_plan()], lat=None, lng=None)
    assert res["checked"] is False
    assert res["inside"] is False


# ─── vworld_client.get_urban_facilities (WFS respx) ──────────────────────────

@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("VWORLD_API_KEY", "test-key")
    monkeypatch.setenv("SERVICE_URL", "http://localhost:8000")


def _wfs_fc(features):
    return {"type": "FeatureCollection", "features": features}


@pytest.mark.asyncio
async def test_get_urban_facilities_parses_wfs():
    feat = {
        "type": "Feature",
        "geometry": {"type": "MultiPolygon", "coordinates": [[[[127.0, 37.5], [127.01, 37.5], [127.01, 37.51], [127.0, 37.5]]]]},
        "properties": {"dgm_nm": "기타도로시설", "dgm_ar": "100", "wtnnc_sn": "X"},
    }
    async with respx.mock:
        respx.get("https://api.vworld.kr/req/wfs").mock(
            return_value=httpx.Response(200, json=_wfs_fc([feat]))
        )
        client = VWorldClient()
        facs = await client.get_urban_facilities(127.0, 37.5)
        await client.close()
    assert facs is not None
    assert len(facs) == 9          # 9개 레이어 × 1 feature
    assert facs[0]["_uq"].startswith("UQ")
    assert facs[0]["dgm_nm"] == "기타도로시설"
    assert facs[0]["geometry"]["type"] == "MultiPolygon"


@pytest.mark.asyncio
async def test_get_urban_facilities_empty_is_not_none():
    """전 레이어 정상·피처 0건 → [] (degrade 아님)."""
    async with respx.mock:
        respx.get("https://api.vworld.kr/req/wfs").mock(
            return_value=httpx.Response(200, json=_wfs_fc([]))
        )
        client = VWorldClient()
        facs = await client.get_urban_facilities(127.0, 37.5)
        await client.close()
    assert facs == []


@pytest.mark.asyncio
async def test_get_urban_facilities_all_fail_returns_none():
    """전 레이어 오류 → None (SHP 폴백 신호)."""
    async with respx.mock:
        respx.get("https://api.vworld.kr/req/wfs").mock(
            return_value=httpx.Response(500, text="error")
        )
        client = VWorldClient()
        facs = await client.get_urban_facilities(127.0, 37.5)
        await client.close()
    assert facs is None


@pytest.mark.asyncio
async def test_get_urban_facilities_no_key(monkeypatch):
    monkeypatch.delenv("VWORLD_API_KEY", raising=False)
    client = VWorldClient()
    facs = await client.get_urban_facilities(127.0, 37.5)
    await client.close()
    assert facs is None
