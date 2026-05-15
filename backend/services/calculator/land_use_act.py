"""행위제한 적합성 계산기 — LURIS + 토지이음(EUM) 교차검증.

두 API 응답을 비교해 verdict 머지:
  - 두 소스 모두 ALLOWED/FORBIDDEN 일치  → confidence 5 (교차검증)
  - 한쪽만 데이터 보유                  → 그 결과 사용, confidence 4
  - 두 소스 verdict 불일치              → pass=None, confidence 2 (수동 검토 요청)
  - 양쪽 모두 미수록/조회실패           → DATA_INSUFFICIENT, confidence 1
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from services.luris_client import LurisClient

if TYPE_CHECKING:
    from services.eum_client import EumClient

logger = logging.getLogger(__name__)

_MAPPING_PATH = Path(__file__).parent.parent.parent / "config" / "ucode_mapping.json"
_MAPPING_CACHE: dict | None = None


def _load_mapping() -> dict:
    global _MAPPING_CACHE
    if _MAPPING_CACHE is None:
        with open(_MAPPING_PATH, encoding="utf-8") as f:
            _MAPPING_CACHE = json.load(f)
    return _MAPPING_CACHE


async def calculate(
    luris: LurisClient | None,
    *,
    zone_use: str,
    building_use: str,
    jurisdiction_code: str,
    eum: "EumClient | None" = None,
) -> dict:
    """행위제한 진단 — LURIS + EUM 교차검증.

    Args:
      luris: LurisClient 인스턴스 (None 시 EUM 단독 사용)
      eum: EumClient 인스턴스 (None 시 LURIS 단독 사용 — 기존 동작)
      zone_use: 용도지역 한글 (예: '제2종일반주거지역')
      building_use: 건물 용도 한글 (예: '공동주택')
      jurisdiction_code: 시군구코드 (PNU 앞 5자리, 예: '11680')

    Returns:
      표준 카테고리 카드 dict
    """
    base = {
        "category": "행위제한",
        "actual_pct": None,
        "limit_pct": None,
        "pass": None,
        "excess_pct": 0.0,
        "score": None,
        "confidence": 1,
        "source": "🏛 LURIS (토지이용규제정보)",
        "law_refs": _law_refs(),
        "notes": "",
    }

    mapping = _load_mapping()
    ucode = mapping["zone_use_to_ucode"].get(zone_use, "")
    land_use_nm = mapping["building_use_to_land_use_nm"].get(building_use, building_use)
    area_cd = (jurisdiction_code or "")[:5]

    if not ucode:
        base["notes"] = f"용도지역 '{zone_use}' 코드 매핑 없음 — 행위제한 검증 불가"
        return base
    if not area_cd:
        base["notes"] = "시군구코드 미확인 — 행위제한 검증 불가"
        return base
    if not land_use_nm:
        base["notes"] = f"건물용도 '{building_use}' 매핑 없음"
        return base

    luris_active = luris is not None and bool(getattr(luris, "_key", ""))
    eum_active = eum is not None and getattr(eum, "available", False)

    if not luris_active and not eum_active:
        base["notes"] = "LURIS / EUM 모두 비활성 — 행위제한 자동 검증 불가"
        return base

    # ── 두 소스 병렬 조회 ────────────────────────────────────────────────
    luris_task = (
        luris.get_act_info(area_cd, ucode, land_use_nm)
        if luris_active else _none_coro()
    )
    eum_task = (
        eum.get_act_restriction_cached(area_cd, ucode, land_use_nm)
        if eum_active else _none_coro()
    )
    luris_info, eum_list = await asyncio.gather(luris_task, eum_task)

    luris_summary = _summarize_luris(luris_info, zone_use, ucode)
    eum_summary = _summarize_eum(eum_list, zone_use, ucode)

    # ── 머지 ────────────────────────────────────────────────────────────
    return _merge_verdicts(base, luris_summary, eum_summary, building_use)


async def _none_coro():
    """비활성 소스용 placeholder coroutine."""
    return None


def _summarize_luris(info: dict | None, zone_use: str, ucode: str) -> dict:
    """LURIS 응답 → 표준 summary dict.

    반환:
      {available, verdict, zone_label, allowed_items, forbidden_items, law_refs}
      verdict ∈ {ALLOWED, FORBIDDEN, MIXED, DATA_INSUFFICIENT, UNAVAILABLE}
    """
    if info is None:
        return {"available": False, "verdict": "UNAVAILABLE",
                "zone_label": f"{zone_use} ({ucode})", "allowed_items": [],
                "forbidden_items": [], "law_refs": []}
    summary = info.get("summary") or {}
    verdict = summary.get("verdict", "DATA_INSUFFICIENT")
    acts = info.get("acts") or []
    allowed_items, forbidden_items, law_refs_set = _collect_items(acts)
    return {
        "available": True,
        "verdict": verdict,
        "zone_label": f"{info.get('zone_name', zone_use)} ({info.get('zone_code', ucode)})",
        "allowed_items": allowed_items,
        "forbidden_items": forbidden_items,
        "law_refs": law_refs_set,
    }


def _summarize_eum(eum_list: list | None, zone_use: str, ucode: str) -> dict:
    """EUM 응답 → 표준 summary dict."""
    if eum_list is None:
        return {"available": False, "verdict": "UNAVAILABLE",
                "zone_label": f"{zone_use} ({ucode})", "allowed_items": [],
                "forbidden_items": [], "law_refs": []}

    # 첫 ucode 결과만 사용 (단일 ucode 조회이므로 항목 1개 예상)
    rec = eum_list[0] if eum_list else None
    if rec is None:
        return {"available": True, "verdict": "DATA_INSUFFICIENT",
                "zone_label": f"{zone_use} ({ucode})", "allowed_items": [],
                "forbidden_items": [], "law_refs": []}

    # EUM act_reg_list 항목 구조: act_nm, reg_nm, lu_info_list[node_desc, lu_ref_law_nm1/2/3, def_ref]
    acts: list[dict] = []
    for item in rec.get("act_reg_list", []) or []:
        reg = (item.get("reg_nm") or "").strip()
        items_norm: list[dict] = []
        for li in item.get("lu_info_list", []) or []:
            node = (li.get("node_desc") or "").strip()
            if not node or node == "관련내용 없음":
                continue
            items_norm.append({
                "name": node,
                "law_ref": (li.get("lu_ref_law_nm1") or "").strip(),
            })
        if not items_norm and not reg:
            continue
        acts.append({"name": (item.get("act_nm") or "").strip(),
                     "allowed": reg, "items": items_norm})

    allowed_items, forbidden_items, law_refs_set = _collect_items(acts)
    has_real = bool(allowed_items or forbidden_items)
    if not has_real:
        verdict = "DATA_INSUFFICIENT"
    elif allowed_items and not forbidden_items:
        verdict = "ALLOWED"
    elif forbidden_items and not allowed_items:
        verdict = "FORBIDDEN"
    else:
        verdict = "MIXED"

    zone_name = (rec.get("uname") or zone_use).strip()
    zone_code = (rec.get("ucode") or ucode).strip()
    return {
        "available": True,
        "verdict": verdict,
        "zone_label": f"{zone_name} ({zone_code})",
        "allowed_items": allowed_items,
        "forbidden_items": forbidden_items,
        "law_refs": law_refs_set,
    }


def _collect_items(acts: list[dict]) -> tuple[list[str], list[str], list[str]]:
    """acts → (allowed_items, forbidden_items, law_refs) — LURIS·EUM 공통 형식."""
    allowed: list[str] = []
    forbidden: list[str] = []
    refs: list[str] = []
    for act in acts:
        allowed_label = act.get("allowed", "") or ""
        for it in act.get("items", []) or []:
            name = it.get("name", "")
            ref = it.get("law_ref", "")
            if not name:
                continue
            if "가능" in allowed_label:
                allowed.append(name)
            elif "금지" in allowed_label or "불가" in allowed_label:
                forbidden.append(name)
            if ref and ref not in refs:
                refs.append(ref)
    return allowed, forbidden, refs


def _merge_verdicts(
    base: dict, luris_s: dict, eum_s: dict, building_use: str,
) -> dict:
    """LURIS · EUM verdict 머지 → 진단 카드."""
    decisive = {"ALLOWED", "FORBIDDEN"}
    l_v, e_v = luris_s["verdict"], eum_s["verdict"]
    l_has = l_v in decisive
    e_has = e_v in decisive

    sources_used: list[str] = []
    if luris_s["available"]:
        sources_used.append("LURIS")
    if eum_s["available"]:
        sources_used.append("EUM(토지이음)")

    # 한쪽도 응답 안 했을 때
    if not luris_s["available"] and not eum_s["available"]:
        base["notes"] = "LURIS / EUM 모두 조회 실패 (네트워크/한도) — 별도 검토 필요"
        base["source"] = "🏛 LURIS + EUM (둘 다 조회 실패)"
        return base

    label = (luris_s["zone_label"] if l_has else eum_s["zone_label"]) or "용도지역"
    all_items = list({*luris_s["allowed_items"], *eum_s["allowed_items"]})
    forb_items = list({*luris_s["forbidden_items"], *eum_s["forbidden_items"]})
    refs = []
    for r in luris_s["law_refs"] + eum_s["law_refs"]:
        if r and r not in refs:
            refs.append(r)

    # 둘 다 결정적 verdict — 일치하면 강화, 불일치면 검토 요청
    if l_has and e_has:
        if l_v == e_v:
            verdict = l_v
            confidence = 5
            cross = " (LURIS·EUM 교차검증 일치)"
        else:
            base["pass"] = None
            base["score"] = None
            base["confidence"] = 2
            base["source"] = "🏛 LURIS + 🌿 EUM (교차검증 불일치)"
            base["notes"] = (
                f"❗ {label}에서 '{building_use}': LURIS는 '{l_v}', "
                f"EUM은 '{e_v}' — 결과 불일치. 시군구 조례 직접 확인 필요."
            )
            base["law_refs"] = _law_refs() + [
                {"name": r, "url": _law_search_url(r)} for r in refs[:3]
            ]
            return base
    elif l_has:
        verdict = l_v
        confidence = 4 if eum_s["available"] else 5
        cross = " (LURIS 단독 — EUM 미수록)" if eum_s["available"] else ""
    elif e_has:
        verdict = e_v
        confidence = 4 if luris_s["available"] else 5
        cross = " (EUM 단독 — LURIS 미수록)" if luris_s["available"] else ""
    else:
        # 둘 다 MIXED 또는 DATA_INSUFFICIENT
        if "MIXED" in (l_v, e_v):
            base["pass"] = None
            base["score"] = 5.0
            base["confidence"] = 3
            base["source"] = "🏛 LURIS + 🌿 EUM (조건부 / 일부 가능)"
            base["notes"] = (
                f"{label}에서 '{building_use}' 일부 가능/일부 금지 (조건부). "
                f"가능 {len(all_items)}건 / 금지 {len(forb_items)}건 — 세부 검토 필요."
            )
            base["law_refs"] = _law_refs() + [
                {"name": r, "url": _law_search_url(r)} for r in refs[:3]
            ]
            return base
        # 둘 다 DATA_INSUFFICIENT
        base["pass"] = None
        base["score"] = None
        base["confidence"] = 1
        base["source"] = f"🏛 {' + '.join(sources_used)} (데이터 미수록)"
        base["notes"] = (
            f"{label}에서 '{building_use}' 행위제한 데이터 미수록 "
            f"({', '.join(sources_used)} DB). "
            "해당 시군구 도시계획조례 별표·국토계획법 시행령 별표 직접 확인 필요."
        )
        return base

    base["source"] = f"🏛 {' + '.join(sources_used)}{cross}"
    if verdict == "ALLOWED":
        base["pass"] = True
        base["score"] = 10.0
        base["confidence"] = confidence
        items_str = ", ".join(all_items[:6])
        if len(all_items) > 6:
            items_str += f" 외 {len(all_items) - 6}건"
        base["notes"] = (
            f"{label}에서 '{building_use}' 건축 가능{cross}. "
            f"허용 세부 용도: {items_str}"
        )
    elif verdict == "FORBIDDEN":
        base["pass"] = False
        base["score"] = 0.0
        base["confidence"] = confidence
        items_str = ", ".join(forb_items[:6])
        if len(forb_items) > 6:
            items_str += f" 외 {len(forb_items) - 6}건"
        base["notes"] = (
            f"⚠ {label}에서 '{building_use}' 건축 **불가**{cross}. "
            f"금지 세부 용도: {items_str}. 용도지역 또는 건물용도 변경 필요."
        )

    base["law_refs"] = _law_refs() + [
        {"name": r, "url": _law_search_url(r)} for r in refs[:3]
    ]
    return base


def _law_refs() -> list[dict]:
    return [
        {
            "name": "국토계획법 제76조 (용도지역·용도지구의 건축물 등 제한)",
            "url": "https://www.law.go.kr/법령/국토의계획및이용에관한법률/제76조",
        },
        {
            "name": "건축법 제19조 (용도변경)",
            "url": "https://www.law.go.kr/법령/건축법/제19조",
        },
    ]


def _law_search_url(law_text: str) -> str:
    """법령 인용 텍스트를 법령정보 검색 URL로 (대략적 변환)."""
    import urllib.parse
    return f"https://www.law.go.kr/lsSc.do?menuId=1&query={urllib.parse.quote(law_text)}"
