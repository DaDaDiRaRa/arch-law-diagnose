"""brief 목록(list_briefs) 회귀 테스트 — 2026-06-26 A+D 성능 개선.

실제 GCS 구조: _briefs/{YYYYMMDD}_{HHMMSS}_{category}.json (+ .md/.xlsx 형제),
회차가 계속 누적. 파일명으로 정렬·필터 후 최근 N건만 본문을 읽고(D), (이름,mtime)
캐시로 재파싱을 막는다(A).
"""
from __future__ import annotations

import json

import pytest

from services import brief_importer as bi


def _write_brief(d, stem: str, *, name: str, sites: int):
    """최소 brief json 1건 작성."""
    obj = {
        "_brief_meta": {"brief_id": stem, "facility_type": stem.split("_")[-1]},
        "brief_project_info": {
            "competition_name": name,
            "sites": [{"site_id": f"부지{i+1}"} for i in range(sites)],
        },
    }
    (d / f"{stem}.json").write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def briefs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("BRIEF_DIR", str(tmp_path))
    bi._LIST_CACHE.clear()
    yield tmp_path
    bi._LIST_CACHE.clear()


def test_sorted_newest_first(briefs_dir):
    _write_brief(briefs_dir, "20260618_034829_public", name="A공모", sites=1)
    _write_brief(briefs_dir, "20260619_050919_public", name="B공모", sites=2)
    _write_brief(briefs_dir, "20260617_010101_residential", name="C공모", sites=3)
    out = bi.list_briefs()
    assert [b["file_id"] for b in out] == [
        "20260619_050919_public",
        "20260618_034829_public",
        "20260617_010101_residential",
    ]
    assert out[0]["competition_name"] == "B공모"
    assert out[0]["site_count"] == 2


def test_category_filter_from_filename(briefs_dir):
    _write_brief(briefs_dir, "20260618_034829_public", name="A", sites=1)
    _write_brief(briefs_dir, "20260619_050919_residential", name="B", sites=1)
    out = bi.list_briefs(category="residential")
    assert len(out) == 1
    assert out[0]["file_id"] == "20260619_050919_residential"


def test_limit_caps_detail_reads(briefs_dir, monkeypatch):
    for i in range(5):
        _write_brief(briefs_dir, f"2026061{i}_010101_public", name=f"N{i}", sites=1)
    reads = {"n": 0}
    orig = bi._read_summary
    monkeypatch.setattr(bi, "_read_summary", lambda p: (reads.__setitem__("n", reads["n"] + 1), orig(p))[1])
    out = bi.list_briefs(limit=2)
    assert len(out) == 2
    assert reads["n"] == 2  # 최근 2건만 본문 읽음


def test_cache_avoids_reparse(briefs_dir, monkeypatch):
    _write_brief(briefs_dir, "20260619_050919_public", name="A", sites=1)
    reads = {"n": 0}
    orig = bi._read_summary
    monkeypatch.setattr(bi, "_read_summary", lambda p: (reads.__setitem__("n", reads["n"] + 1), orig(p))[1])
    bi.list_briefs()
    bi.list_briefs()  # 두 번째 호출은 캐시 히트 → 재파싱 없음
    assert reads["n"] == 1


def test_md_xlsx_siblings_ignored(briefs_dir):
    _write_brief(briefs_dir, "20260619_050919_public", name="A", sites=1)
    (briefs_dir / "20260619_050919_public.md").write_text("# md", encoding="utf-8")
    (briefs_dir / "20260619_050919_public.xlsx").write_text("xlsx", encoding="utf-8")
    out = bi.list_briefs()
    assert len(out) == 1


def test_non_brief_json_skipped(briefs_dir):
    _write_brief(briefs_dir, "20260619_050919_public", name="A", sites=1)
    (briefs_dir / "99999999_999999_garbage.json").write_text('{"foo": 1}', encoding="utf-8")
    out = bi.list_briefs()
    assert [b["file_id"] for b in out] == ["20260619_050919_public"]


def test_facility_and_date_from_filename_when_meta_empty(briefs_dir):
    obj = {"brief_project_info": {"competition_name": "이름만", "sites": []}}
    (briefs_dir / "20260619_050919_public.json").write_text(
        json.dumps(obj, ensure_ascii=False), encoding="utf-8"
    )
    out = bi.list_briefs()
    assert out[0]["facility_type"] == "public"
    assert out[0]["analyzed_at"] == "2026-06-19T05:09:19"


def test_missing_dir_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("BRIEF_DIR", str(tmp_path / "nope"))
    bi._LIST_CACHE.clear()
    assert bi.list_briefs() == []


# ── feasibility_export 부분 채택 (2026-08-27) ─────────────────────────────────
# competition_comparison이 같은 파일에 넣어주는 정규화 블록에서 **우리가 못 뽑는
# 3종만** 가산한다. 전면 위임 안 함 — 실샘플 10건 대조 결과 정량치는 100% 일치했고,
# 블록이 없는 파일이 존재하며(10건 중 4건), 그쪽 블록엔 목표 연면적이 아예 없다.


def _brief_with_fe(fe: dict | None) -> dict:
    obj = {
        "_brief_meta": {"brief_id": "x", "facility_type": "public"},
        "brief_project_info": {
            "competition_name": "테스트공모",
            "sites": [{
                "site_id": "부지1", "address": "서울특별시 영등포구 당산동3가 385",
                "site_area_sqm": 7498, "floor_area_sqm": 30000,
                "building_coverage_pct": 60, "floor_area_ratio_pct": 460,
                "max_height_m": 100, "facilities": ["어린이집(노유자시설)"],
            }],
        },
    }
    if fe is not None:
        obj["feasibility_export"] = fe
    return obj


def _fe(version: int, **site_extra) -> dict:
    return {
        "schema_version": version,
        "sites": [{"site_id": "부지1", **site_extra}],
        "construction_cost_100m_won": 2686,
        "design_cost_100m_won": 124,
        "construction_period_months": 15,
    }


def test_fe_v2_adds_review_parking_and_scale():
    """v2 블록이면 심의 여부·주차대수·사업규모가 얹힌다."""
    m = bi.map_brief(_brief_with_fe(_fe(
        2, limits_determined_by="심의", required_parking_count=430,
        parking_note="부설주차장으로 430대",
    )))
    site = m["sites"][0]
    assert m["feasibility_export_used"] is True
    assert site["limits_determined_by"] == "심의"
    assert site["target_parking_count"] == 430
    assert site["parking_note"] == "부설주차장으로 430대"
    assert m["scale"]["construction_cost_100m_won"] == 2686


def test_fe_v1_is_gated_out():
    """v1에는 2차 필드가 없다 — 얹지 않는다."""
    m = bi.map_brief(_brief_with_fe(_fe(1, limits_determined_by="심의")))
    assert m["feasibility_export_used"] is False
    assert m["sites"][0]["limits_determined_by"] == ""


def test_no_fe_block_keeps_own_parsing():
    """블록이 없어도 자체 파싱 결과는 그대로 — 폴백은 영구히 필요하다."""
    m = bi.map_brief(_brief_with_fe(None))
    site = m["sites"][0]
    assert m["feasibility_export_used"] is False
    assert site["limits_determined_by"] == ""
    assert site["target_parking_count"] is None
    # 정량치·용도 감지는 블록과 무관하게 살아 있어야 한다
    assert site["target_far_pct"] == 460.0
    assert site["target_floor_area_sqm"] == 30000.0
    assert site["facility_use"] == "노유자시설"


def test_fe_does_not_overwrite_own_quantities():
    """블록이 있어도 정량치·연면적은 우리 파싱 값을 쓴다(그쪽 블록엔 연면적이 없다)."""
    m = bi.map_brief(_brief_with_fe(_fe(
        2, limits_determined_by="법정", floor_area_ratio_pct=999,
    )))
    site = m["sites"][0]
    assert site["target_far_pct"] == 460.0        # 999가 아니다
    assert site["target_floor_area_sqm"] == 30000.0


def test_fe_unknown_limits_value_rejected():
    """limits_determined_by는 심의/법정만 통과 — 모르는 값은 빈 값."""
    m = bi.map_brief(_brief_with_fe(_fe(2, limits_determined_by="협의")))
    assert m["sites"][0]["limits_determined_by"] == ""

