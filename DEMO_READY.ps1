$ErrorActionPreference = "Stop"

$RootPath = $PSScriptRoot
if ([string]::IsNullOrEmpty($RootPath)) {
    $RootPath = (Get-Location).Path
}

$BackendPath = Join-Path $RootPath "job_work_planner\task-4-backend-skeleton"
$FrontendPath = Join-Path $RootPath "job_work_planner\task-5-react-frontend"
$DemoUrl = "http://localhost:5173"

Write-Host "=================================" -ForegroundColor Cyan
Write-Host " PROJECT ROODHA DEMO READY" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan

Write-Host "`nSeeding Roodha demo story..." -ForegroundColor Yellow
Push-Location $BackendPath
python scripts/seed_test_data.py
Pop-Location

Write-Host "Starting backend in a hidden window..." -ForegroundColor Green
Start-Process powershell -WindowStyle Hidden -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$BackendPath'; python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001"
)

Write-Host "Starting frontend..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$FrontendPath'; npm run dev -- --host 127.0.0.1 --port 5173"
)

Write-Host "Opening browser at $DemoUrl ..." -ForegroundColor Green
Start-Sleep -Seconds 6

$edge = Get-Command "msedge.exe" -ErrorAction SilentlyContinue
$chrome = Get-Command "chrome.exe" -ErrorAction SilentlyContinue

if ($edge) {
    Start-Process $edge.Source $DemoUrl
} elseif ($chrome) {
    Start-Process $chrome.Source $DemoUrl
} else {
    Start-Process $DemoUrl
}

Write-Host "`nDemo launch complete. Use the DEV BYPASS button on the login screen if needed." -ForegroundColor Cyan
