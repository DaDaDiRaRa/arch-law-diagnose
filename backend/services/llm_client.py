"""Claude API 클라이언트 — 정성 항목 판단용.

원칙:
- temperature=0 (재현성)
- 시스템 프롬프트는 prompt caching (ephemeral) 으로 반복 호출 비용 절감
- 응답은 strict JSON 으로 강제, 파싱 실패 시 None 반환
"""
from __future__ import annotations

import json
import logging
import os
import re

from anthropic import APIError, AsyncAnthropic

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-sonnet-4-5"
_DEFAULT_MAX_TOKENS = 2048

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


class LLMClient:
    """Anthropic SDK 래퍼. API 키 없으면 available=False 로 graceful degrade."""

    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key or api_key.startswith("sk-ant-..."):
            logger.warning("ANTHROPIC_API_KEY 미설정 — AI 판단 항목 비활성화")
            self._client: AsyncAnthropic | None = None
        else:
            self._client = AsyncAnthropic(api_key=api_key)
        self._model = os.environ.get("ANTHROPIC_MODEL", _DEFAULT_MODEL)

    @property
    def available(self) -> bool:
        return self._client is not None

    @property
    def model(self) -> str:
        return self._model

    async def judge_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> dict | None:
        """system + user → JSON dict. 실패 시 None."""
        if self._client is None:
            return None

        try:
            resp = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=0,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_prompt}],
            )
        except APIError as e:
            logger.warning("Claude API 오류: %s", e)
            return None
        except Exception as e:
            logger.exception("Claude API 예외: %s", e)
            return None

        text = "".join(getattr(b, "text", "") for b in resp.content)
        return _extract_json(text)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()


def _extract_json(text: str) -> dict | None:
    """모델 응답에서 JSON 추출. ```json fence 우선, 없으면 첫 {...} 블록."""
    m = _JSON_FENCE_RE.search(text)
    candidate: str | None = m.group(1) if m else None
    if candidate is None:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            candidate = text[start : end + 1]
    if candidate is None:
        logger.warning("LLM 응답에서 JSON 블록을 찾지 못함")
        return None
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        logger.warning("LLM JSON 파싱 실패: %s", e)
        return None
