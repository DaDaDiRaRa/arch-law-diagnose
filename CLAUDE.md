# arch-law-diagnose

건축 법규 자동 진단 시스템 — 사내 전용. 주소 + 건물 정보를 입력받아 8개 카테고리를 자동 검토하고 GREEN/YELLOW/RED 신호와 종합 점수를 반환.

---

## ⏭️ 다음 작업 (즉시 진행)

**큰 데이터·시크릿을 공유 폴더로 옮기는 작업의 마무리 — 회사 PC 셋업 + 동작 검증**

### 집 PC 진행 상태 (2026-05-18 기준)
- ✅ `D:\arch-law-shared\` 폴더 트리 생성 (`data/`, `files/3/`, `cases/`, `backups/`, `lock/`, `docs/` + `README.md`)
- ✅ 기존 데이터 D 드라이브로 이동 완료
  - `files/3/` SHP 데이터 ~2.5GB (836 파일, robocopy /MOVE)
  - `.env` API 키 8종
  - `KUNWON_DB/cases/sample_cases.json`
- ✅ junction 4개 생성 완료 (`files\3`, `data`, `KUNWON_DB\cases`, `.env` → D 드라이브)
- ⏸️ **동작 테스트 미실시** — `start-servers.bat` 으로 백엔드·프론트 정상 부팅 + 진단 한 건 돌려서 D 드라이브 데이터 읽기 확인 필요
- ⏸️ `data/arch_law.db` 는 아직 없음 — 첫 진단 시 `D:\arch-law-shared\data\` 에 자동 생성될 예정

### 다음에 회사 PC 에서 해야 할 일
1. **회사 클라우드 종류 먼저 확인** — OneDrive 비즈니스(✅ 안전) / SharePoint(❌ 위험) / SMB 네트워크 드라이브(⚠️ 위험) 등. `SETUP.md` 의 "⚠️ 시작 전 반드시 확인" 표 참조. **위험 등급이면 DB 만 로컬에 두는 하이브리드 전략으로 변경 필요**
2. **공유 폴더 경로 결정** — 집은 `D:\arch-law-shared\` 이지만 회사 PC 는 다른 경로 가능 (예: `C:\Users\...\OneDrive - 회사명\arch-law-shared\`). junction 만 회사 PC 경로 기준으로 다시 만들면 됨, 코드 수정 0
3. **`SETUP.md` 의 "셋업 — 다른 PC" 절차 따라 진행**
   - `git clone`
   - 회사 클라우드 동기화 완료 대기 (또는 외장 SSD 로 데이터 옮기기)
   - 관리자 권한 cmd 에서 `mklink` 4개 실행 (회사 PC 경로 기준)
   - `pip install -r requirements.txt` + `npm install` (의존성은 PC 마다 재생성이 정상)
   - `start-servers.bat` 동작 테스트
4. **양쪽 PC 데이터 동기화 방식 최종 결정** — 클라우드 자동 동기화? 외장 SSD 휴대? DB 만 별도 동기화?

### 별도 발견 이슈 (해결됨)
- ✅ ~~[backend/services/urban_facility/indexer.py:19](backend/services/urban_facility/indexer.py#L19) 의 `SHP_ROOT = .../files/3/shp/` 가 실제 데이터 위치(`files/3/KLIP_003_*` 직접) 와 불일치~~ → **2026-05-18 해결**. `D:\arch-law-shared\files\3\` 안에 `shp/` 서브폴더 만들고 KLIP/UPIS 폴더 전부 그 안으로 이동 완료. 코드가 기대하는 구조와 일치. 동작 테스트 시 도시계획시설 카드(B1·B7) 정상 출력 확인 거리.

### 참고 파일
- [SETUP.md](SETUP.md) — 공유 폴더 전략 전체 가이드 (트리·junction·운영 규칙·체크리스트)
- [D:\arch-law-shared\README.md](D:\arch-law-shared\README.md) — 공유 폴더 운영 규칙 (락·백업 등)

---

## 기술 스택

- **Backend**: FastAPI (Python 3.12), SQLite, port 8000
- **Frontend**: React + Vite + Tailwind, port 5173
- **DB**: `./data/arch_law.db` (CacheManager 관리)
- **AI**: Anthropic Claude (설비·소방 정성 판단 + 자연어 질의)

---

## 외부 API (.env 키)

| 서비스 | 환경변수 | 용도 |
|---|---|---|
| Anthropic Claude | `ANTHROPIC_API_KEY` (필수), `ANTHROPIC_MODEL`(선택) | 설비·소방 정성 판단·자연어 질의·조례 본문 수치 추출 |
| 법제처 DRF | `LAW_API_KEY` | 조례 본문 수집(`seed_municipal_ordinances`), 시도/시군구 조례 변경 감지 |
| VWorld | `VWORLD_API_KEY` | 좌표 변환·용도지역·지적도·도로폭·지적 폴리곤(WFS) |
| Kakao Local | `KAKAO_API_KEY` | 주소 자동완성 (AddressSearch) |
| 토지이음 (EUM) | `EUM_ID`, `EUM_KEY` | 법령정보(Phase 1)·행정 고시(Phase 2)·개발 인허가(Phase 3)·행위제한 교차검증 |
| 행안부 도로명주소 | `JUSO_API_KEY` | 주소 검색 폴백·정규화 |
| 공공데이터포털 (선택) | `DATA_GO_KR_API_KEY` (또는 legacy `LURIS_API_KEY`) | LURIS 행위제한 (토지이음과 교차검증) |
| Slack (선택) | `SLACK_WEBHOOK_URL` | 시니어 검토 요청 webhook (미설정 시 로컬 로그) |

설정 파일: `DB_PATH`, `CACHE_TTL_DAYS`, `LOG_LEVEL`, `CASE_DB_PATH`, `REVIEW_LOG_PATH`, `ENABLE_LAW_CHANGE_CRON`, `LAW_CHANGE_CRON` — 자세한 설명은 `.env.example` 참조.

시작 시 `main.py` 가 핵심 API 활성 상태를 ✅/❌ 로깅. 누락된 API는 graceful degrade — 해당 항목만 "확인필요(YELLOW)" 처리.

`.env` 는 gitignore 됨. 새로 셋업할 때는 `.env.example` 복사 후 키만 채우기.

---

## 진단 8개 카테고리

| 코드 | 계산기 | 출처 |
|---|---|---|
| 행위제한 | `land_use_act.py` | LURIS API |
| 도시계획시설 | `urban_facility.py` | VWorld 지적도 ∩ 시설 SHP |
| 건폐율 | `coverage.py` | 조례 우선 → 시행령 (zone_limits.json) |
| 용적률 | `far.py` | 동일 + 4종 완화 (녹색·에너지·지능형·장수명) |
| 높이·일조 | `height.py` | §60·§61 자동 판정 (정북 이격거리 입력 시) |
| 주차 | `parking.py` | 주차장법 시행령 |
| 조경 | `landscape.py` | 건축법 §42 + 시행령 §27 |
| 설비·소방 | `fire_safety.py` | Claude AI 정성 판단 |

---

## 신호 판정 로직

- **RED**: `pass=False` 항목 존재
- **YELLOW**: `pass=None` 항목 존재 OR 종합점수 < 7.0
- **GREEN**: 모든 항목 통과 + 종합점수 ≥ 7.0

종합점수 — 가중평균 0~10. 가중치는 `backend/config/law_scoring_weights.json`.

---

## 핵심 설계 원칙

### 정확도
- **용도지역 정규화 필수** — `services/zone_use_normalizer.py` 의 `normalize()`/`category_of()` 통과한 표준명만 사용. 부분매칭 금지 ("주거지역"이 "준주거지역"으로 잘못 매칭되는 버그 방지). 매칭 실패 시 None → "확인필요"
- **AI 단독 판정 금지** — 결정론적 룰로 처리할 수 있는 건 코드로. LLM은 정성 영역(설비·소방) 또는 보조 의견만. 환각으로 가짜 판례 인용 위험.
- **부분 매칭 제거됨** — `coverage._get_limit`, `far._get_limit`, `multi_parcel._get_zone_limit`, `diagnose_engine._get_default_far_limit`, `landscape._required_ratio` 모두 정규화기 사용

### 신뢰성
- **모든 진단 응답에 `data_quality` 필드** — 어떤 API가 사용됐는지, fallback인지, stale 캐시인지 명시. 프론트의 `DataQualityBanner` 가 사용자에게 표시.
- **Stale 캐시 fallback** — `land_use_resolver.py` 에서 VWorld 재조회 실패 시 stale 캐시 사용 (빈 결과보다 낫다는 원칙)
- **조례 seed DB** — `config/ordinance_seed.json` 의 서울특별시 도시계획조례 §54·§55 값을 시작 시 idempotent 적재. API 장애 시에도 안정적.

### 편의성
- **자동 채움** — 주소 선택 시 토지이용계획(VWorld) 자동 조회 → 용도지역/지역지구/도로폭 자동 입력
- **수동 입력 우선** — 사용자가 입력한 값은 항상 자동 조회값보다 우선

---

## 주요 서비스 파일 (backend/services/)

| 파일 | 상태 | 역할 |
|---|---|---|
| `diagnose_engine.py` | ✅ | 진단 전체 오케스트레이션 |
| `zone_use_normalizer.py` | ✅ | 용도지역 표준명 정규화 (19종 + 별칭 61개) |
| `eum_client.py` | ✅ | 토지이음 7개 API (법령·고시·행위제한·개발인허가) |
| `vworld_client.py` | ⚠️ 검증 필요 | VWorld WFS 지적 폴리곤 + 지오코딩 (Phase 5 신규) |
| `ordinance_resolver.py` | ✅ | 조례 cascade 조회 (캐시 → API → LLM fallback). `needs_review=True` 레코드(잘못 추출된 0% 등)는 자동 skip → 시행령 fallback 사용 (안전장치) |
| `ordinance_extractor.py` | ✅ | 법령 본문 → 건폐율/용적률 수치 추출 (regex + LLM) |
| `luris_client.py` | ✅ | LURIS 행위제한정보서비스 |
| `land_use_resolver.py` | ✅ | 토지 정보 조회 + stale 캐시 fallback |
| `far_relief.py` | ✅ | 용적률 완화 4종 (녹색·에너지·지능형·장수명). 근거: 녹색건축물법 §15 + 동법 시행령 §11. 인증 합산 캡 15%, 전체 캡 1.15배 (이전 1.2배는 오류 — 수정 완료) |
| `building_agreement.py` | ✅ | 건축협정 §110의7 완화 사후 보정 — 건폐율 1.2배(§84 캡), 용적률 1.2배(§85 캡), 조경 0.8배(도로면 통합 조성 조건), 높이 1.2배(6m 이상 도로 조건) |
| `multi_parcel.py` | ✅ | 합필 진단 (면적 안분 + 소규모 예외) |
| `review_triggers.py` | ✅ | 심의 자동 트리거 8종 |
| `law_change_tracker.py` | ⚠️ | 법규 변경 감지 (수동 호출만, Cron 미연결) |
| `cache_manager.py` | ✅ | SQLite Lazy Cache (조례 30일 TTL + 진단 이력) |
| `llm_client.py` | ✅ | Claude API (temp=0, prompt caching) |
| `query_engine.py` | ⚠️ | 자연어 질의 (기본 구현, 조문 자동 인용 미완) |

## 주요 프론트엔드 컴포넌트 (frontend/src/components/)

| 컴포넌트 | 상태 | 역할 |
|---|---|---|
| `InputForm/` | ✅ | 전체 입력 폼 (모든 필드 + validation) |
| `DiagnoseResult/` | ✅ | 8개 카테고리 진단 카드 |
| `LegalReviewReport/` | ✅ | Phase 4 종합 검토 보고서 |
| `DataQualityBanner/` | ✅ | 데이터 출처·fallback 여부 경고 표시 (Phase 5 신규) |
| `LawInfoPanel/` | ✅ | 토지이음 법령 조문 펼쳐보기 (Phase 1) |
| `DevTrendPanel/` | ✅ | 주변 개발 인허가 동향 — 토지이음 sDevList 최근 N일 집계, 기간 토글(7/14/30일) (Phase 3) |
| `QueryBox/` | ✅ | 자연어 질의 입력/응답 |
| `CaseReference/` | ✅ | 사내 유사 케이스 추천 |
| `LawChangeAlert/` | ✅ | 법규 변경 + 행정 고시 통합 배너. 법제처 조례 해시 변경(orange) + 토지이음 행정 고시 최근 90일(blue) 2섹션. (Phase 2 통합) |
| `WhatIfPanel/` | ✅ | What-if 시나리오 — 5개 슬라이더(건축면적·연면적·높이·층수·주차) + 비교 매트릭스. `ErrorBoundary` 격리. |
| `AddressSearch/` | ✅ | 카카오 주소 자동완성 |
| `ReviewRequestButton/` | ✅ | 시니어 검토 요청 (Slack 연동) |

---

## 진행 중 / 보류 작업

### Phase 0~3 — 토지이음 5개 API 통합

| Phase | 내용 | 상태 |
|---|---|---|
| Phase 0 | `EumClient` 신설 (7개 메서드 + XML 파싱) | ✅ 완료 (`eum_client.py` 405줄) |
| Phase 1 | 법령정보 → 진단 카드에 조문 본문 펼쳐보기 | ✅ 완료 — `/api/eum/law_info` 엔드포인트·`LawInfoPanel` 컴포넌트·`DiagnoseResult` 삽입 모두 완성. 토지이음 API lazy-fetch (클릭 시), UCODE별 조문 계층(조/항/호/목) 표시. |
| Phase 2 | 고시정보 → 진단 결과 상단 배너 통합 | ✅ 완료 — `/api/eum/notices` 엔드포인트 신설. `LawChangeAlert` 이 진단 시 areaCd(=PNU 5자리)로 토지이음 행정 고시 최근 90일을 자동 조회. 법제처 조례 본문 해시 변경(orange)와 토지이음 행정 고시(blue) 2섹션으로 분리 표시. |
| Phase 3 | 개발행위허가정보 → 주변 개발 동향 섹션 | ✅ 완료 — `/api/eum/dev_permits` 엔드포인트(최근 N일 병렬 집계, default 14일). `DevTrendPanel/` 신규 컴포넌트 lazy-fetch. 기간 토글(7/14/30일), 알려진 필드(인허가 유형·위치·면적·신청인·날짜) 자동 인식 + 미상 필드는 raw 펼침. `DiagnoseResult` 우측 패널 `LawInfoPanel` 하단에 마운트. |

- 쉬운규제안내서: API 통합 안 함, 참고 자료로 활용

### 남은 주요 작업

- **조례 DB 확충** — ✅ 완료. [backend/scripts/seed_municipal_ordinances.py](backend/scripts/seed_municipal_ordinances.py) 전국 일괄 실행 → 법제처 자치법규 API + LLM 추출 → **7,772 레코드 / 192개 지자체** 적재. 시군구는 시 단위만 fetch 하고 자치구는 broadcast. `ordinance_extractor.py` sanity check 실패값(중심상업 0% 등)은 `needs_review=True` 로 표시되며, `ordinance_resolver.py` 가 자동 skip → 시행령 fallback. 시군구 200곳 더 깊은 수집(군계획·관리계획)은 차후 보강.
- **진단 엔진 ↔ EUM 직통 연결** — ✅ 완료. [land_use_act.py](backend/services/calculator/land_use_act.py) 가 LURIS + EUM `get_act_restriction()` 을 병렬 조회 후 머지. 일치(confidence 5 / "교차검증"), 단일소스(confidence 4-5), 불일치(pass=None, confidence 2 / "❗ 불일치"), 둘 다 미수록(confidence 1). 캐시: [cache_manager.py](backend/services/cache_manager.py) `eum_act_restriction_cache` 테이블.
- **조경 → 조례 리졸버 연동** — ✅ 완료. [landscape.py](backend/services/calculator/landscape.py) 가 `ordinance_resolver` 의 `landscape_ratio` 카테고리 우선 적용. [ordinance_seed.json](backend/config/ordinance_seed.json) 에 17개 시도 평균 추정값 적재. 시행령 §27 ②항 4호(200~300㎡=10%) 와 ①항 면제는 시행령 우선 (조례 변경 불가). **옥상조경 §27 ③항 추가 완료** — `rooftop_landscape_area` 파라미터 추가, 옥상면적×2/3 인정 (의무면적 50% 상한 캡). `rooftop_landscape_area_m2`·`rooftop_credit_m2` 필드 결과에 포함.
- **높이 §60 데이터 소스** — ✅ 인프라 구축 완료. `street_block_max_heights` 테이블(bbox + max_height_m + source) + [config/street_block_heights.json](backend/config/street_block_heights.json) seed JSON + idempotent loader. 진단 시 좌표 bbox 매칭으로 자동 적용, 사용자 입력(`street_block_max_height_m`) 우선. 데이터 채우기는 운영자가 자주 진단하는 구역부터 JSON에 추가하는 방식 — 시드 빈 상태로 시작. 정북 사선(§86 ①항) 공식 버그 수정 완료 — 이전에 `max(1.5, 높이/2)` 단일 식이었으나, §86 ①항 1호(≤10m 부분 → 1.5m 고정) / 2호(>10m 부분 → 높이/2)로 분기 수정. `shadow_setback_rule` 필드 추가.
- **특별 완화 토글** — ✅ 완료. `InputForm/` 에 2개 details 섹션 추가:
  - `🤝 건축협정` — `building_agreement` 체크박스 + `agreement_landscape_road_facing` 체크박스. 엔진에서 모든 계산기 실행 후 `building_agreement.py` 의 `apply_to_*` 로 사후 보정.
  - `📋 특별 지구·인증 특례` — `rema_zone`(재정비촉진지구 §19), `easy_remodel`(리모델링이 쉬운 구조 §6의5, 공동주택 한정), `public_rental`(공공지원민간임대 §21). 계산기 실행 전 `cov_limit`/`far_limit` 보정.
- **What-if 슬라이더** — ✅ 완료. `WhatIfPanel/index.jsx` 5개 슬라이더(건축면적·지상연면적·높이·층수·주차수) + 300ms debounce + 원본↔변경 비교 매트릭스. `DiagnoseResult` 좌측 패널(종합 판정 바로 아래)에 마운트. `ErrorBoundary` 격리 적용. 설비·소방 카드는 `cached_fire_safety` 재사용으로 AI 호출 생략.
- **법규 변경 Cron 자동화** — ✅ 완료. [law_change_scheduler.py](backend/services/law_change_scheduler.py) APScheduler 기반. 매주 일요일 03:00 KST 17개 시도 도시계획조례 일괄 스캔, 해시 변경 시 `ordinance_versions` 누적 → 프론트 `LawChangeAlert` 자동 표시. 환경변수 `ENABLE_LAW_CHANGE_CRON` / `LAW_CHANGE_CRON` 으로 ON/OFF·주기 변경, `POST /api/law/scan_now` 즉시 트리거, `GET /api/law/scheduler_status` 다음 실행 시각 조회. 시군구 200곳 스캔은 차후 보강 (군계획·관리계획 등 매칭 로직 재사용 필요).
- **VWorld 폴리곤 성능 검증** — ✅ 완료. 작은 도심 필지~큰 산림 필지(vertex 800개+) 모두 단일 호출 50ms 이내. 합필 시뮬레이션(5개 필지 × VWorld 4건 = 총 20건 동시) 0.5초 이내. 현재 `timeout=15초` 충분, 진단 흐름의 병목 아님. 별개로 도로폭(`LT_L_FRSTCRCL` 레이어 ERROR)은 알려진 데이터 소스 이슈 — 보류 항목으로 별도 처리.
- **사내 케이스 DB** — `KUNWON_DB/cases/sample_cases.json` 더미만 있음. 실제 프로젝트 케이스 수작업 입력 필요 (코드 작업 아님).

### 보류
- **도로폭 자동 조회** (5.3) — VWorld `lt_l_sprd` 레이어가 도로명만 반환 (폭 속성 없음). `lt_l_moctlink` 도 NOT_FOUND. 인프라(코드/DB 컬럼/UI)는 구축 완료, 데이터 소스만 보류 상태. 토지이음 API 도입 후 재검토.

---

## 자주 하는 작업

### 서버 시작
```
start-servers.bat
```
- 백엔드(`uvicorn --reload`) + 프론트엔드(`npm run dev`) 별도 cmd창에서 시작
- `--reload` 옵션 있어서 backend `.py` 수정 시 자동 재시작
- `.env` 변경은 자동 감지 안 함 → 수동 재시작

### 백엔드만 수동 재시작
```
cd backend
.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 캐시 초기화 (특정 PNU)
SQLite 직접 조작:
```sql
DELETE FROM land_info_cache WHERE pnu='...';
```
또는 전체 재시작은 `./data/arch_law.db` 삭제 — `ordinance_seed.json` 17개 시도는 자동 재적재되지만, 시군구 7,772건은 `python -m scripts.seed_municipal_ordinances --commit` 재실행 필요(~수 분 소요, 법제처 API + LLM 호출).

---

## 디버깅 팁

### LLM JSON 파싱
- `llm_client._extract_json()` 가 3단계 자동 복구 (strict → 콤마 보정 → truncation 절단)
- 복구 성공 시 INFO 로그 (`자동 복구 성공`)
- 모두 실패 시 WARNING 에 에러 위치 앞뒤 100자 컨텍스트 출력

### VWorld 응답 디버깅
- 도로폭 호출 시 `[VWorld 도로 응답 샘플] 첫 feature properties = {...}` 로그로 응답 구조 확인 가능
- `vworld_client.py` 의 WFS 폴리곤 조회는 `VWORLD_API_KEY` 필요. 응답이 빈 feature list 이면 레이어명 오타 or 좌표계 확인.

### 토지이음 API 디버깅
- `EumClient` 는 `EUM_ID` + `EUM_KEY` 필요. 인증 실패 시 XML `<errMsg>` 반환 → 로그에 그대로 출력됨.
- `/api/eum/health` 로 연결 상태 확인 가능.

### 브라우저 캐시
- `frontend/src/utils/api.js` 에 `cache: 'no-store'` 적용됨
- 백엔드 `/api/address/search` 응답에도 `Cache-Control: no-store` 헤더
- 그래도 문제 시 Ctrl+Shift+R (강력 새로고침)

---

## 코딩 컨벤션 (이 프로젝트)

### 작업 방식 (LLM 코딩 원칙)

- **가정 먼저 드러내기** — 요구사항이 모호하면 추측으로 진행 금지. 어떤 가정을 했는지 명시하고, 해석이 갈리면 골라서 질문. 특히 법규·조례 해석 영역에서는 무단 해석 금지 (환각으로 가짜 조문 인용 위험)
- **단순함 우선** — 요청 범위 밖의 기능·추상화 추가 금지. 단일 호출용 코드에 "유연성/설정값" 미리 빼두지 않기. 일어날 수 없는 시나리오에 대한 방어 코드 금지 (실제 발생 가능한 API 실패는 graceful degrade 로 별도 처리)
- **외과적 수정** — 요청된 부분만 수정. 주변 코드 정리·포맷팅·"개선" 금지. 기존 스타일이 본인 취향과 달라도 따라가기. 무관한 dead code 발견 시 삭제 말고 사용자에게 보고만. 단, 본인 수정으로 안 쓰이게 된 import/변수/함수는 함께 정리
- **검증 가능한 완료 기준** — 작업 시작 전 "끝났다"의 정의 명시. 다단계 작업은 단계별 확인 항목 포함 (예: 진단 응답 필드 추가 → 계산기 반환값 + `cache_manager` 스키마 + 프론트 표시까지 모두 확인)

### 사용자 커뮤니케이션

- **내부 사고는 전문적으로, 사용자에게는 쉽게** — 코드/설계/법규는 정확하게 다루되, 사용자에게 보고할 때는 전문 용어를 풀어서 설명. 예: "confidence를 4로 낮춘다" → "이 값은 추정값이라 신뢰도를 한 단계 낮춰서 표시". 어쩔 수 없이 기술 용어가 필요하면 한 줄로 풀이를 곁들이기.
- **결과 요약은 ① 무엇이 바뀌었는지 ② 사용자가 실제 어떻게 보게 되는지 순서로** — 파일/메서드/스키마 나열보다 "이제 진단할 때 ~게 보입니다" 식이 우선.

### 프로젝트 규칙

- **새 zone_use 매칭 로직 작성 금지** — 무조건 `services.zone_use_normalizer` 사용
- **LLM 응답 파싱은 `llm_client.judge_json()` 거치기** — 자동 복구 파이프라인 통과
- **API 키 누락은 graceful degrade** — `if not self._key: return None` 패턴, 예외 던지지 않음
- **진단 결과 응답에 새 필드 추가 시** — `cache_manager` 의 land_info_cache 스키마도 함께 ALTER (구버전 DB 호환)
- **로그는 한국어** — 사용자/운영자가 직접 읽음

---

## 참고 자료 (앱 외부)

- 토지이음 쉬운규제안내서 API (`OP/ebGuideBookList`) — **API 통합은 안 함**. 사용자가 어려운 법규 검토할 때, 또는 개발자가 신규 기능 만들 때 참고용으로 호출.

---

## 면책

자동 진단 결과는 **참고용**. 실제 인허가 책임은 시니어 건축사/설계자에게. 모든 진단서 푸터와 LegalReviewReport 에 면책 문구 표시.
