@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
python -m venv .venv
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m traffic.prepare "data/raw/Scats Data October 2006.xls"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m traffic.plot_day --site 0970 --location-id 1 --date 2006-10-01
if errorlevel 1 goto failed
echo.
echo Done. Prepared data: data\processed\scats_15min.csv
echo Example chart: outputs\site_0970_day.png
pause
exit /b 0
:failed
echo.
echo Setup or processing failed. Read the error above.
echo Python 3.10 or newer must be installed and available as python.
pause
exit /b 1
