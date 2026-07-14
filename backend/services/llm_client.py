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

_DEFAULT_MODEL = "claude-sonnet-4-6"
_DEFAULT_MAX_TOKENS = 4096  # 설비·소방 긴 응답 잘림 방지 (구 2048 → 4096)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
# 객체/배열 사이 콤마 누락 자동 복구용 패턴
_MISSING_COMMA_OBJ = re.compile(r"(\}|\"|true|false|null|\d)\s*\n\s*\{", re.MULTILINE)
_MISSING_COMMA_ARR_END = re.compile(r"(\}|\"|true|false|null|\d)\s*\n\s*\]")
_TRAILING_COMMA = re.compile(r",(\s*[\}\]])")


class LLMClient:
    """Anthropic SDK 래퍼. API 키 없으면 available=False 로 graceful degrade."""

    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key or api_key.startswith("sk-ant-..."):
            logger.warning("ANTHROPIC_API_KEY 미설정 — AI 판단 항목 비활성화")
            self._client: AsyncAnthropic | None = None
        else:
            # 네트워크 장애 시 무한 대기 방지 (다른 httpx 클라이언트와 동일 정책).
            # max_retries=1(SDK 기본 2 → 축소): 설비_소방 카드 하나 때문에 진단
            # 전체가 최악의 경우 30초×3회(≈90초)까지 블로킹되던 걸 30초×2회로 단축.
            # 완전 실패 시 fire_safety._fallback()로 graceful degrade — 동작 불변.
            self._client = AsyncAnthropic(api_key=api_key, timeout=30.0, max_retries=1)
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
    """모델 응답에서 JSON 추출. fence → strict → 자동 복구 순으로 시도."""
    m = _JSON_FENCE_RE.search(text)
    candidate: str | None = m.group(1) if m else None
    if candidate is None:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            candidate = text[start : end + 1]
    if candidate is None:
        logger.warning("LLM 응답에서 JSON 블록을 찾지 못함 — 원본 (앞 500자): %s", text[:500])
        return None

    # strict=False — 문자열 값 안의 리터럴 제어문자(줄바꿈·탭)를 허용.
    # 조문 원문 등 멀티라인 텍스트를 모델이 이스케이프 없이 echo해도 파싱되도록.
    # 1차 — 파싱
    try:
        return json.loads(candidate, strict=False)
    except json.JSONDecodeError as e:
        first_err = e

    # 2차 — 자동 복구 시도 (배열/객체 사이 콤마 누락, trailing 콤마)
    repaired = _MISSING_COMMA_OBJ.sub(r"\1,\n{", candidate)
    repaired = _MISSING_COMMA_ARR_END.sub(r"\1\n]", repaired)
    repaired = _TRAILING_COMMA.sub(r"\1", repaired)
    try:
        result = json.loads(repaired, strict=False)
        logger.info("LLM JSON 자동 복구 성공 (콤마 누락/trailing 보정)")
        return result
    except json.JSONDecodeError as e2:
        # 3차 — 마지막 완전한 } 까지만 잘라서 시도 (응답 truncation 대응)
        if "}" in candidate:
            last_brace = candidate.rfind("}")
            for cut in range(last_brace, 0, -1):
                if candidate[cut] == "}":
                    sub = candidate[: cut + 1]
                    try:
                        result = json.loads(sub, strict=False)
                        logger.info(
                            "LLM JSON 자동 복구 성공 (응답 truncation — %d자 → %d자로 절단)",
                            len(candidate), len(sub),
                        )
                        return result
                    except json.JSONDecodeError:
                        continue
        # 모든 복구 실패 — 원본 일부 + 에러 위치 컨텍스트 로그
        err_pos = getattr(first_err, "pos", 0)
        ctx_start = max(0, err_pos - 100)
        ctx_end = min(len(candidate), err_pos + 100)
        logger.warning(
            "LLM JSON 파싱 실패 (자동 복구도 실패): %s\n  에러 부근: ...%s«HERE»%s...",
            first_err,
            candidate[ctx_start:err_pos],
            candidate[err_pos:ctx_end],
        )
        return None
