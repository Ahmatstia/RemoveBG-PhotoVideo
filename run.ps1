$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) { throw 'Jalankan .\setup.ps1 terlebih dahulu.' }
if (-not (Test-Path 'web/out/index.html')) { throw 'Frontend web belum dibuat. Jalankan .\setup.ps1 terlebih dahulu.' }
$env:HF_HUB_DISABLE_TELEMETRY = '1'
try {
    $appPage = Invoke-WebRequest 'http://127.0.0.1:7860/api/health' -UseBasicParsing -TimeoutSec 2
    if (($appPage.Content | ConvertFrom-Json).ok) {
        Start-Process 'http://127.0.0.1:7860'
        exit 0
    }
} catch { }
& .venv/Scripts/python.exe -m removebg.api
