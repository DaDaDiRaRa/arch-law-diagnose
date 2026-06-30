"""심의 트리거 재현 감사 (캘리브레이션 루프 ②).

골든 케이스의 `context_recorded_not_asserted.reviews` 에는 그 실 인허가가 실제로
거친 심의·영향평가가 기록돼 있다. 이 감사는 엔진 `evaluate_reviews` 가 그 심의들을
REQUIRED 로 잡아내는지 대조해, **과소호출(엔진은 안 잡았는데 실제론 거친) 심의**를
재현가능하게 surface 한다. ①(법정 한도 재현 감사)의 심의 버전.

  실행:  .venv\\Scripts\\python.exe -m scripts.audit_review_triggers

⚠ 정직성: 이 도구는 *측정만* 한다. 임계값을 자동 수정하지 않는다 — 교통영향평가 등
임계값은 시행령 별표(HWP 첨부)에 있어 법제처 API 로 수집 불가하고, 단일 익명 사례로
정확한 임계 역산도 불가하므로, 보정은 검증된 법정 수치로만 수동 반영한다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_GOLDEN_DIR = Path(__file__).resolve().parent.parent / "tests" / "golden"

# 실 사례 기록상 심의 명칭 → 엔진 트리거 항목명 매핑.
#   값이 리스트면 그중 하나라도 REQUIRED 면 "잡음"으로 본다(통합심의 등).
#   값이 None 이면 review_triggers 범위 밖(별도 카드/영역)임을 명시.
_REVIEW_MAP: dict[str, list[str] | None] = {
    "건축심의": ["건축위원회 심의"],
    "경관심의": ["경관심의"],
    "건축·경관 통합심의": ["건축위원회 심의", "경관심의"],
    "교통영향평가": ["교통영향평가"],
    "재해영향평가": ["사전재해영향성검토"],
    "사전재해영향성검토": ["사전재해영향성검토"],
    "교육환경평가": ["교육환경평가"],
    "지하안전영향평가": ["지하안전영향평가"],
    "환경영향평가": ["환경영향평가"],
    "도시계획위원회 심의": ["도시계획위원회 심의"],
    "건축물 안전영향평가": ["건축물 안전영향평가"],
    # review_triggers 범위 밖 — 소방 정성 카드(fire_safety) 영역
    "소방 성능위주설계": None,
}


def _engine_required(items: list[dict]) -> set[str]:
    return {it["name"] for it in items if it["severity"] == "REQUIRED"}


def _engine_maybe(items: list[dict]) -> set[str]:
    return {it["name"] for it in items if it["severity"] == "MAYBE"}


def main() -> None:
    from services.review_triggers import evaluate_reviews

    cases = []
    for path in sorted(_GOLDEN_DIR.glob("*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        ctx = c.get("context_recorded_not_asserted") or {}
        if ctx.get("reviews"):
            cases.append(c)

    if not cases:
        print("심의 기록(reviews)이 있는 골든 케이스 없음.")
        return

    print("\n심의 트리거 재현 감사 — 실 사례 기록 심의 vs 엔진 evaluate_reviews")
    print("  ✓=엔진 REQUIRED  △=엔진 MAYBE(과소호출 의심)  ✗=엔진 미발동  ·=범위 밖\n")

    under_calls: list[tuple[str, str, str]] = []  # (case, review, engine_state)
    for c in cases:
        inp = c["input"]
        reviews = c["context_recorded_not_asserted"]["reviews"]
        # 익명 라벨엔 도시명이 없어 in_urban 미검출 → 도시교통정비지역 가정해 보수적으로 평가.
        req = dict(inp)
        req["address"] = "서울특별시"  # 도시교통정비지역 가정(과소호출을 과대평가하지 않기 위함)
        result = evaluate_reviews(req, {"zone_use": inp["zone_use"]})
        req_set = _engine_required(result["items"])
        maybe_set = _engine_maybe(result["items"])

        print(f"[{c['id']}]  ({inp['building_use']}, {inp['total_floor_area']:,.0f}㎡, "
              f"{inp['floors_above']}F, {inp.get('height','?')}m)")
        for rv in reviews:
            mapped = _REVIEW_MAP.get(rv, "UNMAPPED")
            if mapped is None:
                print(f"    · {rv:<20} → review_triggers 범위 밖(소방 카드)")
                continue
            if mapped == "UNMAPPED":
                print(f"    ? {rv:<20} → 매핑 미정의(감사표 보강 필요)")
                continue
            hit_req = any(m in req_set for m in mapped)
            hit_maybe = any(m in maybe_set for m in mapped)
            if hit_req:
                mark = "✓"
            elif hit_maybe:
                mark = "△"
                under_calls.append((c["id"], rv, "MAYBE"))
            else:
                mark = "✗"
                under_calls.append((c["id"], rv, "NONE"))
            print(f"    {mark} {rv:<20} → 엔진 {'/'.join(mapped)} "
                  f"= {'REQUIRED' if hit_req else 'MAYBE' if hit_maybe else 'NONE'}")
        print()

    print("── 과소호출 요약 (실제론 거쳤으나 엔진은 REQUIRED 미판정) ──")
    if not under_calls:
        print("  없음 — 기록된 심의를 엔진이 모두 REQUIRED 로 재현.")
    else:
        for cid, rv, state in under_calls:
            print(f"  ✗ [{cid}] {rv}  (엔진={state})")
        print(f"\n  총 {len(under_calls)}건. 임계값 과대 의심 → 검증된 법정 수치로 수동 보정 대상.")
        print("  ※ 자동 수정 금지: 시행령 별표(HWP) API 미수집 + 단일 익명사례 역산 불가.")


if __name__ == "__main__":
    main()
