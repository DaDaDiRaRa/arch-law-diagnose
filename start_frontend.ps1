# arch-law-diagnose 프론트엔드 실행 스크립트 (PowerShell)
Set-Location "$PSScriptRoot\frontend"

if (-not (Test-Path "node_modules")) {
    Write-Host "[1/2] npm install..."
    npm install
}

Write-Host "[2/2] Vite dev server 시작: http://localhost:5173"
npm run dev
