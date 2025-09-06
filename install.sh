#!/bin/bash

echo "🎯 ToneBridge Voice Analysis Demo - 완전 독립 설치"
echo "=================================================="

# 스크립트 실행 위치 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Python 가상환경 생성 및 활성화
echo "🐍 Python 가상환경 생성 중..."
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
    # Windows
    source venv/Scripts/activate
else
    # Linux/macOS
    source venv/bin/activate
fi

# Python 의존성 설치 (가상환경 내)
echo "📦 Python 의존성 설치 중 (가상환경)..."
pip install --upgrade pip
pip install -r requirements.txt

# Node.js 의존성 확인 및 설치
echo "📦 Node.js 의존성 설치 중..."
if command -v npm &> /dev/null; then
    npm install concurrently
    cd react-app && npm install && cd ..
    echo "✅ 모든 의존성 설치 완료!"
else
    echo "❌ Node.js/npm이 설치되어 있지 않습니다."
    echo "   Ubuntu/Debian: sudo apt install nodejs npm"
    echo "   macOS: brew install node"
    echo "   Windows: https://nodejs.org에서 다운로드"
    exit 1
fi

echo ""
echo "✅ 완전 독립 설치 완료!"
echo ""
echo "🚀 실행 방법:"
echo "   1. 가상환경 활성화:"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    echo "      source venv/Scripts/activate"
else
    echo "      source venv/bin/activate"
fi
echo ""
echo "   2. 애플리케이션 실행:"
echo "      ./run.sh backend         # 백엔드만 (포트 5000)"
echo "      ./run.sh frontend        # 프론트엔드만 (포트 3000)"
echo "      ./run.sh                 # 동시 실행"
echo ""
echo "🧹 정리 방법:"
echo "      ./clean.sh               # 설치된 파일들 모두 삭제"
echo ""
echo "📝 주의: 새 터미널에서는 항상 가상환경을 먼저 활성화하세요!"
echo ""