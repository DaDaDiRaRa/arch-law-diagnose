"""법규 의미 그래프(Step 11) 회귀 테스트.

시드 무결성(끊어진 엣지 0)과 핵심 질의(카테고리→근거·완화·트리거, 위임 체인 도달)를 고정.
"""
from __future__ import annotations

from services import law_graph as lg


def test_graph_builds_nonempty():
    s = lg.stats()
    assert s["nodes"] > 0
    assert s["edges"] > 0


def test_no_dangling_edges():
    """모든 엣지의 source/target이 노드에 존재해야 한다(빌드 시 skip되지 않음)."""
    g = lg.get_graph_dict()
    ids = {n["id"] for n in g["nodes"]}
    for e in g["edges"]:
        assert e["source"] in ids, f"끊어진 source: {e['source']}"
        assert e["target"] in ids, f"끊어진 target: {e['target']}"


def test_far_category_relations():
    """용적률 카테고리 → 근거·완화·제외·트리거 관계가 모두 존재."""
    d = lg.node_detail("cat_far")
    assert d is not None
    rels = {o["rel"] for o in d["out"]}
    assert {"근거", "완화", "제외", "트리거"} <= rels
    out_ids = {o["node"]["id"] for o in d["out"]}
    assert "buildingact_56" in out_ids  # 근거: 건축법 제56조
    assert "greenact_15" in out_ids     # 완화: 녹색건축물조성지원법 제15조


def test_far_subgraph_reaches_delegation_chain():
    """용적률 서브그래프가 위임 체인 끝(에너지절약설계기준 별표9)까지 도달."""
    sub = lg.category_subgraph("cat_far")
    assert sub is not None
    ids = {n["id"] for n in sub["nodes"]}
    assert "nucadecree_85" in ids       # 건축법56 → 국토계획법시행령85 (위임)
    assert "energy_notice_b9" in ids    # 녹색법15 → 별표9 (위임)


def test_search_and_missing():
    assert any(n["id"] == "buildingact_56" for n in lg.search("용적률"))
    assert lg.search("") == []
    assert lg.node_detail("nonexistent") is None
    assert lg.category_subgraph("nonexistent") is None


def test_meta_exposed():
    g = lg.get_graph_dict()
    assert "근거" in g["meta"]["edge_rels"]
    assert "카테고리" in g["meta"]["node_kinds"]
