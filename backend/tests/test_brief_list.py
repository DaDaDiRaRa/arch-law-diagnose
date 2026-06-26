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
