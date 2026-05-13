# arch-law-diagnose 백엔드 실행 스크립트 (PowerShell)
Set-Location "$PSScriptRoot\backend"

# 가상환경 없으면 생성
if (-not (Test-Path ".venv")) {
    Write-Host "[1/3] 가상환경 생성..."
    python -m venv .venv
}

# 활성화
Write-Host "[2/3] 가상환경 활성화..."
& ".venv\Scripts\Activate.ps1"

# 의존성 설치
Write-Host "[3/3] 의존성 설치..."
pip install -r requirements.txt -q

Write-Host ""
Write-Host "✓ 백엔드 시작: http://localhost:8000"
Write-Host "  API 문서: http://localhost:8000/docs"
Write-Host ""

uvicorn main:app --reload --host 0.0.0.0 --port 8000
