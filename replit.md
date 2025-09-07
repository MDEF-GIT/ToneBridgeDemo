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

### 2025-01-07: Complete HTML Architecture Analysis
- Identified index.html as the definitive feature source (not simplified react-complete version)
- Documented template inheritance: base.html → child templates
- Discovered missing CSS/JS files that need to be created for React implementation
- Established complete feature mapping for React conversion
- Confirmed 8 major UI components need to be implemented in React

### Next Steps for React Implementation
1. Create missing CSS styles in React components (styled-components or CSS modules)
2. Implement all 8 major features from index.html
3. Integrate Chart.js with annotation plugin for advanced chart controls
4. Add MediaRecorder API for real-time audio processing
5. Connect to FastAPI backend with proper error handling
6. Implement routing for survey page integration