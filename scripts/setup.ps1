param([switch]$DownloadModel)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) { throw 'Install Python 3.10 or newer, then run setup again.' }
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
        & $pythonCommand.Source -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python virtual environment.' }
    }
    $pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
    $requirements = if (Test-Path -LiteralPath 'requirements-lock.txt') { 'requirements-lock.txt' } else { 'requirements-dev.txt' }
    & $pythonPath -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }

    if (-not (Get-Command node -ErrorAction SilentlyContinue) -and -not (Test-Path -LiteralPath '.tools/node-path.txt')) {
        $nodeVersion = 'v22.23.3'
        $toolDirectory = Join-Path $projectRoot '.tools'
        New-Item -ItemType Directory -Path $toolDirectory -Force | Out-Null
        $archiveName = "node-$nodeVersion-win-x64.zip"
        $archivePath = Join-Path $toolDirectory $archiveName
        $releaseUrl = "https://nodejs.org/dist/$nodeVersion"
        Invoke-WebRequest -Uri "$releaseUrl/$archiveName" -OutFile $archivePath -UseBasicParsing
        $checksumText = (Invoke-WebRequest -Uri "$releaseUrl/SHASUMS256.txt" -UseBasicParsing).Content
        $checksumLine = $checksumText -split "`n" | Where-Object { $_.Trim().EndsWith($archiveName) } | Select-Object -First 1
        if (-not $checksumLine) { throw 'Node.js download checksum was unavailable.' }
        $expectedHash = ($checksumLine -split '\s+')[0]
        $actualHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash
        if ($actualHash -ne $expectedHash) { throw 'Node.js download checksum does not match. Setup stopped.' }
        Expand-Archive -LiteralPath $archivePath -DestinationPath $toolDirectory -Force
        (Join-Path $toolDirectory "node-$nodeVersion-win-x64") | Set-Content -LiteralPath '.tools/node-path.txt'
    }
    & (Join-Path $PSScriptRoot 'frontend.ps1') install
    & (Join-Path $PSScriptRoot 'frontend.ps1') build
    if ($DownloadModel) {
        & $pythonPath scripts/download_model.py
        if ($LASTEXITCODE -ne 0) { throw 'Model download failed. The app can still run in clearly labeled keyword fallback mode.' }
    }
    & $pythonPath scripts/demo.py seed
    Write-Host 'Setup complete. Run: powershell -ExecutionPolicy Bypass -File scripts/run.ps1'
} finally { Pop-Location }
