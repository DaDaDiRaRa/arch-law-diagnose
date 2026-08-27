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


# ── limits_determined_by="심의" (feasibility_export 부분 채택, 2026-08-27) ──────
# 공모가 제시한 60%/460%가 도시계획위원회 심의로 정해진 값일 때, 법정 표(준공업
# 400%)와의 차이는 결함이 아니다. 실사례: 영등포통합신청사 부지1.


def test_gap_review_premised_replaces_over():
    """심의 결정 한도면 초과가 아니라 '심의 전제'."""
    g = fe._compute_gap(460, 400, "max", "심의")
    assert g["status"] == "review_premised"
    assert g["gap"] == -60          # 숫자는 그대로 — 차이를 숨기지 않는다
    assert "심의" in g["gap_text"]


def test_gap_legal_still_over():
    """'법정'이면 기존대로 초과."""
    assert fe._compute_gap(460, 400, "max", "법정")["status"] == "over"
    assert fe._compute_gap(460, 400, "max", None)["status"] == "over"


def test_gap_review_premised_not_applied_when_within_limit():
    """한도 안이면 심의든 아니든 충족."""
    assert fe._compute_gap(300, 400, "max", "심의")["status"] == "ok"


def test_gap_min_semantic_ignores_review():
    """주차 같은 법정 '최소'는 심의로 면제되지 않는다."""
    g = fe._compute_gap(100, 430, "min", "심의")
    assert g["status"] == "over"


def test_recommendation_review_premised_is_not_pass_recommendation():
    """심의 전제만 있으면 '패스 권장'이 아니라 '협상 필요'."""
    cats = [{"gap_analysis": {"status": "review_premised"}, "scenarios": []}]
    r = fe._compute_recommendation(cats)
    assert r["verdict"] == "협상 필요"
    assert "심의" in r["reason"]


def test_recommendation_real_over_still_wins():
    """진짜 초과가 같이 있으면 그쪽이 우선 — 심의 전제가 가리지 않는다."""
    cats = [
        {"gap_analysis": {"status": "review_premised"}, "scenarios": []},
        {"gap_analysis": {"status": "over"}, "scenarios": []},
    ]
    assert fe._compute_recommendation(cats)["verdict"] == "패스 권장"


# ── run_feasibility 통합 — 심의 플래그가 요청→카테고리까지 실제로 흐르는가 ──────
# 단위 테스트는 _compute_gap만 본다. 요청 필드가 거기까지 닿는지는 별개 문제라
# 스텁 엔진으로 전 구간을 한 번 통과시킨다. (영등포 부지1 실측치: 준공업 400% vs 460%)


class _StubResolver:
    async def resolve(self, address, pnu=""):
        return {"zone_use": "준공업지역", "zone_district": "", "parcel_area": 7498.0}


class _StubEngine:
    """diagnose_fast만 흉내내는 최소 엔진 — 네트워크 0."""

    def __init__(self):
        self._resolver = _StubResolver()

    async def diagnose_fast(self, payload, zone_use="", land_info=None, skip_ai=True):
        return {
            "land_info": {"zone_use": zone_use},
            "results": {
                "건폐율": {"limit_pct": 70.0, "source": "시행령"},
                "용적률": {"limit_pct": 400.0, "source": "시행령", "relief_info": {}},
                "주차": {"required_spaces": 300},
            },
            "applicable_reviews": {"items": [], "required_count": 0, "maybe_count": 0},
        }


def _run(req_extra):
    import asyncio
    req = {
        "address": "서울특별시 영등포구 당산동3가 385",
        "facility_use": "업무시설",
        "applicant_type": "공공기관",
        "site_area_override": 7498.0,
        "target_far_pct": 460.0,
        "target_building_coverage_pct": 60.0,
        **req_extra,
    }
    return asyncio.run(fe.run_feasibility(_StubEngine(), req))


def _far_status(res):
    return next(c["gap_analysis"]["status"] for c in res["categories"] if c["key"] == "far")


def test_run_feasibility_review_flag_reaches_categories():
    """limits_determined_by='심의' → 용적률 갭이 review_premised."""
    res = _run({"limits_determined_by": "심의"})
    assert _far_status(res) == "review_premised"
    assert res["overall_recommendation"]["verdict"] == "협상 필요"


def test_run_feasibility_without_flag_is_over():
    """플래그 없으면 기존 그대로 초과 — 회귀 방지."""
    res = _run({})
    assert _far_status(res) == "over"

