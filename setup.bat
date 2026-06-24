@echo off
chcp 65001 >nul
title Claude Switcher - Setup
cd /d "%~dp0"

echo ========================================
echo   Claude Switcher Setup
echo ========================================
echo.

:: ----------------------------------------
:: Python check
:: ----------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python not found. Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

:: ----------------------------------------
:: Mechanism 1: Claude Code CLI pre-flight
:: ----------------------------------------
echo [*] Checking for Claude Code CLI...
set "CLAUDE_EXE="

:: 1a. PATH lookup
for /f "delims=" %%P in ('where claude 2^>nul') do (
    if not defined CLAUDE_EXE set "CLAUDE_EXE=%%P"
)

:: 1b. Desktop app glob: Packages\Claude_*\LocalCache\Roaming\Claude\claude-code\*\claude.exe
if not defined CLAUDE_EXE (
    for /d %%D in ("%LOCALAPPDATA%\Packages\Claude_*") do (
        for /d %%V in ("%%D\LocalCache\Roaming\Claude\claude-code\*") do (
            if exist "%%V\claude.exe" (
                if not defined CLAUDE_EXE set "CLAUDE_EXE=%%V\claude.exe"
            )
        )
    )
)

:: 1c. npm global install
if not defined CLAUDE_EXE (
    if exist "%APPDATA%\npm\claude.cmd" set "CLAUDE_EXE=%APPDATA%\npm\claude.cmd"
)

if not defined CLAUDE_EXE (
    echo [!] Claude Code CLI not found.
    echo     Please install Claude Code first: https://claude.ai/download
    echo.
    pause
    exit /b 1
)
echo [OK] Claude Code CLI found: %CLAUDE_EXE%
echo.

:: ----------------------------------------
:: Mechanism 2: Antigravity detection
:: ----------------------------------------
set "AGY_FOUND="
set "AGY_LIST="

if exist "%LOCALAPPDATA%\Programs\antigravity\" (
    set "AGY_FOUND=1"
    set "AGY_LIST=Antigravity 2.0"
)

where agy >nul 2>&1
if not errorlevel 1 (
    set "AGY_FOUND=1"
    if defined AGY_LIST (set "AGY_LIST=%AGY_LIST%, agy CLI") else (set "AGY_LIST=agy CLI")
)

if exist "%LOCALAPPDATA%\Programs\antigravity-ide\" (
    set "AGY_FOUND=1"
    if defined AGY_LIST (set "AGY_LIST=%AGY_LIST%, Antigravity IDE") else (set "AGY_LIST=Antigravity IDE")
)

if not defined AGY_FOUND goto :skip_agy

echo [*] Antigravity detected: %AGY_LIST%

:: Extract directory of claude exe
for %%F in ("%CLAUDE_EXE%") do set "CLAUDE_DIR=%%~dpF"
:: Remove trailing backslash
if "%CLAUDE_DIR:~-1%"=="\" set "CLAUDE_DIR=%CLAUDE_DIR:~0,-1%"

:: Check if already in user PATH (registry)
reg query HKCU\Environment /v Path 2>nul | find /i "%CLAUDE_DIR%" >nul
if not errorlevel 1 (
    echo [*] Claude CLI path already in user PATH. No changes needed.
    goto :skip_agy
)

set "USER_PATH="
for /f "tokens=2,*" %%A in ('reg query HKCU\Environment /v Path 2^>nul') do (
    set "USER_PATH=%%B"
)

if defined USER_PATH (
    setx PATH "%USER_PATH%;%CLAUDE_DIR%" >nul
) else (
    setx PATH "%CLAUDE_DIR%" >nul
)
echo [*] Claude CLI path added to user PATH: %CLAUDE_DIR%
echo     Restart your terminal / Antigravity IDE for changes to take effect.
echo.

:skip_agy
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
