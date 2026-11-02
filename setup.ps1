$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv belum tersedia. Instal dari https://docs.astral.sh/uv/getting-started/installation/ lalu ulangi.'
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw 'Node.js 22+ diperlukan yt-dlp untuk mengambil video YouTube. Instal dari https://nodejs.org/ lalu ulangi.'
}
$nodeVersion = (& node --version).Trim()
if ($nodeVersion -notmatch '^v(\d+)\.' -or [int]$Matches[1] -lt 22) {
    throw "yt-dlp memerlukan Node.js 22+. Versi saat ini: $nodeVersion"
}
uv venv --python 3.11 .venv --allow-existing
if ($LASTEXITCODE) { throw 'Pembuatan virtual environment gagal.' }
uv pip install --python .venv/Scripts/python.exe 'torch==2.11.0+cu128' 'torchvision==0.26.0+cu128' --index-url https://download.pytorch.org/whl/cu128
if ($LASTEXITCODE) { throw 'Instalasi PyTorch CUDA gagal.' }
uv pip install --python .venv/Scripts/python.exe -r requirements-lock.txt --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match
if ($LASTEXITCODE) { throw 'Instalasi dependensi terkunci gagal.' }
uv pip install --python .venv/Scripts/python.exe --no-deps -e .
if ($LASTEXITCODE) { throw 'Instalasi aplikasi gagal.' }
& .venv/Scripts/python.exe -c "import torch; assert torch.cuda.is_available(), 'CUDA tidak tersedia'; print(torch.cuda.get_device_name(0))"
if ($LASTEXITCODE) { throw 'Pemeriksaan GPU gagal.' }
Push-Location web
try {
    npm ci
    if ($LASTEXITCODE) { throw 'Instalasi dependensi web gagal.' }
    npm run build
    if ($LASTEXITCODE) { throw 'Build web gagal.' }
} finally { Pop-Location }
Write-Host 'Siap. Klik dua kali run.bat untuk membuka web app.'
