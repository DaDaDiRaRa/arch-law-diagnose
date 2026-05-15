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
LURIS_TTL_DAYS = int(os.getenv("LURIS_TTL_DAYS", "90"))  # 행위제한은 변경 빈도 낮음

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

-- B7: parcel polygon (GeoJSON) 별도 마이그레이션 — 신규 DB는 위 CREATE에 따라 컬럼 없이 생성됨.
-- 기존 DB에는 ALTER TABLE 로 추가. 실패해도 무시 (이미 존재).

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

CREATE TABLE IF NOT EXISTS ordinance_zone_limits (
    jurisdiction_code TEXT NOT NULL,
    jurisdiction_name TEXT,
    zone_use          TEXT NOT NULL,
    category          TEXT NOT NULL,
    value             REAL NOT NULL,
    source_law_id     TEXT,
    source_article    TEXT,
    ef_date           TEXT,
    fetched_at        TEXT NOT NULL,
    needs_review      INTEGER NOT NULL DEFAULT 0,
    is_estimate       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (jurisdiction_code, zone_use, category)
);
CREATE INDEX IF NOT EXISTS idx_ozl_code ON ordinance_zone_limits(jurisdiction_code);

-- LURIS 행위제한 응답 캐시 (1000회/일 한도 대응)
-- info_json IS NULL → API가 데이터 없음 응답한 것도 캐싱 (재호출 절약)
CREATE TABLE IF NOT EXISTS luris_act_info_cache (
    area_cd     TEXT NOT NULL,
    ucode       TEXT NOT NULL,
    land_use_nm TEXT NOT NULL,
    info_json   TEXT,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (area_cd, ucode, land_use_nm)
);

-- 토지이음(EUM) 행위제한 응답 캐시 — LURIS와 교차검증용
-- info_json IS NULL → 빈 응답도 캐싱 (재호출 절약)
CREATE TABLE IF NOT EXISTS eum_act_restriction_cache (
    area_cd     TEXT NOT NULL,
    ucode       TEXT NOT NULL,
    land_use_nm TEXT NOT NULL,
    info_json   TEXT,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (area_cd, ucode, land_use_nm)
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
        # B7 마이그레이션: parcel_geometry_json 컬럼 추가 (기존 DB 대응)
        try:
            await self._db.execute(
                "ALTER TABLE land_info_cache ADD COLUMN parcel_geometry_json TEXT"
            )
        except Exception:
            pass  # 이미 존재
        # 5.3 도로폭 자동 조회 컬럼 — 구버전 DB 호환
        try:
            await self._db.execute(
                "ALTER TABLE land_info_cache ADD COLUMN road_width_auto REAL"
            )
        except Exception:
            pass
        try:
            await self._db.execute(
                "ALTER TABLE land_info_cache ADD COLUMN road_width_source TEXT"
            )
        except Exception:
            pass
        # 시행령 평균 추정값 명시 컬럼 — 구버전 DB 호환
        try:
            await self._db.execute(
                "ALTER TABLE ordinance_zone_limits ADD COLUMN is_estimate INTEGER NOT NULL DEFAULT 0"
            )
        except Exception:
            pass
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
        # parcel_geometry_json → dict
        raw_geom = data.pop("parcel_geometry_json", None)
        data["parcel_geometry"] = None
        if raw_geom:
            try:
                data["parcel_geometry"] = json.loads(raw_geom)
            except json.JSONDecodeError:
                pass
        return data

    async def set_land_info(self, pnu: str, address: str, data: dict) -> None:
        now = datetime.utcnow().isoformat()
        geom = data.get("parcel_geometry")
        geom_json = json.dumps(geom, ensure_ascii=False) if geom else None
        await self._db.execute(
            """INSERT INTO land_info_cache
               (pnu, address, jurisdiction_code, zone_use, zone_district, zone_area,
                district_plan, urban_facility, land_category, official_price, lon, lat,
                fetched_at, parcel_geometry_json, road_width_auto, road_width_source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(pnu) DO UPDATE SET
               address=excluded.address, jurisdiction_code=excluded.jurisdiction_code,
               zone_use=excluded.zone_use, zone_district=excluded.zone_district,
               zone_area=excluded.zone_area, district_plan=excluded.district_plan,
               urban_facility=excluded.urban_facility, land_category=excluded.land_category,
               official_price=excluded.official_price, lon=excluded.lon, lat=excluded.lat,
               fetched_at=excluded.fetched_at,
               parcel_geometry_json=excluded.parcel_geometry_json,
               road_width_auto=excluded.road_width_auto,
               road_width_source=excluded.road_width_source""",
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
                geom_json,
                data.get("road_width_auto"),
                data.get("road_width_source"),
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

    # ─── 조례 수치 (ordinance_zone_limits) ───────────────────────────────

    async def get_zone_limit(
        self,
        jurisdiction_code: str,
        zone_use: str,
        category: str,
    ) -> dict | None:
        """DB에 저장된 조례 수치를 반환. 없으면 None."""
        row = await self._fetchone(
            """SELECT * FROM ordinance_zone_limits
               WHERE jurisdiction_code=? AND zone_use=? AND category=?""",
            (jurisdiction_code, zone_use, category),
        )
        return dict(row) if row else None

    async def set_zone_limit(
        self,
        jurisdiction_code: str,
        jurisdiction_name: str | None,
        zone_use: str,
        category: str,
        value: float,
        source_law_id: str | None = None,
        source_article: str | None = None,
        ef_date: str | None = None,
        needs_review: bool = False,
        is_estimate: bool = False,
    ) -> None:
        """조례 수치를 UPSERT.

        is_estimate: 실제 조례에서 추출한 값이 아니라 시행령 평균 추정값일 때 True.
          시도 광역 seed로 미수집 시군구를 임시 채우는 경우 등.
        """
        now = datetime.utcnow().isoformat()
        await self._db.execute(
            """INSERT INTO ordinance_zone_limits
               (jurisdiction_code, jurisdiction_name, zone_use, category,
                value, source_law_id, source_article, ef_date, fetched_at,
                needs_review, is_estimate)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(jurisdiction_code, zone_use, category) DO UPDATE SET
               jurisdiction_name=excluded.jurisdiction_name,
               value=excluded.value,
               source_law_id=excluded.source_law_id,
               source_article=excluded.source_article,
               ef_date=excluded.ef_date,
               fetched_at=excluded.fetched_at,
               needs_review=excluded.needs_review,
               is_estimate=excluded.is_estimate""",
            (
                jurisdiction_code, jurisdiction_name, zone_use, category,
                value, source_law_id, source_article, ef_date, now,
                1 if needs_review else 0,
                1 if is_estimate else 0,
            ),
        )
        await self._db.commit()

    async def list_zone_limits(self, jurisdiction_code: str) -> list[dict]:
        """특정 시군구의 조례 수치 전체 목록."""
        rows = await self._fetchall(
            "SELECT * FROM ordinance_zone_limits WHERE jurisdiction_code=? ORDER BY zone_use, category",
            (jurisdiction_code,),
        )
        return [dict(r) for r in rows]

    # ─── LURIS 행위제한 캐시 ─────────────────────────────────────────────

    async def get_luris_act_info(
        self,
        area_cd: str,
        ucode: str,
        land_use_nm: str,
    ) -> tuple[bool, dict | None]:
        """LURIS 응답 캐시 조회.

        Returns:
          (hit, info)
            hit=False: 캐시 미스 (호출 필요)
            hit=True, info=None: 'API가 빈/오류 응답을 캐싱한 상태' (재호출 불필요)
            hit=True, info=dict: 정상 캐시
        """
        row = await self._fetchone(
            """SELECT info_json, fetched_at FROM luris_act_info_cache
               WHERE area_cd=? AND ucode=? AND land_use_nm=?""",
            (area_cd, ucode, land_use_nm),
        )
        if not row:
            return False, None
        fetched_at = _parse_dt(row["fetched_at"])
        age_days = (datetime.utcnow() - fetched_at).days
        if age_days > LURIS_TTL_DAYS:
            return False, None  # 만료 → 재호출
        raw = row["info_json"]
        if raw is None:
            return True, None
        try:
            return True, json.loads(raw)
        except json.JSONDecodeError:
            return False, None

    async def set_luris_act_info(
        self,
        area_cd: str,
        ucode: str,
        land_use_nm: str,
        info: dict | None,
    ) -> None:
        """LURIS 응답 저장 (info=None도 캐싱 — 재호출 방지)."""
        now = datetime.utcnow().isoformat()
        payload = json.dumps(info, ensure_ascii=False) if info is not None else None
        await self._db.execute(
            """INSERT INTO luris_act_info_cache
               (area_cd, ucode, land_use_nm, info_json, fetched_at)
               VALUES (?,?,?,?,?)
               ON CONFLICT(area_cd, ucode, land_use_nm) DO UPDATE SET
               info_json=excluded.info_json,
               fetched_at=excluded.fetched_at""",
            (area_cd, ucode, land_use_nm, payload, now),
        )
        await self._db.commit()

    # ─── EUM 행위제한 캐시 ───────────────────────────────────────────────

    async def get_eum_act_restriction(
        self,
        area_cd: str,
        ucode: str,
        land_use_nm: str,
    ) -> tuple[bool, list | None]:
        """EUM 행위제한 응답 캐시 조회.

        Returns:
          (hit, list_data)
            hit=False: 캐시 미스
            hit=True, list_data=None: 빈 응답 캐싱됨 (재호출 불필요)
            hit=True, list_data=list: 정상 캐시
        """
        row = await self._fetchone(
            """SELECT info_json, fetched_at FROM eum_act_restriction_cache
               WHERE area_cd=? AND ucode=? AND land_use_nm=?""",
            (area_cd, ucode, land_use_nm),
        )
        if not row:
            return False, None
        fetched_at = _parse_dt(row["fetched_at"])
        age_days = (datetime.utcnow() - fetched_at).days
        if age_days > LURIS_TTL_DAYS:
            return False, None
        raw = row["info_json"]
        if raw is None:
            return True, None
        try:
            return True, json.loads(raw)
        except json.JSONDecodeError:
            return False, None

    async def set_eum_act_restriction(
        self,
        area_cd: str,
        ucode: str,
        land_use_nm: str,
        info: list | None,
    ) -> None:
        """EUM 행위제한 응답 저장 (info=None / 빈 list도 캐싱)."""
        now = datetime.utcnow().isoformat()
        payload = json.dumps(info, ensure_ascii=False) if info else None
        await self._db.execute(
            """INSERT INTO eum_act_restriction_cache
               (area_cd, ucode, land_use_nm, info_json, fetched_at)
               VALUES (?,?,?,?,?)
               ON CONFLICT(area_cd, ucode, land_use_nm) DO UPDATE SET
               info_json=excluded.info_json,
               fetched_at=excluded.fetched_at""",
            (area_cd, ucode, land_use_nm, payload, now),
        )
        await self._db.commit()

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
