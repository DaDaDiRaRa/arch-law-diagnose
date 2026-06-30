# arch-law-diagnose — 시스템 스펙

> 코드에서 역추론한 문서. 불확실한 부분은 **[추정]** 으로 표시.  
> 최종 업데이트: 2026-06-30 (정확도·정직성 강화 반영: data_quality 경고 2종·aggregate_confidence·provenance·골든 테스트셋)

---

## 1. 시스템 목적

건축사무소 내부 전용. 주소 + 건물 계획 수치를 입력하면 건축 인허가 전에 8개 법규 카테고리를 자동 점검해 **GREEN / YELLOW / RED** 신호와 종합 점수(0~10)를 반환한다.

**핵심 사용 흐름:**
1. 설계 초기 — 대지 적합성·최대 건폐율/용적률 빠른 확인
2. 설계 중간 — 계획안이 법정 한도를 초과하는지 즉시 체크
3. 공모 참여 — 공모지침(brief) 요구치 vs 법정 한도 갭 분석 (사업성 모드)
4. 검토 보고 — PDF·Excel 한 장 요약 출력

---

## 2. 시스템 아키텍처

```
┌──────────────────────────────────────────────────────────────┐
│                      브라우저 (SPA)                           │
│   React 18 + Vite + Tailwind                                  │
│   ├── 주소 검색 / 건물 입력 (InputForm)                       │
│   ├── 진단 결과 카드 (DiagnoseResult)                         │
│   ├── What-If 슬라이더 (WhatIfPanel)                          │
│   ├── 사업성 모드 (FeasibilityMode / BriefList)               │
│   ├── 법규 의미 그래프 (LawGraphPanel — react-flow)           │
│   └── 보고서 출력 (LegalReviewReport)                         │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTP (포트 8000 로컬 / 8080 Docker)
┌────────────────────────▼─────────────────────────────────────┐
│                  FastAPI 백엔드 (Python 3.12)                 │
│                                                               │
│  POST /api/diagnose         → DiagnoseEngine.run()           │
│  POST /api/diagnose/whatif  → DiagnoseEngine (fast re-calc)  │
│  POST /api/diagnose/multi   → MultiParcel 합필 진단          │
│  POST /api/feasibility/run  → FeasibilityEngine              │
│  GET  /api/law-graph        → LawGraph (networkx)            │
│  POST /api/query            → QueryEngine (Claude RAG)       │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              DiagnoseEngine (오케스트레이터)           │    │
│  │  ① 토지 정보 조회 (VWorld / 캐시)                     │    │
│  │  ② 도시계획시설 저촉 (VWorld WFS 실시간)               │    │
│  │  ③ 대지면적 보정 (시설 저촉분 제외)                    │    │
│  │  ④ 조례 조회 (OrdinanceResolver cascade)              │    │
│  │  ⑤ 특례 적용 (재정비촉진 / 리모델링 / 공공임대)        │    │
│  │  ⑥ 용적률 완화 계산 (FarRelief — 6종 레버)            │    │
│  │  ⑦ 8개 계산기 병렬 실행                               │    │
│  │  ⑧ 심의 트리거 자동 판정                               │    │
│  │  ⑨ 가중평균 종합점수 → 신호 판정                       │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  SQLite (`./data/arch_law.db`)                                │
│  ├── 조례 캐시 (30일 TTL)                                     │
│  └── 진단 이력 (히스토리)                                     │
└────────────────────────┬─────────────────────────────────────┘
                         │
        ┌────────────────┼─────────────────────┐
        ▼                ▼                     ▼
  VWorld API        EUM / LURIS            Anthropic Claude
  (용도지역·         (행위제한·             (설비소방 정성판단
   WFS 실시간)       법령정보)              + 조례 수치 추출)
        │
        ▼
  법제처 DRF          Kakao Local           arch-law-graph
  (조례 본문)         (주소 자동완성        (조문 원문 RAG,
                      + 학교 근접)          graceful degrade)
        │
        ▼
  국가유산청 GIS (spca.do — 지정문화재 근접, 문화재심의 트리거)
```

---

## 3. 입력 스펙

### 3-1. 기본 진단 (`POST /api/diagnose`)

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `address` | string | ✅ | 도로명 또는 지번 주소 |
| `lat` / `lng` | float | — | 좌표 (주소 선택 시 자동 채움) |
| `pnu` | string | — | 법정동 코드+번지 19자리 |
| `zone_use` | string | ✅ | 용도지역 (예: `제2종일반주거지역`) |
| `site_area` | float | ✅ | 대지면적 (㎡) |
| `building_area` | float | ✅ | 건축면적 (㎡) |
| `total_floor_area` | float | ✅ | 연면적 전체 (㎡) |
| `floor_area_above` | float | — | 지상층 연면적 (용적률 산정용; 없으면 total 사용) [추정] |
| `height` | float | ✅ | 건물 높이 (m) |
| `floors_above` | int | ✅ | 지상 층수 |
| `floors_below` | int | — | 지하 층수 |
| `building_use` | string | ✅ | 건축물 용도 (건축법 19개 분류) |
| `units` | int | — | 세대수 (공동주택) |
| `provided_parking_spaces` | int | — | 계획 주차 대수 |
| `north_setback_m` | float | — | 정북 이격거리 (m); 없으면 §61 pass=None |
| `road_width_m` | float | — | 접도 너비 (m) |
| `jurisdiction_code` | string | — | 시군구코드 (조례 조회용; PNU 있으면 자동 파생) |
| `applicant_type` | string | — | `공공기관` / `민간` (공공인증 의무 판정용) |
| `green_grade` | string | — | 녹색건축 인증 등급 (완화 적용용) |
| `energy_grade` | string | — | 제로에너지 등급 (문자열: `1++`/`1+`/`1`~`5`). 엔진은 `zero_energy_grade`도 허용 |
| `far_limit_manual_override` | float | — | 용적률 상한 수동 지정 (심의 결정값 등) |
| `building_agreement` | bool | — | 건축협정 여부 (§110의7 완화 적용) |
| `skip_fire_safety` | bool | — | AI 설비소방 판단 생략 (빠른 재계산용) |

**용도지역 표준화**: 모든 `zone_use` 값은 `zone_use_normalizer.py`의 `normalize()`를 거쳐 19개 표준명 + 별칭 61개 매핑. 매칭 실패 시 `None` → 전 항목 `pass=None`.

### 3-2. 사업성 모드 추가 필드 (`POST /api/feasibility/run`)

| 필드 | 설명 |
|------|------|
| `target_far_pct` | 공모 요구 용적률 (%) |
| `target_coverage_pct` | 공모 요구 건폐율 (%) |
| `target_height_m` | 공모 요구 최고높이 (m) |
| `target_parking` | 공모 요구 주차 대수 |
| `target_floor_area` | 공모 요구 연면적 (㎡) |
| `brief_id` | `data/briefs/` 디렉토리의 공모지침 파일명 (자동 채움) |

---

## 4. 핵심 진단 흐름

```
DiagnoseEngine.run(req)
│
├─ 1. LandUseResolver.get()
│      VWorld WFS → 용도지역·지역지구·도로폭·지적 폴리곤
│      실패 시: stale 캐시 사용 → data_quality.fallback = true
│
├─ 2. VWorld WFS urban_facility 조회 (lt_c_upisuq151~159 레이어)
│      대지 폴리곤 ∩ 시설 폴리곤 → 저촉 여부 + 저촉면적 산정
│      실패 시: 로컬 SHP 폴백 (SHP_ROOT 환경변수 경로)
│
├─ 3. 대지면적 보정
│      effective_site_area = site_area - 저촉면적
│      (도시계획시설 저촉분은 건폐율·용적률 산정 기준면적에서 제외)
│
├─ 4. OrdinanceResolver.resolve(jurisdiction_code, zone_use, category)
│      ┌─ DB 캐시 HIT → 즉시 반환
│      ├─ MISS → 법제처 API 조회 + LLM 수치 추출 → DB 저장
│      └─ 실패 → zone_limits.json 시행령 기본값 (fallback)
│
├─ 5. 특례 적용 (T3)
│      재정비촉진구역: FAR 1.2배 [추정]
│      공공지원민간임대: 추가 완화
│      리모델링 기준: 별도 한도 [추정]
│
├─ 6. FarRelief.compute_relief()
│      6종 완화 레버 자동 합산 → final_far_limit_pct
│      (상세 로직은 §7 참고)
│
├─ 7. asyncio.gather — 8개 계산기 병렬 실행
│      ├─ coverage.calculate()
│      ├─ far.calculate()
│      ├─ height.calculate()
│      ├─ parking.calculate()
│      ├─ landscape.calculate()
│      ├─ land_use_act.calculate()  ← LURIS + EUM 교차검증
│      ├─ urban_facility.calculate() ← 2에서 수집한 시설목록 사용
│      └─ fire_safety.calculate()   ← Claude AI (skip 가능)
│
├─ 8. BuildingAgreement 후처리 (§110의7)
│      building_agreement=True → 건폐율·용적률 상한 ×1.2 (최대 20% 완화)
│
├─ 9. ReviewTriggers.evaluate()
│      11종 심의 자동 판정 (§4-3 참고)
│
└─ 10. _weighted_score() → GREEN / YELLOW / RED
       (§6 참고)
```

---

## 5. 카테고리별 계산 로직

> **산정 근거(provenance) — 2026-06-30 추가**: 정량 4개 카드(건폐율·용적률·높이·주차)는 반환에 `provenance{inputs, formula, computed, basis}`를 함께 실어, 어떤 입력·산식으로 그 수치가 나왔는지 자가기술한다(기존 필드 불변). 프론트는 카드 펼침의 "🧮 산정 근거"로 표시.

### 5-1. 행위제한 (`land_use_act.py`)

**목적**: 해당 용도지역에 계획 건물 용도가 허용되는지 판정.

```
LURIS iuRlStle API  ──┐
                      ├→ 교차검증 → 최종 verdict
EUM  act_info API  ──┘
```

| 상황 | pass | confidence |
|------|------|------------|
| 두 소스 모두 허용 | True | 5 |
| 두 소스 모두 불허 | False | 5 |
| 한쪽만 데이터 보유 | 해당 소스 verdict | 4 |
| verdict 불일치 | None | 2 |
| 양쪽 조회 실패 | None | 1 |

- `ucode_mapping.json`: 용도지역 코드 ↔ LURIS UCODE 매핑
- 허용/불허 판단 로직에 조건부 허용(용도 변경 가능, 심의 후 가능 등) 처리 포함 [추정]

---

### 5-2. 도시계획시설 (`urban_facility.py`)

**목적**: 대지가 도시계획시설(도로·공원·학교 등) 결정 구역에 저촉되는지 판정.

**데이터 소스 우선순위:**
1. VWorld WFS 실시간 (`lt_c_upisuq151~159`, 9개 레이어) — 주력
2. 로컬 SHP 폴백 (`SHP_ROOT` 환경변수)

**저촉 판정:**
```
저촉면적 = 대지 폴리곤 ∩ 시설 폴리곤 (shapely.intersection)
저촉비율 = 저촉면적 / 대지면적

저촉비율 == 0     → GREEN (pass=True,  score=10)
0 < 비율 < 임계치 → YELLOW (pass=None, score=5)   [추정: 임계치는 config]
비율 ≥ 임계치     → RED   (pass=False, score=0)
좌표 없음         → pass=None, score=null, confidence=1
```

**법적근거**: 국토계획법 §47(매수청구), §64(건축 제한), §65(실시계획 고시 시 효력)

---

### 5-3. 건폐율 (`coverage.py`)

**산식**: 건폐율(%) = 건축면적 / 대지면적 × 100

**한도 결정 (cascade):**
```
①  조례 DB 캐시 (OrdinanceResolver)
②  법제처 API → LLM 수치 추출 → DB 저장
③  zone_limits.json 시행령 기본값 (최종 fallback)
```

건축협정 적용 시: 한도 × 1.2 (사후 보정)

**점수 산식** [추정]:
```
건폐율 / 한도 ≤ 0.7  → 10점
          ≤ 0.9  →  8점
          ≤ 1.0  →  6점
          > 1.0  →  0점 (pass=False)
```

**법적근거**: 건축법 §55, 국토계획법 시행령 §84

---

### 5-4. 용적률 (`far.py`)

**산식**: 용적률(%) = 지상층 연면적 / 대지면적 × 100

제외 항목 (용적률 산정 분모 및 분자):
- 지하층 면적
- 피난안전구역 면적 (초고층)
- 경사지붕 아래 대피공간
- 부속 용도 주차장 (지상·지하 포함) [추정]

**한도 결정**: 건폐율과 동일 cascade + FarRelief 완화 추가 적용

**점수 산식** (`far.py` — 건폐율과 동일 곡선):
```
용적률 / 한도 ≤ 0.7  → 10점
          ≤ 0.9  →  8점 (선형 보간)
          ≤ 1.0  →  6점 (선형 보간)
          > 1.0  →  0점 (pass=False)
```

**법적근거**: 건축법 §56, 시행령 §119, 국토계획법 시행령 §85

---

### 5-5. 높이·일조 (`height.py`)

**두 가지 독립 규정:**

#### (A) 가로구역별 최고높이 (§60)
```
조회 소스: street_block_heights.json (현재 비어 있음)
값 있으면: 건물높이 > 지정높이 → pass=False(RED), 이하 → 통과
값 없으면: §60 자동판정 미수행. height 카드 pass 를 None 으로 고정하지 않음
           (일조 판정으로 결정). data_quality 에 STREET_BLOCK_UNVERIFIED(info) 경고
허가권자(자치구청장) 개별 고시 → 구조화 API 없음, 수동 seed 만 가능
```

#### (B) 일조 사선 (§61 + 시행령 §86, 2023.9.12 개정)

적용 대상: 주거지역(전용·일반·준주거)에서 정북 방향 인접대지

```
정북방향 이격 요구치:
  건물 높이 ≤ 10m: 1.5m 이상
  건물 높이 > 10m: 높이 × 0.5 이상

예) 20m 건물 → 10m 이상 이격 필요
```

**적용 제외 조건** (§86 ②항):
- 너비 20m 이상 도로에 접한 대지
- 건축협정구역 내 대지
- 정북 인접대지가 비주거지역

**판정 로직:**
```
north_setback_m 입력됨 AND 인접지 용도 입력됨
  → pass/fail 자동 계산 (confidence 4~5)
그 외
  → pass=None + 위험도 기반 score (confidence 1~2)
```

---

### 5-6. 주차 (`parking.py`)

**근거**: 주차장법 시행령 별표 1

**산정 방식 3종:**

| 타입 | 기준 | 적용 용도 예시 |
|------|------|--------------|
| `area_based` | 연면적 N㎡당 1대 | 근린생활시설, 업무시설 |
| `unit_based` | 세대당 N대 | 공동주택 |
| `count_based` | 시설 수(홀/타석/정원)당 N대 | 골프장, 골프연습장, 관람장, 옥외수영장 |

**특수 처리:**
- 학생용 기숙사: 별도 기준 적용
- 데이터센터: 별도 기준 적용
- 주차장법 제외 대상: 연면적 50㎡ 이하 등 [추정]

**점수 산식** (`parking.py`):
```
provided < required  → 0점 (pass=False, RED) — 부족 시 중간 YELLOW 단계 없음
provided ≥ required  → 7 + (여유분 / required) × 3, 최대 10점 (pass=True)
                       (딱 맞으면 7점, 넉넉할수록 10점)
provided 미입력      → required만 계산, pass=None (계획 대수 입력 시 판정)
```

---

### 5-7. 조경 (`landscape.py`)

**근거**: 건축법 §42 + 시행령 §27 + 조경기준 고시(국토부 고시 제2021-1778호)

**면제 대상** (시행령 §27 ①):
- 녹지지역 건축물
- 면적 5,000㎡ 미만 또는 연면적 1,500㎡ 미만 공장
- 산업단지 내 공장
- 축사, 가설건축물
- 연면적 1,500㎡ 미만 물류시설
- 자연환경보전·농림·관리지역

**의무 조경비율**: 조례 위임 (confidence 3 — 지자체 확인 필요)

**옥상조경 인정**: 인정 비율 최대 50% [추정]

**식재 기준** (고시 §7):
```
용도지역별 교목 최소 수량 (1주/N㎡):
  상업지역: 1주/10㎡ (교목), 1주/1.0㎡ (관목)
  공업지역: 1주/3㎡  (교목), 1주/1.0㎡ (관목)
  주거·녹지: 1주/5㎡  (교목), 1주/1.0㎡ (관목)
```

---

### 5-8. 설비·소방 (`fire_safety.py`)

**특징**: Claude AI 기반 정성 판단. 결정론적 계산 불가 영역.

**검토 대상 법규:**
- 건축법 시행령 §34·35: 직통계단·피난계단 수 및 너비
- 건축법 시행령 §46: 방화구획 (1,000㎡ 또는 3,000㎡마다)
- 건축법 시행령 §89·90: 승강기·비상용 승강기 설치 의무
- 소방시설설치 및 관리법 시행령 별표4: 스프링클러·옥내소화전
- 다중이용업소 안전관리법

**AI 판단 구조:**
```python
items = [
  {rule, requirement, estimated_result, pass, confidence, note},
  ...
]
```

**Graceful degrade**: `ANTHROPIC_API_KEY` 미설정 시 `pass=None`, "수동 검토 필요" 안내

---

## 6. 용적률 완화 시스템 (FarRelief)

**근거**: 건축법 시행령 §27의2 + 녹색건축물 조성 지원법 §15 + 에너지절약설계기준(고시 제2025-738호)

### 완화 레버 6종

| 종류 | 완화율 | 근거 |
|------|--------|------|
| 공개공지 | 의무 초과분 비례 (최대 cap) | 건축법 §43 |
| 녹색건축 최우수 | +6% | 고시 별표9 |
| 녹색건축 우수 | +3% | 고시 별표9 |
| 제로에너지(ZEB) 1등급 | +15% | 고시 별표9 |
| 제로에너지(ZEB) 5등급 | +11% | 고시 별표9 |
| 시범사업 | +10% | 고시 별표9 |
| 지능형(Smart) | — | 별표9 미포함, 미적용 |
| 장수명주택 | — | 별표9 미포함, 미적용 |

### 합산 캡 규칙
```
인증 완화 합산 ≤ 15%        (cert_cap)
전체 완화 후 한도 ≤ base × 1.15  (overall_cap_ratio)
둘 중 작은 값 적용
```

### 사후 보정: 건축협정 (§110의7)
```
건축협정구역 지정 시: 건폐율·용적률 한도 × 1.2 (20% 범위 내 완화)
→ FarRelief 계산 후 DiagnoseEngine에서 별도 사후 적용
```

---

## 7. 종합 점수 및 신호 판정

### 가중 평균 점수

```
종합점수 = Σ(카테고리 점수 × 가중치) / Σ가중치
```

**카테고리별 가중치** (`law_scoring_weights.json`):

| 카테고리 | 가중치 | 가중치 선정 이유 |
|---------|--------|----------------|
| 용적률 | 20 | 사업성 직결, 인허가 거부 사유 1위 추정 |
| 높이·일조 | 15 | 방화·피난·일조사선 복잡 |
| 행위제한 | 14 | 용도 자체 허용성 (위반 시 모든 검토 무의미) |
| 주차 | 14 | 미달 시 인허가 불가 |
| 도시계획시설 | 12 | 저촉 시 건축불가·매수청구 대상 |
| 건폐율 | 12 | 기본 비율, 초과 시 인허가 불가 |
| 조경 | 7 | 지자체별 편차 크지만 통상 10% 수준 |
| 설비·소방 | 6 | 법규 분량 최대이지만 V1은 AI 정성 판단만 |
| 공공시설_의무인증 | 0 | 점수 미반영 (정보 카드) |
| BF_인증 | 0 | 점수 미반영 (정보 카드) |
| 범죄예방_건축기준 | 0 | 점수 미반영 (정보 카드) |

### 신호 판정

```
어느 카테고리든 pass=False 존재     → 🔴 RED   (위반)
어느 카테고리든 pass=None 존재
  OR 종합점수 < 7.0               → 🟡 YELLOW (확인 필요)
모든 카테고리 pass=True
  AND 종합점수 ≥ 7.0              → 🟢 GREEN  (통과)
```

### 개별 카테고리 점수 (0~10)

| 범위 | 해석 |
|------|------|
| 9~10 | 여유 있음 |
| 7~8 | 적정 |
| 5~6 | 한도 근접 (YELLOW 가능) |
| 3~4 | 요주의 |
| 0~2 | 위반 또는 확인 불가 |

### Confidence (신뢰도, 1~5)

| 값 | 의미 |
|----|------|
| 5 | 교차검증 완료 또는 원문 직접 확인 |
| 4 | 단일 소스 검증 |
| 3 | 조례 확인 필요 (시행령 추정값 사용) |
| 2 | 두 소스 불일치 또는 입력 부족 |
| 1 | 데이터 불충분 — 판정 불가 |

**종합 신뢰도 노출 (2026-06-29 추가)**: `data_quality.aggregate_confidence`(1~5) = 채점에 기여한 카테고리 중 **최저 confidence**. *노출만* 하며 신호(RED/YELLOW/GREEN) 판정에는 사용하지 않는다. 프론트 DataQualityBanner 에 "신뢰도 N/5" 배지로 표시.

---

## 8. 사업성 모드 (FeasibilityEngine)

DiagnoseEngine의 래퍼. 법정 최대값과 공모 요구치(target)를 비교해 갭 분석과 대안 제안을 수행.

### 갭 분석 흐름

```
① DiagnoseEngine.run() → 법정 최대값 계산
② target_* vs 법정 최대값 비교 (per 항목)
③ 갭 상태 분류:
     충족: target ≤ 법정 최대
     초과: target > 법정 최대 (RED)
     확인불가: target 없음 or 판정 데이터 부족
④ 완화 시나리오 3종 자동 생성 (What-If)
⑤ 심의 부담 점수 계산
⑥ 참여 추천: "적합" / "협상 가능" / "패스"
```

### 자동 시나리오 3종 [추정]

| 시나리오 | 완화 조건 |
|---------|---------|
| 기본안 | 완화 없음 |
| 친환경 표준 | 녹색건축 최우수(+6%) + ZEB 3등급 |
| 용적률 최대 | 녹색건축 최우수(+6%) + ZEB 1등급(+15%) |

### Brief 연계 (Step 9)

`data/briefs/` 디렉토리 (`_briefs/` GCS 버킷 GCSFUSE 마운트 가능)에서 `_brief.json` 파일 읽기.

```
brief_importer.map_brief() 자동 매핑:
  주소 → address
  (괄호) 용도 힌트 → building_use 추정
  규모 → target_* 자동 채움
  공공기관 여부 → applicant_type
  완화레버 기재 여부 → green_grade 등 사전 설정
```

---

## 9. 자연어 질의 (QueryEngine)

진단 결과 JSON에 종속된 어시스턴트. 일반 법령 Q&A 아님.

### 동작 흐름

```
① 진단 결과의 law_refs 수집 (_collect_law_refs)
② arch-law-graph /api/lookup 호출 → 조문 원문 확보 (A안)
   실패 시: 조문 원문 없이 계속 (graceful degrade)
③ 프롬프트 구성:
   - 주소·용도지역·현재 시나리오
   - 진단 결과 JSON (카테고리별 판정 값)
   - 적용 조문 (진단 엔진 확정) — 블록 주입
   - 조문 원문 텍스트 (graph RAG, 최대 10건·건당 900자)
④ Claude API 호출 (temperature=0, prompt caching)
⑤ 구조화 응답:
   { answer, citations[], confidence, follow_ups[] }
```

**핵심 제약**: 원문에 있는 내용만 인용 (환각 방지). 조문 원문이 없으면 "원문을 확인할 수 없습니다" 명시.

---

## 10. 심의 트리거 (ReviewTriggers)

11종 자동 판정. 결과는 `required` / `maybe` / `not_required`.

| 심의 종류 | 트리거 조건 |
|---------|-----------|
| 건축위원회 | 특수 구조, 특수 용도, 100m 초과 [추정] |
| 교통영향평가 | 연면적 기준 (용도별 다름) |
| 경관심의 | 경관지구 또는 높이 기준 초과 |
| 재해영향평가 | 재해위험지구 또는 규모 기준 [추정] |
| 교육환경평가 | 학교 경계 50m/200m 이내 (`school_client` Kakao Places 자동 조회; 좌표 없으면 `maybe`) |
| 문화재심의 | 문화재 경계 100~500m 이내 (`heritage_client` 국가유산청 GIS 자동 조회; 좌표 없으면 `maybe`) |
| 환경영향평가 | 보전지역·생태자연도 (데이터 미보유 시 `maybe`) |
| 도시계획위원회 | 지구단위계획구역 내 (VWorld WFS `lt_c_upisuq161` 좌표 자동 감지 → `zone_district` 보강) |
| 지하안전평가 | 굴착깊이 10m 이상 또는 연면적 기준 [추정] |
| 건축물 안전영향평가 | 초고층(50층↑ or 200m↑) OR 연면적 10만㎡ 이상 AND 16층 이상 |
| 범죄예방 검토 | 대상 용도 해당 시 |

---

## 11. 법규 의미 그래프 (LawGraph)

NetworkX DiGraph. 진단 엔진과 독립적인 참조용 조문 관계 탐색기.

```
nodes: 138개 (seed 49 + auto 수확 89) [추정]
  - origin="seed": 수동 검증된 시드
  - origin="auto": 법제처 API 자동 수확 (신뢰도 낮음)
edges: 조문 간 인용·위임 관계

API:
  GET /api/law-graph           → 전체 그래프 JSON
  GET /api/law-graph/node/{id} → 노드 상세
  GET /api/law-graph/neighbors/{id} → 이웃 노드
```

**프론트 렌더**: react-flow 캔버스 (lazy import) + 카테고리→그래프 점프 + arch-law-graph 링크아웃

---

## 12. 외부 API 의존성 및 Graceful Degrade 전략

| API | 필수 여부 | 실패 시 동작 |
|-----|---------|------------|
| VWorld | 준필수 | stale 캐시 사용. 캐시도 없으면 `pass=None` |
| EUM (토지이음) | 권장 | LURIS 단독으로 행위제한 판정 |
| LURIS | 권장 | EUM 단독으로 판정 |
| 법제처 DRF | 권장 | zone_limits.json 시행령 기본값 사용 |
| Anthropic Claude | 준필수 | 설비소방 `pass=None`, 질의 불가 |
| arch-law-graph | 선택 | 조문 원문 없이 질의 (0단계로 degrade) |
| Kakao Local | 권장 | 주소 자동완성 비활성 |
| LURIS (data.go.kr) | 선택 | EUM으로 대체 |

**재시도 정책** (`http_retry.py`): 전송 오류·5xx → 지수 백오프 2회 재시도. 4xx·정상 응답은 즉시 처리.

---

## 13. 데이터 캐시 (`CacheManager`)

**저장소**: `./data/arch_law.db` (SQLite)

| 테이블 | TTL | 내용 |
|--------|-----|------|
| `land_info_cache` | 30일 | 토지 정보 (용도지역·지적 폴리곤 등) |
| `ordinance_zone_limits` | 30일 | 조례 수치 (건폐율·용적률 상한) |
| `diagnose_history` | 영구 | 진단 이력 |

**Stale 캐시 fallback**: VWorld 재조회 실패 시 `data_quality.stale_cache = true` 플래그와 함께 캐시 데이터 사용.

**초기화**:
```bash
python -m scripts.seed_municipal_ordinances --commit
# 서울 도시계획조례 §54·§55 기본값 idempotent 적재
```

---

## 14. 알려진 한계 및 미구현 항목

### 데이터 한계

| 항목 | 상태 | 영향 |
|------|------|------|
| 가로구역 최고높이 (§60) | `street_block_heights.json` 비어 있음 | §60 자동판정 미수행 → `STREET_BLOCK_UNVERIFIED`(info) 경고. height pass 는 일조 판정으로 결정 |
| 교육환경평가 (학교 좌표) | ✅ 연동됨 (`school_client.py` — Kakao Places) | 좌표 확보 시 `required`/`not_required` 확정, 미확보 시 `maybe` |
| 문화재 경계 좌표 | ✅ 연동됨 (`heritage_client.py` — 국가유산청 GIS `spca.do`) | 지정문화재 100~500m 자동 판정, 미확보 시 `maybe` |
| 토지이음 `iuLawInfo` | 서버 측 404 | LawInfoPanel 비활성 |
| 토지이음 `sDevList` | 서버 측 404 | DevTrendPanel 비활성 |
| 도로폭 자동 조회 | VWorld 레이어에 폭 속성 없음 | 사용자 수동 입력 |
| 철도보호지구 (운영 철도) | 철도 선형 SHP 미배치 (`RAILWAY_SHP_PATH`) | 철도보호지구 검사 생략 (VWorld WFS는 운영 철도 선형 미제공) |

### 계산 한계

| 항목 | 상세 |
|------|------|
| 조경 의무비율 | 조례 위임 → confidence 3 고정 |
| 방화구획 자동 계산 | AI 정성 판단으로 처리 (결정론적 미구현) |
| 일조 사선 상세 계산 | 정북 이격거리 입력 필요; 미입력 시 `pass=None` |
| 지구단위계획 수치 | **구역 감지는 자동**(VWorld WFS `lt_c_upisuq161`)되나, 건폐·용적·높이 등 **결정조서 수치는 개별 계획마다 달라 자동 조회 불가** → 도시계획위원회 심의 트리거 + "결정조서 확인 필요" 안내 |

### 설계 결정 (의도적 제한)

| 결정 | 이유 |
|------|------|
| AI 단독 판정 금지 | 결정론적 룰 처리 가능 항목은 코드로 |
| 지구명·조례값 하드코딩 금지 | 전국 적용 원칙 |
| 미구현 항목 → `pass=None` | 오판정보다 "확인 필요" 응답이 안전 |
| 사내 케이스 DB 제거 | 더미 데이터라 실용성 없어 제거 (git 복원 가능) |

### 데이터 품질 경고 (`data_quality.issues` — 2026-06-29 추가)

| code | level | 발동 |
|------|-------|------|
| `STREET_BLOCK_UNVERIFIED` | info | 가로구역 최고높이 미확인 — §60 자동판정 미수행 |
| `FACILITY_AREA_UNCORRECTED` | warn | 도시계획시설 저촉 감지됐으나 지적 폴리곤 미확보로 대지면적 보정 미수행(건폐·용적 낙관 가능) |

(기존 `NO_ZONE_USE`·`NARROW_ROAD_SETBACK`·`STALE_CACHE`·`NO_ORDINANCE` 등과 함께 DataQualityBanner 에 표시.)

### 회귀 테스트 — 골든 케이스 (D, 2026-06-29 추가)

`backend/tests/golden/*.json` — 실 인허가 건축개요서에서 익명화 추출한 **12건(용도지역 7종)** + 고가치 경로 4종(실패/RED·완화·주차부족·비주입). 조례 한도를 stub 주입해 `_diagnose` 를 결정론 실행, 엔진이 실제 산정값(건폐율·용적률)을 재현하는지 고정. `test_golden_cases.py`. (산정값은 원문 절사 흡수 위해 ±0.01%p 허용.)

---

## 15. 프로젝트 구조 요약

```
backend/
├── main.py                      FastAPI 진입점·라우터
├── config/
│   ├── zone_limits.json         용도지역별 법정 상한 (시행령)
│   ├── far_relief_rules.json    완화 규칙 파라미터
│   ├── parking_standards.json   주차 기준표
│   ├── landscape_standards.json 조경 기준표
│   ├── law_scoring_weights.json 종합점수 가중치
│   ├── ordinance_seed.json      서울 조례 시드
│   ├── street_block_heights.json 가로구역 최고높이 (현재 비어 있음)
│   ├── law_graph_seed.json      법규 그래프 수동 시드 (49노드)
│   └── law_graph_auto.json      법규 그래프 자동 수확
├── services/
│   ├── diagnose_engine.py       ★ 진단 오케스트레이터
│   ├── feasibility_engine.py    사업성 검토 엔진
│   ├── far_relief.py            용적률 완화 계산
│   ├── ordinance_resolver.py    조례 cascade 조회
│   ├── ordinance_extractor.py   법령 본문 → 수치 추출 (LLM)
│   ├── land_use_resolver.py     VWorld 토지 정보 조회 + 캐시
│   ├── multi_parcel.py          합필 진단
│   ├── review_triggers.py       심의 11종 자동 판정
│   ├── building_agreement.py    건축협정 완화 보정
│   ├── query_engine.py          자연어 질의 (Claude + RAG)
│   ├── graph_client.py          arch-law-graph 조문 원문 조회
│   ├── law_graph.py             법규 의미 그래프 (networkx)
│   ├── cache_manager.py         SQLite 캐시
│   ├── llm_client.py            Claude API 래퍼
│   ├── http_retry.py            외부 API 재시도/백오프
│   ├── vworld_client.py         VWorld WFS 지적·지오코딩·도시계획시설·지구단위(lt_c_upisuq161)
│   ├── eum_client.py            토지이음 7개 API
│   ├── luris_client.py          LURIS 행위제한 2개 API
│   ├── school_client.py         학교 근접 조회 (Kakao Places — 교육환경평가)
│   ├── heritage_client.py       지정문화재 근접 조회 (국가유산청 GIS spca.do)
│   └── zone_use_normalizer.py   용도지역 표준명 정규화
└── services/calculator/
    ├── coverage.py              건폐율
    ├── far.py                   용적률
    ├── height.py                높이·일조
    ├── parking.py               주차
    ├── landscape.py             조경
    ├── land_use_act.py          행위제한
    ├── urban_facility.py        도시계획시설
    ├── fire_safety.py           설비·소방 (AI)
    ├── public_certification.py  공공시설 의무인증
    ├── bf_certification.py      BF 인증
    ├── crime_prevention.py      범죄예방 기준
    ├── multi_use.py             다중이용건축물 분류
    ├── railway_protection.py    철도보호지구
    └── zone_overlap.py          지구·구역 중첩

frontend/src/
├── components/
│   ├── InputForm/               주소·건물 입력 폼
│   ├── DiagnoseResult/          8개 카테고리 결과 카드
│   ├── WhatIfPanel/             완화 레버 슬라이더 + 비교 매트릭스
│   ├── FeasibilityMode/         사업성 검토 UI 일체
│   ├── LawGraphPanel/           법규 그래프 탐색기
│   ├── LawChangeAlert/          조례 변경 알림 배너
│   ├── DataQualityBanner/       데이터 출처·fallback 경고
│   └── LegalReviewReport/       인쇄용 종합 검토 보고서
├── stores/
│   ├── diagnoseStore.js         진단 모드 전역 상태
│   └── feasibilityStore.js      사업성 모드 전역 상태
└── utils/
    ├── api.js                   fetch 래퍼 (cache: 'no-store')
    └── graphLink.js             arch-law-graph 링크 생성 유틸
```

---

## 면책

자동 진단 결과는 **참고용**. 실제 인허가 판단 및 책임은 시니어 건축사·설계자에게 있다.
