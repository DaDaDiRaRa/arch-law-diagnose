"""arch-law-diagnose FastAPI 백엔드 — Phase 5"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from schemas import (
    DiagnoseRequest,
    FeasibilityRequest,
    LawGraphCurateRequest,
    MultiDiagnoseRequest,
    MultiFeasibilityRequest,
    ParcelInput,
    QueryRequest,
    ReviewRequest,
    WhatIfRequest,
)
from services.address_api_client import AddressApiClient
from services.cache_manager import CacheManager
from services.diagnose_engine import DiagnoseEngine
from services.heritage_client import HeritageClient
from services.school_client import SchoolClient
from services.diagnose_exporter import to_markdown as diagnose_to_markdown
from services.diagnose_exporter import to_xlsx as diagnose_to_xlsx
from services.feasibility_engine import run_feasibility
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
from services.street_block_heights_loader import (
    load_seed_into_db as load_street_block_heights,
)
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
law_tracker: LawChangeTracker | None = None
review_notifier: ReviewNotifier | None = None
law_change_scheduler = None  # APScheduler 인스턴스 (lifespan 안에서 시작)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global cache_manager, address_client, vworld_client, land_resolver, llm_client
    global ordinance_extractor, ordinance_resolver
    global engine, query_engine
    global law_client, luris_client, eum_client, law_tracker, review_notifier
    cache_manager = CacheManager()
    await cache_manager.init()
    seed_stats = await load_seed_into_db(cache_manager)
    sbh_stats = await load_street_block_heights(cache_manager)
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
    # cache 주입 → 행위제한 교차검증 캐시(eum_act_restriction_cache) 활용
    eum_client = EumClient(cache=cache_manager)

    school_client = SchoolClient()
    heritage_client = HeritageClient()

    engine = DiagnoseEngine(
        land_resolver, cache_manager, llm_client,
        ordinance_resolver, luris_client, eum=eum_client,
        school_client=school_client,
        heritage_client=heritage_client,
    )
    query_engine = QueryEngine(llm_client)

    # Phase 4
    law_tracker = LawChangeTracker(cache_manager, law_client)
    review_notifier = ReviewNotifier()

    _status = {
        "VWorld":         "✅" if vworld_client._key  else "❌ VWORLD_API_KEY 미설정",
        "LURIS":          "✅" if luris_client._key   else "❌ LURIS_API_KEY / DATA_GO_KR_API_KEY 미설정",
        "주소검색(Kakao)": "✅" if address_client._key else "❌ KAKAO_API_KEY 미설정",
        "AI(Claude)":     "✅" if llm_client.available else "❌ ANTHROPIC_API_KEY 미설정",
        "토지이음(EUM)":   "✅" if eum_client.available else "❌ EUM_ID / EUM_KEY 미설정",
        "법제처(DRF)":    "✅" if law_client._key      else "❌ LAW_API_KEY 미설정 (조례 본문·변경 감지 불가)",
        "Slack":          "✅" if review_notifier.slack_configured else "⚠ 미설정(선택)",
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
    logger.info(
        "가로구역 최고높이 seed: %d건 적재 (총 %d건 중)",
        sbh_stats.get("loaded", 0), sbh_stats.get("total", 0),
    )
    # 법규 변경 cron — 매주 일요일 03:00 KST 기본 (ENABLE_LAW_CHANGE_CRON=false 로 끔)
    from services.law_change_scheduler import start_scheduler as _start_law_cron
    global law_change_scheduler
    law_change_scheduler = _start_law_cron(law_tracker)

    logger.info("arch-law-diagnose backend ready")
    yield
    if law_change_scheduler is not None:
        law_change_scheduler.shutdown(wait=False)
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

# 교차출처 허용 오리진 — env ALLOWED_ORIGINS(콤마구분)로 지정, 미설정 시 로컬 개발용만.
# 단일 컨테이너 배포는 프론트가 동일 오리진이라 CORS 불필요 → 화이트리스트가 안전.
_default_origins = "http://localhost:5173,http://localhost:8000,http://localhost:8080"
_allowed_origins = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 엔드포인트 ──────────────────────────────────────────────────────────────
# 입력 스키마(DiagnoseRequest 등)는 schemas.py 참조.


@app.get("/health")
async def health():
    return {"status": "ok", "version": app.version}


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


@app.get("/api/eum/notices")
async def eum_notices(
    area_cd: str = Query(..., min_length=5, max_length=5, description="시군구코드 5자리"),
    days: int = Query(90, ge=1, le=365, description="조회 기간 (일)"),
    page_no: int = Query(1, ge=1, description="페이지 번호 (30건/페이지)"),
):
    """토지이음 행정 고시 — Phase 2.

    시군구의 최근 N일간 고시 목록 (도시계획결정·지정·변경고시 등).
    `LawChangeAlert` 에서 진단 지역의 최근 행정 변화를 자동 노출.

    Returns:
      {area_cd, period: {start, end, days}, total_size, total_page,
       list_size, page_no, items: [{title, author, ntc_date, link, summary}]}
    """
    if eum_client is None or not eum_client.available:
        return {
            "area_cd": area_cd,
            "period": {"start": "", "end": "", "days": days},
            "total_size": 0, "total_page": 0, "list_size": 0,
            "page_no": page_no, "items": [],
            "warning": "토지이음 API 비활성 (EUM_ID/EUM_KEY 확인)",
        }
    end_dt = datetime.now().strftime("%Y%m%d")
    start_dt = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    try:
        result = await eum_client.get_notices(area_cd, start_dt, end_dt, page_no)
    except Exception as e:
        logger.exception("EUM 고시 조회 오류: %s", e)
        raise HTTPException(500, "EUM 고시 조회 실패")
    return {
        "area_cd": area_cd,
        "period": {"start": start_dt, "end": end_dt, "days": days},
        **result,
    }


@app.get("/api/eum/dev_permits")
async def eum_dev_permits(
    area_cd: str = Query(..., min_length=5, max_length=5, description="시군구코드 5자리"),
    days: int = Query(14, ge=1, le=30, description="조회 기간 (일, 최대 30)"),
):
    """토지이음 개발 인허가 목록 — Phase 3.

    EUM API는 단일 날짜만 받으므로 최근 N일을 병렬 집계.
    주변 개발 동향(인접 필지에서 어떤 개발이 진행 중인지)을 한눈에.

    Returns:
      {area_cd, period: {start, end, days}, total, items: [{...permit fields..., _permit_date}]}
    """
    if eum_client is None or not eum_client.available:
        return {
            "area_cd": area_cd,
            "period": {"start": "", "end": "", "days": days},
            "total": 0, "items": [],
            "warning": "토지이음 API 비활성 (EUM_ID/EUM_KEY 확인)",
        }
    today = datetime.now()
    dates = [(today - timedelta(days=i)).strftime("%Y%m%d") for i in range(days)]
    tasks = [eum_client.get_dev_permits(area_cd, d, 1) for d in dates]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_items: list[dict] = []
    errors = 0
    for d, r in zip(dates, results):
        if isinstance(r, Exception):
            errors += 1
            continue
        for item in (r.get("list", []) or []):
            all_items.append({**item, "_permit_date": d})

    # 날짜 내림차순 — 본 API의 list 내 순서는 보존하면서 일자 단위로 정렬
    all_items.sort(key=lambda x: x.get("_permit_date", ""), reverse=True)

    return {
        "area_cd": area_cd,
        "period": {"start": dates[-1], "end": dates[0], "days": days},
        "total": len(all_items),
        "items": all_items[:100],  # 응답 비대 방지 — 첫 100건
        "fetch_errors": errors,
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
        raise HTTPException(500, "토지정보 조회 오류")


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
        raise HTTPException(500, "진단 중 오류가 발생했습니다")


@app.post("/api/diagnose/whatif")
async def diagnose_whatif(req: WhatIfRequest):
    """What-if 재진단 — 변수 조정 후 빠른 재계산.

    설비·소방 카드는 cached_fire_safety 재사용으로 AI 호출 생략(skip_ai=True).
    토지 정보는 PNU 캐시 적중으로 VWorld 재호출 생략.
    """
    if engine is None or land_resolver is None:
        raise HTTPException(503, "서비스 초기화 중")
    try:
        payload = _attach_total_floor_area(
            req.model_dump(exclude={"cached_fire_safety"})
        )
        address = payload["address"]
        pnu = payload.get("pnu") or ""
        # land_info_cache 적중 시 VWorld 재호출 안 함
        land = await land_resolver.resolve(address, pnu=pnu)
        if payload.get("zone_use_override"):
            land["zone_use"] = payload["zone_use_override"]
        if payload.get("zone_district"):
            land["zone_district"] = payload["zone_district"]
        zone_use = land.get("zone_use", "")
        if not zone_use:
            raise HTTPException(
                400,
                "용도지역 미확인 — 원본 진단을 먼저 실행하거나 zone_use_override 입력 필요",
            )
        diag = await engine.diagnose_fast(
            payload, zone_use=zone_use, land_info=land,
            skip_ai=True,
            cached_fire_safety=req.cached_fire_safety,
        )
        return diag
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("What-if 진단 오류: %s", e)
        raise HTTPException(500, "What-if 진단 중 오류")


@app.post("/api/diagnose/multi")
async def diagnose_multi(req: MultiDiagnoseRequest):
    """합필 진단 — 여러 필지를 합쳐 단일 사업지로 진단.

    Phase 2: 동일 용도지역 / 소규모 예외(≤330㎡) / 면적 안분 가중평균 지원.
    """
    if engine is None or land_resolver is None:
        raise HTTPException(503, "서비스 초기화 중")
    try:
        # 1. 각 필지 용도지역 병렬 조회 + zone_use_override 반영
        #    한 필지 조회가 실패해도 전체 요청이 죽지 않도록 예외를 개별 수집
        lands = await asyncio.gather(*[
            land_resolver.resolve(p.address, pnu=p.pnu or "")
            for p in req.parcels
        ], return_exceptions=True)
        failed: list[str] = []
        for p, land in zip(req.parcels, lands):
            if isinstance(land, Exception):
                logger.warning("필지 조회 실패: %s (%s)", p.address, land)
                failed.append(p.address)
                continue
            if p.zone_use_override:
                land["zone_use"] = p.zone_use_override
        if failed:
            raise HTTPException(
                400,
                {
                    "error": "ZONE_LOOKUP_FAILED",
                    "message": (
                        f"{len(failed)}개 필지 조회 실패. "
                        "주소를 다시 선택하거나 용도지역을 직접 지정해주세요."
                    ),
                    "failed_addresses": failed,
                },
            )

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
        raise HTTPException(500, "멀티 진단 중 오류")


class ExportRequest(BaseModel):
    """진단 결과 → MD / xlsx 변환 요청.

    프론트에서 현재 진단 결과(result)와 입력값(form_data)을 그대로 POST.
    Stateless — 서버에 결과 캐싱 안 함.
    """
    result: dict = Field(..., description="진단 결과 dict (run / diagnose_fast / multi 응답)")
    form_data: dict | None = Field(None, description="원본 입력 폼 데이터 (선택)")
    project_name: str = Field("", description="프로젝트명 (보고서 헤더)")
    company: str = Field("", description="회사명 (보고서 푸터)")
    author: str = Field("", description="작성자 (보고서 푸터)")


@app.post("/api/diagnose/export/md")
async def diagnose_export_md(req: ExportRequest):
    """진단 결과 → Markdown 텍스트 다운로드."""
    try:
        from fastapi.responses import Response
        md = diagnose_to_markdown(
            req.result, req.form_data, req.project_name, req.company, req.author,
        )
        # UTF-8 BOM (﻿) 추가 — 한국 Windows 메모장/일부 에디터가
        # BOM 없는 UTF-8을 latin-1/CP949로 잘못 해석하는 문제 방지
        return Response(
            content=("﻿" + md).encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": _build_content_disposition(req, ext="md"),
                "Cache-Control": "no-store",
            },
        )
    except Exception as e:
        logger.exception("MD export 오류: %s", e)
        raise HTTPException(500, "MD export 오류")


@app.post("/api/diagnose/export/xlsx")
async def diagnose_export_xlsx(req: ExportRequest):
    """진단 결과 → xlsx 파일 다운로드."""
    try:
        from fastapi.responses import Response
        xlsx = diagnose_to_xlsx(
            req.result, req.form_data, req.project_name, req.company, req.author,
        )
        return Response(
            content=xlsx,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": _build_content_disposition(req, ext="xlsx"),
                "Cache-Control": "no-store",
            },
        )
    except Exception as e:
        logger.exception("xlsx export 오류: %s", e)
        raise HTTPException(500, "xlsx export 오류")


def _build_content_disposition(req: ExportRequest, *, ext: str) -> str:
    """RFC 5987 형식 — ASCII fallback + UTF-8 인코딩 파일명 둘 다 제공.

    HTTP 헤더는 latin-1만 허용하므로 한글 파일명은 percent-encoding 필요.
    브라우저는 filename*=UTF-8 을 우선 사용, 미지원 시 filename 사용.
    """
    import re
    from urllib.parse import quote

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = req.project_name or req.result.get("address") or "diagnose"
    # 파일명 부적합 문자 제거
    base = re.sub(r"[\\/:*?\"<>|]", "_", base)[:60].strip() or "diagnose"

    utf8_name = f"{ts}_{base}.{ext}"
    # ASCII fallback: 비ASCII 문자는 _ 로 대체
    ascii_name = re.sub(r"[^\x20-\x7e]", "_", utf8_name)
    # filename* (RFC 5987): UTF-8 percent-encoded
    encoded = quote(utf8_name, safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"


@app.post("/api/feasibility/run")
async def feasibility_run(req: FeasibilityRequest):
    """사전 사업성 검토 — 공모 요구치 vs 법적 가능 범위 갭 분석.

    검증 모드(/api/diagnose)와 같은 엔진을 공유하되, 입력·출력 형태가 다르다.
    - 입력: 사용자가 설계한 안이 아니라 공모가 요구하는 값(target_*)
    - 출력: 갭 분석 + 완화 시나리오 추천 + 심의 부담 + 종합 판단(참여/협상/패스)
    """
    if engine is None:
        raise HTTPException(503, "서비스 초기화 중")
    try:
        result = await run_feasibility(engine, req.model_dump())
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("사업성 검토 오류: %s", e)
        raise HTTPException(500, "사업성 검토 중 오류")


@app.post("/api/feasibility/export/md")
async def feasibility_export_md(req: ExportRequest):
    """사업성 검토 결과 → Markdown 1장 요약 다운로드."""
    try:
        from fastapi.responses import Response

        from services.feasibility_exporter import to_markdown as feas_to_md
        md = feas_to_md(
            req.result, req.form_data, req.project_name, req.company, req.author,
        )
        return Response(
            content=("﻿" + md).encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": _build_content_disposition(req, ext="md"),
                "Cache-Control": "no-store",
            },
        )
    except Exception as e:
        logger.exception("사업성 MD export 오류: %s", e)
        raise HTTPException(500, "사업성 MD export 오류")


@app.post("/api/feasibility/export/xlsx")
async def feasibility_export_xlsx(req: ExportRequest):
    """사업성 검토 결과 → xlsx 다운로드."""
    try:
        from fastapi.responses import Response

        from services.feasibility_exporter import to_xlsx as feas_to_xlsx
        xlsx = feas_to_xlsx(
            req.result, req.form_data, req.project_name, req.company, req.author,
        )
        return Response(
            content=xlsx,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": _build_content_disposition(req, ext="xlsx"),
                "Cache-Control": "no-store",
            },
        )
    except Exception as e:
        logger.exception("사업성 xlsx export 오류: %s", e)
        raise HTTPException(500, "사업성 xlsx export 오류")


@app.post("/api/feasibility/export/html")
async def feasibility_export_html(req: ExportRequest):
    """사업성 검토 결과 → 자체완결 HTML 보고서 (브라우저 보기·인쇄/PDF용)."""
    try:
        from fastapi.responses import Response

        from services.feasibility_exporter import to_html as feas_to_html
        doc = feas_to_html(
            req.result, req.form_data, req.project_name, req.company, req.author,
        )
        return Response(
            content=doc.encode("utf-8"),
            media_type="text/html; charset=utf-8",
            headers={
                # inline — 새 탭에서 바로 보기/인쇄. 파일명은 저장 시 사용.
                "Content-Disposition": _build_content_disposition(req, ext="html").replace(
                    "attachment;", "inline;"
                ),
                "Cache-Control": "no-store",
            },
        )
    except Exception as e:
        logger.exception("사업성 HTML export 오류: %s", e)
        raise HTTPException(500, "사업성 HTML export 오류")


@app.post("/api/feasibility/run-multi")
async def feasibility_run_multi(req: MultiFeasibilityRequest):
    """다중 대지 동시 사업성 비교 — 부지별로 병렬 실행 후 결과 묶음 반환.

    한 부지 실패가 전체를 막지 않도록 항목별로 오류를 격리한다.
    """
    if engine is None:
        raise HTTPException(503, "서비스 초기화 중")

    async def _one(site_req: FeasibilityRequest):
        label = site_req.site_label or site_req.address
        try:
            res = await run_feasibility(engine, site_req.model_dump())
            res["site_label"] = label
            return {"ok": True, "result": res}
        except Exception as e:  # noqa: BLE001 — 항목 격리
            logger.warning("[다중 사업성] 부지 실패 (%s): %s", label, e)
            return {"ok": False, "site_label": label, "error": str(e)}

    results = await asyncio.gather(*[_one(s) for s in req.sites])
    return {"results": results, "count": len(results)}


@app.get("/api/feasibility/briefs")
async def feasibility_brief_list(
    limit: int = Query(100, ge=1, le=1000, description="상세 로드할 최근 건수"),
    category: str | None = Query(None, description="카테고리 필터(public·residential 등)"),
):
    """공모지침 분석 결과(_brief.json) 목록 — BRIEF_DIR(공유 GCS 마운트)의 _briefs/ 스캔.

    Competition Analyzer가 저장한 brief를 사업성 모드로 불러오기 위한 목록.
    파일명(날짜·카테고리)으로 정렬·필터 후 최근 limit건만 본문을 읽는다(성능).
    """
    from services import brief_importer
    try:
        return {"briefs": brief_importer.list_briefs(limit=limit, category=category)}
    except Exception as e:
        logger.exception("brief 목록 조회 오류: %s", e)
        raise HTTPException(500, "brief 목록 조회 오류")


@app.get("/api/feasibility/briefs/{file_id}")
async def feasibility_brief_get(file_id: str):
    """선택한 brief를 사업성 prefill(부지별 target_*)로 매핑해 반환."""
    from services import brief_importer
    try:
        return brief_importer.get_brief_mapped(file_id)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("brief 매핑 오류: %s", e)
        raise HTTPException(500, "brief 매핑 오류")


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
        raise HTTPException(500, "자연어 질의 오류")


# ── 법규 의미 그래프 (Step 11) ──────────────────────────────────────────────


@app.get("/api/law-graph")
async def law_graph_all():
    """법규 의미 그래프 전체 (노드 + 엣지 + 메타) — 관계 탐색 UI용."""
    from services import law_graph
    try:
        return law_graph.get_graph_dict()
    except Exception as e:
        logger.exception("법규 그래프 조회 오류: %s", e)
        raise HTTPException(500, "법규 그래프 조회 오류")


@app.get("/api/law-graph/node/{node_id}")
async def law_graph_node(node_id: str):
    """노드 1개 + 인접 관계(나가는/들어오는, rel별)."""
    from services import law_graph
    detail = law_graph.node_detail(node_id)
    if detail is None:
        raise HTTPException(404, f"노드 없음: {node_id}")
    return detail


@app.get("/api/law-graph/category/{node_id}")
async def law_graph_category(node_id: str):
    """카테고리(또는 임의) 노드에서 도달하는 서브그래프."""
    from services import law_graph
    sub = law_graph.category_subgraph(node_id)
    if sub is None:
        raise HTTPException(404, f"노드 없음: {node_id}")
    return sub


@app.post("/api/law-graph/promote")
async def law_graph_promote(req: LawGraphCurateRequest):
    """auto 수확 엣지를 검토 후 seed로 승격(영구화, 재수확해도 유지)."""
    from services import law_graph_curate
    if not req.source or not req.target:
        raise HTTPException(400, "엣지 승격은 source·target이 필요합니다")
    result = law_graph_curate.promote_edge(req.source, req.target)
    if not result.get("ok"):
        raise HTTPException(404, result.get("reason", "승격 실패"))
    return result


@app.post("/api/law-graph/reject")
async def law_graph_reject(req: LawGraphCurateRequest):
    """auto 수확 항목을 반려(제거 + 재수확 차단). 엣지 또는 노드 단위."""
    from services import law_graph_curate
    if req.source and req.target:
        result = law_graph_curate.reject_edge(req.source, req.target)
    elif req.node_id:
        result = law_graph_curate.reject_node(req.node_id)
    else:
        raise HTTPException(400, "반려는 (source·target) 또는 node_id가 필요합니다")
    if not result.get("ok"):
        raise HTTPException(404, result.get("reason", "반려 실패"))
    return result


# ── Phase 4 엔드포인트 ─────────────────────────────────────────────────────


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
        raise HTTPException(500, "법규 변경 조회 오류")


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
        raise HTTPException(500, "법규 스캔 오류")


@app.post("/api/law/changes/seed_demo")
async def law_changes_seed_demo(
    jurisdiction_code: str = Query("11560"),
    law_type: str = Query("urban_planning"),
):
    """데모용 — 가짜 변경 이벤트 강제 삽입 (운영 환경에서는 비활성 권장)."""
    if law_tracker is None:
        raise HTTPException(503, "서비스 초기화 중")
    return await law_tracker.seed_demo_change(jurisdiction_code, law_type)


@app.post("/api/law/scan_now")
async def law_scan_now():
    """17개 시도 도시계획조례 즉시 일괄 스캔 (운영자/관리자용).

    스케줄러가 정기 실행하는 작업과 동일. 변경 감지 결과를 반환.
    실행 시간: 약 30초~1분 (시도 17곳 × 평균 1.5초).
    """
    if law_tracker is None:
        raise HTTPException(503, "서비스 초기화 중")
    from services.law_change_scheduler import scan_all_sido
    try:
        return await scan_all_sido(law_tracker)
    except Exception as e:
        logger.exception("law_scan_now 오류: %s", e)
        raise HTTPException(500, "법규 일괄 스캔 오류")


@app.get("/api/law/scheduler_status")
async def law_scheduler_status():
    """법규 변경 cron 스케줄러 상태 (다음 실행 시각 등)."""
    if law_change_scheduler is None:
        return {"enabled": False, "reason": "ENABLE_LAW_CHANGE_CRON=false 또는 미초기화"}
    job = law_change_scheduler.get_job("law_change_scan")
    if job is None:
        return {"enabled": True, "running": False, "next_run_time": None}
    return {
        "enabled": True,
        "running": True,
        "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        "trigger": str(job.trigger),
    }


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
        raise HTTPException(500, "리뷰 요청 오류")


# ── 발주처 지침서 PDF 추출 ─────────────────────────────────────────────────────

@app.post("/api/brief/extract")
async def brief_extract(file: UploadFile = File(...)):
    """발주처 지침서 PDF → 설계 조건 JSON 추출.

    multipart/form-data 로 PDF 파일 전송.
    반환: {max_bcr_pct, max_far_pct, max_floors, max_height_m,
           min_landscape_pct, min_parking_spaces,
           required_uses, prohibited_uses, special_conditions, source_excerpt}
    """
    if llm_client is None or not llm_client.available:
        raise HTTPException(503, "AI 서비스(ANTHROPIC_API_KEY) 미설정 — PDF 추출 불가")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "PDF 파일만 업로드 가능합니다")

    MAX_MB = 20
    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_MB * 1024 * 1024:
        raise HTTPException(413, f"파일 크기 {MAX_MB}MB 초과")

    from services.brief_extractor import extract_from_pdf
    try:
        result = await extract_from_pdf(pdf_bytes, llm_client)
        logger.info(
            "지침서 추출 완료: %s (%d chars, %d pages)",
            file.filename, result.get("_text_length", 0), result.get("_pages_extracted", 0),
        )
        return result
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        logger.exception("지침서 추출 오류: %s", e)
        raise HTTPException(500, "추출 오류")


# ── 프론트엔드 정적 파일 서빙 (컨테이너 단일 포트 운영용) ─────────────────
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """SPA 라우팅 — /api/* 외 모든 경로를 index.html 로 반환."""
        return FileResponse(str(_DIST / "index.html"))

