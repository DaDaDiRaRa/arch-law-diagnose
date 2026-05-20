"""용적률 완화 계산 — 공개공지·녹색건축·제로에너지·시범사업 + 사용자 수동 입력.

근거: 건축법 시행령 제27조의2 + 녹색건축물 조성 지원법 §15 + 건축물의 에너지절약설계기준(국토부 고시 제2025-738호) 별표9.

자동 적용된 완화는 실제 인허가 심의에서 인정받아야 효력 발생.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_RULES_PATH = Path(__file__).parent.parent / "config" / "far_relief_rules.json"
_RULES_CACHE: dict | None = None


def _load_rules() -> dict:
    global _RULES_CACHE
    if _RULES_CACHE is None:
        with open(_RULES_PATH, encoding="utf-8") as f:
            _RULES_CACHE = json.load(f)
    return _RULES_CACHE


def compute_relief(
    *,
    base_limit_pct: float | None,
    zone_use: str,
    building_use: str,
    site_area: float,
    public_open_space_area: float | None = None,
    green_grade: str | None = None,
    zero_energy_grade: str | None = None,
    pilot_project: bool = False,
    smart_grade: str | None = None,
    long_life_grade: str | None = None,
    far_limit_manual_override: float | None = None,
    relief_reason_manual: str | None = None,
) -> dict:
    """기본 용적률 한도에 가능한 완화를 적용해 최종 한도와 내역 반환.

    Returns:
      {
        applied: bool,                    # 완화 1개라도 적용됐는지
        base_limit_pct: float,            # 시행령/조례 기본 한도
        final_limit_pct: float,           # 완화 적용 후 최종 한도
        applied_items: [                  # 적용된 완화 내역
          {kind, label, relief_pct, basis, note}
        ],
        capped: bool,                     # 합산 캡에 걸렸는지
        cap_note: str,                    # 캡 안내
        manual_used: bool,                # 사용자 수동 한도 사용 여부
        manual_reason: str,
      }
    """
    rules = _load_rules()
    caps = rules.get("_caps", {})
    cert_cap = float(caps.get("certification_sum_cap_pct", 15))
    overall_cap_ratio = float(caps.get("total_overall_cap_ratio", 1.15))

    # 사용자 수동 한도가 입력되면 그것이 최우선 (도시계획심의·지구단위 등)
    if far_limit_manual_override is not None and far_limit_manual_override > 0:
        return {
            "applied": True,
            "base_limit_pct": base_limit_pct or 0,
            "final_limit_pct": float(far_limit_manual_override),
            "applied_items": [{
                "kind": "manual",
                "label": "사용자 직접 지정",
                "relief_pct": 0,
                "basis": "도시계획심의 / 지구단위계획 / 정비사업 인센티브 등",
                "note": relief_reason_manual or "사용자가 직접 한도 입력",
            }],
            "capped": False,
            "cap_note": "",
            "manual_used": True,
            "manual_reason": relief_reason_manual or "",
        }

    if base_limit_pct is None or base_limit_pct <= 0:
        return {
            "applied": False,
            "base_limit_pct": base_limit_pct or 0,
            "final_limit_pct": base_limit_pct or 0,
            "applied_items": [],
            "capped": False,
            "cap_note": "",
            "manual_used": False,
            "manual_reason": "",
        }

    items: list[dict] = []

    # 1. 공개공지 완화
    pos_rule = rules["public_open_space"]
    if (
        public_open_space_area is not None
        and public_open_space_area > 0
        and site_area > 0
        and zone_use in pos_rule["applicable_zones"]
    ):
        provided_ratio = (public_open_space_area / site_area) * 100
        mandatory = float(pos_rule["mandatory_ratio_pct"])
        excess = max(0.0, provided_ratio - mandatory)
        # 단순 비례: 초과 1%p 당 1% 완화 (캡 max_relief_pct)
        pos_relief = min(excess, float(pos_rule["max_relief_pct"]))
        if pos_relief > 0:
            items.append({
                "kind": "public_open_space",
                "label": f"공개공지 {provided_ratio:.2f}% 제공 (의무 {mandatory:.0f}% 초과)",
                "relief_pct": round(pos_relief, 2),
                "basis": pos_rule["law"],
                "note": f"초과분 {excess:.2f}%p × 비례 완화",
            })

    # 2~5. 인증 등급 완화
    cert_total = 0.0
    cert_items_raw: list[dict] = []

    def _add_cert(kind: str, grade: str | None, applicable_check=lambda: True):
        nonlocal cert_total
        if not grade:
            return
        rule = rules.get(kind, {})
        if "applicable_uses" in rule:
            uses = rule["applicable_uses"]
            if building_use not in uses:
                return
        relief = float(rule.get("by_grade", {}).get(grade, 0))
        if relief > 0:
            cert_items_raw.append({
                "kind": kind,
                "label": _kind_label(kind, grade),
                "relief_pct": relief,
                "basis": rule.get("law", ""),
                "note": f"{grade} 등급 · 완화율은 국토부 고시 기준 추정값 — 실제 고시 확인 필요",
            })
            cert_total += relief

    _add_cert("green_building", green_grade)
    _add_cert("zero_energy", zero_energy_grade)
    if pilot_project:
        _add_cert("pilot_project", "지정")
    _add_cert("smart_building", smart_grade)
    _add_cert("long_life_housing", long_life_grade)

    # 인증 합산 캡 적용
    capped_by_cert_cap = False
    if cert_total > cert_cap:
        scale = cert_cap / cert_total
        for it in cert_items_raw:
            it["relief_pct"] = round(it["relief_pct"] * scale, 2)
            it["note"] += f" · 합산 캡 {cert_cap}%로 비례 축소"
        cert_total = cert_cap
        capped_by_cert_cap = True

    items.extend(cert_items_raw)

    # 총 완화율 (% pt 합)
    sum_relief_pct = sum(i["relief_pct"] for i in items)

    # 최종 한도 = base + base * sum_relief_pct/100
    raw_final = base_limit_pct * (1 + sum_relief_pct / 100)
    overall_cap = base_limit_pct * overall_cap_ratio
    final_limit = min(raw_final, overall_cap)
    capped_by_overall = raw_final > overall_cap

    cap_note = ""
    if capped_by_cert_cap and capped_by_overall:
        cap_note = (
            f"인증 합산 캡 {cert_cap}% + 전체 캡 {overall_cap_ratio}배 (={overall_cap:.0f}%) 동시 적용"
        )
    elif capped_by_cert_cap:
        cap_note = f"인증 합산 캡 {cert_cap}%로 일부 완화율 축소"
    elif capped_by_overall:
        cap_note = f"전체 캡 {overall_cap_ratio}배 (={overall_cap:.0f}%) 적용 — 추가 완화 무효화"

    return {
        "applied": len(items) > 0,
        "base_limit_pct": round(base_limit_pct, 2),
        "final_limit_pct": round(final_limit, 2),
        "applied_items": items,
        "capped": capped_by_cert_cap or capped_by_overall,
        "cap_note": cap_note,
        "manual_used": False,
        "manual_reason": "",
    }


def _kind_label(kind: str, grade: str) -> str:
    return {
        "green_building":   f"녹색건축 인증 {grade}",
        "zero_energy":      f"제로에너지건축물(ZEB) {grade}",
        "pilot_project":    "녹색건축물 조성 시범사업",
        "smart_building":   f"지능형건축물 인증 {grade}",
        "long_life_housing": f"장수명주택 인증 {grade}",
    }.get(kind, kind)


def build_relief_note(relief: dict) -> str:
    """완화 결과를 사람이 읽을 수 있는 notes 문자열로."""
    if not relief["applied"]:
        return ""
    if relief["manual_used"]:
        return (
            f" · 용적률 한도 {relief['final_limit_pct']}% 적용 — 사용자 직접 지정 "
            f"({relief['manual_reason']}). ⚠ 자동 추정 — 인허가 심의 인정 시 효력"
        )
    parts = []
    for it in relief["applied_items"]:
        parts.append(f"{it['label']} (+{it['relief_pct']}%)")
    txt = (
        f" · 용적률 완화 적용: 기본 {relief['base_limit_pct']}% → "
        f"{relief['final_limit_pct']}%. 내역: {', '.join(parts)}"
    )
    if relief["cap_note"]:
        txt += f" · {relief['cap_note']}"
    txt += ". ⚠ 자동 추정 — 인허가 심의에서 인정받아야 효력 발생"
    return txt
