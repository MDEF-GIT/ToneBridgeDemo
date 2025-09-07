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