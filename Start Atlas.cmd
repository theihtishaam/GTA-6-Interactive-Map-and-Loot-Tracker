@echo off
setlocal
cd /d "%~dp0"
py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>nul
if errorlevel 1 goto usepython
py -3 launch_atlas.py
if errorlevel 1 pause
exit /b
:usepython
python launch_atlas.py
if errorlevel 1 pause

