"""외부 API 공용 재시도/백오프 헬퍼.

정부 API(VWorld·토지이음·LURIS·법제처 등)는 간헐적 timeout·일시 5xx가 잦다.
일시 장애 한 번에 항목이 "확인필요"로 떨어지는 것을 막기 위해, 전송 계층 오류와
5xx에 한해 지수 백오프로 몇 번 재시도한다.

원칙:
- 재시도 대상: 연결/타임아웃 오류(httpx.TransportError·TimeoutException), HTTP 5xx
- 재시도 안 함: 4xx(클라이언트 오류), 정상 응답(데이터 없음 포함) — 즉시 반환
- 모두 실패하면 마지막 예외를 그대로 raise (호출부의 기존 except → graceful degrade 유지)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_RETRYABLE = (httpx.TimeoutException, httpx.TransportError)


async def request_with_retry(
    http: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    retries: int = 2,
    base_delay: float = 0.5,
    **kwargs: Any,
) -> httpx.Response:
    """재시도 포함 HTTP 요청. httpx.Response 반환(호출부가 raise_for_status/파싱).

    Args:
      retries: 최초 시도 외 추가 재시도 횟수(기본 2 → 최대 3회 시도).
      base_delay: 백오프 기준 초. attempt별 base_delay * 2**attempt 만큼 대기.
    """
    for attempt in range(retries + 1):
        try:
            r = await http.request(method, url, **kwargs)
            # 5xx면 재시도(여유 있을 때). 마지막 시도면 그대로 반환 → 호출부가 처리.
            if r.is_server_error and attempt < retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    "[http] %s %s → %d, %.1fs 후 재시도(%d/%d)",
                    method, url, r.status_code, delay, attempt + 1, retries,
                )
                await asyncio.sleep(delay)
                continue
            return r
        except _RETRYABLE as e:
            if attempt >= retries:
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning(
                "[http] %s %s 전송오류(%s), %.1fs 후 재시도(%d/%d)",
                method, url, type(e).__name__, delay, attempt + 1, retries,
            )
            await asyncio.sleep(delay)
