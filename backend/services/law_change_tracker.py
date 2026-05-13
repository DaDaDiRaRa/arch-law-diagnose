"""법규 변경 모니터링 — SHA256 해시 기반.

`ordinance_versions` 테이블에 누적된 해시를 비교하여 변경 감지.

흐름:
  1. scan(jur, region, keyword) → 법제처 재조회 → cache.set_ordinances() 호출
     (cache_manager가 자동으로 새 해시 row 삽입)
  2. recent_changes() → 같은 (jur, law_type)의 연속 두 버전 해시 비교
     → 다르면 '변경' 이벤트로 반환
"""
from __future__ import annotations

import logging
from datetime import datetime

from services.cache_manager import CacheManager
from services.law_go_kr_client import LawGoKrClient

logger = logging.getLogger(__name__)


_RECENT_CHANGES_SQL = """
WITH ranked AS (
    SELECT
        jurisdiction_code,
        law_type,
        content_hash,
        fetched_at,
        ROW_NUMBER() OVER (
            PARTITION BY jurisdiction_code, law_type
            ORDER BY fetched_at DESC
        ) AS rn
    FROM ordinance_versions
)
SELECT
    cur.jurisdiction_code,
    cur.law_type,
    cur.content_hash AS new_hash,
    cur.fetched_at   AS new_at,
    prev.content_hash AS prev_hash,
    prev.fetched_at   AS prev_at
FROM ranked cur
LEFT JOIN ranked prev
       ON prev.jurisdiction_code = cur.jurisdiction_code
      AND prev.law_type = cur.law_type
      AND prev.rn = 2
WHERE cur.rn = 1
  AND prev.content_hash IS NOT NULL
  AND prev.content_hash != cur.content_hash
ORDER BY cur.fetched_at DESC
LIMIT ?
"""


class LawChangeTracker:
    def __init__(self, cache: CacheManager, law_client: LawGoKrClient) -> None:
        self._cache = cache
        self._law = law_client

    async def recent_changes(
        self,
        limit: int = 20,
        jurisdiction_code: str | None = None,
    ) -> list[dict]:
        """최근 변경 이벤트. jurisdiction_code 지정 시 해당 지역만."""
        rows = await self._cache.query(_RECENT_CHANGES_SQL, (limit * 5,))
        events: list[dict] = []
        for r in rows:
            if jurisdiction_code and r["jurisdiction_code"] != jurisdiction_code:
                continue
            events.append(
                {
                    "jurisdiction_code": r["jurisdiction_code"],
                    "law_type": r["law_type"],
                    "previous_hash": (r["prev_hash"] or "")[:12],
                    "current_hash": (r["new_hash"] or "")[:12],
                    "previous_at": r["prev_at"],
                    "current_at": r["new_at"],
                    "days_since_change": _days_since(r["new_at"]),
                }
            )
            if len(events) >= limit:
                break
        return events

    async def scan(
        self,
        jurisdiction_code: str,
        region_name: str,
        law_keyword: str,
        law_type_label: str = "urban_planning",
    ) -> dict:
        """능동 스캔: 법제처 재조회 → cache 저장 → 변경 여부 반환."""
        # 이전 해시 조회
        prev_rows = await self._cache.query(
            """SELECT content_hash, fetched_at
               FROM ordinance_versions
               WHERE jurisdiction_code=? AND law_type=?
               ORDER BY fetched_at DESC LIMIT 1""",
            (jurisdiction_code, law_type_label),
        )
        prev_hash = prev_rows[0]["content_hash"] if prev_rows else None

        # 법제처 재조회
        articles = await self._law.fetch_ordinance(region_name, law_keyword)
        if not articles:
            return {
                "scanned_at": _now_iso(),
                "jurisdiction_code": jurisdiction_code,
                "law_type": law_type_label,
                "article_count": 0,
                "changed": False,
                "note": "법제처 응답 없음 (API 키 또는 키워드 확인)",
            }

        # 저장 (set_ordinances가 새 버전 row 자동 삽입)
        await self._cache.set_ordinances(jurisdiction_code, law_type_label, articles)

        # 새 해시 조회
        new_rows = await self._cache.query(
            """SELECT content_hash FROM ordinance_versions
               WHERE jurisdiction_code=? AND law_type=?
               ORDER BY fetched_at DESC LIMIT 1""",
            (jurisdiction_code, law_type_label),
        )
        new_hash = new_rows[0]["content_hash"] if new_rows else None
        changed = bool(prev_hash and new_hash and prev_hash != new_hash)

        return {
            "scanned_at": _now_iso(),
            "jurisdiction_code": jurisdiction_code,
            "law_type": law_type_label,
            "article_count": len(articles),
            "previous_hash": (prev_hash or "")[:12],
            "current_hash": (new_hash or "")[:12],
            "changed": changed,
            "note": "변경 감지" if changed else ("초기 수집" if not prev_hash else "변경 없음"),
        }

    async def seed_demo_change(
        self,
        jurisdiction_code: str = "11560",
        law_type: str = "urban_planning",
    ) -> dict:
        """데모용 — 가짜 변경 이벤트 2건(prev/curr) 강제 삽입."""
        import hashlib
        now = _now_iso()
        old_hash = hashlib.sha256(f"{jurisdiction_code}-old".encode()).hexdigest()
        new_hash = hashlib.sha256(f"{jurisdiction_code}-{now}".encode()).hexdigest()
        await self._cache.execute(
            "INSERT INTO ordinance_versions (jurisdiction_code, law_type, content_hash, fetched_at) VALUES (?,?,?,?)",
            (jurisdiction_code, law_type, old_hash, "2026-01-01T00:00:00"),
        )
        await self._cache.execute(
            "INSERT INTO ordinance_versions (jurisdiction_code, law_type, content_hash, fetched_at) VALUES (?,?,?,?)",
            (jurisdiction_code, law_type, new_hash, now),
        )
        return {
            "jurisdiction_code": jurisdiction_code,
            "law_type": law_type,
            "previous_hash": old_hash[:12],
            "current_hash": new_hash[:12],
            "seeded_at": now,
        }


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _days_since(ts: str | None) -> int | None:
    if not ts:
        return None
    try:
        return (datetime.utcnow() - datetime.fromisoformat(ts)).days
    except (ValueError, TypeError):
        return None
