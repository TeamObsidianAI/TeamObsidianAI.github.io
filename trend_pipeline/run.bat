@echo off
title Product Trend Pipeline
color 0A
echo.
echo  ============================================
echo   Team Obsidian AI - Product Trend Pipeline
echo  ============================================
echo.

:: Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python is not installed or not in PATH.
    echo  Download it at https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

:: Check .env exists
if not exist ".env" (
    echo  ERROR: .env file not found.
    echo  Copy .env.example to .env and add your ANTHROPIC_API_KEY.
    echo.
    pause
    exit /b 1
)

:: Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo  Setting up virtual environment for the first time...
    python -m venv .venv
)

:: Activate virtual environment
call .venv\Scripts\activate.bat

:: Install/update dependencies quietly
echo  Checking dependencies...
pip install -r requirements.txt -q

:: Run the pipeline
echo.
echo  Running pipeline... (this takes 3-5 minutes)
echo.
python main.py

if errorlevel 1 (
    echo.
    echo  Pipeline encountered an error. Check the output above.
    pause
    exit /b 1
)

:: Open the dashboard in the default browser
echo.
echo  Opening dashboard...
start "" "..\trend-report.html"

echo.
echo  Done! Your trend report is ready.
pause
