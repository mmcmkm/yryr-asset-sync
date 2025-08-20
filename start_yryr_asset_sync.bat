@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul

rem スクリプトのあるディレクトリへ移動
cd /d "%~dp0"

rem Python 実行ファイル検出（仮想環境優先）
set "PYTHON="
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"
if not defined PYTHON if exist "venv\Scripts\python.exe" set "PYTHON=venv\Scripts\python.exe"
if not defined PYTHON where py >nul 2>&1 && set "PYTHON=py"
if not defined PYTHON where python >nul 2>&1 && set "PYTHON=python"

if not defined PYTHON (
    echo Pythonランタイムが見つかりませんでした。Python 3.9以上をインストールしてください。
    pause
    exit /b 1
)

"%PYTHON%" "%~dp0main.py"
set "EXITCODE=%ERRORLEVEL%"

if %EXITCODE% neq 0 (
    echo アプリケーションがエラーコード %EXITCODE% で終了しました。
    pause
)

exit /b %EXITCODE%


