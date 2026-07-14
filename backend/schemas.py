"""API 입력 스키마 (Pydantic). main.py 에서 분리 — 순수 데이터 정의, 상태·의존성 없음."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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
    road_width: float | None = Field(None, gt=0, description="전면도로 폭 (m), 미입력 시 추정")
    landscape_area: float | None = Field(
        None, ge=0, description="조경면적 (㎡, 선택). 미입력 시 의무비율만 표시"
    )
    provided_parking_spaces: int | None = Field(
        None, ge=0, description="계획 주차대수 (선택). 미입력 시 법정 기준만 표시"
    )
    unit_exclusive_area: float | None = Field(
        None, gt=0,
        description="세대 평균 전용면적 (㎡, 공동주택·다가구·오피스텔). 60㎡ 이하/초과 분기에 사용"
    )
    parking_capacity: int | None = Field(
        None, ge=1,
        description="홀 수(골프장) / 타석 수(골프연습장) / 정원(옥외수영장·관람장). count_based 용도에만 사용"
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
    pilot_project: bool = Field(False, description="녹색건축 시범사업 여부 (용적률 완화 레버)")
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

    # 특별 완화 토글 (선택)
    rooftop_landscape_area: float | None = Field(
        None, ge=0, description="옥상 조경면적 (㎡) — 2/3 인정, 의무면적 50% 상한 (§27 ③항)"
    )
    building_agreement: bool = Field(False, description="건축협정 체결 (§110의7) — 건폐율·용적률 1.2배")
    agreement_landscape_road_facing: bool = Field(
        False, description="건축협정 조경 도로면 통합 조성 — 조경 의무 0.8배 (§110의7 1호)"
    )
    rema_zone: bool = Field(False, description="재정비촉진지구 — 용적률 법정 상한 ×1.2 (도시재정비촉진법 §19)")
    easy_remodel: bool = Field(False, description="리모델링이 쉬운 구조 인증 — 용적률 ×1.2 (공동주택 한정, 시행령 §6의5)")
    public_rental: bool = Field(False, description="공공지원민간임대주택 — 건폐율·용적률 법정 상한 (민간임대주택법 §21)")

    # 신청 주체 (선택) — 공공기관 여부에 따라 의무 인증 5종·BF 등 추가 판정
    applicant_type: str = Field(
        "개인",
        description="신청 주체: 개인 / 민간법인 / 공공기관",
    )

    # 도시계획시설 결정고시 (선택)
    decision_notice_confirmed: bool = Field(
        False, description="도시계획시설 결정고시 확인됨 — 저촉 판정 조건부 통과로 전환"
    )
    decision_far_limit: float | None = Field(
        None, gt=0, description="결정고시 용적률 한도 (%) — 일반 한도 대신 사용"
    )
    decision_cov_limit: float | None = Field(
        None, gt=0, description="결정고시 건폐율 한도 (%) — 일반 한도 대신 사용"
    )
    decision_height_limit: float | None = Field(
        None, gt=0, description="결정고시 높이 한도 (m) — 가로구역 최고높이 대신 사용"
    )

    # 발주처 지침서 추출 조건 (선택) — /api/brief/extract 결과를 그대로 전달
    brief_conditions: dict | None = Field(
        None,
        description=(
            "발주처 지침서 PDF에서 추출한 설계 조건. "
            "법규 기준보다 엄격한 항목은 진단에서 지침서 기준 우선 적용."
        ),
    )


class WhatIfRequest(DiagnoseRequest):
    """What-if 재진단 요청 — DiagnoseRequest 모든 필드 + 캐시.

    토지 정보(VWorld) 는 PNU 캐시 적중에 의존하므로 별도 입력 불필요.
    설비·소방 카드는 비싸므로 원본 결과를 cached_fire_safety 로 받아 재사용.
    """
    cached_fire_safety: dict | None = Field(
        None, description="원본 진단 결과의 '설비_소방' 카드. AI 재호출 절약용.",
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
    road_width: float | None = Field(None, gt=0, description="전면도로 폭 (m)")
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


class FeasibilityRequest(BaseModel):
    """사전 사업성 검토 — 공모 받았는데 들어갈 만한가?

    설계 시작 전에 공모 요구치와 법적 가능 범위를 비교한다.
    검증 모드(/api/diagnose)와 달리 사용자 안이 없어도 동작.
    """
    address: str = Field(..., description="도로명 또는 지번 주소")
    pnu: str | None = Field(None, description="필지번호 (선택)")
    facility_use: str = Field(..., description="시설 용도 (건축법 분류)")
    building_use_detail: str | None = Field(None, description="세부 용도 자유 입력")
    applicant_type: str = Field("개인", description="신청 주체: 개인/민간법인/공공기관")
    zone_use_override: str | None = Field(None, description="용도지역 직접 지정")
    zone_district: str | None = Field(None, description="지역지구 직접 지정")
    road_width: float | None = Field(None, gt=0, description="전면도로 폭 (m)")
    site_area_override: float | None = Field(
        None, gt=0, description="대지면적 직접 입력 (VWorld 자동 조회 실패 시)"
    )

    # 공모 요구치 — 모두 선택. 빈 칸은 갭 분석에서 "요구 없음"으로 처리
    target_floor_area_sqm: float | None = Field(
        None, gt=0, description="공모가 요구하는 연면적 (㎡)"
    )
    target_building_coverage_pct: float | None = Field(
        None, gt=0, le=100, description="공모가 요구하는 건폐율 (%)"
    )
    target_far_pct: float | None = Field(
        None, gt=0, description="공모가 요구하는 용적률 (%)"
    )
    target_max_height_m: float | None = Field(
        None, gt=0, description="공모가 요구하는 최고 높이 (m)"
    )
    target_floors_above: int | None = Field(
        None, ge=1, description="공모가 요구하는 지상 층수"
    )
    target_parking_count: int | None = Field(
        None, ge=0, description="공모가 요구하는 주차대수"
    )
    target_open_space_sqm: float | None = Field(
        None, ge=0, description="공모가 요구하는 공개공지 (㎡)"
    )
    target_units: int | None = Field(
        None, ge=1, description="공모가 요구하는 세대수 (공동주택)"
    )
    unit_exclusive_area: float | None = Field(
        None, gt=0, description="세대 평균 전용면적 (㎡, 공동주택·다가구·오피스텔)"
    )

    # 완화 레버 — 대안 비교(What-If)용. 미지정 시 모두 OFF (= raw 법한계)
    green_grade: str | None = Field(None, description="녹색건축 인증 등급: 우수/최우수")
    energy_grade: str | None = Field(None, description="제로에너지건축 등급: 1~5")
    pilot_project: bool = Field(False, description="녹색건축 시범사업 여부")
    building_agreement: bool = Field(False, description="건축협정 체결 (§110의7)")
    rema_zone: bool = Field(False, description="재정비촉진지구 특례")
    easy_remodel: bool = Field(False, description="리모델링이 쉬운 구조 (공동주택)")

    # 다중 대지 비교용 라벨 (선택)
    site_label: str | None = Field(None, description="비교표에 표시할 부지 이름")


class MultiFeasibilityRequest(BaseModel):
    """다중 대지 동시 사업성 비교 — 부지별 요청 목록."""
    sites: list[FeasibilityRequest] = Field(..., min_length=1, max_length=12)


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=2, description="자연어 질문")
    address: str | None = None
    zone_use: str | None = None
    building_info: dict[str, Any] | None = None
    current_result: dict[str, Any] | None = None


class LawGraphCurateRequest(BaseModel):
    """법규 그래프 auto 항목 승격/반려. 엣지=source+target, 노드=node_id."""
    source: str | None = None
    target: str | None = None
    node_id: str | None = None


class ReviewRequest(BaseModel):
    address: str = Field(..., description="대상 대지 주소")
    risk_category: str = Field(..., description="위험 카테고리 (예: 건폐율)")
    risk_reason: str = Field(..., description="위험 내용 / 진단 노트")
    requester: str | None = Field(None, description="요청자 이름/이메일 (선택)")
    building_info: dict[str, Any] | None = None
    signal: str | None = None
    overall_score: float | None = None
    note: str | None = Field(None, description="추가 메모 (선택)")
