@echo off
:: ============================================================
::  auto_update_report.bat
::  每天由 Windows 工作排程器自動執行
::  流程：執行 Python → git add/commit/push
:: ============================================================

:: ★ 請修改以下路徑
set REPO_DIR=C:\GitHub\investor_report
set PYTHON=c:\Users\USER\AppData\Local\Programs\Python\Python312\python.exe
set SCRIPT=%REPO_DIR%\LY_report.py
set LOG=%REPO_DIR%\update_log.txt

echo. >> %LOG%
echo ============================== >> %LOG%
echo %date% %time% - 開始更新 >> %LOG%

:: 切換到 repo 目錄
cd /d %REPO_DIR%

:: 執行 Python 產生 report.html
echo [1/3] 執行 Python 產生報告... >> %LOG%
%PYTHON% %SCRIPT% >> %LOG% 2>&1

if %errorlevel% neq 0 (
    echo [ERROR] Python 執行失敗，中止。 >> %LOG%
    exit /b 1
)

:: git add + commit + push
echo [2/3] git add ... >> %LOG%
git add report.html >> %LOG% 2>&1

echo [3/3] git commit + push ... >> %LOG%
git commit -m "auto update report %date%" >> %LOG% 2>&1
git push origin main >> %LOG% 2>&1

if %errorlevel% neq 0 (
    echo [ERROR] git push 失敗，請檢查網路或 SSH 設定。 >> %LOG%
    exit /b 1
)

echo 完成！報告已更新。 >> %LOG%
exit /b 0