"""arch-law-diagnose FastAPI 백엔드 — Phase 4"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from services.address_api_client import AddressApiClient
from services.cache_manager import CacheManager
from services.case_matcher import CaseMatcher
from services.diagnose_engine import DiagnoseEngine
from services.land_use_resolver import LandUseResolver
from services.law_change_tracker import LawChangeTracker
from services.law_go_kr_client import LawGoKrClient
from services.llm_client import LLMClient
from services.query_engine import QueryEngine
from services.review_notifier import ReviewNotifier
from services.vworld_client import VWorldClient
from services.what_if_simulator import WhatIfSimulator

logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

cache_manager: CacheManager | None = None
address_client: AddressApiClient | None = None
vworld_client: VWorldClient | None = None
land_resolver: LandUseResolver | None = None
llm_client: LLMClient | None = None
engine: DiagnoseEngine | None = None
simulator: WhatIfSimulator | None = None
query_engine: QueryEngine | None = None
law_client: LawGoKrClient | None = None
case_matcher: CaseMatcher | None = None
law_tracker: LawChangeTracker | None = None
review_notifier: ReviewNotifier | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global cache_manager, address_client, vworld_client, land_resolver, llm_client
    global engine, simulator, query_engine
    global law_client, case_matcher, law_tracker, review_notifier
    cache_manager = CacheManager()
    await cache_manager.init()
    address_client = AddressApiClient()
    vworld_client = VWorldClient()
    land_resolver = LandUseResolver(vworld_client, cache_manager)
    llm_client = LLMClient()
    engine = DiagnoseEngine(land_resolver, cache_manager, llm_client)
    simulator = WhatIfSimulator(engine)
    query_engine = QueryEngine(llm_client)

    # Phase 4
    law_client = LawGoKrClient()
    case_matcher = CaseMatcher()
    law_tracker = LawChangeTracker(cache_manager, law_client)
    review_notifier = ReviewNotifier()

    logger.info(
        "arch-law-diagnose backend ready (AI: %s · Slack: %s)",
        "활성" if llm_client.available else "비활성",
        "활성" if review_notifier.slack_configured else "비활성(로그만)",
    )
    yield
    await cache_manager.close()
    await address_client.close()
    await vworld_client.close()
    await llm_client.close()
    await law_client.close()
    await review_notifier.close()


app = FastAPI(
    title="arch-law-diagnose API",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 입력 스키마 ─────────────────────────────────────────────────────────────


class DiagnoseRequest(BaseModel):
    address: str = Field(..., description="도로명 또는 지번 주소")
    pnu: str | None = Field(None, description="필지번호 (선택)")
    building_use: str = Field(..., description="건축물 용도 (예: 근린생활시설, 공동주택)")
    site_area: float = Field(..., gt=0, description="대지면적 (㎡)")
    building_area: float = Field(..., gt=0, description="건축면적 (㎡)")
    total_floor_area: float = Field(..., gt=0, description="연면적 (㎡)")
    floors_above: int = Field(..., ge=1, description="지상 층수")
    floors_below: int = Field(0, ge=0, description="지하 층수")
    height: float = Field(..., gt=0, description="건물 높이 (m)")
    units: int | None = Field(None, description="세대수 (공동주택)")
    road_width: float | None = Field(None, description="전면도로 폭 (m), 미입력 시 추정")
    landscape_area: float | None = Field(
        None, ge=0, description="조경면적 (㎡, 선택). 미입력 시 의무비율만 표시"
    )


class WhatIfRequest(DiagnoseRequest):
    zone_use: str = Field(..., description="기본 진단에서 받은 용도지역. 재조회 안 함")
    land_info: dict[str, Any] | None = Field(None, description="기본 진단의 land_info 전체")
    skip_ai: bool = Field(True, description="True 시 설비_소방 AI 호출 생략 (속도↑)")
    cached_fire_safety: dict[str, Any] | None = Field(
        None, description="skip_ai=True 일 때 재활용할 기본 진단의 설비_소방 결과"
    )


class CompareScenario(BaseModel):
    name: str = Field(..., description="시나리오 이름 (예: '안 A')")
    building_use: str
    site_area: float = Field(..., gt=0)
    building_area: float = Field(..., gt=0)
    total_floor_area: float = Field(..., gt=0)
    floors_above: int = Field(..., ge=1)
    floors_below: int = 0
    height: float = Field(..., gt=0)
    units: int | None = None
    road_width: float | None = None
    landscape_area: float | None = None


class CompareRequest(BaseModel):
    address: str
    pnu: str | None = None
    scenarios: list[CompareScenario] = Field(..., min_length=2, max_length=4)
    skip_ai: bool = Field(True, description="True 시 시나리오별 설비_소방 AI 호출 생략")


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=2, description="자연어 질문")
    address: str | None = None
    zone_use: str | None = None
    building_info: dict[str, Any] | None = None
    current_result: dict[str, Any] | None = None


# ── Phase 4 스키마 ──────────────────────────────────────────────────────────


class CaseMatchRequest(BaseModel):
    building_use: str = Field(..., description="건축물 용도")
    zone_use: str = Field("", description="용도지역")
    site_area: float | None = Field(None, gt=0, description="대지면적 (㎡)")
    jurisdiction: str | None = Field(None, description="관할 구역(예: 영등포구)")
    limit: int = Field(5, ge=1, le=20)


class ReviewRequest(BaseModel):
    address: str = Field(..., description="대상 대지 주소")
    risk_category: str = Field(..., description="위험 카테고리 (예: 건폐율)")
    risk_reason: str = Field(..., description="위험 내용 / 진단 노트")
    requester: str | None = Field(None, description="요청자 이름/이메일 (선택)")
    building_info: dict[str, Any] | None = None
    signal: str | None = None
    overall_score: float | None = None
    note: str | None = Field(None, description="추가 메모 (선택)")


# ── 엔드포인트 ──────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.0.0"}


@app.get("/api/address/search")
async def address_search(q: str = Query(..., min_length=2, description="검색 키워드")):
    """행안부 도로명주소 API — 자동완성용"""
    if address_client is None:
        raise HTTPException(503, "서비스 초기화 중")
    results = await address_client.search(q)
    return {"results": results}


@app.post("/api/diagnose")
async def diagnose(req: DiagnoseRequest):
    """주소 + 건물 정보 → 법규 6개 카테고리 종합 진단"""
    if engine is None:
        raise HTTPException(503, "서비스 초기화 중")
    try:
        result = await engine.run(req.model_dump())
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("진단 오류: %s", e)
        raise HTTPException(500, f"진단 중 오류가 발생했습니다: {e}")


@app.post("/api/whatif")
async def what_if(req: WhatIfRequest):
    """What-if 시뮬레이션 — 변수 수정 즉시 재계산 (토지조회·AI 생략)."""
    if simulator is None:
        raise HTTPException(503, "서비스 초기화 중")
    try:
        payload = req.model_dump()
        zone_use = payload.pop("zone_use")
        land_info = payload.pop("land_info", None)
        skip_ai = payload.pop("skip_ai", True)
        cached_fire = payload.pop("cached_fire_safety", None)
        result = await simulator.simulate(
            payload,
            zone_use=zone_use,
            land_info=land_info,
            skip_ai=skip_ai,
            cached_fire_safety=cached_fire,
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("What-if 오류: %s", e)
        raise HTTPException(500, f"What-if 시뮬레이션 오류: {e}")


@app.post("/api/compare")
async def compare(req: CompareRequest):
    """시나리오 비교 — 2~4개 시나리오 동시 진단. 토지 조회는 1회만."""
    if engine is None or land_resolver is None:
        raise HTTPException(503, "서비스 초기화 중")
    try:
        land = await land_resolver.resolve(req.address, pnu=req.pnu or "")
        zone_use = land.get("zone_use", "")

        scenarios_out: list[dict] = []
        for sc in req.scenarios:
            sc_req = sc.model_dump()
            sc_req["address"] = req.address
            sc_req["pnu"] = req.pnu or ""
            result = await engine.diagnose_fast(
                sc_req,
                zone_use=zone_use,
                land_info=land,
                skip_ai=req.skip_ai,
            )
            scenarios_out.append(
                {
                    "name": sc.name,
                    "input": sc_req,
                    "result": result,
                }
            )

        return {
            "address": req.address,
            "land_info": land,
            "scenarios": scenarios_out,
            "summary": _compare_summary(scenarios_out),
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("Compare 오류: %s", e)
        raise HTTPException(500, f"시나리오 비교 오류: {e}")


@app.post("/api/query")
async def query(req: QueryRequest):
    """자연어 질의 — 진단 컨텍스트 기반 AI 답변 + 조문 인용."""
    if query_engine is None:
        raise HTTPException(503, "서비스 초기화 중")
    try:
        answer = await query_engine.answer(
            req.question,
            address=req.address,
            zone_use=req.zone_use,
            building_info=req.building_info,
            current_result=req.current_result,
        )
        return answer
    except Exception as e:
        logger.exception("Query 오류: %s", e)
        raise HTTPException(500, f"자연어 질의 오류: {e}")


# ── Phase 4 엔드포인트 ─────────────────────────────────────────────────────


@app.post("/api/cases/match")
async def cases_match(req: CaseMatchRequest):
    """사내 케이스 매칭 — 같은 용도+지역 유사 프로젝트 추천."""
    if case_matcher is None:
        raise HTTPException(503, "서비스 초기화 중")
    try:
        return case_matcher.match(
            building_use=req.building_use,
            zone_use=req.zone_use,
            site_area=req.site_area,
            jurisdiction=req.jurisdiction,
            limit=req.limit,
        )
    except Exception as e:
        logger.exception("케이스 매칭 오류: %s", e)
        raise HTTPException(500, f"케이스 매칭 오류: {e}")


@app.post("/api/cases/reload")
async def cases_reload():
    """KUNWON_DB 디스크 재스캔."""
    if case_matcher is None:
        raise HTTPException(503, "서비스 초기화 중")
    count = case_matcher.reload()
    return {"loaded": count}


@app.get("/api/law/changes")
async def law_changes(
    limit: int = Query(20, ge=1, le=100),
    jurisdiction_code: str | None = Query(None, description="특정 지자체 필터"),
):
    """최근 법규/조례 변경 이벤트 (해시 비교)."""
    if law_tracker is None:
        raise HTTPException(503, "서비스 초기화 중")
    try:
        changes = await law_tracker.recent_changes(
            limit=limit, jurisdiction_code=jurisdiction_code
        )
        return {"changes": changes, "count": len(changes)}
    except Exception as e:
        logger.exception("법규 변경 조회 오류: %s", e)
        raise HTTPException(500, f"법규 변경 조회 오류: {e}")


@app.post("/api/law/changes/scan")
async def law_changes_scan(
    jurisdiction_code: str = Query(...),
    region_name: str = Query(..., description="예: 서울특별시 영등포구"),
    law_keyword: str = Query("도시계획조례"),
):
    """능동 스캔 — 법제처 재조회 후 변경 감지."""
    if law_tracker is None:
        raise HTTPException(503, "서비스 초기화 중")
    try:
        return await law_tracker.scan(jurisdiction_code, region_name, law_keyword)
    except Exception as e:
        logger.exception("법규 스캔 오류: %s", e)
        raise HTTPException(500, f"법규 스캔 오류: {e}")


@app.post("/api/law/changes/seed_demo")
async def law_changes_seed_demo(
    jurisdiction_code: str = Query("11560"),
    law_type: str = Query("urban_planning"),
):
    """데모용 — 가짜 변경 이벤트 강제 삽입 (운영 환경에서는 비활성 권장)."""
    if law_tracker is None:
        raise HTTPException(503, "서비스 초기화 중")
    return await law_tracker.seed_demo_change(jurisdiction_code, law_type)


@app.post("/api/review/request")
async def review_request(req: ReviewRequest):
    """시니어 검토 요청 — Slack 발송 + 로컬 로그."""
    if review_notifier is None:
        raise HTTPException(503, "서비스 초기화 중")
    try:
        return await review_notifier.request_review(
            requester=req.requester,
            address=req.address,
            risk_category=req.risk_category,
            risk_reason=req.risk_reason,
            building_info=req.building_info,
            signal=req.signal,
            overall_score=req.overall_score,
            note=req.note,
        )
    except Exception as e:
        logger.exception("리뷰 요청 오류: %s", e)
        raise HTTPException(500, f"리뷰 요청 오류: {e}")


def _compare_summary(scenarios: list[dict]) -> dict:
    """시나리오 비교 요약 — 최고 점수, 신호별 카운트."""
    best_name: str | None = None
    best_score: float | None = None
    signal_count = {"GREEN": 0, "YELLOW": 0, "RED": 0}
    for s in scenarios:
        r = s.get("result", {})
        sig = r.get("signal")
        if sig in signal_count:
            signal_count[sig] += 1
        score = r.get("overall_score")
        if score is None:
            continue
        if best_score is None or score > best_score:
            best_score = score
            best_name = s.get("name")
    return {
        "best": best_name,
        "best_score": best_score,
        "signal_count": signal_count,
    }
