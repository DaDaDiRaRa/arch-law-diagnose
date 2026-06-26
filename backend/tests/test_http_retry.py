"""request_with_retry 회귀 테스트 — 2026-06-26 외부 API 재시도/백오프.

전송오류·5xx만 재시도, 4xx·정상은 즉시 반환, 모두 실패하면 마지막 예외 raise.
base_delay=0으로 실제 대기 없이 검증.
"""
from __future__ import annotations

import httpx
import pytest

from services.http_retry import request_with_retry


class FakeHttp:
    """behaviors: [('raise', exc) | ('status', code), ...] 순서대로 응답."""

    def __init__(self, behaviors):
        self.behaviors = list(behaviors)
        self.calls = 0

    async def request(self, method, url, **kwargs):
        b = self.behaviors[self.calls]
        self.calls += 1
        if b[0] == "raise":
            raise b[1]
        return httpx.Response(b[1], request=httpx.Request(method, url))


async def test_success_no_retry():
    http = FakeHttp([("status", 200)])
    r = await request_with_retry(http, "GET", "http://x", base_delay=0)
    assert r.status_code == 200
    assert http.calls == 1


async def test_retry_on_timeout_then_success():
    http = FakeHttp([("raise", httpx.TimeoutException("t")), ("status", 200)])
    r = await request_with_retry(http, "GET", "http://x", base_delay=0)
    assert r.status_code == 200
    assert http.calls == 2


async def test_retry_on_5xx_then_success():
    http = FakeHttp([("status", 500), ("status", 200)])
    r = await request_with_retry(http, "GET", "http://x", base_delay=0)
    assert r.status_code == 200
    assert http.calls == 2


async def test_exhausts_and_raises_last_exception():
    http = FakeHttp([("raise", httpx.ConnectError("c"))] * 3)
    with pytest.raises(httpx.TransportError):
        await request_with_retry(http, "GET", "http://x", retries=2, base_delay=0)
    assert http.calls == 3  # 최초 + 재시도 2


async def test_5xx_exhausted_returns_last_response():
    http = FakeHttp([("status", 503)] * 3)
    r = await request_with_retry(http, "GET", "http://x", retries=2, base_delay=0)
    assert r.status_code == 503  # 호출부가 raise_for_status로 처리
    assert http.calls == 3


async def test_4xx_not_retried():
    http = FakeHttp([("status", 404)])
    r = await request_with_retry(http, "GET", "http://x", base_delay=0)
    assert r.status_code == 404
    assert http.calls == 1


async def test_non_retryable_exception_propagates_immediately():
    http = FakeHttp([("raise", ValueError("boom"))])
    with pytest.raises(ValueError):
        await request_with_retry(http, "GET", "http://x", base_delay=0)
    assert http.calls == 1
