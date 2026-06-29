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
_AUTO_PATH = Path(__file__).parent.parent / "config" / "law_graph_auto.json"

_GRAPH: nx.DiGraph | None = None
_META: dict = {}


def _add_nodes(g: nx.DiGraph, nodes: list[dict], origin: str) -> None:
    for node in nodes:
        nid = node.get("id")
        if not nid:
            continue
        if nid in g:  # 시드 우선 — 자동 노드가 시드를 덮어쓰지 않음
            continue
        attrs = {k: v for k, v in node.items() if k != "id"}
        attrs.setdefault("origin", origin)
        g.add_node(nid, **attrs)


def _add_edges(g: nx.DiGraph, edges: list[dict], origin: str) -> int:
    dropped = 0
    for edge in edges:
        s, t = edge.get("source"), edge.get("target")
        if s not in g or t not in g:
            logger.warning("[law_graph] 끊어진 엣지 skip: %s → %s (노드 누락)", s, t)
            dropped += 1
            continue
        g.add_edge(s, t, rel=edge.get("rel", "참조"),
                   note=edge.get("note", ""), origin=edge.get("origin", origin))
    return dropped


def _build() -> nx.DiGraph:
    """시드 JSON → DiGraph. 자동수확 파일(있으면) 병합(origin=auto). 끊어진 엣지는 skip."""
    global _META
    with open(_SEED_PATH, encoding="utf-8") as f:
        seed = json.load(f)

    _META = {
        "node_kinds": seed.get("node_kinds", []),
        "edge_rels": seed.get("edge_rels", {}),
        "disclaimer": seed.get("_disclaimer", ""),
    }

    g = nx.DiGraph()
    _add_nodes(g, seed.get("nodes", []), "seed")
    dropped = _add_edges(g, seed.get("edges", []), "seed")

    # 자동수확 병합 (있을 때만) — origin="auto"로 구분 태깅
    auto_n = auto_e = 0
    if _AUTO_PATH.exists():
        try:
            with open(_AUTO_PATH, encoding="utf-8") as f:
                auto = json.load(f)
            _add_nodes(g, auto.get("nodes", []), "auto")
            dropped += _add_edges(g, auto.get("edges", []), "auto")
            auto_n, auto_e = len(auto.get("nodes", [])), len(auto.get("edges", []))
            _META["has_auto"] = True
        except Exception as e:
            logger.warning("[law_graph] 자동수확 파일 로드 실패: %s", e)

    # 큐레이션 오버레이 적용 (반려 제거 / 승격 origin 격상) — baseline 위에 덧입힘
    _apply_curation(g)

    logger.info(
        "[law_graph] 노드 %d · 엣지 %d (자동 노드 %d·엣지 %d, 끊어진 엣지 %d skip)",
        g.number_of_nodes(), g.number_of_edges(), auto_n, auto_e, dropped,
    )
    return g


def _apply_curation(g: nx.DiGraph) -> None:
    """시니어 큐레이션 델타를 그래프에 반영.

    반려(rejected) 노드/엣지는 제거하고, 승격(promoted) 노드/엣지는 origin을
    'seed'로 격상한다. 오버레이 파일이 없으면(기본) 아무것도 하지 않는다.
    law_graph_curate를 함수 내에서 import해 순환참조를 피한다.
    """
    try:
        from services.law_graph_curate import (
            load_promoted_sets,
            load_rejected_sets,
        )
        prom_nodes, prom_edges = load_promoted_sets()
        rej_nodes, rej_edges = load_rejected_sets()
    except Exception as e:  # 큐레이션 로드 실패는 진단을 막지 않음
        logger.warning("[law_graph] 큐레이션 오버레이 로드 실패: %s", e)
        return

    for nid in rej_nodes:
        if g.has_node(nid):
            g.remove_node(nid)  # 연결된 엣지도 함께 제거됨
    for s, t in rej_edges:
        if g.has_edge(s, t):
            g.remove_edge(s, t)
    for nid in prom_nodes:
        if g.has_node(nid):
            g.nodes[nid]["origin"] = "seed"
    for s, t in prom_edges:
        if g.has_edge(s, t):
            g.edges[s, t]["origin"] = "seed"


def _graph() -> nx.DiGraph:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _build()
    return _GRAPH


def invalidate() -> None:
    """그래프 캐시 무효화 — 시드/자동 JSON이 큐레이션으로 바뀐 뒤 호출."""
    global _GRAPH
    _GRAPH = None


def _node_obj(g: nx.DiGraph, nid: str) -> dict:
    """노드 id → 직렬화 dict(id 포함)."""
    return {"id": nid, **g.nodes[nid]}


def get_graph_dict() -> dict:
    """전체 그래프 — 프론트 렌더용 {nodes, edges, meta}."""
    g = _graph()
    return {
        "nodes": [_node_obj(g, n) for n in g.nodes],
        "edges": [
            {"source": s, "target": t, "rel": d.get("rel"), "note": d.get("note", ""),
             "origin": d.get("origin", "seed")}
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
        {"rel": d.get("rel"), "note": d.get("note", ""),
         "origin": d.get("origin", "seed"), "node": _node_obj(g, t)}
        for _, t, d in g.out_edges(node_id, data=True)
    ]
    inc = [
        {"rel": d.get("rel"), "note": d.get("note", ""),
         "origin": d.get("origin", "seed"), "node": _node_obj(g, s)}
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
            {"source": s, "target": t, "rel": d.get("rel"), "note": d.get("note", ""),
             "origin": d.get("origin", "seed")}
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
