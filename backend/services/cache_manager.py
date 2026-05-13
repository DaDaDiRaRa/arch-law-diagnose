"""SQLite 기반 Lazy Cache 관리자.

- 조례 본문 캐시 (30일 TTL)
- 토지정보 캐시 (PNU 기반)
- 진단 이력 로그
- 법규 변경 버전 해시
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta

import aiosqlite
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "./data/arch_law.db")
CACHE_TTL_DAYS = int(os.getenv("CACHE_TTL_DAYS", "30"))

DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS jurisdictions (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    parent_code TEXT,
    type TEXT
);

CREATE TABLE IF NOT EXISTS ordinances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    jurisdiction_code TEXT NOT NULL,
    law_type TEXT NOT NULL,
    title TEXT,
    content TEXT,
    article_no TEXT,
    last_fetched_at TEXT NOT NULL,
    source_url TEXT,
    FOREIGN KEY (jurisdiction_code) REFERENCES jurisdictions(code)
);
CREATE INDEX IF NOT EXISTS idx_ordinances_jcode ON ordinances(jurisdiction_code, law_type);

CREATE VIRTUAL TABLE IF NOT EXISTS ordinances_fts USING fts5(
    title, content,
    content='ordinances',
    content_rowid='id'
);

CREATE TABLE IF NOT EXISTS land_info_cache (
    pnu TEXT PRIMARY KEY,
    address TEXT,
    jurisdiction_code TEXT,
    zone_use TEXT,
    zone_district TEXT,
    zone_area TEXT,
    district_plan TEXT,
    urban_facility TEXT,
    land_category TEXT,
    official_price INTEGER,
    lon REAL,
    lat REAL,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS diagnose_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT,
    pnu TEXT,
    input_json TEXT,
    result_json TEXT,
    overall_score REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ordinance_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    jurisdiction_code TEXT NOT NULL,
    law_type TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);
"""


class CacheManager:
    def __init__(self) -> None:
        self._db: aiosqlite.Connection | None = None
        os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)

    async def init(self) -> None:
        self._db = await aiosqlite.connect(DB_PATH)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(DDL)
        await self._db.commit()
        logger.info("SQLite DB 초기화 완료: %s", DB_PATH)

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    # ─── 토지 정보 캐시 ───────────────────────────────────────────────────

    async def get_land_info(self, pnu: str) -> dict | None:
        row = await self._fetchone(
            "SELECT *, fetched_at FROM land_info_cache WHERE pnu = ?", (pnu,)
        )
        if not row:
            return None
        fetched_at = _parse_dt(row["fetched_at"])
        age_days = (datetime.utcnow() - fetched_at).days
        data = dict(row)
        data["cache_age_days"] = age_days
        data["cache_stale"] = age_days > CACHE_TTL_DAYS
        return data

    async def set_land_info(self, pnu: str, address: str, data: dict) -> None:
        now = datetime.utcnow().isoformat()
        await self._db.execute(
            """INSERT INTO land_info_cache
               (pnu, address, jurisdiction_code, zone_use, zone_district, zone_area,
                district_plan, urban_facility, land_category, official_price, lon, lat, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(pnu) DO UPDATE SET
               address=excluded.address, jurisdiction_code=excluded.jurisdiction_code,
               zone_use=excluded.zone_use, zone_district=excluded.zone_district,
               zone_area=excluded.zone_area, district_plan=excluded.district_plan,
               urban_facility=excluded.urban_facility, land_category=excluded.land_category,
               official_price=excluded.official_price, lon=excluded.lon, lat=excluded.lat,
               fetched_at=excluded.fetched_at""",
            (
                pnu, address,
                data.get("jurisdiction_code", ""),
                data.get("zone_use", ""),
                data.get("zone_district", ""),
                data.get("zone_area", ""),
                data.get("district_plan", ""),
                data.get("urban_facility", ""),
                data.get("land_category", ""),
                data.get("official_price"),
                data.get("lon"),
                data.get("lat"),
                now,
            ),
        )
        await self._db.commit()

    # ─── 조례 캐시 ────────────────────────────────────────────────────────

    async def get_ordinance(self, jurisdiction_code: str, law_type: str) -> list[dict] | None:
        """None = 캐시 미스. [] = 빈 캐시(데이터 없음)."""
        rows = await self._fetchall(
            """SELECT *, last_fetched_at FROM ordinances
               WHERE jurisdiction_code = ? AND law_type = ?
               ORDER BY article_no""",
            (jurisdiction_code, law_type),
        )
        if not rows:
            # 캐시 자체가 없으면 None 반환
            count_row = await self._fetchone(
                "SELECT COUNT(*) as cnt FROM ordinances WHERE jurisdiction_code=? AND law_type=?",
                (jurisdiction_code, law_type),
            )
            if count_row and count_row["cnt"] == 0:
                return None
        if rows:
            fetched_at = _parse_dt(rows[0]["last_fetched_at"])
            if (datetime.utcnow() - fetched_at).days > 90:
                return None  # 강제 재조회
        return [dict(r) for r in rows]

    async def set_ordinances(
        self,
        jurisdiction_code: str,
        law_type: str,
        articles: list[dict],
    ) -> None:
        now = datetime.utcnow().isoformat()
        await self._db.execute(
            "DELETE FROM ordinances WHERE jurisdiction_code=? AND law_type=?",
            (jurisdiction_code, law_type),
        )
        for art in articles:
            content = art.get("content", "")
            await self._db.execute(
                """INSERT INTO ordinances
                   (jurisdiction_code, law_type, title, content, article_no, last_fetched_at, source_url)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    jurisdiction_code, law_type,
                    art.get("title", ""), content,
                    art.get("article_no", ""), now,
                    art.get("source_url", ""),
                ),
            )
        # 버전 해시 기록
        combined = "\n".join(a.get("content", "") for a in articles)
        h = hashlib.sha256(combined.encode()).hexdigest()
        await self._db.execute(
            "INSERT INTO ordinance_versions (jurisdiction_code, law_type, content_hash, fetched_at) VALUES (?,?,?,?)",
            (jurisdiction_code, law_type, h, now),
        )
        await self._db.commit()
        logger.info("조례 캐시 저장: %s/%s (%d 조문)", jurisdiction_code, law_type, len(articles))

    # ─── 진단 이력 ────────────────────────────────────────────────────────

    async def save_history(self, address: str, pnu: str, input_data: dict, result: dict) -> None:
        score = result.get("overall_score")
        await self._db.execute(
            """INSERT INTO diagnose_history
               (address, pnu, input_json, result_json, overall_score, created_at)
               VALUES (?,?,?,?,?,?)""",
            (address, pnu, json.dumps(input_data, ensure_ascii=False),
             json.dumps(result, ensure_ascii=False), score,
             datetime.utcnow().isoformat()),
        )
        await self._db.commit()

    # ─── 유틸 ─────────────────────────────────────────────────────────────

    async def _fetchone(self, sql: str, params=()) -> aiosqlite.Row | None:
        async with self._db.execute(sql, params) as cur:
            return await cur.fetchone()

    async def _fetchall(self, sql: str, params=()) -> list[aiosqlite.Row]:
        async with self._db.execute(sql, params) as cur:
            return await cur.fetchall()

    # ─── 외부 서비스용 (Phase 4) ──────────────────────────────────────────

    async def query(self, sql: str, params=()) -> list[dict]:
        """읽기 전용 raw query. law_change_tracker 등 도메인 서비스용."""
        rows = await self._fetchall(sql, params)
        return [dict(r) for r in rows]

    async def execute(self, sql: str, params=()) -> None:
        """쓰기 statement (INSERT/UPDATE). 외부 서비스에서 직접 기록 시 사용."""
        await self._db.execute(sql, params)
        await self._db.commit()


def _parse_dt(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.utcnow() - timedelta(days=999)
