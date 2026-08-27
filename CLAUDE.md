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

**보류·제외**: MCP/API 정식 통합·QueryBox 경계 재편 = 보류(아래 "다음 작업"). graph.json 파일 이식(B안) = 동기화 부담으로 제외. 합칠 때 조례/주차/완화 해결 범위 분석 → [doc/ACCURACY_SHARPENING_PLAN.md](doc/ACCURACY_SHARPENING_PLAN.md) "graph 합칠 때 조례/주차/완화 해결 범위 분석".

---

## 🔗 competition_comparison 연계 (상류 — 우리가 읽는 쪽)

> 자매 앱 **competition_comparison**(`D:\APPS\competition_comparison`). 공모지침서(PDF/DOCX/HWP)를 분석해 `_brief.json`을 낸다. **우리가 그 파일을 읽는다** — HTTP 아님, 공유 디렉터리(env `BRIEF_DIR`, Cloud Run은 그쪽 GCS `_briefs/`를 GCSFUSE 마운트) 직접 읽기. 소비 경로: `GET /api/feasibility/briefs`(목록) · `GET /api/feasibility/briefs/{file_id}` → `brief_importer.map_brief` → 사업성 `target_*` prefill → `BriefList`·`BriefImportPanel`·`MultiSiteCompare`.

### ⚠️ 계약이 "파일 이름"이다 (깨져도 조용하다)

`list_briefs`는 **파일을 열지 않고 파일명만으로** 정렬·필터한다 — `_FNAME_RE = ^(\d{8})_(\d{6})_(.+)$`, 즉 `YYYYMMDD_HHMMSS_카테고리[_슬러그]`. 파일명이 이 패턴에서 벗어나면 예외가 아니라 `('', '')`로 떨어져 **정렬 뒤로 밀리고 카테고리 필터에서 사라진다**. 프론트 `BriefList.jsx`의 카테고리 14종도 그쪽 파일명 suffix의 사본이다.

같은 성격의 암묵 의존 3가지 — **바뀌면 전부 조용히 깨진다**:

| 의존 | 어디서 | 깨지면 |
| --- | --- | --- |
| 파일명 `YYYYMMDD_HHMMSS_카테고리` | `brief_importer._FNAME_RE` (정렬·필터·`analyzed_at` 폴백) | 목록에서 누락·순서 뒤섞임 |
| `brief_project_info.sites[]` 스키마 (`site_id`·`site_area_sqm`·`floor_area_ratio_pct`·`building_coverage_pct`·`max_height_m`·`floor_area_sqm`·`facilities`·`zoning`) | `brief_importer._map_site` | prefill이 빈 값 → 사업성 입력 침묵 누락 |
| `brief_site[].address`의 `(부지N)` 표기 | `brief_importer._parse_site_addresses` | 부지별 주소 미분해 → 주소 빈칸 |

그쪽 CLAUDE.md에도 「형제앱이 우리를 읽는 경로」로 기록됨(2026-08-27). **파일명 규칙·sites 스키마 변경은 사전 통지 대상**이고, 통지가 없으면 우리 쪽에서 먼저 알 방법이 없다(예외가 안 난다).

### `feasibility_export` 갈아타기 — 부분 채택 (2026-08-27 대조 결과)

그쪽 `_brief.json`에 정규화 블록 `feasibility_export`(schema_version 2)가 있다. 실샘플 10건(공공 5·민간 5, 부지 13개)에서 `map_brief` 출력과 전수 대조한 결론: **정량치는 100% 일치 → 지금 사업성 입력이 틀리고 있지는 않다.** 우리 파서를 지우는 "전면 교체"는 **손해**, 새 필드 3종만 **가산 채택**이 맞다.

- **채택 대상(우리에게 없는 값)**: `limits_determined_by`(「심의」면 공모의 60%/460%는 법정 한계가 아님 — 현재 우리는 이 구분이 없어 심의로 상향된 460%를 법정 400%와 비교해 **없는 갭을 초과로 보고**한다. 영등포 샘플 2부지 실재) · `required_parking_count`+`parking_note`(현재 `target_parking_count`가 brief에서 안 채워져 주차 갭이 항상 "공모 요구 없음") · 사업비·설계비·공사기간.
- **채택 제외**: `zone_use` — 그쪽 정규화에 **동점 오선택 버그**. `제3종일반주거지역 (제2종일반주거지역에서 종상향)` → `max(matches, key=len)`가 길이 동점(9자)에서 리스트 앞 항목을 골라 **`제2종일반주거지역`**(종상향 前)을 반환. 우리 `zone_use_normalizer`는 같은 입력에 `None`(확인필요)으로 정직하게 떨어진다. raw `zoning`을 우리 정규화기에 넣는 현행 유지.
- **파서 삭제 불가**: 샘플 10건 중 4건은 블록 자체가 없고 1건은 v1(2차 필드 없음). `schema_version >= 2`면 우선 사용, 아니면 기존 파서 폴백 — 폴백은 영구히 필요하다.
- **전면 교체 시 유실**: `floor_area_sqm`(목표 연면적)·`open_space_sqm`·`open_space_notes`는 그쪽 블록에 **없다**. `_quantitative` 단일부지 합성 폴백도 없다(종로세부지침 샘플: 우리 1부지 vs 그쪽 0부지). `building_law_uses`는 괄호 안만 보고 19용도 필터가 없어 `주민편의시설` 같은 비표준어를 그대로 내보내고, 괄호 없는 표기(`공동주택`)는 놓친다 — 우리 `_detect_building_uses`가 더 좁고 정확하다.

---

---

## ⏭️ 다음 작업

> 정체성: diagnose = 결정론적 **"대지 판정 계산 엔진"**(숫자 + 판정 + 근거조문 포인터 law_refs). 법 해석은 graph 담당. 설계 원칙·배경은 [doc/ACCURACY_SHARPENING_PLAN.md](doc/ACCURACY_SHARPENING_PLAN.md)(완료된 계획, 원칙·가드레일만 유효).

### 🎯 활성 TODO

- [x] ~~**법규그래프 참조 조문 7건 정정**~~ ✅ **2026-08-27 완료** — graph E-12 감사가 지목한 7건은 **조문 삭제가 아니라 전부 「법령 귀속 오류」**였다(법제처 현행 원문 6개 조문 대조로 확인). 인용 자체는 실재한다 — 딸린 법령 이름만 틀렸다. 원인은 `law_graph_harvest.extract_refs`의 두 구멍: ① **시행령의 `법 제N조`는 모법 조문**인데 시행령 자기 조문으로 읽었다(→ 실재하지 않는 `건축법 시행령 제13조의2·제53조의2·제77조의2·제77조의4` 생성) ② **명시 법령 뒤 나열의 첫 조문만 귀속**시켜 뒤따르는 조문이 현재 법으로 떨어졌다(`「건축법」 제60조 및 제61조` → 제61조가 `녹색건축물법 제61조`로, `「산업입지…법」 제6조, 제7조, 제7조의2` → `건축법 제7조의2`로, `같은 법 제51조`(국토계획법) → `주차장법 제51조`로). 수정: `extract_refs`를 **법령 문맥 추적**(앵커 `「법령명」`·`같은 법`·시행령의 `법` + 연결부 `, · 및`로 이어지는 나열 상속)으로 재작성 + `_canon_law`(정식명칭→시드 약칭, `_LAW_SEARCH_KEYWORD` 역인덱스)로 **같은 조문이 노드 둘로 갈라지던 중복 3건**도 해소. 재수확 결과 **노드 89→79 · 엣지 116→117**, 시드(검증) 노드로 붙는 엣지 10→19(+9 — 없는 조문을 만들던 자리가 검증된 조문에 연결됐다). **전수 검증: auto+seed 참조 조문 102건 전부 법제처 실재 확인 · 미존재 0건**. 회귀 9건 추가(전부 법제처 원문 발췌 고정), 테스트 318→327.
- [ ] **`feasibility_export` 부분 채택**(대조 완료, 착수 대기 — 사용자 승인 필요) — 실샘플 10건 전수 대조 결과 정량치 100% 일치라 **긴급하지 않다**(현재 사업성 입력은 틀리지 않음). 다만 `limits_determined_by="심의"`를 모르는 탓에 심의 상향 용적률(영등포 460% vs 준공업 법정 400%)을 **없는 갭 60%p 초과로 오보**한다 — 이것만이 실사용 오류. 범위: `map_brief`에 `schema_version>=2`면 `limits_determined_by`·`required_parking_count`/`parking_note`·사업비 3종을 **추가로** 얹고(기존 파싱은 폴백으로 유지·삭제 금지), 갭 분석은 「심의 결정」일 때 초과를 RED가 아니라 "심의 전제" 표기로. `zone_use`는 채택 안 함(그쪽 동점 오선택 버그 — 상세는 위 연계 섹션). 상세 근거는 「🔗 competition_comparison 연계」 참조.
- [ ] **brief 추가 샘플**(민간·다부지) → Step 9 매핑 견고화. **competition_comparison DB에 이미 있음 — 요청 형태 확정(2026-08-27)**: `C:\Temp\CompTestDB\_briefs\*.json` 10건으로 1차 대조 완료(민간 5건 = `reconstruction` 카테고리, 다부지 2건). 남은 요청은 ① **다부지 민간** 1건 이상(현재 다부지는 공공 영등포 + 민간 하안주공뿐, 하안주공 2번째 부지는 주소·면적이 비어 있어 반쪽) ② `zoning`에 **종상향·지구단위 표기**가 들어간 건(우리 정규화기 None 폴백 검증용) ③ `brief_design_massing.parking_requirements`에 **부지별 주차 서술**이 있는 건. 형태: `_brief.json` 원본 그대로(파생 md/xlsx 불필요), `feasibility_export` schema_version 2 포함.
- [ ] **토지이음 404 문의**(`iuLawInfo`·`sDevList`) ✉ luris@korea.kr · ☎ 1522-4484 → LawInfoPanel·DevTrendPanel 활성화. *(사용자 처리)*
- [ ] **사내 시설용도 매핑표**(시니어 30분) → brief 용도 완전 자동화. **요청 형태 확정(2026-08-27)**: competition_comparison이 `feasibility_export.sites[].building_law_uses`의 **원시 수집값 전체**(중복 포함 raw 빈도표, 정규화·필터 금지 — 그쪽 추출은 「괄호 안 + 시설로 끝나거나 주택 포함」이라 `주민편의시설`처럼 19용도가 아닌 어휘가 섞여 있고, **그게 정확히 우리가 필요한 재료**)를 CSV 2열(`원문어휘,출현횟수`)로 뽑아 준다 → 시니어가 3열째(`건축법_19용도`)만 채우면 `brief_importer._BUILDING_USES` 대체 매핑표가 된다. 미매핑 어휘는 빈칸 유지(추측 금지) → `facility_use_candidates`에서 제외되고 힌트로만 표시. ⚠ 그쪽 `building_law_uses`를 그대로 쓰는 것이 아니라 **어휘 목록만 재료로** 받는다.
- [ ] **철도보호지구** — 보류(복잡). 코드(`railway/indexer.py`) 준비됨 → `RAILWAY_SHP_PATH`에 철도선형 SHP(Geofabrik OSM `gis_osm_railways_free_1.shp`, EPSG:4326) 배치 시 동작. 도시계획시설 철도는 이미 VWorld 판정 중, 빠진 건 운영철도 30m 보호지구(철도안전법 §45)뿐.
- [ ] (낮음) 운영 인프라(Cloud Logging·Sentry·BigQuery), dev `npm audit fix`.

### 보류 (graph 정식 API 통합 시 착수)

- [ ] **C. QueryBox 일반 법령 Q&A 축소·graph 링크아웃** — 기능 *축소*라 합치기 전엔 안 함. 현재는 일반 질문도 답하되 graph 원문 그라운딩으로 환각만 억제, 그대로 유지.
- [ ] **A(게이팅). confidence로 GREEN→YELLOW** — 판정 로직 변경이라 별도 사용자 결정.
- [ ] **MCP/API 도구화 + 계약** — 불변식: diagnose 도구는 *숫자+판정+law_refs만* 반환, 법령 본문/해석 산문은 절대 반환 안 함(본문은 graph `/api/lookup`).

**하지 말 것** (환각 표면 차단 — 영구 가드레일): 조문 본문·해석 자체 생성 금지(graph 영역), 자치구 고시 PDF 자동파싱 금지(폐지고시 오인 위험), LLM 결정수치 금지, 점수곡선 재발명 금지(골든셋 캘리브레이션만). ※ 법제처 DRF 별표 PDF(현행 시행령 별표, `별표서식PDF파일링크`)는 예외 — 추출값을 seed로 전사 + verify 스크립트로 전수 대조 OK.

---

### 📋 현재 상태

핵심 계산 엔진 운영급 완성(건폐율·용적률·완화 합산·심의 트리거·조례 리졸버 정확). 막힌 건 "데이터"(SHP·고시·brief 샘플 — 외부에서 채울 영역).

| 영역 | 상태 |
| --- | --- |
| 핵심 계산 + 사업성 모드 + UI + PDF/MD/Excel | ✅ 운영급 |
| API 키 (Kakao·VWorld·EUM·LURIS·Claude·법제처) | ✅ 활성 |
| 검증 인프라 (pytest 318건 · CI 게이트) | ✅ |
| brief 연계 (Step 9) | ✅ 동작 (실샘플 `data/briefs/_brief.json` 검증) |
| 일부 SHP 누락 (철도 / 일부 도시계획시설) | ❌ |

### ✅ 완료 이력 (요약)

**2026-05~06월**: Step 5a(법령 수치 검증)·5b(#13~15 주차·다중이용·영향평가 5종)·6(Docker·Cloud Run·디자인 토큰)·7(사업성 초판)·9(brief 연계)·11(법규 그래프 138노드). 버그 5건 fix, pytest CI 게이트, 외부 API 재시도(`http_retry.py`). Step 8(사내 케이스 DB)은 더미라 제거. NSDI 폐기(VWorld 대체)·지구단위계획구역 자동감지·학교(Kakao)·문화재(국가유산청) 좌표 판정·도시계획시설 VWorld WFS 실시간 전환.

**2026-06-29~07-01 정확도·정직성 강화** (배경·원칙 [doc/ACCURACY_SHARPENING_PLAN.md](doc/ACCURACY_SHARPENING_PLAN.md)): 침묵 과대평가 경고 2종(`STREET_BLOCK_UNVERIFIED`·`FACILITY_AREA_UNCORRECTED`) · `aggregate_confidence` 노출 · 정량 4개 카드 `provenance` 블록 · 골든 케이스 12건(용도지역 7종)+합성 경로 4종(`tests/golden/`) · 조례 한도 DB 보강(17개 시도 310건 — 법정 한도 재현 감사로 서울 밖 최대 +810%p 과대평가 발견·해소, 한글수사 추출 버그 fix) · 심의 트리거 감사 + 교통영향평가 임계 정정(별표1 PDF 전수 대조) · 환경영향평가 임계 정밀화(별표4, 도시지역 완전누락 구간 발견·해소) · 별표 PDF 수집 경로 확보(법제처 DRF `별표서식PDF파일링크` + pdfplumber). **실사용 라이브 진단 감사(2026-07-01, 실주소 `/api/diagnose` 호출)**로 3건 추가 발견·수정: 조례 1차추출 needs_review 미게이팅(검증 안 된 조례값이 첫 조회 때 그대로 쓰이던 구멍, `ordinance_resolver.py`) · `data_quality.ordinance_used`가 건폐율만 체크하던 문제(`ordinance_used_bcr`/`ordinance_used_far` 분리) · 진단 1건 레이턴시 114초(국가유산청 8회 순차 호출 + Claude 재시도) → 병렬화로 65초(-43%). 테스트 269→314건.

**2026-07-14 전체 코드 리뷰·수정** (PR #2, 5개 에이전트 종합 리뷰 후 확정건만 수정): CORS `*`→화이트리스트(env `ALLOWED_ORIGINS`) · 자연어질의 `.format()` 인젝션→치환 · HTTP 500 응답에서 내부 예외 메시지 제거(20곳) · 행위제한 `"불가능"⊃"가능"` substring 오분류 정정(`land_use_act.py`) · 공공인증 `permit_year<2020` max() 크래시 폴백(`public_certification.py`) · 주차 제외용도 양방향 substring 오매칭('병원'↔'정신병원') 정정(`parking.py`) · VWorld BBOX 경도 `cos(위도)` 보정(도시계획시설 저촉 과소평가 해소) · `road_width` `gt=0` 검증 · `/health` 버전 동기화 · `pilot_project` 진단경로 스키마 추가(사문화 해소). 회귀 4건 추가. 테스트 314→318건.

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
| 용적률 | `far.py` | 동일 + 완화(공개공지·녹색·ZEB·시범 — 지능형·장수명은 별표9 미포함으로 현재 비활성) |
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

> `backend/main.py`는 FastAPI 라우터만 담당, API 입력 스키마는 `backend/schemas.py`(Pydantic)로 분리되어 있다.

| 파일 | 역할 |
| --- | --- |
| `diagnose_engine.py` | 진단 전체 오케스트레이션 |
| `zone_use_normalizer.py` | 용도지역 표준명 정규화 (19종 + 별칭 31개) |
| `eum_client.py` | 토지이음 7개 API |
| `luris_client.py` | 공공데이터포털 LURIS 행위제한 2개 API (EUC-KR XML) |
| `vworld_client.py` ⚠️ | VWorld WFS 지적 폴리곤 + 지오코딩 (검증 필요) |
| `ordinance_resolver.py` | 조례 cascade 조회. `needs_review=True` 레코드는 자동 skip → 시행령 fallback |
| `ordinance_extractor.py` | 법령 본문 → 건폐율/용적률 수치 추출 (regex + LLM) |
| `land_use_resolver.py` | 토지 정보 조회 + stale 캐시 fallback |
| `far_relief.py` | 용적률 완화 4레버 활성(공개공지·녹색·ZEB·시범)+수동. 지능형·장수명은 규칙 골격만 있고 `by_grade` 값이 비어 있어 현재 0% 기여(별표9 미포함, 원문 확인 전까지 비활성). 인증 합산 캡 15%, 전체 캡 1.15배 |
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
