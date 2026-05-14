"""지상 주차장 면적 용적률 제외 검증.

시나리오: 공동주택 — 1·2층 필로티 주차장 + 3층 이상 주거
- 대지면적: 1,000㎡
- 지상 연면적: 3,000㎡ (1·2층 주차 500㎡ × 2 = 1,000㎡ + 3~10층 주거 250 × 8 = 2,000㎡)
- 지상 주차장: 1,000㎡
- 지하 연면적: 800㎡ (지하 주차)
- 용도: 공동주택, 제2종일반주거지역(용적률 한도 250%)

기대값:
- 용적률 산정 면적 = 3000 - 1000 = 2000㎡ (지하 800은 이미 제외, 지상 주차 1000도 제외)
- 용적률 = 2000 / 1000 × 100 = 200% (한도 250% 이내 → 적합)
- 만약 주차장 제외 안 했다면 = 3000/1000 × 100 = 300% (한도 초과 → 부적합)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.calculator import far

print("=== 공동주택 필로티 주차장 시나리오 ===\n")

# 케이스 A: 주차장 제외 적용 (정상)
res_correct = far.calculate(
    floor_area_above=2000,    # 3000 - 1000 (호출 측에서 미리 차감됨)
    site_area=1000,
    zone_use="제2종일반주거지역",
    floors_below=2,
    parking_excluded=1000,
)
print("[A] 주차장 제외 적용 (정확한 계산)")
print(f"    실제 용적률: {res_correct['actual_pct']}%")
print(f"    한도:        {res_correct['limit_pct']}%")
print(f"    pass:        {res_correct['pass']}")
print(f"    score:       {res_correct['score']}")
print(f"    notes: {res_correct['notes']}")
print()

# 케이스 B: 주차장 미제외 (예전 잘못된 계산)
res_wrong = far.calculate(
    floor_area_above=3000,    # 전체 지상 연면적 그대로 (잘못)
    site_area=1000,
    zone_use="제2종일반주거지역",
    floors_below=2,
)
print("[B] 주차장 미제외 (옛 방식 — 잘못)")
print(f"    실제 용적률: {res_wrong['actual_pct']}%")
print(f"    한도:        {res_wrong['limit_pct']}%")
print(f"    pass:        {res_wrong['pass']}")
print(f"    score:       {res_wrong['score']}")
print()

# 검증
assert res_correct["actual_pct"] == 200
assert res_correct["pass"] is True   # 200% ≤ 250% 적합
assert res_correct["score"] > 7      # 적합 점수
assert "지상 부속용도 주차장 1000㎡ 제외" in res_correct["notes"]
assert "지하 2층 면적은 용적률 산정 제외" in res_correct["notes"]

assert res_wrong["actual_pct"] == 300
assert res_wrong["pass"] is False    # 300% > 250% 부적합
assert res_wrong["score"] == 0       # 초과 점수

print("✅ 케이스 A (정상): 용적률 200% — 한도 250% 이내, 적합")
print("❌ 케이스 B (잘못): 용적률 300% — 한도 250% 초과, 부적합")
print()
print("→ 지상 주차장 제외 기능이 결과를 뒤집음 (부적합 → 적합)")
print()


# === 엔진 통합 테스트 ===
print("\n=== 엔진 통합 (req 흐름 검증) ===")
from main import DiagnoseRequest, _attach_total_floor_area

req = DiagnoseRequest(
    address="서울 강남구 역삼동 737",
    building_use="공동주택",
    site_area=1000,
    building_area=600,
    floor_area_above=3000,
    floor_area_below=800,
    floor_area_parking_above=1000,
    floors_above=10,
    floors_below=2,
    height=30,
    units=40,
)
data = _attach_total_floor_area(req.model_dump())
print(f"  floor_area_above:         {data['floor_area_above']}")
print(f"  floor_area_below:         {data['floor_area_below']}")
print(f"  floor_area_parking_above: {data['floor_area_parking_above']}")
print(f"  total_floor_area:         {data['total_floor_area']}  (지상+지하, 주차/소방용)")

# 엔진 내부 계산 미러링
floor_area_above = data["floor_area_above"]
parking_above = data.get("floor_area_parking_above") or 0
floor_area_for_far = max(0.0, floor_area_above - parking_above)
print(f"  → 용적률 산정 면적: {floor_area_for_far} (=above-parking)")
assert floor_area_for_far == 2000

print("\n✅ 모든 검증 통과")
