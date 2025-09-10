# ToneBridge Voice Analysis Microservices

## Overview
ToneBridge is a Korean prosody learning platform designed to assist users, particularly in deaf education and language therapy, in analyzing and improving Korean speech patterns. It utilizes a microservices architecture for voice analysis and pronunciation training, offering real-time audio processing and visualization. The platform integrates authentic Praat pitch extraction algorithms via Parselmouth with a modern React frontend, providing interactive user experiences. Its modular design allows for independent deployment and integration, supporting both language therapists and general users, with mechanisms for gathering feedback for continuous improvement.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### UI/UX Decisions
- **Frontend**: React 18+ with TypeScript for interactive interfaces.
- **Visualizations**: Chart.js with annotation plugins for real-time audio data.
- **Styling**: Bootstrap 5.3+ and Pretendard Korean font for optimal readability and responsive design.
- **Color Schemes**: Custom Bootstrap integration.
- **Animations**: CSS animations (`shake`, `bounce`) for mobile warnings.
- **Gradients**: Linear gradients for CTAs and warning sections.
- **Font**: Pretendard Korean font for optimal readability.

### Technical Implementations
- **Backend API Service (Port 8000)**:
    - **Framework**: FastAPI with Python 3.8+.
    - **Audio Processing**: Parselmouth (Praat Python) for pitch extraction and prosodic analysis.
    - **API Design**: RESTful endpoints supporting WAV and TextGrid files.
    - **Database**: SQLAlchemy ORM, configurable (default SQLite).
    - **Location**: `backend/` directory.
    - **Advanced Voice Processing**: Includes modules for multi-engine STT (Whisper, Google Cloud, Azure, Naver CLOVA) with reliability scoring, Korean syllable alignment, and jamo decomposition. Features automated audio processing, advanced STT, engine comparison, and syllable alignment analysis.
- **Frontend Service**:
    - **Framework**: React 18+ with TypeScript.
    - **Build System**: Create React App.
    - **API Integration**: Configurable backend API endpoint.
    - **Location**: `frontend/` directory.
- **Client Proxy Service (Port 5000)**:
    - **Framework**: Express.js with CORS and proxy middleware.
    - **Purpose**: Demonstration client, proxies requests to the backend.
    - **Location**: `temp-frontend/` directory.
- **Data Storage**:
    - **Database**: SQLAlchemy ORM (default SQLite).
    - **Models**: User, analysis sessions, surveys, reference files.
    - **File Storage**: Local filesystem in `static/uploads`.
- **Authentication**: Flask-Login based, with password hashing and database-backed sessions. Public access to demo features and reference files.
- **Audio Analysis Pipeline**:
    - Real-time F0 analysis, gender detection, Korean syllable counting.
    - Supports WAV audio and TextGrid annotations.
    - Automated TextGrid optimization using energy and pitch variation analysis, silent interval removal, and adaptive syllable boundary optimization for enhanced phonological accuracy.
- **Deployment**: Standalone design with virtual environments, cross-platform support (Linux, macOS, Windows), Replit compatibility, and hot-reloading for development.

### Feature Specifications
- **Core Features (from `index.html` as target for React)**:
    - Personalized Coaching Survey CTA.
    - Mobile Landscape Orientation Guide.
    - Learner Information Input (name, gender, age group).
    - Learning Method Selection (pitch vs. reference intonation).
    - Practice Sentence Selection & Video Guide.
    - Real-time Analysis Chart with controls (zoom, scroll, key adjustment).
    - Syllable Analysis Table with prosodic measurements.
    - Gender Selection Modal for voice calibration.
- **Technical Implementations for React**:
    - Utilizes `MediaRecorder API` for audio capture.
    - `FormData` handling for file uploads.
    - `Fetch API` for backend integration.
    - `Chart.js` for pitch visualization.
    - Comprehensive error handling.
    - Syllable annotation visualization on charts (dotted lines, purple labels).
    - Chart controls for pitch adjustment, zoom, scroll, and reset.
    - Integration of multi-engine STT and Korean syllable alignment for improved accuracy.
    - **Performance Optimization**: Conditional preprocessing to avoid redundant processing on file selection.
    - **Smart File Management**: Processing status display (✅ processed, ⏳ pending) and manual reprocessing option.

## External Dependencies

### Core Python Libraries
- **FastAPI**: Web framework.
- **Parselmouth**: Praat interface for speech analysis.
- **SQLAlchemy**: Database ORM.
- **NumPy**: Numerical computing.
- **Uvicorn**: ASGI server.

### Frontend Dependencies
- **React**: UI library.
- **Chart.js**: Charting library for visualization.
- **Axios**: HTTP client.
- **React Query**: Server state management.
- **Bootstrap**: CSS framework.

### Development Tools
- **Concurrently**: For running multiple scripts.
- **TypeScript**: Static typing for JavaScript.
- **React Scripts**: Build toolchain.
- **Create React App**: Project bootstrapping.

### External Services
- **Google Analytics**: User behavior tracking (ID: G-56D78RCESE).
- **Naver Forms**: External survey collection.
- **CDN Resources**: Bootstrap, Font Awesome, Chart.js, Pretendard font.

### System Requirements
- **Python**: 3.8+.
- **Node.js**: 16+.
- **Browser Compatibility**: Modern browsers with WebRTC.
- **Audio Hardware**: Microphone access.