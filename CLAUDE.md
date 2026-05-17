# arch-law-diagnose

건축 법규 자동 진단 시스템 — 사내 전용. 주소 + 건물 정보를 입력받아 8개 카테고리를 자동 검토하고 GREEN/YELLOW/RED 신호와 종합 점수를 반환.

---

## 기술 스택

- **Backend**: FastAPI (Python 3.12), SQLite, port 8000
- **Frontend**: React + Vite + Tailwind, port 5173
- **DB**: `./data/arch_law.db` (CacheManager 관리)
- **AI**: Anthropic Claude (설비·소방 정성 판단 + 자연어 질의)

---

## 외부 API (.env 키 5종)

| 서비스 | 환경변수 | 용도 |
|---|---|---|
| VWorld | `VWORLD_API_KEY` | 좌표 변환·용도지역·지적도·도로폭·지적 폴리곤 |
| Kakao Local | `KAKAO_API_KEY` | 주소 자동완성 |
| 공공데이터포털 | `LURIS_API_KEY` 또는 `DATA_GO_KR_API_KEY` | LURIS 행위제한 (legacy) |
| 토지이음 | `EUM_ID`, `EUM_KEY` | 법령정보·고시·개발인허가·행위제한 (`eum_client.py` 완성, 진단 엔진 직통 연결은 미완) |
| Anthropic | `ANTHROPIC_API_KEY` | Claude API |
| Slack (선택) | `SLACK_WEBHOOK_URL` | 시니어 검토 요청 |

시작 시 `main.py` 가 5개 API 활성 상태를 ✅/❌ 로깅. 누락된 API는 graceful degrade — 해당 항목만 "확인필요(YELLOW)" 처리.

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
| `ordinance_resolver.py` | ✅ | 조례 cascade 조회 (캐시 → API → LLM fallback) |
| `ordinance_extractor.py` | ✅ | 법령 본문 → 건폐율/용적률 수치 추출 (regex + LLM) |
| `luris_client.py` | ✅ | LURIS 행위제한정보서비스 |
| `land_use_resolver.py` | ✅ | 토지 정보 조회 + stale 캐시 fallback |
| `far_relief.py` | ✅ | 용적률 완화 4종 (녹색·에너지·지능형·장수명) |
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
| `LawInfoPanel/` | ✅ | 토지이음 법령 조문 펼쳐보기 (Phase 5 신규) |
| `QueryBox/` | ✅ | 자연어 질의 입력/응답 |
| `CaseReference/` | ✅ | 사내 유사 케이스 추천 |
| `LawChangeAlert/` | ✅ | 법규 변경 알림 배너 |
| `AddressSearch/` | ✅ | 카카오 주소 자동완성 |
| `ReviewRequestButton/` | ✅ | 시니어 검토 요청 (Slack 연동) |

---

## 진행 중 / 보류 작업

### Phase 0~3 — 토지이음 5개 API 통합

| Phase | 내용 | 상태 |
|---|---|---|
| Phase 0 | `EumClient` 신설 (7개 메서드 + XML 파싱) | ✅ 완료 (`eum_client.py` 405줄) |
| Phase 1 | 법령정보 → 진단 카드에 조문 본문 펼쳐보기 | ⚠️ 부분 완료 — `/api/eum/law_info` 엔드포인트·`LawInfoPanel` 컴포넌트 있음. 진단 카드 자동 삽입은 미구현 |
| Phase 2 | 고시정보 → `law_change_tracker.py` 보강 | ❌ 미시작 — EUM `get_notices()` 구현됨, tracker 연결 안 됨 |
| Phase 3 | 개발행위허가정보 → 주변 개발 동향 섹션 | ❌ 미시작 — EUM `get_dev_permits()` 구현됨, UI 없음 |

- 쉬운규제안내서: API 통합 안 함, 참고 자료로 활용

### 남은 주요 작업

- **조례 DB 확충** (🔴 최우선) — `ordinance_seed.json` 현재 48개, 전국 ~162개 시군구 기준 수천 건 필요. `backend/scripts/seed_ordinances.py` 아직 미실행. 실행 전까지 서울 외 지역은 시행령 기본값(fallback) 사용.
- **진단 엔진 ↔ EUM 직통 연결** — ✅ 완료. [land_use_act.py](backend/services/calculator/land_use_act.py) 가 LURIS + EUM `get_act_restriction()` 을 병렬 조회 후 머지. 일치(confidence 5 / "교차검증"), 단일소스(confidence 4-5), 불일치(pass=None, confidence 2 / "❗ 불일치"), 둘 다 미수록(confidence 1). 캐시: [cache_manager.py](backend/services/cache_manager.py) `eum_act_restriction_cache` 테이블.
- **조경 → 조례 리졸버 연동** — ✅ 완료. [landscape.py](backend/services/calculator/landscape.py) 가 `ordinance_resolver` 의 `landscape_ratio` 카테고리 우선 적용. [ordinance_seed.json](backend/config/ordinance_seed.json) 에 17개 시도 평균 추정값 적재 (시군구 정확값은 (b) 에서). 시행령 §27 ②항 4호(200~300㎡=10%) 와 ①항 면제는 시행령 우선 (조례 변경 불가).
- **높이 §60 데이터 소스** — ✅ 인프라 구축 완료. `street_block_max_heights` 테이블(bbox + max_height_m + source) + [config/street_block_heights.json](backend/config/street_block_heights.json) seed JSON + idempotent loader. 진단 시 좌표 bbox 매칭으로 자동 적용, 사용자 입력(`street_block_max_height_m`) 우선. 데이터 채우기는 운영자가 자주 진단하는 구역부터 JSON에 추가하는 방식 — 시드 빈 상태로 시작. 정북 사선(§86 ①항)은 height.py 자동 판정 (변경 없음).
- **What-if 슬라이더** — 사양엔 있음, 미구현. 변수(연면적·높이·주차수) 조정 → 즉시 재계산 엔드포인트 + 시나리오 비교 매트릭스 UI.
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
또는 전체 재시작은 `./data/arch_law.db` 삭제 (조례 seed 48건은 자동 재적재됨).

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
