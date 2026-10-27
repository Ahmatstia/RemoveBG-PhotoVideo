$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) { throw 'Jalankan .\setup.ps1 terlebih dahulu.' }
$env:GRADIO_ANALYTICS_ENABLED = 'False'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
try {
    $appPage = Invoke-WebRequest 'http://127.0.0.1:7860/config' -UseBasicParsing -TimeoutSec 2
    if ($appPage.Content -like '*RemoveBG Local*') {
        Start-Process 'http://127.0.0.1:7860'
        exit 0
    }
} catch { }
& .venv/Scripts/python.exe -m removebg.ui.app
