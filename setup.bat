@echo off
chcp 65001 >nul
title Claude Switcher - Setup
cd /d "%~dp0"

echo ========================================
echo   Claude Switcher Setup
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python not found. Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

echo [*] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [!] pip install failed. Check your internet connection and try again.
    pause
    exit /b 1
)

echo.
echo [OK] Setup complete. Run run.bat to start.
echo.
pause
