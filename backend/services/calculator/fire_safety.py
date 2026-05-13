"""설비·소방 계산기 — Claude API 기반 정성 종합 판단.

다루는 항목 (개략):
- 스프링클러·옥내소화전 (소방시설법 시행령 별표 4)
- 방화구획 (건축법 시행령 제46조)
- 비상용 승강기·승강기 의무 (건축법 시행령 제89조·제90조)
- 직통계단·피난계단 (건축법 시행령 제34조·제35조)

V1: 입력 정보(용도/층수/높이/연면적)만으로 AI 종합 판단 → confidence 3.
API 키 미설정 시 graceful degrade (수동 검토 안내).
"""
from __future__ import annotations

import logging

from services.llm_client import LLMClient

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """\
당신은 한국 건축법·소방법 검토 전문가입니다.

TASK: 입력 건물 정보 기반으로 설비·소방 의무사항을 종합 판단.

대상 법규:
- 건축법 시행령 제34조·제35조 (직통계단·피난계단)
- 건축법 시행령 제46조 (방화구획)
- 건축법 시행령 제89조·제90조 (승강기·비상용 승강기)
- 소방시설 설치 및 관리에 관한 법률 시행령 별표 4 (스프링클러·옥내소화전 등)
- 다중이용업소 관련 (해당 시)

규칙:
- 추측 금지. 명확한 법적 근거가 있을 때만 의무 항목 명시
- 정확한 기준 수치 인용 (예: "11층 이상 또는 연면적 5,000㎡ 이상")
- 입력만으로 판단 불가한 항목(무창층, 거실 수, 객실 수 등)은 status="needs_review"
- 모호한 경우 warnings 에 기재
- 출력은 반드시 valid JSON 한 덩어리만. 전후 설명 텍스트·코드펜스 금지.

OUTPUT_SCHEMA (반드시 준수):
{
  "items": [
    {
      "name": "<항목명 예: 스프링클러>",
      "status": "required" | "not_required" | "needs_review",
      "basis": "<법조문 예: 소방시설법 시행령 별표 4 제1호>",
      "note": "<왜 그렇게 판단했는지 한 문장>"
    }
  ],
  "overall_pass": true | false | null,
  "score": <0~10 숫자>,
  "summary": "<2~3문장 종합 의견>",
  "warnings": ["<추가 검토 필요 사항>"]
}

판정 기준:
- needs_review 가 없고 의무 항목이 모두 충족 가정 가능 → overall_pass=true, score 8~10
- 추가 검토 항목 多 또는 일부 의무 미충족 가정 → overall_pass=null, score 5~7
- 명백한 미달(예: 30층 건물에 스프링클러 미계획 등) → overall_pass=false, score 0~3
"""


_USER_TEMPLATE = """\
[건물 정보]
- 용도: {building_use}
- 지상 층수: {floors_above}층
- 지하 층수: {floors_below}층
- 건물 높이: {height}m
- 연면적: {total_floor_area:.0f}㎡
- 세대수: {units}

위 건물의 설비·소방 의무사항을 종합 판단하여 명시된 JSON 스키마로만 응답하세요.
"""


async def calculate(
    llm: LLMClient,
    *,
    building_use: str,
    floors_above: int,
    floors_below: int,
    height: float,
    total_floor_area: float,
    units: int | None = None,
) -> dict:
    """설비·소방 AI 종합 판단."""
    law_refs = _law_refs()

    if not llm.available:
        return _fallback(law_refs, "ANTHROPIC_API_KEY 미설정 — AI 판단 비활성화, 수동 검토 필요")

    user_prompt = _USER_TEMPLATE.format(
        building_use=building_use,
        floors_above=floors_above,
        floors_below=floors_below,
        height=height,
        total_floor_area=total_floor_area,
        units=units if units is not None else "N/A",
    )

    data = await llm.judge_json(_SYSTEM_PROMPT, user_prompt)
    if data is None:
        return _fallback(law_refs, "AI 응답 파싱 실패 — 수동 검토 필요")

    items_raw = data.get("items", []) or []
    items: list[dict] = [it for it in items_raw if isinstance(it, dict)]

    overall_pass = data.get("overall_pass")
    pass_val: bool | None = overall_pass if isinstance(overall_pass, bool) else None

    score_raw = data.get("score")
    score: float | None
    try:
        score = float(score_raw) if score_raw is not None else None
        if score is not None:
            score = max(0.0, min(10.0, round(score, 1)))
    except (TypeError, ValueError):
        score = None

    summary = str(data.get("summary", "")).strip()
    warnings = [str(w) for w in (data.get("warnings", []) or []) if w]

    return {
        "category": "설비_소방",
        "pass": pass_val,
        "score": score,
        "confidence": 3,
        "items": items,
        "summary": summary,
        "warnings": warnings,
        "source": f"AI 종합 판단 ({llm.model}) + 건축법 시행령·소방시설법",
        "law_refs": law_refs,
        "notes": _notes(summary, items, warnings),
    }


def _notes(summary: str, items: list[dict], warnings: list[str]) -> str:
    parts: list[str] = []
    if summary:
        parts.append(summary)
    if items:
        bullets = " · ".join(
            f"{it.get('name', '?')}({_status_kor(it.get('status'))})"
            for it in items
        )
        if bullets:
            parts.append(bullets)
    if warnings:
        parts.append("주의: " + "; ".join(warnings))
    return " / ".join(parts) if parts else "AI 응답 없음"


def _status_kor(s) -> str:
    return {
        "required": "의무",
        "not_required": "면제",
        "needs_review": "검토필요",
    }.get(s or "", "미정")


def _fallback(law_refs: list[dict], note: str) -> dict:
    return {
        "category": "설비_소방",
        "pass": None,
        "score": None,
        "confidence": 1,
        "items": [],
        "summary": "",
        "warnings": [],
        "source": "건축법 시행령 + 소방시설법 (AI 미사용)",
        "law_refs": law_refs,
        "notes": note,
    }


def skipped_result(note: str = "AI 재판단 생략") -> dict:
    """What-if/시나리오 비교에서 AI 호출을 건너뛸 때 사용."""
    return _fallback(_law_refs(), note)


def _law_refs() -> list[dict]:
    return [
        {
            "name": "건축법 시행령 제46조 (방화구획)",
            "url": "https://www.law.go.kr/법령/건축법시행령/제46조",
        },
        {
            "name": "건축법 시행령 제89조 (승강기)",
            "url": "https://www.law.go.kr/법령/건축법시행령/제89조",
        },
        {
            "name": "건축법 시행령 제90조 (비상용 승강기)",
            "url": "https://www.law.go.kr/법령/건축법시행령/제90조",
        },
        {
            "name": "소방시설 설치 및 관리에 관한 법률 시행령 별표 4",
            "url": "https://www.law.go.kr/법령/소방시설설치및관리에관한법률시행령",
        },
    ]
