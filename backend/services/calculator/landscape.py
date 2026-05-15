"""조경 계산기.

건축법 제42조 + 시행령 제27조 — 대지 안의 조경 의무.

시행령 §27 ①항 면제 대상 (법제처 API 확인, 2026 현행):
  1호. 녹지지역에 건축하는 건축물
  2호. 면적 5천㎡ 미만 대지의 공장
  3호. 연면적 1,500㎡ 미만 공장
  4호. 산업단지의 공장
  5호. 염분/용도 특성상 곤란 — 건축조례
  6호. 축사
  7호. 가설건축물
  8호. 1,500㎡ 미만 물류시설 (주거·상업 제외)
  9호. 자연환경보전·농림·관리지역 (지구단위계획구역 제외)
  10호. 그 밖에 건축조례

시행령 §27 ②항 — 의무 비율:
  4호. 면적 200~300㎡ 미만 대지: 대지면적의 10% 이상
  그 외 일반 건축물 비율은 건축조례에 위임 — by_zone JSON은 지자체 평균 추정값.
  confidence 3 (지자체 조례 확인 필요).
"""
from __future__ import annotations

import json
import os

_STANDARDS: dict = {}


def _load_standards() -> dict:
    global _STANDARDS
    if _STANDARDS:
        return _STANDARDS
    cfg = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../config/landscape_standards.json")
    )
    with open(cfg, encoding="utf-8") as f:
        _STANDARDS = json.load(f)
    return _STANDARDS


def calculate(
    landscape_area: float | None,
    site_area: float,
    zone_use: str,
    building_use: str,
) -> dict:
    """조경 진단 결과.

    Args:
      landscape_area: 조경면적(㎡). 미입력 시 요건만 표시.
      site_area: 대지면적(㎡).
      zone_use: 용도지역.
      building_use: 건축물 용도.

    Returns:
      {category, actual_pct, required_pct, exempt, pass, deficit_m2,
       required_area_m2, score, confidence, source, law_refs, notes}
    """
    std = _load_standards()
    exempt_threshold = std.get("exempt_below_site_area", 200)

    exempt = False
    exempt_reason: str | None = None
    required_pct: float = 0.0

    # ── 시행령 §27 ①항 면제 (우선순위 순) ──────────────────────────────────
    # 1호: 녹지지역
    if _is_green_zone(zone_use):
        exempt = True
        exempt_reason = (
            f"{zone_use} 건축 — 조경 면제 (시행령 §27 ①항 1호: 녹지지역)"
        )
    # 9호: 자연환경보전·농림·관리지역 (단, 지구단위계획구역은 제외)
    elif _is_conservation_or_management_zone(zone_use):
        # 지구단위계획구역인지 확인은 사용자 입력 zone_district 등에 단서 필요.
        # 현재 calculator에는 그 정보가 없으므로 보수적으로 면제 처리 + 안내.
        exempt = True
        exempt_reason = (
            f"{zone_use} 건축 — 조경 면제 (시행령 §27 ①항 9호: "
            f"자연환경보전·농림·관리지역). 지구단위계획구역이면 면제 제외 — 별도 확인 필요"
        )
    # 6호: 축사
    elif "축사" in (building_use or ""):
        exempt = True
        exempt_reason = "축사 — 조경 면제 (시행령 §27 ①항 6호)"
    # 7호: 가설건축물
    elif "가설" in (building_use or ""):
        exempt = True
        exempt_reason = "가설건축물 — 조경 면제 (시행령 §27 ①항 7호)"
    # 2호: 면적 5천㎡ 미만 대지의 공장
    elif "공장" in (building_use or "") and site_area < 5000:
        exempt = True
        exempt_reason = (
            f"공장 + 대지 {site_area:.0f}㎡ < 5,000㎡ — 조경 면제 "
            f"(시행령 §27 ①항 2호)"
        )
    # 200㎡ 미만 대지 (시행령 §27 ②항 4호의 반대 — 200㎡ 이상부터 의무)
    elif site_area < exempt_threshold:
        exempt = True
        exempt_reason = (
            f"대지면적 {site_area:.0f}㎡ < {exempt_threshold}㎡ — 조경 의무 없음 "
            f"(시행령 §27 ②항 4호 적용 외)"
        )
    else:
        # ②항 4호: 200~300㎡ 미만은 10% 의무 (시행령 직접 명시)
        if site_area < 300:
            required_pct = 10.0
        else:
            # 그 외 비율은 시·도 조례 위임. by_zone JSON은 평균 추정값.
            required_pct = _required_ratio(building_use, site_area, zone_use, std)
        if required_pct == 0:
            exempt = True
            exempt_reason = f"용도 '{building_use}' 별 면제"

    required_area = round(site_area * required_pct / 100, 2)
    law_refs = _law_refs()

    # 조경면적 미입력 처리
    if landscape_area is None:
        if exempt:
            return _result(
                actual_pct=None,
                required_pct=required_pct,
                required_area=required_area,
                exempt=True,
                passed=True,
                deficit=0.0,
                score=10.0,
                confidence=5,
                source="건축법 시행령 제27조 (면제 대상)",
                law_refs=law_refs,
                notes=exempt_reason or "조경 의무 면제",
            )
        return _result(
            actual_pct=None,
            required_pct=required_pct,
            required_area=required_area,
            exempt=False,
            passed=None,
            deficit=None,
            score=None,
            confidence=3,
            source="건축법 시행령 제27조 별표 (지자체 조례 평균)",
            law_refs=law_refs,
            notes=(
                f"조경 의무 {required_pct:.0f}% 이상 (≈ {required_area:.0f}㎡). "
                f"조경면적 입력 시 적합 여부 자동 판정."
            ),
        )

    actual_pct = (landscape_area / site_area * 100) if site_area > 0 else 0.0

    if exempt:
        return _result(
            actual_pct=round(actual_pct, 2),
            required_pct=required_pct,
            required_area=required_area,
            exempt=True,
            passed=True,
            deficit=0.0,
            score=10.0,
            confidence=5,
            source="건축법 시행령 제27조 (면제 대상)",
            law_refs=law_refs,
            notes=(exempt_reason or "조경 의무 면제") + f" (계획 조경 {actual_pct:.1f}%)",
        )

    passed = actual_pct >= required_pct
    deficit = max(0.0, required_area - landscape_area)

    if not passed:
        score = 0.0
    else:
        margin_ratio = (actual_pct - required_pct) / required_pct if required_pct > 0 else 1.0
        if margin_ratio >= 0.3:
            score = 10.0
        elif margin_ratio >= 0.1:
            score = round(8.0 + (margin_ratio - 0.1) / 0.2 * 2.0, 1)
        else:
            score = round(7.0 + margin_ratio / 0.1 * 1.0, 1)

    return _result(
        actual_pct=round(actual_pct, 2),
        required_pct=required_pct,
        required_area=required_area,
        exempt=False,
        passed=passed,
        deficit=round(deficit, 2),
        score=round(score, 1),
        confidence=3,
        source="건축법 시행령 제27조 별표 (지자체 조례 평균)",
        law_refs=law_refs,
        notes=_notes(passed, actual_pct, required_pct, deficit, zone_use),
    )


def _is_green_zone(zone_use: str) -> bool:
    """녹지지역 — 시행령 §27 ①항 1호 면제."""
    if not zone_use:
        return False
    return any(kw in zone_use for kw in ("보전녹지", "생산녹지", "자연녹지"))


def _is_conservation_or_management_zone(zone_use: str) -> bool:
    """자연환경보전·농림·관리지역 — 시행령 §27 ①항 9호 면제 (지구단위계획구역 제외)."""
    if not zone_use:
        return False
    return any(kw in zone_use for kw in (
        "자연환경보전", "농림지역", "보전관리", "생산관리", "계획관리",
    ))


def _required_ratio(
    building_use: str,
    site_area: float,
    zone_use: str,
    std: dict,
) -> float:
    """의무 비율(%) 결정. by_use_override > by_zone > default."""
    by_use = std.get("by_use_override", {})
    for use_key, val in by_use.items():
        if use_key.startswith("_"):
            continue
        if use_key not in building_use and building_use not in use_key:
            continue
        # 면적 구간 (공장 등)
        if isinstance(val, dict) and "thresholds" in val:
            for t in val["thresholds"]:
                max_area = t.get("max_site_area")
                if max_area is None or site_area <= max_area:
                    return float(t["ratio"])
        elif isinstance(val, (int, float)):
            return float(val)

    by_zone = std.get("by_zone", {})
    if zone_use in by_zone and not zone_use.startswith("_"):
        return float(by_zone[zone_use])
    for key, val in by_zone.items():
        if key.startswith("_"):
            continue
        if zone_use and (zone_use in key or key in zone_use):
            return float(val)

    return float(std.get("default_required_pct", 15))


def _notes(
    passed: bool,
    actual: float,
    required: float,
    deficit: float,
    zone: str,
) -> str:
    if not passed:
        return (
            f"[주의] 조경 {actual:.1f}% < 의무 {required:.0f}% "
            f"({deficit:.0f}㎡ 부족). 인허가 보완 필요."
        )
    margin = actual - required
    return (
        f"조경 {actual:.1f}% / 의무 {required:.0f}% "
        f"({margin:.1f}%p 여유, {zone} 기준). 지자체 조례 강화 여부 별도 확인."
    )


def _result(**kwargs) -> dict:
    """카테고리 결과 dict 빌더."""
    return {
        "category": "조경",
        "actual_pct": kwargs["actual_pct"],
        "required_pct": kwargs["required_pct"],
        "required_area_m2": kwargs["required_area"],
        "exempt": kwargs["exempt"],
        "pass": kwargs["passed"],
        "deficit_m2": kwargs["deficit"],
        "score": kwargs["score"],
        "confidence": kwargs["confidence"],
        "source": kwargs["source"],
        "law_refs": kwargs["law_refs"],
        "notes": kwargs["notes"],
    }


def _law_refs() -> list[dict]:
    return [
        {
            "name": "건축법 제42조 (조경 등의 조치)",
            "url": "https://www.law.go.kr/법령/건축법/제42조",
        },
        {
            "name": "건축법 시행령 제27조 (대지의 조경)",
            "url": "https://www.law.go.kr/법령/건축법시행령/제27조",
        },
    ]
