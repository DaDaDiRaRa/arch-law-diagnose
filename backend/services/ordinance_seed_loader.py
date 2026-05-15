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
    skipped = 0
    jurisdictions = []

    for jur in seed.get("jurisdictions", []):
        code = jur["code"]
        name = jur["name"]
        source = jur.get("source", "")
        for category, zone_map in jur.get("limits", {}).items():
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

                # 기존 row 확인 — 있으면 건너뛰기 (추출값 보호)
                existing = await cache.get_zone_limit(code, zone_use, category)
                if existing is not None:
                    skipped += 1
                    continue

                await cache.set_zone_limit(
                    jurisdiction_code=code,
                    jurisdiction_name=name,
                    zone_use=zone_use,
                    category=category,
                    value=float(value),
                    source_article=f"seed: {source}",
                    needs_review=False,
                )
                inserted += 1
        jurisdictions.append(name)

    logger.info(
        "조례 seed 로드 완료: %d개 지자체, %d건 신규 삽입, %d건 기존값 보존",
        len(jurisdictions), inserted, skipped,
    )
    return {"inserted": inserted, "skipped": skipped, "jurisdictions": jurisdictions}
