"""What-if 시뮬레이터 — 입력 변수 조정 시 즉시 재계산.

DiagnoseEngine.diagnose_fast() 위에 얹은 얇은 래퍼.
토지 조회 생략 + 설비_소방 AI 호출 생략(기본) → 슬라이더 드래그 응답 속도 확보.
"""
from __future__ import annotations

import logging

from services.diagnose_engine import DiagnoseEngine

logger = logging.getLogger(__name__)


class WhatIfSimulator:
    def __init__(self, engine: DiagnoseEngine) -> None:
        self._engine = engine

    async def simulate(
        self,
        req: dict,
        zone_use: str,
        land_info: dict | None = None,
        *,
        skip_ai: bool = True,
        cached_fire_safety: dict | None = None,
    ) -> dict:
        """수정된 입력으로 진단 재실행.

        Args:
          req: 전체 DiagnoseRequest dict (수정 반영 완료).
          zone_use: 기존 진단의 용도지역 (그대로 사용).
          land_info: 토지 정보 전체. 응답에 동일하게 포함.
          skip_ai: 기본 True — 설비_소방 AI 재호출 생략.
          cached_fire_safety: 기본 진단의 설비_소방 결과. skip_ai=True 시 재활용.
        """
        result = await self._engine.diagnose_fast(
            req,
            zone_use=zone_use,
            land_info=land_info,
            skip_ai=skip_ai,
            cached_fire_safety=cached_fire_safety,
        )
        result["mode"] = "what_if"
        return result
