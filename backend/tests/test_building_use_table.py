"""건축법 시행령 [별표 1] 전사본 + 시설용도 감지 회귀.

배경(2026-08-28): `_BUILDING_USES` 가 손으로 적은 18종이라 운수·수련·자동차관련·
방송통신·장례·야영장 등 **13개 용도군을 아예 모르고 있었다**. 그런 용도의 공모가
오면 어휘가 정확해도 후보 0 이 된다. 별표1(29개 용도군)을 전사해 해결.

전사본 자체의 현행 일치는 `scripts/verify_building_use_seed.py`(네트워크)가 본다.
여기서는 **파서 규칙과 감지 동작**만 고정한다(네트워크 0).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from services import building_use_table as but
from services.brief_importer import (
    _detect_building_uses,
    _facility_use_hints,
    _use_vocab,
)

_SEED = Path(__file__).parent.parent / "config" / "building_use_seed.json"


# ── 전사본 ───────────────────────────────────────────────────────────────────
def test_seed_has_29_groups():
    """별표1 용도군은 29개. 숫자가 바뀌면 별표 구조가 바뀐 것이다."""
    assert len(but.load_seed()["groups"]) == 29


def test_seed_groups_cover_previously_missing():
    """예전 18종에 없던 용도군이 실제로 들어왔는가."""
    groups = {g.replace(" ", "") for g in but.use_groups()}
    for g in ("운수시설", "수련시설", "자동차관련시설", "방송통신시설",
              "장례시설", "야영장시설", "교정시설", "발전시설"):
        assert g in groups, g


def test_vocab_keeps_legacy_spellings():
    """드롭다운에 있던 표기가 사라지면 기존 brief 매칭이 깨진다."""
    v = _use_vocab()
    for u in ("근린생활시설", "공공업무시설", "제1종근린생활시설", "공동주택"):
        assert u in v


def test_vocab_specific_before_generic():
    """구체적인 용도가 먼저 와야 한 항목당 가장 구체적인 1개가 잡힌다."""
    v = _use_vocab()
    assert v.index("제1종근린생활시설") < v.index("근린생활시설")


# ── 파서 규칙 ────────────────────────────────────────────────────────────────
def test_parser_drops_exclusion_clause_names():
    """괄호 안 '…에 해당하지 아니하는 것을 말한다' 의 **제외 대상**은 시설명이 아니다.

    노유자시설 괄호의 '단독주택, 공동주택'을 긁으면 그것들이 노유자시설 시설명이 된다.
    """
    text = (
        "11. 노유자시설\n"
        "가. 아동 관련 시설(어린이집, 아동복지시설, 그 밖에 이와 비슷한 것으로서 단\n"
        "독주택, 공동주택 및 제1종 근린생활시설에 해당하지 아니하는 것을 말한\n"
        "다)\n"
    )
    p = but.parse_byeolpyo1(text)
    assert "어린이집" in p["names"]
    assert "단독주택" not in p["names"]
    assert "공동주택" not in p["names"]


def test_parser_rejoins_wrapped_words():
    """PDF 는 단어 중간에서 줄을 끊는다 — 공백 없이 이어 붙여야 복원된다."""
    text = "9. 의료시설\n가. 병원(종합병원, 병원, 치과병원, 한방병\n원을 말한다)\n"
    p = but.parse_byeolpyo1(text)
    assert "한방병원" in p["names"]


def test_parser_reads_numbered_subitems():
    """'가.' 뿐 아니라 '1)' 하위항목도 읽어야 한다(오피스텔이 거기 있다)."""
    text = ("14. 업무시설\n나. 일반업무시설: 다음 요건을 갖춘 업무시설을 말한다.\n"
            "2) 오피스텔(업무를 주로 하며 분양하는 것을 말한다)\n")
    p = but.parse_byeolpyo1(text)
    assert "오피스텔" in p["names"]


def test_conditional_names_excluded_from_safe():
    """면적·제외규정에 걸린 이름은 자동 채움 후보가 아니다.

    보건소는 1천㎡ 미만이면 제1종근생, 넘으면 업무시설 — 이름만으론 못 정한다.
    """
    assert "보건소" not in but.safe_names()
    assert "보건소" in but.hint_names()


# ── 감지 동작 ────────────────────────────────────────────────────────────────
def test_detect_uses_byeolpyo_name():
    assert _detect_building_uses(["학교"]) == ["교육연구시설"]
    assert _detect_building_uses(["종합병원"]) == ["의료시설"]
    assert _detect_building_uses(["오피스텔"]) == ["업무시설"]


def test_detect_exact_match_only_for_facility_names():
    """부분매칭 금지 — '세대창고'(아파트 부대 창고)가 창고시설이 되면 안 된다."""
    assert _detect_building_uses(["세대창고"]) == []
    assert _detect_building_uses(["스카이라운지"]) == []


def test_detect_skips_ancillary():
    """부설·부대·부속은 주용도가 아니다. 이게 후보로 잡히면 자동 채움이 꺼진다."""
    assert _detect_building_uses(["어린이집(노유자시설)", "부설주차장"]) == ["노유자시설"]
    assert _detect_building_uses(["부설주차장"]) == []
    assert _detect_building_uses(["부대복리시설"]) == []


def test_detect_unknown_competition_jargon_stays_empty():
    """법에 없는 공모 관용어는 추측하지 않는다."""
    assert _detect_building_uses(["공공커뮤니티지원센터(주민편의시설)"]) == []


def test_hints_are_not_auto_fill():
    """힌트는 facility_use 가 아니다 — 후보 목록과 분리돼야 한다."""
    assert _detect_building_uses(["보건소"]) == []
    hints = _facility_use_hints(["보건소"])
    assert [h["term"] for h in hints] == ["보건소"]
    assert hints[0]["uses"]


def test_hints_skip_already_resolved():
    """자동감지로 정해진 용도를 힌트로 또 보여주지 않는다."""
    assert _facility_use_hints(["어린이집(노유자시설)"]) == []


# ── 프론트 계약 ──────────────────────────────────────────────────────────────
def test_frontend_dropdown_covers_backend_vocab():
    """백엔드가 내보내는 이름이 드롭다운에 없으면 prefill 이 조용히 무시된다."""
    js = (Path(__file__).parents[2] / "frontend" / "src" / "constants"
          / "buildingUses.js").read_text(encoding="utf-8")
    options = set(re.findall(r"'([^']+)'", js))
    missing = [u for u in _use_vocab() if u not in options]
    assert not missing, f"드롭다운에 없는 용도: {missing}"
