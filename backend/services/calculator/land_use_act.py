"""행위제한 적합성 계산기 — LURIS API 기반.

LURIS 응답을 다른 카테고리(건폐율, 용적률 등)와 동일한 구조의 진단 카드로 변환.

판정:
  ALLOWED            → pass=True, score=10, confidence=5
  FORBIDDEN          → pass=False, score=0, confidence=5
  DATA_INSUFFICIENT  → pass=None, score=null, confidence=1 (LURIS DB 미수록)
  조회 실패/네트워크 → pass=None, score=null, confidence=1
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from services.luris_client import LurisClient

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
) -> dict:
    """행위제한 진단.

    Args:
      luris: LurisClient 인스턴스 (None 시 미설정 결과)
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

    if luris is None:
        base["notes"] = "LurisClient 미초기화 — 행위제한 자동 검증 불가"
        return base

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

    info = await luris.get_act_info(area_cd, ucode, land_use_nm)
    if info is None:
        base["notes"] = "LURIS 조회 실패 (네트워크/한도) — 별도 검토 필요"
        return base

    summary = info.get("summary") or {}
    verdict = summary.get("verdict", "DATA_INSUFFICIENT")
    acts = info.get("acts") or []

    # 가능/금지 행위명 모음 (notes·law_refs용)
    allowed_items: list[str] = []
    forbidden_items: list[str] = []
    law_refs_set: list[str] = []
    for act in acts:
        for it in act.get("items", []):
            name = it.get("name", "")
            ref = it.get("law_ref", "")
            if not name:
                continue
            if "가능" in act.get("allowed", ""):
                allowed_items.append(name)
            elif "금지" in act.get("allowed", "") or "불가" in act.get("allowed", ""):
                forbidden_items.append(name)
            if ref and ref not in law_refs_set:
                law_refs_set.append(ref)

    zone_label = f"{info.get('zone_name', zone_use)} ({info.get('zone_code', ucode)})"

    if verdict == "ALLOWED":
        base["pass"] = True
        base["score"] = 10.0
        base["confidence"] = 5
        items_str = ", ".join(allowed_items[:6])
        if len(allowed_items) > 6:
            items_str += f" 외 {len(allowed_items) - 6}건"
        base["notes"] = (
            f"{zone_label}에서 '{building_use}' 건축 가능. "
            f"허용 세부 용도: {items_str}"
        )
    elif verdict == "FORBIDDEN":
        base["pass"] = False
        base["score"] = 0.0
        base["confidence"] = 5
        items_str = ", ".join(forbidden_items[:6])
        if len(forbidden_items) > 6:
            items_str += f" 외 {len(forbidden_items) - 6}건"
        base["notes"] = (
            f"⚠ {zone_label}에서 '{building_use}' 건축 **불가**. "
            f"금지 세부 용도: {items_str}. 용도지역 또는 건물용도 변경 필요."
        )
    elif verdict == "MIXED":
        base["pass"] = None
        base["score"] = 5.0
        base["confidence"] = 3
        base["notes"] = (
            f"{zone_label}에서 '{building_use}' 일부 가능/일부 금지 (조건부). "
            f"가능 {len(allowed_items)}건 / 금지 {len(forbidden_items)}건 — 세부 검토 필요."
        )
    else:  # DATA_INSUFFICIENT
        base["pass"] = None
        base["score"] = None
        base["confidence"] = 1
        base["notes"] = (
            f"{zone_label}에서 '{building_use}' 행위제한 데이터 미수록 (LURIS DB). "
            f"해당 시군구 도시계획조례 별표·국토계획법 시행령 별표 직접 확인 필요."
        )

    # LURIS 인용 법령을 law_refs에 추가 (앞 3개만)
    extra_refs = [
        {"name": r, "url": _law_search_url(r)}
        for r in law_refs_set[:3]
    ]
    base["law_refs"] = _law_refs() + extra_refs

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
