@echo off
echo 🎯 ToneBridge Voice Analysis Demo - 완전 독립 설치 (Windows)
echo ===========================================================

cd /d "%~dp0"

echo 🐍 Python 가상환경 생성 중...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python이 설치되어 있지 않습니다.
    echo    https://python.org에서 Python을 다운로드하세요.
    pause
    exit /b 1
)

if not exist venv (
    echo 📦 새 가상환경 생성 중...
    python -m venv venv
) else (
    echo 📦 기존 가상환경 사용 중...
)

echo 🔄 가상환경 활성화 중...
call venv\Scripts\activate.bat

echo 📦 Python 의존성 설치 중 (가상환경)...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo 📦 Node.js 의존성 설치 중...
npm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js/npm이 설치되어 있지 않습니다.
    echo    https://nodejs.org에서 Node.js를 다운로드하세요.
    pause
    exit /b 1
)

npm install concurrently
cd react-app && npm install && cd ..

echo.
echo ✅ 완전 독립 설치 완료!
echo.
echo 🚀 실행 방법:
echo    1. 가상환경 활성화:
echo       venv\Scripts\activate
echo.
echo    2. 애플리케이션 실행:
echo       npm run start-backend    # 백엔드만 (포트 8000)
echo       npm run start-frontend   # 프론트엔드만 (포트 3000)
echo       npm start               # 동시 실행
echo.
echo 📝 주의: 새 명령 프롬프트에서는 항상 가상환경을 먼저 활성화하세요!
echo.
pause