"""OrdinanceResolver — 2단계(첫 조회) needs_review 게이팅 회귀 테스트.

배경: 라이브 진단 실사용 감사(2026-07-01)에서 발견 — 캐시 미스 상태로 법제처
조례를 처음 추출했을 때, sanity check 실패(needs_review=True)로 플래그가
붙어도 그 호출 자체는 값을 그대로 반환하던 버그. 안전장치(needs_review→
시행령 폴백)가 두 번째 조회(캐시 재조회)부터만 작동해 첫 사용자가 검증 안
된 값을 그대로 받았다. CLAUDE.md "④-a" 항목.
"""
import pytest

from services.ordinance_resolver import OrdinanceResolver


class _FakeCache:
    """DB 캐시 미스만 흉내 — 항상 None 반환, set_zone_limit은 기록만."""

    def __init__(self):
        self.saved = []

    async def get_zone_limit(self, jurisdiction_code, zone_use, category):
        return None

    async def set_zone_limit(self, **kwargs):
        self.saved.append(kwargs)


class _FakeLawClient:
    async def fetch_ordinance(self, region, keyword):
        return [{"article": "dummy"}]  # non-empty → extractor 호출됨


class _FakeExtractor:
    def __init__(self, result):
        self._result = result

    async def extract(self, articles, zone_use, category):
        return self._result


@pytest.mark.asyncio
async def test_first_extraction_needs_review_falls_back_to_decree():
    """needs_review=True인 첫 추출값은 사용하지 않고 시행령으로 폴백해야 한다."""
    cache = _FakeCache()
    extractor = _FakeExtractor({
        "value": 800.0,
        "source_article": "8. 일반상업지역: 800퍼센트(단, 서울도심: 600퍼센트)",
        "needs_review": True,
    })
    resolver = OrdinanceResolver(cache, _FakeLawClient(), extractor)

    result = await resolver.resolve(
        jurisdiction_code="11000",
        jurisdiction_name="서울특별시",
        zone_use="일반상업지역",
        category="floor_area_ratio",
    )

    assert result["source"] == "시행령"
    assert result["is_ordinance"] is False
    assert result["value"] != 800.0  # 검증 안 된 조례값을 그대로 쓰지 않음
    # 캐시엔 여전히 기록되어(수동 검토용) 다음 조회 시 재활용 가능해야 한다.
    assert cache.saved and cache.saved[0]["needs_review"] is True


@pytest.mark.asyncio
async def test_first_extraction_clean_value_used_as_ordinance():
    """needs_review=False인 정상 추출값은 기존처럼 조례로 사용해야 한다(회귀 방지)."""
    cache = _FakeCache()
    extractor = _FakeExtractor({
        "value": 60.0,
        "source_article": "8. 일반상업지역: 60퍼센트",
        "needs_review": False,
    })
    resolver = OrdinanceResolver(cache, _FakeLawClient(), extractor)

    result = await resolver.resolve(
        jurisdiction_code="11000",
        jurisdiction_name="서울특별시",
        zone_use="일반상업지역",
        category="building_coverage_ratio",
    )

    assert result["source"] == "조례"
    assert result["is_ordinance"] is True
    assert result["value"] == 60.0
