"""법규 그래프 자동 수확(Step 11 #1) 회귀 테스트.

extract_refs 순수 파서 + 엔진 자동병합(origin 태깅)을 검증. 외부 API 미호출.
"""
from __future__ import annotations

import json

import pytest

from services import law_graph as lg
from services.law_go_kr_client import _parse_law_xml
from services.law_graph_harvest import extract_refs


# ── 국가법령(target=law) XML 파싱 — 조문단위 스키마 (2026-06-26 버그 회귀) ──────
_NATIONAL_XML = """<LawService>
  <조문단위 조문키="0005600">
    <조문번호>56</조문번호>
    <조문가지번호></조문가지번호>
    <조문제목>건축물의 용적률</조문제목>
    <조문내용><![CDATA[제56조(건축물의 용적률) 건축물의 용적률은 「국토의 계획 및 이용에 관한 법률」 제78조에 따른다.]]></조문내용>
  </조문단위>
  <조문단위 조문키="0005302">
    <조문번호>53</조문번호>
    <조문가지번호>2</조문가지번호>
    <조문제목>범죄예방</조문제목>
    <조문내용><![CDATA[제53조의2(범죄예방) ...]]></조문내용>
  </조문단위>
  <조문단위 조문키="0001000">
    <조문번호>1</조문번호>
    <조문내용><![CDATA[제1장 총칙]]></조문내용>
  </조문단위>
</LawService>"""


def test_parse_national_law_articles():
    arts = _parse_law_xml(_NATIONAL_XML)
    by_no = {a["article_no"]: a for a in arts}
    # 6자리 코드: 제56조=005600, 제53조의2=005302
    assert "005600" in by_no and "005302" in by_no
    assert by_no["005600"]["content"].startswith("제56조")
    assert "제78조" in by_no["005600"]["content"]


def test_parse_excludes_chapter_heading():
    arts = _parse_law_xml(_NATIONAL_XML)
    # "제1장 총칙"은 제N조 패턴이 아니므로 제외
    assert all(not a["content"].startswith("제1장") for a in arts)


def test_extract_named_ref():
    refs = extract_refs("이 경우 「건축법」 제42조에 따라 조경을 설치한다.", "주차장법")
    assert {"law": "건축법", "article": "제42조", "kind": "named"} in refs


def test_extract_article_with_sub():
    refs = extract_refs("「건축법」 제53조의2를 준용한다.", "주차장법")
    assert any(r["article"] == "제53조의2" and r["law"] == "건축법" for r in refs)


def test_extract_same_law_and_byp():
    refs = extract_refs("제56조 및 별표 4에 따른다.", "건축법", self_article="제10조")
    laws_arts = {(r["law"], r["article"]) for r in refs}
    assert ("건축법", "제56조") in laws_arts
    assert ("건축법", "별표 4") in laws_arts


def test_self_reference_excluded():
    refs = extract_refs("제55조(건폐율) 이 조에서 정한다.", "건축법", self_article="제55조")
    assert all(r["article"] != "제55조" for r in refs)


def test_dedup():
    refs = extract_refs("「건축법」 제42조 ... 「건축법」 제42조 다시", "주차장법")
    assert sum(1 for r in refs if r["article"] == "제42조") == 1


def test_empty_text():
    assert extract_refs("", "건축법") == []


# ── 엔진 자동병합 ────────────────────────────────────────────────────────────
@pytest.fixture
def reset_graph(tmp_path, monkeypatch):
    """auto 파일 경로를 임시로 바꾸고 그래프 캐시를 리셋."""
    monkeypatch.setattr(lg, "_AUTO_PATH", tmp_path / "auto.json")
    monkeypatch.setattr(lg, "_GRAPH", None)
    yield tmp_path
    monkeypatch.setattr(lg, "_GRAPH", None)


def test_no_auto_file_is_seed_only(reset_graph):
    """자동 파일 없으면 시드만 — 모든 노드 origin=seed."""
    g = lg.get_graph_dict()
    assert all(n.get("origin", "seed") == "seed" for n in g["nodes"])


def test_auto_merge_tags_origin(reset_graph):
    """자동 파일이 있으면 병합되고 origin=auto로 태깅된다."""
    auto = {
        "nodes": [{"id": "auto_x", "kind": "법률", "law": "테스트법", "article": "제1조", "title": ""}],
        "edges": [{"source": "cat_far", "target": "auto_x", "rel": "참조", "note": "자동"}],
    }
    (reset_graph / "auto.json").write_text(json.dumps(auto, ensure_ascii=False), encoding="utf-8")
    lg._GRAPH = None  # 재빌드 강제

    g = lg.get_graph_dict()
    node = next((n for n in g["nodes"] if n["id"] == "auto_x"), None)
    assert node is not None and node["origin"] == "auto"
    edge = next((e for e in g["edges"] if e["target"] == "auto_x"), None)
    assert edge is not None and edge["origin"] == "auto"


def test_auto_does_not_override_seed(reset_graph):
    """자동 노드가 시드 노드 id를 덮어쓰지 않는다."""
    auto = {"nodes": [{"id": "cat_far", "kind": "법률", "law": "가짜", "article": "x", "origin": "auto"}], "edges": []}
    (reset_graph / "auto.json").write_text(json.dumps(auto, ensure_ascii=False), encoding="utf-8")
    lg._GRAPH = None
    d = lg.node_detail("cat_far")
    assert d["node"]["kind"] == "카테고리"  # 시드 값 유지


# ── 법령 귀속 회귀 (graph E-12 감사 7건, 2026-06-30 발견 → 2026-08-27 정정) ──────
# 본문은 전부 법제처 현행 원문에서 발췌. 7건 모두 "실재하지 않는 조문"이 만들어진
# 사례였고, 원인은 조문 삭제가 아니라 **법령 귀속 오류** 두 가지였다.


def test_decree_bare_law_means_parent_act():
    """시행령 본문의 "법 제N조"는 모법 조문 — 시행령 자기 조문이 아니다.

    이걸 모르면 실재하지 않는 '건축법 시행령 제13조의2'가 생성된다.
    (건축법 시행령 제10조의3 실제 본문)
    """
    refs = extract_refs(
        '제10조의3(건축물 안전영향평가) ① 법 제13조의2제1항에서 "초고층 건축물 등"이란',
        "건축법 시행령", self_article="제10조의3",
    )
    assert {"law": "건축법", "article": "제13조의2", "kind": "named"} in refs
    assert all(r["law"] != "건축법 시행령" for r in refs)


def test_decree_bare_law_crime_prevention():
    """건축법 시행령 제63조의7 → 건축법 제53조의2 (시행령 제53조의2 아님)."""
    refs = extract_refs(
        '제63조의7(건축물의 범죄예방) 법 제53조의2제2항에서 "대통령령으로 정하는 건축물"이란',
        "건축법 시행령", self_article="제63조의7",
    )
    assert {"law": "건축법", "article": "제53조의2", "kind": "named"} in refs


def test_decree_mixed_anchors_keep_each_law():
    """「명시」·"같은 법"·"법"이 한 조문에 섞여도 각각 제 법령으로 간다.

    (건축법 시행령 제86조 실제 본문 — 제77조의2를 시행령 조문으로 읽던 자리)
    """
    refs = extract_refs(
        "「국토의 계획 및 이용에 관한 법률」 제51조에 따른 지구단위계획구역, "
        "같은 법 제37조제1항제1호에 따른 경관지구 나. 「경관법」 제9조제1항제4호에 "
        "따른 중점경관관리구역 다. 법 제77조의2제1항에 따른 특별가로구역",
        "건축법 시행령", self_article="제86조",
    )
    got = {(r["law"], r["article"]) for r in refs}
    # 정식명칭은 시드 약칭(국토계획법)으로 정규화된다 — 같은 조문이 노드 둘로 갈라지지 않게
    assert ("국토계획법", "제51조") in got
    assert ("국토계획법", "제37조") in got                        # "같은 법" 회귀
    assert ("경관법", "제9조") in got
    assert ("건축법", "제77조의2") in got                        # "법" = 모법
    assert ("건축법 시행령", "제77조의2") not in got


def test_named_law_carries_through_enumeration():
    """나열된 조문은 전부 앞의 명시 법령 소속 — 첫 조문만이 아니다.

    "「건축법」 제60조 및 제61조"에서 제61조가 녹색건축물법 제61조(미존재)로
    떨어지던 회귀. (녹색건축물 조성 지원법 제15조 실제 본문)
    """
    refs = extract_refs(
        "1. 「건축법」 제56조에 따른 건축물의 용적률: 100분의 115 이하 "
        "2. 「건축법」 제60조 및 제61조에 따른 건축물의 높이: 100분의 115 이하",
        "녹색건축물 조성 지원법", self_article="제15조",
    )
    got = {(r["law"], r["article"]) for r in refs}
    assert ("건축법", "제61조") in got
    assert ("녹색건축물 조성 지원법", "제61조") not in got


def test_comma_enumeration_carries_through():
    """쉼표 나열도 동일 — 건축법 제61조 본문의 산업입지법 조문 4개."""
    refs = extract_refs(
        "4. 「산업입지 및 개발에 관한 법률」 제6조, 제7조, 제7조의2 및 제8조에 따른 국가산업단지",
        "건축법", self_article="제61조",
    )
    got = {(r["law"], r["article"]) for r in refs}
    assert ("산업입지 및 개발에 관한 법률", "제7조의2") in got
    assert ("건축법", "제7조의2") not in got   # 건축법에 제7조의2는 없다


def test_same_law_anaphora_after_unnumbered_mention():
    """법령명이 조문 없이 먼저 나오고 "같은 법 제N조"가 뒤에 와도 귀속된다.

    (주차장법 제19조 실제 본문 — 주차장법 제51조를 만들던 자리)
    """
    refs = extract_refs(
        "제19조(부설주차장의 설치) ① 「국토의 계획 및 이용에 관한 법률」에 따른 도시지역, "
        "같은 법 제51조제3항에 따른 지구단위계획구역",
        "주차장법", self_article="제19조",
    )
    got = {(r["law"], r["article"]) for r in refs}
    assert ("국토계획법", "제51조") in got          # 정식명칭 → 시드 약칭으로 정규화
    assert ("주차장법", "제51조") not in got


def test_bare_article_still_means_current_law():
    """앵커 없이 홀로 선 "제N조"는 여전히 현재 법 조문(기존 동작 유지)."""
    refs = extract_refs("제56조에 따른 용적률은 별표 4에 따른다.", "건축법", self_article="제10조")
    got = {(r["law"], r["article"]) for r in refs}
    assert ("건축법", "제56조") in got
    assert ("건축법", "별표 4") in got


def test_law_suffix_not_mistaken_for_anchor():
    """"건축법"의 꼬리 '법'을 모법 앵커로 오인하지 않는다."""
    refs = extract_refs("「건축법」 제42조에 따라 조경을 설치한다.", "주차장법")
    assert {"law": "건축법", "article": "제42조", "kind": "named"} in refs


def test_formal_law_name_canonicalized_to_seed_alias():
    """본문의 정식명칭과 시드 약칭이 같은 노드로 모인다.

    "「국토의 계획 및 이용에 관한 법률」 제77조"(본문)와 시행령의 "법 제77조"가
    각각 다른 이름으로 남으면 같은 조문이 노드 둘이 된다.
    """
    a = extract_refs("「국토의 계획 및 이용에 관한 법률」 제77조에 따른다.", "건축법")
    b = extract_refs("법 제77조에 따른다.", "국토계획법 시행령", self_article="제84조")
    assert ("국토계획법", "제77조") in {(r["law"], r["article"]) for r in a}
    assert ("국토계획법", "제77조") in {(r["law"], r["article"]) for r in b}

