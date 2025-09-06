@echo off
echo 🎯 ToneBridge Voice Analysis Demo - 실행 (Windows)
echo ===============================================

cd /d "%~dp0"

if not exist venv (
    echo ❌ 가상환경이 없습니다. 먼저 설치를 실행하세요:
    echo    install.bat
    pause
    exit /b 1
)

echo 🔄 가상환경 활성화 중...
call venv\Scripts\activate.bat

set MODE=%1
if "%MODE%"=="" set MODE=both

if "%MODE%"=="backend" (
    echo 🚀 백엔드만 실행 중 (포트 8000)...
    uvicorn backend_server:app --host 0.0.0.0 --port 8000 --reload
) else if "%MODE%"=="frontend" (
    echo 🚀 프론트엔드만 실행 중 (포트 3000)...
    cd react-app && npm start
) else (
    echo 🚀 백엔드 + 프론트엔드 동시 실행 중...
    npm start
)