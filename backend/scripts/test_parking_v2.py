"""주차장법 시행령 별표 1 정확성 검증 — v2 (오류 수정 후).

각 케이스의 기대 결과는 시행령 별표 1 + 주택건설기준규정 §27 직접 산정.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 캐시 클리어 (다른 테스트가 먼저 로드했으면)
from services.calculator import parking as p
p._STANDARDS = {}

from services.calculator.parking import calculate


def case(label, use, area, expected, units=None, ea=None):
    r = calculate(use, area, provided_spaces=None, units=units, unit_exclusive_area=ea)
    got = r["required_spaces"]
    ok = "✅" if got == expected else "❌"
    print(f"  {ok} {label}: 법정 {got}대 (기대 {expected}대) — {use}")
    if got != expected:
        print(f"     note: {r['notes']}")
    return got == expected


print("=== 단독주택 누적식 (시행령 별표 1) ===")
all_ok = True
all_ok &= case("40㎡ 단독", "단독주택", 40, 0)       # 50㎡ 이하 면제
all_ok &= case("50㎡ 단독", "단독주택", 50, 0)       # 50㎡까지 면제
all_ok &= case("80㎡ 단독", "단독주택", 80, 1)       # 50~150: 1대
all_ok &= case("150㎡ 단독", "단독주택", 150, 1)
all_ok &= case("180㎡ 단독", "단독주택", 180, 2)     # 150 + 30㎡ → +1대
all_ok &= case("250㎡ 단독", "단독주택", 250, 2)     # 150 + 100㎡ → 1대 + ceil(100/100)=1 → 2대
all_ok &= case("260㎡ 단독", "단독주택", 260, 3)     # 1 + ceil(110/100) = 3
all_ok &= case("350㎡ 단독", "단독주택", 350, 3)     # 1 + ceil(200/100) = 3

print("\n=== 공동주택 (주택건설기준규정 §27) ===")
all_ok &= case("100세대 전용 55㎡", "공동주택", 0, 70, units=100, ea=55)  # 0.7대 × 100
all_ok &= case("100세대 전용 60㎡", "공동주택", 0, 70, units=100, ea=60)  # 60㎡ 경계: 0.7대
all_ok &= case("100세대 전용 75㎡", "공동주택", 0, 100, units=100, ea=75) # 1.0대 × 100
all_ok &= case("100세대 전용 30㎡", "공동주택", 0, 70, units=100, ea=30)  # 0.7대

print("\n=== 시행령 별표 1 면적기준 (주요 용도) ===")
all_ok &= case("위락 200㎡", "위락시설", 200, 2)              # 100㎡/대
all_ok &= case("판매 200㎡", "판매시설", 200, 2)              # 150㎡/대 → ceil(200/150)=2
all_ok &= case("판매 300㎡", "판매시설", 300, 2)              # ceil(300/150)=2
all_ok &= case("업무 1000㎡", "업무시설", 1000, 7)            # 150㎡/대 → ceil(1000/150)=7
all_ok &= case("의료 1000㎡", "의료시설", 1000, 7)            # 150㎡/대
all_ok &= case("문화집회 1000㎡", "문화및집회시설", 1000, 7)  # 150㎡/대
all_ok &= case("종교 1000㎡", "종교시설", 1000, 7)            # 150㎡/대
all_ok &= case("운동 1500㎡", "운동시설", 1500, 10)           # 150㎡/대
all_ok &= case("근생1 1000㎡", "제1종근린생활시설", 1000, 5) # 200㎡/대 → ceil(1000/200)=5
all_ok &= case("근생2 1000㎡", "제2종근린생활시설", 1000, 5) # 200㎡/대
all_ok &= case("숙박 1000㎡", "숙박시설", 1000, 5)            # 200㎡/대
all_ok &= case("교육 2000㎡", "교육연구시설", 2000, 10)       # 200㎡/대
all_ok &= case("창고 1000㎡", "창고시설", 1000, 3)            # 400㎡/대 → ceil(1000/400)=3
all_ok &= case("공장 1000㎡", "공장", 1000, 3)                # 350㎡/대 → ceil(1000/350)=3
all_ok &= case("수련 1000㎡", "수련시설", 1000, 3)            # 350㎡/대
all_ok &= case("그밖 1000㎡", "기타용도", 1000, 4)            # 300㎡/대 default → ceil(1000/300)=4

print()
print("✅ 모두 통과" if all_ok else "❌ 일부 실패 — 위 결과 확인")
