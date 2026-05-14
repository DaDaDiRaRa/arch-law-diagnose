"""피난안전구역 면적 용적률 제외 검증.

시나리오: 60층 초고층 주거 (강남 등 중심상업지역)
- 대지면적: 5,000㎡
- 지상 연면적: 70,000㎡ (60층 × 평균 1,167㎡)
- 지상 주차장 (필로티): 2,000㎡
- 피난안전구역: 30층마다 1개 = 2개소 × 800㎡ = 1,600㎡
- 지하 연면적: 15,000㎡
- 용도지역: 중심상업지역 (용적률 한도 1,500%)

기대값:
- 용적률 산정 면적 = 70000 - 2000 - 1600 = 66,400㎡
- 용적률 = 66400 / 5000 × 100 = 1,328%
- 만약 모두 미제외 시 = 70000 / 5000 × 100 = 1,400% (한도 1500% 이내라 둘 다 적합이지만, 점수와 여유는 다름)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.calculator import far
from main import DiagnoseRequest, _attach_total_floor_area

print("=== 60층 초고층 시나리오 ===\n")

# 케이스 A: 주차장 + 피난안전구역 모두 제외
res_correct = far.calculate(
    floor_area_above=66400,    # 70000 - 2000 - 1600
    site_area=5000,
    zone_use="중심상업지역",
    floors_below=3,
    parking_excluded=2000,
    refuge_excluded=1600,
)
print("[A] 주차장 + 피난안전구역 제외 (정확)")
print(f"    실제 용적률: {res_correct['actual_pct']}%")
print(f"    한도:        {res_correct['limit_pct']}%")
print(f"    pass:        {res_correct['pass']}")
print(f"    score:       {res_correct['score']}")
print(f"    notes: {res_correct['notes']}")
print()

# 케이스 B: 피난안전구역만 미제외
res_partial = far.calculate(
    floor_area_above=68000,    # 70000 - 2000 (parking 만 제외)
    site_area=5000,
    zone_use="중심상업지역",
    floors_below=3,
    parking_excluded=2000,
)
print("[B] 주차장만 제외, 피난안전구역 누락")
print(f"    실제 용적률: {res_partial['actual_pct']}%")
print(f"    score:       {res_partial['score']}")
print()

# 검증
assert res_correct["actual_pct"] == 1328
assert res_correct["pass"] is True
assert "피난안전구역 1600㎡ 제외" in res_correct["notes"]
assert "지상 부속용도 주차장 2000㎡ 제외" in res_correct["notes"]
assert res_partial["actual_pct"] == 1360

print("✅ 케이스 A: 1,328% (한도 1,500% 이내, 32% 여유)")
print("⚠️ 케이스 B: 1,360% (피난안전구역 미반영 시 32% 추가로 사용된 것처럼 잘못 계산)")
print()


# === 엔진 통합 흐름 ===
print("\n=== 엔진 통합 (req 흐름 검증) ===")
req = DiagnoseRequest(
    address="서울 강남구 테헤란로",
    building_use="공동주택",
    site_area=5000,
    building_area=3000,
    floor_area_above=70000,
    floor_area_below=15000,
    floor_area_parking_above=2000,
    floor_area_refuge=1600,
    floors_above=60,
    floors_below=3,
    height=220,
    units=600,
)
data = _attach_total_floor_area(req.model_dump())
print(f"  floor_area_above:         {data['floor_area_above']:,}")
print(f"  floor_area_below:         {data['floor_area_below']:,}")
print(f"  floor_area_parking_above: {data['floor_area_parking_above']:,}")
print(f"  floor_area_refuge:        {data['floor_area_refuge']:,}")
print(f"  total_floor_area:         {data['total_floor_area']:,}  (주차/소방용)")

# 엔진 미러
above = data["floor_area_above"]
parking = data.get("floor_area_parking_above") or 0
refuge = data.get("floor_area_refuge") or 0
far_area = max(0.0, above - parking - refuge)
print(f"  → 용적률 산정 면적: {far_area:,.0f} (=above - parking - refuge)")
assert far_area == 66400

print("\n✅ 모든 검증 통과")
