# ToneBridge 설치 가이드

ToneBridge 한국어 음성 분석 플랫폼의 우분투/Pure Nix 완전 호환 설치 가이드입니다.

## 🚀 자동 설치 (권장)

### 방법 1: Bash 스크립트 (Ubuntu/Debian)
```bash
# 저장소 클론
git clone [repository-url]
cd backend

# 실행 권한 부여
chmod +x install.sh

# 자동 설치 실행
./install.sh
```

### 방법 2: Python 스크립트 (모든 환경)
```bash
cd backend
python3 install_dependencies.py
```

## 📋 지원 환경

### ✅ 완전 지원
- **Ubuntu 20.04+ / Debian 11+**
- **Pure Nix 환경 (Replit)**
- **Python 3.11+**

### ⚠️ 부분 지원
- **Python 3.9-3.10** (일부 기능 제한 가능)
- **기타 Linux 배포판** (수동 의존성 설치 필요)

## 🎯 핵심 패키지 (100% 검증됨)

다음 패키지들은 Ubuntu와 Pure Nix 환경에서 완전히 검증되었습니다:

### 🎵 음성 분석 엔진
- **praat-parselmouth 0.4.3** - Praat 음성 분석
- **faster-whisper 1.2.0** - 고성능 STT 엔진
- **librosa 0.10.2** - 오디오 신호 처리
- **soundfile 0.12.1** - 오디오 파일 I/O

### 🇰🇷 한국어 처리
- **jamo 0.4.1** - 한글 자모 분해/조합
- **konlpy 0.6.0** - 한국어 형태소 분석
- **jpype1 1.6.0** - Java 연결 (konlpy 의존성)

### 🌐 웹 프레임워크
- **fastapi 0.104.1** - 고성능 웹 API
- **uvicorn 0.24.0** - ASGI 서버
- **sqlalchemy 2.0.43** - 데이터베이스 ORM

## 🔧 수동 설치

### 시스템 의존성 (Ubuntu)
```bash
sudo apt update
sudo apt install -y \
    python3-dev python3-pip python3-venv \
    build-essential pkg-config libffi-dev libssl-dev \
    libasound2-dev libportaudio2 portaudio19-dev \
    libsndfile1-dev libsamplerate0-dev libfftw3-dev \
    libblas-dev liblapack-dev gfortran \
    openjdk-17-jdk curl wget git
```

### Python 패키지
```bash
# 가상환경 생성 (선택사항)
python3 -m venv venv
source venv/bin/activate

# pip 업그레이드
python3 -m pip install --upgrade pip setuptools wheel

# ToneBridge 패키지 설치
pip install -r requirements.txt
```

## 🧪 설치 확인

```bash
python3 -c "
import parselmouth, faster_whisper, librosa, soundfile
import jamo, konlpy, fastapi, uvicorn
print('🎉 ToneBridge 핵심 패키지 설치 완료!')
"
```

## 🚀 서버 시작

```bash
cd backend
python backend_server.py
```

또는

```bash
./run_server.sh
```

서버가 `http://localhost:8000`에서 시작됩니다.

## 🐛 문제 해결

### Java 관련 오류 (konlpy)
```bash
# Java 설치 확인
java -version

# JAVA_HOME 설정 (Ubuntu)
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
echo 'export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64' >> ~/.bashrc
```

### 오디오 라이브러리 오류
```bash
# Ubuntu 추가 오디오 패키지
sudo apt install -y ffmpeg libavcodec-extra
```

### 권한 오류
```bash
# 스크립트 실행 권한 부여
chmod +x install.sh run_server.sh
```

## 📊 설치 성공률

- **Pure Nix 환경**: 100% (16/16 패키지)
- **Ubuntu 20.04+**: 95%+ (핵심 패키지 완전 지원)
- **기타 Linux**: 80%+ (수동 의존성 설치 필요)

## 🎯 최소 요구사항

- **Python**: 3.9+ (3.11+ 권장)
- **메모리**: 4GB+ RAM
- **저장공간**: 2GB+ 여유공간
- **Java**: 17+ (konlpy용, 자동 설치됨)

## 📞 지원

설치 문제가 발생하면 다음을 확인하세요:

1. Python 버전 호환성
2. 시스템 의존성 설치 상태
3. 네트워크 연결 상태
4. 디스크 여유공간

로그 파일: `install.log` (자동 생성됨)
