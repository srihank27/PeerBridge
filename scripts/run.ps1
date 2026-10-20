param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    $pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run scripts/setup.ps1 first to create .venv.' }
    if (-not (Test-Path -LiteralPath 'dist/assets')) { throw 'Build the React frontend first: powershell -ExecutionPolicy Bypass -File scripts/frontend.ps1 build' }
    Write-Host "PeerBridge fictional local demo: http://127.0.0.1:$Port"
    Write-Host 'Press Ctrl+C to stop. No live student registration or staff monitoring.'
    & $pythonPath -m uvicorn backend.peerbridge.main:app --host 127.0.0.1 --port $Port
} finally { Pop-Location }
