#!/bin/bash

echo "🎯 ToneBridge Voice Analysis Demo - 실행"
echo "======================================="

# 스크립트 실행 위치 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 환경별 설치 확인
if [ -n "$REPLIT_DB_URL" ] || [ -n "$REPL_ID" ]; then
    # Replit 환경 - Python 패키지 설치 확인
    if ! python -c "import fastapi" 2>/dev/null; then
        echo "❌ Python 의존성이 설치되지 않았습니다. 먼저 설치를 실행하세요:"
        echo "   npm run install"
        exit 1
    fi
else
    # 로컬 환경 - 가상환경 확인
    if [ ! -d "venv" ]; then
        echo "❌ 가상환경이 없습니다. 먼저 설치를 실행하세요:"
        echo "   npm run install-local"
        exit 1
    fi
fi

# 환경별 설정
if [ -n "$REPLIT_DB_URL" ] || [ -n "$REPL_ID" ]; then
    # Replit 환경
    echo "🔍 Replit 환경에서 실행 중..."
    REPLIT_ENV=true
else
    # 로컬 환경 - 가상환경 활성화
    echo "🔄 로컬 환경: 가상환경 활성화 중..."
    REPLIT_ENV=false
    
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        source venv/Scripts/activate
    else
        source venv/bin/activate
    fi
fi

# 실행 모드 확인
MODE=${1:-"both"}

case $MODE in
    "backend")
        echo "🚀 백엔드만 실행 중 (포트 8000)..."
        uvicorn backend_server:app --host 0.0.0.0 --port 8000 --reload
        ;;
    "frontend")
        echo "🚀 프론트엔드만 실행 중 (포트 3000)..."
        cd react-app && npm start
        ;;
    "both"|*)
        echo "🚀 백엔드 + 프론트엔드 동시 실행 중..."
        npm start
        ;;
esac