"""public_certification · bf_certification · multi_use · query_engine 테스트.

외부 의존 없는 3개 계산기(결정론적)와 LLM 의존 1개(AsyncMock).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.calculator.bf_certification import calculate as calc_bf
from services.calculator.multi_use import classify
from services.calculator.public_certification import calculate as calc_pub
from services.query_engine import QueryEngine


# ════════════════════════════════════════════════════════════════════════════
# 1. public_certification
# ════════════════════════════════════════════════════════════════════════════

def _item_names(result: dict) -> list[str]:
    return [i["name"] for i in result.get("items", [])]


class TestPublicCertification:
    def test_non_public_applicant(self):
        r = calc_pub(building_use="업무시설", applicant_type="민간")
        assert r["pass"] is True
        assert r["score"] == 10.0
        assert r["items"] == []

    def test_public_gfa_zero(self):
        """연면적 0 → 신재생+생태면적률 2종 + 판정불가 note."""
        r = calc_pub(building_use="업무시설", applicant_type="공공기관", gross_floor_area=0)
        assert r["pass"] is None
        assert r["score"] == 5.0
        names = _item_names(r)
        assert "신재생에너지 공급의무비율" in names
        assert "생태면적률" in names
        assert "녹색건축물 인증" not in names
        assert "미입력" in r["notes"]

    def test_public_small_gfa_under_1000(self):
        """GFA < 1000 → 신재생+생태면적률만 (ZEB·Green·BEMS 없음)."""
        r = calc_pub(building_use="업무시설", applicant_type="공공기관", gross_floor_area=500)
        names = _item_names(r)
        assert "녹색건축물 인증" not in names
        assert "제로에너지건축물 인증" not in names
        assert "건축물 에너지관리시스템 (BEMS)" not in names
        assert "신재생에너지 공급의무비율" in names

    def test_public_medium_gfa_mandatory_use(self):
        """1000 ≤ GFA < 3000 + 의무용도(업무시설) → ZEB 포함."""
        r = calc_pub(building_use="업무시설", applicant_type="공공기관", gross_floor_area=2000)
        names = _item_names(r)
        assert any("제로에너지건축물" in n for n in names)
        assert "녹색건축물 인증" not in names
        assert "건축물 에너지관리시스템 (BEMS)" not in names

    def test_public_medium_gfa_exempt_use(self):
        """1000 ≤ GFA < 3000 + 면제용도(공장) → ZEB 없음."""
        r = calc_pub(building_use="공장", applicant_type="공공기관", gross_floor_area=2000)
        names = _item_names(r)
        assert not any("제로에너지건축물" in n for n in names)

    def test_public_large_gfa_mandatory_use(self):
        """GFA ≥ 3000 + 의무용도 → Green + ZEB + BEMS 모두 포함."""
        r = calc_pub(building_use="업무시설", applicant_type="공공기관", gross_floor_area=5000)
        names = _item_names(r)
        assert "녹색건축물 인증" in names
        assert any("제로에너지건축물" in n for n in names)
        assert "건축물 에너지관리시스템 (BEMS)" in names

    def test_public_large_gfa_exempt_use(self):
        """GFA ≥ 3000 + 면제용도(창고) → Green + BEMS 있지만 ZEB 없음."""
        r = calc_pub(building_use="창고시설", applicant_type="공공기관", gross_floor_area=5000)
        names = _item_names(r)
        assert "녹색건축물 인증" in names
        assert "건축물 에너지관리시스템 (BEMS)" in names
        assert not any("제로에너지건축물 인증" == n for n in names)

    def test_renewable_ratio_by_year(self):
        r24 = calc_pub(building_use="업무시설", applicant_type="공공기관",
                       gross_floor_area=1500, permit_year=2024)
        r26 = calc_pub(building_use="업무시설", applicant_type="공공기관",
                       gross_floor_area=1500, permit_year=2026)
        r30 = calc_pub(building_use="업무시설", applicant_type="공공기관",
                       gross_floor_area=1500, permit_year=2030)

        def _ratio(r: dict) -> str:
            return next(i["required_level"] for i in r["items"]
                        if "신재생에너지" in i["name"])

        assert "34%" in _ratio(r24)
        assert "36%" in _ratio(r26)
        assert "40%" in _ratio(r30)

    def test_zeb_unknown_use(self):
        """목록 미등재 용도 → '확인 필요' 아이템 추가."""
        r = calc_pub(building_use="기타시설", applicant_type="공공기관", gross_floor_area=2000)
        names = _item_names(r)
        assert any("확인 필요" in n for n in names)


# ════════════════════════════════════════════════════════════════════════════
# 2. bf_certification
# ════════════════════════════════════════════════════════════════════════════

class TestBfCertification:
    def test_non_public_non_mandatory(self):
        r = calc_bf(building_use="공장", applicant_type="민간")
        assert r["pass"] is True
        assert r["score"] == 10.0
        assert r["required_level"] is None

    def test_public_institution(self):
        r = calc_bf(building_use="업무시설", applicant_type="공공기관")
        assert r["pass"] is None
        assert r["score"] == 5.0
        assert "우수" in r["required_level"]

    def test_mandatory_use_private(self):
        """교육연구시설 민간 → 일반 등급 의무."""
        r = calc_bf(building_use="교육연구시설", applicant_type="민간")
        assert r["pass"] is None
        assert "일반" in r["required_level"]

    def test_medical_use_mandatory(self):
        r = calc_bf(building_use="의료시설", applicant_type="민간")
        assert r["pass"] is None

    def test_childcare_guideline(self):
        """어린이집 → 어린이집 전용 가이드라인 추가."""
        r = calc_bf(building_use="노유자시설(어린이집)", applicant_type="공공기관")
        assert "어린이집" in r["guidelines"]

    def test_cultural_assembly_public(self):
        r = calc_bf(building_use="문화및집회시설", applicant_type="공공기관")
        assert r["pass"] is None
        assert "우수" in r["required_level"]


# ════════════════════════════════════════════════════════════════════════════
# 3. multi_use
# ════════════════════════════════════════════════════════════════════════════

class TestMultiUse:
    def test_multi_use_by_area(self):
        r = classify("문화및집회시설", total_floor_area=6000, floors_above=5)
        assert r["classification"] == "다중이용건축물"

    def test_multi_use_by_floors(self):
        """16층 이상은 용도·면적 무관."""
        r = classify("단독주택", total_floor_area=200, floors_above=16)
        assert r["classification"] == "다중이용건축물"

    def test_quasi_multi_use_main_uses(self):
        """판매시설 1000㎡ < 5000㎡ → 준다중이용."""
        r = classify("판매시설", total_floor_area=2000, floors_above=3)
        assert r["classification"] == "준다중이용건축물"

    def test_quasi_multi_use_extra_uses(self):
        """교육연구시설(준다중이용 추가 용도) 1000㎡ → 준다중이용."""
        r = classify("교육연구시설", total_floor_area=1500, floors_above=3)
        assert r["classification"] == "준다중이용건축물"

    def test_not_applicable(self):
        r = classify("단독주택", total_floor_area=200, floors_above=2)
        assert r["classification"] == "해당없음"
        assert r["implications"] == []

    def test_boundary_5000_multi(self):
        r = classify("판매시설", total_floor_area=5000, floors_above=5)
        assert r["classification"] == "다중이용건축물"

    def test_boundary_1000_quasi(self):
        r = classify("장례시설", total_floor_area=1000, floors_above=3)
        assert r["classification"] == "준다중이용건축물"

    def test_quasi_under_1000_not_applicable(self):
        r = classify("교육연구시설", total_floor_area=999, floors_above=3)
        assert r["classification"] == "해당없음"

    def test_transport_caveat(self):
        """운수시설 → 여객용 한정 주석 포함."""
        r = classify("운수시설", total_floor_area=6000, floors_above=5)
        assert "여객용" in r["notes"]

    def test_medical_not_hospital_caveat(self):
        """의료시설(종합병원 아님) → 종합병원 한정 주석 포함."""
        r = classify("의료시설", total_floor_area=6000, floors_above=5)
        assert "종합병원" in r["notes"]

    def test_pass_is_none(self):
        """정보 카드 — pass·score 는 항상 None."""
        for cls_val in ("다중이용건축물", "준다중이용건축물", "해당없음"):
            r = classify("판매시설", total_floor_area=6000, floors_above=5)
            assert r["pass"] is None
            assert r["score"] is None
            break


# ════════════════════════════════════════════════════════════════════════════
# 4. query_engine
# ════════════════════════════════════════════════════════════════════════════

def _make_llm(available: bool = True, return_value=None) -> MagicMock:
    llm = MagicMock()
    llm.available = available
    llm.judge_json = AsyncMock(return_value=return_value)
    return llm


class TestQueryEngine:
    @pytest.mark.asyncio
    async def test_llm_unavailable(self):
        engine = QueryEngine(_make_llm(available=False))
        result = await engine.answer("건폐율이 뭐예요?")
        assert result["confidence"] == "low"
        assert "ANTHROPIC_API_KEY" in result["answer"]
        assert result["citations"] == []

    @pytest.mark.asyncio
    async def test_llm_success(self):
        llm_response = {
            "answer": "건축법 제55조에 따르면 건폐율은 ...",
            "citations": [{"name": "건축법 제55조", "url": ""}],
            "confidence": "high",
            "follow_ups": ["조례 기준 추가 확인 권장"],
        }
        engine = QueryEngine(_make_llm(return_value=llm_response))
        result = await engine.answer("건폐율이 뭐예요?", zone_use="제2종일반주거지역")
        assert "건축법" in result["answer"]
        assert result["confidence"] == "high"
        assert len(result["citations"]) == 1
        assert len(result["follow_ups"]) == 1

    @pytest.mark.asyncio
    async def test_llm_parse_failure(self):
        """judge_json → None 이면 파싱 실패 응답."""
        engine = QueryEngine(_make_llm(return_value=None))
        result = await engine.answer("주차 기준은?")
        assert result["confidence"] == "low"
        assert "파싱 실패" in result["answer"]

    @pytest.mark.asyncio
    async def test_citation_url_autofill(self):
        """URL 없는 인용 → _law_url 로 자동 채움."""
        llm_response = {
            "answer": "건축법에 따르면...",
            "citations": [
                {"name": "건축법 제55조", "url": ""},
                {"name": "주차장법 시행령 별표", "url": ""},
            ],
            "confidence": "medium",
            "follow_ups": [],
        }
        engine = QueryEngine(_make_llm(return_value=llm_response))
        result = await engine.answer("주차 기준은?")
        urls = [c["url"] for c in result["citations"]]
        assert any("건축법" in u for u in urls)
        assert any("주차장법" in u for u in urls)

    @pytest.mark.asyncio
    async def test_context_passed_to_llm(self):
        """address·zone_use·building_info 제공 시 LLM 에 전달되는지 확인."""
        llm = _make_llm(return_value={
            "answer": "답변", "citations": [], "confidence": "medium", "follow_ups": [],
        })
        engine = QueryEngine(llm)
        await engine.answer(
            "몇 층까지 지을 수 있나요?",
            address="서울 영등포구",
            zone_use="제2종일반주거지역",
            building_info={"gross_floor_area": 3000},
        )
        call_args = llm.judge_json.call_args
        user_prompt = call_args[0][1]  # 두 번째 positional arg
        assert "영등포구" in user_prompt
        assert "제2종일반주거지역" in user_prompt

    @pytest.mark.asyncio
    async def test_applied_refs_injected_into_prompt(self):
        """진단 결과의 law_refs가 '적용 조문' 블록으로 프롬프트에 주입되는지."""
        llm = _make_llm(return_value={
            "answer": "답변", "citations": [], "confidence": "medium", "follow_ups": [],
        })
        engine = QueryEngine(llm)
        current_result = {
            "results": {
                "건폐율": {"pass": True, "law_refs": [
                    {"name": "건축법 제55조 (건폐율)", "url": "https://www.law.go.kr/a"},
                ]},
            },
        }
        await engine.answer("왜 적합인가요?", current_result=current_result)
        user_prompt = llm.judge_json.call_args[0][1]
        assert "적용 조문(진단 엔진 확정)" in user_prompt
        assert "건축법 제55조 (건폐율)" in user_prompt

    @pytest.mark.asyncio
    async def test_citation_url_from_diagnosis_refs(self):
        """LLM citation의 빈 URL은 진단 엔진 확정 조문의 정확한 URL로 보강."""
        llm_response = {
            "answer": "건축법 제55조에 따라...",
            "citations": [{"name": "건축법 제55조 (건폐율)", "url": ""}],
            "confidence": "high",
            "follow_ups": [],
        }
        engine = QueryEngine(_make_llm(return_value=llm_response))
        current_result = {
            "results": {
                "건폐율": {"pass": True, "law_refs": [
                    {"name": "건축법 제55조 (건폐율)", "url": "https://www.law.go.kr/exact"},
                ]},
            },
        }
        result = await engine.answer("왜 적합?", current_result=current_result)
        assert result["citations"][0]["url"] == "https://www.law.go.kr/exact"
