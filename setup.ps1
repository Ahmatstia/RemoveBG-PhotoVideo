$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv belum tersedia. Instal dari https://docs.astral.sh/uv/getting-started/installation/ lalu ulangi.'
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
Write-Host 'Siap. Jalankan .\run.ps1 atau klik dua kali run.bat.'
