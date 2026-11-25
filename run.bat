@echo off
chcp 65001 >nul
title MyTools
cd /d "%~dp0"
echo.
echo ================================
echo   MyTools - Pilih Mode
echo ================================
echo   D. Pengembangan (Next.js dev)
echo   P. Pemakaian (build stabil)
echo.
choice /C DP /N /M "Pilih mode [D/P]: "
if errorlevel 2 goto use
if errorlevel 1 goto development
goto end

:development
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" -Mode Development
goto finish

:use
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" -Mode Use
goto finish

:finish
if errorlevel 1 pause

:end
