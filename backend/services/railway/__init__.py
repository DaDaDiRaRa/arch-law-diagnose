"""철도보호지구 검사 모듈.

철도안전법 §45: 철도경계선으로부터 30m 이내를 철도보호지구로 지정.
해당 구역 내 건축 시 국토교통부장관(또는 관리자) 허가·협의 필요.

데이터: 전국 철도망 SHP (RAILWAY_SHP_PATH 환경변수 또는 files/railway/railway.shp)
좌표계: EPSG:5179 (GRS80 TM, 국토지리정보원 현행 표준) — .env RAILWAY_SHP_CRS로 변경 가능
"""
from services.railway.indexer import check_railway_proximity

__all__ = ["check_railway_proximity"]
