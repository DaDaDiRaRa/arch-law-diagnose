# ── Stage 1: 프론트엔드 빌드 ──────────────────────────────────────────────
FROM node:20-slim AS frontend-builder

# 자매 앱 arch-law-graph 링크아웃 주소 (빌드타임 주입). 미지정 시 기본 localhost.
# 배포 시: docker build --build-arg VITE_GRAPH_URL=https://<graph-url>
ARG VITE_GRAPH_URL
ENV VITE_GRAPH_URL=$VITE_GRAPH_URL

WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


# ── Stage 2: 백엔드 런타임 ────────────────────────────────────────────────
FROM python:3.12-slim

# shapely / pyproj 시스템 의존 라이브러리
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgeos-dev \
        libproj-dev \
        proj-data \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# 의존성 먼저 설치 (레이어 캐시 활용)
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 백엔드 소스
COPY backend/ ./

# 프론트엔드 빌드 결과물
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
