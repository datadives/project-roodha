$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendPath = Join-Path $projectRoot 'job_work_planner\task-4-backend-skeleton'
$frontendPath = Join-Path $projectRoot 'job_work_planner\task-5-react-frontend'

$backendCommand = @"
Set-Location '$backendPath'
`$env:ENV = 'development'
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload
"@

$frontendCommand = @"
Set-Location '$frontendPath'
npm run dev
"@

Start-Process powershell -ArgumentList '-NoExit', '-Command', $backendCommand
Start-Process powershell -ArgumentList '-NoExit', '-Command', $frontendCommand

Write-Host 'Project Roodha V1.0 is launching... Open http://localhost:5173 to begin.'
