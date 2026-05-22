# arch-law-diagnose 프론트엔드 디자인 시스템

> 분석 기준: React 19 + Tailwind CSS 3.4 + Zustand  
> 용도: 디자인 일관성 유지, 신규 컴포넌트 개발 참고

---

## 1. 색상

### 브랜드 / 기본 팔레트

| 역할 | Tailwind 클래스 | Hex 근사값 | 사용처 |
|------|----------------|-----------|--------|
| 주색 (Primary) | `bg-blue-600` | `#2563eb` | 주요 버튼, 포커스 링 |
| 주색 Hover | `hover:bg-blue-700` | `#1d4ed8` | 버튼 호버 |
| 주색 배경 | `bg-blue-50` | `#eff6ff` | 정보 박스 배경 |
| 주색 테두리 | `border-blue-100` | `#dbeafe` | 정보 카드 테두리 |
| 주색 텍스트 | `text-blue-600` | `#2563eb` | 링크, 고스트 버튼 |
| 페이지 배경 | `bg-gray-50` | `#f9fafb` | 전체 배경 (`App`) |
| 카드/패널 | `bg-white` | `#ffffff` | 입력 폼, 헤더, 카드 |
| 기본 텍스트 | `text-gray-700` | `#374151` | 라벨, 본문 |
| 보조 텍스트 | `text-gray-500` | `#6b7280` | 힌트, 플레이스홀더 |
| 테두리 기본 | `border-gray-300` | `#d1d5db` | 입력 필드, 구분선 |
| 완화/긍정 | `bg-emerald-600` | `#059669` | 조경·완화 버튼, 배지 |

### 시그널 색상 (GREEN / YELLOW / RED)

| 신호 | 배경 | 텍스트 | 테두리 | 의미 |
|------|------|--------|--------|------|
| GREEN (적합) | `bg-green-50` | `text-green-700` | `border-green-400` | 모든 항목 통과 |
| YELLOW (주의) | `bg-yellow-50` | `text-yellow-700` | `border-yellow-400` | 조건부·확인 필요 |
| RED (부적합) | `bg-red-50` | `text-red-700` | `border-red-400` | 기준 초과·불합격 |

### 배지/라벨 색상

| 배지 종류 | 배경 + 텍스트 | 사용처 |
|----------|-------------|--------|
| 필수/의무 | `bg-blue-100 text-blue-700` | 공공인증 의무 항목 |
| 적합/완료 | `bg-green-100 text-green-700` | 통과 배지 |
| 검토 필요 | `bg-yellow-100 text-yellow-700` | YELLOW 항목 |
| 위험/필요 | `bg-red-100 text-red-700` | RED 항목 |
| 기본/미분류 | `bg-gray-100 text-gray-600` | 정보 전용 카드 |

### 카테고리별 포인트 색상

| 용도 | 클래스 | 사용 컴포넌트 |
|------|--------|-------------|
| What-if 패널 | `bg-purple-50`, `accent-purple-600` | `WhatIfPanel` |
| 케이스 참고 | `bg-amber-50` | `CaseReference` |
| 도시계획시설 | `bg-sky-50` | `DiagnoseResult` |
| 심의 트리거 | `bg-indigo-50` | `DiagnoseResult` |

---

## 2. 폰트

### 폰트 패밀리

| 상황 | 폰트 | 선언 위치 |
|------|------|----------|
| 일반 화면 | Tailwind 기본 sans-serif 스택 | `tailwind.config.js` |
| 인쇄 (법규 검토서) | `'Malgun Gothic', '맑은 고딕', sans-serif` | `LegalReviewReport/index.jsx:626` |
| 코드/해시값 | `font-mono` | PNU, 조례 해시 표시 |

### 폰트 크기 / 굵기

| 용도 | Tailwind 클래스 | 설명 |
|------|----------------|------|
| 페이지 제목 | `text-2xl font-bold` | 헤더 "건축 법규 자동 진단" |
| 섹션 헤더 | `text-sm font-semibold` | 카테고리명, 패널 제목 |
| 일반 본문 | `text-sm` | 설명문, 입력 필드 값 |
| 보조/캡션 | `text-xs` | 힌트, 주석, 단위 표시 |
| 극소 텍스트 | `text-[10px]`, `text-[11px]` | 세부 법조문, 각주 |
| 강조 수치 | `font-bold` | 건폐율·용적률 수치 |
| 라벨 | `font-medium` | 입력 필드 라벨 |

---

## 3. 버튼

### 종류별 클래스 조합

#### Primary — 파랑 (주요 액션)
```
bg-blue-600 text-white font-semibold py-3 px-4 rounded-lg
hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed
transition-colors
```
사용처: "법규 진단 시작", "요청 발송"  
파일: `frontend/src/components/InputForm/index.jsx:599`

#### Primary — 에메랄드 (AI 액션)
```
bg-emerald-600 text-white font-semibold px-4 py-2 rounded-lg
hover:bg-emerald-700 disabled:bg-gray-300
```
사용처: "질문하기"  
파일: `frontend/src/components/QueryBox/index.jsx:86`

#### Secondary — 흰 배경
```
bg-white border border-gray-300 text-gray-700 px-3 py-1.5 rounded-lg
hover:bg-gray-50 hover:border-gray-400 shadow-sm
```
사용처: "대지정보 수정 ✏️"  
파일: `frontend/src/App.jsx:37`

#### Danger — 빨강
```
bg-red-600 text-white font-semibold px-4 py-2 rounded-lg
hover:bg-red-700 disabled:bg-gray-300
```
사용처: "시니어 검토 요청"  
파일: `frontend/src/components/ReviewRequestButton/index.jsx:56`

#### Ghost — 텍스트 링크
```
text-xs text-blue-600 hover:text-blue-800 hover:underline
```
사용처: 조문 참조, 법령 링크

#### Outlined — 선택 필터
```
border border-gray-300 rounded px-3 py-1.5 text-xs text-gray-600
hover:bg-gray-100
```
사용처: 기간 필터 (7일 / 14일 / 30일)

#### Tag / Chip
```
bg-gray-100 hover:bg-gray-200 text-gray-600 px-2 py-1 rounded text-xs
```
사용처: 추천 질문 버튼

### 공통 disabled 처리
- `disabled:bg-gray-300` — 배경 회색
- `disabled:opacity-40` — 투명도
- `disabled:cursor-not-allowed`

---

## 4. 레이아웃

### 전체 구조

```
App (min-h-screen bg-gray-50)
│
├── Header  ─────────────────────────────── sticky top-0 z-10
│   bg-white border-b shadow-sm px-6 py-4
│   flex items-center justify-between
│   └── 아이콘 + 제목 + [수정 버튼] + [상태 배지]
│
├── Main  ───────────────────────────────── w-full px-6 py-6
│   ├── [초기 상태 / 대지정보 수정]
│   │   InputForm  max-w-screen-2xl mx-auto bg-white rounded-2xl shadow
│   │
│   └── [진단 결과 표시]
│       xl:grid xl:grid-cols-[295px_minmax(0,1fr)] gap-5
│       │
│       ├── 좌측 패널  ──────────── sticky top-4, 295px 고정
│       │   ├── 종합 판정 박스 (GREEN/YELLOW/RED)
│       │   ├── WhatIfPanel (슬라이더)
│       │   ├── LawChangeAlert (법규/고시 알림)
│       │   └── DataQualityBanner (데이터 품질)
│       │
│       └── 우측 영역  ──────────── flex-1, 2xl:grid-cols-2
│           ├── 심의·위험·수동검토 카드
│           ├── 8개 카테고리 카드
│           ├── LawInfoPanel (법령 조문)
│           ├── DevTrendPanel (개발 동향)
│           └── CaseReference (유사 케이스)
│
├── Drawer  ─────────────────────────────── fixed left-0 top-0 h-full
│   w-[580px] bg-white shadow-xl
│   transform: -translate-x-full ↔ translate-x-0 (transition)
│   └── 대지정보 수정용 InputForm
│
└── Footer  ─────────────────────────────── border-t text-center py-6
    면책 문구
```

### 입력 폼 내부 (3열 그리드)

```
grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_minmax(0,1fr)] gap-5

Column 1 — 기본 정보
  주소 검색, 건축물 용도, 용도지역, 지역지구, 신청 주체

Column 2 — 규모 / 면적 (중앙, 1.4배 너비)
  대지면적, 건축면적, 지상 연면적, 지하 연면적,
  지상 주차장, 피난안전구역, 층수, 높이, 세대수,
  주차대수, 조경면적, 공개공지

Column 3 — 선택 옵션
  용적률 완화 (녹색/에너지/지능형/장수명),
  결정고시, 건축협정, 높이·일조 보강,
  옥상조경, 발주처 지침서 업로드
```

### 간격 규칙

| 용도 | 클래스 | 값 |
|------|--------|----|
| 패널 간격 | `gap-5` | 1.25rem |
| 항목 간격 | `gap-3` | 0.75rem |
| 섹션 내 | `space-y-3` | 0.75rem |
| 인접 요소 | `space-y-2` | 0.5rem |
| 카드 패딩 | `p-4` | 1rem |
| 헤더 패딩 | `px-6 py-4` | 1.5rem / 1rem |

---

## 5. 컴포넌트 목록

### 핵심 컴포넌트

| 컴포넌트 | 경로 | 핵심 UI 요소 | 역할 |
|---------|------|-------------|------|
| `InputForm` | `components/InputForm/index.jsx` | 입력 필드 60+, 셀렉트, 체크박스, `<details>` 펼침 | 건축 정보 입력 폼 |
| `AddressSearch` | `components/AddressSearch/index.jsx` | 텍스트 입력, 자동완성 드롭다운 (최대 64개), 스피너 | 주소 검색 + PNU 추출 |
| `BriefUploader` | `components/BriefUploader/index.jsx` | PDF 드롭 업로드 박스, 추출 결과 테이블 | 발주처 지침서 PDF → 수치 추출 |
| `DiagnoseResult` | `components/DiagnoseResult/index.jsx` | 8개 카테고리 카드, 종합 판정 박스, 위험 경고 | 진단 결과 출력 |
| `WhatIfPanel` | `components/WhatIfPanel/index.jsx` | 슬라이더 × 5, 비교 매트릭스 | 시나리오 조정 (300ms 디바운스) |
| `QueryBox` | `components/QueryBox/index.jsx` | 텍스트영역, 추천 질문 × 4, 답변 카드, 히스토리 | 자연어 질의 (AI) |
| `CaseReference` | `components/CaseReference/index.jsx` | 케이스 카드 × 5 (유사도 표시) | 유사 사내 케이스 매칭 |
| `DataQualityBanner` | `components/DataQualityBanner/index.jsx` | 상태 배지 × 5, 이슈 리스트 | 데이터 출처·품질 경고 |
| `LawChangeAlert` | `components/LawChangeAlert/index.jsx` | 법규 변경 행, 행정 고시 행, 펼침 버튼 | 법규/조례 변경 알림 |
| `LawInfoPanel` | `components/LawInfoPanel/index.jsx` | 펼침 토글, 조문 3단 들여쓰기 | 토지이음 법령 본문 |
| `DevTrendPanel` | `components/DevTrendPanel/index.jsx` | 기간 필터, 인허가 행, 상세 펼침 | 주변 개발 인허가 동향 |
| `LegalReviewReport` | `components/LegalReviewReport/index.jsx` | A4 인쇄 테이블 × 10+, 메타 입력 | 법규 검토서 자동 생성 |
| `ReviewRequestButton` | `components/ReviewRequestButton/index.jsx` | 버튼 + 모달 (이름/메모 입력) | 시니어 검토 Slack 발송 |

### 세부 UI 요소

| 요소 | Tailwind 클래스 / 타입 | 사용 컴포넌트 |
|------|----------------------|-------------|
| **슬라이더** | `input[type="range"] accent-purple-600` | `WhatIfPanel` |
| **체크박스** | `w-4 h-4 accent-blue-600` (일반) / `accent-amber-600` (협정) | `InputForm` |
| **펼침 섹션** | `<details><summary>` + ▾/▲ 토글 아이콘 | `InputForm`, `DiagnoseResult` |
| **파일 업로드** | `<input type="file" accept=".pdf">` + 드래그앤드롭 영역 | `BriefUploader` |
| **자동완성 드롭다운** | `absolute z-10 bg-white border rounded-lg shadow-lg max-h-64 overflow-y-auto` | `AddressSearch` |
| **테이블** | `border-collapse w-full border-gray-200` | `LegalReviewReport`, 합필 내역 |
| **모달/오버레이** | `fixed inset-0 bg-black/40 z-20 transition-opacity` | 검토서, 심의 상세 |
| **드로어** | `fixed top-0 left-0 h-full w-[580px] -translate-x-full transition-transform` | 대지정보 수정 |
| **로딩 스피너** | `animate-spin` (⟳ 아이콘) | `AddressSearch`, `DiagnoseResult` |
| **배지** | `inline-flex px-2 py-0.5 rounded-full text-xs font-medium` | 상태 라벨 전역 |
| **카드** | `rounded-xl border p-4 space-y-2` | 카테고리 카드 전역 |
| **알림 박스** | `rounded-lg border p-3 flex items-start gap-2` | 성공/경고/오류/정보 |

---

## 6. 폼 필드 표준

### 입력 필드 클래스 (공통)

```
w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm
focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
```

### 라벨 구조

```jsx
<label className="block text-sm font-medium text-gray-700 mb-1">
  항목명 <span className="text-red-500">*</span>          {/* 필수 */}
  <span className="text-gray-400 text-xs">(힌트 텍스트)</span>  {/* 힌트 */}
</label>
```

### 알림 / 피드백 박스

| 종류 | 클래스 |
|------|--------|
| 성공 ✅ | `bg-green-50 border-green-200 text-green-700` |
| 경고 ⚠️ | `bg-yellow-50 border-yellow-200 text-yellow-800` |
| 오류 🔴 | `bg-red-50 border-red-200 text-red-700` |
| 정보 ℹ️ | `bg-blue-50 border-blue-200 text-blue-700` |

---

## 7. 인쇄 스타일 (법규 검토서)

```css
/* 화면 UI 요소 숨김 */
.no-print { display: none !important; }

/* A4 용지 설정 */
@media print {
  font-family: 'Malgun Gothic', '맑은 고딕', sans-serif;
  /* 페이지 나누기 제어 */
}
```

파일: `frontend/src/components/LegalReviewReport/index.jsx:620-640`

---

## 8. 기술 스택 요약

| 항목 | 내용 |
|------|------|
| 프레임워크 | React 19 |
| 스타일 | Tailwind CSS 3.4 |
| 상태관리 | Zustand |
| 아이콘 | 유니코드 이모지 (✅ ⚠️ 🔴 📋 등) |
| 반응형 | 데스크톱 중심 (xl, 2xl 브레이크포인트) |
| 색상 철학 | 시그널 기반 (GREEN / YELLOW / RED) + 브랜드 파랑 |
| 빌드 | Vite |
