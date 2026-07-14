# arch-law-diagnose

사내 전용 건축 법규 자동 진단 시스템.  
주소와 건물 정보를 입력하면 8개 법규 카테고리를 자동 검토하고 **GREEN / YELLOW / RED** 신호와 종합 점수(0~10)를 반환한다.

> 결과는 참고용. 실제 인허가 판단은 시니어 건축사가 한다.

---

## 빠른 시작 (로컬)

```bash
# 1. 환경 변수 설정
cp .env.example .env   # 필수 키 6개 채우기 (아래 표 참고)

# 2. 서버 일괄 시작 (백엔드 8000 + 프론트 5173)
start-servers.bat

# 브라우저: http://localhost:5173
```

백엔드만 수동으로 시작하려면:

```bash
cd backend
.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 환경 변수 (.env)

| 변수 | 필수 | 용도 |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | AI 판단 (설비·소방, 자연어 질의, 조례 수치 추출) |
| `VWORLD_API_KEY` | ✅ | 용도지역 조회, 좌표 변환, 도시계획시설·지구단위계획구역 WFS |
| `KAKAO_API_KEY` | ✅ | 주소 자동완성, 학교 근접 조회(교육환경평가) |
| `EUM_ID` / `EUM_KEY` | ✅ | 토지이음 — 행위제한·법령정보·개발 인허가 |
| `LAW_API_KEY` | ✅ | 법제처 — 조례 본문 수집 |
| `LURIS_API_KEY` | 선택 | LURIS 행위제한 (EUM 교차검증) |
| `GRAPH_API_URL` | 선택 | arch-law-graph 서비스 URL (기본값: 프로덕션 Cloud Run) |
| `ANTHROPIC_MODEL` | 선택 | 기본값 `claude-sonnet-4-6` |

전체 목록과 기본값은 [`.env.example`](.env.example) 참조.

---

## 아키텍처

```
브라우저 (React + Vite + Tailwind)
    ↕ HTTP
FastAPI 백엔드 (Python 3.12, 포트 8000)
    ├── 진단 엔진 (건폐율·용적률·높이·주차·조경·행위제한·도시계획시설·설비소방)
    ├── 사업성 모드 (What-If 슬라이더, 다중 대지 비교, MD/Excel 내보내기)
    ├── 법규 의미 그래프 (networkx, 138노드)
    └── SQLite 캐시 (조례 30일 TTL)
    ↕
외부 API: VWorld · 토지이음(EUM) · LURIS · 법제처 · Anthropic Claude
자매 앱: arch-law-graph (법령 원문 RAG 그라운딩, graceful degrade)
```

---

## 진단 카테고리

| 카테고리 | 계산기 |
|---|---|
| 행위제한 | `land_use_act.py` |
| 도시계획시설 | `urban_facility.py` (VWorld WFS 실시간) |
| 건폐율 | `coverage.py` |
| 용적률 | `far.py` (완화 4종 활성 — 공개공지·녹색건축·ZEB·시범사업) |
| 높이·일조 | `height.py` |
| 주차 | `parking.py` |
| 조경 | `landscape.py` |
| 설비·소방 | `fire_safety.py` (Claude AI 정성 판단) |

신호 판정: **RED** = 위반 항목 있음 / **YELLOW** = 확인 필요 or 점수 < 7.0 / **GREEN** = 전항목 통과 + 점수 ≥ 7.0

---

## 테스트

```bash
cd backend
pytest tests/ -q
```

---

## GCP Cloud Run 배포

Docker 단일 컨테이너(포트 8080)로 배포. 상세 절차는 [DEPLOY.md](DEPLOY.md) 참조.

```bash
docker build -t arch-law-diagnose .
docker run --env-file .env -p 8080:8080 arch-law-diagnose
# http://localhost:8080
```

---

## 관련 앱

| 앱 | 역할 |
|---|---|
| **arch-law-diagnose** (이 앱) | 대지 판정 — 주소 입력 → 법규 통과/위반 계산 |
| **arch-law-graph** | 법령 지식 — 조문 검색·원문·판례·지자체 비교 |
