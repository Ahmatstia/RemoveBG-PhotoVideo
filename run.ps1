param([ValidateSet('Development', 'Use')][string]$Mode = 'Use')

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$python = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
$webPath = Join-Path $PSScriptRoot 'apps/web'

if (-not (Test-Path $python)) { throw 'Jalankan .\setup.ps1 terlebih dahulu.' }

function Test-LocalServer([string]$Url) {
    try {
        $null = Invoke-WebRequest $Url -UseBasicParsing -TimeoutSec 2
        return $true
    } catch { return $false }
}

function Test-MyToolsDevServer {
    try {
        $page = Invoke-WebRequest 'http://127.0.0.1:3000' -UseBasicParsing -TimeoutSec 2
        return $page.Content.Contains('MyTools')
    } catch { return $false }
}

if ($Mode -eq 'Development') {
    $env:MYTOOLS_OPEN_BROWSER = '0'
    if (-not (Test-Path (Join-Path $webPath 'node_modules/next'))) {
        throw 'Dependensi frontend belum tersedia. Jalankan npm ci dari apps/web.'
    }

    if (Test-LocalServer 'http://127.0.0.1:7860/api/health') {
        Write-Host 'Backend lokal sudah berjalan; memakai server yang ada. Perubahan kode Python butuh restart backend.'
    } else {
        Write-Host 'Menjalankan backend lokal di jendela baru…'
        Start-Process -FilePath $python -ArgumentList @('-m', 'removebg.api') -WorkingDirectory $PSScriptRoot -WindowStyle Normal
        $ready = $false
        for ($attempt = 0; $attempt -lt 40; $attempt++) {
            if (Test-LocalServer 'http://127.0.0.1:7860/api/health') { $ready = $true; break }
            Start-Sleep -Milliseconds 750
        }
        if (-not $ready) { throw 'Backend tidak merespons di port 7860. Periksa jendela backend.' }
    }

    if (Test-MyToolsDevServer) {
        Write-Host 'Next.js dev server sudah berjalan; membuka http://127.0.0.1:3000.'
    } else {
        if ((Test-LocalServer 'http://127.0.0.1:3000') -or (Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue)) {
            throw 'Port 3000 sedang dipakai aplikasi lain. Tutup aplikasi tersebut lalu pilih mode pengembangan lagi.'
        }
        Write-Host 'Menjalankan Next.js dev server di jendela baru…'
        Start-Process -FilePath $env:ComSpec -ArgumentList @('/k', 'npm run dev -- --port 3000') -WorkingDirectory $webPath -WindowStyle Normal
        $ready = $false
        for ($attempt = 0; $attempt -lt 40; $attempt++) {
            if (Test-MyToolsDevServer) { $ready = $true; break }
            Start-Sleep -Milliseconds 750
        }
        if (-not $ready) { throw 'Next.js dev server tidak merespons di port 3000. Periksa jendela frontend.' }
    }

    Start-Process 'http://127.0.0.1:3000'
    Write-Host 'Mode pengembangan aktif: frontend auto-refresh di port 3000; API di port 7860.'
    exit 0
}

if (-not (Test-Path (Join-Path $webPath 'out/index.html'))) {
    throw 'Frontend build belum dibuat. Jalankan npm run build dari apps/web.'
}

if (Test-LocalServer 'http://127.0.0.1:7860/api/health') {
    Start-Process 'http://127.0.0.1:7860'
    exit 0
}

& $python -m removebg.api
