"""법규 그래프 큐레이션(auto→seed 승격 / 반려) 테스트.

임시 JSON에 경로를 monkeypatch하여 실제 시드/자동 파일을 건드리지 않는다.
"""
from __future__ import annotations

import json

import pytest

from services import law_graph, law_graph_curate


def _write(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def graph_files(tmp_path, monkeypatch):
    """seed/auto/rejected 임시 파일 + 경로 패치. (seed, auto, rejected) 경로 반환."""
    seed_p = tmp_path / "seed.json"
    auto_p = tmp_path / "auto.json"
    rej_p = tmp_path / "rejected.json"

    _write(seed_p, {
        "node_kinds": ["카테고리", "법률"],
        "edge_rels": {"근거": "x", "참조": "y"},
        "nodes": [
            {"id": "buildingact_55", "kind": "법률", "law": "건축법",
             "article": "제55조", "title": "건폐율"},
        ],
        "edges": [],
    })
    _write(auto_p, {
        "nodes": [
            {"id": "auto_law_77", "kind": "법률", "law": "국토계획법",
             "article": "제77조", "title": "", "origin": "auto"},
        ],
        "edges": [
            {"source": "buildingact_55", "target": "auto_law_77",
             "rel": "참조", "note": "본문 자동 추출", "origin": "auto"},
        ],
    })

    # law_graph_curate 와 law_graph 양쪽의 경로 패치
    for mod in (law_graph_curate, law_graph):
        monkeypatch.setattr(mod, "_SEED_PATH", seed_p, raising=False)
        monkeypatch.setattr(mod, "_AUTO_PATH", auto_p, raising=False)
    monkeypatch.setattr(law_graph_curate, "_REJECTED_PATH", rej_p)
    law_graph.invalidate()
    yield seed_p, auto_p, rej_p
    law_graph.invalidate()


def test_promote_edge_moves_to_seed(graph_files):
    seed_p, auto_p, _ = graph_files
    result = law_graph_curate.promote_edge("buildingact_55", "auto_law_77")
    assert result["ok"] is True
    assert "auto_law_77" in result["promoted_nodes"]

    seed = json.loads(seed_p.read_text(encoding="utf-8"))
    auto = json.loads(auto_p.read_text(encoding="utf-8"))
    # 엣지·노드가 seed로 이동, auto에서 제거
    assert any(e["source"] == "buildingact_55" and e["target"] == "auto_law_77"
               for e in seed["edges"])
    assert any(n["id"] == "auto_law_77" for n in seed["nodes"])
    assert auto["edges"] == []
    assert auto["nodes"] == []
    # 승격된 항목엔 origin 필드 없음(=seed)
    promoted_edge = seed["edges"][0]
    assert "origin" not in promoted_edge


def test_promoted_edge_shows_as_seed_in_graph(graph_files):
    law_graph_curate.promote_edge("buildingact_55", "auto_law_77")
    detail = law_graph.node_detail("buildingact_55")
    out = detail["out"]
    assert len(out) == 1
    assert out[0]["origin"] == "seed"  # auto 아님


def test_reject_edge_removes_and_records(graph_files):
    _, auto_p, rej_p = graph_files
    result = law_graph_curate.reject_edge("buildingact_55", "auto_law_77")
    assert result["ok"] is True
    auto = json.loads(auto_p.read_text(encoding="utf-8"))
    rej = json.loads(rej_p.read_text(encoding="utf-8"))
    assert auto["edges"] == []
    assert ["buildingact_55", "auto_law_77"] in rej["edges"]


def test_reject_node_removes_incident_edges(graph_files):
    _, auto_p, rej_p = graph_files
    result = law_graph_curate.reject_node("auto_law_77")
    assert result["ok"] is True
    assert result["removed_edges"] == 1
    auto = json.loads(auto_p.read_text(encoding="utf-8"))
    rej = json.loads(rej_p.read_text(encoding="utf-8"))
    assert auto["nodes"] == []
    assert auto["edges"] == []
    assert "auto_law_77" in rej["nodes"]


def test_load_rejected_sets_shape(graph_files):
    law_graph_curate.reject_edge("buildingact_55", "auto_law_77")
    nodes, edges = law_graph_curate.load_rejected_sets()
    assert ("buildingact_55", "auto_law_77") in edges
    assert isinstance(nodes, set)


def test_promote_missing_edge_fails(graph_files):
    result = law_graph_curate.promote_edge("nope", "nada")
    assert result["ok"] is False
