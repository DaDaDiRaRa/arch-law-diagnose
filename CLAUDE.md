# arch-law-diagnose

건축 법규 자동 진단 시스템 — 사내 전용. 주소 + 건물 정보를 입력받아 8개 카테고리를 자동 검토하고 GREEN/YELLOW/RED 신호와 종합 점수를 반환.

---

## 🔴 세션 운영 규칙 (반드시 준수)

1. **컴팩트 전 이 파일 먼저 업데이트** — 대화가 압축되면 이전 작업 내용이 사라지므로, 다단계 작업 중 context 압축이 예상되면 CLAUDE.md의 Spec 표와 "다음 작업" 섹션을 먼저 갱신한 뒤 계속 진행한다.
2. **전국 적용 원칙** — 모든 Spec·기능은 특정 대지(영등포구 등)에 종속되지 않고 전국 어느 주소에서나 동작해야 한다. 지구명·조례값 하드코딩 금지, 범용 파싱·조회 로직 사용.

---

## ⏭️ 다음 작업

**2026-05-20 기준 — Step 5a 완료. Step 5b 진행 중 (#13·#14 완료).**

### 🚨 Step 5a: 법령 수치 검증 (최우선 — 현재 코드에 미검증 수치 다수)

기존 코드에 법령 원문을 직접 대조하지 않고 추정값으로 구현된 항목들이 발견됐다.
**작업 방법론**: 각 항목마다 법제처(law.go.kr) 원문 또는 국토부·에너지공단 공식 고시 원문을 직접 열어 수치를 확인한 뒤 수정한다. 모르면 해당 값을 제거하고 `pass=None, confidence=1, notes="법령 원문 확인 필요"` 처리.

**원문 공유 방법**: 아래 "법제처 검색 경로"로 해당 조문 텍스트를 복사 → Claude에 붙여넣기. 한 번에 다 안 해도 되고 항목별로 진행 가능.

| # | 파일 | 문제 | 확인할 법령 원문 | 법제처 검색 경로 | 작업 |
|---|---|---|---|---|---|
| 1 | `far_relief_rules.json` | ✅ **완료 (2026-05-20)** | 건축물의 에너지절약설계기준 국토부 고시 제2025-738호 별표9 원문 대조 완료. 녹색건축: 최우수 6%·우수 3% (기존 9%·6% 오류). ZEB: 1등급 15%~5등급 11%. 시범사업 10% 추가. smart_building·long_life_housing 별표9 미포함 → by_grade 비워둠. | — | — |
| 2 | `public_certification.py` | ✅ **완료 (2026-05-20)** | 별표 2 원문 이미지 직접 확인: 2020→30%, 2022→32%, 2024→34%, 2026→36%, 2028→38%, 2030이후→40%. 기존 추정값과 완전 일치 → "추정값" 표시 제거, 원문 확인 완료로 처리. | — | — |
| 3 | `landscape_standards.json` | ✅ **완료 (2026-05-20)** | §27 ②항 원문 대조: 공장·공항·철도역·200~300㎡만 직접 수치 명시, 나머지는 조례 위임. by_zone 숫자값 전체 제거. landscape.py에서 limit_override·by_use_override 미매칭 시 `pass=None, confidence=2, notes="지자체 조례 확인 필요"` 반환하도록 수정. | — | — |
| 4 | `public_certification.py` | ✅ **완료 (2026-05-20)** | ZEB 의무 대상 용도 frozenset 기반 분류 + 연면적 조건(녹색건축/BEMS 3,000㎡, ZEB 1,000㎡) 분리 구현. 제23호의2(국방·군사) ≠ 제23호(교정) 확인 반영. | — | — |
| 5 | `building_agreement.py` | ✅ **완료 (2026-05-20)** | §110조의7 제1호 원문 확인: "해당 지역에 적용하는 조경 면적기준의 100분의 20의 범위에서 완화" → `_LANDSCAPE_RATIO = 0.80` 정확. 코드 수정 불필요. | — | — |
| 6 | `review_triggers.py` | ✅ **완료 (2026-05-20)** | 연면적 기반 판단 제거. MAYBE 고정 + "학교 경계 200m 이내 토지이음/교육청 직접 확인" 안내로 교체. 제한 가능 용도(숙박·유흥·위락 등) 힌트만 유지. | — | — |
| 7 | `review_triggers.py` | ✅ **완료 (2026-05-20)** | 주석·note에 "법 기준은 개발행위 면적, 입력값(대지면적)으로 대체 판단 중" 명시. triggered_reasons 라벨도 "개발행위 면적"으로 수정. | — | — |
| 8 | `review_triggers.py` | ✅ **완료 (2026-05-20)** | 추정 깊이임을 note·triggered_reasons에 명시. "실제 굴착 깊이로 구조설계 확정 후 재확인" 안내 추가. | — | — |

### 구현 Spec 진행 상황

| Spec | 내용 | 상태 |
|---|---|---|
| Spec 1~8, 10~11 | 공개공지 완화·결정고시·공공인증·BF·범죄예방·가로구역·신재생·철도보호·중첩지구·폐기물매립 | ✅ 코드 완료 (수치 검증은 Step 5a에서) |
| Spec 9 | 조경 기준 고시 반영 (국토부 고시 제2021-1778호, `landscape.py` 보강) | ✅ 완료 (2026-05-20) — 고시 §7조 원문 대조. 용도지역별 교목·관목 최소 수량 자동 계산(상업 0.1/관목 1.0, 공업 0.3/1.0, 주거·녹지 0.2/1.0주 per ㎡). §4조·§5조 체크리스트 notes 추가. `landscape_standards.json`에 planting_rates 추가. |
| #13 | 세부 주차 분류 (`parking.py` + `parking_standards.json` 보강) | ✅ 완료 (2026-05-20) — count_based 타입 추가(골프장·골프연습장·관람장·옥외수영장), 학생용기숙사·데이터센터 신규, 버그 3종 수정 |
| #14 | 다중이용/준다중이용 분리 | ✅ 완료 (2026-05-20) — 시행령 §2-17·17의2 원문 대조. `multi_use.py` 신규, review_triggers 오류(위락시설 위치·16층 플래그) 수정, 진단 카드 추가 |
| #15 | 영향평가 5종 (지하안전 추가, `review_triggers.py`) | ✅ 완료 (2026-05-20) — 건축물 안전영향평가 추가. 시행령 §10조의3 원문 대조: 초고층(50층↑ or 200m↑) or 연면적 10만㎡↑ AND 16층↑. 총 11개 항목 |

### 다음 Step

| Step | 내용 | 추천 모델 |
|---|---|---|
| ~~Step 5a~~ | ✅ 완료 | — |
| **Step 5b** (완료) | ~~#13~~ ✅ · ~~#14~~ ✅ · ~~#15~~ ✅ · ~~Spec 9~~ ✅ · ~~Phase 2(PDF 추출)~~ ✅ | Sonnet 4.6 |

### 사용자가 직접 처리해야 할 항목

1. **토지이음 두 404 엔드포인트 문의** — `iuLawInfo` (3.3) + `sDevList` (3.8). ✉ luris@korea.kr + ☎ 1522-4484 두 곳 각각 연락. 회신 오면 코드 조치 진행.
2. **사내 케이스 DB 실제 데이터 입력** — `KUNWON_DB/cases/sample_cases.json` 6건은 더미. 실제 인허가 프로젝트로 교체 필요 (코드 작업 아님).

### 공유 폴더 전략 (셋업 완료, 2026-05-18)

- **집 PC**: `D:\arch-law-shared\` + junction 4개
- **회사 PC**: SHP(3.8GB) → M 드라이브, 환경변수 `SHP_ROOT` 로 참조. DB·`.env`·케이스 JSON → C 드라이브 로컬
- 자세한 셋업 가이드: [SETUP.md](SETUP.md)

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
| 법제처 DRF | `LAW_API_KEY` | 조례 본문 수집, 조례 변경 감지 |
| VWorld | `VWORLD_API_KEY` | 좌표 변환·용도지역·지적도·도로폭·지적 폴리곤(WFS) |
| Kakao Local | `KAKAO_API_KEY` | 주소 자동완성 |
| 토지이음 (EUM) | `EUM_ID`, `EUM_KEY` | 법령정보·행정 고시·개발 인허가·행위제한 교차검증 |
| 행안부 도로명주소 | `JUSO_API_KEY` | 주소 검색 폴백·정규화 |
| 공공데이터포털 (선택) | `DATA_GO_KR_API_KEY` | LURIS 행위제한 (토지이음과 교차검증) |
| Slack (선택) | `SLACK_WEBHOOK_URL` | 시니어 검토 요청 webhook |

기타 설정: `DB_PATH`, `CACHE_TTL_DAYS`, `LOG_LEVEL`, `ENABLE_LAW_CHANGE_CRON` 등 → `.env.example` 참조.
누락된 API는 graceful degrade — 해당 항목만 "확인필요(YELLOW)" 처리.

---

## 진단 카테고리

### 핵심 8개 (가중치 적용 → 종합점수 반영)

| 코드 | 계산기 | 출처 |
|---|---|---|
| 행위제한 | `land_use_act.py` | LURIS + EUM 교차검증 |
| 도시계획시설 | `urban_facility.py` | VWorld 지적도 ∩ 시설 SHP |
| 건폐율 | `coverage.py` | 조례 우선 → 시행령 (zone_limits.json) |
| 용적률 | `far.py` | 동일 + 4종 완화 (녹색·에너지·지능형·장수명) |
| 높이·일조 | `height.py` | §60·§61 자동 판정 |
| 주차 | `parking.py` | 주차장법 시행령 |
| 조경 | `landscape.py` | 건축법 §42 + 시행령 §27 + 조례 리졸버 |
| 설비·소방 | `fire_safety.py` | Claude AI 정성 판단 |

### 추가 정보 카드 3개 (가중치 0, 정보 표시 전용)

| 코드 | 계산기 | 조건 |
|---|---|---|
| 공공시설_의무인증 | `public_certification.py` | `applicant_type=공공기관` 시 5종 의무 YELLOW 표시 |
| BF_인증 | `bf_certification.py` | 공공기관 또는 의무 용도 시 등급 표시 |
| 범죄예방_건축기준 | `crime_prevention.py` | 대상 용도 시 체크리스트 표시 |

---

## 신호 판정 로직

- **RED**: `pass=False` 항목 존재
- **YELLOW**: `pass=None` 항목 존재 OR 종합점수 < 7.0
- **GREEN**: 모든 항목 통과 + 종합점수 ≥ 7.0

종합점수 — 가중평균 0~10. 가중치는 `backend/config/law_scoring_weights.json`.

---

## 핵심 설계 원칙

### 정확도

- **용도지역 정규화 필수** — `services/zone_use_normalizer.py` 의 `normalize()`/`category_of()` 통과한 표준명만 사용. 부분매칭 금지. 매칭 실패 시 None → "확인필요"
- **AI 단독 판정 금지** — 결정론적 룰로 처리할 수 있는 건 코드로. LLM은 정성 영역(설비·소방) 또는 보조 의견만.

### 신뢰성

- **모든 진단 응답에 `data_quality` 필드** — API 사용 여부·fallback·stale 캐시 명시. 프론트 `DataQualityBanner` 표시.
- **Stale 캐시 fallback** — `land_use_resolver.py` 에서 VWorld 재조회 실패 시 stale 캐시 사용.
- **조례 seed DB** — `config/ordinance_seed.json` 서울 도시계획조례 §54·§55 값 시작 시 idempotent 적재.

### 편의성

- **자동 채움** — 주소 선택 시 VWorld 자동 조회 → 용도지역/지역지구/도로폭 자동 입력
- **수동 입력 우선** — 사용자가 입력한 값은 항상 자동 조회값보다 우선

---

## 주요 서비스 파일 (backend/services/)

| 파일 | 역할 |
|---|---|
| `diagnose_engine.py` | 진단 전체 오케스트레이션 |
| `zone_use_normalizer.py` | 용도지역 표준명 정규화 (19종 + 별칭 61개) |
| `eum_client.py` | 토지이음 7개 API |
| `vworld_client.py` ⚠️ | VWorld WFS 지적 폴리곤 + 지오코딩 (검증 필요) |
| `ordinance_resolver.py` | 조례 cascade 조회. `needs_review=True` 레코드는 자동 skip → 시행령 fallback |
| `ordinance_extractor.py` | 법령 본문 → 건폐율/용적률 수치 추출 (regex + LLM) |
| `land_use_resolver.py` | 토지 정보 조회 + stale 캐시 fallback |
| `far_relief.py` | 용적률 완화 4종. 인증 합산 캡 15%, 전체 캡 1.15배 |
| `building_agreement.py` | 건축협정 §110의7 완화 사후 보정 |
| `multi_parcel.py` | 합필 진단 (면적 안분 + 소규모 예외) |
| `review_triggers.py` | 심의 자동 트리거 9종 |
| `law_change_tracker.py` ⚠️ | 법규 변경 감지 (수동 호출만) |
| `cache_manager.py` | SQLite Lazy Cache (조례 30일 TTL + 진단 이력) |
| `llm_client.py` | Claude API (temp=0, prompt caching) |
| `query_engine.py` ⚠️ | 자연어 질의 (조문 자동 인용 미완) |

## 주요 프론트엔드 컴포넌트 (frontend/src/components/)

| 컴포넌트 | 역할 |
|---|---|
| `InputForm/` | 전체 입력 폼 (건축협정·특별지구 토글 포함) |
| `DiagnoseResult/` | 8개 카테고리 진단 카드 |
| `WhatIfPanel/` | What-if 슬라이더 5개 + 비교 매트릭스 |
| `LawChangeAlert/` | 조례 해시 변경(orange) + 행정 고시(blue) 통합 배너 |
| `LawInfoPanel/` | 토지이음 법령 조문 펼쳐보기 |
| `DevTrendPanel/` | 주변 개발 인허가 동향 (7/14/30일 토글) |
| `DataQualityBanner/` | 데이터 출처·fallback 경고 |
| `LegalReviewReport/` | 종합 검토 보고서 |
| `QueryBox/` | 자연어 질의 |
| `CaseReference/` | 사내 유사 케이스 추천 |

---

## 보류 작업

- **도로폭 자동 조회** — VWorld 레이어에 폭 속성 없음. 인프라 완료, 데이터 소스만 보류. 토지이음 도입 후 재검토.
- **토지이음 `iuLawInfo`·`sDevList` 404** — 코드 문제 아님, 서버 측 장애. `LawInfoPanel`·`DevTrendPanel` 빈 결과, 핵심 8개 카테고리 영향 없음. 사용자가 직접 문의 후 회신 시 처리.
- **사내 케이스 DB** — `KUNWON_DB/cases/sample_cases.json` 더미만 있음. 실제 케이스 수작업 입력 필요.

---

## 자주 하는 작업

### 서버 시작
```
start-servers.bat
```
백엔드(`uvicorn --reload`) + 프론트엔드(`npm run dev`). `.env` 변경은 자동 감지 안 함 → 수동 재시작.

### 백엔드만 수동 재시작
```
cd backend
.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 캐시 초기화

```sql
DELETE FROM land_info_cache WHERE pnu='...';
```
전체 초기화: `./data/arch_law.db` 삭제 후 `python -m scripts.seed_municipal_ordinances --commit` 재실행.

---

## 디버깅 팁

- **LLM JSON 파싱** — `llm_client._extract_json()` 3단계 자동 복구. 실패 시 WARNING에 에러 위치 앞뒤 100자 출력.
- **VWorld 응답** — `[VWorld 도로 응답 샘플]` 로그로 구조 확인. 빈 feature list면 레이어명 오타 or 좌표계 확인.
- **토지이음** — `/api/eum/health` 로 연결 상태 확인. 인증 실패 시 XML `<errMsg>` 로그 출력.
- **브라우저 캐시** — 문제 시 Ctrl+Shift+R. `api.js` 에 `cache: 'no-store'` 적용됨.
- **Windows 포트 8000 충돌** — `netstat -ano | grep ":8000"` 으로 PID 확인 → 관리자 PowerShell에서 `Stop-Process -Id <PID> -Force` 후 재시작.

---

## 코딩 컨벤션

### 작업 방식

- **가정 먼저 드러내기** — 모호하면 추측 금지. 특히 법규·조례 해석은 무단 해석 금지.
- **단순함 우선** — 요청 범위 밖 기능·추상화 추가 금지. 일어날 수 없는 시나리오 방어 코드 금지.
- **외과적 수정** — 요청된 부분만 수정. 무관한 dead code는 삭제 말고 보고만.
- **검증 가능한 완료 기준** — 작업 전 "끝났다"의 정의 명시.

### 사용자 커뮤니케이션

- 사용자에게 보고할 때 전문 용어는 풀어서. 결과 요약은 ① 무엇이 바뀌었는지 ② 사용자가 어떻게 보게 되는지 순서로.

### 프로젝트 규칙

- **새 zone_use 매칭 로직 작성 금지** — 무조건 `services.zone_use_normalizer` 사용
- **LLM 응답 파싱은 `llm_client.judge_json()` 거치기**
- **API 키 누락은 graceful degrade** — `if not self._key: return None` 패턴
- **진단 결과 응답에 새 필드 추가 시** — `cache_manager` 스키마도 함께 ALTER
- **로그는 한국어**

---

## 면책

자동 진단 결과는 **참고용**. 실제 인허가 책임은 시니어 건축사/설계자에게. 모든 진단서 푸터와 LegalReviewReport 에 면책 문구 표시.
