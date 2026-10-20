param([ValidateSet('install', 'build', 'dev', 'preview')][string]$Task = 'dev')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    $nodeCommand = Get-Command node -ErrorAction SilentlyContinue
    if ($nodeCommand) {
        $nodePath = $nodeCommand.Source
    } elseif (Test-Path -LiteralPath '.tools/node-path.txt') {
        $localNodeFolder = (Get-Content -LiteralPath '.tools/node-path.txt' -Raw).Trim()
        if (-not (Test-Path -LiteralPath $localNodeFolder)) {
            $localNodeFolder = Join-Path $projectRoot ('.tools/' + (Split-Path -Leaf $localNodeFolder))
        }
        $nodePath = Join-Path $localNodeFolder 'node.exe'
    } else {
        throw 'Node.js 22.12 or newer is required. Install Node.js or run scripts/setup.ps1.'
    }
    $nodeDirectory = Split-Path -Parent $nodePath
    $env:PATH = $nodeDirectory + [IO.Path]::PathSeparator + $env:PATH
    $npmCli = Join-Path $nodeDirectory 'node_modules/npm/bin/npm-cli.js'
    $env:npm_config_cache = Join-Path $projectRoot '.cache/npm'
    Set-Location (Join-Path $projectRoot 'frontend')
    if ($Task -eq 'install') { & $nodePath $npmCli ci }
    else { & $nodePath $npmCli run $Task }
    if ($LASTEXITCODE -ne 0) { throw "Frontend $Task failed with exit code $LASTEXITCODE." }
} finally { Pop-Location }
