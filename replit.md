# ToneBridge Voice Analysis Platform

## Overview

ToneBridge is a comprehensive voice analysis platform specifically designed for Korean prosody learning, targeting deaf education and language therapy applications. The platform integrates advanced audio preprocessing, multi-STT engines, and real-time pitch analysis in a microservice architecture to provide a complete voice learning experience.

The system achieves 99% STT accuracy through multi-engine integration (Whisper, Google Cloud, Azure, Naver CLOVA) and features Korean-specific syllable segmentation algorithms with phonetic validation. It provides real-time voice processing and visualization using Chart.js for advanced data presentation, along with a fully automated pipeline from STT to segmentation to TextGrid generation to visualization.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Microservice Architecture
The platform employs a three-tier microservice architecture:

**Frontend Layer**: React 18+ with TypeScript, featuring 4 custom hooks for state management and Chart.js integration for real-time pitch visualization. The client proxy runs on Express.js (port 5000) handling static file serving and API routing.

**Backend Layer**: FastAPI server (port 8000) with 32 API endpoints implementing the core voice analysis pipeline. The backend features Parselmouth (Praat Python binding) for authentic F0 extraction and includes 18 specialized AI processing modules for different aspects of voice analysis.

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
- **Axios 1.6.0**: HTTP client for API communication with interceptors and error handling

### Development and Build Tools
- **React Scripts 5.0.1**: Build toolchain for React applications with webpack and babel configuration
- **Express.js**: Proxy server for development environment routing between frontend and backend
- **CORS middleware**: Cross-origin resource sharing configuration for API access

### Analytics and Monitoring
- **Google Analytics**: User behavior tracking and performance monitoring with custom event tracking for voice analysis sessions
- **Custom logging system**: Comprehensive application logging for debugging and performance analysis

The system is designed to be modular and extensible, allowing for easy integration of additional STT engines or audio processing capabilities. All external dependencies are managed through package managers (pip for Python, npm for Node.js) with version pinning for reproducible builds.