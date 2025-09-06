#!/bin/bash

echo "🧹 ToneBridge Voice Analysis Demo - 정리"
echo "====================================="

# 스크립트 실행 위치 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🗑️  설치된 파일들을 정리합니다..."

# Python 가상환경 삭제
if [ -d "venv" ]; then
    echo "🐍 Python 가상환경 삭제 중..."
    rm -rf venv/
    echo "✅ Python 가상환경 삭제 완료"
else
    echo "ℹ️  Python 가상환경이 없습니다"
fi

# Node.js 의존성 삭제
if [ -d "node_modules" ]; then
    echo "📦 Node.js 의존성 삭제 중..."
    rm -rf node_modules/
    echo "✅ Node.js 의존성 삭제 완료"
else
    echo "ℹ️  Node.js 의존성이 없습니다"
fi

# React 앱 node_modules 삭제
if [ -d "react-app/node_modules" ]; then
    echo "⚛️  React 앱 의존성 삭제 중..."
    rm -rf react-app/node_modules/
    echo "✅ React 앱 의존성 삭제 완료"
else
    echo "ℹ️  React 앱 의존성이 없습니다"
fi

# package-lock.json 삭제
if [ -f "package-lock.json" ]; then
    echo "📄 package-lock.json 삭제 중..."
    rm -f package-lock.json
    echo "✅ package-lock.json 삭제 완료"
else
    echo "ℹ️  package-lock.json이 없습니다"
fi

# React 앱 package-lock.json 삭제
if [ -f "react-app/package-lock.json" ]; then
    echo "📄 React 앱 package-lock.json 삭제 중..."
    rm -f react-app/package-lock.json
    echo "✅ React 앱 package-lock.json 삭제 완료"
else
    echo "ℹ️  React 앱 package-lock.json이 없습니다"
fi

# Python 캐시 파일들 삭제
if [ -d "__pycache__" ]; then
    echo "🐍 Python 캐시 파일 삭제 중..."
    rm -rf __pycache__/
    echo "✅ Python 캐시 파일 삭제 완료"
else
    echo "ℹ️  Python 캐시 파일이 없습니다"
fi

# 임시 로그 파일들 삭제
echo "📝 임시 로그 파일 정리 중..."
rm -f *.log
rm -f /tmp/demo_server.log 2>/dev/null || true
echo "✅ 임시 로그 파일 정리 완료"

echo ""
echo "✅ 모든 설치 파일 정리 완료!"
echo ""
echo "💡 다시 설치하려면:"
echo "   ./install.sh"
echo ""