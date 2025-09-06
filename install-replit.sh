#!/bin/bash

echo "🎯 ToneBridge Voice Analysis Demo - Replit 환경 설치"
echo "=================================================="

# 스크립트 실행 위치 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Replit 환경 감지
if [ -n "$REPLIT_DB_URL" ] || [ -n "$REPL_ID" ]; then
    echo "🔍 Replit 환경 감지됨"
    REPLIT_ENV=true
else
    echo "🖥️  로컬 환경에서 실행 중"
    REPLIT_ENV=false
fi

# Python 의존성 설치
echo "📦 Python 의존성 설치 중..."
if [ "$REPLIT_ENV" = true ]; then
    # Replit 환경에서는 전역으로 설치
    echo "🔧 Replit 환경: 전역 Python 패키지 설치"
    pip install --user -r requirements.txt
else
    # 로컬 환경에서는 가상환경 사용
    echo "🏠 로컬 환경: 가상환경 생성 및 설치"
    
    # Python 명령어 확인
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        echo "❌ Python이 설치되어 있지 않습니다."
        echo "   Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
        echo "   macOS: brew install python"
        echo "   Windows: https://python.org에서 다운로드"
        exit 1
    fi
    
    # 가상환경 생성 (이미 있으면 재사용)
    if [ ! -d "venv" ]; then
        echo "📦 새 가상환경 생성 중..."
        $PYTHON_CMD -m venv venv
    else
        echo "📦 기존 가상환경 사용 중..."
    fi
    
    # 가상환경 활성화
    echo "🔄 가상환경 활성화 중..."
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        source venv/Scripts/activate
    else
        source venv/bin/activate
    fi
    
    pip install --upgrade pip
    pip install -r requirements.txt
fi

# Node.js 의존성 설치
echo "📦 Node.js 의존성 설치 중..."
if command -v npm &> /dev/null; then
    npm install concurrently
    if [ -d "react-app" ]; then
        cd react-app && npm install && cd ..
    fi
    echo "✅ Node.js 의존성 설치 완료!"
else
    echo "❌ Node.js/npm이 설치되어 있지 않습니다."
    echo "   Ubuntu/Debian: sudo apt install nodejs npm"
    echo "   macOS: brew install node"
    echo "   Windows: https://nodejs.org에서 다운로드"
    exit 1
fi

echo ""
echo "✅ $( [ "$REPLIT_ENV" = true ] && echo "Replit 환경" || echo "로컬 환경" ) 설치 완료!"
echo ""
echo "🚀 실행 방법:"
if [ "$REPLIT_ENV" = false ]; then
    echo "   1. 가상환경 활성화 (로컬 환경만):"
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        echo "      source venv/Scripts/activate"
    else
        echo "      source venv/bin/activate"
    fi
    echo ""
fi
echo "   2. 애플리케이션 실행:"
echo "      ./run.sh backend         # 백엔드만 (포트 5000)"
echo "      ./run.sh frontend        # 프론트엔드만 (포트 3000)"
echo "      ./run.sh                 # 동시 실행"
echo ""
echo "🧹 정리 방법:"
echo "      ./clean.sh               # 설치된 파일들 모두 삭제"
echo ""