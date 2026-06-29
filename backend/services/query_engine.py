"""자연어 질의 엔진 — Claude API 기반.

진단 컨텍스트(주소·용도지역·현재 시나리오·최근 결과)를 함께 전달하여
"이 대지에 근생 6층 지으면 주차 몇 대?" 같은 질문에 조문 근거와 함께 답변.
"""
from __future__ import annotations

import json
import logging

from services.graph_client import fetch_law_bodies
from services.llm_client import LLMClient

logger = logging.getLogger(__name__)

# 조문 원문 그라운딩 컨텍스트 상한 (토큰 폭주·LLM 타임아웃 방지)
_MAX_BODIES = 10          # 본문 주입 조문 최대 개수
_MAX_BODY_CHARS = 900     # 조문당 본문 길이 상한(글자)


_SYSTEM_PROMPT = """\
당신은 한국 건축법·국토계획법·주차장법·소방법 전문가이자
현장 설계 컨설턴트입니다.

TASK: 사용자의 자연어 질문에 대해 다음을 만족하는 답변을 작성하세요.
- 정확한 조문 인용 (예: "건축법 제55조에 따르면 ...")
- 모호한 경우 가정을 명시
- 진단 컨텍스트(현재 시나리오 + 최근 진단 결과)가 있으면 그 수치를 우선 참조
- 컨텍스트에 "적용 조문(진단 엔진 확정)" 목록이 있으면, citations는 그 목록의
  조문명을 그대로 우선 사용 (진단 엔진이 결정론적으로 산정한 정답 조문임).
  목록 밖 조문을 추가로 인용할 때만 본인 판단으로 보강.
- 컨텍스트에 "조문 원문" 블록이 있으면, 그 조문의 **내용·문구는 반드시 제공된
  원문에 근거**해 인용하고 원문에 없는 내용을 지어내지 마세요. 원문이 제공되지
  않은 조문의 본문을 인용해야 하면 "원문 미확보 — 법제처 확인 필요"로 명시.
- 컨텍스트와 모순되는 가정은 사용 금지
- 추측 금지 — 근거 없는 부분은 "법조문상 명시 없음, 추가 확인 필요"로
- 한국어 존댓말, 3~6문장으로 간결하게
- 마지막 줄에 근거 조문 목록 (예: "근거: 건축법 제55조, 국토계획법 시행령 별표")

- 조문 원문 인용은 질문과 직접 관련된 1~2개 조문으로 제한 (무관한 조문 장황 나열 금지)

출력은 반드시 JSON 한 덩어리만:
주의: "answer" 값 안에서는 큰따옴표(") 대신 홑따옴표(') 또는 「」 사용 (JSON 파손 방지)
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

        applied_refs = _collect_law_refs(current_result)
        # graph 에서 적용 조문 본문 확보(있으면 그라운딩, 없으면 degrade)
        bodies = await fetch_law_bodies([r["name"] for r in applied_refs])
        context = self._build_context(
            address, zone_use, building_info, current_result, applied_refs, bodies
        )
        user_prompt = _USER_TEMPLATE.format(question=question.strip(), context=context)

        data = await self._llm.judge_json(_SYSTEM_PROMPT, user_prompt, max_tokens=4096)
        if data is None:
            return {
                "answer": "AI 응답 파싱 실패 — 잠시 후 다시 시도해주세요.",
                "citations": [],
                "confidence": "low",
                "follow_ups": [],
            }

        # citations URL 보강 — 진단 엔진 확정 조문의 정확한 URL을 최우선 사용
        ref_urls = {r["name"]: r["url"] for r in applied_refs if r.get("url")}
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
                url = ref_urls.get(name) or _law_url(name)
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
        applied_refs: list[dict] | None = None,
        bodies: dict[str, dict] | None = None,
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
        if applied_refs:
            parts.append("- 적용 조문(진단 엔진 확정):")
            for r in applied_refs:
                parts.append(f"  · {r['name']}")
        if bodies:
            parts.append(
                "- 조문 원문(graph 제공 — 아래 본문에 있는 내용만 그대로 인용):"
            )
            for name, b in list(bodies.items())[:_MAX_BODIES]:
                content = (b.get("content") or "").strip()
                if len(content) > _MAX_BODY_CHARS:
                    content = content[:_MAX_BODY_CHARS] + " …(이하 생략)"
                # 본문 내 ASCII 큰따옴표 → 홑따옴표: LLM이 그대로 echo해도 JSON 미파손
                content = content.replace('"', "'")
                parts.append(f"  ▸ {name}\n    {content}")
        if not parts:
            return "(추가 컨텍스트 없음 — 일반론 답변)"
        return "\n".join(parts)


def _collect_law_refs(result: dict | None) -> list[dict]:
    """진단 결과 각 카테고리의 law_refs를 평탄화·중복 제거.

    계산기가 결정론적으로 산정한 정답 조문(name + 정확한 law.go.kr URL)을
    LLM 컨텍스트와 citation URL 보강에 재사용한다.
    """
    if not result or not isinstance(result, dict):
        return []
    refs: list[dict] = []
    seen: set[str] = set()
    categories = result.get("results", {}) or {}
    for r in categories.values():
        if not isinstance(r, dict):
            continue
        for ref in r.get("law_refs", []) or []:
            if not isinstance(ref, dict):
                continue
            name = str(ref.get("name", "")).strip()
            if not name or name in seen:
                continue
            seen.add(name)
            refs.append({"name": name, "url": str(ref.get("url", "")).strip()})
    return refs


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
