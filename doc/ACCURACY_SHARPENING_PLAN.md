# 정확도·정직성 강화 계획 (arch-law-diagnose)

> 작성 2026-06-29. 이 문서는 **앞으로 할 작업의 상세 계획**이다.
> CLAUDE.md "⏭️ 다음 작업" 섹션에 요약·포인터가 있고, 이 문서가 그 본문이다.

---

## 0. 배경 — 왜 이 계획인가

자매 앱 **arch-law-graph**(법령 지식·RAG·원문 뷰의 주인)와 역할을 나누는 방향을
논의하던 중, 이 앱(diagnose)의 **정체성을 더 날카롭게** 하자는 결론이 나왔다.

- **diagnose = 결정론적 "대지 판정 계산 엔진".**
  출력은 *숫자 + 판정(RED/YELLOW/GREEN) + 근거 조문 포인터(law_refs)*뿐이다.
- **"이 법조문이 무슨 뜻인가"는 절대 직접 생성하지 않고 graph에 위임한다.**
  (그게 환각의 가장 큰 진입점이기 때문.)
- graph가 "지식의 주인"이면, diagnose는 **"검증 가능한 판정의 주인"**이어야 한다.

"날카롭게 한다"의 정확한 의미:

1. 계산이 더 정확해지고,
2. **자기가 모르는 걸 정확히 안다**(= 침묵 과대평가 제로),
3. 법 해석 영역으로 새지 않는다.

---

## 1. 대원칙 (이 계획 전체의 게이트)

| # | 원칙 | 의미 |
| --- | --- | --- |
| P1 | **기능 유지** | 지금은 MCP/API화·기능 경계 재편을 **하지 않는다.** 있는 기능을 빼거나 바꾸지 않는다. |
| P2 | **추가형 우선** | 지금 단계 작업은 전부 *기존 동작을 0으로 건드리는 추가형*이어야 한다. 신호·점수·답변범위를 바꾸는 건 보류. |
| P3 | **정체성 ≠ 기능 제거** | "정체성을 날카롭게" = *같은 기능을 더 정확하게.* 기능을 빼서 날카롭게 하는 건(예: C) graph가 정식 API로 붙는 그때 일이다. |
| P4 | **환각 표면을 늘리지 않는다** | 정확도를 올린다며 새 추정·새 자동파싱·새 LLM 산정을 들이지 않는다. (§5 "하지 말 것" 참조) |

> **트리거 규칙**: 보류 항목(§4)은 "graph가 백엔드 API로 정식 통합됨"이 충족되기 전에는 착수하지 않는다.

---

## 2. 지금 할 일 (기존 동작 불변 · 추가형)

우선순위 순서: **E → A(노출) → B → D**.
(E·A는 즉시 코드만으로, B는 중간 규모, D는 사내 케이스 데이터 대기)

### E. 침묵 과대평가 구멍 → `data_quality` 경고로 노출 ★먼저 — ✅ 완료 (2026-06-29)

> 구현: [diagnose_engine.py](../backend/services/diagnose_engine.py) 데이터 품질 블록에 2종 추가
> (`STREET_BLOCK_UNVERIFIED` info, `FACILITY_AREA_UNCORRECTED` warn). 신호·점수 불변.
> 테스트: [test_regressions.py](../backend/tests/test_regressions.py) +5건(전체 269 통과).

- **목표**: 자동판정이 약한 항목이 사용자에게 "초록불"로 읽히지 않도록 **명시 경고/플래그만** 추가한다. **신호·점수 로직은 손대지 않는다.**
- **근거 위치**:
  - 신호 로직 [diagnose_engine.py:639-645](../backend/services/diagnose_engine.py#L639) — pass/None/score만 본다.
  - 데이터 품질 경고 구성 [diagnose_engine.py:666-744](../backend/services/diagnose_engine.py#L666) — 이미 `NO_ZONE_USE`·`STALE_CACHE`·`NARROW_ROAD_SETBACK` 등 좋은 선례가 있다. **같은 패턴으로 항목만 추가**한다.
- **대상 구멍(점검 후 해당되면 경고 추가)**:
  - **가로구역 §60**: seed 0건이라 `street_block_max_height_m`가 없으면 §60 자동판정이 사실상 미수행. 높이 결과가 가로구역 한도 없이 "통과"로 보일 때 → `STREET_BLOCK_UNVERIFIED` 같은 경고("가로구역 최고높이 미확인 — §60 자동판정 미수행, 자치구 고시 확인 필요").
  - **도시계획시설 면적보정**: `parcel_geometry`가 없어 자동 산정을 못 했을 때(폴리곤 미확보) → 보정 미수행을 경고로(현재는 조용히 skip).
  - (이미 처리됨 — 추가 불필요) 정북 일조 미입력은 `pass=None`→YELLOW로 잘 떨어진다([height.py:153-166](../backend/services/calculator/height.py#L153)). 좁은 도로 후퇴도 경고 있음.
- **완료 기준**: 해당 케이스에서 `data_quality.issues`에 새 code가 뜬다 + 회귀 테스트 +N건. **신호 값은 동일**(테스트로 불변 확인).
- **환각 위험**: 0 (표시만 추가).

### A(노출만). 종합 신뢰도 `aggregate_confidence` 노출 — ✅ 완료 (2026-06-29)

> 구현: [diagnose_engine.py](../backend/services/diagnose_engine.py)에서 `_weighted_score`가 버리던
> 최저 confidence를 `data_quality.aggregate_confidence`(1~5)로 노출 + [DataQualityBanner](../frontend/src/components/DataQualityBanner/index.jsx)에
> "신뢰도 N/5" 배지. 신호·점수 불변. 이력은 JSON blob → 스키마 ALTER 불필요.
> 테스트 +1(전체 270) + 프론트 빌드 통과.

- **목표**: 지금 **계산해 놓고 버리는** 신뢰도 최솟값을 응답에 노출한다. **신호 로직은 안 건드린다.**
- **근거 위치**: [diagnose_engine.py:626](../backend/services/diagnose_engine.py#L626) — `overall, _confidence_min = _weighted_score(results)`에서 `_confidence_min`이 `_` 프리픽스로 버려진다. `_weighted_score`는 [diagnose_engine.py:814-837](../backend/services/diagnose_engine.py#L814)에서 항목별 `confidence` 최솟값을 이미 구한다.
- **구현 개요**:
  - `_confidence_min`을 받아 `data_quality["aggregate_confidence"]`(1~5)로 넣는다.
  - 프론트 `DataQualityBanner`에 "종합 신뢰도 N/5" 표시(선택).
- **완료 기준**: 응답 `data_quality.aggregate_confidence` 필드 존재 + 테스트. **신호·점수 불변.**
- **주의**:
  - 신호를 이 값으로 **게이팅하지 않는다**(그건 §4의 보류 항목).
  - 진단 이력 저장([diagnose_engine.py:790-794](../backend/services/diagnose_engine.py#L790))에 새 필드가 함께 저장되면 `cache_manager` 스키마 점검(프로젝트 규칙: 응답 새 필드 ↔ 스키마 ALTER). 단순 응답 파생 필드면 ALTER 불필요할 수 있으니 저장 경로 확인.
- **환각 위험**: 0.

### B. 산정 근거(provenance) 블록 추가 — ✅ 백엔드 완료 (2026-06-29)

> 구현: 정량 4개 계산기([coverage](../backend/services/calculator/coverage.py)·[far](../backend/services/calculator/far.py)·[height](../backend/services/calculator/height.py)·[parking](../backend/services/calculator/parking.py))
> 반환에 `provenance{inputs, formula, computed, basis}` 추가. `law_refs`는 top-level 그대로 두고
> 중복하지 않음(분기 위험 회피). 계산이 일어난 카드에만 부착(확인불가 분기는 산식이 없어 생략).
> 기존 필드·동작 불변. 테스트 +2(전체 272).
> 프론트: [DiagnoseResult](../frontend/src/components/DiagnoseResult/index.jsx) 카테고리 카드
> 펼침에 "🧮 산정 근거" 접이식(`ProvenanceBlock`, 입력값·산식·산출 + 키→한글 라벨). 빌드 통과.
> ⏳ 선택(미착수): LegalReviewReport(인쇄 검토서)에도 산정 근거 노출.

- **목표**: 각 정량 카드에 `{입력값, 공식, 결과, 근거조문}`을 **한 블록**으로 묶어 추가한다. **기존 필드는 그대로 둔다(추가형).**
- **근거 위치**: `law_refs`(조문 포인터)는 이미 계산기마다 결정론적으로 있다([coverage.py:117](../backend/services/calculator/coverage.py#L117), [height.py:252](../backend/services/calculator/height.py#L252)). 다만 *입력값·공식*은 카드마다 흩어져 있고(`site_correction`은 별도, `actual_pct`는 결과 안) 한 곳에 모여 있지 않다.
- **구현 개요(예: 건폐율)**:
  ```jsonc
  "provenance": {
    "inputs": {"building_area": 480, "site_area_effective": 1000, "site_area_original": 1000},
    "formula": "건폐율 = 건축면적 / 대지면적 × 100",
    "result_pct": 48.0,
    "limit_pct": 60,
    "limit_source": "🏛 조례 — ...",
    "law_refs": [ ... 기존 그대로 ... ]
  }
  ```
  - 정량 4개(건폐율·용적률·높이·주차)부터. 조경·행위제한은 다음.
  - `LegalReviewReport`/`DiagnoseResult`가 이 블록을 표시에 활용 가능(검토서 추적성↑).
- **완료 기준**: 정량 4개 카드 `provenance` 포함 + 테스트. 기존 필드·동작 불변.
- **주의**: 지금 단계에서 가장 큰 작업. MCP 없이도 **검토 보고서 추적성**에 바로 값이 있으나, 우선순위는 E·A 뒤.
- **환각 위험**: 0 (이미 계산한 값을 재구성·노출만).

### D. 골든 케이스 회귀셋 (계산 엔진 #1 정확도 자산) — ✅ 골격+실제 10건 (2026-06-29)

> 구현: [tests/golden/](../backend/tests/golden/) (익명화 JSON, 스키마는 [golden/README.md](../backend/tests/golden/README.md))
> + [test_golden_cases.py](../backend/tests/test_golden_cases.py) (조례 stub + `_diagnose` skip_ai 결정론, 외부 API 미호출,
> actual_pct ±0.01%p 허용으로 원문 절사 흡수).
> M드라이브 실 인허가 건축개요서 **10건**(식별정보 전부 제외·수치만). **용도지역 6종**: 일반상업·준주거·
> 제2종일반주거·제3종일반주거·중심상업·지구단위. **유형**: 오피스텔·주거복합·재개발/재건축 아파트·주상복합·업무·교육.
> 다수가 법정/허용/상한 **면도날 통과**(예 용적률 299.99/300, 489.99/490, 699.80/700)를 엔진이 정확 재현.
> 테스트 +10(전체 282). ⏳ 남은 용도지역(1종일반주거·전용주거·근린/유통상업·준공업·녹지)·시설(근생·숙박·의료·물류)은
> golden/ 에 JSON만 추가하면 자동 수집(후보 카탈로그 scratchpad `m_cat2.tsv`·`m_gaeyo.tsv`·`m_hits.tsv`).



- **목표**: **실 인허가 통과 사례**의 주소→정답(건폐율·용적률·완화 내역·심의 결과)을 end-to-end로 고정한다. 재빌드/리팩터가 정답을 깨면 CI가 잡는다.
- **제거된 Step 8과의 차이**: Step 8은 케이스 *매칭*(추천)이었고 더미라 제거됐다. 이건 **정답 측정(ground-truth)**으로, 매칭 로직이 아니라 *회귀 테스트*다.
- **구현 개요**:
  - `backend/tests/golden/` + 케이스 JSON(주소·건물스펙·기대 결과).
  - 외부 API는 모킹(respx) 또는 고정 `land_info` 주입(`diagnose_fast` 경로)으로 결정론화 → 네트워크 없이 재현.
  - `DiagnoseEngine` 통과 결과와 기대값 비교(핵심 수치 + 신호).
  - CI 게이트(`deploy.yml` test job)에 포함.
- **의존**: 사내 케이스 데이터(사용자 수집). 케이스당 30~60분. **코드 골격은 지금 가능**, 데이터는 대기.
- **완료 기준**: 케이스 N건이 CI에서 통과.
- **환각 위험**: 0 (측정이지 새 주장이 아님).

---

## 3. 작업 순서 권장

```text
1) E  (침묵 과대평가 경고)      ← 즉시, 가장 안전, 신호 불변
2) A  (aggregate_confidence)    ← 즉시, 버려지는 값 노출, 신호 불변
3) B  (provenance 블록)         ← 중간 규모, 추적성 가치
4) D  (골든 케이스 회귀셋)       ← 골격은 지금, 케이스 데이터 모이면 최우선 승격
```

---

## 4. 보류 (기존 동작 변경/제거 수반 → graph 정식 API 통합 시)

> 트리거(§1 P-규칙): **graph가 백엔드 API로 정식 통합**되기 전엔 착수하지 않는다.

| 항목 | 왜 보류 | 통합 시 할 일 |
| --- | --- | --- |
| **C. QueryBox 일반 법령 Q&A 축소·graph 링크아웃** | 기능 *축소*다. graph가 API로 안 붙은 지금 빼면 앱이 그냥 나빠진다. | 진단 무관 질문은 graph로 링크아웃, diagnose는 "진단 결과 종속 어시스턴트"로 좁힘. **지금은 일반 질문도 답하되 graph 원문 그라운딩(A안)으로 환각만 억제 — 그대로 유지.** |
| **A(게이팅). confidence로 GREEN→YELLOW** | 판정 로직 *변경*이라 "원래 기능"을 건드린다. | `aggregate_confidence` 임계로 GREEN 게이팅. 별도 사용자 결정 후. |
| **MCP/API 도구화 + 계약** | 합치는 단계 일. | 각 계산기를 명시 타입 입출력 도구로 노출. 불변식: **diagnose 도구는 숫자+판정+law_refs만 반환, 법령 본문/해석 산문은 절대 반환 안 함.** 합친 앱이 law_refs 포인터를 graph `/api/lookup`에 넘겨 본문을 받음. |

---

## 5. 하지 말 것 (환각 표면 차단 — 영구 가드레일)

- ❌ **조문 의미 설명·본문 인용을 diagnose가 자체 생성** — graph 영역. 새면 즉시 환각원.
- ❌ **가로구역/고시 PDF 자동 파싱** — 폐지고시 오인·환각 위험으로 이미 보류한 판단을 **유지.** 수동 입력만.
- ❌ **LLM이 결정 가능한 수치(건폐율·용적률·주차대수 등)를 만들게 하기** — 룰 계산은 코드로. LLM은 정성(설비·소방)·요약·보조 의견만(기존 원칙).
- ❌ **점수 곡선([coverage.py:58-68](../backend/services/calculator/coverage.py#L58) 류)을 재설계해 "정밀도"를 흉내** — 임의 휴리스틱을 더 정교하게 보이게 만들면 *가짜 정밀도*가 된다. 점수는 D(골든셋)으로 **캘리브레이션만**, 곡선 자체를 새로 발명하지 않는다.

---

## 6. 검증 가능한 "끝났다"의 정의

- **E**: 대상 구멍 케이스에서 `data_quality.issues`에 새 경고 code가 뜨고, **같은 입력의 신호 값은 변하지 않음**을 테스트가 증명.
- **A**: 응답에 `aggregate_confidence`(1~5)가 있고, 신호·점수는 회귀 테스트상 불변.
- **B**: 정량 4개 카드에 `provenance`가 있고 기존 필드·키가 모두 유지됨(스냅샷 테스트).
- **D**: 골든 케이스 N건이 CI에서 통과, 임의 리팩터가 정답을 깨면 실패.

> 공통: 이 계획의 어떤 항목도 **기존 진단 응답의 기존 필드·신호·점수를 바꾸지 않는다**(추가형). 바꾸는 건 전부 §4 보류.
