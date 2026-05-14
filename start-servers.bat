@echo off
chcp 65001 > nul
pushd %~dp0

start "backend" cmd /k "cd backend && .venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak > nul
start "frontend" cmd /k "cd frontend && npm run dev"

popd
