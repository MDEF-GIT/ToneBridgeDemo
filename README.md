# ToneBridge Voice Analysis Demo

한국어 운율 학습 플랫폼 - 완전 독립 실행형 데모

## 🚀 빠른 시작 (완전 독립 설치)

### 1. 자동 설치 (권장)

**Linux/macOS:**
```bash
# 완전 독립 환경 설치 (Python 가상환경 + React)
./install.sh

# 실행
./run.sh
```

**Windows:**
```cmd
REM 완전 독립 환경 설치
install.bat

REM 실행
run.bat
```

### 2. 수동 설치

```bash
# 1. Python 가상환경 생성
python3 -m venv venv

# 2. 가상환경 활성화
source venv/bin/activate  # Linux/macOS
# 또는
venv\Scripts\activate     # Windows

# 3. Python 의존성 설치 (가상환경 내)
pip install -r requirements.txt

# 4. React 의존성 설치
npm install concurrently
cd react-app && npm install && cd ..
```

### 3. 애플리케이션 실행

```bash
# 가상환경 활성화 (필수!)
source venv/bin/activate

# 실행 옵션
./run.sh              # 백엔드 + 프론트엔드 동시
./run.sh backend      # 백엔드만 (포트 8000)
./run.sh frontend     # 프론트엔드만 (포트 3000)

# 또는 npm 스크립트
npm start             # 동시 실행
npm run start-backend # 백엔드만
npm run start-frontend # 프론트엔드만
```

## 📁 프로젝트 구조

```
voice-analysis-demo/
├── backend_server.py          # FastAPI 백엔드 서버
├── requirements.txt           # Python 의존성
├── package.json              # 프로젝트 설정
├── reference_files/          # 연습용 음성 파일 (20개)
├── static/                   # 정적 파일들
└── react-app/                # React TypeScript 앱
    ├── package.json          # React 의존성  
    └── src/
        ├── VoiceAnalysisApp.tsx    # 메인 컴포넌트
        └── hooks/                   # 커스텀 훅들
```

## 🔧 의존성

### Python (backend_server.py)
- fastapi, uvicorn - 웹 서버
- parselmouth - 음성 분석
- sqlalchemy - 데이터베이스
- numpy - 수치 연산

### React (react-app/)
- react, typescript - UI 프레임워크
- chart.js, react-chartjs-2 - 차트 라이브러리
- axios, @tanstack/react-query - API 통신

## 🎯 기능

- ✅ 실시간 음성 분석 및 시각화
- ✅ 참조 음성과 실시간 비교
- ✅ WebAudio API 기반 마이크 녹음
- ✅ Parselmouth 기반 정확한 피치 분석
- ✅ 완전 독립 실행 (외부 서비스 불필요)

## 📋 시스템 요구사항

- Python 3.8+
- Node.js 16+
- 마이크 지원 브라우저