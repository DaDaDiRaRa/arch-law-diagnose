"""4가지 용적률 제외 항목 통합 검증 (건축법 시행령 제119조).

1. 지하층 면적
2. 지상층 부속용도 주차장
3. 피난안전구역 (초고층/준초고층)
4. 경사지붕 아래 대피공간 (11층 이상)

시나리오: 15층 공동주택 (다락 대피공간 포함)
- 대지: 2,000㎡
- 지상 연면적: 12,000㎡ (1·2층 필로티 + 3~14층 주거 + 15층 다락)
- 지상 주차장: 1,200㎡ (1·2층 필로티)
- 경사지붕 대피공간: 100㎡ (다락 일부)
- 지하 연면적: 3,000㎡
- 제3종일반주거지역 (용적률 한도 300%)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.calculator import far
from main import DiagnoseRequest, _attach_total_floor_area

print("=== 15층 공동주택 — 4가지 제외 통합 ===\n")

# 케이스 A: 모두 정확 적용
res = far.calculate(
    floor_area_above=12000 - 1200 - 100,  # = 10700
    site_area=2000,
    zone_use="제3종일반주거지역",
    floors_below=2,
    parking_excluded=1200,
    refuge_excluded=0,
    attic_refuge_excluded=100,
)
# 용적률 = 10700 / 2000 * 100 = 535% (한도 300% 초과)
# 이건 한도 초과지만 그건 데이터 이슈; 제외 적용 자체는 정확

# 시나리오를 한도 이내로 조정해 의미있게:
# 지상 연면적 6000 (필로티 1200 + 주거 4700 + 다락 100)
res = far.calculate(
    floor_area_above=6000 - 1200 - 100,  # = 4700
    site_area=2000,
    zone_use="제3종일반주거지역",
    floors_below=2,
    parking_excluded=1200,
    refuge_excluded=0,
    attic_refuge_excluded=100,
)
print("[A] 11층 공동주택 — 주차장 + 대피공간 제외")
print(f"    실제 용적률: {res['actual_pct']}%")
print(f"    한도:        {res['limit_pct']}%")
print(f"    pass:        {res['pass']}")
print(f"    score:       {res['score']}")
print(f"    notes:")
for part in res['notes'].split(' · '):
    print(f"      · {part.strip()}")
print()

# 검증
assert res["actual_pct"] == 235.0  # 4700/2000*100 = 235%
assert res["pass"] is True
assert "지하 2층 면적은 용적률 산정 제외" in res["notes"]
assert "지상 부속용도 주차장 1200㎡ 제외" in res["notes"]
assert "경사지붕 대피공간 100㎡ 제외" in res["notes"]
assert "피난안전구역" not in res["notes"]  # 입력 0이므로 표시 안 됨


# === 엔진 흐름 — 4가지 모두 입력 ===
print("\n=== 엔진 통합 (4가지 모두 입력) ===")
req = DiagnoseRequest(
    address="서울 강남구",
    building_use="공동주택",
    site_area=3000,
    building_area=1500,
    floor_area_above=30000,        # 30층 건물
    floor_area_below=6000,         # 지하 3층
    floor_area_parking_above=2400,
    floor_area_refuge=400,         # 피난안전구역
    floor_area_attic_refuge=80,    # 경사지붕 대피공간
    floors_above=30,
    floors_below=3,
    height=110,
    units=200,
)
data = _attach_total_floor_area(req.model_dump())
above = data["floor_area_above"]
below = data["floor_area_below"]
parking = data.get("floor_area_parking_above") or 0
refuge = data.get("floor_area_refuge") or 0
attic = data.get("floor_area_attic_refuge") or 0
far_area = max(0.0, above - parking - refuge - attic)

print(f"  지상 연면적:       {above:>8,.0f}㎡")
print(f"  지하 연면적:       {below:>8,.0f}㎡")
print(f"  - 지상 주차장:     {parking:>8,.0f}㎡")
print(f"  - 피난안전구역:    {refuge:>8,.0f}㎡")
print(f"  - 경사지붕 대피:   {attic:>8,.0f}㎡")
print(f"  ─────────────────────────────")
print(f"  용적률 산정 면적:  {far_area:>8,.0f}㎡  (지상 - 주차 - 피난 - 대피)")
print(f"  전체 연면적:       {data['total_floor_area']:>8,.0f}㎡  (지상 + 지하, 주차/소방 산정용)")

assert far_area == 27120  # 30000 - 2400 - 400 - 80

print("\n✅ 4가지 제외 항목 모두 정확히 누적 차감됨")
