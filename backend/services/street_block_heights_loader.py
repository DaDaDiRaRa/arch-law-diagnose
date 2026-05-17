"""§60 가로구역별 최고높이 seed 로더.

config/street_block_heights.json → DB. idempotent (같은 jcode + bbox 면 갱신).
운영자가 JSON 에 가로구역을 추가하면 백엔드 재시작 시 자동 반영.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from services.cache_manager import CacheManager

logger = logging.getLogger(__name__)

_SEED_PATH = Path(__file__).parent.parent / "config" / "street_block_heights.json"


async def load_seed_into_db(cache: CacheManager) -> dict:
    if not _SEED_PATH.exists():
        logger.info("street_block_heights.json 없음 — seed 로드 생략")
        return {"loaded": 0}

    with open(_SEED_PATH, encoding="utf-8") as f:
        seed = json.load(f)

    blocks = seed.get("blocks", []) or []
    loaded = 0
    skipped = 0
    for b in blocks:
        try:
            jcode = str(b["jurisdiction_code"]).strip()
            bbox = tuple(float(x) for x in b["bbox"])
            if len(bbox) != 4:
                raise ValueError("bbox 는 [min_lon, min_lat, max_lon, max_lat] 4개 필요")
            max_h = float(b["max_height_m"])
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("street_block_heights seed 행 무시: %s (%s)", b, e)
            skipped += 1
            continue
        await cache.upsert_street_block_height(
            jurisdiction_code=jcode,
            bbox=bbox,
            max_height_m=max_h,
            block_name=b.get("block_name"),
            source=b.get("source"),
            source_url=b.get("source_url"),
            ef_date=b.get("ef_date"),
        )
        loaded += 1

    logger.info("가로구역 최고높이 seed 로드: %d건 적재, %d건 무시", loaded, skipped)
    return {"loaded": loaded, "skipped": skipped, "total": len(blocks)}
