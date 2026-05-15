"""높이·일조 계산기.

근거 (법제처 API 확인, 2026 현행):
- 건축법 제60조: 가로구역별 최고높이는 허가권자가 지정·공고
  - 시행령 §82: 도로 너비, 도시미관 등 고려해 결정. **"도로 너비 × N배" 같은 일반 규정 없음**
- 건축법 제61조 + 시행령 §86 (2023.9.12 개정 현행):
  ① 전용·일반주거지역: 정북방향 인접 대지경계선으로부터
     1. 높이 10m 이하 부분: 1.5m 이상 이격
     2. 높이 10m 초과 부분: 해당 부분 높이의 1/2 이상 이격
  ② 적용 제외:
     1. 너비 20m 이상 도로 접한 대지 상호간 (특정 구역)
     2. 건축협정구역 안 대지 상호간 (협정에 일정거리 띄움 포함 시)
     3. 정북방향 인접 대지가 비주거지역인 경우
  ③ 공동주택: 채광창 벽면 → 인접 대지경계선 수평거리의 2배
     (근린상업·준주거 4배) 이하로 높이 제한 + 동간거리

판정 로직 (V2):
- 입력값 충분 (북측 이격거리 + 인접조건 1개 이상) → 자동 pass/fail
- 입력값 부족 → pass=None, 위험도 기반 score, 필수 수동검토 표시
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def calculate(
    height: float,
    floors_above: int,
    zone_use: str,
    road_width: float | None = None,
    *,
    north_setback_m: float | None = None,
    adjacent_zone_north: str | None = None,
    road_20m_adjacent: bool | None = None,
    street_block_max_height_m: float | None = None,
    parcel_geometry: dict | None = None,
) -> dict:
    """높이·일조 진단 결과.

    Args:
      height: 건물 높이 (m)
      floors_above: 지상 층수
      zone_use: 우리 대지 용도지역
      road_width: 전면도로 폭 (m)
      north_setback_m: 정북 인접대지경계선까지 실제 이격거리 (m) — 입력 시 자동 판정
      adjacent_zone_north: 정북 방향 인접대지 용도지역 — '비주거' 키워드 포함 시 §86 ②항 3호 적용 제외
      road_20m_adjacent: 너비 20m 이상 도로 접함 여부 — True 시 §86 ②항 1호 적용 제외
      street_block_max_height_m: 가로구역별 최고높이 지정값 (m) — 있으면 §60 자동 비교
      parcel_geometry: VWorld 지적도 폴리곤 (GeoJSON dict) — 보조 정보로 정북 방향 필지 깊이 계산
    """
    shadow_applies = _shadow_applies(zone_use)
    shadow_min_setback_m = round(max(1.5, height / 2), 2) if shadow_applies else None

    # ─── 적용 제외 사유 판단 (§86 ②항) ──────────────────────────────────
    exemptions: list[str] = []
    if shadow_applies:
        if road_20m_adjacent is True:
            exemptions.append("너비 20m 이상 도로 접함 (§86 ②항 1호)")
        if adjacent_zone_north and "비주거" in adjacent_zone_north:
            exemptions.append("정북 인접대지 비주거지역 (§86 ②항 3호)")
        elif adjacent_zone_north:
            from services.zone_use_normalizer import category_of
            adj_cat = category_of(adjacent_zone_north)
            if adj_cat and adj_cat not in ("전용주거", "일반주거", "주거"):
                exemptions.append(
                    f"정북 인접대지 비주거지역 ({adjacent_zone_north} → {adj_cat}계, §86 ②항 3호)"
                )

    effective_shadow_applies = shadow_applies and not exemptions

    # ─── 폴리곤 기반 보조 정보: 정북 방향 필지 깊이 ────────────────────────
    parcel_north_depth_m = _compute_north_depth(parcel_geometry) if parcel_geometry else None

    # ─── 자동 pass/fail 판정 ──────────────────────────────────────────────
    pass_value: bool | None = None
    score: int
    confidence: int
    judgement_notes: list[str] = []

    # 1. 가로구역별 최고높이 위반 우선 검사 (§60)
    if street_block_max_height_m is not None and street_block_max_height_m > 0:
        if height > street_block_max_height_m:
            pass_value = False
            score = 0
            confidence = 5
            judgement_notes.append(
                f"❌ 가로구역 최고높이 {street_block_max_height_m}m 초과 — "
                f"실제 {height}m (§60 위반)"
            )
        else:
            judgement_notes.append(
                f"✓ 가로구역 최고높이 {street_block_max_height_m}m 이하 (실제 {height}m, §60)"
            )

    # 2. 정북 일조 사선 자동 판정 (입력 충분 시)
    if pass_value is None:  # 가로구역 위반이 아니면
        if not shadow_applies:
            # 정북 일조 미적용 용도지역
            pass_value = True
            score = 8
            confidence = 4
            judgement_notes.append(
                f"✓ 정북 일조 사선 미적용 용도지역 ({zone_use}) — §86 ①항 비대상"
            )
        elif exemptions:
            # 적용 제외 사유 존재
            pass_value = True
            score = 9
            confidence = 4
            judgement_notes.append(
                f"✓ 정북 일조 사선 적용 제외: {' / '.join(exemptions)}"
            )
        elif north_setback_m is not None and north_setback_m >= 0:
            # 사선 적용 + 이격거리 입력 → 자동 판정
            required = shadow_min_setback_m or 1.5
            if north_setback_m >= required:
                pass_value = True
                score = 10 if north_setback_m >= required * 1.2 else 8
                confidence = 5
                judgement_notes.append(
                    f"✓ 정북 이격 {north_setback_m}m ≥ 필요 {required}m (§86 ①항)"
                )
            else:
                pass_value = False
                score = 0
                confidence = 5
                judgement_notes.append(
                    f"❌ 정북 이격 {north_setback_m}m < 필요 {required}m "
                    f"(부족 {required - north_setback_m:.2f}m, §86 ①항 위반)"
                )
        else:
            # 사선 적용 + 이격거리 미입력 → 수동검토
            pass_value = None
            if height <= 10:
                score = 6
            elif height <= 20:
                score = 5
            else:
                score = 4
            confidence = 2
            judgement_notes.append(
                f"⚠ 정북 일조 사선 적용 대상 (필요 이격 {shadow_min_setback_m}m). "
                "정북 이격거리 미입력 — 자동 판정 불가, 필수 수동검토."
            )

    # ─── 컨텍스트 notes 빌드 ───────────────────────────────────────────────
    context_notes: list[str] = [
        f"건물 높이 {height}m / 지상 {floors_above}층.",
    ]
    if road_width:
        if street_block_max_height_m:
            context_notes.append(f"전면도로 폭 {road_width}m, 가로구역 최고높이 {street_block_max_height_m}m 지정됨.")
        else:
            context_notes.append(
                f"전면도로 폭 {road_width}m — 가로구역 최고높이 지정 여부 별도 확인 필요 "
                f"(§60·시행령 §82; 일반 '도로폭×N배' 자동 산정 규정 없음)."
            )
    if shadow_applies and not effective_shadow_applies:
        context_notes.append(f"정북 일조 사선 적용 제외: {', '.join(exemptions)}")
    elif not shadow_applies:
        context_notes.append(
            "정북 일조 사선 미적용 용도지역. "
            "공동주택인 경우 §86 ③항 인동거리(채광창 기준 2배, 근린상업·준주거 4배) 별도 검토."
        )
    if parcel_north_depth_m is not None:
        context_notes.append(
            f"📐 폴리곤 기반 정북 방향 필지 최대 깊이 ≈ {parcel_north_depth_m:.1f}m "
            "(보조 정보 — 실제 이격거리는 건물 위치에 따라 다름)."
        )

    needs_manual_review = pass_value is None
    if needs_manual_review:
        context_notes.append("※ 자동 판정 불가 — 정북 이격거리 등 입력 시 자동 판정 가능.")

    return {
        "category": "높이_일조",
        "actual_height_m": height,
        "floors_above": floors_above,
        "road_width_m": road_width,
        "shadow_applies": effective_shadow_applies,
        "shadow_applies_base": shadow_applies,
        "shadow_min_setback_m": shadow_min_setback_m,
        "north_setback_m": north_setback_m,
        "adjacent_zone_north": adjacent_zone_north,
        "road_20m_adjacent": road_20m_adjacent,
        "street_block_max_height_m": street_block_max_height_m,
        "parcel_north_depth_m": parcel_north_depth_m,
        "exemptions": exemptions,
        "needs_manual_review": needs_manual_review,
        "road_height_limit_m": street_block_max_height_m,
        "pass": pass_value,
        "score": score,
        "confidence": confidence,
        "source": (
            "건축법 §60·§61 + 시행령 §82·§86 (입력값 기반 자동 판정)"
            if not needs_manual_review
            else "건축법 §60·§61 + 시행령 §82·§86 (입력 부족 — 필수 수동검토)"
        ),
        "law_refs": _law_refs(),
        "notes": " ".join(judgement_notes + context_notes),
    }


def _shadow_applies(zone_use: str) -> bool:
    """정북 일조 사선 적용 여부 — 시행령 §86 ①항 전용·일반주거지역 한정."""
    from services.zone_use_normalizer import category_of
    cat = category_of(zone_use)
    return cat in ("전용주거", "일반주거")


def _compute_north_depth(geom: dict) -> float | None:
    """폴리곤의 정북(N-S) 방향 최대 깊이 (m).

    GeoJSON 좌표가 EPSG:4326(위경도)이라고 가정하고, 위도 차이를 m로 변환.
    실제 이격거리가 아니라 필지 자체의 N-S 길이 — 보조 정보 용도.
    """
    try:
        from shapely.geometry import shape
        poly = shape(geom)
        minx, miny, maxx, maxy = poly.bounds
        # 위도 1도 ≈ 111,000m (지구 반경 기반 근사)
        depth_m = (maxy - miny) * 111_000.0
        return round(depth_m, 1) if depth_m > 0 else None
    except Exception as e:
        logger.debug("정북 깊이 계산 실패: %s", e)
        return None


def _law_refs() -> list[dict]:
    return [
        {
            "name": "건축법 제60조 (건축물의 높이 제한)",
            "url": "https://www.law.go.kr/법령/건축법/제60조",
        },
        {
            "name": "건축법 제61조 (일조 등의 확보를 위한 높이 제한)",
            "url": "https://www.law.go.kr/법령/건축법/제61조",
        },
        {
            "name": "건축법 시행령 제82조 (건축물의 높이 제한)",
            "url": "https://www.law.go.kr/법령/건축법시행령/제82조",
        },
        {
            "name": "건축법 시행령 제86조 (일조 등의 확보를 위한 건축물의 높이 제한)",
            "url": "https://www.law.go.kr/법령/건축법시행령/제86조",
        },
    ]
