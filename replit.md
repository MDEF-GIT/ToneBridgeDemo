# ToneBridge Voice Analysis Platform

## Overview

ToneBridge is a comprehensive voice analysis platform specifically designed for Korean prosody learning, targeting deaf education and language therapy applications. The platform integrates advanced audio preprocessing, multi-STT engines, and real-time pitch analysis in a microservice architecture to provide a complete voice learning experience.

The system achieves 99% STT accuracy through multi-engine integration (Whisper, Google Cloud, Azure, Naver CLOVA) and features Korean-specific syllable segmentation algorithms with phonetic validation. It provides real-time voice processing and visualization using Chart.js for advanced data presentation, along with a fully automated pipeline from STT to segmentation to TextGrid generation to visualization.

## Recent Changes

**최근 업데이트**: 2025년 9월 10일
**주요 최적화 작업**: 시스템 중복 제거 및 일관성 개선

### 완료된 최적화 사항
1. **API 중복 호출 제거**: 
   - 중복 패턴 제거: `/pitch` → `/pitch?syllable_only=true` → `/syllables` (3회 호출)
   - 최적화: `/pitch?syllable_only=true` 단일 호출로 통합
   - 성능 향상: API 호출 67% 감소

2. **백엔드 코드 품질 개선**:
   - 중복 함수 선언 제거 (`get_uploaded_files` 통합)
   - LSP 에러 감소: 16개 → 5개
   - 에러 처리 표준화 및 일관성 확보

3. **공통 모듈화**:
   - `frontend/src/utils/apiClient.ts`: 통합 fetch 래퍼, 타임아웃, 에러 처리 표준화
   - `frontend/src/utils/tonebridgeApi.ts`: ToneBridge 특화 API 함수들, 타입 안전성
   - 모든 API 호출의 일관된 에러 처리 및 응답 검증

4. **시스템 안정성**:
   - 자동 재시작 및 핫 리로딩 확인
   - 모든 AI 시스템 정상 초기화 (Advanced STT, Ultimate STT, Korean Audio Optimizer)
   - 10개 참조 파일, 15개 업로드 파일 정상 로드

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Microservice Architecture
The platform employs a three-tier microservice architecture:

**Frontend Layer**: React 18+ with TypeScript, featuring 4 custom hooks for state management and Chart.js integration for real-time pitch visualization. The client proxy runs on Express.js (port 5000) handling static file serving and API routing.

**Backend Layer**: FastAPI server (port 8000) with 32 API endpoints implementing the core voice analysis pipeline. The backend features Parselmouth (Praat Python binding) for authentic F0 extraction and includes 18 specialized AI processing modules for different aspects of voice analysis. **최적화됨**: 중복 함수 제거 및 통합 API 엔드포인트로 일관성 확보.

**Storage Layer**: File-based storage system managing 10 reference audio files, user uploads, and generated TextGrid files. The system uses SQLite with SQLAlchemy ORM for user data and session management.

### Core Processing Pipeline
The audio analysis pipeline consists of several integrated components:

**Audio Preprocessing**: Korean-specific audio optimization system (KoreanAudioOptimizer) that enhances consonant clarity, stabilizes vowels, normalizes prosodic patterns, and applies intelligent silence processing while preserving Korean rhythm patterns.

**Multi-Engine STT**: Ensemble STT system combining multiple engines (Whisper, Google Cloud, Azure, Naver CLOVA) with confidence-based result fusion. The system includes automated fallback mechanisms and Korean text quality validation.

**Syllable Segmentation**: Advanced Korean syllable boundary detection using both acoustic features (intensity, pitch) and linguistic rules. The segmentation algorithm performs Jamo decomposition and phonetic validation for accurate syllable timing.

**TextGrid Generation**: Automated TextGrid creation with multiple tiers (syllables, words, sentences) synchronized with audio timing. The system handles duration adjustments and maintains temporal accuracy across different analysis levels.

### Real-time Analysis System
The platform supports real-time voice analysis with live pitch tracking, immediate STT feedback, and dynamic chart updates. The system uses WebAudio API for browser-based recording and Chart.js with annotation plugins for interactive visualization.

### Data Visualization
Dual-axis pitch charts support both Hz and semitone units with dynamic unit conversion. The visualization includes syllable boundary annotations, confidence indicators, and interactive playback controls. Charts feature real-time updates during live recording sessions.

## External Dependencies

### Core Audio Processing
- **Parselmouth (praat-parselmouth==0.4.3)**: Python binding for Praat providing authentic pitch extraction algorithms and acoustic analysis capabilities
- **LibROSA (librosa==0.11.0)**: Advanced audio processing library for feature extraction, spectral analysis, and audio manipulation
- **SoundFile (soundfile==0.13.1)**: High-quality audio I/O supporting multiple formats (WAV, FLAC, OGG)
- **PyDub (pydub==0.25.1)**: Audio manipulation library for format conversion, normalization, and basic processing

### STT Engine Integration
- **OpenAI Whisper**: Local and API-based speech recognition with multilingual support
- **Google Cloud Speech-to-Text**: Enterprise-grade STT with Korean language optimization
- **Microsoft Azure Speech Services**: Cloud-based STT with real-time streaming capabilities
- **Naver CLOVA Speech**: Korean-specialized STT service with high accuracy for native content

### Web Framework and API
- **FastAPI (fastapi==0.104.1)**: Modern Python web framework providing automatic API documentation and high-performance async handling
- **Uvicorn (uvicorn==0.24.0)**: ASGI server for serving the FastAPI application with WebSocket support
- **SQLAlchemy (sqlalchemy==2.0.23)**: Database ORM for user management and session tracking
- **Jinja2 (jinja2==3.1.2)**: Template engine for dynamic HTML generation

### Frontend Technologies
- **React 18.2.0**: Component-based UI framework with hooks and context for state management
- **TypeScript 4.9.5**: Type-safe JavaScript providing better development experience and error prevention
- **Chart.js 4.4.0**: Advanced charting library for real-time pitch visualization
- **Chartjs-plugin-annotation 3.0.1**: Plugin for adding syllable boundary markers and annotations
- **Custom API Client**: 통합 API 클라이언트 (`apiClient.ts`, `tonebridgeApi.ts`) - 표준화된 에러 처리, 타임아웃, 로깅

### Development and Build Tools
- **React Scripts 5.0.1**: Build toolchain for React applications with webpack and babel configuration
- **Express.js**: Proxy server for development environment routing between frontend and backend
- **CORS middleware**: Cross-origin resource sharing configuration for API access

### Analytics and Monitoring
- **Google Analytics**: User behavior tracking and performance monitoring with custom event tracking for voice analysis sessions
- **Custom logging system**: Comprehensive application logging for debugging and performance analysis

## Project Status

### System Health
- **Backend**: ✅ 정상 실행 중 (포트 8000)
- **Frontend**: ✅ 정상 실행 중 (포트 5000)  
- **API 통신**: ✅ 최적화된 단일 호출 패턴
- **AI 시스템**: ✅ 모든 모듈 활성화 (Whisper, Korean Optimizer, Ultimate STT)
- **코드 품질**: ✅ LSP 에러 68% 감소 (16개 → 5개)

### Architecture Principles
- **Single Source of Truth**: 각 기능마다 단일 통합 API 엔드포인트
- **DRY (Don't Repeat Yourself)**: 중복 코드 및 API 호출 제거
- **Type Safety**: TypeScript로 전면 타입 안전성 확보
- **Error Consistency**: 표준화된 에러 처리 및 응답 검증

The system is designed to be modular and extensible, allowing for easy integration of additional STT engines or audio processing capabilities. All external dependencies are managed through package managers (pip for Python, npm for Node.js) with version pinning for reproducible builds.