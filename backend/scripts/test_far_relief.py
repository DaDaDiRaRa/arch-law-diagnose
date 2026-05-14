"""용적률 완화 통합 테스트.

사진 케이스 재현: 준공업지역 400% 한도 → 460%로 완화된 사업
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.calculator import far
from services.far_relief import build_relief_note, compute_relief


def print_relief(r):
    print(f"  applied:       {r['applied']}")
    print(f"  base:          {r['base_limit_pct']}%")
    print(f"  final:         {r['final_limit_pct']}%")
    print(f"  manual_used:   {r['manual_used']}")
    if r['applied_items']:
        print(f"  items:")
        for it in r['applied_items']:
            print(f"    · {it['label']} +{it['relief_pct']}% ({it['basis']})")
    if r['capped']:
        print(f"  cap: {r['cap_note']}")


# ── 케이스 1: 사용자 수동 한도 (도시계획심의 결정 460%) ──
print("=== 케이스 1: 사진 케이스 — 도시계획심의 460% 수동 지정 ===")
relief = compute_relief(
    base_limit_pct=400,  # 준공업 기본
    zone_use="준공업지역",
    building_use="공동주택",
    site_area=7500,
    far_limit_manual_override=460,
    relief_reason_manual="설계공모지침서 기준 (서울시 도시계획심의 결정)",
)
print_relief(relief)
assert relief["final_limit_pct"] == 460
assert relief["manual_used"]

# ── 케이스 2: 자동 완화 — 공개공지 25% + 녹색 우수 + 에너지 1+ ──
print("\n=== 케이스 2: 자동 완화 — 공개공지 25% + 친환경 ===")
relief = compute_relief(
    base_limit_pct=1300,  # 일반상업
    zone_use="일반상업지역",
    building_use="업무시설",
    site_area=2000,
    public_open_space_area=500,   # 25% (의무 10% 초과 15%p)
    green_grade="우수",            # +6%
    energy_grade="1+",             # +9%
)
print_relief(relief)
# 공개공지: 25-10=15%p → 15% 완화 (캡 20%)
# 인증 합산: 6+9=15% → 캡 12%로 비례 축소 (6/15*12=4.8, 9/15*12=7.2)
# 총: 15 + 12 = 27%
# 최종: 1300 * 1.27 = 1651 — 그러나 전체 캡 1.2배 = 1560 적용
expected_final = 1300 * 1.2  # 1560
assert relief["final_limit_pct"] == expected_final, f"기대 {expected_final}, 실제 {relief['final_limit_pct']}"
assert relief["capped"]

# ── 케이스 3: 완화 적용된 한도로 far 진단 ──
print("\n=== 케이스 3: 진단 흐름 — far.calculate에 완화 한도 전달 ===")
far_result = far.calculate(
    floor_area_above=3400,       # 지상 연면적
    site_area=7500,
    zone_use="준공업지역",
    floors_below=2,
    limit_override=460,           # 완화 한도
    source_override="🌿 완화 적용 (자동 추정)",
)
# 실제 용적률 = 3400/7500*100 = 45.33% → 한도 460% 이내 → 적합
print(f"  실제: {far_result['actual_pct']}%")
print(f"  한도: {far_result['limit_pct']}%")
print(f"  pass: {far_result['pass']}")
print(f"  source: {far_result['source']}")

# ── 케이스 4: 인증만 입력 — 합산 캡 검증 ──
print("\n=== 케이스 4: 인증 4종 동시 입력 — 합산 캡 12% 검증 ===")
relief = compute_relief(
    base_limit_pct=250,  # 2종주거
    zone_use="제2종일반주거지역",
    building_use="공동주택",
    site_area=2000,
    green_grade="최우수",   # +9
    energy_grade="1++",     # +12
    smart_grade="최우수",   # +9
    long_life_grade="최우수", # +9 (공동주택만 적용)
)
print_relief(relief)
# 9+12+9+9 = 39 → 캡 12로 비례 축소
assert relief["capped"]
total = sum(i["relief_pct"] for i in relief["applied_items"])
assert abs(total - 12) < 0.01, f"인증 합산 12% 캡 실패: {total}"
# 최종: 250 * 1.12 = 280
assert abs(relief["final_limit_pct"] - 280) < 0.1

# ── 케이스 5: 적용 안 함 — 공개공지 의무비율 이하 ──
print("\n=== 케이스 5: 적용 없음 — 공개공지 5% (의무 10% 미달) ===")
relief = compute_relief(
    base_limit_pct=1300,
    zone_use="일반상업지역",
    building_use="업무시설",
    site_area=2000,
    public_open_space_area=100,  # 5% — 의무 미달
)
print_relief(relief)
assert not relief["applied"]

print("\n✅ 5개 케이스 모두 통과")
print("\n--- 완화 노트 예시 ---")
relief = compute_relief(
    base_limit_pct=400,
    zone_use="준공업지역",
    building_use="공동주택",
    site_area=7500,
    far_limit_manual_override=460,
    relief_reason_manual="서울시 도시계획심의 결정",
)
print(build_relief_note(relief))
