"""법규 그래프 큐레이션 — auto 수확 노드/엣지를 시니어가 검토해 승격/반려.

큐레이션 결과는 **델타 오버레이** 한 파일(law_graph_curation.json)에만 누적된다:

    {"promoted": {"nodes": [id,...], "edges": [[s,t],...]},
     "rejected": {"nodes": [id,...], "edges": [[s,t],...]}}

- seed/auto 원본(repo config/)은 **건드리지 않는다** — baseline·재수확 가능 유지.
- `law_graph._build()`가 baseline 위에 오버레이를 적용한다:
    · 반려(rejected) → 그래프에서 노드/엣지 제거.
    · 승격(promoted) → origin 태그를 auto→seed로 격상(UI에서 실선·확정 표시).
- harvest는 `load_rejected_sets()`로 반려분 재생성을 차단한다.

영속성:
  오버레이 파일 위치는 환경변수 `LAW_GRAPH_CURATION_DIR`(설정 시)로 정한다.
  Cloud Run에서는 GCSFUSE 마운트 경로를 지정해 **배포본에서 누른 큐레이션이
  재시작·재배포에도 보존**되게 한다. (휘발성 파일시스템 문제 해소)
  미설정 시 repo `config/` — 로컬 큐레이션→커밋→배포 흐름(기존)과 동일.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from services import law_graph

# 구버전 호환 — 과거 reject가 쓰던 별도 파일. 있으면 읽어 병합(쓰기는 안 함).
_LEGACY_REJECTED_PATH = (
    Path(__file__).parent.parent / "config" / "law_graph_rejected.json"
)


def _curation_dir() -> Path:
    """오버레이 저장 디렉터리. 환경변수 우선, 미설정 시 repo config/."""
    raw = os.getenv("LAW_GRAPH_CURATION_DIR")
    if raw:
        p = Path(raw).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p
    return Path(__file__).parent.parent / "config"


def _curation_path() -> Path:
    return _curation_dir() / "law_graph_curation.json"


def _empty() -> dict:
    return {
        "promoted": {"nodes": [], "edges": []},
        "rejected": {"nodes": [], "edges": []},
    }


def _load_curation() -> dict:
    """오버레이 로드. 레거시 rejected.json이 있으면 반려분에 병합(읽기 전용)."""
    data = _empty()
    p = _curation_path()
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            for tier in ("promoted", "rejected"):
                t = raw.get(tier) or {}
                data[tier]["nodes"] = list(t.get("nodes", []))
                data[tier]["edges"] = [list(e) for e in t.get("edges", [])]
        except Exception:
            pass  # 손상 시 빈 오버레이로 degrade

    if _LEGACY_REJECTED_PATH.exists():
        try:
            leg = json.loads(_LEGACY_REJECTED_PATH.read_text(encoding="utf-8"))
            for nid in leg.get("nodes", []):
                if nid not in data["rejected"]["nodes"]:
                    data["rejected"]["nodes"].append(nid)
            for e in leg.get("edges", []):
                if list(e) not in data["rejected"]["edges"]:
                    data["rejected"]["edges"].append(list(e))
        except Exception:
            pass
    return data


def _save_curation(data: dict) -> None:
    _curation_path().write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_auto() -> dict:
    """auto baseline(repo) 로드 — 큐레이션 대상 검증용. 경로는 law_graph가 소유."""
    p = Path(law_graph._AUTO_PATH)
    if not p.exists():
        return {"nodes": [], "edges": []}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _seed_node_ids() -> set:
    p = Path(law_graph._SEED_PATH)
    if not p.exists():
        return set()
    with open(p, encoding="utf-8") as f:
        seed = json.load(f)
    return {n.get("id") for n in seed.get("nodes", [])}


# ─── harvest / build 용 조회 ──────────────────────────────────────────────
def load_rejected_sets() -> tuple[set, set]:
    """harvest·build용 — (반려 노드 id set, 반려 엣지 (source,target) set)."""
    d = _load_curation()
    return (
        set(d["rejected"]["nodes"]),
        {tuple(e) for e in d["rejected"]["edges"]},
    )


def load_promoted_sets() -> tuple[set, set]:
    """build용 — (승격 노드 id set, 승격 엣지 (source,target) set)."""
    d = _load_curation()
    return (
        set(d["promoted"]["nodes"]),
        {tuple(e) for e in d["promoted"]["edges"]},
    )


# ─── 큐레이션 동작 (오버레이에만 기록 — baseline 불변) ──────────────────────
def promote_edge(source: str, target: str) -> dict:
    """auto 엣지를 승격 — 오버레이 promoted에 기록. 양끝 auto 노드도 함께 승격."""
    auto = _load_auto()
    exists = any(
        e.get("source") == source and e.get("target") == target
        for e in auto.get("edges", [])
    )
    if not exists:
        return {"ok": False, "reason": "해당 auto 엣지가 없습니다(이미 승격/반려됐을 수 있음)"}

    data = _load_curation()
    if [source, target] not in data["promoted"]["edges"]:
        data["promoted"]["edges"].append([source, target])

    seed_ids = _seed_node_ids()
    auto_node_ids = {n.get("id") for n in auto.get("nodes", [])}
    promoted_nodes: list[str] = []
    for nid in (source, target):
        if nid in auto_node_ids and nid not in seed_ids:
            if nid not in data["promoted"]["nodes"]:
                data["promoted"]["nodes"].append(nid)
            promoted_nodes.append(nid)

    # 반려와 충돌 시 승격이 반려를 해제
    data["rejected"]["edges"] = [
        e for e in data["rejected"]["edges"] if e != [source, target]
    ]
    _save_curation(data)
    law_graph.invalidate()
    return {"ok": True, "promoted_nodes": promoted_nodes}


def reject_edge(source: str, target: str) -> dict:
    """auto 엣지를 반려 — 오버레이 rejected에 기록(재수확·빌드에서 제외)."""
    auto = _load_auto()
    exists = any(
        e.get("source") == source and e.get("target") == target
        for e in auto.get("edges", [])
    )
    if not exists:
        return {"ok": False, "reason": "해당 auto 엣지가 없습니다"}

    data = _load_curation()
    if [source, target] not in data["rejected"]["edges"]:
        data["rejected"]["edges"].append([source, target])
    # 승격과 충돌 시 반려 우선
    data["promoted"]["edges"] = [
        e for e in data["promoted"]["edges"] if e != [source, target]
    ]
    _save_curation(data)
    law_graph.invalidate()
    return {"ok": True}


def reject_node(node_id: str) -> dict:
    """auto 노드 반려 — 노드 + 연결된 auto 엣지를 오버레이 rejected에 기록."""
    auto = _load_auto()
    if not any(n.get("id") == node_id for n in auto.get("nodes", [])):
        return {"ok": False, "reason": "해당 auto 노드가 없습니다"}

    removed_edges = [
        (e["source"], e["target"])
        for e in auto.get("edges", [])
        if e.get("source") == node_id or e.get("target") == node_id
    ]
    data = _load_curation()
    if node_id not in data["rejected"]["nodes"]:
        data["rejected"]["nodes"].append(node_id)
    for s, t in removed_edges:
        if [s, t] not in data["rejected"]["edges"]:
            data["rejected"]["edges"].append([s, t])
    # 승격 목록에서도 제거
    data["promoted"]["nodes"] = [
        n for n in data["promoted"]["nodes"] if n != node_id
    ]
    _save_curation(data)
    law_graph.invalidate()
    return {"ok": True, "removed_edges": len(removed_edges)}
