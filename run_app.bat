@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
python -m venv .venv
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
if exist "data\processed\scats_15min.csv" goto gui
".venv\Scripts\python.exe" -m traffic.prepare "data/raw/Scats Data October 2006.xls"
if errorlevel 1 goto failed
:gui
".venv\Scripts\python.exe" -m traffic.gui
if errorlevel 1 goto failed
exit /b 0
:failed
echo Setup or application failed. Read the error above.
pause
exit /b 1
