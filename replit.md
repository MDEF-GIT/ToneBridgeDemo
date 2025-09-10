# ToneBridge Voice Analysis Platform

## Overview

ToneBridge is a comprehensive Korean voice analysis platform designed for pronunciation learning and speech therapy applications. The system integrates advanced speech processing algorithms, multi-engine STT (Speech-to-Text) capabilities, and real-time pitch analysis to provide accurate voice analysis and feedback for Korean language learners, particularly targeting hearing-impaired education and speech therapy domains.

The platform implements a microservices architecture with a FastAPI backend handling complex audio processing pipelines and a React TypeScript frontend providing interactive visualization and user interface components.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
The frontend is built using React 18+ with TypeScript, implementing a component-based architecture:

- **Build System**: Create React App (CRA) with TypeScript configuration
- **State Management**: React hooks with custom hook patterns for audio analysis
- **Visualization**: Chart.js with react-chartjs-2 for dual-axis pitch charts and real-time audio visualization
- **HTTP Client**: Axios for API communication with the backend
- **Routing**: React Router v6 for single-page application navigation
- **UI Components**: Custom components for file upload, audio analysis, and pitch visualization

Key frontend components include:
- `VoiceAnalysisApp`: Main application component managing audio analysis workflow
- `UploadedFileTestSection`: Handles user audio file uploads and processing
- Custom hooks for pitch chart management and audio analysis state

### Backend Architecture
The backend implements a FastAPI-based microservices architecture with specialized audio processing modules:

- **Core Server**: FastAPI application (`backend_server.py`) with 25+ API endpoints
- **Audio Processing Pipeline**: Parselmouth (Python binding for Praat) for authentic pitch extraction
- **STT Integration**: Multi-engine STT system supporting Whisper, Google Cloud, Azure, and Naver CLOVA
- **Korean Language Processing**: Specialized modules for Korean syllable segmentation and phonetic analysis
- **File Management**: Static file serving for reference audio files and user uploads

Core backend modules include:
- `tonebridge_core/`: Core AI modules for analysis, segmentation, and STT processing
- `advanced_stt_processor.py`: Multi-engine STT with Korean language optimization
- `korean_audio_optimizer.py`: Korean-specific audio preprocessing for improved STT accuracy
- `audio_analysis.py`: Comprehensive audio feature extraction and analysis tools

### Database and Storage
The system uses SQLAlchemy ORM with models for:
- User management and learner profiles
- Analysis session tracking
- Reference file metadata management
- Survey response collection

File storage is handled through a static file system with organized directories for reference files and user uploads.

### API Architecture
The backend exposes a comprehensive REST API with endpoints for:
- **Audio Analysis**: `/analyze_ref`, `/api/record_realtime` for real-time and batch audio processing
- **File Management**: CRUD operations for reference files and user uploads
- **STT Processing**: Multiple STT engine endpoints with quality validation
- **Pitch Analysis**: Specialized endpoints for pitch data extraction and TextGrid generation

### Real-time Processing Pipeline
The system implements a sophisticated audio processing pipeline:
1. Audio normalization and Korean-specific preprocessing
2. Multi-engine STT processing with ensemble results
3. Syllable segmentation using Korean linguistic rules
4. Pitch analysis using Praat algorithms via Parselmouth
5. TextGrid generation for temporal alignment
6. Real-time visualization data preparation

## External Dependencies

### Core Technologies
- **FastAPI**: Backend web framework for high-performance API development
- **React 18+**: Frontend framework with TypeScript for type safety
- **Parselmouth**: Python binding for Praat acoustic analysis software
- **SQLAlchemy**: ORM for database operations and model management

### Audio Processing Libraries
- **librosa**: Advanced audio analysis and feature extraction
- **soundfile**: Audio file I/O operations
- **pydub**: Audio manipulation and format conversion
- **numpy**: Numerical computing for audio signal processing

### STT Engines and APIs
- **OpenAI Whisper**: Local STT processing with Korean language support
- **Google Cloud Speech-to-Text**: Cloud-based STT with high accuracy
- **Azure Cognitive Services**: Microsoft's speech recognition services
- **Naver CLOVA Speech**: Korean-optimized commercial STT service

### Visualization and UI
- **Chart.js**: Charting library for pitch visualization and real-time audio feedback
- **chartjs-plugin-annotation**: Chart.js plugin for adding annotations to pitch charts
- **react-chartjs-2**: React wrapper for Chart.js integration

### Development and Deployment
- **Express.js**: Client proxy server for microservices communication (port 5000)
- **CORS**: Cross-origin resource sharing for API access
- **http-proxy-middleware**: Proxy middleware for frontend-backend communication

### Analytics and Monitoring
- **Google Analytics**: User behavior tracking with ID G-56D78RCESE
- Comprehensive logging system for debugging and performance monitoring

The system is designed to handle gateway timeouts and connection issues gracefully, with fallback mechanisms for STT processing and audio analysis when primary services are unavailable.