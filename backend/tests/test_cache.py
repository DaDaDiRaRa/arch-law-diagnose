"""CacheManager 회귀 테스트 — 임시 SQLite 파일 사용(외부 의존 없음).

2026-06-26 수정: EUM 행위제한 캐시가 빈 list([])를 None으로 뭉개지 않고
그대로 보존해야 한다(LURIS 캐시와 일관). docstring("info=None / 빈 list도 캐싱")과 일치.
"""
from __future__ import annotations

import pytest

from services import cache_manager as cm


@pytest.fixture
async def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cm, "DB_PATH", str(tmp_path / "test.db"))
    c = cm.CacheManager()
    await c.init()
    yield c
    await c._db.close()


async def test_eum_empty_list_preserved(cache):
    """빈 list 저장 → 조회 시 (hit=True, [])로 복원(None으로 뭉개지지 않음)."""
    await cache.set_eum_act_restriction("11560", "u1", "준공업지역", [])
    hit, data = await cache.get_eum_act_restriction("11560", "u1", "준공업지역")
    assert hit is True
    assert data == []


async def test_eum_none_cached_as_hit(cache):
    """None 저장 → 조회 시 (hit=True, None) — '빈 응답 캐싱됨' 시맨틱 유지."""
    await cache.set_eum_act_restriction("11560", "u2", "준공업지역", None)
    hit, data = await cache.get_eum_act_restriction("11560", "u2", "준공업지역")
    assert hit is True
    assert data is None


async def test_eum_nonempty_roundtrip(cache):
    items = [{"act": "건폐율", "limit": 60}]
    await cache.set_eum_act_restriction("11560", "u3", "준공업지역", items)
    hit, data = await cache.get_eum_act_restriction("11560", "u3", "준공업지역")
    assert hit is True
    assert data == items


async def test_eum_cache_miss(cache):
    hit, data = await cache.get_eum_act_restriction("99999", "zzz", "없음")
    assert hit is False
    assert data is None
