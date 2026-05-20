"""전국 철도망 SHP → STRtree (선형 거리 기반, 싱글턴 캐시).

철도보호지구 판정: 대지 좌표 ↔ 철도 선형 최단거리 ≤ 30m.

SHP 배치: RAILWAY_SHP_PATH 환경변수 또는 files/railway/railway.shp
SHP 좌표계: RAILWAY_SHP_CRS 환경변수 (기본: EPSG:4326 WGS84)
  - Geofabrik OSM: EPSG:4326 (기본값, 변경 불필요)
  - 국토지리정보원 수치지형도: EPSG:5179
  - 구 Bessel TM SHP: EPSG:5174

내부 작업 좌표계는 항상 EPSG:5179 (GRS80 TM, 미터 단위) — 30m 버퍼 정확도 보장.

OSM railways 필드:
  fclass: rail / subway / tram / light_rail / narrow_gauge 등
  name: 노선명 (빈 경우 있음)
"""
from __future__ import annotations

import functools
import logging
import os
import threading
from pathlib import Path

import shapefile
from pyproj import Transformer
from shapely.geometry import MultiLineString, Point
from shapely.ops import transform as shp_transform
from shapely.strtree import STRtree

logger = logging.getLogger(__name__)

PROTECTION_M = 30.0  # 철도보호지구 폭 — 철도안전법 §45

# 내부 작업 좌표계: EPSG:5179 (GRS80 TM 중부원점, 미터 단위)
_WORK_CRS = "EPSG:5179"

_DEFAULT_SHP = Path(__file__).resolve().parents[3] / "files" / "railway" / "railway.shp"

_lock = threading.Lock()
_sentinel = object()
_index = _sentinel  # 로드 전 sentinel


class _RailwayIndex:
    def __init__(self) -> None:
        self.lines: list = []
        self.records: list[dict] = []
        self.tree: STRtree | None = None

    def load(self, shp_path: Path, src_crs: str) -> None:
        to_work = _make_reprojector(src_crs, _WORK_CRS)
        sf = shapefile.Reader(str(shp_path.with_suffix("")), encoding="utf-8")
        try:
            pass
        except Exception:
            sf = shapefile.Reader(str(shp_path.with_suffix("")), encoding="cp949")

        fields = [f[0] for f in sf.fields[1:]]
        for shape_rec in sf.iterShapeRecords():
            shp = shape_rec.shape
            if not shp.points:
                continue
            geom_native = _to_linestring(shp)
            if geom_native is None or geom_native.is_empty:
                continue
            try:
                geom_5179 = shp_transform(to_work, geom_native)
                if geom_5179.is_empty:
                    continue
            except Exception:
                continue
            rec = dict(zip(fields, shape_rec.record))
            self.lines.append(geom_5179)
            self.records.append(rec)

        if self.lines:
            self.tree = STRtree(self.lines)
        logger.info("철도망 SHP 로드 완료: %d개 선형 (src=%s → %s)", len(self.lines), src_crs, _WORK_CRS)

    def check(self, x5179: float, y5179: float) -> tuple[bool, list[dict]]:
        """EPSG:5179 좌표가 철도경계 30m 이내인지 판정."""
        if not self.tree:
            return False, []
        pt = Point(x5179, y5179)
        candidates = self.tree.query(pt.buffer(PROTECTION_M))
        hits = []
        for i in candidates:
            dist = self.lines[i].distance(pt)
            if dist <= PROTECTION_M:
                rec = self.records[i]
                hits.append({
                    "name": _rail_name(rec),
                    "fclass": rec.get("fclass") or rec.get("type") or "",
                    "distance_m": round(dist, 1),
                })
        hits.sort(key=lambda h: h["distance_m"])
        return bool(hits), hits


def _to_linestring(shp):
    parts = list(shp.parts) + [len(shp.points)]
    segments = [shp.points[parts[i]:parts[i + 1]] for i in range(len(parts) - 1)]
    valid = [s for s in segments if len(s) >= 2]
    if not valid:
        return None
    if len(valid) == 1:
        from shapely.geometry import LineString
        return LineString(valid[0])
    return MultiLineString(valid)


def _rail_name(rec: dict) -> str:
    for key in ("name", "RAIL_NM", "LINE_NM", "RAILRD_NM", "RRNM", "노선명", "철도명"):
        v = rec.get(key)
        if v and str(v).strip() not in ("", "None"):
            return str(v).strip()
    # OSM fclass로 대체
    fc = rec.get("fclass") or rec.get("type") or ""
    if fc:
        return f"철도({fc})"
    return "철도노선"


@functools.lru_cache(maxsize=4)
def _make_reprojector(src: str, dst: str):
    tr = Transformer.from_crs(src, dst, always_xy=True)
    return tr.transform


@functools.lru_cache(maxsize=1)
def _wgs84_to_5179() -> Transformer:
    return Transformer.from_crs("EPSG:4326", _WORK_CRS, always_xy=True)


def _get_index() -> "_RailwayIndex | None":
    global _index
    if _index is not _sentinel:
        return _index  # type: ignore[return-value]

    with _lock:
        if _index is not _sentinel:
            return _index  # type: ignore[return-value]

        shp_path = Path(os.getenv("RAILWAY_SHP_PATH") or _DEFAULT_SHP)
        if not shp_path.exists():
            logger.info("철도망 SHP 미배치 (%s) — 철도보호지구 검사 생략", shp_path)
            _index = None
            return None

        src_crs = os.getenv("RAILWAY_SHP_CRS", "EPSG:4326")
        try:
            idx = _RailwayIndex()
            idx.load(shp_path, src_crs)
            _index = idx
            return idx
        except Exception as e:
            logger.warning("철도망 SHP 로드 실패: %s", e)
            _index = None
            return None


def check_railway_proximity(lat: float, lng: float) -> dict:
    """대지 좌표(WGS84)가 철도보호지구(30m) 이내인지 판정."""
    idx = _get_index()
    if idx is None:
        return {
            "checked": False,
            "within_zone": False,
            "nearby": [],
            "note": "철도망 SHP 미배치 — files/railway/railway.shp 배치 후 재시작 필요",
        }

    x, y = _wgs84_to_5179().transform(lng, lat)
    within, hits = idx.check(x, y)
    return {
        "checked": True,
        "within_zone": within,
        "nearby": [{"name": h["name"], "distance_m": h["distance_m"]} for h in hits],
        "note": (
            f"철도경계 {hits[0]['distance_m']}m 이내 — {hits[0]['name']} 인접"
            if within else
            "철도보호지구(30m) 해당 없음"
        ),
    }
