@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -c "import textual" 2>nul || pip install textual -q
python app.py
