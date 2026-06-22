"""사전 사업성 검토 결과 → 1장 요약 Markdown / xlsx.

run_feasibility() 응답(result)을 시니어 보고용 한 장 요약으로 변환.
LLM 호출 없음 — 기존 데이터를 표로 렌더링만.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def _num(v: Any, d: int = 0) -> str:
    if v is None or v == "":
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if d == 0:
        return f"{f:,.0f}"
    return f"{f:,.{d}f}"


def _site_source_label(src: str | None) -> str:
    return {
        "user_override": "수동 입력",
        "auto": "자동 조회",
        "default_1000": "기본값(1000㎡)",
    }.get(src or "", src or "—")


def _gap_label(status: str | None) -> str:
    return {
        "ok": "충족",
        "over": "초과",
        "unknown": "확인 불가",
        "no_target": "요구 없음",
    }.get(status or "", status or "—")


# ── Markdown ────────────────────────────────────────────────────────────
def to_markdown(
    result: dict,
    form_data: dict | None = None,
    project_name: str = "",
    company: str = "",
    author: str = "",
) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    address = result.get("address") or "—"
    land = result.get("land_facts") or {}
    proposal = result.get("proposal") or {}
    categories = result.get("categories") or []
    review = result.get("review_burden") or {}
    rec = result.get("overall_recommendation") or {}

    L: list[str] = []
    L.append("# 사전 사업성 검토 요약")
    L.append("")
    if project_name:
        L.append(f"- **프로젝트**: {project_name}")
    L.append(f"- **주소**: {address}")
    L.append(f"- **작성일**: {today}")
    if company or author:
        L.append(f"- **작성**: {company} {author}".rstrip())
    L.append("")

    # 종합 판단
    L.append("## 종합 판단")
    L.append(f"**{rec.get('verdict', '—')}** — {rec.get('reason', '')}")
    L.append("")

    # 대지 정보
    L.append("## 대지 정보")
    L.append("| 항목 | 값 |")
    L.append("| --- | --- |")
    L.append(f"| 용도지역 | {land.get('zone_use') or '미확인'} |")
    L.append(f"| 지역지구 | {land.get('zone_district') or '—'} |")
    L.append(
        f"| 대지면적 | {_num(result.get('site_area_used'))}㎡ "
        f"({_site_source_label(result.get('site_area_source'))}) |"
    )
    L.append("")

    # 가능 범위 제안
    L.append("## 이 대지에 지을 수 있는 범위")
    L.append("| 항목 | 값 | 비고 |")
    L.append("| --- | --- | --- |")
    cov = proposal.get("max_building_coverage_pct")
    L.append(
        f"| 최대 건폐율 | {_num(cov, 1)}% | 최대 건축면적 "
        f"{_num(proposal.get('max_building_area_sqm'))}㎡ |"
    )
    far = proposal.get("far_pct")
    far_relief = proposal.get("max_far_pct_relief")
    far_note = (
        f"완화 시 최대 {_num(far_relief, 1)}%"
        if far_relief and far and far_relief > far else "—"
    )
    L.append(f"| 최대 용적률 | {_num(far, 1)}% | {far_note} |")
    fa = proposal.get("max_floor_area_sqm")
    fa_relief = proposal.get("max_floor_area_relief_sqm")
    fa_note = (
        f"완화 시 {_num(fa_relief)}㎡"
        if fa_relief and fa and fa_relief > fa else "용적률 한도 기준"
    )
    L.append(f"| 가능 연면적 | {_num(fa)}㎡ | {fa_note} |")
    L.append(
        f"| 권장 주차대수 | {_num(proposal.get('recommended_parking_spaces'))}대 | "
        f"최대 연면적 기준 |"
    )
    L.append("")
    relief_items = proposal.get("applied_relief_items") or []
    if relief_items:
        labels = ", ".join(it.get("label") or it.get("kind", "") for it in relief_items)
        L.append(f"적용 완화: {labels}")
        L.append("")

    # 갭 분석 (target 있을 때만)
    has_target = any(
        (c.get("gap_analysis") or {}).get("has_target") for c in categories
    )
    if has_target:
        L.append("## 공모 요구치 대비 (갭 분석)")
        L.append("| 카테고리 | 공모 요구 | 법적 가능 | 판정 |")
        L.append("| --- | --- | --- | --- |")
        for c in categories:
            gap = c.get("gap_analysis") or {}
            if not gap.get("has_target"):
                continue
            unit = c.get("unit", "")
            L.append(
                f"| {c.get('label')} | {_num(c.get('competition_target'), 1)}{unit} | "
                f"{_num(c.get('legal_limit'), 1)}{unit} | "
                f"{_gap_label(gap.get('status'))} ({gap.get('gap_text', '')}) |"
            )
        L.append("")

        # 완화 시나리오
        scen_cat = next(
            (c for c in categories if c.get("key") == "far" and c.get("scenarios")),
            None,
        )
        if scen_cat:
            L.append("## 용적률 완화 시나리오")
            L.append("| 완화 항목 | 적용 후 | 충족 |")
            L.append("| --- | --- | --- |")
            for s in scen_cat.get("scenarios", []):
                L.append(
                    f"| {s.get('label', '')} | {_num(s.get('result_pct'), 1)}% | "
                    f"{'충족' if s.get('covers_target') else '부족'} |"
                )
            L.append("")

    # 심의 부담
    L.append("## 심의·평가 부담")
    req_items = review.get("required") or []
    maybe_items = review.get("maybe") or []
    if req_items:
        L.append(f"**필수 ({len(req_items)})**")
        for r in req_items:
            L.append(f"- {r.get('name', '')} — {r.get('reason', '')}")
    if maybe_items:
        L.append("")
        L.append(f"**조건부 ({len(maybe_items)})**")
        for r in maybe_items:
            L.append(f"- {r.get('name', '')} — {r.get('reason', '')}")
    if not req_items and not maybe_items:
        L.append("자동 트리거된 심의·평가 없음.")
    L.append("")

    L.append("---")
    L.append(
        "사전 사업성 검토는 참여 판단 보조용입니다. "
        "실제 인허가 가능성은 시니어 건축사 검토가 필수입니다."
    )
    return "\n".join(L)


# ── xlsx ────────────────────────────────────────────────────────────────
def to_xlsx(
    result: dict,
    form_data: dict | None = None,
    project_name: str = "",
    company: str = "",
    author: str = "",
) -> bytes:
    import io

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    today = datetime.now().strftime("%Y-%m-%d")
    land = result.get("land_facts") or {}
    proposal = result.get("proposal") or {}
    categories = result.get("categories") or []
    review = result.get("review_burden") or {}
    rec = result.get("overall_recommendation") or {}

    header_fill = PatternFill(start_color="F1F3F5", end_color="F1F3F5", fill_type="solid")
    accent_fill = PatternFill(start_color="E60012", end_color="E60012", fill_type="solid")
    bold = Font(bold=True)
    white_bold = Font(bold=True, color="FFFFFF")
    title_font = Font(bold=True, size=16)
    wrap = Alignment(wrap_text=True, vertical="top")

    wb = Workbook()

    # ── Sheet 1: 사업성 요약 ────────────────────────────────────────────
    ws = wb.active
    ws.title = "사업성요약"
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 24
    ws.column_dimensions["C"].width = 30

    r = 1
    ws.cell(r, 1, "사전 사업성 검토 요약").font = title_font
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
    r += 1
    for label, val in [
        ("프로젝트", project_name or "—"),
        ("주소", result.get("address") or "—"),
        ("작성일", today),
        ("작성", f"{company} {author}".strip() or "—"),
    ]:
        ws.cell(r, 1, label).font = bold
        ws.cell(r, 2, val)
        r += 1
    r += 1

    def section(title: str):
        nonlocal r
        c = ws.cell(r, 1, title)
        c.font = white_bold
        c.fill = accent_fill
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
        r += 1

    def row(label: str, *vals: str):
        nonlocal r
        ws.cell(r, 1, label).font = bold
        for i, v in enumerate(vals):
            ws.cell(r, 2 + i, v).alignment = wrap
        r += 1

    section("종합 판단")
    row(rec.get("verdict", "—"), rec.get("reason", ""))
    ws.cell(r - 1, 2).alignment = wrap
    r += 1

    section("대지 정보")
    row("용도지역", land.get("zone_use") or "미확인")
    row("지역지구", land.get("zone_district") or "—")
    row("대지면적", f"{_num(result.get('site_area_used'))}㎡ ({_site_source_label(result.get('site_area_source'))})")
    r += 1

    section("이 대지에 지을 수 있는 범위")
    row("최대 건폐율", f"{_num(proposal.get('max_building_coverage_pct'), 1)}%", f"최대 건축면적 {_num(proposal.get('max_building_area_sqm'))}㎡")
    far = proposal.get("far_pct")
    far_relief = proposal.get("max_far_pct_relief")
    row("최대 용적률", f"{_num(far, 1)}%", f"완화 시 최대 {_num(far_relief, 1)}%" if far_relief and far and far_relief > far else "—")
    fa = proposal.get("max_floor_area_sqm")
    fa_relief = proposal.get("max_floor_area_relief_sqm")
    row("가능 연면적", f"{_num(fa)}㎡", f"완화 시 {_num(fa_relief)}㎡" if fa_relief and fa and fa_relief > fa else "용적률 한도 기준")
    row("권장 주차대수", f"{_num(proposal.get('recommended_parking_spaces'))}대", "최대 연면적 기준")
    r += 1

    # 갭 분석
    has_target = any((c.get("gap_analysis") or {}).get("has_target") for c in categories)
    if has_target:
        section("공모 요구치 대비 (갭 분석)")
        for col, txt in enumerate(["카테고리", "공모 요구", "법적 가능"]):
            cell = ws.cell(r, 1 + col, txt)
            cell.font = bold
            cell.fill = header_fill
        r += 1
        for c in categories:
            gap = c.get("gap_analysis") or {}
            if not gap.get("has_target"):
                continue
            unit = c.get("unit", "")
            ws.cell(r, 1, f"{c.get('label')} — {_gap_label(gap.get('status'))}")
            ws.cell(r, 2, f"{_num(c.get('competition_target'), 1)}{unit}")
            ws.cell(r, 3, f"{_num(c.get('legal_limit'), 1)}{unit}")
            r += 1

    # ── Sheet 2: 심의·평가 ──────────────────────────────────────────────
    ws2 = wb.create_sheet("심의평가")
    ws2.column_dimensions["A"].width = 12
    ws2.column_dimensions["B"].width = 26
    ws2.column_dimensions["C"].width = 50
    for col, txt in enumerate(["구분", "항목", "사유"]):
        cell = ws2.cell(1, 1 + col, txt)
        cell.font = white_bold
        cell.fill = accent_fill
    rr = 2
    for kind, items in [("필수", review.get("required") or []), ("조건부", review.get("maybe") or [])]:
        for it in items:
            ws2.cell(rr, 1, kind)
            ws2.cell(rr, 2, it.get("name", "")).alignment = wrap
            ws2.cell(rr, 3, it.get("reason", "")).alignment = wrap
            rr += 1
    if rr == 2:
        ws2.cell(2, 1, "자동 트리거된 심의·평가 없음")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
