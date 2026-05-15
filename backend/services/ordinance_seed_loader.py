"""조례 seed 로더 — 시작 시 ordinance_seed.json 을 DB에 idempotent 적재.

기존 동일 (jurisdiction_code, zone_use, category) row 가 있으면 건너뛴다
(법제처 API 추출값을 보호). seed 의 source_article 에 'seed:' 접두사를 붙여
나중에 추출된 값과 구분 가능.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from services.cache_manager import CacheManager
from services.zone_use_normalizer import normalize as normalize_zone

logger = logging.getLogger(__name__)

_SEED_PATH = Path(__file__).parent.parent / "config" / "ordinance_seed.json"


async def load_seed_into_db(cache: CacheManager) -> dict:
    """seed JSON → DB. 이미 있는 항목은 건너뛴다.

    Returns:
      {"inserted": int, "skipped": int, "jurisdictions": [...]}
    """
    if not _SEED_PATH.exists():
        logger.info("ordinance_seed.json 없음 — seed 로드 생략")
        return {"inserted": 0, "skipped": 0, "jurisdictions": []}

    with open(_SEED_PATH, encoding="utf-8") as f:
        seed = json.load(f)

    inserted = 0
    updated = 0
    skipped = 0
    jurisdictions = []

    for jur in seed.get("jurisdictions", []):
        code = jur["code"]
        name = jur["name"]
        source = jur.get("source", "")
        estimate_cats = set(jur.get("estimate_categories", []))
        cat_sources: dict = jur.get("category_sources", {})

        for category, zone_map in jur.get("limits", {}).items():
            is_estimate = category in estimate_cats
            cat_source = cat_sources.get(category, source)
            source_article = f"seed: {cat_source}"

            for zone_use, value in zone_map.items():
                if value is None:
                    continue
                # 표준명 검증
                canonical = normalize_zone(zone_use)
                if canonical != zone_use:
                    logger.warning(
                        "seed 비표준 용도지역명 '%s' (%s) — 정규화: %s",
                        zone_use, name, canonical,
                    )
                    if canonical is None:
                        continue
                    zone_use = canonical

                existing = await cache.get_zone_limit(code, zone_use, category)
                if existing is not None:
                    # 기존 row가 추출값이면 (source가 'seed:'로 시작 안함) 절대 덮어쓰지 않음
                    existing_src = (existing.get("source_article") or "").strip()
                    if not existing_src.startswith("seed:"):
                        skipped += 1
                        continue
                    # seed 출처 row면 메타(is_estimate / source_article)가 바뀐 경우만 갱신
                    same_estimate = bool(existing.get("is_estimate")) == is_estimate
                    same_source = existing_src == source_article
                    same_value = float(existing.get("value", 0)) == float(value)
                    if same_estimate and same_source and same_value:
                        skipped += 1
                        continue
                    await cache.set_zone_limit(
                        jurisdiction_code=code,
                        jurisdiction_name=name,
                        zone_use=zone_use,
                        category=category,
                        value=float(value),
                        source_article=source_article,
                        needs_review=False,
                        is_estimate=is_estimate,
                    )
                    updated += 1
                    continue

                await cache.set_zone_limit(
                    jurisdiction_code=code,
                    jurisdiction_name=name,
                    zone_use=zone_use,
                    category=category,
                    value=float(value),
                    source_article=source_article,
                    needs_review=False,
                    is_estimate=is_estimate,
                )
                inserted += 1
        jurisdictions.append(name)

    logger.info(
        "조례 seed 로드 완료: %d개 지자체, 신규 %d건, 메타 갱신 %d건, 보존 %d건",
        len(jurisdictions), inserted, updated, skipped,
    )
    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "jurisdictions": jurisdictions,
    }
