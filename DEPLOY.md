# 배포 가이드 — GCP Cloud Run (단일 컨테이너)

> 작성 기준: arch-law-diagnose (FastAPI + React/Vite)  
> 플랫폼: Google Cloud Run  
> 포트: 8080 (Cloud Run 기본값)  
> 전략: 프론트엔드를 백엔드가 직접 서빙하는 **단일 컨테이너** 방식

---

## 목차

1. [전체 구조 결정 배경](#1-전체-구조-결정-배경)
2. [멀티 스테이지 Dockerfile](#2-멀티-스테이지-dockerfile)
3. [.dockerignore](#3-dockerignore)
4. [백엔드 코드 변경](#4-백엔드-코드-변경)
5. [로컬 빌드·검증](#5-로컬-빌드검증)
6. [GCP Cloud Run 배포 절차](#6-gcp-cloud-run-배포-절차)
7. [환경 변수 주입 (Secret Manager)](#7-환경-변수-주입-secret-manager)
8. [겪은 오류와 해결](#8-겪은-오류와-해결)
9. [Cloud Run 특성상 주의할 점](#9-cloud-run-특성상-주의할-점)
10. [다른 앱에 적용할 때 체크리스트](#10-다른-앱에-적용할-때-체크리스트)

---

## 1. 전체 구조 결정 배경

### 선택지

| 방식 | 장점 | 단점 |
|------|------|------|
| **단일 컨테이너** (채택) | 포트 1개, 설정 단순, CORS 불필요 | 백엔드 재배포 시 프론트도 함께 빌드 |
| 분리 컨테이너 (API + CDN) | 독립 배포, CDN 캐시 가능 | CORS 설정 필요, Cloud Run 2개 + Load Balancer 비용 |
| Cloud Run + Firebase Hosting | 프론트 CDN 분리 | 설정 복잡도 증가 |

**단일 컨테이너를 선택한 이유:**
- 사내 전용 앱으로 트래픽이 많지 않음
- React 빌드 결과물을 FastAPI가 직접 서빙하면 CORS 헤더 불필요
- Cloud Run 하나만 관리하면 됨

### 최종 컨테이너 내부 구조

```
/app/
├── backend/          ← WORKDIR, uvicorn 실행 위치
│   ├── main.py
│   ├── services/
│   └── ...
└── frontend/
    └── dist/         ← React 빌드 산출물 (Stage 1에서 복사)
        ├── index.html
        └── assets/
```

---

## 2. 멀티 스테이지 Dockerfile

```dockerfile
# ── Stage 1: 프론트엔드 빌드 ──────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci                      # --ignore-scripts 붙이지 말 것 (⚠ 오류 #1 참고)
COPY frontend/ ./
RUN npm run build


# ── Stage 2: 백엔드 런타임 ───────────────────────────────
FROM python:3.12-slim

# shapely/pyproj 는 시스템 C 라이브러리 필요 (⚠ 오류 #2 참고)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgeos-dev \
        libproj-dev \
        proj-data \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# requirements 먼저 → 소스 나중 (레이어 캐시 최적화)
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# Stage 1 결과물 복사 (⚠ 오류 #3 참고)
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

# WORKDIR이 /app/backend이므로 --app-dir 플래그 불필요
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 레이어 캐시 전략

```
COPY package*.json → npm ci       # 의존성 레이어 (느림, 자주 안 바뀜)
COPY frontend/ → npm run build    # 소스 레이어 (소스 변경 시만 재실행)
---
COPY requirements.txt → pip install  # 의존성 레이어
COPY backend/ ./                     # 소스 레이어
```

소스만 수정한 경우 의존성 설치 레이어는 캐시에서 재사용된다.

---

## 3. .dockerignore

```gitignore
# Git
.git
.gitignore

# 환경 변수 — 절대 이미지에 포함하지 않음
.env
.env.*
!.env.example          # 예시 파일은 포함해도 무방

# Node 의존성 / 빌드 산출물
node_modules/          # Stage 1에서 새로 설치하므로 불필요
frontend/dist          # Stage 1에서 빌드하므로 불필요

# Python 캐시 / 가상환경
backend/.venv/
**/__pycache__/
**/*.pyc

# 데이터 / 런타임 파일 (⚠ 오류 #4 참고)
backend/data/          # SQLite DB — Cloud Run은 ephemeral, 이미지에 넣지 않음
files/
*.db
*.sqlite

# 개발 도구
.vscode/
.idea/
*.log
*.tmp
```

**핵심 규칙:**
- `.env` 는 절대 포함하지 않는다 → Secret Manager로 주입
- `node_modules/`, `frontend/dist` 는 빌드 컨텍스트에서 제외해 전송 속도 향상
- `backend/data/` (SQLite) 는 이미지에 넣지 않는다 — Cloud Run 인스턴스가 종료되면 사라짐

---

## 4. 백엔드 코드 변경

Cloud Run 배포를 위해 `backend/main.py`를 두 곳 수정했다.

### 4-1. CORS allow_origins

```python
# 변경 전 — 로컬 개발 전용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    ...
)

# 변경 후 — 단일 컨테이너 서빙이므로 CORS 자체가 불필요하지만,
# 향후 분리 배포나 API 직접 호출 대비해 전체 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

> 단일 컨테이너로 같은 origin에서 API를 호출하면 CORS가 발동하지 않으므로
> `["*"]` 는 외부 클라이언트 대응용이다. 보안이 민감하면 Cloud Run URL로 제한.

### 4-2. 프론트엔드 정적 파일 서빙

`main.py` 맨 끝에 추가. `/api/*` 라우트는 위에서 먼저 매칭되므로 충돌 없음.

```python
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _DIST.is_dir():
    # Vite 빌드 결과물의 /assets 디렉터리를 정적으로 서빙
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        # React Router 등 SPA 라우팅 — 모든 미매칭 경로를 index.html로
        return FileResponse(str(_DIST / "index.html"))
```

**`if _DIST.is_dir():` 조건의 역할:**  
로컬 개발 환경(`npm run dev` 별도 실행)에서는 `dist/`가 없으므로
이 블록이 실행되지 않는다 — 기존 개발 방식 그대로 유지.

---

## 5. 로컬 빌드·검증

```bash
# 프로젝트 루트에서

# 1. 이미지 빌드
docker build -t arch-law-diagnose:local .

# 2. 컨테이너 실행 (환경 변수 직접 주입)
docker run --rm -p 8080:8080 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -e VWORLD_API_KEY=... \
  -e KAKAO_API_KEY=... \
  arch-law-diagnose:local

# 3. 확인
curl http://localhost:8080/health          # {"status":"ok"}
open http://localhost:8080                 # 프론트엔드 화면

# 이미지 크기 확인
docker images arch-law-diagnose:local
```

---

## 6. GCP Cloud Run 배포 절차

### 6-1. 사전 준비

```bash
# GCP CLI 설치 확인
gcloud version

# 프로젝트 설정
gcloud config set project YOUR_PROJECT_ID

# Artifact Registry 활성화 (최초 1회)
gcloud services enable artifactregistry.googleapis.com run.googleapis.com

# 저장소 생성 (최초 1회)
gcloud artifacts repositories create arch-law \
  --repository-format=docker \
  --location=asia-northeast3 \
  --description="arch-law-diagnose container images"

# Docker 인증 설정
gcloud auth configure-docker asia-northeast3-docker.pkg.dev
```

### 6-2. 이미지 빌드 & 푸시

```bash
IMAGE=asia-northeast3-docker.pkg.dev/YOUR_PROJECT_ID/arch-law/app

# 빌드 (M1/M2 Mac이라면 --platform linux/amd64 추가)
docker build --platform linux/amd64 -t $IMAGE:latest .

# 푸시
docker push $IMAGE:latest
```

### 6-3. Cloud Run 서비스 배포

```bash
gcloud run deploy arch-law-diagnose \
  --image $IMAGE:latest \
  --region asia-northeast3 \
  --platform managed \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 60 \
  --concurrency 80 \
  --min-instances 0 \
  --max-instances 3 \
  --set-secrets "ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest" \
  --set-secrets "VWORLD_API_KEY=VWORLD_API_KEY:latest" \
  --set-secrets "KAKAO_API_KEY=KAKAO_API_KEY:latest" \
  --set-secrets "EUM_ID=EUM_ID:latest" \
  --set-secrets "EUM_KEY=EUM_KEY:latest" \
  --no-allow-unauthenticated   # 사내 전용 → 인증 필요
```

> `--no-allow-unauthenticated`: IAM으로 접근 제어. 사내 Google 계정만 허용.  
> 외부 공개가 필요하면 `--allow-unauthenticated`로 변경.

### 6-4. 재배포 (코드 변경 시)

```bash
# 이미지 빌드 → 푸시 → 서비스 업데이트
docker build --platform linux/amd64 -t $IMAGE:latest . \
  && docker push $IMAGE:latest \
  && gcloud run services update-traffic arch-law-diagnose \
       --to-latest --region asia-northeast3
```

---

## 7. 환경 변수 주입 (Secret Manager)

`.env` 파일을 이미지에 포함하지 않는다. 대신 GCP Secret Manager를 사용.

```bash
# 시크릿 생성 (최초 1회, 값은 직접 입력)
echo -n "sk-ant-실제키값" | \
  gcloud secrets create ANTHROPIC_API_KEY --data-file=-

echo -n "실제키값" | \
  gcloud secrets create VWORLD_API_KEY --data-file=-

# 기존 시크릿 값 업데이트
echo -n "새로운키값" | \
  gcloud secrets versions add ANTHROPIC_API_KEY --data-file=-

# Cloud Run 서비스 계정에 시크릿 접근 권한 부여 (최초 1회)
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding ANTHROPIC_API_KEY \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 환경 변수 목록 (이 프로젝트 기준)

| 시크릿명 | 필수 | 용도 |
|---------|------|------|
| `ANTHROPIC_API_KEY` | ✅ | Claude AI |
| `VWORLD_API_KEY` | ✅ | 지적도·좌표 |
| `KAKAO_API_KEY` | ✅ | 주소 자동완성 |
| `EUM_ID` / `EUM_KEY` | ⚠ | 토지이음 API |
| `JUSO_API_KEY` | ⚠ | 도로명주소 API |
| `SLACK_WEBHOOK_URL` | ⚪ | 시니어 검토 알림 |
| `LAW_API_KEY` | ⚪ | 법제처 DRF |

누락 시 graceful degrade — 해당 항목만 YELLOW 처리.

---

## 8. 겪은 오류와 해결

### 오류 #1 — `npm ci --ignore-scripts` 빌드 실패

**증상:** Vite 빌드 중 `postinstall` 스크립트가 스킵되어 의존 패키지 초기화 실패.

**원인:** `--ignore-scripts` 플래그가 `package.json`의 postinstall 훅을 막음.
일부 패키지는 postinstall에서 바이너리 다운로드나 초기화를 수행함.

**해결:** 플래그 제거.
```dockerfile
# 잘못된 방식
RUN npm ci --ignore-scripts

# 올바른 방식
RUN npm ci
```

---

### 오류 #2 — `shapely` / `pyproj` import 실패

**증상:** 컨테이너 실행 시 `ImportError: libgeos_c.so.1: cannot open shared object file`

**원인:** `python:3.12-slim`은 최소 이미지라 GEOS/PROJ C 라이브러리가 없음.
`shapely`와 `pyproj`는 pip로 Python 패키지만 설치해선 안 되고
시스템 라이브러리가 필요함.

**해결:** apt로 시스템 라이브러리 선 설치.
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgeos-dev \
        libproj-dev \
        proj-data \
        gcc \
    && rm -rf /var/lib/apt/lists/*
```

> **다른 앱 적용 시:**  
> `opencv-python` → `libgl1`, `libglib2.0-0`  
> `Pillow` → `libjpeg-dev`, `zlib1g-dev`  
> `psycopg2` → `libpq-dev`  
> `cryptography` → `libssl-dev`, `libffi-dev`

---

### 오류 #3 — uvicorn이 `main` 모듈을 못 찾음

**증상:** `ModuleNotFoundError: No module named 'main'`

**원인:** 첫 번째 Dockerfile에서 `WORKDIR /app`으로 설정하고
`--app-dir /app/backend` 플래그를 쓴 것이 오동작.
uvicorn이 `sys.path`를 `/app/backend`로 바꾸기 전에 모듈을 찾으려 해서 실패.

**해결:** `WORKDIR`을 실행 위치로 직접 지정. `--app-dir` 불필요.
```dockerfile
# 잘못된 방식
WORKDIR /app
CMD ["python", "-m", "uvicorn", "main:app", "--app-dir", "/app/backend", ...]

# 올바른 방식
WORKDIR /app/backend
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

---

### 오류 #4 — `backend/data/` vs `data/` .dockerignore 경로

**증상:** SQLite DB 파일(300MB+)이 빌드 컨텍스트에 포함되어 `docker build` 가 느림.

**원인:** `.dockerignore`에 `data/`를 루트 기준으로 작성했는데,
실제 DB는 `backend/data/`에 있어서 제외 규칙이 적용되지 않음.

**해결:** 정확한 경로 명시.
```gitignore
# 잘못된 방식
data/

# 올바른 방식
backend/data/
```

> `.dockerignore` 패턴은 `gitignore`와 비슷하지만 루트 기준 절대 경로임.
> 서브디렉터리를 제외하려면 전체 경로를 써야 한다.

---

### 오류 #5 — 로컬 개발 CORS 오류

**증상:** 배포 후 API 호출이 `CORS policy` 오류로 차단됨.

**원인:** `allow_origins`가 `["http://localhost:5173"]`로 고정되어 있었음.
Cloud Run URL(`https://arch-law-diagnose-xxxx.run.app`)이 허용 목록에 없음.

**해결:** 단일 컨테이너 배포에서는 같은 origin이므로 CORS 자체가 불필요.
외부 API 클라이언트 대응으로 `["*"]`로 변경.
```python
allow_origins=["*"]
```

> 보안이 중요하면 Cloud Run URL로 제한:
> `allow_origins=["https://arch-law-diagnose-xxxx.a.run.app"]`

---

### 오류 #6 — SPA 새로고침 404

**증상:** `/diagnose` 같은 React Router 경로에서 새로고침하면 404 반환.

**원인:** FastAPI는 `/diagnose` 라는 라우트를 모름.
React Router 경로는 브라우저에서만 처리되는데,
서버는 실제 파일이 없어서 404를 돌려줌.

**해결:** catch-all 라우트로 모든 미매칭 요청을 `index.html`로 반환.
```python
@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    return FileResponse(str(_DIST / "index.html"))
```

> **중요:** 이 라우트는 반드시 모든 API 라우트 선언 **이후**에 위치해야 함.
> FastAPI는 라우트를 등록 순서대로 매칭하므로, 먼저 선언된 `/api/*` 가 우선됨.

---

## 9. Cloud Run 특성상 주의할 점

### SQLite / 로컬 파일 저장 불가

Cloud Run 컨테이너는 요청 처리 후 종료될 수 있고 디스크가 **ephemeral**이다.
인스턴스가 교체되면 `data/arch_law.db` 같은 로컬 파일이 사라진다.

**대안:**

| 현재 용도 | Cloud Run 대응 |
|---------|--------------|
| SQLite 캐시 DB | Cloud SQL (PostgreSQL) 또는 Firestore |
| 파일 업로드 임시 저장 | Cloud Storage (GCS) |
| 세션 / 상태 공유 | Redis (Memorystore) |

> 이 프로젝트는 캐시 DB라 손실되어도 재조회로 복구 가능.
> 운영 전에 Cloud SQL 마이그레이션 검토 필요.

### 콜드 스타트

`--min-instances 0`이면 트래픽 없을 때 인스턴스가 0으로 줄어든다.
첫 요청 시 1~3초 콜드 스타트 발생.

```bash
# 최소 1개 유지 (콜드 스타트 방지, 비용 발생)
--min-instances 1
```

### 타임아웃

Cloud Run 기본 타임아웃은 60초. AI 호출 등 긴 작업은 늘려야 함.

```bash
--timeout 300   # 최대 3600초
```

### 인스턴스당 동시 요청

```bash
--concurrency 80   # 인스턴스당 최대 동시 요청 수 (기본값)
```

uvicorn의 async 특성상 80 정도는 문제없음.
CPU 집약 작업(shapely 연산 등)이 많으면 낮추는 것 고려.

---

## 10. 다른 앱에 적용할 때 체크리스트

### Dockerfile 작성 시

- [ ] 멀티 스테이지 빌드로 이미지 크기 최소화
- [ ] `package*.json` 먼저 복사 → 의존성 설치 → 소스 복사 순서 유지 (캐시 활용)
- [ ] `requirements.txt` 먼저 복사 → pip 설치 → 소스 복사
- [ ] `python:*-slim` 사용 시 C 라이브러리 의존 패키지 목록 확인
- [ ] `WORKDIR`을 실행 위치로 정확히 설정
- [ ] `ENV PYTHONUNBUFFERED=1` — 로그 즉시 출력
- [ ] `EXPOSE 8080` — Cloud Run 기본 포트

### .dockerignore

- [ ] `.env` 반드시 제외
- [ ] `node_modules/` 제외 (경로 정확히)
- [ ] `__pycache__/`, `*.pyc` 제외
- [ ] 대용량 데이터 디렉터리 경로 정확히 명시 (상대 경로 주의)
- [ ] `frontend/dist` 제외 (Stage 1에서 빌드)

### 백엔드 코드

- [ ] CORS `allow_origins` 배포 환경에 맞게 조정
- [ ] 정적 파일 서빙 코드 추가 (단일 컨테이너 방식)
- [ ] SPA fallback 라우트가 API 라우트 **이후**에 위치하는지 확인
- [ ] `if _DIST.is_dir():` 조건으로 로컬 개발 환경과 호환

### GCP 설정

- [ ] `.env` 값을 Secret Manager로 이전
- [ ] Cloud Run 서비스 계정에 시크릿 접근 권한 부여
- [ ] 메모리 설정 확인 (`--memory` — 기본 256Mi는 부족할 수 있음)
- [ ] 타임아웃 설정 (`--timeout` — AI 호출 등 고려)
- [ ] 사내 전용이면 `--no-allow-unauthenticated`
- [ ] 로컬 파일 의존성 있으면 Cloud SQL / GCS 마이그레이션 계획

### 배포 후 검증

- [ ] `GET /health` → `{"status": "ok"}` 확인
- [ ] 프론트엔드 화면 로드 확인
- [ ] SPA 경로에서 새로고침 시 404 없는지 확인
- [ ] API 엔드포인트 동작 확인
- [ ] Cloud Run 로그에서 에러 없는지 확인
  ```bash
  gcloud run services logs read arch-law-diagnose --region asia-northeast3 --limit 50
  ```
