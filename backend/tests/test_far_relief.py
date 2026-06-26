"""far_relief.compute_relief 회귀 테스트 — 완화 합산·캡 로직 고정.

법규 수치(등급별 완화·캡)는 룰 JSON에서 읽어 자기일관성 유지. 캡·비례축소·전체상한
같은 계산 로직이 바뀌면 깨지도록 설계.
"""
from __future__ import annotations

from services.far_relief import compute_relief, _load_rules

RULES = _load_rules()
GREEN = max(RULES["green_building"]["by_grade"], key=RULES["green_building"]["by_grade"].get)
GREEN_PCT = RULES["green_building"]["by_grade"][GREEN]          # 최우수 = 6
ZEB = max(RULES["zero_energy"]["by_grade"], key=RULES["zero_energy"]["by_grade"].get)
ZEB_PCT = RULES["zero_energy"]["by_grade"][ZEB]                 # 1등급 = 15
POS_ZONE = RULES["public_open_space"]["applicable_zones"][0]
CAPS = RULES.get("_caps", {})
CERT_CAP = float(CAPS.get("certification_sum_cap_pct", 15))
OVERALL_RATIO = float(CAPS.get("total_overall_cap_ratio", 1.15))


def _base(**kw):
    args = dict(base_limit_pct=400.0, zone_use=POS_ZONE, building_use="업무시설", site_area=1000.0)
    args.update(kw)
    return compute_relief(**args)


def test_manual_override_wins():
    r = _base(far_limit_manual_override=520.0, relief_reason_manual="지구단위")
    assert r["manual_used"] is True
    assert r["final_limit_pct"] == 520.0


def test_no_base_limit():
    r = _base(base_limit_pct=None)
    assert r["applied"] is False
    assert r["final_limit_pct"] == 0


def test_single_green_cert():
    r = _base(green_grade=GREEN)
    assert r["applied"] is True
    assert r["final_limit_pct"] == round(400.0 * (1 + GREEN_PCT / 100), 2)
    kinds = {i["kind"] for i in r["applied_items"]}
    assert "green_building" in kinds


def test_cert_sum_cap():
    """녹색+ZEB 합이 캡(15%) 초과 → 비례 축소, capped True."""
    r = _base(green_grade=GREEN, zero_energy_grade=ZEB)  # 6 + 15 = 21 > 15
    assert GREEN_PCT + ZEB_PCT > CERT_CAP
    cert_sum = sum(i["relief_pct"] for i in r["applied_items"]
                   if i["kind"] in ("green_building", "zero_energy"))
    assert abs(cert_sum - CERT_CAP) < 0.05      # 캡까지 비례 축소
    assert r["capped"] is True
    assert r["final_limit_pct"] == round(400.0 * (1 + CERT_CAP / 100), 2)


def test_overall_cap_115():
    """공개공지(최대 20%) + 인증 → 전체 캡 1.15배로 제한."""
    # 공개공지 30% 제공 → 의무 10% 초과 20%p → +20%(캡), + 녹색 6% = 26% > 15%(=1.15배)
    r = _base(public_open_space_area=300.0, green_grade=GREEN)
    assert r["capped"] is True
    assert r["final_limit_pct"] == round(400.0 * OVERALL_RATIO, 2)
    assert "전체 캡" in r["cap_note"]


def test_pos_below_mandatory_no_relief():
    """공개공지가 의무비율 미만이면 완화 없음."""
    r = _base(public_open_space_area=50.0)  # 5% < 의무 10%
    assert r["applied"] is False
    assert r["final_limit_pct"] == 400.0
