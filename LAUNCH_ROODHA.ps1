$ErrorActionPreference = "Stop"

$RootPath = $PSScriptRoot
if ([string]::IsNullOrEmpty($RootPath)) {
    $RootPath = (Get-Location).Path
}

$BackendPath = Join-Path $RootPath "job_work_planner\task-4-backend-skeleton"
$FrontendPath = Join-Path $RootPath "job_work_planner\task-5-react-frontend"

Write-Host "=================================" -ForegroundColor Cyan
Write-Host "🚀 LAUNCHING PROJECT ROODHA" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan

Write-Host "`nStarting Backend in a new window..."
# Start Backend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$BackendPath'; Write-Host '--- Backend Server ---' -ForegroundColor Green; uvicorn app.main:app --reload"

Write-Host "Starting Frontend in a new window..."
# Start Frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$FrontendPath'; Write-Host '--- Frontend Server ---' -ForegroundColor Blue; npm run dev"

Write-Host "`nLaunch sequence initiated! Check the new terminal windows." -ForegroundColor Green
