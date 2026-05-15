"""arch-law-diagnose FastAPI 백엔드 — Phase 5"""
from __future__ import annotations

import asyncio
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
from services.eum_client import EumClient
from services.land_use_resolver import LandUseResolver
from services.law_change_tracker import LawChangeTracker
from services.law_go_kr_client import LawGoKrClient
from services.llm_client import LLMClient
from services.luris_client import LurisClient
from services.multi_parcel import aggregate_zones, apply_weighted_limits
from services.ordinance_extractor import OrdinanceExtractor
from services.ordinance_resolver import OrdinanceResolver
from services.ordinance_seed_loader import load_seed_into_db
from services.query_engine import QueryEngine
from services.review_notifier import ReviewNotifier
from services.vworld_client import VWorldClient

logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

cache_manager: CacheManager | None = None
address_client: AddressApiClient | None = None
vworld_client: VWorldClient | None = None
land_resolver: LandUseResolver | None = None
llm_client: LLMClient | None = None
ordinance_extractor: OrdinanceExtractor | None = None
ordinance_resolver: OrdinanceResolver | None = None
engine: DiagnoseEngine | None = None
query_engine: QueryEngine | None = None
law_client: LawGoKrClient | None = None
luris_client: LurisClient | None = None
eum_client: EumClient | None = None
case_matcher: CaseMatcher | None = None
law_tracker: LawChangeTracker | None = None
review_notifier: ReviewNotifier | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global cache_manager, address_client, vworld_client, land_resolver, llm_client
    global ordinance_extractor, ordinance_resolver
    global engine, query_engine
    global law_client, luris_client, eum_client, case_matcher, law_tracker, review_notifier
    cache_manager = CacheManager()
    await cache_manager.init()
    seed_stats = await load_seed_into_db(cache_manager)
    address_client = AddressApiClient()
    vworld_client = VWorldClient()
    land_resolver = LandUseResolver(vworld_client, cache_manager)
    llm_client = LLMClient()

    # Phase 5 — 조례 리졸버
    law_client = LawGoKrClient()
    ordinance_extractor = OrdinanceExtractor(llm_client)
    ordinance_resolver = OrdinanceResolver(cache_manager, law_client, ordinance_extractor)

    # LURIS — 행위제한정보 (토지이용규제정보서비스), SQLite 캐시 주입 (1000회/일 한도 절약)
    luris_client = LurisClient(cache=cache_manager)

    # 토지이음 표준연계 (Phase 0 — EumClient. 5개 메인 + 2개 헬퍼 API)
    eum_client = EumClient()

    engine = DiagnoseEngine(land_resolver, cache_manager, llm_client, ordinance_resolver, luris_client)
    query_engine = QueryEngine(llm_client)

    # Phase 4
    case_matcher = CaseMatcher()
    law_tracker = LawChangeTracker(cache_manager, law_client)
    review_notifier = ReviewNotifier()

    _status = {
        "VWorld":   "✅" if vworld_client._key  else "❌ VWORLD_API_KEY 미설정",
        "LURIS":    "✅" if luris_client._key   else "❌ LURIS_API_KEY / DATA_GO_KR_API_KEY 미설정",
        "주소검색":  "✅" if address_client._key else "❌ KAKAO_API_KEY 미설정",
        "AI(Claude)": "✅" if llm_client.available else "❌ ANTHROPIC_API_KEY 미설정",
        "토지이음":  "✅" if eum_client.available else "❌ EUM_ID / EUM_KEY 미설정",
        "Slack":    "✅" if review_notifier.slack_configured else "⚠ 미설정(로그만)",
    }
    for svc, st in _status.items():
        logger.info("  %-12s %s", svc, st)
    if any("❌" in st for st in _status.values()):
        logger.warning(
            "일부 외부 API가 비활성 상태입니다. "
            "해당 진단 항목은 '확인필요(YELLOW)'로 처리됩니다."
        )
    logger.info(
        "조례 seed: %d건 신규 삽입, %d건 기존값 보존 (%s)",
        seed_stats["inserted"], seed_stats["skipped"],
        ", ".join(seed_stats["jurisdictions"]) or "없음",
    )
    logger.info("arch-law-diagnose backend ready")
    yield
    await cache_manager.close()
    await address_client.close()
    await vworld_client.close()
    await llm_client.close()
    await law_client.close()
    await luris_client.close()
    await eum_client.close()
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
    building_use: str = Field(..., description="건축물 주 용도 (분류, 예: 공공업무시설)")
    building_use_detail: str | None = Field(
        None, description="세부/복합 용도 자유 입력 (예: '공공업무시설(구청, 어린이집, 부설주차장)')"
    )
    zone_district: str | None = Field(
        None,
        description="지역지구 (예: '지구단위계획구역, 일반미관지구'). 미입력 시 VWorld 조회값 사용",
    )
    site_area: float = Field(..., gt=0, description="대지면적 (㎡)")
    building_area: float = Field(..., gt=0, description="건축면적 (㎡)")
    floor_area_above: float = Field(..., gt=0, description="지상 연면적 (㎡) — 주차장 포함 전체")
    floor_area_below: float | None = Field(
        None, ge=0, description="지하 연면적 (㎡, 선택). 용적률 산정에서 제외"
    )
    floor_area_parking_above: float | None = Field(
        None, ge=0,
        description="지상 주차장 면적 (㎡, 선택). 부속용도 — 용적률 산정에서 제외 (건축법 시행령 제119조)",
    )
    floor_area_refuge: float | None = Field(
        None, ge=0,
        description="피난안전구역 면적 (㎡, 선택). 초고층/준초고층 한정 — 용적률 산정에서 제외 (건축법 시행령 제119조)",
    )
    floor_area_attic_refuge: float | None = Field(
        None, ge=0,
        description="경사지붕 아래 대피공간 면적 (㎡, 선택). 11층 이상 한정 — 용적률 산정에서 제외 (건축법 시행령 제119조)",
    )
    floors_above: int = Field(..., ge=1, description="지상 층수")
    floors_below: int = Field(0, ge=0, description="지하 층수")
    height: float = Field(..., gt=0, description="건물 높이 (m)")
    units: int | None = Field(None, description="세대수 (공동주택)")
    road_width: float | None = Field(None, description="전면도로 폭 (m), 미입력 시 추정")
    landscape_area: float | None = Field(
        None, ge=0, description="조경면적 (㎡, 선택). 미입력 시 의무비율만 표시"
    )
    provided_parking_spaces: int | None = Field(
        None, ge=0, description="계획 주차대수 (선택). 미입력 시 법정 기준만 표시"
    )
    public_open_space_area: float | None = Field(
        None, ge=0, description="공개공지 면적 (㎡, 선택)"
    )
    zone_use_override: str | None = Field(
        None, description="용도지역 직접 지정 (미입력 시 VWorld 자동 조회)"
    )

    # 용적률 완화 입력 (모두 선택)
    green_grade: str | None = Field(None, description="녹색건축 인증 등급 (최우수/우수/우량/일반)")
    energy_grade: str | None = Field(None, description="에너지효율 등급 (1++/1+/1/2)")
    smart_grade: str | None = Field(None, description="지능형건축물 인증 등급 (최우수/우수/우량/일반)")
    long_life_grade: str | None = Field(None, description="장수명주택 인증 등급 (최우수/우수/우량/일반, 공동주택 한정)")
    far_limit_manual_override: float | None = Field(
        None, gt=0,
        description="용적률 한도 직접 지정 (도시계획심의/지구단위/정비사업 등). 입력 시 기본 한도 대신 사용",
    )
    relief_reason_manual: str | None = Field(
        None, description="용적률 한도 변경 사유 (자유 입력)"
    )

    # B7: 도시계획시설 저촉 면적 — 비워두면 자동 (VWorld 지적도 ∩ 시설 SHP)
    urban_facility_exclude_area: float | None = Field(
        None, ge=0,
        description="대지면적에서 제외할 시설부지 면적 (선택). 자동 추정 결과를 무시하고 수동 지정.",
    )

    # 높이·일조 보강 입력 (선택, 입력 시 자동 pass/fail)
    north_setback_m: float | None = Field(
        None, ge=0,
        description="정북 인접대지경계선까지 실제 이격거리 (m). 입력 시 §86 ①항 자동 판정.",
    )
    adjacent_zone_north: str | None = Field(
        None, description="정북 방향 인접대지 용도지역 (비주거이면 §86 ②항 3호 적용 제외)",
    )
    road_20m_adjacent: bool | None = Field(
        None, description="너비 20m 이상 도로 접함 여부 (True 시 §86 ②항 1호 적용 제외)",
    )
    street_block_max_height_m: float | None = Field(
        None, gt=0,
        description="가로구역별 최고높이 지정값 (m). 입력 시 §60 자동 비교.",
    )


class ParcelInput(BaseModel):
    address: str = Field(..., description="필지 주소")
    pnu: str | None = Field(None, description="필지번호 (선택)")
    site_area: float = Field(..., gt=0, description="해당 필지 면적 (㎡)")
    zone_use_override: str | None = Field(None, description="용도지역 직접 지정")


class MultiDiagnoseRequest(BaseModel):
    parcels: list[ParcelInput] = Field(..., min_length=2, max_length=20, description="합산 대상 필지 목록")
    building_use: str = Field(..., description="건축물 주 용도")
    building_use_detail: str | None = Field(None, description="세부/복합 용도 자유 입력")
    zone_district: str | None = Field(None, description="지역지구 (미입력 시 VWorld)")
    building_area: float = Field(..., gt=0, description="건축면적 (㎡)")
    floor_area_above: float = Field(..., gt=0, description="지상 연면적 (㎡) — 주차장 포함 전체")
    floor_area_below: float | None = Field(None, ge=0, description="지하 연면적 (㎡, 선택)")
    floor_area_parking_above: float | None = Field(
        None, ge=0, description="지상 주차장 면적 (㎡, 선택) — 용적률 산정 제외"
    )
    floor_area_refuge: float | None = Field(
        None, ge=0, description="피난안전구역 면적 (㎡, 선택, 초고층 한정) — 용적률 산정 제외"
    )
    floor_area_attic_refuge: float | None = Field(
        None, ge=0, description="경사지붕 대피공간 면적 (㎡, 선택, 11층 이상) — 용적률 산정 제외"
    )
    floors_above: int = Field(..., ge=1, description="지상 층수")
    floors_below: int = Field(0, ge=0, description="지하 층수")
    height: float = Field(..., gt=0, description="건물 높이 (m)")
    units: int | None = Field(None, description="세대수 (공동주택)")
    road_width: float | None = Field(None, description="전면도로 폭 (m)")
    landscape_area: float | None = Field(None, ge=0, description="조경면적 (㎡)")
    provided_parking_spaces: int | None = Field(None, ge=0, description="계획 주차대수 (선택)")
    public_open_space_area: float | None = Field(None, ge=0, description="공개공지 면적 (㎡, 선택)")

    # 용적률 완화 입력
    green_grade: str | None = None
    energy_grade: str | None = None
    smart_grade: str | None = None
    long_life_grade: str | None = None
    far_limit_manual_override: float | None = Field(None, gt=0)
    relief_reason_manual: str | None = None

    # B7: 도시계획시설 저촉 면적 (선택)
    urban_facility_exclude_area: float | None = Field(None, ge=0)

    # 높이·일조 보강 입력 (선택)
    north_setback_m: float | None = Field(None, ge=0)
    adjacent_zone_north: str | None = None
    road_20m_adjacent: bool | None = None
    street_block_max_height_m: float | None = Field(None, gt=0)


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


@app.get("/api/eum/health")
async def eum_health():
    """토지이음 API 연결·인증 검증 — 시군구 코드 조회 (가장 가벼운 호출).

    Returns:
      {"available": bool, "area_count": int, "sample": [first 3 items]}
    """
    if eum_client is None or not eum_client.available:
        return {"available": False, "area_count": 0, "sample": [], "reason": "EUM_ID / EUM_KEY 미설정"}
    areas = await eum_client.search_area_codes()
    return {
        "available": True,
        "area_count": len(areas),
        "sample": areas[:3],
    }


@app.get("/api/eum/law_info")
async def eum_law_info(
    area_cd: str = Query(..., min_length=5, max_length=5, description="시군구코드 5자리"),
    zone_use: str = Query("", description="용도지역명 (예: 제2종일반주거지역)"),
    zone_district: str = Query("", description="지역지구명 (콤마 구분 가능)"),
):
    """토지이용규제 법령정보 — Phase 1.

    1. zone_use + zone_district → 토지이음 UCODE 변환 (searchZone)
    2. iuLawInfo 호출 → 법령 본문 받기
    3. UCODE별로 그룹화해서 반환

    Returns:
      {
        ucode_count, total_items,
        groups: [{ucode, uname, law_cd, law_nm, items: [{law_contents, law_level, ...}]}]
      }
    """
    if eum_client is None or not eum_client.available:
        raise HTTPException(503, "토지이음 API 비활성 (EUM_ID/EUM_KEY 확인)")

    names: list[str] = []
    if zone_use.strip():
        names.append(zone_use.strip())
    if zone_district.strip():
        for d in zone_district.split(","):
            ds = d.strip()
            if ds:
                names.append(ds)
    if not names:
        return {"ucode_count": 0, "total_items": 0, "groups": [], "warning": "zone_use 또는 zone_district 필요"}

    ucode_info = await eum_client.resolve_zone_ucodes(area_cd, names)
    if not ucode_info:
        return {
            "ucode_count": 0,
            "total_items": 0,
            "groups": [],
            "warning": "토지이음 표준명 매칭 실패 — 입력값과 일치하는 UCODE 없음",
        }

    ucode_list = [u["ucode"] for u in ucode_info if u["ucode"]]
    laws = await eum_client.get_law_info(area_cd, ucode_list)

    # UCODE별 그룹화 + level 순 정렬
    groups: dict[str, dict] = {
        u["ucode"]: {
            "ucode": u["ucode"],
            "uname": u["uname"],
            "law_cd": u["law_cd"],
            "law_nm": u["law_nm"],
            "items": [],
        }
        for u in ucode_info
    }
    for law in laws:
        if law["ucode"] in groups:
            groups[law["ucode"]]["items"].append({
                "law_contents": law["law_contents"],
                "law_level": law["law_level"],  # 0=조, 1=항, 2=호, 3=목
                "law_full_cd": law["law_full_cd"],
            })

    return {
        "ucode_count": len(ucode_info),
        "total_items": len(laws),
        "groups": list(groups.values()),
    }


@app.get("/api/luris/stats")
async def luris_stats():
    """LURIS API 호출 통계 — 1000회/일 한도 모니터링.

    이번 프로세스 기간(서버 시작 이후) 캐시 적중률.
    """
    if luris_client is None:
        return {"hits": 0, "misses": 0, "hit_rate": None, "cache_enabled": False}
    total = luris_client.cache_hits + luris_client.cache_misses
    rate = round(luris_client.cache_hits / total, 3) if total else None
    return {
        "hits": luris_client.cache_hits,
        "misses": luris_client.cache_misses,
        "hit_rate": rate,
        "cache_enabled": luris_client._cache is not None,
    }


@app.get("/api/address/search")
async def address_search(q: str = Query(..., min_length=2, description="검색 키워드")):
    """행안부 도로명주소 API — 자동완성용"""
    if address_client is None:
        raise HTTPException(503, "서비스 초기화 중")
    results = await address_client.search(q)
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"results": results},
        headers={"Cache-Control": "no-store"},  # 빈 응답 캐싱 방지
    )


@app.get("/api/land_info")
async def land_info(
    pnu: str | None = Query(None, description="필지번호 19자리 (우선 사용)"),
    address: str | None = Query(None, description="주소 (PNU 없을 때 fallback)"),
):
    """주소/PNU 로 토지이용계획 즉시 조회 — 용도지역·지역지구·지목·공시지가 자동 채움."""
    if land_resolver is None:
        raise HTTPException(503, "서비스 초기화 중")
    if not pnu and not address:
        raise HTTPException(400, "pnu 또는 address 중 하나는 필수")
    try:
        info = await land_resolver.resolve(address or "", pnu=pnu or "")
        return info
    except Exception as e:
        logger.exception("land_info 조회 오류: %s", e)
        raise HTTPException(500, f"토지정보 조회 오류: {e}")


def _attach_total_floor_area(d: dict) -> dict:
    """floor_area_above + floor_area_below → total_floor_area 자동 계산.

    용적률(far)은 지상만 사용, 그 외 계산기(parking·fire_safety 등)는 지상+지하 합계 사용.
    엔진/계산기 호환을 위해 dict 에 둘 다 포함.
    """
    above = float(d.get("floor_area_above") or 0)
    below = float(d.get("floor_area_below") or 0)
    d["total_floor_area"] = above + below
    return d


@app.post("/api/diagnose")
async def diagnose(req: DiagnoseRequest):
    """주소 + 건물 정보 → 법규 6개 카테고리 종합 진단"""
    if engine is None:
        raise HTTPException(503, "서비스 초기화 중")
    try:
        result = await engine.run(_attach_total_floor_area(req.model_dump()))
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("진단 오류: %s", e)
        raise HTTPException(500, f"진단 중 오류가 발생했습니다: {e}")


@app.post("/api/diagnose/multi")
async def diagnose_multi(req: MultiDiagnoseRequest):
    """합필 진단 — 여러 필지를 합쳐 단일 사업지로 진단.

    Phase 2: 동일 용도지역 / 소규모 예외(≤330㎡) / 면적 안분 가중평균 지원.
    """
    if engine is None or land_resolver is None:
        raise HTTPException(503, "서비스 초기화 중")
    try:
        # 1. 각 필지 용도지역 병렬 조회 + zone_use_override 반영
        lands = await asyncio.gather(*[
            land_resolver.resolve(p.address, pnu=p.pnu or "")
            for p in req.parcels
        ])
        for p, land in zip(req.parcels, lands):
            if p.zone_use_override:
                land["zone_use"] = p.zone_use_override

        # 2. 용도지역 정보 부족한 필지 검사
        missing = [
            p.address for p, l in zip(req.parcels, lands)
            if not (l.get("zone_use") or "").strip()
        ]
        if missing:
            raise HTTPException(
                400,
                {
                    "error": "ZONE_LOOKUP_FAILED",
                    "message": (
                        f"{len(missing)}개 필지의 용도지역 조회 실패. "
                        "주소를 다시 선택하거나 용도지역을 직접 지정해주세요."
                    ),
                    "failed_addresses": missing,
                },
            )

        # 3. 합산 규칙 결정 (same_zone / small_part / weighted)
        parcels_dump = [
            {**p.model_dump(), "site_area": p.site_area}
            for p in req.parcels
        ]
        agg = aggregate_zones(parcels_dump, lands)

        # 4. 진단 엔진 호출 — primary_zone 기준 단일 진단
        first = req.parcels[0]
        above = float(req.floor_area_above)
        below = float(req.floor_area_below or 0)
        parking_above = float(req.floor_area_parking_above or 0)
        refuge = float(req.floor_area_refuge or 0)
        attic_refuge = float(req.floor_area_attic_refuge or 0)
        agg_req = {
            "address": first.address,
            "pnu": first.pnu or "",
            "building_use": req.building_use,
            "building_use_detail": req.building_use_detail,
            "zone_district": req.zone_district,
            "site_area": agg["total_site_area"],
            "building_area": req.building_area,
            "floor_area_above": above,
            "floor_area_below": below,
            "floor_area_parking_above": parking_above,
            "floor_area_refuge": refuge,
            "floor_area_attic_refuge": attic_refuge,
            "total_floor_area": above + below,
            "floors_above": req.floors_above,
            "floors_below": req.floors_below,
            "height": req.height,
            "units": req.units,
            "road_width": req.road_width,
            "provided_parking_spaces": req.provided_parking_spaces,
            "public_open_space_area": req.public_open_space_area,
            "landscape_area": req.landscape_area,
            "green_grade": req.green_grade,
            "energy_grade": req.energy_grade,
            "smart_grade": req.smart_grade,
            "long_life_grade": req.long_life_grade,
            "far_limit_manual_override": req.far_limit_manual_override,
            "relief_reason_manual": req.relief_reason_manual,
            "urban_facility_exclude_area": req.urban_facility_exclude_area,
            "north_setback_m": req.north_setback_m,
            "adjacent_zone_north": req.adjacent_zone_north,
            "road_20m_adjacent": req.road_20m_adjacent,
            "street_block_max_height_m": req.street_block_max_height_m,
        }
        base_land = dict(lands[0])
        base_land["zone_use"] = agg["primary_zone"]

        # B7: 합필 폴리곤 union → 진단 엔진의 자동 보정 경로 재사용
        # 모든 필지의 지적 폴리곤을 합쳐 base_land["parcel_geometry"]에 주입.
        # 사용자가 직접 urban_facility_exclude_area 를 넣은 경우 진단 엔진이
        # manual 분기를 우선 적용하므로 union 은 무시됨.
        try:
            from shapely.geometry import mapping, shape
            from shapely.ops import unary_union

            polys = [
                shape(l["parcel_geometry"])
                for l in lands
                if l.get("parcel_geometry")
            ]
            if polys:
                union_geom = unary_union(polys)
                base_land["parcel_geometry"] = mapping(union_geom)
        except Exception as e:
            logger.warning("합필 폴리곤 union 실패 — 보정 생략: %s", e)

        diag = await engine.diagnose_fast(
            agg_req,
            zone_use=agg["primary_zone"],
            land_info=base_land,
            skip_ai=False,
        )

        # 5. 합산 한도 적용 (small_part / weighted 인 경우 한도/점수 재계산)
        diag = apply_weighted_limits(diag, agg)

        # 6. 응답 구성
        return {
            "mode": "multi_parcel",
            "phase": 2,
            "parcels": [
                {
                    "address": p.address,
                    "pnu": p.pnu or "",
                    "site_area": p.site_area,
                    "zone_use": l.get("zone_use", ""),
                    "jurisdiction_name": l.get("jurisdiction_name", ""),
                    "zone_district": l.get("zone_district", ""),
                }
                for p, l in zip(req.parcels, lands)
            ],
            "aggregate": {
                "total_site_area": agg["total_site_area"],
                "calc_mode": agg["mode"],           # same_zone | small_part | weighted
                "primary_zone": agg["primary_zone"],
                "small_part_zone": agg["small_part_zone"],
                "weighted_coverage_limit": agg["weighted_coverage_limit"],
                "weighted_far_limit": agg["weighted_far_limit"],
                "zone_breakdown": agg["zone_breakdown"],
                "calc_method": agg["calc_method"],
                "threshold_m2": agg.get("threshold_m2"),
                "threshold_basis": agg.get("threshold_basis"),
                "cross_jurisdiction": agg["cross_jurisdiction"],
                "jurisdictions": agg["jurisdictions"],
                "parcel_count": len(req.parcels),
            },
            "result": diag,
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("멀티 진단 오류: %s", e)
        raise HTTPException(500, f"멀티 진단 중 오류: {e}")


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


