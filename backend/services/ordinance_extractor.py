"""조례 본문 텍스트 → (zone_use, category, value, source_article) 추출기.

전략:
  1. regex: zone_use가 포함된 줄 자체에서 값 추출 + category 조문 문맥 확인
  2. LLM: regex 실패 시 fallback
  sanity check: 시행령 기본값 ±1.5배 초과 시 needs_review=True
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .llm_client import LLMClient

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "zone_limits.json"
with open(_CONFIG_PATH, encoding="utf-8") as _f:
    _ZONE_LIMITS: dict = json.load(_f)

SANITY_FACTOR = 1.5

_CATEGORY_KW = {
    "building_coverage_ratio": ["건폐율"],
    "floor_area_ratio": ["용적률"],
}

# 한글 숫자 단위 변환
_KR_UNIT = {"천": 1000, "백": 100}

_PCT_IN_LINE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:천|백)?\s*(?:%|퍼센트|퍼\s*센트)"
    r"|100\s*분\s*의\s*(\d+(?:\.\d+)?)"
)


def _parse_value(text: str) -> float | None:
    """한 줄 텍스트에서 첫 번째 % / 퍼센트 / 100분의 N 값을 추출."""
    # "1천퍼센트" 같은 한글 단위 처리
    kr = re.search(r"(\d+)\s*(천|백)\s*퍼센트", text)
    if kr:
        return float(kr.group(1)) * _KR_UNIT[kr.group(2)]

    m = _PCT_IN_LINE.search(text)
    if m:
        return float(m.group(1) or m.group(2))
    return None


def _sanity_ok(value: float, category: str, zone_use: str) -> bool:
    baseline = _ZONE_LIMITS.get(category, {}).get(zone_use)
    if baseline is None:
        return True
    return (baseline / SANITY_FACTOR) <= value <= (baseline * SANITY_FACTOR)


def _combined(articles: list[dict]) -> str:
    return "\n".join(
        f"[{a.get('article_no', '')} {a.get('title', '')}]\n{a.get('content', '')}"
        for a in articles
    )


class OrdinanceExtractor:
    """조례 텍스트에서 건폐율/용적률 수치를 추출한다."""

    def __init__(self, llm: "LLMClient | None" = None) -> None:
        self._llm = llm

    async def extract(
        self,
        articles: list[dict],
        zone_use: str,
        category: str,
    ) -> dict | None:
        kws = _CATEGORY_KW.get(category, [])

        # 1순위: "용도지역 안에서의" / "용도지역별" 주 조문만
        primary = [
            a for a in articles
            if any(kw in a.get("title", "") for kw in kws)
            and ("용도지역 안에서의" in a.get("title", "") or "용도지역별" in a.get("title", ""))
        ]
        # 2순위: category 키워드가 제목에 있는 모든 조문
        secondary = [
            a for a in articles
            if any(kw in a.get("title", "") for kw in kws)
        ]
        # 3순위: 전체
        tiers = [t for t in [primary, secondary, articles] if t]

        for tier in tiers:
            content = _combined(tier)
            result = self._regex_extract(content, zone_use, category)
            if result is not None:
                return result

        # LLM fallback: secondary 조문만 전달
        if self._llm and self._llm.available:
            content = _combined(secondary or articles)
            result = await self._llm_extract(content, zone_use, category)
            if result is not None:
                return result

        return None

    # ── regex ────────────────────────────────────────────────────────────

    def _regex_extract(
        self, content: str, zone_use: str, category: str
    ) -> dict | None:
        kws = _CATEGORY_KW.get(category, [])
        lines = content.splitlines()

        # zone_use가 포함된 줄을 순서대로 탐색
        for i, ln in enumerate(lines):
            if zone_use not in ln:
                continue

            # 해당 줄 자체에서 값 추출 (이전/다음 줄 참조 없이)
            value = _parse_value(ln)
            if value is None:
                continue

            # category 확인: 이 줄보다 앞 최대 30줄에서 category 키워드 검색
            context = "\n".join(lines[max(0, i - 30) : i + 1])
            if not any(kw in context for kw in kws):
                continue

            needs_review = not _sanity_ok(value, category, zone_use)
            source = ln.strip()[:150]
            # 해당 조문 번호/제목을 출처에 포함
            # 앞으로 올라가며 [조문번호 제목] 헤더 탐색
            art_header = ""
            for j in range(i, max(-1, i - 30), -1):
                if lines[j].startswith("[") and "]" in lines[j]:
                    art_header = lines[j].strip()
                    break

            if needs_review:
                logger.warning(
                    "sanity check 실패 — %s %s: %.1f%% (regex)", zone_use, category, value
                )
            return {
                "value": value,
                "source_article": f"{art_header} {source}"[:200].strip(),
                "needs_review": needs_review,
                "method": "regex",
            }

        return None

    # ── LLM fallback ─────────────────────────────────────────────────────

    async def _llm_extract(
        self, content: str, zone_use: str, category: str
    ) -> dict | None:
        kw = _CATEGORY_KW.get(category, [category])[0]
        # category 키워드 근처 조문만 전달
        kws = _CATEGORY_KW.get(category, [])
        lines = content.splitlines()
        cat_lines = [i for i, ln in enumerate(lines) if any(k in ln for k in kws)]
        if cat_lines:
            start = max(0, cat_lines[0] - 2)
            end = min(len(lines), cat_lines[-1] + 50)
            snippet = "\n".join(lines[start:end])[:2000]
        else:
            snippet = content[:2000]

        system = (
            "당신은 한국 건축 법규 전문가입니다. "
            "주어진 조례 조문에서 특정 용도지역의 건폐율 또는 용적률 상한값을 추출합니다. "
            "반드시 JSON 형식으로만 응답하세요."
        )
        user = (
            f"아래 조례 조문에서 [{zone_use}]의 [{kw}] 상한값(%)을 추출하세요.\n\n"
            f"조문:\n{snippet}\n\n"
            "응답 형식 (값을 찾을 수 없으면 null):\n"
            '{"value": 60.0, "source_article": "관련 조문 문구 (50자 이내)"}'
        )

        raw = await self._llm.judge_json(system, user)
        if not raw or raw.get("value") is None:
            return None

        try:
            value = float(raw["value"])
        except (TypeError, ValueError):
            return None

        needs_review = not _sanity_ok(value, category, zone_use)
        if needs_review:
            logger.warning(
                "sanity check 실패 — %s %s: %.1f%% (LLM)", zone_use, category, value
            )
        return {
            "value": value,
            "source_article": str(raw.get("source_article", ""))[:200],
            "needs_review": needs_review,
            "method": "llm",
        }
