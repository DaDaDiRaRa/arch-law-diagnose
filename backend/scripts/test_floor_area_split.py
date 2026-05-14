"""floor_area_above/below 분리 스키마 검증."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import main
print("OK - main imports")

from main import DiagnoseRequest, MultiDiagnoseRequest, ParcelInput, _attach_total_floor_area

# 1) 지상만
r1 = DiagnoseRequest(
    address="서울", building_use="업무시설",
    site_area=500, building_area=300,
    floor_area_above=1500,
    floors_above=5, height=20,
)
d1 = _attach_total_floor_area(r1.model_dump())
print(f"  지상만: above={d1['floor_area_above']} below={d1.get('floor_area_below')} total={d1['total_floor_area']}")
assert d1["total_floor_area"] == 1500

# 2) 지상+지하
r2 = DiagnoseRequest(
    address="서울", building_use="업무시설",
    site_area=500, building_area=300,
    floor_area_above=1500, floor_area_below=400,
    floors_above=5, floors_below=2, height=20,
)
d2 = _attach_total_floor_area(r2.model_dump())
print(f"  지상+지하: above={d2['floor_area_above']} below={d2['floor_area_below']} total={d2['total_floor_area']}")
assert d2["total_floor_area"] == 1900

# 3) 멀티
m = MultiDiagnoseRequest(
    parcels=[
        ParcelInput(address="a", site_area=500),
        ParcelInput(address="b", site_area=300),
    ],
    building_use="업무시설", building_area=400,
    floor_area_above=2000, floor_area_below=600,
    floors_above=10, floors_below=3, height=40,
)
print(f"  멀티: above={m.floor_area_above} below={m.floor_area_below}")
assert m.floor_area_above == 2000
assert m.floor_area_below == 600

# 4) far.py 계산 — 지상만 사용
from services.calculator import far
res_far = far.calculate(
    floor_area_above=2000,
    site_area=500,
    zone_use="일반상업지역",
    floors_below=2,
)
# 용적률 = 2000/500*100 = 400%
print(f"  far 계산 (지상 2000/대지 500): actual={res_far['actual_pct']}%, limit={res_far['limit_pct']}%, pass={res_far['pass']}")
assert abs(res_far["actual_pct"] - 400) < 0.01
assert "지하 2층 면적은 용적률 산정에서 제외" in res_far["notes"]

# 5) 비교: 만약 지하 포함 전체 2600을 그냥 넣었다면 = 520% (잘못 계산)
res_far_wrong = far.calculate(
    floor_area_above=2600,  # 전체 (잘못)
    site_area=500,
    zone_use="일반상업지역",
)
print(f"  비교 (전체 2600/500): actual={res_far_wrong['actual_pct']}%")
assert abs(res_far_wrong["actual_pct"] - 520) < 0.01

print("\nOK - 모든 검증 통과")
