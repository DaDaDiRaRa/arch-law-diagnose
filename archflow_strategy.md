# 건축설계 AI 자동화 워크플로우 — 전략 종합 문서

> 정현님의 사내 건축 설계 자동화 MCP 에코시스템 구축 전략 정리
> 작성: 2026-05-11 / 최종 업데이트: 2026-05-13

---

## 1. 출발점: 기존 자산

### 보유 중인 앱
**Competition Analyzer** — 설계공모 경쟁사 비교분석 & 제안서 진단 앱

**구조**
- **모드 1 (데이터 축적)**: 과거 공모 PDF(지침서 + 각 사 제안서) → Node 1→2→3 파이프라인 → JSON DB
- **모드 2 (신규 진단)**: 새 지침서 + 자사 제안서 → DB 당선 패턴과 비교 → 진단

**3단계 파이프라인**
1. **Node 1 (페이지 분류)**: PDF → 페이지별 17 유형 분류 (COVER, CONCEPT, FLOOR_PLAN, SECTION, ELEVATION, AREA_TABLE 등)
2. **Node 2 (데이터 추출)**: 유형별 다른 추출 프롬프트 → 구조화 JSON
3. **Node 3 (비교분석)**: 7~8개 비교축으로 문서 간 비교

**기술 스택**
- Frontend: React (Vite)
- Backend: Python (FastAPI)
- AI: Claude API (claude-sonnet-4)
- DB: JSON 파일 기반 (서버 폴더)
- PDF: pymupdf + PaddleOCR + pdfplumber

**DB 폴더 구조 (시설유형 12개)**
```
KUNWON_COMPETITION_DB/
├── _config/           (page_taxonomy, prompt_templates)
├── _patterns/         (시설유형별 당선패턴 — 자동생성)
├── public/            (공공시설)
│   └── 2025_영등포_신청사/
│       ├── _meta.json
│       ├── _brief.json
│       ├── submissions/
│       │   ├── kunwon_win.json
│       │   └── company_a_lose.json
│       └── _comparison.json
├── residential/ ... mixed_use/  (총 12 시설유형)
```

**핵심 출력물**
- `report_generator.py` — 종합 비교 HTML 리포트
- `submission_report_generator.py` — 개별 제안서 리포트
- 두 리포트 모두 `@media print` 모드로 **A4 가로 PDF 출력 가능 (사실상 PPT)**

---

## 2. 시장 조사 결과

### ARCO.AI (경쟁사 추정 제품)
- 건축가 1인이 3개월 만에 개발
- 6개 자체 MCP (39 tools), 9단계 파이프라인
- Electron 데스크톱 앱 (10만+ 줄 코드)
- 47,225 법조문 3D Galaxy 시각화
- GREEN-T 일조환경 특허
- 구현률 32%

### SeonJ Archflow (경쟁사 - 정현님이 발견)
**MCP 서버 6개** (총 39 tools)

| MCP | 상태 | tools | 역할 |
|---|---|---|---|
| arch-checklist-mcp | production | 6 | 공모 지침서 PDF 분석 |
| arch-law-mcp | production | 15 | 건축법규 온톨로지 DB (TypeScript+SQLite+FTS5+법제처 API) |
| arch-analysis-mcp | production | 3 | KOSIS 196개 통계 + AI 인문 내러티브 |
| arch-site-mcp | production | 3 | NGII ZIP → Rhino 3DM 부지 모델 |
| arch-zoning-mcp | production | 9 | AI 조닝 + SVG 캔버스 + DXF 출력 |
| arch-drawing-mcp | development | 3 | DXF + 3DM CAD 출력 |

**웹 앱 4개**
- **arch-hub**: 9-phase 오케스트레이터 (Next.js 16 + FastAPI, 41 endpoints, 59 components, WebSocket)
- **arch-law-galaxy**: 47,225 조문 3D 시각화 (Three.js)
- **arch-work-hub**: 실시간 대시보드 (React + Zustand)
- **hub-website**: 마케팅 사이트

### 결정적 발견
**SeonJ ≈ ARCO.AI** 거의 확실 (같은 사람 또는 한쪽이 다른 쪽 복제)

| 지표 | ARCO.AI | SeonJ |
|---|---|---|
| MCP 서버 | 6 | 6 |
| MCP 도구 | 39 | 39 |
| Pipeline Phases | 9 | 9 |
| 3D 법조문 | 47,225 | 47,225 |
| 지자체 조례 | 162 | 162 (Phase 5에서 수집 인프라 완성 — seed 진행 예정) |

---

## 3. 전략 결정: 왜 사내 자산으로 만드는가

### 핵심 인사이트
**SeonJ는 우리 회사가 아닌 경쟁사 개발물.**
→ 우리 회사에서 사용 불가
→ 데이터 외부 유출 위험
→ **자체 버전 필수**

### 시장 제품 vs 사내 자산 (관점 차이)

| 관점 | 시장 제품 | 사내 자산 (우리 상황) |
|---|---|---|
| 목표 | 차별화로 점유율 | 경쟁사와 동등 이상 역량 확보 |
| SeonJ 의미 | 경쟁자 | 벤치마크 + 보안 위협 |
| 모방 | 안 됨 | **오히려 따라잡아야 함** |
| 차별화 | 시장에서 이김 | 회사가 뒤처지지 않음 + 자체 우위 |

이건 정현님의 user preferences("로컬 서버 기반, 클라우드 의존성 축소, Team Asset 표준화") 와 정확히 일치.

---

## 4. 3-Wave 로드맵

### Wave 1: USP 먼저 (1~2개월) — 즉시 가치
**SeonJ에 없는 영역**부터. 정현님이 이미 80% 설계 완료.

```
competition-brief-mcp     ← 지침서 분석 (정현님 기존)
submission-analysis-mcp   ← 제안서 분석 (SeonJ에 없음)
pattern-db-mcp            ← 당선 패턴 비교 (정현님 USP, SeonJ에 없음)
```

**Wave 1을 먼저 하는 이유**
- 이미 설계 끝나있어 빠름
- SeonJ에 없으니 진짜 차별화
- 1~2개월 안에 팀에 첫 결과물
- 다른 모든 단계의 **상류(upstream)** 역할

### Wave 2: 실제 통증 기반 재정의 (3~5개월)
정현님이 실제로 겪는 일상 통증 4가지:

| 통증 | 시간 | SeonJ에 있는가? | 만들 MCP |
|---|---|---|---|
| 법규분석 | 1~3일 | ⚠️ 부분적 (단편적) | **law-mcp** (더 좋게) |
| 제안서 검토 | 1~3일 | ❌ 없음 | **proposal-review-mcp** (Wave 1과 통합) |
| 사업성 검토 | 1~2일 | ❌ 없음 | **feasibility-mcp** (신규) |
| PPT 만들기 | 1~3일 | ❌ 없음 | **이미 만들어짐** (아래 5번 참조) |

→ **4개 중 3개가 SeonJ 미개척 영역**

### Wave 3: 우위 점하기 (6개월+) — 일단 보류
- rendering-mcp (패널/투시도 자동화)
- aor-mcp (실시설계/디테일)
- environment-mcp (일조/음영/풍 시뮬레이션)
- orchestrator (arch-hub 대응)

---

## 5. PPT 자동화 — 이미 완성됨

### 발견
`report_generator.py`의 print 모드가 사실상 PPT 출력:

```css
@media print {
  @page { size: A4 landscape; margin: 10mm 12mm; }
  *, *::before, *::after { -webkit-print-color-adjust: exact !important; }
  .sec { page-break-inside: avoid; }
  .db-axis-content { display: block !important; }  /* 아코디언 전부 펼침 */
  .db-filter-bar { display: none !important; }     /* 인터랙티브 UI 숨김 */
}
```

**브라우저 Ctrl+P → PDF 저장 = 발표 자료**

### 결론: PPT MCP 별도 개발 불필요

3가지 선택지 중:
- **옵션 1**: HTML 그대로 = PPT (이미 됨, 추가 개발 0)
- **옵션 2**: HTML → PPTX 변환기 (python-pptx로 얇게 얹기)
- ~~옵션 3: JSON → PPTX 직접 생성 (드리프트 위험, 비추)~~

**user preferences "재현성, 팀 표준화"** 기준 → 옵션 1 또는 2가 답

### 수정된 Wave 2 구조
```
[수정] 법규 / 제안서검토 / 사업성 = 3개 MCP
       └─ 각 MCP가 표준 HTML 리포트 출력
          └─ 공통 어댑터: html → pptx (선택적, 필요 시)
```

리포트 생성기(submission_report_generator + report_generator)를 표준화 컴포넌트로 굳히면, **새 MCP 만들 때마다 같은 패턴으로 리포트 자동 생성** = Team Asset 표준화 완성.

---

## 6. 각 Wave 2 MCP — SeonJ보다 더 좋게 만드는 법

### law-mcp — 시나리오 기반으로

**SeonJ 약점**: 15개 도구가 단편적 (`check_far`, `check_setback`, `check_parking` 따로따로). 사용자가 어떤 도구를 어떤 순서로 부를지 알아야 함.

**현재 상태**: `arch-law-diagnose` Phase 5가 사실상 law-mcp 역할 수행 중.

```text
SeonJ:  check_far() + check_setback() + check_parking() + ... 따로 호출
우리:   /api/diagnose(주소, 용도, 규모)
        → 6개 카테고리 자동 체크
        → 지자체 조례 cascade 적용 (Phase 5)
        → 종합 점수 + 신호등 + 위험 항목
```

**추가 차별화** (SeonJ에 없음):

- 지자체 조례 DB cascade (DB → 법제처 → 시행령 기본값)
- 법규 변경 추적/알림 (SHA256 해시 비교)
- 타사 유사 프로젝트 케이스 비교 (KUNWON_DB 연계)
- V2: `arch-law-mcp`으로 추출 → Claude Desktop/Code에서 직접 사용 가능

### proposal-review-mcp — 이미 80% 설계됨
Wave 1의 `submission-analysis-mcp` + `pattern-db-mcp` 통합 버전.

**추가**:
- 심사 기준 자동 매핑 (지침서 평가 기준 ↔ 우리 안 응답)
- 약점 진단 + 보강 제안

### feasibility-mcp — 완전 신규
SeonJ에 없는 영역. 정현님 AOR 경력이 가장 빛나는 자리.

```
도구 구성:
- estimate_construction_cost   (평당 공사비 × 면적)
- calculate_revenue            (분양가/임대료 시나리오)
- compute_roi                  (사업 수익률)
- compare_scenarios            (안 A vs 안 B vs 안 C)
- generate_feasibility_report  (종합 리포트)
```

**데이터 소스**: 국토부 분양가, 한국감정원 임대료, 사내 과거 실적

---

## 7. MCP 호출 구조 정리

```
사용자 (브라우저)
      ↓ 클릭/입력
  웹사이트 (Next.js/React)
      ↓ API 요청
  백엔드 서버 (FastAPI)
      ↓ Claude API 호출
  Claude (AI 모델)
      ↓ 도구 사용
  MCP 서버들 (tool 실행)
```

**핵심**: Claude가 MCP를 부른다. 웹사이트나 백엔드가 직접 부르는 게 아님.

**MCP 사용의 2가지 방식**:
1. Claude Desktop/Code에서 바로 사용 (웹앱 없이도)
2. 나중에 웹앱 만들 때 백엔드로 재사용 (같은 MCP)

**개발 순서**:
```
Step 1: MCP 서버 만들기 (Claude Desktop에서 바로 테스트)
Step 2: MCP들이 잘 작동하면 → 웹앱(orchestrator) 씌우기
```

---

## 8. 현재까지의 결정 사항

| 항목 | 결정 |
|---|---|
| Wave 3 (rendering/AOR/environment) | 일단 보류 |
| Wave 2 우선 | 확정 |
| SeonJ 추격 | 사내 자산으로 자체 구축 |
| PPT MCP | 별도 개발 안 함 (HTML 리포트 = PPT) |
| MCP 수 (Wave 2 수정 후) | 3개 (law / proposal-review / feasibility) |
| 호스팅 환경 | 회사 NAS / 로컬 서버 (user prefs 부합) |
| 재현성 | temperature=0, 태그/규칙 기반 프롬프트 |

---

## 9. 열린 질문 (다음에 결정 필요)

1. **팀에서 PPT를 실제로 편집하는가, 출력만 하는가?**
   - 편집 → HTML→PPTX 변환기 추가 필요
   - 출력만 → 현재 print 모드로 충분

2. **다음 단계 우선순위는?**
   - law-mcp 부터 (가장 무겁지만 임팩트 큼)
   - feasibility-mcp 부터 (정현님 강점)
   - proposal-review-mcp 부터 (Wave 1 마무리)

3. **단독 개발 vs 팀 개발?**
   - 단독: Wave 2까지 6~9개월
   - 팀 2명: 3~5개월

4. **MCP 호스팅 위치?**
   - 회사 NAS
   - 각자 로컬
   - 사내 클라우드

---

## 10. 권장 시작 순서

### 즉시 시작 가능
**`submission-analysis-mcp`** (Wave 1)
- 정현님 기존 파이프라인 그대로 MCP화
- SeonJ에 없으니 즉시 차별화
- FastMCP 학습 적정 난이도
- 단독으로도 가치 있음 (다른 MCP 호출 불필요)

### Wave 2 진입 시점
**B (PPT는 이미 됨) → 사실상 A or D 부터**
- A. **proposal-review-mcp**: 이미 설계 완료, 빠른 실행
- D. **feasibility-mcp**: 정현님 전문성, 신규 영역
- C. **law-mcp**: 가장 무거우니 마지막

추천 순서: **proposal-review → feasibility → law**

---

## 11. 핵심 원칙 (user preferences 반영)

1. **Team Asset 표준화** — 누가 만들어도 같은 결과
2. **로컬 서버 기반** — 클라우드 의존성 최소화
3. **재현성** — temperature=0, 시드 고정, 태그/규칙 기반
4. **카메라/구도 고정** — AI 임의 변경 차단
5. **파이프라인 사고** — 일회성 팁 X, 시스템 빌딩 ✓
6. **에러 = 자동화 의도 불일치** — 임시 fix X, 프로세스 개선 ✓
7. **SeonJ 베끼지 말되, 똑같이 만들지도 말 것** — 빈자리 + USP 우선

---

## 12. 참고 자료

- ARCO.AI: (영상/포트폴리오 링크)
- SeonJ Archflow: https://web-portfolio-mu-liard.vercel.app/projects/mcp
- 기존 Competition Analyzer 코드: 로컬

---

## 13. 다음 대화 시작 방법

이 파일을 첨부하고 다음 중 하나로 시작:

- "submission-analysis-mcp 부터 만들자. FastMCP 보일러플레이트 생성해줘."
- "proposal-review-mcp 설계를 더 구체화하고 싶어."
- "feasibility-mcp의 데이터 소스를 정리해줘."
- "law-mcp의 시나리오 기반 도구 구조를 잡아줘."
- "HTML → PPTX 변환기 어댑터 설계해줘."
- "전체 MCP 간 데이터 흐름 다이어그램 그려줘."

---

*end of document*
