# arch-law-diagnose — 종합 사양서

> 사내 건축 법규 자동 진단 시스템 V1
> 작성: 2026-05-11
> 다음 대화 시작용 컨텍스트 문서

---

## 0. 빠른 시작 가이드 (다음 대화용)

이 문서를 첨부하고 다음 중 하나로 시작:

- `"arch-law-diagnose Phase 1 프롬프트 생성해줘. Claude Code에서 실행할 거야."`
- `"이 사양으로 프로젝트 구조부터 잡아줘."`
- `"법제처 DRF API 응답 샘플 보고 DB 스키마 같이 설계하자."`
- `"가중치 JSON 설정 파일부터 만들어줘."`

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
│       │   ├── InputForm/        # 대지 주소·용도·규모 입력
│       │   ├── DiagnoseResult/   # 8개 카테고리 신호등
│       │   ├── WhatIfPanel/      # 슬라이더 시뮬레이션
│       │   ├── ScenarioCompare/  # 안 A/B/C 비교
│       │   ├── CaseReference/    # 사내 케이스 연계
│       │   └── LawChangeAlert/   # 법규 변경 알림
│       ├── stores/               # Zustand
│       └── utils/
│
├── backend/                      # FastAPI
│   ├── pyproject.toml
│   ├── main.py
│   ├── config/
│   │   └── law_scoring_weights.json  # 가중치 (외부 설정)
│   ├── services/
│   │   ├── vworld_client.py      # VWorld API
│   │   ├── law_go_kr_client.py   # 법제처 DRF API
│   │   ├── llm_client.py         # Claude API
│   │   ├── cache_manager.py      # SQLite 캐시
│   │   ├── address_normalizer.py # 주소 → PNU
│   │   ├── land_use_resolver.py  # 토지이용계획 조회
│   │   ├── diagnose_engine.py    # 8개 카테고리 진단 엔진
│   │   ├── calculator/
│   │   │   ├── coverage.py       # 건폐율
│   │   │   ├── far.py            # 용적률
│   │   │   ├── height.py         # 높이·일조
│   │   │   ├── parking.py        # 주차
│   │   │   ├── landscape.py      # 조경
│   │   │   └── fire_safety.py    # 설비-소방
│   │   ├── what_if_simulator.py
│   │   ├── case_matcher.py       # Competition Analyzer DB 연계
│   │   └── law_change_tracker.py
│   └── data/
│       ├── arch_law.db           # SQLite (gitignore)
│       └── seed/                 # 초기 데이터 (있을 경우)
│
├── docs/
│   ├── api_response_samples/     # 실제 API 응답 샘플
│   │   ├── vworld_geocoder.json
│   │   ├── vworld_land_use.json
│   │   └── law_go_kr_ordinance.json
│   └── reference/                # 건축법 참고 자료
│       ├── 건축물_면적_높이_세부_산정기준.pdf
│       └── 그림으로_이해하는_건축법.pdf
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
    name TEXT NOT NULL,         -- '영등포구'
    parent_code TEXT,           -- '11' (서울)
    type TEXT                   -- 'gu' | 'si' | 'do'
);

-- 조례 캐시
CREATE TABLE ordinances (
    id INTEGER PRIMARY KEY,
    jurisdiction_code TEXT,     -- '11560'
    law_type TEXT,              -- 'urban_planning' | 'building' 등
    title TEXT,
    content TEXT,               -- 전문
    article_no TEXT,            -- '제25조'
    last_fetched_at TIMESTAMP,
    source_url TEXT,
    FOREIGN KEY (jurisdiction_code) REFERENCES jurisdictions(code)
);

-- FTS5 전문 검색 인덱스
CREATE VIRTUAL TABLE ordinances_fts USING fts5(
    title, content,
    content='ordinances'
);

-- 토지 정보 캐시 (PNU 기반)
CREATE TABLE land_info_cache (
    pnu TEXT PRIMARY KEY,           -- 19자리 필지번호
    address TEXT,
    jurisdiction_code TEXT,
    zone_use TEXT,                  -- 용도지역
    zone_district TEXT,             -- 용도지구
    zone_area TEXT,                 -- 용도구역
    district_plan TEXT,             -- 지구단위계획
    urban_facility TEXT,            -- 도시계획시설
    land_category TEXT,             -- 지목
    official_price INTEGER,         -- 공시지가
    fetched_at TIMESTAMP
);

-- 진단 이력 (감사 로그 + V2 학습용)
CREATE TABLE diagnose_history (
    id INTEGER PRIMARY KEY,
    user_id TEXT,
    address TEXT,
    pnu TEXT,
    input_json TEXT,                -- 입력 전체 (용도, 규모 등)
    result_json TEXT,               -- 결과 전체
    overall_score REAL,
    created_at TIMESTAMP
);

-- 법규 변경 감지 (해시 기반)
CREATE TABLE ordinance_versions (
    id INTEGER PRIMARY KEY,
    jurisdiction_code TEXT,
    law_type TEXT,
    content_hash TEXT,              -- SHA256
    fetched_at TIMESTAMP
);
```

---

## 11. Phase별 개발 로드맵

### Phase 1 (1~2주): 기반 + 정량 4개
**목표**: SeonJ 기본 수준 달성

- 프로젝트 구조 셋업 (Vite + FastAPI + SQLite)
- VWorld 클라이언트 (Geocoder + 토지이용계획)
- 법제처 DRF 클라이언트 + Lazy Cache
- 정량 계산 4개: 건폐율, 용적률, 높이, 주차
- 기본 입력 폼 + 결과 화면

**Deliverable**: 주소 입력 → 정량 4개 점수 출력

### Phase 2 (1주): 8개 카테고리 + 종합 진단
**목표**: SeonJ 추월

- 조경, 설비-소방 추가 (AI 보조)
- 종합 점수 산출 (가중평균)
- 신호등 대시보드
- 위험 항목 자동 추출
- 확신도 표시
- 근거 법조문 자동 인용

**Deliverable**: 한 화면 종합 진단

### Phase 3 (1~2주): What-if + 비교 + 자연어 질의
**목표**: 의사결정 도구로 진화

- 슬라이더 기반 What-if 시뮬레이션
- 시나리오 비교 매트릭스 (안 A/B/C)
- 자연어 질의 (조문 + 판례 종합)

**Deliverable**: 실시간 의사결정 지원

### Phase 4 (2주): 사내 연계 + 변경 추적
**목표**: 차별화 완성

- Competition Analyzer DB 연동
- 유사 케이스 자동 매칭
- 법규 변경 모니터링 (cron + diff)
- 변경 영향도 자동 분석
- 시니어 검토 요청 버튼

**Deliverable**: 회사 자산 통합 + 자동 모니터링

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

## 17. 다음 액션

### 즉시
1. 이 사양서 검토 (수정사항 있으면 알려주세요)
2. `arch-law-diagnose` 폴더 생성
3. VSCode + Claude Code Extension 열기

### Claude Code 첫 프롬프트 작성 시 포함할 것
- 이 사양서 전체 첨부
- Phase 1 명시 ("Phase 1만 작업, Phase 2~4는 다음 단계")
- 첫 작업: 프로젝트 구조 셋업 + VWorld 클라이언트
- 환경 변수 처리 방식 명시
- 테스트용 더미 주소 1개 제공 ("서울 영등포구 당산동3가 123")

---

*end of document*
