#!/bin/bash
# ToneBridge 우분투/Pure Nix 호환 설치 스크립트
# Ubuntu/Debian 환경에서도 완전 호환되도록 설계

set -e

echo "🚀 ToneBridge 설치 시작..."
echo "=================================="

# 환경 감지
detect_environment() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    else
        OS=$(uname -s)
    fi

    # Nix 환경 감지
    if command -v nix >/dev/null 2>&1 || [ -n "$NIX_PATH" ]; then
        ENV_TYPE="nix"
    elif [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
        ENV_TYPE="ubuntu"
    else
        ENV_TYPE="generic"
    fi

    echo "🔍 감지된 환경: $ENV_TYPE ($OS)"
}

# 시스템 의존성 설치
install_system_dependencies() {
    echo "📦 시스템 의존성 설치 중..."
    
    case $ENV_TYPE in
        "ubuntu")
            echo "Ubuntu/Debian 시스템 패키지 설치..."
            sudo apt update
            sudo apt install -y \
                python3-dev \
                python3-pip \
                python3-venv \
                build-essential \
                pkg-config \
                libffi-dev \
                libssl-dev \
                libasound2-dev \
                libportaudio2 \
                libportaudiocpp0 \
                portaudio19-dev \
                libsndfile1-dev \
                libsamplerate0-dev \
                libfftw3-dev \
                libblas-dev \
                liblapack-dev \
                gfortran \
                openjdk-17-jdk \
                curl \
                wget \
                git
            
            # Java 환경 설정
            export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
            echo "export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64" >> ~/.bashrc
            ;;
            
        "nix")
            echo "Nix 환경에서는 시스템 패키지가 이미 관리됩니다."
            ;;
            
        *)
            echo "⚠️  일반적인 Linux 환경입니다. 수동으로 의존성 설치가 필요할 수 있습니다."
            echo "다음 패키지들이 필요합니다:"
            echo "  - Python 3.11+ 개발 도구"
            echo "  - 오디오 처리 라이브러리 (portaudio, sndfile, fftw)"
            echo "  - Java 17 (konlpy용)"
            echo "  - 컴파일러 도구 (gcc, g++, gfortran)"
            ;;
    esac
}

# Python 가상환경 설정
setup_python_environment() {
    echo "🐍 Python 환경 설정 중..."
    
    # Python 버전 확인
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo "Python 버전: $PYTHON_VERSION"
    
    if [ $(echo "$PYTHON_VERSION >= 3.11" | bc -l) -eq 0 ]; then
        echo "⚠️  Python 3.11 이상이 권장됩니다. 현재: $PYTHON_VERSION"
    fi

    # 가상환경 생성 (Pure Nix가 아닌 경우에만)
    if [ "$ENV_TYPE" != "nix" ]; then
        if [ ! -d "venv" ]; then
            echo "가상환경 생성 중..."
            python3 -m venv venv
        fi
        echo "가상환경 활성화..."
        source venv/bin/activate
    fi

    # pip 업그레이드
    python3 -m pip install --upgrade pip setuptools wheel
}

# ToneBridge 패키지 설치
install_tonebridge_packages() {
    echo "📚 ToneBridge 패키지 설치 중..."
    
    # 필수 패키지 설치
    echo "1. 필수 패키지 설치..."
    python3 -m pip install -r requirements.txt
    
    # 선택적 패키지 설치 (실패해도 계속 진행)
    echo "2. 선택적 패키지 설치 시도..."
    while IFS= read -r package; do
        # 주석이나 빈 줄 건너뛰기
        if [[ $package =~ ^#.*$ ]] || [[ -z "$package" ]]; then
            continue
        fi
        
        echo "  설치 시도: $package"
        if python3 -m pip install "$package" 2>/dev/null; then
            echo "  ✅ $package 설치 성공"
        else
            echo "  ⚠️  $package 설치 실패 (선택사항이므로 계속 진행)"
        fi
    done < requirements-optional.txt
}

# 설치 확인
verify_installation() {
    echo "🧪 설치 확인 중..."
    
    python3 -c "
import sys
print(f'Python: {sys.version}')

# 핵심 패키지 확인
core_packages = [
    ('parselmouth', 'Praat 음성 분석'),
    ('faster_whisper', 'STT 엔진'),
    ('librosa', '오디오 처리'),
    ('soundfile', '오디오 I/O'),
    ('jamo', '한글 처리'),
    ('konlpy', '한국어 분석'),
    ('fastapi', '웹 프레임워크'),
    ('uvicorn', '웹 서버')
]

success_count = 0
total_count = len(core_packages)

print('\\n=== 핵심 패키지 확인 ===')
for module, desc in core_packages:
    try:
        __import__(module)
        print(f'✅ {desc} ({module})')
        success_count += 1
    except ImportError:
        print(f'❌ {desc} ({module})')

print(f'\\n📊 설치 성공률: {success_count}/{total_count} ({success_count/total_count*100:.1f}%)')

if success_count >= 6:
    print('\\n🎉 ToneBridge 설치 성공! 모든 핵심 기능을 사용할 수 있습니다.')
else:
    print('\\n⚠️  일부 패키지 설치에 실패했습니다. requirements-optional.txt의 패키지들을 개별적으로 설치해보세요.')
"
}

# 사용법 안내
show_usage() {
    echo ""
    echo "🎯 설치 완료!"
    echo "=================================="
    echo "ToneBridge 백엔드 서버 시작:"
    echo "  cd backend"
    
    if [ "$ENV_TYPE" != "nix" ]; then
        echo "  source venv/bin/activate  # 가상환경 활성화"
    fi
    
    echo "  python backend_server.py"
    echo ""
    echo "또는 설치 스크립트 사용:"
    echo "  ./run_server.sh"
    echo ""
    echo "프론트엔드는 temp-frontend 디렉토리에서:"
    echo "  cd temp-frontend"
    echo "  npm install"
    echo "  npm start"
}

# 메인 실행
main() {
    detect_environment
    install_system_dependencies
    setup_python_environment
    install_tonebridge_packages
    verify_installation
    show_usage
}

# 스크립트 실행
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi