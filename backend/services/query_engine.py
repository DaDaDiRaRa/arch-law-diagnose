"""자연어 질의 엔진 — Claude API 기반.

진단 컨텍스트(주소·용도지역·현재 시나리오·최근 결과)를 함께 전달하여
"이 대지에 근생 6층 지으면 주차 몇 대?" 같은 질문에 조문 근거와 함께 답변.
"""
from __future__ import annotations

import json
import logging

from services.llm_client import LLMClient

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """\
당신은 한국 건축법·국토계획법·주차장법·소방법 전문가이자
현장 설계 컨설턴트입니다.

TASK: 사용자의 자연어 질문에 대해 다음을 만족하는 답변을 작성하세요.
- 정확한 조문 인용 (예: "건축법 제55조에 따르면 ...")
- 모호한 경우 가정을 명시
- 진단 컨텍스트(현재 시나리오 + 최근 진단 결과)가 있으면 그 수치를 우선 참조
- 컨텍스트와 모순되는 가정은 사용 금지
- 추측 금지 — 근거 없는 부분은 "법조문상 명시 없음, 추가 확인 필요"로
- 한국어 존댓말, 3~6문장으로 간결하게
- 마지막 줄에 근거 조문 목록 (예: "근거: 건축법 제55조, 국토계획법 시행령 별표")

출력은 반드시 JSON 한 덩어리만:
{
  "answer": "<본문 답변>",
  "citations": [
    {"name": "<조문명>", "url": "<law.go.kr URL or 빈 문자열>"}
  ],
  "confidence": "high" | "medium" | "low",
  "follow_ups": ["<추가 검토 권장 항목 ...>"]
}
전후 설명 텍스트·코드펜스 금지.
"""


_USER_TEMPLATE = """\
[질문]
{question}

[컨텍스트]
{context}
"""


def _law_url(name: str) -> str:
    """조문명 → 법제처 URL 추정."""
    if not name:
        return ""
    base = "https://www.law.go.kr/법령/"
    # 단순 키워드 매핑 — 실패 시 빈 문자열 (프론트가 안전하게 처리)
    if "건축법 시행령" in name:
        return base + "건축법시행령"
    if "건축법" in name:
        return base + "건축법"
    if "국토계획법 시행령" in name or "국토의계획" in name:
        return base + "국토의계획및이용에관한법률시행령"
    if "국토계획법" in name:
        return base + "국토의계획및이용에관한법률"
    if "주차장법 시행령" in name:
        return base + "주차장법시행령"
    if "주차장법" in name:
        return base + "주차장법"
    if "소방시설" in name:
        return base + "소방시설설치및관리에관한법률"
    return ""


class QueryEngine:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def answer(
        self,
        question: str,
        *,
        address: str | None = None,
        zone_use: str | None = None,
        building_info: dict | None = None,
        current_result: dict | None = None,
    ) -> dict:
        """질문 + 컨텍스트 → 구조화된 답변."""
        if not self._llm.available:
            return {
                "answer": "ANTHROPIC_API_KEY 미설정 — AI 자연어 질의 비활성화. 백엔드 환경변수 확인 필요.",
                "citations": [],
                "confidence": "low",
                "follow_ups": [],
            }

        context = self._build_context(address, zone_use, building_info, current_result)
        user_prompt = _USER_TEMPLATE.format(question=question.strip(), context=context)

        data = await self._llm.judge_json(_SYSTEM_PROMPT, user_prompt, max_tokens=2048)
        if data is None:
            return {
                "answer": "AI 응답 파싱 실패 — 잠시 후 다시 시도해주세요.",
                "citations": [],
                "confidence": "low",
                "follow_ups": [],
            }

        # citations URL 보강
        citations_raw = data.get("citations", []) or []
        citations: list[dict] = []
        for c in citations_raw:
            if not isinstance(c, dict):
                continue
            name = str(c.get("name", "")).strip()
            url = str(c.get("url", "")).strip()
            if not name:
                continue
            if not url:
                url = _law_url(name)
            citations.append({"name": name, "url": url})

        return {
            "answer": str(data.get("answer", "")).strip(),
            "citations": citations,
            "confidence": data.get("confidence", "medium"),
            "follow_ups": [str(f) for f in (data.get("follow_ups", []) or []) if f],
        }

    @staticmethod
    def _build_context(
        address: str | None,
        zone_use: str | None,
        building_info: dict | None,
        current_result: dict | None,
    ) -> str:
        """LLM에 전달할 컨텍스트 블록 구성."""
        parts: list[str] = []
        if address:
            parts.append(f"- 주소: {address}")
        if zone_use:
            parts.append(f"- 용도지역: {zone_use}")
        if building_info:
            parts.append("- 현재 검토 건물 정보:")
            for k, v in building_info.items():
                if v is None or v == "":
                    continue
                parts.append(f"  · {k}: {v}")
        if current_result and isinstance(current_result, dict):
            summary = _summarize_result(current_result)
            if summary:
                parts.append("- 최근 진단 결과 요약:")
                parts.append(summary)
        if not parts:
            return "(추가 컨텍스트 없음 — 일반론 답변)"
        return "\n".join(parts)


def _summarize_result(result: dict) -> str:
    """진단 결과를 LLM 입력용으로 요약."""
    lines: list[str] = []
    overall = result.get("overall_score")
    signal = result.get("signal")
    if overall is not None and signal:
        lines.append(f"  · 종합 {overall}/10 ({signal})")

    categories = result.get("results", {}) or {}
    for cat, r in categories.items():
        if not isinstance(r, dict):
            continue
        pass_val = r.get("pass")
        status = "적합" if pass_val is True else "초과" if pass_val is False else "확인필요"
        bits: list[str] = [status]
        if r.get("actual_pct") is not None and r.get("limit_pct") is not None:
            bits.append(f"{r['actual_pct']}%/{r['limit_pct']}%")
        elif r.get("required_pct") is not None:
            actual = r.get("actual_pct")
            if actual is not None:
                bits.append(f"{actual}%/의무 {r['required_pct']}%")
            else:
                bits.append(f"의무 {r['required_pct']}%")
        elif r.get("required_spaces") is not None:
            provided = r.get("provided_spaces")
            bits.append(f"법정 {r['required_spaces']}대" + (f"/계획 {provided}대" if provided else ""))
        elif r.get("actual_height_m") is not None:
            bits.append(f"{r['actual_height_m']}m")
        lines.append(f"  · {cat}: " + " ".join(bits))

    return "\n".join(lines)
