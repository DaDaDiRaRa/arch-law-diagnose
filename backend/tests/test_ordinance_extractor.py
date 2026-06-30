"""조례 수치 추출기 — 한글 혼합 수사 파싱 회귀.

법정 한도 재현 감사(scripts/audit_legal_limit_reproduction)에서 조례 DB 보강을
위해 seed_ordinances 를 돌리다 발견한 버그를 고정한다: 부산 도시계획조례
"중심상업지역 : 1천300퍼센트"(=1,300%)를 과거 regex 가 300% 로 오인했다.
"""
from __future__ import annotations

import pytest

from services.ordinance_extractor import _kr_numeral, _parse_value


@pytest.mark.parametrize(
    "token,expected",
    [
        ("60", 60),
        ("1천", 1000),       # 일반상업 "1천퍼센트"
        ("1천300", 1300),    # ← 중심상업 "1천300퍼센트" (회귀 핵심)
        ("1천500", 1500),    # 중심상업 서울
        ("1천5백", 1500),    # 천+백 혼합 표기
        ("2천", 2000),
        ("800", 800),
        ("1,300", 1300),     # 콤마 표기
        ("99.5", 99.5),      # 소수
    ],
)
def test_kr_numeral(token, expected):
    assert _kr_numeral(token) == pytest.approx(expected)


@pytest.mark.parametrize(
    "line,expected",
    [
        ("7. 중심상업지역 : 1천300퍼센트 이하", 1300),   # 버그 재현 라인(부산)
        ("7. 중심상업지역 : 1천 300퍼센트 이하", 1300),  # 천 뒤 공백 변종(대구)
        ("8. 일반상업지역 : 1천 퍼센트 이하", 1000),     # 천 뒤 공백
        ("8. 일반상업지역 : 1천퍼센트 이하", 1000),
        ("9. 근린상업지역 : 700퍼센트", 700),
        ("1. 제1종전용주거지역 : 100퍼센트", 100),
        ("제2종일반주거지역 60% 이하", 60),
        ("건폐율은 100분의 60 이하로 한다", 60),
        ("중심상업지역 1천500퍼 센트", 1500),            # "퍼 센트" 띄어쓰기
    ],
)
def test_parse_value_real_lines(line, expected):
    assert _parse_value(line) == pytest.approx(expected)


def test_parse_value_no_match():
    assert _parse_value("이 줄에는 수치가 없습니다") is None
