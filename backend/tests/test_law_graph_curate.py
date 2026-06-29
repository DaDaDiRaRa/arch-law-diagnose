"""법규 그래프 큐레이션(auto→seed 승격 / 반려) 테스트 — 델타 오버레이 모델.

큐레이션은 seed/auto 원본을 건드리지 않고 law_graph_curation.json(오버레이)에만
누적한다. 오버레이 위치는 LAW_GRAPH_CURATION_DIR 환경변수로 정해 영속화한다.
"""
from __future__ import annotations

import json

import pytest

from services import law_graph, law_graph_curate


def _write(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def graph_files(tmp_path, monkeypatch):
    """seed/auto baseline + 오버레이 디렉터리(tmp) 격리. (seed, auto, curation_dir) 반환."""
    seed_p = tmp_path / "seed.json"
    auto_p = tmp_path / "auto.json"
    overlay_dir = tmp_path / "overlay"
    overlay_dir.mkdir()

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

    # baseline 경로는 law_graph 소유 — 양쪽 모듈에서 참조하므로 둘 다 패치
    for mod in (law_graph_curate, law_graph):
        monkeypatch.setattr(mod, "_SEED_PATH", seed_p, raising=False)
        monkeypatch.setattr(mod, "_AUTO_PATH", auto_p, raising=False)
    # 오버레이는 환경변수로 tmp 디렉터리 지정 (영속 경로 시뮬레이션)
    monkeypatch.setenv("LAW_GRAPH_CURATION_DIR", str(overlay_dir))
    # 레거시 rejected.json이 실 repo에 없도록 보장(병합 경로 격리)
    monkeypatch.setattr(
        law_graph_curate, "_LEGACY_REJECTED_PATH", tmp_path / "no_legacy.json"
    )
    law_graph.invalidate()
    yield seed_p, auto_p, overlay_dir
    law_graph.invalidate()


def _overlay(overlay_dir) -> dict:
    return json.loads((overlay_dir / "law_graph_curation.json").read_text(encoding="utf-8"))


def test_promote_edge_records_overlay(graph_files):
    seed_p, auto_p, overlay_dir = graph_files
    result = law_graph_curate.promote_edge("buildingact_55", "auto_law_77")
    assert result["ok"] is True
    assert "auto_law_77" in result["promoted_nodes"]

    # baseline 원본은 불변
    assert json.loads(seed_p.read_text(encoding="utf-8"))["edges"] == []
    assert len(json.loads(auto_p.read_text(encoding="utf-8"))["edges"]) == 1

    # 오버레이에 승격 기록
    ov = _overlay(overlay_dir)
    assert ["buildingact_55", "auto_law_77"] in ov["promoted"]["edges"]
    assert "auto_law_77" in ov["promoted"]["nodes"]


def test_promoted_edge_shows_as_seed_in_graph(graph_files):
    law_graph_curate.promote_edge("buildingact_55", "auto_law_77")
    detail = law_graph.node_detail("buildingact_55")
    out = detail["out"]
    assert len(out) == 1
    assert out[0]["origin"] == "seed"  # auto 아님 — 빌드 시 격상됨


def test_reject_edge_removes_from_graph_and_records(graph_files):
    _, _, overlay_dir = graph_files
    result = law_graph_curate.reject_edge("buildingact_55", "auto_law_77")
    assert result["ok"] is True
    # 그래프에서 엣지 사라짐
    detail = law_graph.node_detail("buildingact_55")
    assert detail["out"] == []
    # 오버레이에 반려 기록
    ov = _overlay(overlay_dir)
    assert ["buildingact_55", "auto_law_77"] in ov["rejected"]["edges"]


def test_reject_node_removes_incident_edges(graph_files):
    _, _, overlay_dir = graph_files
    result = law_graph_curate.reject_node("auto_law_77")
    assert result["ok"] is True
    assert result["removed_edges"] == 1
    # 그래프에서 노드·엣지 제거 확인
    g = law_graph._graph()
    assert not g.has_node("auto_law_77")
    ov = _overlay(overlay_dir)
    assert "auto_law_77" in ov["rejected"]["nodes"]


def test_load_rejected_sets_shape(graph_files):
    law_graph_curate.reject_edge("buildingact_55", "auto_law_77")
    nodes, edges = law_graph_curate.load_rejected_sets()
    assert ("buildingact_55", "auto_law_77") in edges
    assert isinstance(nodes, set)


def test_promote_missing_edge_fails(graph_files):
    result = law_graph_curate.promote_edge("nope", "nada")
    assert result["ok"] is False


def test_reject_then_promote_resolves_conflict(graph_files):
    """반려 후 승격하면 반려가 해제되고 승격이 반영된다."""
    law_graph_curate.reject_edge("buildingact_55", "auto_law_77")
    law_graph_curate.promote_edge("buildingact_55", "auto_law_77")
    detail = law_graph.node_detail("buildingact_55")
    assert len(detail["out"]) == 1
    assert detail["out"][0]["origin"] == "seed"


def test_curation_persists_across_rebuild(graph_files):
    """오버레이 파일이 디렉터리에 남아 그래프 재빌드(invalidate) 후에도 적용된다.

    Cloud Run 재시작 = 새 프로세스가 같은 GCSFUSE 경로에서 오버레이를 다시 읽는 상황.
    여기선 invalidate로 캐시만 비우고 같은 LAW_GRAPH_CURATION_DIR에서 재로딩되는지 확인.
    """
    law_graph_curate.promote_edge("buildingact_55", "auto_law_77")
    law_graph.invalidate()  # 캐시 폐기 → 다음 접근 시 파일에서 재빌드
    detail = law_graph.node_detail("buildingact_55")
    assert len(detail["out"]) == 1
    assert detail["out"][0]["origin"] == "seed"
