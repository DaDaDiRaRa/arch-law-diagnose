"""법규 그래프 자동 수확(Step 11 #1) 회귀 테스트.

extract_refs 순수 파서 + 엔진 자동병합(origin 태깅)을 검증. 외부 API 미호출.
"""
from __future__ import annotations

import json

import pytest

from services import law_graph as lg
from services.law_graph_harvest import extract_refs


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
