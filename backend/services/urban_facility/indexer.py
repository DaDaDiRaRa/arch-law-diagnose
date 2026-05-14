"""SHP → 시·도별 R-tree 인덱스 (메모리, LRU 캐시).

진단 시점에 해당 시·도 SHP만 메모리에 로딩.
shapely.STRtree로 후보 좁힌 뒤 point-in-polygon 정확 검사.
"""
from __future__ import annotations

import threading
from collections import OrderedDict
from pathlib import Path

import shapefile
from shapely.geometry import Polygon
from shapely.strtree import STRtree

from services.urban_facility.sido import resolve_sido_folder

# 시·도 SHP 루트 (프로젝트 루트 기준)
SHP_ROOT = Path(__file__).resolve().parents[3] / "files" / "3" / "shp"

# UQ 카테고리 코드 목록
UQ_CATEGORIES = [f"UQ15{i}" for i in range(1, 10)]

# LRU 캐시 — 시·도 단위로 RAM 차지가 있어 무한정 두면 안 됨
_CACHE_MAX = 4
_cache: OrderedDict[str, "SidoIndex"] = OrderedDict()
_cache_lock = threading.Lock()


class SidoIndex:
    """한 시·도의 모든 UQ 카테고리 폴리곤 + STRtree."""

    def __init__(self, sido_code: str):
        self.sido_code = sido_code
        self.polygons: list[Polygon] = []
        self.records: list[dict] = []  # 폴리곤 i의 속성
        self.tree: STRtree | None = None

    def load(self, folder: Path) -> None:
        for shp_path in sorted(folder.glob("*.shp")):
            stem = shp_path.stem            # 예: KLIP_C_UQ151
            uq = stem.split("_")[-1]
            if uq not in UQ_CATEGORIES:
                continue
            self._load_one(shp_path.with_suffix(""), uq)
        if self.polygons:
            self.tree = STRtree(self.polygons)

    def _load_one(self, base: Path, uq: str) -> None:
        sf = shapefile.Reader(str(base), encoding="cp949")
        fields = [f[0] for f in sf.fields[1:]]
        for shape_rec in sf.iterShapeRecords():
            shp = shape_rec.shape
            if not shp.points:
                continue
            # POLYGON: parts로 외곽/내부 링 구분
            parts = list(shp.parts) + [len(shp.points)]
            rings = [shp.points[parts[i]:parts[i + 1]] for i in range(len(parts) - 1)]
            if not rings or len(rings[0]) < 3:
                continue
            try:
                poly = Polygon(rings[0], rings[1:] if len(rings) > 1 else None)
                if not poly.is_valid:
                    poly = poly.buffer(0)  # self-intersection 보정
                if poly.is_empty:
                    continue
            except Exception:
                continue
            rec = dict(zip(fields, shape_rec.record))
            rec["_uq"] = uq
            self.polygons.append(poly)
            self.records.append(rec)

    def query(self, x: float, y: float) -> list[dict]:
        """EPSG:5174 좌표(x, y)와 교차하는 시설 속성 목록."""
        if not self.tree:
            return []
        from shapely.geometry import Point
        pt = Point(x, y)
        idxs = self.tree.query(pt)
        hits = []
        for i in idxs:
            if self.polygons[i].covers(pt):
                hits.append(self.records[i])
        return hits

    def query_polygon(self, parcel_poly) -> tuple[list[tuple[dict, float]], float]:
        """EPSG:5174 대지 폴리곤 → (시설별 교차내역, union 기준 총 보정면적).

        반환:
          ([(record, individual_area), ...],  # 시설별 (참고용, 중복 가능)
           union_overlap_area)                # 시설들을 union한 뒤 대지와 교차한 면적
                                              # (보정에 써야 할 정확한 값)
        """
        if not self.tree:
            return [], 0.0
        from shapely.ops import unary_union

        idxs = self.tree.query(parcel_poly)
        per_facility: list[tuple[dict, float]] = []
        intersected_polys = []
        for i in idxs:
            inter = self.polygons[i].intersection(parcel_poly)
            if inter.is_empty:
                continue
            a = inter.area
            if a <= 0.01:
                continue
            per_facility.append((self.records[i], a))
            intersected_polys.append(inter)

        per_facility.sort(key=lambda x: -x[1])
        union_area = unary_union(intersected_polys).area if intersected_polys else 0.0
        return per_facility, union_area


def get_index(sido_code: str) -> SidoIndex | None:
    """시·도 R-tree 인덱스 가져오기 (없으면 로드)."""
    with _cache_lock:
        if sido_code in _cache:
            _cache.move_to_end(sido_code)
            return _cache[sido_code]

    folder = resolve_sido_folder(SHP_ROOT, sido_code)
    if folder is None:
        return None

    idx = SidoIndex(sido_code)
    idx.load(folder)

    with _cache_lock:
        _cache[sido_code] = idx
        _cache.move_to_end(sido_code)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
    return idx
