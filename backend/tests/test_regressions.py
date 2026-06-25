"""회귀 테스트 — 2026-06-25 코드 점검에서 발견·수정한 버그 재발 방지.

각 테스트는 수정 전 코드에서 실패(크래시/오답)하고, 수정 후 통과한다.
외부 API 호출 없이 오프라인으로 동작한다(모의 객체 사용).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# 버그 #1: street_block_max_height_m 입력 시 diagnose_engine 의 `lat` UnboundLocalError
#   - 수정 전: lat 이 §60 블록 안에서만 할당되어, 사용자가 가로구역 최고높이를
#     직접 입력하면 railway_protection.calculate(lat=lat) 에서 진단 전체가 500.
#   - 수정 후: lat=land.get("lat") 로 항상 안전하게 참조.
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def _land():
    return {
        "zone_use": "준공업지역",
        "zone_district": "",
        "zone_area": "",
        "land_category": "대",
        "official_price": 5_000_000,
        "lon": 126.8957,
        "lat": 37.5301,
        "pnu": "1156010300103850000",
        "parcel_geometry": None,
        "road_width_auto": 12.0,
        "road_width_source": "VWorld",
        "jurisdiction_code": "11560",
        "jurisdiction_name": "서울특별시",
        "cache_hit": False,
        "cache_age_days": 0,
        "cache_stale": False,
    }


def _req(**extra):
    base = {
        "address": "서울특별시 영등포구 당산동3가 385",
        "building_use": "업무시설",
        "site_area": 1000.0,
        "building_area": 500.0,
        "total_floor_area": 4000.0,
        "floor_area_above": 4000.0,
        "floors_above": 8,
        "height": 32.0,
    }
    base.update(extra)
    return base


@pytest.fixture
def _engine(monkeypatch):
    from services.diagnose_engine import DiagnoseEngine
    from services.calculator import land_use_act, urban_facility

    # 외부 의존 계산기 2종만 중립화 — 나머지(건폐율·용적률·높이·주차·조경 등)는 실제 실행
    async def _fake_land_use(*a, **k):
        return {"pass": None, "score": None, "confidence": 1, "summary": "test", "notes": ""}

    monkeypatch.setattr(land_use_act, "calculate", _fake_land_use)
    monkeypatch.setattr(
        urban_facility, "calculate",
        lambda **k: {"pass": True, "score": 10, "confidence": 3, "summary": "test", "notes": ""},
    )

    resolver = MagicMock()
    cache = MagicMock()
    cache.save_history = AsyncMock()
    cache.lookup_street_block_height = AsyncMock(return_value=None)
    llm = MagicMock()
    llm.available = False
    return DiagnoseEngine(resolver, cache, llm, ordinance_resolver=None, luris=None, eum=None)


async def test_street_block_height_does_not_crash(_engine, _land):
    """가로구역 최고높이를 직접 입력해도 진단이 크래시하지 않는다 (버그 #1)."""
    req = _req(street_block_max_height_m=31.0)
    result = await _engine._diagnose(req, _land, save_history=False, skip_ai=True)
    assert "results" in result
    assert "철도보호지구" in result["results"]
    # §60 입력이 반영되어 높이 판정이 수행됐는지(라벨 존재) 확인
    assert result["results"]["높이_일조"] is not None


async def test_no_street_block_height_still_works(_engine, _land):
    """가로구역 입력이 없을 때도 정상 동작 (회귀 대칭 케이스)."""
    result = await _engine._diagnose(_req(), _land, save_history=False, skip_ai=True)
    assert "results" in result and result.get("signal") in {"RED", "YELLOW", "GREEN"}


# ─────────────────────────────────────────────────────────────────────────────
# 버그 #2: /api/brief/extract 가 항상 500 (judge_json 시그니처 불일치 + await 누락)
# ─────────────────────────────────────────────────────────────────────────────
async def test_brief_parse_awaits_judge_json_correctly():
    """parse_conditions_with_llm 이 judge_json 을 (system, user) 위치인자로 await 한다."""
    from services import brief_extractor as be

    captured = {}

    class FakeLLM:
        async def judge_json(self, system_prompt, user_prompt, *, max_tokens=4096):
            captured["system"] = system_prompt
            captured["user"] = user_prompt
            return {"max_bcr_pct": 60, "max_far_pct": 400, "required_uses": ["업무시설"]}

    result = await be.parse_conditions_with_llm("공모지침 본문 텍스트", FakeLLM())
    assert captured["system"] and "지침서" in captured["system"]
    assert "공모지침 본문 텍스트" in captured["user"]
    assert result["max_bcr_pct"] == 60.0
    assert result["max_far_pct"] == 400.0
    assert result["required_uses"] == ["업무시설"]


async def test_brief_parse_none_response_raises_valueerror():
    """LLM 이 None 을 반환하면(키 없음·파싱 실패) 500 대신 ValueError 로 graceful 처리 (버그 #2)."""
    from services import brief_extractor as be

    class NullLLM:
        async def judge_json(self, *a, **k):
            return None

    with pytest.raises(ValueError):
        await be.parse_conditions_with_llm("텍스트", NullLLM())


def test_brief_extract_from_pdf_is_coroutine():
    """extract_from_pdf 가 async 여야 라우트에서 await 가능 (버그 #2)."""
    import inspect
    from services import brief_extractor as be

    assert inspect.iscoroutinefunction(be.extract_from_pdf)
    assert inspect.iscoroutinefunction(be.parse_conditions_with_llm)


# ─────────────────────────────────────────────────────────────────────────────
# 버그 #5: LURIS 서비스 에러(throttle/quota)를 90일 캐시로 고착시키지 않는다
# ─────────────────────────────────────────────────────────────────────────────
def test_luris_service_error_detection():
    from services.luris_client import _is_service_error

    throttle = (
        "<OpenAPI_ServiceResponse><cmmMsgHeader>"
        "<returnReasonCode>22</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>"
    )
    assert _is_service_error(throttle) is True
    assert _is_service_error("LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR") is True
    # 정상 '데이터 없음' 응답은 서비스 에러가 아님 → 캐시 허용
    assert _is_service_error("<response><item><actRegList/></item></response>") is False


# ─────────────────────────────────────────────────────────────────────────────
# 버그 #6: VWorld get_land_info 가 잘못된 PNU 를 CQL filter 에 보간하지 않는다
# ─────────────────────────────────────────────────────────────────────────────
async def test_vworld_rejects_malformed_pnu():
    from services.vworld_client import VWorldClient

    client = VWorldClient()
    client._key = "dummy-key"  # 키가 있어야 PNU 검증 경로로 진입
    # http 가 호출되면 테스트 실패하도록 설정
    client._http = MagicMock()
    client._http.get = AsyncMock(side_effect=AssertionError("http 가 호출되면 안 됨"))

    assert await client.get_land_info("'; DROP--") == {}
    assert await client.get_land_info("123") == {}          # 19자리 아님
    assert await client.get_land_info("11560103001038500AB") == {}  # 숫자 아님
    client._http.get.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# 버그 #3·#4: land_use_resolver — gather 예외 내성 + 빈 결과 캐시 미오염
# ─────────────────────────────────────────────────────────────────────────────
async def test_resolver_does_not_poison_cache_on_empty(monkeypatch):
    """용도지역 조회 실패 + stale 캐시 없음 → 빈 결과를 캐시에 저장하지 않는다 (버그 #4)."""
    from services.land_use_resolver import LandUseResolver

    vworld = MagicMock()
    vworld.geocode = AsyncMock(return_value={"lon": 126.9, "lat": 37.5})
    vworld.get_land_use = AsyncMock(return_value={})          # 용도지역 없음
    vworld.get_land_info = AsyncMock(return_value={})
    vworld.get_parcel_polygon = AsyncMock(return_value=None)
    vworld.get_road_width = AsyncMock(return_value=None)

    cache = MagicMock()
    cache.get_land_info = AsyncMock(return_value=None)        # 기존 캐시 없음
    cache.set_land_info = AsyncMock()

    resolver = LandUseResolver(vworld, cache)
    result = await resolver.resolve("서울특별시 어딘가", pnu="1156010300103850000")

    assert not result.get("zone_use")           # 빈 결과
    cache.set_land_info.assert_not_called()      # 캐시 오염 없음


async def test_resolver_survives_gather_exception(monkeypatch):
    """병렬 VWorld 호출 중 하나가 예외를 던져도 요청이 크래시하지 않는다 (버그 #3)."""
    from services.land_use_resolver import LandUseResolver

    vworld = MagicMock()
    vworld.geocode = AsyncMock(return_value={"lon": 126.9, "lat": 37.5})
    vworld.get_land_use = AsyncMock(return_value={"zone_use": "준공업지역"})
    vworld.get_land_info = AsyncMock(side_effect=RuntimeError("VWorld 일시 장애"))
    vworld.get_parcel_polygon = AsyncMock(return_value=None)
    vworld.get_road_width = AsyncMock(return_value=None)

    cache = MagicMock()
    cache.get_land_info = AsyncMock(return_value=None)
    cache.set_land_info = AsyncMock()

    resolver = LandUseResolver(vworld, cache)
    # 예외가 전파되면 이 호출이 RuntimeError 로 실패 → 수정 전 동작
    result = await resolver.resolve("서울특별시 어딘가", pnu="1156010300103850000")
    assert result.get("zone_use") == "준공업지역"
