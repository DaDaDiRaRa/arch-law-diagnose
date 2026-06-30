# arch-law-diagnose

건축 법규 자동 진단 시스템 — 사내 전용. 주소 + 건물 정보를 입력받아 8개 카테고리를 자동 검토하고 GREEN/YELLOW/RED 신호와 종합 점수를 반환.

---

## 🔴 세션 운영 규칙 (반드시 준수)

1. **컴팩트 전 이 파일 먼저 업데이트** — 대화가 압축되면 이전 작업 내용이 사라지므로, 다단계 작업 중 context 압축이 예상되면 CLAUDE.md의 Spec 표와 "다음 작업" 섹션을 먼저 갱신한 뒤 계속 진행한다.
2. **전국 적용 원칙** — 모든 Spec·기능은 특정 대지(영등포구 등)에 종속되지 않고 전국 어느 주소에서나 동작해야 한다. 지구명·조례값 하드코딩 금지, 범용 파싱·조회 로직 사용.

---

## 🔗 arch-law-graph 연계 (역할 분담)

> 자매 앱 **arch-law-graph**(`D:\APPS\arch-law-graph`, GitHub `DaDaDiRaRa/arch-law-graph`). graph = 법령 지식 레이어(데이터·RAG·원문 주인, 25,235노드·조례 84개 시), diagnose = 대지 판정 레이어(계산·컨텍스트).

| | **diagnose (이 앱)** | **arch-law-graph** |
| --- | --- | --- |
| 질문 | "이 땅에 이 건물 지을 수 있나?" | "이 법조문이 무슨 뜻이야?" |
| 출력 | RED/YELLOW/GREEN + 종합점수 | 법령 본문 + 인용관계 + 지자체 기준표 |
| 계산 | 건폐율·용적률·주차 실계산 | 계산 없음, 조문 원문 제시 |
| 데이터 | 실시간 API(VWorld·EUM·LURIS) | 정적 graph.json(매일 빌드) |

**연계 현황 (완료, 2026-06-29)**:

- ① **진단 결과 종속 어시스턴트** — `query_engine`이 진단 law_refs를 "적용 조문" 블록으로 주입 + graph `POST /api/lookup`으로 조문 원문 RAG 그라운딩(`graph_client.py`, env `GRAPH_API_URL`, 실패 시 degrade). "원문에 있는 내용만 인용"으로 환각 차단.
- ② **링크아웃** — 진단 카드 law_refs·AI citation 옆 "원문↗"이 graph 검색을 `?q=<조문명>`으로 엶(`utils/graphLink.js`, env `VITE_GRAPH_URL`). ⚠ graph 레포 변경분은 별도 커밋.

**보류·제외**: MCP/API 정식 통합·QueryBox 경계 재편 = 보류(아래 "다음 작업"). graph.json 파일 이식(B안) = 동기화 부담으로 제외. 합칠 때 조례/주차/완화 해결 범위 분석 → [doc/ACCURACY_SHARPENING_PLAN.md](doc/ACCURACY_SHARPENING_PLAN.md) §4.5.1.

---

## ⏭️ 다음 작업

**2026-06-29 계획 — 정확도·정직성 강화 (기능 유지·추가형 우선)** → 상세: [doc/ACCURACY_SHARPENING_PLAN.md](doc/ACCURACY_SHARPENING_PLAN.md)

> 정체성: diagnose = 결정론적 **"대지 판정 계산 엔진"**(숫자 + 판정 + 근거조문 포인터 law_refs). 법 해석은 graph 담당.
> 원칙: **MCP/API화·기능 경계 재편은 보류**(graph 정식 통합 시). 지금은 **기존 기능 그대로 두고 정확도·정직성만** 올린다 = 추가형만(기존 신호·점수·답변범위 불변).

지금 할 일 (기존 동작 불변·추가형, 순서 E→A→B→D):

- [x] **E. 침묵 과대평가 구멍 경고** — ✅ 완료 (2026-06-29). `data_quality.issues`에 2종 추가: `STREET_BLOCK_UNVERIFIED`(info — 가로구역 §60 미평가 고지) + `FACILITY_AREA_UNCORRECTED`(warn — 시설 저촉 감지됐으나 폴리곤 미확보로 면적보정 미수행). **신호·점수 로직 불변**(테스트로 보증). 테스트 +5(전체 269).
- [x] **A(노출만). 종합 신뢰도 노출** — ✅ 완료 (2026-06-29). `_weighted_score`가 계산해 버리던 `min_confidence`를 `data_quality.aggregate_confidence`(채점 항목 중 최저 confidence 1~5)로 노출 + `DataQualityBanner`에 "신뢰도 N/5" 배지(초록/노랑/주황). **신호 로직 불변**(게이팅 아님). 이력은 JSON blob이라 스키마 ALTER 불필요. 테스트 +1(전체 270) + 프론트 빌드 통과.
- [x] **B. 산정 근거(provenance) 블록** — ✅ 백엔드 완료 (2026-06-29). 정량 4개 카드(건폐율·용적률·높이_일조·주차) 반환에 `provenance{inputs·formula·computed·basis}` 추가 — 각 계산기가 자기 산식을 스스로 기술(미래 MCP 도구화 대비). 기존 필드(`law_refs`·`source`·`notes` 등)·동작 불변. 계산 발생한 카드에만 부착(확인불가 분기 생략). 테스트 +2(전체 272). 프론트: `DiagnoseResult` 카테고리 카드 펼침에 "🧮 산정 근거" 접이식 추가(입력값·산식·산출, 키→한글 라벨). 프론트 빌드 통과.
- [x] **D. 골든 케이스 회귀셋** — ✅ 골격+실제 **12건** 완료 (2026-06-29). `tests/golden/*.json`(익명화·숫자만) + `test_golden_cases.py`(조례 stub + `_diagnose` skip_ai 결정론, actual_pct ±0.01%p 허용으로 원문 절사 흡수). M드라이브 실 인허가 건축개요서 12건 추출(식별정보 전부 제외, 수치·용도지역만). **용도지역 7종 커버**: 일반상업(오피스텔·업무재개발·여의도주상복합·김포숙박)·준주거(주거복합)·제2종일반주거(재개발·목동재건축)·제3종일반주거(방배재건축·수지초교육)·중심상업(대구주상복합)·준공업(문래동지식산업센터)·지구단위(광교). 재건축·아파트·공동주택·업무·교육·숙박·지식산업센터 등 유형 다양. 다수가 법정/허용/상한 면도날 통과. 커버리지 표·스키마·익명화 규칙은 `golden/README.md`. **+ 고가치 경로 4종 검증 완료**(합성, `test_path_*`): 실패/RED(한도초과→pass=False·신호 RED)·완화(`far_relief` 공개공지 25.18%+녹색최우수→전체 캡 1.15배=460%, 룰 문서화 실증 시나리오)·주차 부족(pass=False)·비주입(조례 미주입 시 엔진이 `zone_limits.json` 시행령 60/250 자가결정). **전부 엔진이 정확 처리 확인**(버그 무, 경로 회귀 고정). 테스트 +16(전체 288). ※ 제거된 Step 8(케이스 매칭)과 다른 *정답 측정*. ⏳ 남은 용도지역(1종일반주거·전용주거·근린/유통상업·일반공업·녹지)·시설(근생·의료·물류)은 통과형이라 가치 작음 — 폭 넓힐 때만. 후보 카탈로그 scratchpad `m_cat2.tsv`·`m_gaeyo.tsv`·`m_hits.tsv`.

보류 (기존 동작 변경/제거 수반 → graph 정식 API 통합 시):

- [ ] **C. QueryBox 일반 법령 Q&A 축소·graph 링크아웃** — 기능 *축소*라 합치기 전엔 안 함. 현재는 일반 질문도 답하되 graph 원문 그라운딩(A안)으로 환각만 억제, **그대로 유지**.
- [ ] **A(게이팅). confidence로 GREEN→YELLOW** — 판정 로직 변경이라 별도 사용자 결정.
- [ ] **MCP/API 도구화 + 계약** — 합치는 단계 일. 불변식: diagnose 도구는 *숫자+판정+law_refs만* 반환, 법령 본문/해석 산문은 절대 반환 안 함(본문은 graph `/api/lookup`).

하지 말 것 (환각 표면 차단): 조문 본문·해석 자체 생성 금지(graph 영역), 고시 PDF 자동파싱 금지(폐지고시 오인), LLM 결정수치 금지, 점수곡선 재발명 금지(골든셋 캘리브레이션만).

**다음 정확도 단계 (미착수)** — 실제 케이스 기반 **캘리브레이션 루프**: 골든은 "맞음을 증명·고정", 이건 "틀림을 찾아 고침"(엔진 정확도가 실제로 오르는 경로). 진입점=**법정 한도 재현 감사**(케이스 `legal_*` vs 엔진 비주입 출력 갭 수치화) → 가치순 ① **조례 한도 DB 보강**(`ordinance_seed.json`, 최대 레버·낮은 위험) ② 주차·심의 트리거 보정 ③ ~~완화/정비 인센티브 모델~~(환각 위험 커 보류). 새 구조 아님 — 기존 `ordinance_resolver`/`seed`/`extractor` 파이프라인을 신뢰·우선순위화. 상세: [doc/ACCURACY_SHARPENING_PLAN.md](doc/ACCURACY_SHARPENING_PLAN.md) §4.5.

---

**완료 이력 (요약)** — 2026-06-22 사업성 모드 A~E 확장(제안화면·What-If·brief 불러오기 E1·다중비교 E2·MD/Excel E3, `feasibility_*`·`/api/feasibility/*`). 2026-06-26 버그 5건 fix + pytest CI 게이트(`deploy.yml` test job) + 외부 API 재시도(`http_retry.py`, 정부 GET 14곳) + Step 8(사내 케이스 DB) 제거 + Step 9(brief 연계, 소스앱 `competition_comparison`·버킷 `kunwon-competition-db/_briefs/`·env `BRIEF_DIR`) + Step 11(법규 그래프 138노드). 2026-05-20~22 Step 5a(법령 수치 검증)·5b(#13~15)·6(Docker·Cloud Run·디자인 토큰). 2026-06-19 Step 7(사업성 초판).

**보류 (외부 의존)**: D 부대시설·사업성 지표(추가 데이터·기준 필요) · 용도 매핑표(brief 사업유형↔건축법 19용도 전체표, 시니어 회의). ※ brief 괄호표기 부분 자동감지는 이미 동작.

### 📋 현재 상태

핵심 계산 엔진 운영급 완성(건폐율·용적률·완화 합산·심의 트리거 정확). 막힌 건 "데이터"(SHP·고시·brief 샘플 — 외부에서 채울 영역).

| 영역 | 상태 |
| --- | --- |
| 핵심 계산 + 사업성 모드 + UI + PDF/MD/Excel | ✅ 운영급 |
| API 키 (Kakao·VWorld·EUM·LURIS·Claude·법제처) | ✅ 활성 |
| 검증 인프라 (pytest 288건 · CI 게이트) | ✅ |
| brief 연계 (Step 9) | ✅ 동작 (실샘플 `data/briefs/_brief.json` 검증) |
| 일부 SHP 누락 (철도 / 일부 도시계획시설) | ❌ |

### 🎯 활성 TODO

> 정규 로드맵 Step 5a~11 전부 완료/제외(Step 8 케이스 DB·10 계산식 노출은 사용자 결정으로 제외).

- [ ] **가로구역 §60 seed** (현재 0건 → 자동판정 거의 안 됨) — 자치구 고시 PDF에만 존재, **수동 입력만** (PDF 파싱은 환각·폐지고시 오인 위험으로 보류).
- [ ] **brief 추가 샘플**(민간·다부지) → Step 9 매핑 견고화 (공공 1건 검증됨).
- [ ] **토지이음 404 문의**(`iuLawInfo`·`sDevList`) ✉ luris@korea.kr · ☎ 1522-4484 → LawInfoPanel·DevTrendPanel 활성화.
- [ ] **사내 시설용도 매핑표**(시니어 30분) → brief 용도 완전 자동화.
- [ ] **철도보호지구** — 보류(복잡). 코드(`railway/indexer.py`) 준비됨 → `RAILWAY_SHP_PATH`에 철도선형 SHP(Geofabrik OSM `gis_osm_railways_free_1.shp`, EPSG:4326, → `backend/files/railway/`) 배치 시 동작. ※ 도시계획시설 철도는 이미 VWorld 판정 중, 빠진 건 운영철도 30m 보호지구(철도안전법 §45)뿐.
- [ ] (낮음) 운영 인프라(Cloud Logging·Sentry·BigQuery), dev `npm audit fix`.

> 완료: NSDI 폐기(서비스 종료→VWorld 대체)·지구단위계획구역 자동감지(VWorld WFS `lt_c_upisuq161`)·학교(Kakao)·문화재(국가유산청 GIS) 좌표 판정·도시계획시설 VWorld WFS 실시간 전환.

---

### 완료 로드맵 (요약)

- **Step 5a 법령 수치 검증**(2026-05-20): `far_relief_rules.json` 별표9(녹색 6/3·ZEB 15~11·시범 10), `public_certification` ZEB 의무, `landscape_standards` 추정값 제거(미매칭→pass=None·conf 2), `building_agreement` §110의7.
- **Step 5b**(2026-05-20): #13 주차 세부분류·#14 다중이용(`multi_use.py`)·#15 영향평가 5종(총 11 심의), Spec 9 조경 고시(국토부 제2021-1778호).
- **Step 6**(2026-05-22): Docker·Cloud Run·디자인 토큰(`kunwon-tokens.css`), `DESIGN_SYSTEM.md`·`DEPLOY.md`.
- **Step 7**(2026-06-19): 사업성 모드 + MD/Excel. **Step 9**: brief 연계. **Step 11**: 법규 그래프(138노드). **Step 8·10**: 제거/보류(사용자 결정). Spec 1~11 코드 완료.

### 사용자가 직접 처리할 항목

1. brief 추가 샘플(`competition_comparison` 출력, 민간 1 + 다부지 1). 공공 1건 검증됨.
2. 토지이음 404 문의(`iuLawInfo`·`sDevList` — ✉ luris@korea.kr · ☎ 1522-4484).
3. 사내 시설용도 매핑표(brief 14 사업유형 ↔ 건축법 19 용도, 시니어 30분).

### 공유 폴더 (셋업 완료)

회사 PC: SHP(3.8GB) → M 드라이브, env `SHP_ROOT` 참조. DB·`.env`·케이스 JSON → C 로컬. 상세 [SETUP.md](SETUP.md).

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
| --- | --- | --- |
| Anthropic Claude | `ANTHROPIC_API_KEY` (필수), `ANTHROPIC_MODEL`(선택) | 설비·소방 정성 판단·자연어 질의·조례 본문 수치 추출 |
| 법제처 DRF | `LAW_API_KEY` | 조례 본문 수집, 조례 변경 감지 |
| VWorld | `VWORLD_API_KEY` | 좌표 변환·용도지역·지적도·도로폭·지적 폴리곤(WFS) |
| Kakao Local | `KAKAO_API_KEY` | 주소 자동완성, 학교 근접 조회(교육환경평가) |
| 국가유산청 GIS | (키 불필요) | 지정문화재 근접 조회(문화재심의 트리거) — `heritage_client.py` |
| 토지이음 (EUM) | `EUM_ID`, `EUM_KEY` | 법령정보·행정 고시·개발 인허가·행위제한 교차검증 |
| 행안부 도로명주소 | `JUSO_API_KEY` | 주소 검색 폴백·정규화 |
| 공공데이터포털 / LURIS (선택) | `LURIS_API_KEY` 우선, 없으면 `DATA_GO_KR_API_KEY` 폴백 | LURIS 행위제한 (토지이음과 교차검증) |
| Slack (선택) | `SLACK_WEBHOOK_URL` | 시니어 검토 요청 webhook |

기타 설정: `DB_PATH`, `CACHE_TTL_DAYS`, `LOG_LEVEL`, `ENABLE_LAW_CHANGE_CRON` 등 → `.env.example` 참조.
누락된 API는 graceful degrade — 해당 항목만 "확인필요(YELLOW)" 처리.

---

## 진단 카테고리

### 핵심 8개 (가중치 적용 → 종합점수 반영)

| 코드 | 계산기 | 출처 |
| --- | --- | --- |
| 행위제한 | `land_use_act.py` | LURIS + EUM 교차검증 |
| 도시계획시설 | `urban_facility.py` | VWorld WFS 실시간(lt_c_upisuq151~159) ∩ 지적도 — SHP 없이. 실패 시 로컬 SHP 폴백 |
| 건폐율 | `coverage.py` | 조례 우선 → 시행령 (zone_limits.json) |
| 용적률 | `far.py` | 동일 + 4종 완화 (녹색·에너지·지능형·장수명) |
| 높이·일조 | `height.py` | §60·§61 자동 판정 |
| 주차 | `parking.py` | 주차장법 시행령 |
| 조경 | `landscape.py` | 건축법 §42 + 시행령 §27 + 조례 리졸버 |
| 설비·소방 | `fire_safety.py` | Claude AI 정성 판단 |

### 추가 정보 카드 3개 (가중치 0, 정보 표시 전용)

| 코드 | 계산기 | 조건 |
| --- | --- | --- |
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
| --- | --- |
| `diagnose_engine.py` | 진단 전체 오케스트레이션 |
| `zone_use_normalizer.py` | 용도지역 표준명 정규화 (19종 + 별칭 61개) |
| `eum_client.py` | 토지이음 7개 API |
| `luris_client.py` | 공공데이터포털 LURIS 행위제한 2개 API (EUC-KR XML) |
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
| `query_engine.py` | 자연어 질의 (law_refs 주입 + graph RAG 그라운딩, `graph_client.py` 연동) |
| `law_graph.py` | 법규 의미 그래프 (networkx DiGraph, `config/law_graph_seed.json`) — 조문 관계 탐색 |
| `http_retry.py` | 외부 API 공용 재시도/백오프 (`request_with_retry`) |

## 주요 프론트엔드 파일 (frontend/src/)

### 디자인 시스템

| 파일 | 역할 |
| --- | --- |
| `kunwon-tokens.css` | CSS 변수 60여 개 (색상·폰트·간격·인쇄 전용 `--color-print-*`) |
| `index.css` | `@import './kunwon-tokens.css'` + Tailwind base |
| `tailwind.config.js` | CSS 변수를 Tailwind 테마로 연결 (colors·fontFamily·fontSize 등) |
| `frontend/DESIGN_SYSTEM.md` | 색상 팔레트·버튼·레이아웃·컴포넌트 문서 |

### 주요 컴포넌트 (frontend/src/components/)

| 컴포넌트 | 역할 |
| --- | --- |
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

## 확장 후보 (someday — 도입 시 가치)

- **외부 API**: 환경부 EGIS(환경평가 정밀화, egis.me.go.kr), 국토부 실거래가(rtdown.molit.go.kr)·통계청 SGIS(사업성 보강). ※ NSDI 폐기, 학교(Kakao)·문화재(국가유산청)는 완료.
- **데이터셋(다운로드형)**: 철도망 SHP(Geofabrik), 가로구역 최고높이 고시 PDF(§60 seed), DEM(3D 지형, ngii.go.kr), 군사보호구역(국방부).
- **사내 데이터(ROI 최고)**: 인허가 통과 케이스(정확도 ground-truth — 골든셋 `tests/golden/`으로 일부 시작됨), 반려 케이스(anti-pattern), 시설용도 매핑표, 자주 다루는 자치구 가로구역 고시 seed, 표준 검토서 양식.
- **라이브러리(필요 시)**: `python-docx`(brief DOCX), `rasterio`/`GDAL`·`rhino3dm`·`ezdxf`(3D·도면, 단계 2-3), `pandas`(케이스 통계). ※ pytest·respx·networkx 도입됨.
- **인프라**: pre-commit(ruff/mypy), Cloud Logging·Sentry, Cloud Scheduler(`ENABLE_LAW_CHANGE_CRON` 트리거), BigQuery·Looker(분석). ※ GitHub Actions CI 게이트 완료.
- **통합(선택)**: MCP wrapper(외부 제공 시), Notion·Slack 양방향.

> ROI 순서: brief 추가 샘플 → 사내 케이스/매핑표(시니어). pytest·SHP→VWorld·학교·문화재 API는 완료.

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
