# arch-law-diagnose — 종합 사양서

> 사내 건축 법규 자동 진단 시스템
> 작성: 2026-05-11 / 최종 업데이트: 2026-05-13
> 다음 대화 시작용 컨텍스트 문서 — **현재 Phase 5 완료 상태**

---

## 0. 빠른 시작 가이드 (다음 대화용)

### 현재 완료 상태 (2026-05-13)

Phase 1~5 전부 완료. 백엔드 `main.py` 버전 5.0, 프론트엔드 Phase 4 UI.

### 서버 실행

```bash
# 백엔드
cd backend && uvicorn main:app --reload --port 8000

# 프론트엔드
cd frontend && npm run dev   # → http://localhost:5173
```

### 다음 대화 시작 예시

- `"seed_ordinances.py 작성해줘 — 7대 광역시 건폐율 dry-run 먼저"` ← 다음 단계
- `"조경/높이 카테고리도 조례 리졸버 연동해줘"` ← Phase 6 범위
- `"MCP 서버로 추출하는 구조 잡아줘"` ← V2 방향
- `"법규 변경 cron 스캔 자동화해줘"` ← Phase 4 확장

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|---|---|
| 프로젝트명 | **arch-law-diagnose** |
| 한글명 | (가칭) 건축 법규 자동 진단 시스템 |
| 목적 | 대지 주소·용도·규모 입력 → 건축 법규 8개 카테고리 종합 진단 |
| 성격 | 사내 자산 (Team Asset), 비상업 |
| 사용자 | 회사 건축 설계 팀 (신입~시니어) |
| 배포 | 로컬 또는 사내 서버 |
| 라이선스 | 사내 전용 |

---

## 2. 전략적 배경 (왜 만드는가)

### 경쟁 환경
- **SeonJ Archflow** (≈ARCO.AI) = 경쟁사 제품
  - 6 MCP, 39 tools, 9-phase orchestrator
  - 계획설계 자동화 90% 완성
- 우리 회사가 사용 불가 (경쟁사 IP)
- **자체 버전 구축 필수**

### 차별화 포인트 (SeonJ에 없는 것)
1. **사내 케이스 연계** — 우리 회사 과거 프로젝트 DB 자동 매칭
2. **시나리오 종합 진단** — 단편 도구 호출 X, 한 화면 종합 판단
3. **What-if 실시간 시뮬레이션** — 변수 조정 즉시 재계산
4. **법규 변경 추적** — 사용 지역만 모니터링
5. **확신도 표시** — 신입 사용자 안전 장치

### Roadmap 전체 그림
```
[Wave 1: USP - 완료/진행 중]
└── Competition Analyzer (제안서 검토 + 패턴 DB)

[Wave 2: 현재 작업]
├── arch-law-diagnose ★ (이 문서)
├── proposal-review-mcp (Competition Analyzer MCP化)
└── feasibility-mcp (사업성 검토 - 다음)

[Wave 3: 보류]
├── rendering-mcp
├── aor-mcp
└── environment-mcp
```

---

## 3. 6대 핵심 기능

| # | 기능 | 핵심 차이 (vs SeonJ) |
|---|---|---|
| 1 | **시나리오 종합 진단** | 단편 도구 호출 X → 한 입력으로 종합 출력 |
| 2 | **What-if 시뮬레이션** | 슬라이더로 변수 조정 → 즉시 재계산 |
| 3 | **시나리오 비교 매트릭스** | 안 A/B/C 동시 진단 + 비교 표 |
| 4 | **사내 케이스 연계** | Competition Analyzer DB 자동 매칭 |
| 5 | **법규 변경 추적** | 사용 지역만 모니터링, 영향도 자동 분석 |
| 6 | **자연어 질의** | 검색이 아닌 컨설팅 (조문 + 판례 + 사내 케이스 종합) |

---

## 4. 진단 카테고리 (V1 권장 6개)

### V1 범위 (4~5주 개발 목표)

| 카테고리 | 계산 방식 | 가중치 |
|---|---|---|
| **용적률** | 결정론적 (사업성 직결) | 25 |
| **높이·일조** | 결정론적 + 사선 검토 | 20 |
| **주차** | 결정론적 (부설주차 산정) | 20 |
| **건폐율** | 결정론적 | 15 |
| **조경** | 결정론적 + AI 보조 | 10 |
| **설비(소방)** | AI 종합 판단 | 10 |
| **합계** | | **100** |

### V2 확장 예정
- 친환경/에너지 인증 (G-SEED, 에너지효율등급)
- 특화 (장애인편의, 범죄예방, 지자체 가산)
- 조경 확장 (옥상녹화, 벽면녹화)
- 설비 확장 (정화조, 승강기, 장애인편의)

---

## 5. 점수 산출 방식 — 하이브리드

### 원칙
```
정량 항목 → 결정론적 계산 (재현성 100%)
정성 항목 → AI 종합 판단 (보강 제안, 위험 설명)
종합 점수 → 정량 가중평균 (재현성 보장)
```

### 가중치 설정 (외부 JSON)

**파일 위치**: `backend/config/law_scoring_weights.json`

```json
{
  "version": "v1.0",
  "last_updated": "2026-05-11",
  "rationale": "초기 디폴트 — 건축법 분량 비례 + 일반 통념. 실사용 후 보정 필요.",
  "weights": {
    "용적률":      25,
    "높이_일조":   20,
    "주차":        20,
    "건폐율":      15,
    "조경":        10,
    "설비_소방":   10
  },
  "notes": {
    "용적률":     "사업성 직결, 인허가 거부 사유 1위 추정",
    "높이_일조":  "방화/피난 다음 분량(3장), 일조사선 복잡",
    "주차":       "미달 시 인허가 불가",
    "건폐율":     "용적률보다 단순",
    "조경":       "지자체별 편차 크지만 통상 10% 수준",
    "설비_소방":  "법규 분량 최대(9장)지만 V1은 소방만"
  }
}
```

**보정 방식**: JSON 파일 수정 → 재배포 불필요 → 5초 적용

### 확신도 표시 (신입 보호)
```
용적률 285% / 한도 300%
점수: 8.5/10
확신도: ★★★★★ (결정론적 계산)

조경 비율 32% / 한도 30%
점수: 7.0/10
확신도: ★★★☆☆ (AI 종합 판단 일부 포함)
```

---

## 6. 데이터 흐름 — Lazy Cache + 토지이음 통합

### 핵심 원칙
**전국 162개 일괄 수집 X** → **주소 입력 시 그 지역만 즉시 조회 → 캐시**

### 흐름 다이어그램

```
[사용자 입력]
대지 주소, 용도, 규모

   ↓ 1단계 — 주소 정규화

[VWorld Geocoder API]
주소 → PNU (필지번호) + 좌표 + 행정구역 코드

   ↓ 2단계 — 토지 정보 (토지이음 데이터)

[VWorld 데이터 API]
PNU → {
  용도지역,        ← 한도값 결정의 출발점
  용도지구,        ← 추가 규제
  용도구역,        ← 특수 규제
  지구단위계획,
  도시계획시설,    ← 대지면적 제외 사유
  지목,
  공시지가
}

   ↓ 3단계 — 조례 로드 (Lazy Cache)

[캐시 확인]
SQLite DB → 해당 지역 조례 있나?
  - 있음 → 사용
  - 없음 → 법제처 DRF API 호출 → SQLite 저장

  로드 대상:
  - 영등포구 도시계획조례
  - 영등포구 건축조례 (있을 경우)
  - 서울시 도시계획조례
  - 국가 건축법

   ↓ 4단계 — 하이브리드 진단

[8개 카테고리 동시 분석]
정량 (4개): 건폐율, 용적률, 높이, 주차 → 공식 계산
정성 (2개): 조경, 설비 → AI 종합 판단
종합: 가중평균

   ↓ 5단계 — 사내 케이스 매칭

[Competition Analyzer DB 검색]
같은 시설유형 + 같은 지역 → 유사 케이스 추천

   ↓ 6단계 — 출력

[결과 화면]
- 종합 점수 + 신호등
- 각 카테고리 상세 + 확신도
- 위험 항목 + 보강 제안
- 근거 법조문 자동 인용
- 유사 사내 케이스 링크
```

### 캐시 갱신 정책
- **30일 이내**: 그대로 사용
- **30~90일**: "오래된 데이터" 뱃지 + 백그라운드 갱신
- **90일 초과**: 자동 재조회
- **수동 갱신 버튼**: 언제든 즉시 갱신 가능

---

## 7. 기술 스택

| 레이어 | 기술 | 비고 |
|---|---|---|
| **Frontend** | React 19 + Vite 7 | Competition Analyzer와 동일 |
| **Backend** | Python 3.11 + FastAPI | 동일 |
| **DB** | SQLite + FTS5 | SeonJ 기본 차용, 단순함 |
| **AI** | Claude API (claude-sonnet-4) | 정성 판단용 |
| **외부 API** | 법제처 DRF, VWorld | 키 발급 완료 |
| **상태관리** | Zustand | 가벼움 |
| **스타일** | TailwindCSS | 빠른 프로토타입 |
| **PDF 처리** | (옵션, V2부터) | 조례 PDF 첨부 시 |

---

## 8. 외부 API 키 정리

| API | 키 발급 | 용도 | 상태 |
|---|---|---|---|
| 법제처 DRF | open.law.go.kr | 법조문 + 조례 본문 | ✓ 발급 완료 |
| VWorld OpenAPI | vworld.kr | Geocoder + 토지이용계획 + 공시지가 | ✓ 발급 완료 |
| 공공데이터포털 | data.go.kr | 보조 (VWorld 누락 시) | 회원가입만 |
| Anthropic API | console.anthropic.com | Claude API (AI 판단) | 별도 |

### 환경 변수 (`.env`)
```
ANTHROPIC_API_KEY=sk-ant-...
LAW_GO_KR_API_KEY=...
VWORLD_API_KEY=...
DATA_GO_KR_API_KEY=...     # 옵션
DB_PATH=./data/arch_law.db
CACHE_TTL_DAYS=30
```

---

## 9. 프로젝트 구조 (제안)

```
arch-law-diagnose/
├── README.md
├── .env                          # API 키 (gitignore)
├── .env.example                  # 템플릿
├── .gitignore
│
├── frontend/                     # React + Vite
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── App.jsx
│       ├── main.jsx
│       ├── components/
│       │   ├── InputForm/           # 대지 주소·용도·규모 입력
│       │   ├── DiagnoseResult/      # 6개 카테고리 신호등 + source 배지 (Phase 5)
│       │   ├── WhatIfPanel/         # 슬라이더 시뮬레이션 (Phase 3)
│       │   ├── ScenarioCompare/     # 안 A/B/C 비교 (Phase 3)
│       │   ├── QueryBox/            # 자연어 질의 (Phase 3)
│       │   ├── CaseReference/       # 사내 케이스 연계 (Phase 4)
│       │   ├── LawChangeAlert/      # 법규 변경 알림 (Phase 4)
│       │   └── ReviewRequestButton/ # 시니어 검토 요청 (Phase 4)
│       ├── stores/                  # Zustand (diagnoseStore.js)
│       └── utils/                   # api.js
│
├── backend/                      # FastAPI (v5.0)
│   ├── pyproject.toml
│   ├── main.py                   # Phase 5 — OrdinanceResolver 포함
│   ├── config/
│   │   ├── law_scoring_weights.json  # 가중치 (외부 설정)
│   │   └── zone_limits.json          # 시행령 기본값 — 조례 미조회 시 fallback
│   ├── services/
│   │   ├── vworld_client.py         # VWorld API (Geocoder + 토지이용계획)
│   │   ├── law_go_kr_client.py      # 법제처 DRF API (조례 본문)
│   │   ├── llm_client.py            # Claude API (AsyncAnthropic)
│   │   ├── cache_manager.py         # SQLite 캐시 + ordinance_zone_limits
│   │   ├── address_api_client.py    # 행안부 도로명주소 API (자동완성)
│   │   ├── land_use_resolver.py     # 토지이용계획 조회 + jurisdiction_name
│   │   ├── ordinance_extractor.py   # 조례 본문 → 수치 추출 (regex+LLM) ★Phase5
│   │   ├── ordinance_resolver.py    # cascade: DB→법제처→JSON fallback ★Phase5
│   │   ├── diagnose_engine.py       # 6개 카테고리 진단 엔진 (OrdinanceResolver 주입)
│   │   ├── calculator/
│   │   │   ├── coverage.py          # 건폐율 (limit_override 지원)
│   │   │   ├── far.py               # 용적률 (limit_override 지원)
│   │   │   ├── height.py            # 높이·일조
│   │   │   ├── parking.py           # 주차
│   │   │   ├── landscape.py         # 조경
│   │   │   └── fire_safety.py       # 설비·소방 (AI)
│   │   ├── what_if_simulator.py     # Phase 3
│   │   ├── query_engine.py          # Phase 3
│   │   ├── case_matcher.py          # Phase 4 — KUNWON_DB 연계
│   │   ├── law_change_tracker.py    # Phase 4 — SHA256 해시 변경 감지
│   │   └── review_notifier.py       # Phase 4 — Slack/로그 시니어 알림
│   ├── scripts/
│   │   └── seed_ordinances.py       # Phase 5 — 7대 광역시 조례 수집 (작성 예정)
│   └── data/
│       ├── arch_law.db              # SQLite (gitignore)
│       └── seed/
│
├── docs/
│   ├── api_response_samples/
│   └── reference/
│
└── tests/
    └── (계산 엔진 단위 테스트)
```

---

## 10. SQLite 스키마 (V1 초안)

### 테이블 구조

```sql
-- 행정구역 코드 → 명칭 매핑
CREATE TABLE jurisdictions (
    code TEXT PRIMARY KEY,      -- '11560' (영등포구)
    name TEXT NOT NULL,
    parent_code TEXT,
    type TEXT
);

-- 조례 본문 캐시 (법제처 DRF API 응답)
CREATE TABLE ordinances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    jurisdiction_code TEXT NOT NULL,
    law_type TEXT NOT NULL,
    title TEXT,
    content TEXT,
    article_no TEXT,
    last_fetched_at TEXT NOT NULL,
    source_url TEXT,
    FOREIGN KEY (jurisdiction_code) REFERENCES jurisdictions(code)
);
CREATE INDEX idx_ordinances_jcode ON ordinances(jurisdiction_code, law_type);

-- FTS5 전문 검색 인덱스
CREATE VIRTUAL TABLE ordinances_fts USING fts5(
    title, content,
    content='ordinances',
    content_rowid='id'
);

-- 토지 정보 캐시 (PNU 기반)
CREATE TABLE land_info_cache (
    pnu TEXT PRIMARY KEY,
    address TEXT,
    jurisdiction_code TEXT,
    zone_use TEXT,
    zone_district TEXT,
    zone_area TEXT,
    district_plan TEXT,
    urban_facility TEXT,
    land_category TEXT,
    official_price INTEGER,
    lon REAL,
    lat REAL,
    fetched_at TEXT NOT NULL
);

-- 진단 이력
CREATE TABLE diagnose_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT,
    pnu TEXT,
    input_json TEXT,
    result_json TEXT,
    overall_score REAL,
    created_at TEXT NOT NULL
);

-- 법규 변경 감지 (SHA256 해시 비교)
CREATE TABLE ordinance_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    jurisdiction_code TEXT NOT NULL,
    law_type TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

-- ★ Phase 5 — 조례 수치 (건폐율·용적률 상한값)
-- cascade: 이 테이블 → 법제처+LLM 추출 → zone_limits.json fallback
CREATE TABLE ordinance_zone_limits (
    jurisdiction_code TEXT NOT NULL,   -- PNU 앞 5자리 (시군구)
    jurisdiction_name TEXT,            -- '서울특별시'
    zone_use          TEXT NOT NULL,   -- '일반상업지역'
    category          TEXT NOT NULL,   -- 'building_coverage_ratio' | 'floor_area_ratio'
    value             REAL NOT NULL,   -- % 수치
    source_law_id     TEXT,            -- 법제처 law_id
    source_article    TEXT,            -- 관련 조문 문구
    ef_date           TEXT,            -- 시행일
    fetched_at        TEXT NOT NULL,
    needs_review      INTEGER NOT NULL DEFAULT 0,  -- sanity check 실패 플래그
    PRIMARY KEY (jurisdiction_code, zone_use, category)
);
CREATE INDEX idx_ozl_code ON ordinance_zone_limits(jurisdiction_code);
```

---

## 11. Phase별 개발 로드맵

### Phase 1 ✅ 완료 — 기반 + 정량 4개

- 프로젝트 구조 셋업 (Vite + FastAPI + SQLite)
- VWorld 클라이언트 (Geocoder + 토지이용계획)
- 법제처 DRF 클라이언트 + Lazy Cache
- 정량 계산 4개: 건폐율, 용적률, 높이, 주차
- 기본 입력 폼 + 결과 화면

### Phase 2 ✅ 완료 — 6개 카테고리 + 종합 진단

- 조경, 설비·소방 추가 (AI 보조)
- 종합 점수 산출 (가중평균)
- 신호등 대시보드, 위험 항목 자동 추출
- 확신도 표시, 근거 법조문 자동 인용

### Phase 3 ✅ 완료 — What-if + 비교 + 자연어 질의

- 슬라이더 기반 What-if 시뮬레이션
- 시나리오 비교 매트릭스 (안 A/B/C)
- 자연어 질의 (컨텍스트 기반 AI 답변)

### Phase 4 ✅ 완료 — 사내 연계 + 변경 추적

- KUNWON_DB 유사 케이스 자동 매칭
- 법규 변경 모니터링 (SHA256 해시 비교)
- 시니어 검토 요청 버튼 (Slack/로그)

### Phase 5 ✅ 완료 — 지자체 조례 기반 진단

- `ordinance_zone_limits` 테이블 + CRUD
- `OrdinanceExtractor`: 조례 본문 → 수치 추출 (regex 1차 / LLM 2차 / sanity check)
- `OrdinanceResolver`: DB → 법제처+LLM → zone_limits.json cascade
- `coverage.py`, `far.py` — `limit_override`/`source_override` 주입 방식
- `diagnose_engine.py` — OrdinanceResolver 연동, `_fmt_source()` 헬퍼
- UI source 배지: `🏛 조례 —` (파랑) / `📋 시행령 —` (회색)

### Phase 6 (예정) — 조례 데이터 적재 + 카테고리 확장

- `seed_ordinances.py`: 7대 광역시 건폐율·용적률 조례 일괄 수집 (dry-run 우선)
- 조경·높이 카테고리 OrdinanceResolver 연동
- 법규 변경 cron 자동 스캔
- 단위 테스트 (calculator 계층)

---

## 12. 신입 사용자 보호 장치

### 1. 확신도 표시 (모든 결과에)
```
★★★★★ 결정론적 계산 (정확)
★★★★☆ 결정론적 + AI 보정
★★★☆☆ AI 종합 판단 (검증 필요)
★★☆☆☆ 데이터 부족
★☆☆☆☆ 추정값
```

### 2. 시니어 검토 요청 버튼
높은 위험 항목 옆에 버튼 → Slack/이메일 알림 → 시니어 코멘트 → DB 누적

### 3. 입력 자동화 (수동 입력 최소화)
- 주소 → 용도지역/지구/구역 자동
- 주소 → 도시계획시설 자동
- 주소 → 공시지가 자동
- 사용자가 직접 입력하는 것: 용도(드롭다운), 규모(층수·면적)

### 4. 위험 우선 정렬
결과 화면에서 위험 항목이 가장 위로. 통과 항목은 접혀서 표시.

---

## 13. AI 프롬프트 원칙 (Claude API 호출 시)

### 시스템 프롬프트 기본 구조
```
TASK: 정성 항목 판단 (조경 / 설비-소방)
INPUT_FORMAT: structured_json
OUTPUT_FORMAT: structured_json
TEMPERATURE: 0
LANGUAGE: ko

REFERENCE_LAW: <첨부된 조례 본문>
REFERENCE_GUIDE: <건축물 면적 산정기준 발췌>

RULES:
- 추측 금지, 명확한 근거 있을 때만 판단
- 한도 위반 시 정확한 위반량 명시
- 보강 가능한 경우 구체적 대안 1~3개 제시
- 모호한 경우 "판단 불가" 반환 + 검토 사유 명시

OUTPUT_SCHEMA: { ... JSON ... }
```

### 재현성 보장
- temperature=0 고정
- system prompt 버전 관리 (`prompts/v1.0/`)
- 모델 버전 명시 (`claude-sonnet-4`)

---

## 14. 향후 통합 계획 (V2 이후)

### MCP化
V1 완성 후 백엔드 로직을 MCP 서버로 추출:
- `arch-law-mcp` (시나리오 진단)
- `arch-land-use-mcp` (토지이용계획)
- `arch-case-mcp` (사내 케이스)

→ Claude Desktop / Code에서 직접 사용 가능

### Competition Analyzer 통합
별도 앱이지만 데이터 레이어 공유:
- 같은 `KUNWON_DB/` 폴더 사용
- 시설유형 정의 일관성
- 케이스 매칭 양방향

### Archflow 추격 로드맵
- V1.0: arch-law-diagnose (이 문서)
- V1.5: proposal-review-mcp (Competition Analyzer 통합)
- V2.0: feasibility-mcp (사업성)
- V3.0: rendering / aor / environment (Wave 3)
- V4.0: 통합 orchestrator (arch-hub 대응)

---

## 15. 모든 결정 사항 요약 (체크리스트)

| 항목 | 결정 |
|---|---|
| 별도 앱 vs 통합 | **별도 앱** |
| 웹앱 vs MCP 우선 | **웹앱 우선** (MCP는 V2) |
| 카테고리 V1 | **6개** (용/높/주/건/조/설) |
| 점수 산출 | **하이브리드** |
| 가중치 | **외부 JSON** (용25/높20/주20/건15/조10/설10) |
| 데이터 수집 | **Lazy Cache** (전국 일괄 X) |
| 토지 정보 | **VWorld 경유 토지이음 데이터** |
| 캐시 TTL | **30일** |
| 신입 보호 | **확신도 + 시니어 검토 버튼** |
| 기술 스택 | **React+Vite + FastAPI + SQLite+FTS5** |
| 프로젝트명 | **arch-law-diagnose** |
| 개발 환경 | **VSCode + Claude Code Extension** |
| API 키 | 법제처 DRF ✓, VWorld ✓, 공공데이터 (회원가입) |

---

## 16. 핵심 원칙 (개발 중 항상 참조)

1. **Team Asset 표준화** — 누가 만들어도 같은 결과
2. **로컬 서버 기반** — 클라우드 의존성 최소화
3. **재현성** — temperature=0, 결정론적 우선
4. **카메라/구도 고정** — AI 임의 변경 차단 (해당 시)
5. **파이프라인 사고** — 일회성 팁 X, 시스템 빌딩 ✓
6. **에러 = 자동화 의도 불일치** — 임시 fix X, 프로세스 개선 ✓
7. **SeonJ 베끼지 않되 따라잡기** — 빈자리 + USP 우선
8. **신입 보호** — 확신도, 시니어 검토, 자동 입력
9. **외부 설정 우선** — 코드 하드코딩 최소화 (JSON 설정 활용)
10. **점진적 완성** — Phase별 출시, 사용 데이터로 보정

---

## 17. 다음 액션 (Phase 6 기준 — 2026-05-13 업데이트)

### 즉시 착수 가능

1. **`seed_ordinances.py` 작성** — 7대 광역시(서울·부산·대구·인천·광주·대전·울산) 건폐율·용적률 조례 일괄 수집. `--dry-run` 플래그로 API 조회 결과만 출력, DB 저장은 `--commit` 옵션에서만.
2. **조례 sanity check 리포트** — `needs_review=1`인 행 목록 출력 엔드포인트 추가.

### 단기 (Phase 6)

- 조경·높이 카테고리 `OrdinanceResolver` 연동 (현재 건폐율·용적률만 적용)
- `law_change_tracker` cron 자동 스캔 (현재 수동 트리거)
- `calculator/` 단위 테스트 추가

### 중기 (V2 방향)

- MCP 서버로 추출: `arch-law-mcp` (시나리오 진단), `arch-land-use-mcp` (토지이용계획)
- `feasibility-mcp` 연동 (사업성 검토)

### 다음 대화 시작 프롬프트 예시

```text
"seed_ordinances.py 작성해줘.
7대 광역시 건폐율·용적률 dry-run 먼저.
법제처 API 응답이 없으면 어떻게 처리할지도 포함해줘."
```

---

*end of document*
