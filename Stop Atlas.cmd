@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\WindowsLauncher.ps1" -Action Stop %*
set "atlas_result=%errorlevel%"
if not "%atlas_result%"=="0" pause
exit /b %atlas_result%
