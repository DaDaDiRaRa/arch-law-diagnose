"""자매 앱 arch-law-graph 의 조문 원문 조회 클라이언트 (서버 간 호출).

진단 적용 조문의 **본문 텍스트**를 graph 에서 받아 query_engine 이 LLM 컨텍스트에
주입 → 조문 내용 환각을 막는 데 사용(A안 RAG 그라운딩).

graph 미가동·미배포·미보유 시 모두 graceful degrade — 빈 결과를 돌려
query_engine 은 원문 없이(0단계 상태로) 동작한다. 진단 자체엔 영향 없음.
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

# 백엔드 간 호출용 graph API 주소 (프론트 VITE_GRAPH_URL 과 별개).
# 자동배포 CI 가 런타임 env 를 안 넣으므로 기본값을 프로덕션 graph 로 둔다.
# 로컬 graph(8001)로 테스트하려면 GRAPH_API_URL 환경변수로 override.
# 미가동/오류 시 어차피 degrade 라 무해.
_GRAPH_API_URL = os.getenv(
    "GRAPH_API_URL",
    "https://arch-law-graph-30350777436.asia-northeast3.run.app",
).rstrip("/")
# graph 가 Cloud Run 콜드스타트(22MB graph.json + RAG 로딩) 시 느릴 수 있어 여유 둠.
_TIMEOUT = float(os.getenv("GRAPH_API_TIMEOUT", "8"))


async def fetch_law_bodies(names: list[str]) -> dict[str, dict]:
    """적용 조문명 목록 → {조문명: {id, law_nm, title, content, source_url}}.

    graph 가 보유한 조문만 포함. 미가동/오류/미보유는 조용히 제외(degrade).
    """
    names = [n for n in dict.fromkeys(n for n in names if n)]  # 중복 제거·빈값 제거
    if not names:
        return {}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_GRAPH_API_URL}/api/lookup", json={"queries": names}
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:  # 연결 실패·타임아웃·HTTP 오류 모두 degrade
        logger.info("graph 조문 원문 조회 실패 — 원문 그라운딩 생략(degrade): %s", e)
        return {}

    out: dict[str, dict] = {}
    for item in data.get("results", []) or []:
        if item.get("found") and item.get("content"):
            out[item.get("query", "")] = {
                "id": item.get("id"),
                "law_nm": item.get("law_nm"),
                "title": item.get("title"),
                "content": item.get("content"),
                "source_url": item.get("source_url"),
            }
    if out:
        logger.info("graph 조문 원문 %d건 확보 (요청 %d건)", len(out), len(names))
    return out
