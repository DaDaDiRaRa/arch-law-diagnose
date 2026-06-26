"""feasibility_engine 순수 헬퍼 회귀 테스트 — 갭 분석·심의 부담·종합 판단·형변환.

_build_review_burden은 dict({items})/list 양쪽을 받아야 함(2026-06-22 버그 회귀).
"""
from __future__ import annotations

from services import feasibility_engine as fe


# ── _compute_gap ─────────────────────────────────────────────────────────────
def test_gap_no_target():
    assert fe._compute_gap(None, 400, "max")["status"] == "no_target"
    assert fe._compute_gap(0, 400, "max")["status"] == "no_target"


def test_gap_unknown_limit():
    assert fe._compute_gap(400, None, "max")["status"] == "unknown"


def test_gap_max_ok_and_over():
    assert fe._compute_gap(300, 400, "max")["status"] == "ok"     # 한도 이하
    assert fe._compute_gap(450, 400, "max")["status"] == "over"   # 한도 초과
    assert fe._compute_gap(450, 400, "max")["gap"] == -50.0


def test_gap_min_ok_and_over():
    # 주차 등 하한: target(계획) ≥ limit(법정최소)면 ok
    assert fe._compute_gap(120, 100, "min")["status"] == "ok"
    assert fe._compute_gap(80, 100, "min")["status"] == "over"


# ── _build_review_burden (dict / list / garbage) ─────────────────────────────
def _reviews():
    return {
        "items": [
            {"name": "건축위원회 심의", "severity": "REQUIRED", "triggered_reasons": ["16층"], "law_ref": "§4-2"},
            {"name": "교통영향평가", "severity": "MAYBE", "triggered_reasons": [], "note": "임박"},
            {"name": "환경영향평가", "severity": "NONE"},
        ]
    }


def test_review_burden_from_dict():
    b = fe._build_review_burden(_reviews())
    assert b["count_required"] == 1
    assert b["count_maybe"] == 1
    assert b["required"][0]["name"] == "건축위원회 심의"
    assert "16층" in b["required"][0]["reason"]


def test_review_burden_from_list():
    b = fe._build_review_burden(_reviews()["items"])
    assert b["count_required"] == 1
    assert b["count_maybe"] == 1


def test_review_burden_garbage():
    assert fe._build_review_burden(None)["count_required"] == 0
    assert fe._build_review_burden("nope")["count_maybe"] == 0


# ── _compute_recommendation ──────────────────────────────────────────────────
def _cat(status, covers=False):
    return {"gap_analysis": {"status": status},
            "scenarios": [{"covers_target": covers}] if status == "over" else []}


def test_recommendation_participate():
    out = fe._compute_recommendation([_cat("ok"), _cat("no_target")])
    assert out["verdict"] == "참여 권장"


def test_recommendation_pass():
    out = fe._compute_recommendation([_cat("over", covers=False)])
    assert out["verdict"] == "패스 권장"


def test_recommendation_negotiate():
    out = fe._compute_recommendation([_cat("over", covers=True)])
    assert out["verdict"] == "협상 필요"


def test_recommendation_info_shortage():
    out = fe._compute_recommendation([_cat("unknown")])
    assert out["verdict"] == "정보 부족"


# ── _to_float / _to_int ──────────────────────────────────────────────────────
def test_to_float():
    assert fe._to_float("123.5") == 123.5
    assert fe._to_float(None, default=1.0) == 1.0
    assert fe._to_float("", default=2.0) == 2.0
    assert fe._to_float("bad", default=3.0) == 3.0


def test_to_int():
    assert fe._to_int("7") == 7
    assert fe._to_int(None, default=0) == 0
    assert fe._to_int("bad", default=5) == 5
