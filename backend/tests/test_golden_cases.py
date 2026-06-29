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
        "height": inp["height"],
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
            assert card["actual_pct"] == exp["actual_pct"], (
                f"[{case['id']}] {cat} 산정값 {card['actual_pct']} != 기대 {exp['actual_pct']}"
            )
        if "limit_pct" in exp:
            assert card["limit_pct"] == exp["limit_pct"], (
                f"[{case['id']}] {cat} 한도 {card['limit_pct']} != 기대 {exp['limit_pct']}"
            )
        if "pass" in exp:
            assert card["pass"] is exp["pass"], (
                f"[{case['id']}] {cat} pass {card['pass']} != 기대 {exp['pass']}"
            )
