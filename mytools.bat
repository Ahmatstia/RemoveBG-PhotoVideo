@echo off
title MyTools Hybrid Terminal CLI
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment Python (.venv) tidak ditemukan!
    echo Silakan jalankan setup.ps1 terlebih dahulu.
    echo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" cli.py %*

if errorlevel 1 (
    echo.
    echo [!] Terjadi kesalahan pada program.
    pause
)
