"""골든 회귀 — 실 인허가 사례(익명화)로 진단 엔진의 정답 재현을 고정.

각 케이스: backend/tests/golden/*.json (식별정보 제외, 숫자·용도지역만).
외부 API 없이 `_diagnose`(skip_ai) + 조례 stub 로 결정론 실행 → 실 사례의
건폐율·용적률 등 핵심 산정값을 엔진이 그대로 재현하는지 검증한다.

새 케이스 추가법: golden/ 에 같은 스키마의 JSON 한 개 더 넣으면 자동 수집된다.
스키마·익명화 규칙은 golden/README.md 참조.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

_GOLDEN_DIR = Path(__file__).parent / "golden"
_CASES = sorted(_GOLDEN_DIR.glob("*.json"))


class _FakeOrdinance:
    """그 사례에 실제 적용된 조례 한도를 돌려주는 stub (실 조례 모사)."""

    def __init__(self, limits: dict):
        self._limits = limits or {}

    async def resolve(self, code, name, zone, key):  # noqa: ARG002 (시그니처 일치용)
        v = self._limits.get(key)
        if v is None:
            return {"value": None}
        return {
            "value": float(v),
            "is_ordinance": True,
            "source_detail": "골든 적용 조례(익명)",
        }


def _build_engine(applied_ordinance: dict):
    from services.diagnose_engine import DiagnoseEngine

    resolver = MagicMock()
    cache = MagicMock()
    cache.save_history = AsyncMock()
    cache.lookup_street_block_height = AsyncMock(return_value=None)
    llm = MagicMock()
    llm.available = False
    ordinance = _FakeOrdinance(applied_ordinance) if applied_ordinance else None
    return DiagnoseEngine(resolver, cache, llm, ordinance_resolver=ordinance, luris=None, eum=None)


def _build_req(inp: dict, label: str) -> dict:
    req = {
        "address": label,
        "building_use": inp["building_use"],
        "site_area": inp["site_area"],
        "building_area": inp["building_area"],
        "total_floor_area": inp["total_floor_area"],
        "floor_area_above": inp.get("floor_area_above", inp["total_floor_area"]),
        "floors_above": inp["floors_above"],
        "floors_below": inp.get("floors_below", 0),
        # 높이(m)가 없는 개요서(층수만 기재)는 층수×3.3 근사로 채움 — 높이 카드는
        # expected 에서 검증하지 않으므로 건폐율·용적률 정합에 영향 없음.
        "height": inp.get("height") or round(inp["floors_above"] * 3.3, 1),
    }
    # 선택 입력 — 있으면만 전달 (없는 키로 계산기 분기 오염 방지)
    for opt in (
        "landscape_area",
        "provided_parking_spaces",
        "units",
        "unit_exclusive_area",
        "public_open_space_area",
    ):
        if inp.get(opt) is not None:
            req[opt] = inp[opt]
    return req


@pytest.mark.skipif(not _CASES, reason="골든 케이스 없음")
@pytest.mark.parametrize("case_path", _CASES, ids=[p.stem for p in _CASES])
async def test_golden_case(case_path):
    case = json.loads(case_path.read_text(encoding="utf-8"))
    inp = case["input"]
    engine = _build_engine(case.get("applied_ordinance") or {})

    land = {
        "zone_use": inp["zone_use"],
        # 외부 조회를 막기 위해 lat/lon 미제공(좌표 의존 블록 skip).
        # 조례 stub 호출 트리거용으로 jurisdiction 만 비식별 placeholder 로 채움.
        "jurisdiction_code": "GOLD0",
        "jurisdiction_name": "(익명 지자체)",
    }

    result = await engine._diagnose(
        _build_req(inp, case.get("label", case["id"])),
        land,
        save_history=False,
        skip_ai=True,
    )
    res = result["results"]

    for cat, exp in case["expected"].items():
        if cat == "signal_not":
            assert result["signal"] != exp, (
                f"[{case['id']}] 신호가 {exp} 이면 안 됨 (실제 {result['signal']})"
            )
            continue
        card = res[cat]
        if "actual_pct" in exp:
            # 원문 건축개요서 표기와 ±0.01%p 허용 — 용도별 절사·반올림 경계의
            # 표기 관례 차이를 흡수(엔진은 면적÷면적을 2자리 반올림).
            assert abs(card["actual_pct"] - exp["actual_pct"]) < 0.011, (
                f"[{case['id']}] {cat} 산정값 {card['actual_pct']} != 기대 {exp['actual_pct']} (±0.01 허용)"
            )
        if "limit_pct" in exp:
            assert card["limit_pct"] == exp["limit_pct"], (
                f"[{case['id']}] {cat} 한도 {card['limit_pct']} != 기대 {exp['limit_pct']}"
            )
        if "pass" in exp:
            assert card["pass"] is exp["pass"], (
                f"[{case['id']}] {cat} pass {card['pass']} != 기대 {exp['pass']}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 고가치 경로 테스트 (합성) — 실 통과 케이스가 못 건드리는 미검증 경로를 직접 때린다.
#   실패/RED · 완화(far_relief) · 주차 부족 · 비주입(엔진 자가 한도결정).
#   여기서 실패가 나면 그게 곧 정확도 개선 지점.
# ─────────────────────────────────────────────────────────────────────────────
def _land(zone: str) -> dict:
    return {"zone_use": zone, "jurisdiction_code": "GOLD0", "jurisdiction_name": "(익명)"}


async def test_path_red_when_coverage_exceeds():
    """건폐율이 한도를 넘으면 pass=False + 종합신호 RED (실패 경로 검증)."""
    engine = _build_engine({"building_coverage_ratio": 60.0, "floor_area_ratio": 250.0})
    req = {
        "address": "RED-edge", "building_use": "업무시설",
        "site_area": 1000.0, "building_area": 700.0,   # 70% > 한도 60%
        "total_floor_area": 2000.0, "floor_area_above": 2000.0,  # 용적률 200% ≤ 250
        "floors_above": 5, "floors_below": 1, "height": 18.0,
    }
    result = await engine._diagnose(req, _land("제2종일반주거지역"), save_history=False, skip_ai=True)
    cov = result["results"]["건폐율"]
    assert cov["pass"] is False
    assert cov["actual_pct"] == 70.0 and cov["excess_pct"] == 10.0
    assert result["signal"] == "RED"          # pass=False 항목이 있으면 RED


async def test_path_relief_open_space_and_green_capped():
    """공개공지 초과 + 녹색최우수 완화가 합산되되 전체 캡 1.15배에 걸린다 (far_relief 경로).

    far_relief_rules.json 에 문서화된 실증 시나리오: 준공업·base 400% → 캡 460%.
    """
    engine = _build_engine({"floor_area_ratio": 400.0})
    req = {
        "address": "relief-edge", "building_use": "업무시설",
        "site_area": 10000.0, "building_area": 5000.0,
        "total_floor_area": 40000.0, "floor_area_above": 40000.0,
        "floors_above": 10, "floors_below": 2, "height": 40.0,
        "public_open_space_area": 2518.0,   # 25.18% → 의무 10% 초과 15.18%p
        "green_grade": "최우수",             # +6%
    }
    result = await engine._diagnose(req, _land("준공업지역"), save_history=False, skip_ai=True)
    far = result["results"]["용적률"]
    relief = far["relief_info"]
    assert relief["applied"] is True and relief["capped"] is True
    assert far["limit_pct"] == 460.0          # 400 × 1.15 (전체 캡)


async def test_path_parking_shortfall_fails():
    """계획 주차가 법정보다 적으면 주차 pass=False + 부족분 노출 (주차 경로)."""
    engine = _build_engine(None)
    req = {
        "address": "parking-edge", "building_use": "업무시설",
        "site_area": 2000.0, "building_area": 1000.0,
        "total_floor_area": 30000.0, "floor_area_above": 30000.0,
        "floors_above": 10, "floors_below": 2, "height": 40.0,
        "provided_parking_spaces": 10,        # 턱없이 부족
    }
    result = await engine._diagnose(req, _land("일반상업지역"), save_history=False, skip_ai=True)
    pk = result["results"]["주차"]
    assert pk["required_spaces"] is not None and pk["required_spaces"] > 10
    assert pk["pass"] is False and pk["deficit"] > 0


async def test_path_uninjected_uses_sihaengryeong_default():
    """조례를 주입하지 않으면 엔진이 zone_limits.json(시행령) 한도를 스스로 적용한다.

    → 한도 결정 로직 + 설정값 정확성 검증(여기 실패 = 실무 정확도 버그).
    제2종일반주거 시행령: 건폐율 60% · 용적률 250%.
    """
    engine = _build_engine(None)   # OrdinanceResolver 없음
    req = {
        "address": "uninjected", "building_use": "업무시설",
        "site_area": 1000.0, "building_area": 400.0,
        "total_floor_area": 2000.0, "floor_area_above": 2000.0,
        "floors_above": 5, "floors_below": 1, "height": 18.0,
    }
    result = await engine._diagnose(req, _land("제2종일반주거지역"), save_history=False, skip_ai=True)
    assert result["results"]["건폐율"]["limit_pct"] == 60
    assert result["results"]["용적률"]["limit_pct"] == 250
