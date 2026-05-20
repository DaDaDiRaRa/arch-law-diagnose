"""철도보호지구 저촉 진단 — 정보 카드 (가중치 0).

철도안전법 §45: 철도경계선으로부터 30m 이내를 철도보호지구로 지정.
해당 구역 내 건축 시 국토교통부장관(또는 철도관리자) 사전 허가 필요.

SHP 미배치 시: checked=False → 안내 메시지만 표시.
"""
from __future__ import annotations

from services.railway import check_railway_proximity


def calculate(
    *,
    lat: float | None,
    lng: float | None,
) -> dict:
    """철도보호지구 진단 카드.

    Returns:
      카드 dict. within_zone=True → pass=None(YELLOW), False → pass=True.
      SHP 미배치 → pass=None, checked=False.
    """
    if lat is None or lng is None:
        return _card(
            passed=None,
            score=None,
            confidence=1,
            notes="좌표 정보 없음 — 철도보호지구 검사 미수행",
            items=[],
            checked=False,
        )

    result = check_railway_proximity(lat=lat, lng=lng)

    if not result["checked"]:
        return _card(
            passed=None,
            score=None,
            confidence=1,
            notes=result["note"],
            items=[],
            checked=False,
        )

    if not result["within_zone"]:
        return _card(
            passed=True,
            score=10,
            confidence=4,
            notes="철도보호지구(경계 30m) 해당 없음.",
            items=[],
            checked=True,
        )

    items = [
        {
            "name": h["name"],
            "distance_m": h["distance_m"],
            "note": f"철도경계로부터 {h['distance_m']}m — 30m 이내 (철도보호지구)",
        }
        for h in result["nearby"]
    ]
    note = (
        f"⚠ 철도보호지구 해당 — {len(items)}개 철도 경계 30m 이내. "
        "건축 시 철도관리자(국토교통부/철도공사) 허가 필요 (철도안전법 §45)."
    )
    return _card(
        passed=None,
        score=5,
        confidence=4,
        notes=note,
        items=items,
        checked=True,
    )


def _card(
    *,
    passed: bool | None,
    score: float | None,
    confidence: int,
    notes: str,
    items: list,
    checked: bool,
) -> dict:
    return {
        "category": "철도보호지구",
        "pass": passed,
        "score": score,
        "confidence": confidence,
        "source": "전국 철도망 SHP (RAILWAY_SHP_PATH)",
        "law_refs": [
            {
                "name": "철도안전법 제45조 (철도보호지구의 지정)",
                "url": "https://www.law.go.kr/법령/철도안전법/제45조",
            },
            {
                "name": "철도안전법 제46조 (철도보호지구에서의 행위 제한)",
                "url": "https://www.law.go.kr/법령/철도안전법/제46조",
            },
        ],
        "notes": notes,
        "items": items,
        "checked": checked,
    }
