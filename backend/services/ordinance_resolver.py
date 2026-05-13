"""지자체 조례 기반 건폐율/용적률 상한값 결정기.

cascade:
  1. ordinance_zone_limits DB (캐시 히트)
  2. 법제처 API + LLM 추출 → DB 저장
  3. zone_limits.json 시행령 기본값 (최종 fallback)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .cache_manager import CacheManager
    from .law_go_kr_client import LawGoKrClient
    from .ordinance_extractor import OrdinanceExtractor

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "zone_limits.json"
with open(_CONFIG_PATH, encoding="utf-8") as _f:
    _ZONE_LIMITS: dict = json.load(_f)

# 법제처 조례 검색 키워드 (도시계획조례가 건폐율/용적률 포함)
_LAW_KEYWORD = "도시계획 조례"

# jurisdiction_code[:2] → 지역명 매핑 (법제처 API 검색용)
_SIDO_NAME: dict[str, str] = {
    "11": "서울특별시",
    "26": "부산광역시",
    "27": "대구광역시",
    "28": "인천광역시",
    "29": "광주광역시",
    "30": "대전광역시",
    "31": "울산광역시",
    "36": "세종특별자치시",
    "41": "경기도",
    "42": "강원도",
    "43": "충청북도",
    "44": "충청남도",
    "45": "전라북도",
    "46": "전라남도",
    "47": "경상북도",
    "48": "경상남도",
    "50": "제주특별자치도",
}

# 지역명 → 시도 jurisdiction_code (VWorld PNU 없을 때 fallback)
_NAME_TO_SIDO_CODE: dict[str, str] = {v: k + "000" for k, v in _SIDO_NAME.items()}


class OrdinanceResolver:
    def __init__(
        self,
        cache: "CacheManager",
        law_client: "LawGoKrClient",
        extractor: "OrdinanceExtractor",
    ) -> None:
        self._cache = cache
        self._law = law_client
        self._extractor = extractor

    async def resolve(
        self,
        jurisdiction_code: str,
        jurisdiction_name: str | None,
        zone_use: str,
        category: str,
    ) -> dict:
        """
        반환:
          {
            "value": float,
            "source": "조례" | "시행령",
            "source_detail": str,       # 조례명/조문 or "zone_limits.json"
            "is_ordinance": bool,
            "needs_review": bool,
          }
        """
        # VWorld WFS 실패 등으로 PNU 없을 때: jurisdiction_name으로 시도 코드 유도
        if not jurisdiction_code and jurisdiction_name:
            jurisdiction_code = _NAME_TO_SIDO_CODE.get(jurisdiction_name, "")
            if jurisdiction_code:
                logger.debug("jurisdiction_name으로 코드 유도: %s → %s", jurisdiction_name, jurisdiction_code)

        if not jurisdiction_code or not zone_use:
            return self._fallback(zone_use, category, "jurisdiction_code 없음")

        # ── 1단계: DB 캐시 (시군구 정확 매칭) ────────────────────────
        row = await self._cache.get_zone_limit(jurisdiction_code, zone_use, category)
        if row is not None:
            logger.debug("조례 DB 히트(시군구): %s %s %s = %.1f%%", jurisdiction_code, zone_use, category, row["value"])
            return {
                "value": row["value"],
                "source": "조례",
                "source_detail": row.get("source_article") or "DB 캐시",
                "is_ordinance": True,
                "needs_review": bool(row.get("needs_review")),
            }

        # ── 1-b단계: DB 캐시 (시도 레벨 — seed로 저장된 광역시 조례) ──
        sido_code = jurisdiction_code[:2] + "000"
        if sido_code != jurisdiction_code:
            row = await self._cache.get_zone_limit(sido_code, zone_use, category)
            if row is not None:
                logger.debug("조례 DB 히트(시도): %s %s %s = %.1f%%", sido_code, zone_use, category, row["value"])
                return {
                    "value": row["value"],
                    "source": "조례",
                    "source_detail": row.get("source_article") or f"DB 캐시 ({sido_code})",
                    "is_ordinance": True,
                    "needs_review": bool(row.get("needs_review")),
                }

        # ── 2단계: 법제처 API + 추출 ─────────────────────────────────
        extracted = await self._fetch_and_extract(
            jurisdiction_code, jurisdiction_name, zone_use, category
        )
        if extracted is not None:
            await self._cache.set_zone_limit(
                jurisdiction_code=jurisdiction_code,
                jurisdiction_name=jurisdiction_name,
                zone_use=zone_use,
                category=category,
                value=extracted["value"],
                source_article=extracted.get("source_article"),
                needs_review=extracted.get("needs_review", False),
            )
            return {
                "value": extracted["value"],
                "source": "조례",
                "source_detail": extracted.get("source_article", ""),
                "is_ordinance": True,
                "needs_review": extracted.get("needs_review", False),
            }

        # ── 3단계: JSON fallback ──────────────────────────────────────
        return self._fallback(zone_use, category, "조례 미조회")

    # ── 내부 ──────────────────────────────────────────────────────────────

    async def _fetch_and_extract(
        self,
        jurisdiction_code: str,
        jurisdiction_name: str | None,
        zone_use: str,
        category: str,
    ) -> dict | None:
        region = jurisdiction_name or _SIDO_NAME.get(jurisdiction_code[:2], "")
        if not region:
            logger.debug("sido 매핑 없음: %s", jurisdiction_code)
            return None

        try:
            articles = await self._law.fetch_ordinance(region, _LAW_KEYWORD)
        except Exception as e:
            logger.warning("법제처 API 오류 (%s): %s", region, e)
            return None

        if not articles:
            logger.debug("법제처 조례 없음: %s", region)
            return None

        try:
            result = await self._extractor.extract(articles, zone_use, category)
        except Exception as e:
            logger.warning("조례 추출 오류: %s", e)
            return None

        return result

    def _fallback(self, zone_use: str, category: str, reason: str) -> dict:
        baseline_map: dict = _ZONE_LIMITS.get(category, {})
        value = baseline_map.get(zone_use)
        if value is None:
            logger.debug("zone_limits.json에도 없음: %s %s", zone_use, category)
            return {
                "value": None,
                "source": "시행령",
                "source_detail": "미정 — 별도 확인 필요",
                "is_ordinance": False,
                "needs_review": True,
            }
        logger.debug("시행령 fallback (%s): %s %s = %.1f%%", reason, zone_use, category, value)
        return {
            "value": value,
            "source": "시행령",
            "source_detail": "국토계획법 시행령 별표 (zone_limits.json)",
            "is_ordinance": False,
            "needs_review": False,
        }
