$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendPath = Join-Path $projectRoot 'job_work_planner\task-4-backend-skeleton'
$frontendPath = Join-Path $projectRoot 'job_work_planner\task-5-react-frontend'
$backendPython = Join-Path $backendPath '.venv\Scripts\python.exe'
$backendEnvFile = Join-Path $backendPath '.env'
$backendUrl = 'http://127.0.0.1:8000/health'
$frontendUrl = 'http://127.0.0.1:5173'

$env:ENV = 'development'

function Test-UrlReady {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSec = 2
    )

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    } catch {
        return $false
    }
}

function Wait-UntilReady {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$Attempts = 60
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        if (Test-UrlReady -Url $Url) {
            Write-Host "$Label is reachable at $Url" -ForegroundColor Green
            return
        }

        Start-Sleep -Seconds 1
    }

    throw "$Label did not become reachable at $Url"
}

if (-not (Test-Path $backendPython)) {
    throw "Backend Python not found at $backendPython"
}

if (-not (Test-Path (Join-Path $frontendPath 'package.json'))) {
    throw "Frontend package.json not found at $frontendPath"
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
if (Test-Path 'node_modules\.vite') {
  Remove-Item -LiteralPath 'node_modules\.vite' -Recurse -Force -ErrorAction SilentlyContinue
}
npm run dev
"@

Write-Host 'Launching Project Roodha local certification stack...' -ForegroundColor Cyan

Start-Process powershell -ArgumentList '-NoExit', '-Command', $backendCommand | Out-Null
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList '-NoExit', '-Command', $frontendCommand | Out-Null

Wait-UntilReady -Url $backendUrl -Label 'Backend'
Wait-UntilReady -Url $frontendUrl -Label 'Frontend'

Write-Host 'PROD-READY LOCAL V1.0 CERTIFIED' -ForegroundColor Green
