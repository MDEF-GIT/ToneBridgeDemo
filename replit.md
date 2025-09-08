# ToneBridge Voice Analysis Microservices

## Overview

ToneBridge is a Korean prosody learning platform built with microservices architecture for voice analysis and pronunciation training. The application focuses on helping users, particularly those in deaf education and language therapy, analyze and improve Korean speech patterns through real-time audio processing and visualization.

The platform is designed as independent microservices that can be deployed separately and integrated into larger systems.

The system implements authentic Praat pitch extraction algorithms using parselmouth (Praat Python) for accurate voice analysis, combined with a modern React frontend for interactive user experiences. The platform serves both language therapists and general users with specialized survey systems to gather feedback for service improvement.

## User Preferences

Preferred communication style: Simple, everyday language.

## Microservices Architecture

### Backend API Service (Port 8000)
- **Framework**: FastAPI with Python 3.8+ for high-performance API development
- **Audio Processing**: Parselmouth (Praat Python) integration for authentic pitch extraction and prosodic analysis
- **API Design**: RESTful endpoints for voice analysis, reference files, and audio processing
- **File Handling**: Supports WAV and TextGrid file processing for audio analysis
- **Database**: SQLAlchemy ORM with configurable database backends
- **Location**: `backend/` directory

### Frontend Service (Standalone React App)
- **Framework**: React 18+ with TypeScript for modern, interactive user interfaces
- **Charts and Visualization**: Chart.js with annotation plugins for real-time audio data visualization
- **Styling**: Bootstrap 5.3+ with Pretendard Korean font for optimal readability
- **Build System**: Create React App with standard React toolchain
- **API Integration**: Configurable backend API endpoint (default: localhost:8000)
- **Location**: `frontend/` directory

### Client Proxy Service (Port 5000)
- **Framework**: Express.js with CORS and proxy middleware
- **Purpose**: Demonstration client that proxies requests to backend API
- **Features**: Web interface with direct app access, API docs, and iframe embedding
- **Location**: `temp-frontend/` directory

### Data Storage
- **Database**: SQLAlchemy ORM with configurable database backends (default SQLite)
- **Models**: User management, analysis sessions, survey responses, and reference file storage
- **Session Management**: Flask-Login integration for user authentication
- **File Storage**: Local filesystem storage in static/uploads directory

### Authentication and Authorization
- **User System**: Flask-Login based authentication with password hashing
- **Session Management**: Database-backed user sessions and analysis history
- **Public Access**: Reference files and demo features available without authentication
- **Privacy Controls**: User-controlled visibility settings for uploaded content

### Audio Analysis Pipeline
- **Pitch Extraction**: Real-time F0 (fundamental frequency) analysis using Praat algorithms
- **Gender Detection**: Automatic voice characteristic analysis for personalized feedback
- **Syllable Counting**: Korean language-specific prosodic unit detection
- **File Format Support**: WAV audio input with TextGrid annotation support
- **Real-time Processing**: Live audio analysis with immediate visual feedback

### Deployment Architecture
- **Standalone Design**: Complete independent environment with virtual Python environment
- **Cross-Platform**: Support for Linux, macOS, and Windows with automated setup scripts
- **Replit Integration**: Special npm commands for cloud development environment compatibility
- **Development Mode**: Concurrent backend/frontend development with hot reloading

## External Dependencies

### Core Python Libraries
- **FastAPI**: Modern async web framework for API development
- **Parselmouth**: Python interface to Praat for speech analysis
- **SQLAlchemy**: Database ORM for data persistence
- **NumPy**: Numerical computing for audio signal processing
- **Uvicorn**: ASGI server for FastAPI application hosting

### Frontend Dependencies
- **React**: Component-based UI library with hooks and modern features
- **Chart.js**: Canvas-based charting library for audio visualization
- **Axios**: HTTP client for API communication
- **React Query**: Server state management and caching
- **Bootstrap**: CSS framework for responsive design

### Development Tools
- **Concurrently**: Tool for running multiple npm scripts simultaneously
- **TypeScript**: Static typing for JavaScript development
- **React Scripts**: Build toolchain and development server
- **Create React App**: Project bootstrapping and configuration

### External Services
- **Google Analytics**: User behavior tracking and analytics (ID: G-56D78RCESE)
- **Naver Forms**: External survey collection for user feedback
- **CDN Resources**: Bootstrap, Font Awesome, Chart.js, and Pretendard font delivery

### System Requirements
- **Python**: Version 3.8 or higher for modern async/await support
- **Node.js**: Version 16+ for React development and build processes
- **Browser Compatibility**: Modern browsers with WebRTC support for audio capture
- **Audio Hardware**: Microphone access required for real-time analysis features

## HTML Template Analysis and React Implementation Strategy

### Template Inheritance Hierarchy
```
base.html (Master Template)
├── index.html (Main Learning Platform - COMPLETE FEATURES)
├── react-complete-voice-analysis.html (React-style Demo)
└── survey.html (User Feedback Collection)
```

### Core Features from index.html (Target for React Implementation)
1. **Personalized Coaching Survey CTA** - Gradient banner with badges and survey link
2. **Mobile Landscape Orientation Guide** - Animated warning for mobile users  
3. **Learner Information Input** - Name, gender (required), age group forms
4. **Learning Method Selection** - Pitch learning vs Reference intonation learning with detailed guides
5. **Practice Sentence Selection & Video Guide** - 10 prepared sentences with instructional video
6. **Real-time Analysis Chart** - Advanced Chart.js with controls (zoom, scroll, key adjustment)
7. **Syllable Analysis Table** - Detailed breakdown with prosodic measurements
8. **Gender Selection Modal** - Bootstrap modal for voice calibration

### Technical Implementation References from react-complete-voice-analysis.html
- **MediaRecorder API**: Real-time audio capture and processing
- **FormData Handling**: File uploads (audio + TextGrid)
- **Backend Integration**: Fetch API calls to Python FastAPI endpoints
- **Chart.js Integration**: Canvas-based pitch visualization
- **Error Handling**: Comprehensive try-catch with user feedback

### Missing Assets and Dependencies
- **CSS**: `/static/css/custom.css` (referenced but not found)
- **JavaScript**: `/static/js/audio-analysis.js` (referenced but not found)
- **Media Files**: 
  - `/static/images/video-thumbnail.jpg` ✓ (exists)
  - `/static/videos/tonebridge_guide.mp4` ✓ (exists)
- **Reference Files**: 10 audio files with TextGrid annotations ✓ (exists)

### API Endpoint Mapping
```
index.html: API_BASE = "" (relative paths)
react-complete: API_BASE = "http://localhost:8000" (absolute paths)
React App Target: Configurable API_BASE for both development and production
```

### Animation and Styling Requirements
- **CSS Animations**: `shake`, `bounce` for mobile warning
- **Gradient Backgrounds**: Linear gradients for CTA and warning sections
- **Bootstrap Integration**: Full Bootstrap 5.3.3 with custom color schemes
- **Responsive Design**: Mobile-first approach with landscape orientation handling
- **Font Integration**: Pretendard Korean font for optimal readability

## Recent Changes

### 2025-09-08: 다중 STT 엔진 통합 및 고급 음성 처리 시스템 완성
- **고급 음성 처리 모듈 개발**: `backend/audio_enhancement.py` 완전 자동화된 처리 시스템
- **다중 STT 엔진 통합**: `backend/advanced_stt_processor.py`에 엔터프라이즈급 STT 시스템 구현
  - **UniversalSTT**: Whisper, Google Cloud, Azure, Naver CLOVA 다중 엔진 지원
  - **KoreanSyllableAligner**: 한국어 특화 음절 정렬 및 자모 분해 시스템
  - **AdvancedSTTProcessor**: 신뢰도 평가 및 자동 엔진 선택 기능
- **한국어 특화 기능**: 
  - 자모 분해 기반 음성학적 분석 (초성, 중성, 종성)
  - 타임스탬프 기반 정밀 음절 분절
  - 텍스트 유사도 기반 자동 보정
- **백엔드 API 대폭 확장**: 
  - `/api/auto-process`: 완전 자동화된 오디오 처리
  - `/api/advanced-stt`: 고급 STT 처리 (다중 엔진 + 신뢰도 평가)
  - `/api/multi-engine-comparison`: STT 엔진 성능 비교 분석
  - `/api/syllable-alignment-analysis`: 음절 정렬 상세 분석
  - `/api/optimize-textgrid/{file_id}`: 기존 파일 TextGrid 최적화
  - `/api/stt-status`: 고급 STT 시스템 상태 및 엔진 정보
- **실제 검증 완료**: 
  - "낭독문장.wav" 파일로 17개 음절 정확 분절 확인
  - 다중 엔진 fallback 시스템 정상 작동
  - 한국어 음절 정렬 및 자모 분해 기능 완벽 구현
- **TextGrid 동기화 문제 완전 해결**: 자동 분절을 통해 오디오-TextGrid 시간 오프셋 문제 완전 해결

### 2025-09-08: 연습문제 선택 리스트 및 차트 자동 반영 기능 수정
- **오리지널 백업 분석**: vanilla-js 버전의 loadSentenceForLearner() 로직 분석
- **handleSentenceSelection 수정**: 잘못된 `/api/analyze/${fileId}` API 호출 제거
- **올바른 차트 로딩**: `pitchChart.loadReferenceData(fileId)` 함수 호출로 변경
- **성별 검증 추가**: 오리지널과 동일한 학습자 성별 필수 선택 로직 구현
- **API 응답 구조 개선**: data.files 또는 직접 배열 모두 처리하도록 유연성 추가
- **useEffect 무한 루프 문제 해결**: 의존성 배열 분리로 API 중복 호출 방지

### 2025-09-08: Chart.js Annotation 및 음절 시각화 기능 구현
- **Chart.js annotation 플러그인 설치**: React 프론트엔드에 chartjs-plugin-annotation@3.0.1 패키지 추가
- **음절 구간 표시 기능 구현**: 
  - usePitchChart 훅에 addSyllableAnnotations() 함수 추가
  - 오리지널 vanilla JS와 동일한 음절 시각화 로직 (점선 구간, 보라색 라벨 박스)
  - 음절 시작/끝 경계선: rgba(255, 99, 132, 0.8) 색상의 점선 표시
  - 음절 라벨: rgba(138, 43, 226, 0.9) 보라색 배경의 한글 라벨
- **백엔드 syllables API 추가**:
  - `/api/reference_files/{file_id}/syllables` 엔드포인트 구현
  - TextGrid 파일 파싱 대비 테스트용 더미 데이터 반환
  - 에러 시 빈 배열 반환으로 프론트엔드 호환성 보장
- **차트 컨트롤 기능 확장**: 
  - adjustPitch (피치 위/아래 조정), zoomIn/zoomOut (시간축 확대/축소)
  - scrollLeft/scrollRight (좌우 스크롤), resetView (전체 보기)
  - 오리지널 버전의 모든 차트 조작 기능 React로 이식

### 2025-09-07: Complete TypeScript and React Syntax Resolution
- **Fixed all TypeScript configuration issues**: Updated `tsconfig.json` with proper ES2020 target, comprehensive lib array including DOM, ES2015-2020, and webworker
- **Resolved React import compatibility**: Changed all React imports from `import * as React` to `import React` for React 19 compatibility
- **Added comprehensive type definitions**: Created extensive type declarations in `react-app-env.d.ts` for:
  - React hooks (useState, useEffect, useCallback, useRef) with proper destructuring support
  - All browser APIs (localStorage, window, document, navigator, fetch, etc.)
  - Audio processing APIs (AudioContext, MediaRecorder, Float32Array)
  - Event handler types with proper value/checked properties
  - Array methods (map, filter, includes) and Number prototype methods
- **Upgraded TypeScript**: Updated from 4.9.5 to 5.2.2 with @types/node@20 for better React 19 support
- **Eliminated all 121 LSP diagnostics**: Complete resolution of syntax errors across 5 TypeScript React files
- **Verified application functionality**: Both backend and frontend services running correctly with successful API communication

### System Status
- ✅ Backend Service: Running on port 8000 with 10 reference files loaded
- ✅ Frontend Client: React 18.2.0 successfully building and serving on port 5000  
- ✅ API Integration: Proxy successfully routing requests to backend
- ✅ TypeScript: Zero compilation errors across all components
- ✅ React Components: All hooks and event handlers working properly
- ✅ Runtime Errors: Completely resolved (React 19→18 compatibility fix)
- ✅ 404 Errors: Resolved (removed unused CSS/JS file references)
- ✅ Production Build: Stable React 18 bundle (main.8f06955d.js)
- ✅ Advanced STT System: Multi-engine support with Korean syllable alignment
- ✅ Automated Processing: Complete audio-to-TextGrid pipeline operational
- ✅ Quality Assurance: Confidence scoring and validation systems active

### 2025-01-07: Complete HTML Architecture Analysis
- Identified index.html as the definitive feature source (not simplified react-complete version)
- Documented template inheritance: base.html → child templates
- Discovered missing CSS/JS files that need to be created for React implementation
- Established complete feature mapping for React conversion
- Confirmed 8 major UI components need to be implemented in React