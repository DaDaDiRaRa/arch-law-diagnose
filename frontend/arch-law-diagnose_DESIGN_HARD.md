# DESIGN AUDIT — 하드코딩 스타일 값 전수 조사

> 기준일: 2026-05-22  
> 스캔 범위: `frontend/src/**/*.{jsx,js,css}` + `frontend/tailwind.config.js`  
> 제외: `kunwon-tokens.css` (토큰 정의 파일), `node_modules/`, `dist/`  
> 참조 토큰: `frontend/src/kunwon-tokens.css`

---

## 범례

| 아이콘 | 의미 |
|--------|------|
| ✅ | 정확히 일치하는 토큰 있음 |
| ⚠️ | 근사값 토큰 있음 (1~2px 차이) |
| 🆕 | 신규 토큰 추가 필요 |
| ❌ | 토큰 매핑 불가 (특수 목적 값) |

---

## 1. 잔존 Hex 색상 (LegalReviewReport 다크 툴바)

> `LegalReviewReport`의 인쇄 미리보기 툴바는 어두운 배경이 의도적. 별도 다크 테마 토큰 그룹 추가 검토 필요.

| 값 | 파일 | 줄 | 교체할 토큰 |
|---|---|---|---|
| `#525659` | `src/components/LegalReviewReport/index.jsx` | 624 | ❌ 매핑 없음 — 다크 프린트 오버레이. `--color-print-overlay` 신규 토큰 권장 |
| `#2d2d2d` | `src/components/LegalReviewReport/index.jsx` | 630 | ❌ 매핑 없음 — 다크 툴바 배경. `--color-print-toolbar` 신규 토큰 권장 |
| `#555` | `src/components/LegalReviewReport/index.jsx` | 637 | ❌ 매핑 없음 — 다크 툴바 테두리. `--color-print-border` 신규 토큰 권장 |
| `#3d3d3d` | `src/components/LegalReviewReport/index.jsx` | 638 | ❌ 매핑 없음 — 다크 입력 배경. `--color-print-input` 신규 토큰 권장 |
| `#555` | `src/components/LegalReviewReport/index.jsx` | 644 | ❌ 매핑 없음 — 위와 동일 |
| `#3d3d3d` | `src/components/LegalReviewReport/index.jsx` | 645 | ❌ 매핑 없음 — 위와 동일 |
| `#4d4d4d` | `src/components/LegalReviewReport/index.jsx` | 647 | ❌ 매핑 없음 — 다크 툴바 호버. `--color-print-toolbar-hover` 신규 토큰 권장 |

---

## 2. 잔존 px 값 (LegalReviewReport styles 문자열)

| 값 | 파일 | 줄 | 교체할 토큰 |
|---|---|---|---|
| `6px` | `src/components/LegalReviewReport/index.jsx` | 637 | ⚠️ `var(--gap-xs)` (4px) 또는 `var(--gap-sm)` (8px) — 중간값, 새 토큰 `--gap-2xs: 6px` 권장 |
| `16px` | `src/components/LegalReviewReport/index.jsx` | 644 | 🆕 매핑 없음 — `--gap-md`(12)와 `--gap-lg`(20) 사이. `--gap-4: 16px` 신규 토큰 권장 |
| `letter-spacing: 12px` | `src/components/LegalReviewReport/index.jsx` | 658 | ❌ `--gap-md`와 값은 같으나 의미 상이 (자간 ≠ 간격) — 매핑 부적절 |
| `margin-bottom: 16px` | `src/components/LegalReviewReport/index.jsx` | 662 | 🆕 `--gap-4: 16px` 신규 토큰 권장 |
| `padding-left: 10px` | `src/components/LegalReviewReport/index.jsx` | 676 | ⚠️ `var(--gap-sm)` (8px)과 `var(--gap-md)` (12px) 사이. 🆕 신규 토큰 `--gap-3: 10px` 권장 |
| `border: 1px` (각 테이블) | `src/components/LegalReviewReport/index.jsx` | 686 | ❌ 테두리 두께 1px — 토큰화 불필요 |
| `font-size: 11.5px` | `src/components/LegalReviewReport/index.jsx` | 687 | ⚠️ `var(--font-size-xs)` (11px, 0.5px 차이) — 통일 권장 |
| `margin-top: 40px` | `src/components/LegalReviewReport/index.jsx` | 704 | 🆕 `--gap-xl`(32px)과 `--layout-content-py`(32px) 초과. `--gap-2xl: 40px` 신규 토큰 권장 |
| `margin-top: 16px` | `src/components/LegalReviewReport/index.jsx` | 706 | 🆕 `--gap-4: 16px` 신규 토큰 권장 |
| `padding: 20mm 15mm` | `src/components/LegalReviewReport/index.jsx` | 715 | ❌ 인쇄 전용 mm 단위 — 토큰화 불필요 |

---

## 3. 인라인 style={{}} — em 상대값 (LegalReviewReport)

> 부모 폰트 크기에 상대적인 값. 절대 px 토큰으로 통일 권장.

| 값 | 파일 | 줄 | 교체할 토큰 |
|---|---|---|---|
| `fontSize: '0.85em'` | `src/components/LegalReviewReport/index.jsx` | 126 | ⚠️ `var(--font-size-xs)` (11px ≈ 0.85×13px) |
| `fontSize: '0.85em'` | `src/components/LegalReviewReport/index.jsx` | 180 | ⚠️ `var(--font-size-xs)` |
| `fontSize: '0.9em'` | `src/components/LegalReviewReport/index.jsx` | 210 | ⚠️ `var(--font-size-sm)` (12px ≈ 0.9×13px) |
| `fontSize: '0.85em'` | `src/components/LegalReviewReport/index.jsx` | 215 | ⚠️ `var(--font-size-xs)` |
| `fontSize: '0.85em'` | `src/components/LegalReviewReport/index.jsx` | 221 | ⚠️ `var(--font-size-xs)` |
| `fontSize: '0.9em'` | `src/components/LegalReviewReport/index.jsx` | 333 | ⚠️ `var(--font-size-sm)` |
| `fontSize: '0.9em'` | `src/components/LegalReviewReport/index.jsx` | 541 | ⚠️ `var(--font-size-sm)` |
| `fontSize: '0.9em'` | `src/components/LegalReviewReport/index.jsx` | 560 | ⚠️ `var(--font-size-sm)` |

---

## 4. 인라인 style={{}} — percentage width (LegalReviewReport)

> 테이블 컬럼 비율 조정용. CSS 변수 토큰화 불필요.

| 값 | 파일 | 줄 | 교체할 토큰 |
|---|---|---|---|
| `width: '14%'` | `src/components/LegalReviewReport/index.jsx` | 289 | ❌ 테이블 컬럼 비율 — 토큰화 불필요 |
| `width: '24%'` | `src/components/LegalReviewReport/index.jsx` | 290 | ❌ 테이블 컬럼 비율 — 토큰화 불필요 |
| `width: '40%'` | `src/components/LegalReviewReport/index.jsx` | 291 | ❌ 테이블 컬럼 비율 — 토큰화 불필요 |
| `width: '12%'` | `src/components/LegalReviewReport/index.jsx` | 292 | ❌ 테이블 컬럼 비율 — 토큰화 불필요 |
| `width: '10%'` | `src/components/LegalReviewReport/index.jsx` | 293 | ❌ 테이블 컬럼 비율 — 토큰화 불필요 |
| `width: '20%'` | `src/components/LegalReviewReport/index.jsx` | 325 | ❌ 테이블 컬럼 비율 — 토큰화 불필요 |
| `width: '20%'` | `src/components/LegalReviewReport/index.jsx` | 540 | ❌ 테이블 컬럼 비율 — 토큰화 불필요 |
| `width: '12%'` | `src/components/LegalReviewReport/index.jsx` | 549 | ❌ 테이블 컬럼 비율 — 토큰화 불필요 |

---

## 5. Tailwind Arbitrary 값 — `text-[10px]`

> 프로젝트 전체에서 가장 많이 쓰이는 하드코딩 값. `--font-size-xs`(11px)와 1px 차이. 새 토큰 `--font-size-2xs: 10px` 추가 후 일괄 교체 권장.

| 값 | 파일 | 줄 | 교체할 토큰 |
|---|---|---|---|
| `text-[10px]` | `src/App.jsx` | — | 🆕 `text-[var(--font-size-2xs)]` (신규 토큰 추가 시) |
| `text-[10px]` | `src/components/BriefUploader/index.jsx` | 77 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/BriefUploader/index.jsx` | 113 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/BriefUploader/index.jsx` | 122 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/BriefUploader/index.jsx` | 133 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/BriefUploader/index.jsx` | 138 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/BriefUploader/index.jsx` | 145 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/BriefUploader/index.jsx` | 155 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/CaseReference/index.jsx` | 51 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/CaseReference/index.jsx` | 131 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/CaseReference/index.jsx` | 134 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/CaseReference/index.jsx` | 148 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/DataQualityBanner/index.jsx` | 25 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/DataQualityBanner/index.jsx` | 98 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/DevTrendPanel/index.jsx` | 128 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/DevTrendPanel/index.jsx` | 183 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/DevTrendPanel/index.jsx` | 196 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/DevTrendPanel/index.jsx` | 201 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/DevTrendPanel/index.jsx` | 208 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/DevTrendPanel/index.jsx` | 214 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/DiagnoseResult/index.jsx` | 210 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/DiagnoseResult/index.jsx` | 364 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/DiagnoseResult/index.jsx` | 413 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/DiagnoseResult/index.jsx` | 432 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/DiagnoseResult/index.jsx` | 441 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/DiagnoseResult/index.jsx` | 805 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/DiagnoseResult/index.jsx` | 818 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/InputForm/index.jsx` | 478 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/InputForm/index.jsx` | 503 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/InputForm/index.jsx` | 519 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/InputForm/index.jsx` | 539 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/InputForm/index.jsx` | 550 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/InputForm/index.jsx` | 590 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/InputForm/index.jsx` | 632 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/InputForm/index.jsx` | 635 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/InputForm/index.jsx` | 641 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/InputForm/index.jsx` | 712 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/InputForm/index.jsx` | 730 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/LawChangeAlert/index.jsx` | 78 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/LawChangeAlert/index.jsx` | 175 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/LawChangeAlert/index.jsx` | 201 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/LawChangeAlert/index.jsx` | 225 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/LawInfoPanel/index.jsx` | 72 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/LawInfoPanel/index.jsx` | 88 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/LawInfoPanel/index.jsx` | 119 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/WhatIfPanel/index.jsx` | 205 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/WhatIfPanel/index.jsx` | 222 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/WhatIfPanel/index.jsx` | 266 | 🆕 `text-[var(--font-size-2xs)]` |
| `text-[10px]` | `src/components/WhatIfPanel/index.jsx` | 311 | 🆕 `text-[var(--font-size-2xs)]` |

---

## 6. Tailwind Arbitrary 값 — `text-[11px]`

> `--font-size-xs: 11px`와 정확히 일치. Tailwind config 확장 클래스 `text-token-xs`로 즉시 교체 가능.

| 값 | 파일 | 줄 | 교체할 토큰 |
|---|---|---|---|
| `text-[11px]` | `src/components/CaseReference/index.jsx` | 53 | ✅ `text-token-xs` (`var(--font-size-xs)`) |
| `text-[11px]` | `src/components/CaseReference/index.jsx` | 156 | ✅ `text-token-xs` |
| `text-[11px]` | `src/components/DevTrendPanel/index.jsx` | 96 | ✅ `text-token-xs` |
| `text-[11px]` | `src/components/DevTrendPanel/index.jsx` | 192 | ✅ `text-token-xs` |
| `text-[11px]` | `src/components/DiagnoseResult/index.jsx` | 425 | ✅ `text-token-xs` |
| `text-[11px]` | `src/components/LawChangeAlert/index.jsx` | 228 | ✅ `text-token-xs` |
| `text-[11px]` | `src/components/ReviewRequestButton/index.jsx` | 59 | ✅ `text-token-xs` |
| `text-[11px]` | `src/components/WhatIfPanel/index.jsx` | 224 | ✅ `text-token-xs` |
| `text-[11px]` | `src/components/WhatIfPanel/index.jsx` | 230 | ✅ `text-token-xs` |

---

## 7. Tailwind Arbitrary 값 — `w-[580px]`

| 값 | 파일 | 줄 | 교체할 토큰 |
|---|---|---|---|
| `w-[580px]` | `src/App.jsx` | 118 | ✅ `w-[var(--panel-width-lg)]` (`--panel-width-lg: 580px`) |

---

## 요약 통계

| 분류 | 건수 | 즉시 교체 가능 | 신규 토큰 필요 | 교체 불필요 |
|------|------|--------------|-------------|-----------|
| 잔존 Hex (다크 툴바) | 7 | 0 | 7 | 0 |
| 잔존 px (styles 문자열) | 10 | 0 | 5 | 5 |
| 인라인 em 값 | 8 | 0 | 8 | 0 |
| 인라인 % width | 8 | 0 | 0 | 8 |
| `text-[10px]` | 48 | 0 | 48 | 0 |
| `text-[11px]` | 9 | 9 | 0 | 0 |
| `w-[580px]` | 1 | 1 | 0 | 0 |
| **합계** | **91** | **10** | **68** | **13** |

---

## 권장 조치

### 우선순위 1 — 즉시 교체 (10건, 신규 토큰 불필요)

`text-[11px]` 9건 + `w-[580px]` 1건. `tailwind.config.js`에 이미 `text-token-xs`가 정의되어 있으므로 단순 치환.

```bash
# 예: text-[11px] → text-token-xs 일괄 치환
# 각 파일에서 수동 또는 sed로 교체
```

### 우선순위 2 — 신규 토큰 추가 후 교체 (48건)

`kunwon-tokens.css`에 아래 토큰 추가:

```css
:root {
  --font-size-2xs: 10px;   /* 배지·법조문 극소 텍스트 */
  --gap-2xs: 6px;           /* fire-items 등 중간 간격 */
  --gap-4: 16px;            /* 섹션 구분 표준 여백 */
  --gap-2xl: 40px;          /* 푸터·서명란 큰 여백 */
}
```

추가 후 `tailwind.config.js`의 `fontSize`·`spacing` 섹션에 등록하면
`text-[10px]` → `text-[var(--font-size-2xs)]` 일괄 치환 가능.

### 우선순위 3 — 다크 툴바 토큰 분리 (7건)

`LegalReviewReport` 전용 프린트 뷰 다크 색상. `kunwon-tokens.css` 말미에 추가:

```css
/* 인쇄 미리보기 전용 (화면 노출 없음) */
:root {
  --color-print-overlay:      #525659;
  --color-print-toolbar:      #2d2d2d;
  --color-print-toolbar-hover:#4d4d4d;
  --color-print-border:       #555555;
  --color-print-input:        #3d3d3d;
}
```

### 교체 불필요 (13건)

- 테이블 컬럼 `%` width — 콘텐츠 종속 레이아웃 비율
- `letter-spacing: 12px` — 자간 값, 공백 토큰과 의미 상이
- `border: 1px` — 테두리 두께 1px 상수
- `padding: 20mm 15mm` — 인쇄 mm 단위
