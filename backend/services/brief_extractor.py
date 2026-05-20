"""발주처 지침서 PDF 추출기.

PDF 업로드 → 텍스트 추출(pdfplumber) → LLM 파싱 → 설계 조건 JSON 반환.

추출 대상 조건:
  - 건폐율 제한 (%)
  - 용적률 제한 (%)
  - 최고 층수
  - 최고 높이 (m)
  - 조경 최소 비율 (%)
  - 주차 최소 대수
  - 허용·의무 도입 용도
  - 금지 용도
  - 기타 특수 조건 (자유 텍스트)
"""
from __future__ import annotations

import io
import logging
import re
from typing import Any

import pdfplumber

logger = logging.getLogger(__name__)

# 페이지당 최대 문자 수 — LLM 컨텍스트 절약
_MAX_CHARS_PER_PAGE = 3000
# 총 전달 최대 문자 수
_MAX_TOTAL_CHARS = 20000

_EXTRACT_PROMPT = """당신은 건축 설계공모·인허가 발주처 지침서에서 설계 조건을 추출하는 전문가입니다.

아래 지침서 원문에서 다음 항목들을 추출하여 **JSON만** 반환하세요.
값이 명시되지 않은 항목은 null로 표기하세요. 수치 단위를 반드시 확인하세요.

추출 항목:
- max_bcr_pct: 건폐율 제한 (숫자, %, null 가능)
- max_far_pct: 용적률 제한 (숫자, %, null 가능)
- max_floors: 최고 층수 (정수, null 가능)
- max_height_m: 최고 높이 (숫자, m 단위, null 가능)
- min_landscape_pct: 조경 최소 비율 (숫자, %, null 가능)
- min_parking_spaces: 주차 최소 대수 (정수, null 가능)
- required_uses: 의무 도입 용도 목록 (문자열 배열, 없으면 [])
- prohibited_uses: 금지 용도 목록 (문자열 배열, 없으면 [])
- special_conditions: 기타 주요 설계 조건 (문자열 배열, 없으면 [])
- source_excerpt: 각 수치의 근거가 된 원문 핵심 문장 (문자열)

반드시 JSON만 반환하고, 설명·주석 없이 { } 로만 응답하세요.

---
지침서 원문:
{text}
"""


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """pdfplumber로 PDF 텍스트 추출."""
    pages: list[str] = []
    total = 0
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                if total >= _MAX_TOTAL_CHARS:
                    pages.append(f"\n[... 이후 {len(pdf.pages) - i}페이지 생략 ...]")
                    break
                text = page.extract_text() or ""
                text = text[:_MAX_CHARS_PER_PAGE]
                pages.append(f"[p.{i+1}]\n{text}")
                total += len(text)
    except Exception as e:
        logger.warning("PDF 텍스트 추출 실패: %s", e)
        raise ValueError(f"PDF 읽기 실패: {e}") from e

    combined = "\n\n".join(pages)
    if not combined.strip():
        raise ValueError("PDF에서 텍스트를 추출할 수 없습니다. 스캔 이미지 PDF일 수 있습니다.")
    return combined


def parse_conditions_with_llm(text: str, llm_client: Any) -> dict:
    """LLM으로 지침서 텍스트 → 설계 조건 JSON 파싱."""
    prompt = _EXTRACT_PROMPT.format(text=text[:_MAX_TOTAL_CHARS])
    result = llm_client.judge_json(
        prompt=prompt,
        schema_hint={
            "max_bcr_pct": "number|null",
            "max_far_pct": "number|null",
            "max_floors": "integer|null",
            "max_height_m": "number|null",
            "min_landscape_pct": "number|null",
            "min_parking_spaces": "integer|null",
            "required_uses": "array",
            "prohibited_uses": "array",
            "special_conditions": "array",
            "source_excerpt": "string",
        },
    )
    return _validate(result)


def _validate(raw: dict) -> dict:
    """추출 결과 타입 보정 및 이상값 제거."""
    def to_float(v: Any, lo: float, hi: float) -> float | None:
        try:
            f = float(v)
            return f if lo <= f <= hi else None
        except (TypeError, ValueError):
            return None

    def to_int(v: Any, lo: int, hi: int) -> int | None:
        try:
            i = int(v)
            return i if lo <= i <= hi else None
        except (TypeError, ValueError):
            return None

    def to_list(v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(x) for x in v if x]
        return []

    return {
        "max_bcr_pct": to_float(raw.get("max_bcr_pct"), 1, 100),
        "max_far_pct": to_float(raw.get("max_far_pct"), 1, 2000),
        "max_floors": to_int(raw.get("max_floors"), 1, 200),
        "max_height_m": to_float(raw.get("max_height_m"), 1, 1000),
        "min_landscape_pct": to_float(raw.get("min_landscape_pct"), 0, 100),
        "min_parking_spaces": to_int(raw.get("min_parking_spaces"), 0, 99999),
        "required_uses": to_list(raw.get("required_uses")),
        "prohibited_uses": to_list(raw.get("prohibited_uses")),
        "special_conditions": to_list(raw.get("special_conditions")),
        "source_excerpt": str(raw.get("source_excerpt") or ""),
    }


def extract_from_pdf(pdf_bytes: bytes, llm_client: Any) -> dict:
    """전체 파이프라인: PDF bytes → 설계 조건 dict."""
    text = extract_text_from_pdf(pdf_bytes)
    conditions = parse_conditions_with_llm(text, llm_client)
    conditions["_text_length"] = len(text)
    conditions["_pages_extracted"] = text.count("[p.")
    return conditions
