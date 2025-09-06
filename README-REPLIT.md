# ToneBridge Voice Analysis Demo - Replit 사용법

## 🎯 Replit 환경 전용 npm 명령어

원본 스크립트 파일들(`install.sh`, `run.sh`, `clean.sh`)은 수정하지 않고, Replit 환경에서만 사용할 수 있는 별도의 npm 명령어를 제공합니다.

## 📦 설치

```bash
# Replit 환경 전용 설치 (가상환경 없이 전역 설치)
npm run install-replit
```

## 🚀 실행

```bash
# 백엔드만 실행 (포트 5000)
npm run start-backend-replit

# 개발 모드 (포트 5000)
npm run dev-replit
```

## 🧹 정리

```bash
# Replit 환경 전용 정리 (가상환경 제외)
npm run clean-replit
```

## 📋 전체 명령어 목록

### Replit 전용
- `npm run install-replit` - Replit 환경 전용 설치
- `npm run start-backend-replit` - 백엔드 실행 (포트 5000)
- `npm run dev-replit` - 개발 모드 실행
- `npm run clean-replit` - Replit 환경 전용 정리

### 원본 스크립트 (로컬 환경용)
- `npm run install` - 로컬 가상환경 설치
- `npm run start` - 전체 실행
- `npm run start-backend` - 백엔드 실행
- `npm run start-frontend` - 프론트엔드 실행
- `npm run clean` - 완전 정리

## 🔧 차이점

| 항목 | 원본 스크립트 | Replit 전용 |
|-----|-------------|------------|
| Python 설치 | 가상환경 (venv) | 전역 설치 (--user) |
| 포트 | 8000 | 5000 |
| 환경 감지 | 자동 | 없음 (직접 명령) |
| 스크립트 수정 | 필요 | 불필요 |

## 💡 사용 팁

1. **원격지에서 받은 소스**: 스크립트 수정 없이 `npm run install-replit`로 바로 설치
2. **포트 충돌 방지**: Replit 전용 명령어는 포트 5000 사용
3. **빠른 개발**: `npm run dev-replit`로 개발 서버 실행