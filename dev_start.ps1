$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendPath = Join-Path $projectRoot 'job_work_planner\task-4-backend-skeleton'
$frontendPath = Join-Path $projectRoot 'job_work_planner\task-5-react-frontend'
$backendPython = Join-Path $backendPath '.venv\Scripts\python.exe'
$backendEnvFile = Join-Path $backendPath '.env'

if (-not (Test-Path $backendPython)) {
    Write-Error "Backend Python not found at $backendPython"
    exit 1
}

if (-not (Test-Path (Join-Path $frontendPath 'package.json'))) {
    Write-Error "Frontend package.json not found at $frontendPath"
    exit 1
}

if (-not (Test-Path $backendEnvFile)) {
    Write-Host "Backend .env not found at $backendEnvFile" -ForegroundColor Yellow
    Write-Host "Create it from .env.example and set DATABASE_URL before launching the backend." -ForegroundColor Yellow
}

$backendCommand = @"
Set-Location '$backendPath'
`$env:ENV = 'development'
`$env:PYTHONPATH = '$backendPath'
if (Test-Path '$backendEnvFile') {
  Get-Content '$backendEnvFile' | ForEach-Object {
    if (`$_ -match '^\s*#' -or `$_ -match '^\s*$') { return }
    `$parts = `$_ -split '=', 2
    if (`$parts.Length -eq 2) {
      [System.Environment]::SetEnvironmentVariable(`$parts[0].Trim(), `$parts[1].Trim(), 'Process')
    }
  }
}
& '$backendPython' -m uvicorn app.main:app --reload
"@

$frontendCommand = @"
Set-Location '$frontendPath'
npm run dev
"@

Start-Process powershell -ArgumentList '-NoExit', '-Command', $backendCommand
Start-Process powershell -ArgumentList '-NoExit', '-Command', $frontendCommand

Write-Host 'Project Roodha V1.0 is launching... Open http://localhost:5173 to begin.'
