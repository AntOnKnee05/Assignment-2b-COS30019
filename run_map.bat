@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" research_map\serve_map.py
) else (
    python research_map\serve_map.py
)
if errorlevel 1 (
    echo Map launcher failed. Install Python 3.10 or later, or use the project Python environment.
    pause
)
