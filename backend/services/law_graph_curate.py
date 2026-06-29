"""법규 그래프 큐레이션 — auto 수확 노드/엣지를 시니어가 검토해 seed로 승격/반려.

- **승격(promote)**: auto 항목을 `law_graph_seed.json`으로 이동(origin 제거 → seed).
  엣지 승격 시 양끝 auto 노드도 함께 승격한다(seed 엣지는 seed 노드를 요구 —
  `law_graph._add_edges`가 노드 없는 엣지를 drop하므로). 재수확해도 유지됨.
- **반려(reject)**: auto.json에서 제거 + `law_graph_rejected.json`에 기록 →
  `law_graph_harvest`가 재수확 시 다시 만들지 않도록 차단.

모든 변경 후 `law_graph.invalidate()`로 그래프 캐시를 비운다.
"""
from __future__ import annotations

import json
from pathlib import Path

from services import law_graph

_SEED_PATH = law_graph._SEED_PATH
_AUTO_PATH = law_graph._AUTO_PATH
_REJECTED_PATH = Path(__file__).parent.parent / "config" / "law_graph_rejected.json"


def _load(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_rejected() -> dict:
    return _load(_REJECTED_PATH, {"nodes": [], "edges": []})


def load_rejected_sets() -> tuple[set, set]:
    """harvest용 — (반려 노드 id set, 반려 엣지 (source,target) set)."""
    d = _load_rejected()
    return set(d.get("nodes", [])), {tuple(e) for e in d.get("edges", [])}


def _strip_origin(obj: dict) -> dict:
    return {k: v for k, v in obj.items() if k != "origin"}


def promote_edge(source: str, target: str) -> dict:
    """auto 엣지를 seed로 승격. 양끝 auto 노드도 함께 승격."""
    auto = _load(_AUTO_PATH, {"nodes": [], "edges": []})
    edge = next(
        (e for e in auto.get("edges", [])
         if e.get("source") == source and e.get("target") == target),
        None,
    )
    if edge is None:
        return {"ok": False, "reason": "해당 auto 엣지가 없습니다(이미 승격/반려됐을 수 있음)"}

    seed = _load(_SEED_PATH, {"nodes": [], "edges": []})
    seed_node_ids = {n.get("id") for n in seed.get("nodes", [])}
    auto_nodes = {n.get("id"): n for n in auto.get("nodes", [])}

    promoted_nodes: list[str] = []
    for nid in (source, target):
        if nid not in seed_node_ids and nid in auto_nodes:
            seed["nodes"].append(_strip_origin(auto_nodes[nid]))
            promoted_nodes.append(nid)

    seed["edges"].append(_strip_origin(edge))
    auto["edges"] = [
        e for e in auto.get("edges", [])
        if not (e.get("source") == source and e.get("target") == target)
    ]
    if promoted_nodes:
        auto["nodes"] = [n for n in auto.get("nodes", []) if n.get("id") not in promoted_nodes]

    _save(_SEED_PATH, seed)
    _save(_AUTO_PATH, auto)
    law_graph.invalidate()
    return {"ok": True, "promoted_nodes": promoted_nodes}


def reject_edge(source: str, target: str) -> dict:
    """auto 엣지를 반려 — auto.json에서 제거 + rejected.json 기록(재수확 차단)."""
    auto = _load(_AUTO_PATH, {"nodes": [], "edges": []})
    before = len(auto.get("edges", []))
    auto["edges"] = [
        e for e in auto.get("edges", [])
        if not (e.get("source") == source and e.get("target") == target)
    ]
    if len(auto["edges"]) == before:
        return {"ok": False, "reason": "해당 auto 엣지가 없습니다"}

    rej = _load_rejected()
    if [source, target] not in rej["edges"]:
        rej["edges"].append([source, target])

    _save(_AUTO_PATH, auto)
    _save(_REJECTED_PATH, rej)
    law_graph.invalidate()
    return {"ok": True}


def reject_node(node_id: str) -> dict:
    """auto 노드 반려 — 노드 + 연결된 auto 엣지 제거 + rejected.json 기록."""
    auto = _load(_AUTO_PATH, {"nodes": [], "edges": []})
    if not any(n.get("id") == node_id for n in auto.get("nodes", [])):
        return {"ok": False, "reason": "해당 auto 노드가 없습니다"}

    auto["nodes"] = [n for n in auto.get("nodes", []) if n.get("id") != node_id]
    removed_edges = [
        (e["source"], e["target"]) for e in auto.get("edges", [])
        if e.get("source") == node_id or e.get("target") == node_id
    ]
    auto["edges"] = [
        e for e in auto.get("edges", [])
        if e.get("source") != node_id and e.get("target") != node_id
    ]

    rej = _load_rejected()
    if node_id not in rej["nodes"]:
        rej["nodes"].append(node_id)
    for pair in removed_edges:
        if list(pair) not in rej["edges"]:
            rej["edges"].append(list(pair))

    _save(_AUTO_PATH, auto)
    _save(_REJECTED_PATH, rej)
    law_graph.invalidate()
    return {"ok": True, "removed_edges": len(removed_edges)}
