"""llm_client._extract_json — JSON 추출·자동복구 테스트."""
from __future__ import annotations

from services.llm_client import _extract_json


def test_plain_json():
    assert _extract_json('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_fenced_json():
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_control_chars_in_string():
    """문자열 값 안의 리터럴 줄바꿈/탭 허용(strict=False).

    조문 원문 등 멀티라인 텍스트를 모델이 이스케이프 없이 echo해도 파싱돼야 함.
    """
    raw = '{"answer": "제56조(용적률)\n다만 완화 규정\t참조", "confidence": "high"}'
    result = _extract_json(raw)
    assert result is not None
    assert result["confidence"] == "high"
    assert "다만 완화 규정" in result["answer"]


def test_trailing_comma_recovered():
    assert _extract_json('{"a": 1, "b": 2,}') == {"a": 1, "b": 2}


def test_truncated_json_recovered():
    """응답 truncation — 마지막 완전한 } 까지로 복구."""
    raw = '{"a": 1, "b": 2} 뒤에 잘린 쓰레기 {"c":'
    assert _extract_json(raw) == {"a": 1, "b": 2}


def test_no_json_returns_none():
    assert _extract_json("JSON이 전혀 없는 일반 텍스트") is None
