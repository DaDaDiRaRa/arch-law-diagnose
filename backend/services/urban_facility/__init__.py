"""도시계획시설 저촉 검사 모듈.

대지 좌표 → 도시계획시설 폴리곤 교차 검사 → 저촉 시설 정보 반환.

데이터 출처: 토지이음 (국토교통부) — files/3/shp/
좌표계: EPSG:5174 (Bessel 중부) → 진단 시 WGS84(4326)에서 변환
"""
from services.urban_facility.lookup import (
    check_facility_conflict,
    compute_facility_overlap,
)

__all__ = ["check_facility_conflict", "compute_facility_overlap"]
