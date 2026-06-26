# arch-law-diagnose

건축 법규 자동 진단 시스템 — 사내 전용. 주소 + 건물 정보를 입력받아 8개 카테고리를 자동 검토하고 GREEN/YELLOW/RED 신호와 종합 점수를 반환.

---

## 🔴 세션 운영 규칙 (반드시 준수)

1. **컴팩트 전 이 파일 먼저 업데이트** — 대화가 압축되면 이전 작업 내용이 사라지므로, 다단계 작업 중 context 압축이 예상되면 CLAUDE.md의 Spec 표와 "다음 작업" 섹션을 먼저 갱신한 뒤 계속 진행한다.
2. **전국 적용 원칙** — 모든 Spec·기능은 특정 대지(영등포구 등)에 종속되지 않고 전국 어느 주소에서나 동작해야 한다. 지구명·조례값 하드코딩 금지, 범용 파싱·조회 로직 사용.

---

## ⏭️ 다음 작업

**2026-06-22 갱신** — 사업성 모드 대폭 확장 완료 + 실서버 e2e 테스트 통과 (커밋 `bfd4d70` 외):

- **A** 제안 우선 화면 (target 없이도 이 대지 최대 건폐율·용적률·연면적·권장주차 제시)
- **B/C/E4** 대안 비교(What-If) — 완화 레버 6종(녹색·제로에너지·시범·건축협정·재정비촉진·리모델링) 실시간 조정 + 비교 매트릭스
- **E1** 공모지침 불러오기 — Competition Analyzer의 `_brief.json`을 `BRIEF_DIR` 폴더(운영=brief 버킷 GCSFUSE 마운트)에서 읽어 target_* 자동 채움 (`brief_importer.py`, `/api/feasibility/briefs*`)
- **E2** 다중 대지 동시 비교 (`/api/feasibility/run-multi`, asyncio 병렬)
- **E3** 사업성 1장 요약 MD/Excel (`feasibility_exporter.py`, `/api/feasibility/export/*`)
- fix: `_build_review_burden`가 applicable_reviews(dict{items}) 구조를 list로 오순회하던 버그

**2026-06-26 갱신** — 코드 점검 fix + 검증 인프라 + Step 8 제거 + Step 9·11 완료:

- 진단 엔진/캐시/클라이언트 **버그 5건 수정** (다필지 gather 예외내성·신호 GREEN오신호·EUM 빈리스트 캐시·VWorld 응답 방어·LLM 타임아웃). 추가로 `get_law_articles(LAW)` 국가법령 본문 파서 버그(자치법규 스키마만 지원하던 것) 수정.
- **pytest 게이트 CI** (`.github/workflows/deploy.yml` test job + `needs: test`, PR에서도 실행) + **회귀 테스트 141건** (계산기 전반·캐시·brief·재시도·법규그래프·far_relief·multi_parcel·review_triggers·height·landscape·building_agreement·feasibility).
- **외부 API 재시도/백오프** (`http_retry.py` — 정부 API GET 14곳 래핑, 전송오류·5xx만 지수백오프 2회. 일시장애로 "확인필요" 떨어지는 것 방지).
- **Step 8 (사내 케이스 DB + harness) 제거** — `case_matcher.py`·`CaseReference/`·`KUNWON_DB/`·`/api/cases/*`·`CaseMatchRequest` 전부 삭제. 더미라 제외 (git 복원 가능).
- **Step 9 brief 연계 완료·검증** — 실샘플 `data/briefs/_brief.json`(영등포 신청사)로 `map_brief()` 검증(주소·용도힌트·완화레버·공공판정 자동). `list_briefs` 성능개선(파일명 정렬·카테고리필터·mtime 캐시) + 프론트 필터/검색 + **다부지→E2 다중비교 연동**(전체 부지 전송 버튼). 소스앱=`competition_comparison`, 버킷=`kunwon-competition-db/_briefs/`(파일명 `{YYYYMMDD}_{HHMMSS}_{카테고리}.json` — `BRIEF_DIR`은 `_briefs/` 하위 지정).
- **Step 11 법규 의미 그래프 완료** — 조문 참조 그래프(`law_graph.py`, networkx, 코드수확 시드 49노드) + API 3종 + 프론트 탐색기 + 카테고리→그래프 점프 + react-flow 캔버스(lazy) + 법제처 자동수확(`law_graph_auto.json`, origin=auto 태깅 자동병합 → 총 138노드).

**보류 (나중에) — 외부 의존 있음**:

- **D** 부대시설·사업성 지표(분양면적·사업비 등 추가 데이터·기준 필요)
- **용도 매핑표** brief 사업유형 ↔ 건축법 19용도 전체표(시니어 회의). ※ 단, brief 괄호표기("(노유자시설)" 등)에서 부분 자동감지는 이미 동작.

*히스토리*: 2026-06-22 사업성 A~E 확장. 2026-06-19 Step 7 (사업성 모드 초판). 2026-05-22 Step 5a·5b·6 (법령 수치 검증·배포 인프라·디자인 토큰).

### 📋 현재 상태 (한 줄 진단)

핵심 계산 엔진은 운영급 완성 (건폐율·용적률·완화 합산·심의 트리거 정확). **막혀있는 건 "데이터"와 "검증 인프라"** — 둘 다 사용자가 외부에서 채워야 할 영역.

| 영역 | 상태 |
| --- | --- |
| 핵심 계산 + 사업성 모드 + UI + PDF/MD/Excel 다운로드 | ✅ 운영급 |
| API 키 6개 (Kakao·VWorld·EUM·LURIS·Claude·법제처) | ✅ 활성 |
| 검증 인프라 (pytest 141건 + CI 게이트) | ✅ 도입 (2026-06-26) — 계산기 전반·캐시·brief·재시도·법규그래프·far_relief·multi_parcel·review_triggers·height·landscape·building_agreement·feasibility |
| brief 연계 (Step 9) | ✅ 동작 (실샘플 `data/briefs/_brief.json`로 매핑 검증) |
| 사내 케이스 DB (Step 8) | 🗑 제거 (더미라 일단 삭제, git 복원 가능) |
| 일부 SHP 누락 (철도 / 시·도별 도시계획시설 일부) | ❌ |

### 🎯 앞으로 할 작업 (로드맵 Step 5~11 소진 — 이후 점증 보강)

> 정규 로드맵(Step 5a~11)은 2026-06-26 전부 완료/제외. 아래는 그 다음 단계.
> Step 8(사내 케이스 DB)·Step 10(계산식 노출)은 사용자 결정으로 제외.

#### 🟢 지금 코드로 가능 (외부 데이터 불필요)

- [ ] **외부 API 클라이언트 테스트 (1순위)** — `respx`/httpx-mock 도입 → vworld·eum·luris·ordinance_extractor 오프라인 모킹. 회귀망 마지막 큰 공백, 정부 API 응답 변형 대응.
- [ ] 소형 계산기 테스트 — public_certification·bf_certification·multi_use·query_engine (커버리지 마무리)
- [ ] 법규 그래프 검증 워크플로 — 시니어가 자동수확(origin=auto) 엣지 검토 → 맞는 것 시드 승격(auto→seed). 재수확: `python -m services.law_graph_harvest`
- [ ] 가로구역 최고높이 seed (현재 0건 → §60 자동판정 거의 안 됨) — 단, 고시 PDF 수집 선행
- [ ] (낮음) markdown lint 일괄 정리 / dev 의존성 `npm audit fix`(vite·babel, 빌드 검증 필요)

#### 🟡 외부 데이터·사용자 대기 (코드는 준비됨)

- [ ] brief 추가 샘플(민간·다부지) → Step 9 매핑 견고화 (공공 1건은 검증됨, 5분 다운로드)
- [ ] 토지이음 두 404 엔드포인트 문의 (✉ luris@korea.kr · ☎ 1522-4484) → LawInfoPanel·DevTrendPanel 활성화
- [ ] 도시계획시설 SHP 영등포구 등 `nsdi.go.kr` 재다운로드 → 시설 저촉 오판정 방지
- [ ] 사내 시설용도 매핑표 (시니어 30분) → brief 용도 완전 자동화

#### 🔵 선택적 신규 (더 큰 투자, 상세는 "확장 후보" 섹션)

- [ ] NSDI API 연동 (SHP 자동 다운로드) — 🔴 높음
- [ ] 학교알리미·문화재 API → `review_triggers` 교육환경·문화재 MAYBE→확정
- [ ] 운영 인프라 — Cloud Logging·Sentry·BigQuery / 실거래가·SGIS(사업성 보강)

#### ✅ 푸시 직후 운영 검증

- [ ] GCP에서 법규 그래프 패널(탐색기/캔버스·카테고리 점프) + brief 불러오기(필터/검색·다부지 E2) 동작 확인
- [ ] 사업성 모드 본격 테스트 (모드 선택 → 갭 분석 → 다부지 비교)

---

### ✅ Step 5a: 법령 수치 검증 (완료 2026-05-20)

추정값으로 구현됐던 8개 항목을 법제처/국토부 고시 원문에 직접 대조해 검증·수정 완료. 핵심:

- `far_relief_rules.json` — 에너지절약설계기준(고시 제2025-738호) 별표9: 녹색건축 최우수 6%·우수 3%(기존 9%/6% 오류 수정), ZEB 1등급 15%~5등급 11%, 시범사업 10%. smart·long_life는 별표9 미포함이라 비워둠.
- `public_certification.py` — 별표2 제로에너지 의무비율(2020 30%→2030↑ 40%) 원문 확인, ZEB 의무 용도 frozenset + 연면적 조건(녹색/BEMS 3,000㎡, ZEB 1,000㎡) 분리.
- `landscape_standards.json` — §27②: 직접 명시 외 by_zone 추정값 전체 제거 → 미매칭 시 `pass=None, confidence=2`(조례 확인 필요).
- `building_agreement.py` — §110의7 1호 "100분의 20 범위 완화" → `_LANDSCAPE_RATIO=0.80` 확정.
- `review_triggers.py` — 교육환경 MAYBE 고정(좌표 필요), 개발행위 면적·굴착깊이 추정 한계를 note·triggered_reasons에 명시.

### 구현 Spec 진행 상황

| Spec | 내용 | 상태 |
|---|---|---|
| Spec 1~8, 10~11 | 공개공지 완화·결정고시·공공인증·BF·범죄예방·가로구역·신재생·철도보호·중첩지구·폐기물매립 | ✅ 코드 완료 (수치 검증은 Step 5a에서) |
| Spec 9 | 조경 기준 고시 반영 (국토부 고시 제2021-1778호, `landscape.py` 보강) | ✅ 완료 (2026-05-20) — 고시 §7조 원문 대조. 용도지역별 교목·관목 최소 수량 자동 계산(상업 0.1/관목 1.0, 공업 0.3/1.0, 주거·녹지 0.2/1.0주 per ㎡). §4조·§5조 체크리스트 notes 추가. `landscape_standards.json`에 planting_rates 추가. |
| #13 | 세부 주차 분류 (`parking.py` + `parking_standards.json` 보강) | ✅ 완료 (2026-05-20) — count_based 타입 추가(골프장·골프연습장·관람장·옥외수영장), 학생용기숙사·데이터센터 신규, 버그 3종 수정 |
| #14 | 다중이용/준다중이용 분리 | ✅ 완료 (2026-05-20) — 시행령 §2-17·17의2 원문 대조. `multi_use.py` 신규, review_triggers 오류(위락시설 위치·16층 플래그) 수정, 진단 카드 추가 |
| #15 | 영향평가 5종 (지하안전 추가, `review_triggers.py`) | ✅ 완료 (2026-05-20) — 건축물 안전영향평가 추가. 시행령 §10조의3 원문 대조: 초고층(50층↑ or 200m↑) or 연면적 10만㎡↑ AND 16층↑. 총 11개 항목 |

### Step 6: 배포 인프라 + 디자인 시스템 (✅ 완료, 2026-05-22)

| 항목 | 내용 | 상태 |
|---|---|---|
| Docker 배포 | 멀티 스테이지 Dockerfile (Node 20 → Python 3.12-slim), .dockerignore, FastAPI SPA serving | ✅ 완료 |
| GCP Cloud Run | 단일 컨테이너 포트 8080, Secret Manager 환경변수, DEPLOY.md 작성 | ✅ 완료 |
| kunwon-tokens.css | CSS 변수 60여 개 선언 (색상·폰트·간격·인쇄 전용 토큰), index.css·tailwind.config.js 연결 | ✅ 완료 |
| 하드코딩 교체 | text-[10px]→font-size-2xs (48건), text-[11px]→font-size-xs (9건), em 단위 (8건), 다크 툴바 hex (7건), w-[580px] (1건) | ✅ 완료 |
| DESIGN_SYSTEM.md | 색상 팔레트·폰트·버튼·레이아웃·컴포넌트 13개 문서화 | ✅ 완료 |
| DEPLOY.md | 배포 방법·오류 6건·해결·체크리스트 문서화 | ✅ 완료 |

### 다음 Step

| Step | 내용 | 상태 |
| --- | --- | --- |
| ~~Step 5a~~ | 법령 수치 검증 (8건 원문 대조) | ✅ 완료 (2026-05-20) |
| ~~Step 5b~~ | #13·#14·#15·Spec 9·Phase 2 | ✅ 완료 (2026-05-20) |
| ~~Step 6~~ | Docker·Cloud Run·디자인 토큰 | ✅ 완료 (2026-05-22) |
| ~~Step 7~~ | 사업성 모드 + MD/Excel 다운로드 + 다수 버그 fix (urban_facility=0 / exporter / encoding) | ✅ 완료 (2026-06-19) |
| ~~Step 8~~ | 사내 케이스 DB + 정확도 harness | 🗑 제거 (2026-06-26, 더미라 제외) |
| **Step 9** | brief→law 자동 연계 (`competition_comparison` 통합) | ✅ 핵심 매핑 동작 (2026-06-26 검증). 추가 샘플로 견고화만 남음 |
| ~~Step 10~~ | 카테고리 계산식 노출 | 🚫 보류 (사용자 결정, 안 함) |
| ~~Step 11~~ | 법규 의미 그래프 (조문 참조 그래프 NetworkX) | ✅ 완료 (2026-06-26) — 시드+API+탐색기 / 카테고리→그래프 점프 / react-flow 캔버스(lazy) / 법제처 자동수확+자동병합(origin=auto 태깅) |

### 사용자가 직접 처리해야 할 항목

1. **brief 추가 샘플 다운로드 후 공유** (Step 9 견고화) — `competition_comparison` 출력 `{brief_id}.json`을 민간 1건 + 다부지 1건. 공공 1건(영등포 신청사)은 이미 `data/briefs/`에 있어 매핑 검증 완료. 5분 작업.
2. **토지이음 두 404 엔드포인트 문의** — `iuLawInfo` (3.3) + `sDevList` (3.8). ✉ luris@korea.kr + ☎ 1522-4484 각각 연락. 회신 오면 코드 조치 진행.
3. **도시계획시설 SHP 갱신** — 영등포 케이스에서 6시설 100% 저촉 오판정 발생. NSDI(`nsdi.go.kr`)에서 자주 다루는 자치구 SHP 분기 갱신.
4. **사내 시설용도 매핑표** (Step 9 보조) — brief 14개 사업유형 ↔ 건축법 19개 용도 변환표. 시니어 1명 30분 회의로 결정.

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
- **배포**: Docker (멀티 스테이지 빌드) → GCP Cloud Run (포트 8080, 단일 컨테이너)
- **디자인**: `frontend/src/kunwon-tokens.css` — CSS 변수 60여 개, Tailwind arbitrary value 연결

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
- **외부 API 재시도/백오프** — `services/http_retry.py`의 `request_with_retry`로 모든 정부 API GET 호출 래핑. 전송오류·5xx만 지수 백오프 2회 재시도(4xx·정상은 즉시). 일시 장애로 항목이 "확인필요"로 떨어지는 것 방지. (Slack webhook POST는 중복 알림 방지로 제외)
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
| `far_relief.py` | 용적률 완화 6레버(공개공지·녹색·ZEB·시범·지능형·장수명)+수동. 인증 합산 캡 15%, 전체 캡 1.15배 |
| `building_agreement.py` | 건축협정 §110의7 완화 사후 보정 |
| `multi_parcel.py` | 합필 진단 (면적 안분 + 소규모 예외) |
| `review_triggers.py` | 심의 자동 트리거 11종 (건축위·교통·경관·재해·교육·문화재·환경·도시계획위·지하안전·안전영향·범죄예방) |
| `law_change_tracker.py` ⚠️ | 법규 변경 감지 (수동 호출만) |
| `cache_manager.py` | SQLite Lazy Cache (조례 30일 TTL + 진단 이력) |
| `llm_client.py` | Claude API (temp=0, prompt caching) |
| `query_engine.py` ⚠️ | 자연어 질의 (조문 자동 인용 미완) |
| `law_graph.py` | 법규 의미 그래프 (networkx DiGraph, `config/law_graph_seed.json`) — 조문 관계 탐색 |
| `http_retry.py` | 외부 API 공용 재시도/백오프 (`request_with_retry`) |

## 주요 프론트엔드 파일 (frontend/src/)

### 디자인 시스템

| 파일 | 역할 |
|---|---|
| `kunwon-tokens.css` | CSS 변수 60여 개 (색상·폰트·간격·인쇄 전용 `--color-print-*`) |
| `index.css` | `@import './kunwon-tokens.css'` + Tailwind base |
| `tailwind.config.js` | CSS 변수를 Tailwind 테마로 연결 (colors·fontFamily·fontSize 등) |
| `frontend/DESIGN_SYSTEM.md` | 색상 팔레트·버튼·레이아웃·컴포넌트 문서 |

### 주요 컴포넌트 (frontend/src/components/)

| 컴포넌트 | 역할 |
|---|---|
| `InputForm/` | 전체 입력 폼 (건축협정·특별지구 토글 포함) |
| `DiagnoseResult/` | 8개 카테고리 진단 카드 |
| `WhatIfPanel/` | What-if 슬라이더 5개 + 비교 매트릭스 |
| `LawChangeAlert/` | 조례 해시 변경(orange) + 행정 고시(blue) 통합 배너 |
| `LawInfoPanel/` | 토지이음 법령 조문 펼쳐보기 |
| `DevTrendPanel/` | 주변 개발 인허가 동향 (7/14/30일 토글) |
| `DataQualityBanner/` | 데이터 출처·fallback 경고 |
| `LegalReviewReport/` | 종합 검토 보고서 (인쇄 미리보기 포함, `--color-print-*` 토큰 사용) |
| `QueryBox/` | 자연어 질의 |

---

## 보류 작업

- **도로폭 자동 조회** — VWorld 레이어에 폭 속성 없음. 인프라 완료, 데이터 소스만 보류. 토지이음 도입 후 재검토.
- **토지이음 `iuLawInfo`·`sDevList` 404** — 코드 문제 아님, 서버 측 장애. `LawInfoPanel`·`DevTrendPanel` 빈 결과, 핵심 8개 카테고리 영향 없음. 사용자가 직접 문의 후 회신 시 처리.
- **JUSO_API_KEY** — `.env`에 등록되어 있으나 코드에서 사용 안 함 (행안부 폴백 미구현). Kakao로 충분히 동작 중. 폴백 필요 시 `address_api_client.py` 보강.

---

## 확장 후보 — 외부 데이터·API·도구

당장 필수는 아니지만 도입 시 즉시 가치 있는 항목들. 우선순위별로 정리.

### A. 외부 API 추가 후보

| API | 용도 | 진단 영향 | 발급처 | 우선순위 |
| --- | --- | --- | --- | --- |
| **국가공간정보포털 (NSDI) API** | 도시계획시설·지구단위·지정문화재 SHP 자동 다운로드 | 시설 저촉 자동 판정 정확도 ↑ | nsdi.go.kr (무료, 회원가입) | 🔴 높음 |
| **공공데이터포털 학교알리미 API** | 학교 경계 좌표 → 교육환경평가(50/200m) 자동 판정 | `review_triggers` 교육환경 MAYBE → REQUIRED/NONE 확정 | data.go.kr → 학교알리미 | 🟡 중간 |
| **국가유산청 (문화재) GIS API** | 지정문화재 외곽 100~500m 자동 판정 | `review_triggers` 문화재 MAYBE → 확정 | khs.go.kr → 공간정보 | 🟡 중간 |
| **환경부 환경공간정보 (EGIS) API** | 보전지역·생태자연도·습지 자동 조회 | 환경영향평가 트리거 정밀화 | egis.me.go.kr | 🟢 낮음 |
| **국토부 실거래가 API** | 인근 거래 시세 → 사업성 보강 | 사업성 모드에 시세 카드 추가 가능 | rtdown.molit.go.kr | 🟢 낮음 |
| **통계청 SGIS API** | 인구·세대·상권 통계 → 지역 컨텍스트 | 사업성 모드 인문 분석 (ARCO arch-analysis-mcp 참고) | sgis.kostat.go.kr | 🟢 낮음 |
| **국세청 사업자등록조회 API** | 발주처 자동 분류 (공공/민간) | brief 연계 시 applicant_type 자동 추론 | hometax 비공식, 또는 공공기관 명단 DB로 대체 | 🟢 낮음 |

### B. 외부 데이터셋 (SHP·고시 — 다운로드형)

| 데이터 | 용도 | 어디서 | 갱신 주기 |
|---|---|---|---|
| **도시계획시설 SHP (시·도별)** | 시설 저촉 자동 판정 | NSDI → 도시계획시설 결정도면 | 분기 |
| **철도망 SHP** | 철도보호지구(30m) 판정 | NSDI 또는 철도산업정보센터 | 연 1회 |
| **지구단위계획구역 SHP** | 지구단위 자동 감지 → 결정사항 조회 | NSDI → 도시·군관리계획 | 분기 |
| **DEM (수치표고 5m·1m)** | 단계 2-3 (3D 지형 자동 생성) | 국토지리정보원 ngii.go.kr | 비정기 |
| **학교 경계 SHP** | 교육환경평가 좌표 판정 | 학교알리미 + 교육청 SHP | 연 1회 |
| **군사보호구역 SHP** | 군사보호구역 건축 제한 | 국방부 — 비공개, NSDI 일부 공개 | 비정기 |
| **가로구역 최고높이 고시 PDF** | §60 자동 판정 (현재 seed 0건 — `street_block_heights_loader`) | 시·구청 고시 사이트, PDF 파싱 후 seed JSON | 비정기 |
| **OpenStreetMap 한국 추출** | 도로·건물 보조 (단계 2-3 주변부 모델) | Geofabrik download.geofabrik.de | 일/주 |

### C. 사내 데이터 (수동 수집 — ROI 최고)

> ⚠ 케이스 매칭/정확도 harness 코드(Step 8)는 2026-06-26 제거됨. 아래 케이스 항목은 향후 재도입 시의 후보 (재도입하려면 git에서 `case_matcher.py` 복원).

| 데이터 | 용도 | 형태 | 작업량 |
|---|---|---|---|
| **인허가 통과 케이스 10건+** | 정확도 측정 ground_truth + 케이스 매칭 | JSON (주소·용도·면적·실제 산정값·완화 내역·심의 결과) | 케이스당 30~60분 |
| **반려·재검토 케이스 3~5건** | anti-pattern 학습 (`pattern_builder` 의 `loser_stats`) | JSON (동일 + 반려 사유) | 케이스당 30분 |
| **brief 샘플 PDF/DOCX 3건+** | Step 2 매핑 룰 결정 (공공/민간/다부지 각 1건) | 원본 + 추출된 `_brief.json` | 5분 (다운로드만) |
| **사내 시설용도 매핑표** | brief 14개 사업유형 ↔ 건축법 19개 용도 변환 | 표 (md·xlsx) | 시니어 1명 30분 회의 |
| **사내 자주 다루는 가로구역 고시** | 영등포·강남·종로 등 자주 다루는 자치구 §60 seed | JSON (block_name·max_height_m·polygon) | 자치구당 1~2시간 |
| **사내 표준 검토서 양식·로고** | PDF/Excel 푸터 표준화 | 이미지·텍스트 | 30분 |

### D. Python 라이브러리 (필요 시 추가)

| 라이브러리 | 용도 | 도입 시점 |
|---|---|---|
| `pytest`, `pytest-asyncio` | 회귀 테스트 | ✅ 도입 (141건, 2026-06-26) |
| `httpx-mock` 또는 `respx` | 외부 API 모킹 (오프라인 테스트) | 미도입 — 클라이언트(vworld·eum·luris) 테스트 시 |
| `networkx` | 법규 의미 그래프 (조문 간 관계) | ✅ 도입 (Step 11, 2026-06-26) |
| `python-docx` | brief DOCX 파싱 (PDF만 아니라 DOCX도) | Step 2 brief 연계 시 |
| `rasterio` 또는 `GDAL` | DEM 처리 (3D 지형) | 단계 2-3 진입 시 |
| `rhino3dm` | Rhino 3DM 모델 생성 | 단계 2-3 진입 시 |
| `ezdxf` | DXF 도면 생성 | 단계 2-2 진입 시 |
| `pandas` | 케이스 통계·분포 계산 | 케이스 10건+ 모이면 |
| `pillow` | 이미지 생성·합성 (보고서 도식) | 보고서 시각화 강화 시 |

### E. 개발·운영 인프라

| 도구 | 용도 | 우선순위 |
|---|---|---|
| **pre-commit hooks (ruff, mypy)** | 커밋 전 코드 품질 자동 검사 | 🟡 |
| ~~GitHub Actions 확장~~ | `pytest` 자동 실행 + 배포 게이트 | ✅ 완료 (deploy.yml test job + needs) |
| **GCP Cloud Logging + Error Reporting** | 운영 에러 추적 (현재 콘솔만) | 🟡 |
| **GCP Cloud Scheduler** | `ENABLE_LAW_CHANGE_CRON` 외부 트리거 (Cloud Run 무인 운영) | 🟢 |
| **BigQuery** | 진단 이력 누적 분석 (어떤 카테고리·지역에서 자주 막히나) | 🟢 |
| **Looker Studio** | 정확도 측정 대시보드 (사내 시니어 모니터링) | 🟢 |
| **Sentry** | 프론트엔드 런타임 에러 자동 수집 | 🟢 |

### F. 외부 통합 (선택)

| 도구 | 용도 | 비고 |
|---|---|---|
| **Claude Desktop MCP wrapper** | arch-law-diagnose 계산기를 MCP 도구로 노출 → Claude Desktop·다른 에이전트에서 직접 호출 | 사내 단일 사용처면 오버엔지니어링. 외부 제공 계획 있을 때만 |
| **Notion API** | 사내 케이스 DB를 Notion에서 관리 → 진단 도구가 Notion에서 동기화 | 사내가 이미 Notion 쓰는 경우만 |
| **Slack 양방향** | 시니어 검토 요청 + 회신을 Slack 스레드로 (현재 단방향 webhook만) | Slack 사내 사용 시 |

### 도입 순서 권장 (즉시 ROI 기준)

1. ~~pytest 도입~~ — ✅ 완료 (2026-06-26, 141건 + CI 게이트).
2. **brief 추가 샘플** (C) — 민간·다부지 각 1건으로 Step 9 매핑 견고화. 작업 5분. (공공 1건은 이미 검증)
3. **도시계획시설 SHP 영등포구·자주 다루는 자치구 갱신** (B) — 998배 부풀리기 같은 함정 방지.
4. **NSDI API 연동** (A) — SHP 자동 다운로드로 B의 수동 작업 자동화.
5. **학교·문화재 API** (A) — `review_triggers` MAYBE 고정 항목 확정 판정.

> ~~사내 케이스 10건~~ — Step 8 제거로 보류(사용자 결정). 향후 정확도 측정이 다시 필요하면 git에서 `case_matcher.py` 복원.

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

### Docker 로컬 빌드·실행

```
docker build -t arch-law-diagnose .
docker run --env-file .env -p 8080:8080 arch-law-diagnose
```

브라우저에서 `http://localhost:8080` 확인. `.env` 파일이 컨테이너에 주입됨.

### GCP Cloud Run 배포 (요약)

```
gcloud builds submit --tag gcr.io/PROJECT_ID/arch-law-diagnose
gcloud run deploy arch-law-diagnose --image gcr.io/PROJECT_ID/arch-law-diagnose \
  --platform managed --region asia-northeast3 --port 8080 \
  --set-secrets="ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest,..."
```
전체 절차 및 Secret Manager 설정은 [DEPLOY.md](DEPLOY.md) 참조.

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
