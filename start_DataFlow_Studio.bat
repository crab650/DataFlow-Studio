@echo off
chcp 65001 >nul
title DataFlow Studio - SQL + Python Analytics Workbench
cd /d "%~dp0"
echo ============================================================
echo   🚀 正在啟動 DataFlow Studio (SQL + Python 數據分析工作台)...
echo   👉 啟動後將自動開啟瀏覽器: http://127.0.0.1:5000
echo ============================================================
start "" "http://127.0.0.1:5000"
python app.py
pause
