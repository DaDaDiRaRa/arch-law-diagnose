"""법규 의미 그래프 (Step 11).

이 시스템이 적용하는 조문·근거를 노드로, 적용·위임·완화·제외·트리거·참조 관계를
엣지로 갖는 방향 그래프(networkx DiGraph). config/law_graph_seed.json에서 빌드.

용도: 진단 카테고리에서 관련 조문으로의 탐색(설명가능성), What-If 정교화의 기반.
확장: 시드에 노드/엣지 추가, 또는 향후 법제처 DRF API 자동 수확.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import networkx as nx

logger = logging.getLogger(__name__)

_SEED_PATH = Path(__file__).parent.parent / "config" / "law_graph_seed.json"

_GRAPH: nx.DiGraph | None = None
_META: dict = {}


def _build() -> nx.DiGraph:
    """시드 JSON → DiGraph. 끊어진 엣지(노드 누락)는 경고 후 skip(graceful)."""
    global _META
    with open(_SEED_PATH, encoding="utf-8") as f:
        seed = json.load(f)

    _META = {
        "node_kinds": seed.get("node_kinds", []),
        "edge_rels": seed.get("edge_rels", {}),
        "disclaimer": seed.get("_disclaimer", ""),
    }

    g = nx.DiGraph()
    for node in seed.get("nodes", []):
        nid = node.get("id")
        if not nid:
            continue
        g.add_node(nid, **{k: v for k, v in node.items() if k != "id"})

    dropped = 0
    for edge in seed.get("edges", []):
        s, t = edge.get("source"), edge.get("target")
        if s not in g or t not in g:
            logger.warning("[law_graph] 끊어진 엣지 skip: %s → %s (노드 누락)", s, t)
            dropped += 1
            continue
        g.add_edge(s, t, rel=edge.get("rel", "참조"), note=edge.get("note", ""))

    logger.info(
        "[law_graph] 노드 %d · 엣지 %d 적재 (끊어진 엣지 %d skip)",
        g.number_of_nodes(), g.number_of_edges(), dropped,
    )
    return g


def _graph() -> nx.DiGraph:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _build()
    return _GRAPH


def _node_obj(g: nx.DiGraph, nid: str) -> dict:
    """노드 id → 직렬화 dict(id 포함)."""
    return {"id": nid, **g.nodes[nid]}


def get_graph_dict() -> dict:
    """전체 그래프 — 프론트 렌더용 {nodes, edges, meta}."""
    g = _graph()
    return {
        "nodes": [_node_obj(g, n) for n in g.nodes],
        "edges": [
            {"source": s, "target": t, "rel": d.get("rel"), "note": d.get("note", "")}
            for s, t, d in g.edges(data=True)
        ],
        "meta": _META,
    }


def node_detail(node_id: str) -> dict | None:
    """노드 + 인접 관계(나가는/들어오는, rel별 묶음). 없으면 None."""
    g = _graph()
    if node_id not in g:
        return None
    out = [
        {"rel": d.get("rel"), "note": d.get("note", ""), "node": _node_obj(g, t)}
        for _, t, d in g.out_edges(node_id, data=True)
    ]
    inc = [
        {"rel": d.get("rel"), "note": d.get("note", ""), "node": _node_obj(g, s)}
        for s, _, d in g.in_edges(node_id, data=True)
    ]
    return {"node": _node_obj(g, node_id), "out": out, "in": inc}


def category_subgraph(node_id: str) -> dict | None:
    """카테고리(또는 임의) 노드에서 out-edge로 도달하는 서브그래프 {nodes, edges}."""
    g = _graph()
    if node_id not in g:
        return None
    reachable = nx.descendants(g, node_id) | {node_id}
    sub = g.subgraph(reachable)
    return {
        "root": node_id,
        "nodes": [_node_obj(g, n) for n in sub.nodes],
        "edges": [
            {"source": s, "target": t, "rel": d.get("rel"), "note": d.get("note", "")}
            for s, t, d in sub.edges(data=True)
        ],
    }


def search(q: str) -> list[dict]:
    """law/title/article 부분일치 노드 목록."""
    g = _graph()
    ql = (q or "").strip().lower()
    if not ql:
        return []
    hits = []
    for n in g.nodes:
        d = g.nodes[n]
        hay = f"{d.get('law','')} {d.get('article','')} {d.get('title','')}".lower()
        if ql in hay:
            hits.append(_node_obj(g, n))
    return hits


def stats() -> dict:
    """노드/엣지 수 + kind·rel 분포 (헬스/디버그용)."""
    g = _graph()
    kinds: dict[str, int] = {}
    for n in g.nodes:
        k = g.nodes[n].get("kind", "기타")
        kinds[k] = kinds.get(k, 0) + 1
    rels: dict[str, int] = {}
    for _, _, d in g.edges(data=True):
        r = d.get("rel", "참조")
        rels[r] = rels.get(r, 0) + 1
    return {
        "nodes": g.number_of_nodes(),
        "edges": g.number_of_edges(),
        "by_kind": kinds,
        "by_rel": rels,
    }
