# 관리자 권한으로 실행 필요
$taskName = "arch-law-diagnose"
$scriptPath = "C:\Users\20260102\법검토\arch-law-diagnose\start-servers.bat"

# 기존 작업 삭제 (있으면)
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$scriptPath`"" -WorkingDirectory "C:\Users\20260102\법검토\arch-law-diagnose"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 0) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "arch-law-diagnose 백엔드/프론트엔드 자동 시작"

Write-Host ""
Write-Host "등록 완료: 로그인 시 자동으로 서버가 시작됩니다." -ForegroundColor Green
Write-Host "작업 이름: $taskName" -ForegroundColor Cyan
