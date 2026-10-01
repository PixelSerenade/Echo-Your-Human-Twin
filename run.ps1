# Start or reuse both HumanTwin services as one application.
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendUrl = 'http://127.0.0.1:8003/health'
$FrontendUrl = 'http://127.0.0.1:5173/'

function Test-HttpService([string]$Url) {
    try {
        $null = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 $Url
        return $true
    } catch {
        return $false
    }
}

if (-not (Test-HttpService $BackendUrl)) {
    $PythonPath = Join-Path $ProjectRoot 'backend\.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $PythonPath)) {
        throw "Backend environment not found at $PythonPath. Install backend dependencies first."
    }
    Start-Process -FilePath $PythonPath -ArgumentList @('-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8003', '--reload') -WorkingDirectory $ProjectRoot -WindowStyle Hidden
}

if (-not (Test-HttpService $FrontendUrl)) {
    $FrontendRoot = Join-Path $ProjectRoot 'frontend'
    if (-not (Test-Path -LiteralPath (Join-Path $FrontendRoot 'node_modules'))) {
        throw 'Frontend dependencies are missing. Run npm install in the frontend directory first.'
    }
    Start-Process -FilePath 'npm.cmd' -ArgumentList @('run', 'dev', '--', '--host', '127.0.0.1') -WorkingDirectory $FrontendRoot -WindowStyle Hidden
}

$Ready = $false
for ($Attempt = 0; $Attempt -lt 30; $Attempt++) {
    if ((Test-HttpService $BackendUrl) -and (Test-HttpService $FrontendUrl)) {
        $Ready = $true
        break
    }
    Start-Sleep -Seconds 1
}
if (-not $Ready) {
    throw 'The frontend and backend did not both become ready. Check the local services and PostgreSQL.'
}

Write-Host 'HumanTwin is running as one app:' -ForegroundColor Green
Write-Host '  Frontend: http://127.0.0.1:5173/'
Write-Host '  Backend:  http://127.0.0.1:8003/health'
Write-Host '  API docs: http://127.0.0.1:8003/docs'
