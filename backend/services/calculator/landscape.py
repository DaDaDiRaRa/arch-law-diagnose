"""조경 계산기.

건축법 제42조: 조경 등의 조치
건축법 시행령 제27조 + 별표 1: 대지 안의 조경 의무 비율

면제:
- 대지면적 200㎡ 미만
- 공장(1500㎡ 미만 등) 면적 구간별 특례

V1 한계: 지자체 도시계획조례 평균값 사용. 실제 의무비율은 지역별 편차가 크므로
충족 시에도 confidence 3 (지자체 조례 확인 필요).
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

    if site_area < exempt_threshold:
        exempt = True
        exempt_reason = (
            f"대지면적 {site_area:.0f}㎡ < {exempt_threshold}㎡ — 조경 의무 면제"
        )
        required_pct: float = 0.0
    else:
        required_pct = _required_ratio(building_use, site_area, zone_use, std)
        if required_pct == 0:
            exempt = True
            exempt_reason = f"용도 '{building_use}' 면적 구간 면제"

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
