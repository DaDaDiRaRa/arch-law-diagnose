# arch-law-diagnose — 프로젝트 요약

---

## 앱 개요

**arch-law-diagnose**는 건축 인허가 전 단계에서 주소와 건물 정보를 입력하면 8개 법규 카테고리를 자동 진단해 GREEN/YELLOW/RED 신호와 종합 점수(0~10)를 반환하는 사내 전용 진단 보조 시스템이다.

- **목적**: 건축사·설계자가 수작업으로 확인하던 건폐율·용적률·높이·주차·조경·행위제한·도시계획시설·설비소방을 자동화. 실제 인허가 결정은 시니어 건축사가 검토.
- **주요 사용자**: 사내 건축사·설계 담당자 (초기 법규 검토 단계)
- **사용 맥락**: 프로젝트 초기에 "이 땅에 이 건물이 법적으로 가능한가?"를 빠르게 확인하는 용도. 결과는 참고용이며 인허가 책임은 시니어에게 있다.

---

## 기술 스택

### 언어 및 프레임워크

| 영역 | 기술 | 비고 |
|---|---|---|
| Backend | Python 3.12 + FastAPI | 비동기(async/await) 전체 적용 |
| Frontend | React 18 + Vite + Tailwind CSS | SPA, JSX |
| DB | SQLite (WAL 모드) | `./data/arch_law.db`, CacheManager 관리 |
| 상태 관리 | Zustand | 입력 폼·진단 결과·추가 필지 공유 |
| 공간 연산 | Shapely | 도시계획시설 저촉, 철도보호지구 좌표 판정 |
| PDF 처리 | PyMuPDF (fitz) | 지침서 파일 텍스트 추출 |
| AI | Anthropic Claude API | 설비·소방 정성 판단 + 자연어 질의 + 조례 수치 추출 |

### 주요 Python 라이브러리

`fastapi`, `pydantic`, `uvicorn`, `httpx`, `aiohttp`, `shapely`, `pyproj`, `fitz(PyMuPDF)`, `anthropic`, `aiosqlite`, `apscheduler`, `lxml`

### 주요 JS 라이브러리

`react`, `vite`, `tailwindcss`, `zustand`, `axios`(미사용, fetch 직접 사용)

### 외부 API

| 서비스 | 환경변수 | 용도 | 필수 여부 |
|---|---|---|---|
| Anthropic Claude | `ANTHROPIC_API_KEY` | 설비·소방 AI 판단, 자연어 질의, 조례 수치 추출 | 필수 |
| VWorld OpenAPI | `VWORLD_API_KEY` | 좌표 변환, 용도지역 조회, 지적도 폴리곤, 도로폭 | 필수 |
| Kakao 로컬 API | `KAKAO_API_KEY` | 주소 자동완성 | 필수 |
| LURIS (공공데이터포털) | `LURIS_API_KEY` | 행위제한 정보 조회 | 선택 (EUM으로 교차검증) |
| 토지이음 (EUM) | `EUM_ID`, `EUM_KEY` | 법령정보·행정 고시·개발 인허가·UCODE 변환 | 선택 |
| 법제처 공개 API | `LAW_API_KEY` | 조례 본문 수집, 조례 변경 감지 | 선택 |
| 행안부 도로명주소 | `JUSO_API_KEY` | 주소 검색 폴백 | 선택 |
| Slack webhook | `SLACK_WEBHOOK_URL` | 시니어 검토 요청 알림 | 선택 |

---

## 핵심 기능 목록

### 1. 단일 필지 진단 (`POST /api/diagnose`)
- 주소·건물 정보 입력 → 8개 카테고리 자동 계산 → GREEN/YELLOW/RED 신호 + 종합 점수 반환
- **처리 파일**: `backend/main.py` → `services/diagnose_engine.py` → `services/calculator/*.py`

### 2. 합필(多필지) 진단 (`POST /api/diagnose/multi`)
- 여러 필지를 하나로 합쳐 진단. 모두 같은 용도지역이면 단순 합산, 다른 지역이면 면적 안분 가중평균
- **처리 파일**: `backend/main.py` → `services/multi_parcel.py` → `services/diagnose_engine.py`

### 3. What-if 시뮬레이션 (`POST /api/diagnose/whatif`)
- 건축면적·연면적·높이·층수·주차 수를 슬라이더로 조정하면 300ms debounce 후 진단 재실행
- 토지 정보와 설비·소방 결과는 캐시 재사용(AI 호출 절감)
- **처리 파일**: `backend/main.py` → `services/diagnose_engine.py` (skip_ai=True)
- **프론트**: `frontend/src/components/WhatIfPanel/index.jsx`

### 4. 자연어 질의 (`POST /api/query`)
- 진단 결과를 컨텍스트로 Claude API에 질의. 조문 URL 자동 인용
- **처리 파일**: `backend/main.py` → `services/query_engine.py` → `services/llm_client.py`
- **프론트**: `frontend/src/components/QueryBox/index.jsx`

### 5. 주소 자동완성 (`GET /api/address/search`)
- Kakao 로컬 API 호출. 도로명·지번 모두 지원, 실패 시 행안부 API 폴백
- **처리 파일**: `backend/main.py` → `services/address_api_client.py`
- **프론트**: `frontend/src/components/AddressSearch/index.jsx`

### 6. VWorld 토지정보 자동 조회 (`GET /api/land_info`)
- 주소 입력 시 용도지역·지역지구·도로폭을 VWorld에서 자동 조회해 폼에 채움
- SQLite 30일 캐시로 재조회 최소화. 조회 실패 시 stale 캐시 사용
- **처리 파일**: `backend/main.py` → `services/land_use_resolver.py` → `services/vworld_client.py`

### 7. 용적률 완화 계산 (`far_relief.py`)
- 공개공지, 녹색건축(최우수 6%·우수 3%), ZEB(1등급 15%~5등급 11%), 지능형·장수명(일부 미구현)
- 인증 합산 캡 15%, 전체 캡 기본 한도의 1.15배 적용
- **처리 파일**: `services/far_relief.py`, `config/far_relief_rules.json`

### 8. 건축협정 완화 (`building_agreement.py`)
- 건축협정 체결 시 건폐율·용적률 1.2배, 조경 의무 0.8배, 높이 §86③ 완화 사후 적용
- **처리 파일**: `services/building_agreement.py`

### 9. 조례 자동 조회 및 캐시 (`ordinance_resolver.py`)
- 시군구 코드 기반으로 건폐율·용적률 상한을 DB → 법제처 API → 시행령 순서로 cascade 조회
- LLM(Claude)으로 조례 본문에서 수치 추출. 추출 실패 시 needs_review=True 처리
- **처리 파일**: `services/ordinance_resolver.py`, `services/ordinance_extractor.py`

### 10. 법규 변경 감지 (`law_change_tracker.py`)
- 조례 본문 SHA256 해시를 DB에 저장하고, 변경 감지 시 프론트 알림 배너(주황색) 표시
- **처리 파일**: `services/law_change_tracker.py`, `services/law_change_scheduler.py`
- **프론트**: `frontend/src/components/LawChangeAlert/index.jsx`

### 11. 행정 고시 조회 (토지이음)
- 해당 시군구의 최근 90일 도시계획 결정·고시를 토지이음 API로 조회해 파란색 배너로 표시
- **처리 파일**: `services/eum_client.py`
- **프론트**: `frontend/src/components/LawChangeAlert/index.jsx`

### 12. 토지이음 법령정보 펼쳐보기
- 사용자가 클릭 시 UCODE별 법령 본문을 lazy fetch해 표시
- **처리 파일**: `services/eum_client.py`
- **프론트**: `frontend/src/components/LawInfoPanel/index.jsx`

### 13. 주변 개발 인허가 동향
- 토지이음 API로 반경 내 최근 인허가 목록 조회 (7/14/30일 토글)
- **처리 파일**: `services/eum_client.py`
- **프론트**: `frontend/src/components/DevTrendPanel/index.jsx`

### 14. 사내 케이스 추천 (`case_matcher.py`)
- 같은 용도지역·건물용도 조합의 기존 프로젝트 케이스 매칭
- **처리 파일**: `services/case_matcher.py`, `KUNWON_DB/cases/*.json`
- **프론트**: `frontend/src/components/CaseReference/index.jsx`

### 15. 심의 자동 트리거 (`review_triggers.py`)
- 건축위원회·도시계획심의·경관심의 등 8종 심의 필요 여부를 자동 판정
- 연면적·층수·높이·특수 용도 기반 규칙
- **처리 파일**: `services/review_triggers.py`

### 16. PDF 지침서 업로드 및 추출 (`brief_extractor.py`)
- 건축 지침서 PDF를 업로드하면 Claude Vision으로 주요 법규 수치 추출
- **처리 파일**: `services/brief_extractor.py`
- **프론트**: `frontend/src/components/BriefUploader/index.jsx`

### 17. 종합 검토 보고서 + 시니어 검토 요청
- 위험 카테고리별 상세 리포트 생성. 시니어 검토 요청 시 Slack webhook 또는 로컬 로그 저장
- **처리 파일**: `services/review_notifier.py`
- **프론트**: `frontend/src/components/LegalReviewReport/index.jsx`, `ReviewRequestButton/index.jsx`

### 18. 도시계획시설 저촉 판정 (`urban_facility.py`)
- VWorld 지적 폴리곤과 도시계획시설 SHP 파일을 Shapely로 교차해 저촉 면적·비율 산정
- **처리 파일**: `services/calculator/urban_facility.py`, `services/urban_facility/indexer.py`

### 19. 데이터 품질 배너 (`DataQualityBanner`)
- VWorld 미조회, 조례 미적용, LURIS 미설정 등 진단 신뢰도에 영향을 주는 상황을 프론트에 표시
- **처리 파일**: `frontend/src/components/DataQualityBanner/index.jsx`

---

## 파일 구조

```
arch-law-diagnose/
├── Dockerfile                         # 멀티 스테이지 빌드 (Node 20 + Python 3.12-slim)
├── .dockerignore
├── CLAUDE.md                          # 개발 진행 상황·규칙·다음 작업
├── DEPLOY.md                          # Docker/Cloud Run 배포 가이드
├── SETUP.md                           # 로컬 환경 설정 가이드
├── summary.md                         # 이 파일
│
├── backend/
│   ├── main.py                        # FastAPI 진입점. 9개 엔드포인트 + lifespan 초기화
│   │
│   ├── config/
│   │   ├── zone_limits.json           # 국토계획법 시행령 별표. 19개 용도지역 기본 건폐율·용적률·높이
│   │   ├── law_scoring_weights.json   # 8개 카테고리 종합점수 가중치
│   │   ├── far_relief_rules.json      # 용적률 완화 규정 (원문 대조 완료, 2026-05-20)
│   │   ├── landscape_standards.json   # 조경 기준. by_zone 수치 대부분 조례 위임 → pass=None
│   │   ├── parking_standards.json     # 주차 기준. 건축물 용도별 산정 방식
│   │   ├── street_block_heights.json  # 가로구역별 최고높이 DB (지자체별 선택 적재)
│   │   ├── municipal_codes.json       # 시군구 5자리 코드 ↔ 지역명
│   │   ├── ucode_mapping.json         # 용도지역 표준명 ↔ 토지이음 UCODE 6자리
│   │   └── ordinance_seed.json        # 서울 도시계획조례 §54·§55 초기값 (서울만)
│   │
│   ├── services/
│   │   ├── diagnose_engine.py         # 진단 전체 오케스트레이션. 계산기 호출·신호 판정·이력 저장
│   │   ├── query_engine.py            # 자연어 질의. 진단 컨텍스트 + Claude API
│   │   ├── cache_manager.py           # SQLite lazy cache. 조례 30일·LURIS 90일 TTL
│   │   ├── llm_client.py              # Claude API 래퍼. temp=0, prompt caching, 3단계 JSON 파싱
│   │   ├── vworld_client.py           # VWorld API. geocode·용도지역·WFS 폴리곤·도로폭
│   │   ├── address_api_client.py      # Kakao 로컬 API. 도로명+지번 자동완성
│   │   ├── luris_client.py            # LURIS API. 행위제한 조회, EUC-KR 디코딩 필요
│   │   ├── eum_client.py              # 토지이음 표준연계 API. XML 파싱, 7개 메서드
│   │   ├── law_go_kr_client.py        # 법제처 공개 API. 조례·법률 검색·본문 수집
│   │   ├── land_use_resolver.py       # 토지정보 통합 조회. VWorld + 캐시 + stale fallback
│   │   ├── ordinance_resolver.py      # 조례 cascade 조회. DB → 법제처 → zone_limits.json
│   │   ├── ordinance_extractor.py     # 조례 본문 → 수치 추출. regex → LLM fallback
│   │   ├── far_relief.py              # 용적률 완화 계산. 4종 + 합산 캡 1.15배
│   │   ├── building_agreement.py      # 건축협정 §110의7 완화. 건폐율·용적률 1.2배
│   │   ├── multi_parcel.py            # 합필 진단. 면적 안분 + 소규모 예외(≤330㎡)
│   │   ├── zone_use_normalizer.py     # 용도지역 표준명 정규화. 19종 + 61개 별칭
│   │   ├── review_triggers.py         # 심의 자동 트리거. 8종 (건축위·도시계획·경관 등)
│   │   ├── case_matcher.py            # 사내 케이스 매칭. KUNWON_DB/cases/*.json 검색
│   │   ├── law_change_tracker.py      # 조례 변경 감지. SHA256 해시 비교
│   │   ├── law_change_scheduler.py    # 변경 감지 cron 스케줄러 (일요일 03:00)
│   │   ├── review_notifier.py         # 시니어 검토 요청. Slack webhook + 로컬 로그
│   │   ├── brief_extractor.py         # PDF 지침서 추출. Claude Vision 기반
│   │   ├── ordinance_seed_loader.py   # ordinance_seed.json → DB 적재 (idempotent)
│   │   ├── street_block_heights_loader.py  # 가로구역 높이 JSON → 메모리 dict 적재
│   │   │
│   │   ├── calculator/
│   │   │   ├── coverage.py            # 건폐율. actual_pct vs limit_pct
│   │   │   ├── far.py                 # 용적률. 지상층만, 주차·피난·대피 제외
│   │   │   ├── height.py              # 높이·일조. §60 가로구역 + §61 사선제한
│   │   │   ├── parking.py             # 주차. 주차장법 시행령 별표 1
│   │   │   ├── landscape.py           # 조경. 건축법 §42 + 시행령 §27 + 조례
│   │   │   ├── fire_safety.py         # 설비·소방. Claude AI 정성 판단 (11개 항목)
│   │   │   ├── land_use_act.py        # 행위제한. LURIS + EUM 교차검증
│   │   │   ├── urban_facility.py      # 도시계획시설. VWorld 지적도 ∩ SHP (Shapely)
│   │   │   ├── public_certification.py  # 공공기관 의무인증 5종 (ZEB·녹색건축·BEMS 등)
│   │   │   ├── bf_certification.py    # BF 무장애 인증 등급 표시
│   │   │   ├── crime_prevention.py    # 범죄예방 건축기준 체크리스트
│   │   │   ├── multi_use.py           # 다중이용건축물 분류 (시행령 §2-17·17의2)
│   │   │   ├── zone_overlap.py        # 중첩 지구·구역 정보 표시
│   │   │   └── railway_protection.py  # 철도보호지구 30m 이내 여부
│   │   │
│   │   ├── railway/
│   │   │   └── indexer.py             # 철도노선 공간 인덱싱 (Shapely R-tree)
│   │   │
│   │   └── urban_facility/
│   │       ├── categories.py          # 도시계획시설 11개 카테고리 분류
│   │       ├── indexer.py             # 시설 SHP 공간 인덱싱
│   │       ├── lookup.py              # PNU 기반 시설 lookup
│   │       └── sido.py                # 시도별 시설 SHP 파일 경로 매핑
│   │
│   └── scripts/                       # 25개 테스트·적재·검증 스크립트 (운영 무관)
│       ├── seed_municipal_ordinances.py  # 자치구(420개) 조례 적재
│       ├── seed_ordinances.py            # 16개 시도 도시계획조례 적재
│       └── (테스트 23개)
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx                    # 메인 진단 UI. 탭 전환(진단↔질의) + 드로어(입력 수정)
│   │   ├── main.jsx                   # React 진입점
│   │   ├── index.css                  # @import kunwon-tokens.css + Tailwind base
│   │   ├── kunwon-tokens.css          # CSS 변수 60개 (색상·폰트·간격·인쇄 전용)
│   │   │
│   │   ├── components/
│   │   │   ├── InputForm/             # 전체 입력 폼. 단일+합필 모드, 주소, 특별지구 토글
│   │   │   ├── AddressSearch/         # 주소 자동완성 (Kakao API)
│   │   │   ├── BriefUploader/         # PDF 지침서 업로드 → Claude Vision 추출
│   │   │   ├── DiagnoseResult/        # 8개 카테고리 진단 카드. GREEN/YELLOW/RED 신호
│   │   │   ├── WhatIfPanel/           # What-if 슬라이더 5개 + 원본↔변경 비교 매트릭스
│   │   │   ├── QueryBox/              # 자연어 질의 + 조문 인용
│   │   │   ├── CaseReference/         # 사내 유사 케이스 추천
│   │   │   ├── LawChangeAlert/        # 조례 변경(주황) + 행정 고시(파랑) 배너
│   │   │   ├── DataQualityBanner/     # 데이터 품질 경고 (VWorld 미조회, 조례 미적용 등)
│   │   │   ├── LawInfoPanel/          # 토지이음 법령 본문 (클릭 시 lazy fetch)
│   │   │   ├── DevTrendPanel/         # 주변 개발 인허가 동향 (7/14/30일 토글)
│   │   │   ├── LegalReviewReport/     # 종합 검토 보고서 + 인쇄 미리보기
│   │   │   └── ReviewRequestButton/   # 시니어 검토 요청 버튼
│   │   │
│   │   ├── stores/
│   │   │   └── diagnoseStore.js       # Zustand. formData·result·additionalParcels·loading
│   │   │
│   │   └── utils/
│   │       └── api.js                 # fetch 래퍼. 9개 API 메서드, cache:'no-store'
│   │
│   ├── DESIGN_SYSTEM.md               # 색상 팔레트·버튼·레이아웃·컴포넌트 문서
│   ├── tailwind.config.js             # CSS 변수 → Tailwind 테마 연결
│   └── vite.config.js                 # 번들러 설정 (API 프록시 /api → localhost:8000)
│
├── KUNWON_DB/
│   └── cases/
│       └── sample_cases.json          # 사내 케이스 DB (현재 6개 더미)
│
└── data/
    └── arch_law.db                    # SQLite (자동 생성). 조례·토지정보·진단이력 캐시
```

---

## 데이터 흐름

### 단계 1 — 주소 입력 및 토지정보 자동 조회

```
사용자가 주소 타이핑
  → AddressSearch: GET /api/address/search
    → Kakao 로컬 API (도로명+지번)
    → 선택된 주소에서 PNU·법정동코드 추출

주소 선택 확정
  → GET /api/land_info?pnu=...&address=...
    → land_use_resolver.resolve()
      ① cache_manager.get_land_info(pnu) — 캐시 히트 시 즉시 반환
      ② VWorld geocode(address) → 위경도
      ③ VWorld get_land_use(lon, lat) → 용도지역·지역지구·도로폭
      ④ VWorld get_parcel_polygon(lon, lat) → 지적 폴리곤 (GeoJSON)
      ⑤ cache_manager.set_land_info(pnu, result) — 30일 TTL
      실패 시: stale 캐시 사용 (data_quality에 경고 추가)

  → 프론트: 용도지역·지역지구·도로폭 폼에 자동 입력
```

### 단계 2 — 진단 요청 및 계산

```
사용자가 폼 입력 완료 → "진단 실행" 클릭
  → POST /api/diagnose (or /api/diagnose/multi)
    → main.py: Pydantic 스키마 검증
    → diagnose_engine.run(req)

      [조례 사전 조회]
        ordinance_resolver.resolve(jur_code, zone_use, "building_coverage_ratio")
        ordinance_resolver.resolve(jur_code, zone_use, "floor_area_ratio")
          ① cache_manager.get_zone_limit() — 30일 캐시
          ② law_go_kr_client.search_law() + ordinance_extractor.extract() (LLM)
          ③ zone_limits.json 기본값 (최종 fallback)

      [도시계획시설 저촉 — 대지면적 보정]
        urban_facility.compute_facility_overlap(parcel_polygon, shp_index)
          → Shapely intersection → 저촉 면적·비율 산정
          → 실질 대지면적 = site_area - 저촉면적

      [8개 계산기 병렬 실행]
        coverage.calculate()        → 건폐율 pass/score
        far.calculate()             → 용적률 pass/score
          └ far_relief.compute()   → 4종 완화 후 용적률 재계산
        height.calculate()          → §60 가로구역 + §61 사선제한
        parking.calculate()         → 기준 대수 vs 계획 대수
        landscape.calculate()       → 의무면적 vs 실제 제공
        land_use_act.calculate()    → LURIS + EUM 행위제한 교차검증
        urban_facility.calculate()  → 도시계획시설 저촉 여부
        fire_safety.calculate()     → Claude AI 정성 판단 (11개 항목)

      [추가 정보 카드 6개 — 가중치 0]
        public_certification, bf_certification, crime_prevention
        multi_use, zone_overlap, railway_protection

      [건축협정 사후 보정]
        building_agreement.apply_*() — 건폐율·용적률·조경·높이 재계산

      [심의 자동 트리거]
        review_triggers.evaluate_reviews() — 8종 심의 필요 여부

      [신호 판정]
        pass=False 있음 → RED
        pass=None 있거나 종합점수 < 7.0 → YELLOW
        모두 통과 + 점수 ≥ 7.0 → GREEN

      [이력 저장]
        cache_manager.save_history(address, pnu, req, result)

  → JSON 응답: { results: {8개 카테고리}, overall_score, signal, risks, warnings, data_quality }
```

### 단계 3 — 결과 표시

```
DiagnoseResult 컴포넌트:
  • 8개 카테고리 카드 (PASS ✓ / FAIL ✗ / 확인필요 ?)
  • 종합 점수 + GREEN/YELLOW/RED 신호
  • 심의 자동 트리거 목록
  • DataQualityBanner (VWorld 미조회·stale 캐시·조례 미적용 경고)
  • LawChangeAlert (조례 변경·행정 고시)
  • LawInfoPanel (법령 본문 펼쳐보기 — lazy)
  • DevTrendPanel (주변 개발 동향)
  • CaseReference (사내 유사 케이스)
  • WhatIfPanel (슬라이더 조정)
  • LegalReviewReport + 시니어 검토 요청 버튼
```

### 단계 4 — What-if 시뮬레이션

```
WhatIfPanel 슬라이더 조정 (±50% 범위)
  → 300ms debounce
  → POST /api/diagnose/whatif
    → land_use_resolver (PNU 캐시 히트 — VWorld 재호출 없음)
    → diagnose_engine.diagnose_fast(payload, skip_ai=True, cached_fire_safety=...)
      • 설비·소방 카드: cached_fire_safety 재사용 (Claude API 호출 생략)
      • 나머지 7개 계산기: 새 슬라이더 값으로 재계산
  → 비교 매트릭스 표시 (원본 → 변경, 카테고리별 점수·pass 변화)
```

### 단계 5 — 자연어 질의 (선택)

```
QueryBox에 질문 입력
  → POST /api/query { question, context: 현재 진단 결과 }
    → query_engine.answer()
      → _build_context(): 주소·용도지역·결과 요약 + 위험 항목
      → llm_client.complete(system_prompt, user_message)
        → Anthropic Claude API (prompt caching 활성화)
      → 조문 URL 자동 인용
  → 응답 텍스트 + 신뢰도(high/medium/low) 표시
```

---

## 현재 한계 / 미완성 부분

### 미구현 기능

| 항목 | 현황 | 이유 |
|---|---|---|
| 지능형건축물(smart_building) 용적률 완화율 | `far_relief_rules.json`에서 `by_grade: {}` 빈 값 | 건축물 에너지절약설계기준 별표9에 항목 없음. 별도 고시 원문 필요 |
| 장수명주택(long_life_housing) 완화율 | 동일하게 `by_grade: {}` 빈 값 | 주택건설기준규정 §65의2 원문 대조 미완료 |
| 폐기물매립시설 설치제한 좌표 판정 | `zone_overlap.py`에서 키워드 매칭만 | 좌표 기반 저촉 판정용 공간 데이터 없음 |
| 도로폭 자동 조회 | VWorld 레이어에 도로폭 속성 없어 수동 입력 필요 | 인프라는 완성, 데이터 소스 없음 |

### 외부 API 장애 (코드 문제 아님)

| 항목 | 현황 | 조치 |
|---|---|---|
| 토지이음 `iuLawInfo` (3.3) | 404 응답 | LawInfoPanel 빈 결과. 사용자가 EUM에 직접 문의 필요 |
| 토지이음 `sDevList` (3.8) | 404 응답 | DevTrendPanel 빈 결과. 동일 |

### 데이터 한계

- **조례 기준 대부분 지자체 조례 위임**: `landscape_standards.json`의 by_zone 수치가 제거되어, 조경 한도를 자치구 조례에서 조회 실패 시 `pass=None, confidence=2`("지자체 조례 확인 필요") 처리. 정확한 수치는 해당 구청 조례 직접 확인 필요.
- **사내 케이스 DB**: `KUNWON_DB/cases/sample_cases.json`에 6건의 더미 데이터만 있음. 실제 인허가 프로젝트 데이터로 교체가 필요하나 수작업.
- **도시계획시설 SHP**: 환경변수 `SHP_ROOT`로 로컬 경로 지정. 미설정 시 도시계획시설 카테고리 전체 `pass=None`.

### 신뢰도 자동 저하 조건

다음 조건에서 해당 카테고리가 `pass=None`, `confidence=1~2`로 처리됨:
- 용도지역 표준명 매칭 실패 (19종 + 61개 별칭 모두 불일치)
- LURIS + 토지이음 행위제한 결과 불일치
- 조례 수치 추출 실패 (regex + LLM 모두 실패)
- 높이 판단 시 `north_setback_m` 또는 인접 용도지역 미입력
- 주차 산정 시 `count_based` 용도이지만 정원·홀 수 미입력

### 배포 환경 주의

- **SQLite ephemeral**: GCP Cloud Run은 컨테이너 재시작 시 `./data/arch_law.db` 초기화됨. 캐시가 날아가며 조례는 다시 seed 적재됨. 중요한 데이터(케이스 DB 등)는 컨테이너 외부 저장소 필요.
- **설비·소방 AI 응답 시간**: Claude API 첫 호출 약 3~8초. 진단 전체 응답 시간에 직결.
- **VWorld/LURIS 한도**: LURIS 1,000회/일 한도. 캐시 90일 TTL로 보완 중이나 대량 조회 시 초과 가능.

---

*자동 진단 결과는 참고용. 실제 인허가 책임은 시니어 건축사·설계자에게.*
