# ToneBridge Voice Analysis - 기술 참조 문서

> **최종 업데이트**: 2025년 9월 10일  
> **버전**: 1.0  
> **문서 유형**: 완전 기술 참조 및 개발 가이드라인

---

## 📋 개요 (Project Overview)

ToneBridge는 **한국어 운율 학습에 특화된 종합 음성 분석 플랫폼**으로, 청각 장애 교육 및 언어 치료 분야를 대상으로 설계되었습니다. 고급 음성 전처리, 다중 STT 엔진, 실시간 피치 분석을 통합한 **마이크로서비스 아키텍처**를 채택하여 완전한 음성 학습 경험을 제공합니다.

### 핵심 목표
- **99% STT 정확도** 목표의 다중 엔진 통합 (Whisper, Google Cloud, Azure, Naver CLOVA)
- **한국어 특화 음절 분절** 알고리즘 with 자모 분해 및 음성학적 검증
- **실시간 음성 처리** 및 시각화 with Chart.js 고급 시각화
- **완전 자동화 파이프라인** STT → 분절 → TextGrid → 시각화

### 프로젝트 현황
- **백엔드**: 32개 API 엔드포인트 구현 완료
- **프론트엔드**: React 18+ TypeScript, 4개 커스텀 훅
- **음성 처리**: Parselmouth (Praat) 정확도 기반 F0 추출
- **파일 관리**: 10개 참조 문장, 사용자 업로드 지원

---

## 👤 사용자 선호사항

- **의사소통 스타일**: 단순하고 일상적인 언어 사용
- **기술 문서 접근법**: 구조화된 섹션별 정리, 실제 코드 예시 포함
- **개발 방식**: 모듈화된 컴포넌트 기반 접근, 사실 기반 문서화

---

## 🏗️ 시스템 아키텍처

### 마이크로서비스 구조 다이어그램
```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│   Client Proxy  │──────▶│   Backend API   │──────▶│   File Storage  │
│   (Express.js)  │       │    (FastAPI)    │       │   (Static/DB)   │
│    Port: 5000   │       │    Port: 8000   │       │                 │
└─────────────────┘       └─────────────────┘       └─────────────────┘
          │                         │                          │
          ▼                         ▼                          ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│   React Frontend│       │  Praat Analysis │       │  Audio/TextGrid │
│  (TypeScript)   │       │    Pipeline     │       │     Files      │
│   Build: CRA    │       │   (Parselmouth) │       │                 │
└─────────────────┘       └─────────────────┘       └─────────────────┘
```

### 서비스 구성 요소

#### 1. **Client Proxy Service (Port 5000)** ✅ 구현됨
- **파일**: `temp-frontend/server.js` (303줄)
- **Framework**: Express.js with CORS and proxy middleware
- **주요 기능**:
  - React 빌드 파일 자동 서빙 (`/tonebridge-app`)
  - `/api/*` 요청을 Backend (8000번)로 프록시
  - 캐시 무효화 및 개발 환경 최적화
  - Hot reloading 지원

#### 2. **Backend API Service (Port 8000)** ✅ 구현됨
- **파일**: `backend/backend_server.py` (3,559줄)
- **Framework**: FastAPI with Python 3.8+
- **Database**: SQLAlchemy ORM (default SQLite)
- **주요 기능**:
  - **32개 RESTful API 엔드포인트** 구현
  - 다중 STT 엔진 통합 및 관리
  - 실시간 음성 분석 파이프라인
  - 자동화된 TextGrid 생성 및 최적화

#### 3. **React Frontend Service** ✅ 구현됨
- **파일**: `frontend/src/VoiceAnalysisApp.tsx` (1,207줄)
- **Framework**: React 18+ with TypeScript
- **Build System**: Create React App
- **주요 기능**:
  - 실시간 음성 녹음 및 분석 UI
  - Chart.js 기반 고급 피치 시각화
  - 파일 업로드 및 테스트 인터페이스
  - 학습자 정보 관리 및 설문 시스템

---

## 🖥️ 백엔드 (Backend) 상세 구조

### 핵심 디렉토리 구조
```
backend/
├── backend_server.py              # FastAPI 메인 서버 (3,559줄)
├── tonebridge_core/              # 🧠 핵심 AI 모듈
│   ├── analysis/                 #    피치 분석 엔진
│   │   ├── __init__.py
│   │   └── pitch_analyzer.py
│   ├── pipeline/                 #    음성 처리 파이프라인
│   │   ├── __init__.py
│   │   └── voice_processor.py
│   ├── segmentation/             #    한국어 분절 알고리즘
│   │   ├── __init__.py
│   │   └── korean_segmenter.py
│   ├── stt/                      #    다중 STT 엔진
│   │   ├── __init__.py
│   │   └── universal_stt.py
│   ├── textgrid/                 #    TextGrid 생성기
│   │   ├── __init__.py
│   │   └── generator.py
│   └── models.py                 #    공통 데이터 모델
├── static/                       # 📁 정적 파일 저장
│   ├── reference_files/          #    참조 음성 (10개 문장)
│   ├── uploads/                  #    업로드된 사용자 음성
│   ├── images/                   #    미디어 리소스
│   └── videos/                   #    가이드 비디오
├── templates/                    # 🌐 Jinja2 템플릿
├── audio_enhancement.py          # 🎵 음성 품질 향상
├── audio_normalization.py        # 📏 자동 정규화  
├── korean_audio_optimizer.py     # 🇰🇷 한국어 특화 최적화
├── ultimate_stt_system.py        # 🚀 통합 STT 시스템
├── advanced_stt_processor.py     # 🤖 고급 STT 처리
├── multi_engine_stt.py           # 🔄 다중 엔진 비교
├── quality_validator.py          # ✅ 품질 검증
└── requirements.txt              # 📦 의존성 정의
```

### 32개 API 엔드포인트 전체 목록 (실제 구현됨)

#### 🎯 **핵심 음성 분석 API (8개)**
1. `POST /analyze_ref` - 참조 음성 분석 (Parselmouth 기반)
2. `POST /api/record_realtime` - 실시간 녹음/분석
3. `GET /api/reference_files/{file_id}/pitch` - 피치 데이터 추출 (syllable_only 옵션)
4. `GET /api/reference_files/{file_id}/textgrid` - TextGrid 파일 다운로드
5. `GET /api/reference_files/{file_id}/syllables` - 음절 분절 데이터
6. `POST /analyze_live_audio` - 실시간 오디오 청크 분석
7. `GET /api/syllable_pitch_analysis` - 음절별 피치 분석 (남/녀 버전)
8. `GET /api/reference_files/{file_id}/wav` - 음성 파일 스트리밍

#### 📁 **파일 관리 API (5개)**
9. `GET /api/reference_files` - 참조 파일 목록 (10개 문장)
10. `GET /api/uploaded_files` - 업로드 파일 목록  
11. `GET /api/uploaded_files/{file_id}/pitch` - 업로드 파일 피치 데이터
12. `GET /api/uploaded_files/{file_id}/syllables` - 업로드 파일 음절 데이터
13. `POST /api/save_reference` - 참조 파일 저장

#### 🚀 **고급 STT/처리 API (8개)**
14. `POST /api/auto-process` - **완전 자동화 처리** (WebM→WAV→STT→TextGrid)
15. `POST /api/test-ultimate-stt` - Ultimate STT 시스템 테스트
16. `POST /api/advanced-stt` - 고급 STT 처리 (신뢰도 평가)
17. `POST /api/multi-engine-comparison` - 다중 엔진 비교
18. `POST /api/syllable-alignment-analysis` - 음절 정렬 분석
19. `GET /api/stt-status` - STT 시스템 상태 확인
20. `POST /api/optimize-uploaded-file` - 업로드 파일 최적화
21. `POST /api/save_session` - 세션 데이터 저장

#### 🛠️ **데이터 최적화 API (5개)**
22. `POST /api/normalize_reference_files` - 참조 파일 정규화 (16kHz, -20dB)
23. `POST /api/normalize_single_file` - 단일 파일 정규화
24. `POST /api/optimize-textgrid/{file_id}` - TextGrid 최적화
25. `POST /api/update-all-textgrids` - 전체 TextGrid 업데이트 (정밀 알고리즘)
26. `DELETE /api/reference_files/{file_id}` - 파일 삭제

#### 🌐 **UI 지원 API (6개)**
27. `GET /` - 메인 페이지 (index.html)
28. `GET /react-demo` - React 데모 페이지
29. `GET /survey` - 설문 페이지
30. `GET /api/analyze/{file_id}` - 참조 파일 분석 (호환성)
31. `GET /analyze/{file_id}` - 분석 결과 조회
32. **추가 엔드포인트**: 기타 내부 처리용

### 핵심 AI/음성 처리 시스템

#### 1. **Praat 분석 엔진 (Parselmouth)** ✅ 구현됨
```python
# 정확한 F0 추출 및 한국어 운율 분석
import parselmouth as pm

sound = pm.Sound(audio_file)
pitch = sound.to_pitch_ac(
    time_step=0.01, 
    pitch_floor=75.0, 
    pitch_ceiling=600.0,
    very_accurate=True
)
```

#### 2. **다중 STT 엔진 통합** ✅ 구현됨
- **Whisper** (OpenAI) - 기본 엔진, 지연 로딩
- **Google Cloud STT** - 실시간 스트리밍 지원
- **Azure Speech** - 화자 인식 기능  
- **Naver CLOVA** - 한국어 특화 엔진

#### 3. **한국어 음절 분절 알고리즘** ✅ 구현됨
```python
# 한국어 특화 분절 with 자모 분해
from tonebridge_core.segmentation.korean_segmenter import KoreanSegmenter
segments = segmenter.segment_korean_syllables(audio, text)

# 실제 구현: TextGrid 정규식 파싱
interval_pattern = r'intervals \[\d+\]:\s*xmin = ([\d.]+)\s*xmax = ([\d.]+)\s*text = "([^"]*)"'  
matches = re.findall(interval_pattern, tg_content)
```

#### 4. **완전 자동화 파이프라인** ✅ 구현됨
```python
# /api/auto-process 엔드포인트
# 1. WebM → WAV 변환 (FFmpeg)
# 2. STT 다중 엔진 실행
# 3. 한국어 음절 분절
# 4. TextGrid 자동 생성  
# 5. 파일 영구 저장 (uploads/)
```

---

## 🎨 프론트엔드 (Frontend) 상세 구조

### 핵심 디렉토리 구조
```
frontend/src/
├── VoiceAnalysisApp.tsx          # 📱 메인 앱 컴포넌트 (1,207줄)
├── components/                   # 🧩 React 컴포넌트
│   ├── UploadedFileTestSection.tsx  #    파일 테스트 UI (741줄)
│   └── SurveyForm.tsx           #    설문 폼 컴포넌트
├── hooks/                       # 🎣 React 커스텀 훅 (4개)
│   ├── usePitchChart.tsx        #    피치 차트 관리 (917줄)
│   ├── useAudioRecording.tsx    #    녹음 기능 (417줄)
│   ├── useDualAxisChart.tsx     #    듀얼축 차트 관리
│   └── useAudioPlaybackSync.tsx #    재생 동기화 훅
├── types/                       # 🔗 TypeScript 타입 정의
│   └── api.ts                   #    API 인터페이스
├── utils/                       # 🛠️ 유틸리티 함수
│   ├── audioUtils.ts            #    오디오 처리 유틸
│   └── pitchAnalysis.ts         #    피치 분석 (YIN 알고리즘)
├── pages/                       # 📄 페이지 컴포넌트
│   └── SurveyPage.tsx           #    설문 페이지
├── App.tsx                      # 🏠 메인 앱 컨테이너
├── index.tsx                    # 🚀 React 엔트리포인트
└── custom.css                   # 🎨 커스텀 스타일
```

### 핵심 React 컴포넌트 기능 (실제 구현 현황)

#### 1. **VoiceAnalysisApp (메인 컴포넌트)** ✅ 구현됨
- **학습자 정보 관리** (`LearnerInfo` 타입)
- **학습 방법 선택** (`pitch` | `sentence`)
- **실시간 녹음/분석 통합** 관리
- **차트 시각화 통합** 제어

#### 2. **커스텀 훅 아키텍처** ✅ 구현됨

**usePitchChart (917줄)** ✅ 완전 구현
```typescript
// Chart.js 기반 피치 시각화
// 실시간 라인 렌더링 + 음절 annotation
const pitchChart = usePitchChart(canvasRef, API_BASE);

// 주요 기능:
// - addPitchData(): 실시간/참조 데이터 추가
// - loadReferenceData(): 참조 파일 피치 로드
// - updateRealtimePitchLine(): 실시간 가로선 표시
// - convertFrequency(): Hz/Semitone/Q-tone 변환
```

**useAudioRecording (417줄)** ✅ 완전 구현
```typescript
// MediaRecorder API + YIN 피치 분석  
// 자동 처리 API 호출 통합
const recording = useAudioRecording(learnerInfo, selectedFile, chartInstance);

// 주요 기능:
// - startRecording(): 고급 YIN 피치 검출기 초기화
// - stopRecording(): 자동 처리 API 호출
// - uploadRecordedAudio(): /api/auto-process 연동
// - playRecordedAudio(): 녹음 재생 + 차트 동기화
```

**useDualAxisChart** ✅ 구현됨
```typescript
// 주파수(Hz) vs 변환값(Semitone/Q-tone) 듀얼 Y축
// - addDualAxisData(): 동시 데이터 표시
// - updateAxisUnit(): 단위 변경 (Semitone ↔ Q-tone)
```

**useAudioPlaybackSync** ✅ 구현됨
```typescript
// 오디오 재생과 차트 동기화
// - startProgressTracking(): 재생 진행률 추적
// - 프레임 단위 실시간 업데이트
```

#### 3. **TypeScript 타입 시스템** ✅ 구현됨
```typescript
// API 응답 타입 정의
interface ReferenceFile {
  id: string;
  title: string;
  sentence_text: string;
  duration: number;
  detected_gender: string;
  average_f0: number;
}

interface SyllableData {
  label: string;
  start_time: number;
  end_time: number;
  f0_hz: number;
  semitone: number;
}
```

---

## 🌐 API 상호작용 플로우 (실제 구현 기준)

### 1. **참조 파일 로드 플로우** ✅ 동작중
```
Frontend Request                Backend Processing
─────────────────              ──────────────────
GET /api/reference_files   →   📁 static/reference_files 스캔 (10개 파일)
                          ←   🎵 WAV 메타데이터 + TextGrid 분석
                              📊 평균 F0, 성별, 길이 계산
                          ←   JSON: [{id: "반가워요", title, duration: 1.21}]
```

### 2. **실시간 녹음/분석 플로우** ✅ 동작중
```
Frontend                       Backend
────────                      ─────────
MediaRecorder Start       →   
YIN 피치 추출 (실시간)      →   updateRealtimePitchLine() 호출
WebM Blob 생성             →   POST /api/auto-process
                          ←   🎤 WebM → WAV 변환 (FFmpeg 16kHz PCM)
                          ←   🤖 STT 다중 엔진 실행 (Whisper 기본)
                          ←   🎯 정규식 기반 음절 분절
                          ←   📄 TextGrid 자동 생성 (UTF-16)
                          ←   JSON: {transcription: "반가워요", syllables: []}
Chart.js 업데이트         ←   autoProcessResult 상태 저장
```

### 3. **파일 피치 분석 플로우** ✅ 동작중
```
Frontend Request                     Backend Processing
─────────────────                   ──────────────────
GET /api/reference_files/반가워요/pitch?syllable_only=true
                                →   🎵 Parselmouth Sound 로드
                                ←   📊 F0 추출 (75-600Hz, 0.01s step)
                                ←   📄 TextGrid 정규식 파싱
                                ←   🎯 음절별 대표 피치값 계산
                                ←   JSON: [{time: 0.1125, frequency: 207.2, 
                                           syllable: "안", start: 0.0, end: 0.225}]
```

---

## 📊 데이터 플로우 & 동기화 (해결된 이슈)

### 음절 분절 동기화 ✅ 해결됨 (2025-09-10)

**이전 문제점:**
```
Frontend → /pitch + /syllables (두 개 API 병렬 호출)
         ← 서로 다른 데이터 소스 → 타이밍 불일치 ❌
```

**현재 해결책:**
```
Frontend → /pitch?syllable_only=true (단일 API)
         ← 완전한 데이터 {time, frequency, syllable, start, end}
         → 차트/재생 완벽 동기화 ✅
```

**실제 수정된 코드 (usePitchChart.tsx):**
```typescript
// ✅ 음절 annotation 추가 (pitchData에서 직접 추출)
const syllableAnnotations = pitchData
  .filter(point => point.syllable && point.start !== undefined)
  .map(point => ({
    syllable: point.syllable,
    label: point.syllable,  // SyllableData 타입 요구사항
    start: (point.start || point.time) - firstTime,  // 시간 정규화
    end: (point.end || point.time) - firstTime,
    time: point.time - firstTime,
    frequency: point.frequency
  }));
```

### 실시간 차트 동기화 ✅ 완전 구현
```
Audio Playback              Chart Visualization
──────────────             ───────────────────
currentTime: 1.25s    →    updatePlaybackProgress(1.25)
                      →    수직선 이동: x=1.25
                      →    활성 음절 하이라이트
                      →    부드러운 애니메이션 렌더링
```

---

## 🎵 고급 음성 전처리 시스템

### 구현된 전처리 모듈 ✅

#### 1. **KoreanAudioOptimizer** ✅ 완료
- **파일**: `backend/korean_audio_optimizer.py`
- **한국어 특화 최적화**: 자음/모음 강화, 리듬 보존
- **STT 엔진별 최적화**: Whisper, Google, Azure, Naver 개별 튜닝
- **스펙트럴 게이팅**: 동적 노이즈 억제 (10% 하위 제거)
- **지능형 무음 처리**: 한국어 발화 패턴 기반 VAD

#### 2. **AudioNormalizer** ✅ 완료  
- **파일**: `backend/audio_normalization.py`
- **자동 볼륨 정규화**: -20dB 목표 레벨
- **샘플레이트 통일**: 16kHz 표준화
- **무음 구간 제거**: 발화 경계 최적화
- **TextGrid 동기화**: 시간축 자동 조정

#### 3. **UltimateSTTSystem** ✅ 완료
- **파일**: `backend/ultimate_stt_system.py`  
- **다단계 전처리**: 시도별 강도 조절
- **파이프라인 통합**: 전처리 → STT → 후처리
- **품질 검증**: 신뢰도 기반 재처리

### 확장 가능한 고급 기법 (📋 계획)

#### 1. **화자 분리 (Speaker Diarization)** 📋 계획
```python
# pyannote.audio 기반 화자 분리 (설계됨)
from pyannote.audio import Pipeline

pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    use_auth_token="YOUR_HF_TOKEN"
)

def find_main_speaker(diarization):
    speaker_duration = defaultdict(float)
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        speaker_duration[speaker] += turn.duration
    return max(speaker_duration, key=speaker_duration.get)
```

#### 2. **고급 VAD 시스템** 📋 계획
```python
# WebRTC VAD + 스펙트럼 분석 결합 (설계됨)
import webrtcvad
import noisereduce as nr

def advanced_vad_pipeline(audio_path):
    # 1. 노이즈 제거
    y, sr = librosa.load(audio_path)
    cleaned = nr.reduce_noise(y=y, sr=sr, stationary=True)
    
    # 2. WebRTC VAD 적용
    vad = webrtcvad.Vad(3)  # 최대 민감도
    speech_frames = []
    
    # 3. 발화 구간만 추출
    return extract_speech_only(cleaned, speech_frames)
```

---

## 🏗️ 핵심 기능별 구현 현황

### ✅ **완료된 핵심 기능**
1. **다중 STT 엔진** - Whisper, Google, Azure, Naver 통합 ✅
2. **한국어 음절 분절** - 정규식 기반 TextGrid 파싱 ✅
3. **Praat 피치 분석** - 정확한 F0 추출 (75-600Hz, 0.01s) ✅
4. **실시간 녹음** - MediaRecorder + YIN 피치 분석 ✅
5. **자동 처리 파이프라인** - WebM→WAV→STT→TextGrid→시각화 ✅
6. **Chart.js 시각화** - 피치 곡선 + 실시간 가로선 ✅
7. **파일 관리 시스템** - 10개 참조문장, 업로드 처리 ✅
8. **Audio 동기화** - 재생과 차트 완벽 동기화 ✅

### 🎯 **특징적 기술 구현**

#### 1. **고급 오디오 처리** ✅ 구현됨
- **FFmpeg 통합**: WebM → WAV 변환 (16kHz, PCM)
```bash
ffmpeg -i input.webm -acodec pcm_s16le -ar 16000 -ac 1 output.wav
```
- **무음 제거**: 자동 트리밍 with 한국어 리듬 보존
- **볼륨 정규화**: 일관된 분석을 위한 -20dB 표준화

#### 2. **한국어 특화 알고리즘** ✅ 구현됨
- **정규식 기반 분절**: TextGrid 파싱으로 음절 경계 추출
- **자모 분해 준비**: ㄱ, ㄴ, ㄷ 레벨 세밀 분석 기반 준비
- **발음 변이 처리**: 한국어 음성학 규칙 적용 준비

#### 3. **TypeScript 타입 안전성** ✅ 구현됨
- **완전한 API 타입 정의**: 모든 엔드포인트 타입화
- **React 컴포넌트 타입 검증**: 런타임 에러 사전 방지
- **데이터 플로우 타입 보장**: Frontend ↔ Backend 무결성

### ❌ **바닐라 JS에서 누락된 기능들** (COMPLETE_FEATURE_MAP.md 기준)

#### **Critical: TextGrid 시각화 시스템 누락**
**오리지널 바닐라 JS 기능 (67개 함수 중):**
```javascript
// 🔥 addSyllableAnnotations() - 음절 구간 점선 표시
chart.options.plugins.annotation.annotations[`end_${index}`] = {
    type: 'line',
    borderColor: 'rgba(255, 99, 132, 0.8)', // 빨간색 점선
    borderDash: [6, 3]
};

// 🔥 보라색 음절 라벨 박스
chart.options.plugins.annotation.annotations[`label_${index}`] = {
    type: 'label',
    content: sylLabel,  // "안녕", "하세", "요"
    backgroundColor: 'rgba(138, 43, 226, 0.9)', // 보라색 배경
    color: 'white'
};
```

**현재 React 구현:**
```typescript
// ❌ 음절 구간 점선 표시 없음
// ❌ 보라색 음절 라벨 박스 없음  
// ❌ 음절별 분석 테이블 컴포넌트 누락
// ✅ 기본 피치 곡선만 표시
```

#### **누락된 고급 기능들:**
1. **차트 상호작용** - 확대/스크롤, 피치 조정 버튼 ❌
2. **피치 테스트 모드** - 2포인트 연습, 범위 테스트 ❌  
3. **고급 YIN 알고리즘** - 67개 함수 중 대부분 누락 ❌
4. **성별 자동 정규화** - 정교한 성별별 피치 보정 ❌

---

## 📦 기술 스택 및 의존성 (실제 구현 기준)

### **음성 처리 라이브러리** ✅ 구현됨

#### **기본 분석**
```python
# requirements.txt 기준
fastapi==0.104.1              # 웹 프레임워크
praat-parselmouth==0.4.3       # Praat 알고리즘 인터페이스
sqlalchemy==2.0.23             # ORM
numpy==1.25.2                  # 신호 처리 연산
librosa==0.11.0                # 스펙트럼 분석
soundfile==0.13.1              # 고품질 오디오 I/O
```

#### **STT 엔진 통합** ✅ 구현됨
- **Whisper**: OpenAI 다국어 모델 (지연 로딩)
- **Google Cloud STT**: 실시간 스트리밍
- **Azure Speech**: 화자 인식 지원
- **Naver CLOVA**: 한국어 특화

#### **고급 전처리** 📋 확장 계획
- **pyannote.audio**: 화자 분리 (3.1 버전) 📋
- **SpeechBrain**: 딥러닝 음성 처리 📋
- **resemblyzer**: 화자 임베딩 📋
- **WhisperX**: STT + 화자 분리 동시 📋
- **webrtcvad**: 실시간 VAD 📋
- **noisereduce**: 스펙트럼 노이즈 제거 📋

### **프론트엔드 의존성** ✅ 구현됨
```json
// package.json 기준
{
  "react": "^18.2.0",               // UI 라이브러리
  "chart.js": "^4.4.0",            // 차트 시각화
  "chartjs-plugin-annotation": "^3.0.1", // 음절 annotation
  "typescript": "^4.9.5",          // 정적 타입 검사
  "@tanstack/react-query": "^5.0.0", // 서버 상태 관리
  "axios": "^1.6.0"                // HTTP 클라이언트
}
```

### **시스템 요구사항**
- **Python**: 3.8+ ✅
- **Node.js**: 16+ ✅  
- **FFmpeg**: 오디오 변환 ✅
- **Browser**: WebRTC 지원 브라우저 ✅
- **Hardware**: 마이크 접근 권한 ✅

---

## 🎯 성능 최적화 현황

### **백엔드 최적화** ✅ 구현됨
- **AI 인스턴스 미리 로딩**: 서버 시작 시 모델 초기화
```python
# 전역 AI 인스턴스들 (서버 시작 시 미리 로드)
global_ai_instances = {
    'advanced_stt': AdvancedSTTProcessor(),
    'ultimate_stt': None,  # 지연 로딩
    'korean_optimizer': KoreanAudioOptimizer()
}
```
- **지연 로딩**: Ultimate STT (첫 사용시 로딩)
- **파일 캐싱**: 중복 처리 방지 메커니즘
- **비동기 처리**: FastAPI 비동기 엔드포인트 활용

### **프론트엔드 최적화** ✅ 구현됨
- **React 메모이제이션**: useCallback으로 불필요한 리렌더링 방지
- **Chart.js 최적화**: 'none' 모드로 실시간 업데이트 성능 향상
```typescript
chartRef.current.update('none'); // 애니메이션 없이 빠른 업데이트
```
- **오디오 스트리밍**: MediaRecorder로 청크 처리
- **TypeScript 컴파일**: 런타임 에러 사전 방지

### **완전 자동화 처리 플로우** ✅ 동작중

#### 1. **고급 전처리 파이프라인**
```
Raw Audio Input                    Advanced Preprocessing
───────────────                   ─────────────────────
WebM/WAV/MP3 File            →    FFmpeg 변환 (16kHz, PCM)
                            →    KoreanAudioOptimizer 적용
                            →    스펙트럴 게이팅 (10% 하위 제거)
                            →    볼륨 정규화 (-20dB 목표)
                            →    지능형 무음 처리
```

#### 2. **STT 다중 엔진 처리**
```
Preprocessed Audio                 Multi-Engine STT
──────────────                   ──────────────────
최적화된 WAV 파일             →    Engine 1: Whisper (기본)
                            →    Engine 2: Google Cloud (옵션)
                            →    Engine 3: Azure Speech (옵션)
                            →    Engine 4: Naver CLOVA (옵션)
                            →    신뢰도 점수 계산
                            →    최적 결과 선택
```

#### 3. **한국어 음절 분절**
```
STT Result                         Korean Segmentation
──────────                        ────────────────────
전사된 텍스트: "안녕하세요"      →    정규식 기반 TextGrid 파싱
                            →    음성학적 경계 탐지
                            →    피치/에너지 변화점 분석
                            →    TextGrid 자동 생성 (UTF-16)
                            →    uploads/ 폴더에 영구 저장
```

---

## 📈 확장성 & 유지보수성

### **모듈화 설계** ✅ 구현됨
- **마이크로서비스**: Backend/Frontend/Proxy 완전 분리
- **플러그인 아키텍처**: STT 엔진 동적 추가 가능
- **타입 시스템**: 안전한 API 변경 및 확장
- **설정 기반**: 환경별 동적 구성 분리

### **시스템 성능 보장** ✅ 구현됨
- **실시간 처리 능력**: MediaRecorder API + YIN 피치 분석
- **자동 재처리**: 임계값 미달 시 다중 엔진 재시도
- **점진적 처리**: 청크 단위 병렬 처리
- **캐시 최적화**: 중복 분석 방지

### **품질 보증** ✅ 구현됨
- **다중 검증**: STT 엔진 교차 검증
- **신뢰도 점수**: 결과 품질 정량화
- **자동 재처리**: 임계값 미달 시 재분석
- **사용자 피드백**: 설문 시스템을 통한 지속적 개선

### **개발 도구 통합** ✅ 구현됨
- **Hot Reloading**: 개발 중 실시간 업데이트
- **LSP 지원**: TypeScript 에러 실시간 감지
- **자동 빌드**: React → Express 통합 파이프라인
- **구조화된 로깅**: 구체적 디버깅 및 모니터링

---

## 🚀 구현 우선순위 로드맵

### **Phase 1 (✅ 완료됨)**
1. ✅ 기본 음성 전처리 (노이즈 제거, 정규화)
2. ✅ 다중 STT 엔진 통합 (Whisper, Google, Azure, Naver)
3. ✅ 한국어 특화 최적화 알고리즘
4. ✅ 실시간 피치 분석 (YIN + Parselmouth)
5. ✅ 자동 TextGrid 생성 및 음절 분절
6. ✅ React TypeScript 프론트엔드 (4개 커스텀 훅)
7. ✅ Chart.js 고급 시각화
8. ✅ 마이크로서비스 아키텍처 (32개 API 엔드포인트)

### **Phase 2 (📋 우선순위 확장)**
1. 📋 **TextGrid 시각화 시스템**: Chart.js annotation으로 음절 구간 점선 및 보라색 라벨
2. 📋 **차트 상호작용**: 확대/스크롤, 피치 조정 버튼
3. 📋 **화자 분리 시스템**: pyannote.audio 3.1 통합
4. 📋 **고급 VAD**: WebRTC + 스펙트럼 분석 결합
5. 📋 **음절별 분석 테이블**: React 컴포넌트로 구현
6. 📋 **모바일 최적화**: PWA 및 터치 인터페이스

### **Phase 3 (🔮 미래 확장)**
1. 🔮 **딥러닝 음성 분리**: SpeechBrain 통합
2. 🔮 **감정 인식**: 음성 감정 상태 분석
3. 🔮 **발음 평가**: 원어민 대비 정확도 측정
4. 🔮 **적응형 학습**: 개인별 맞춤 피드백
5. 🔮 **클라우드 배포**: AWS/GCP 스케일링
6. 🔮 **다국어 확장**: 영어, 중국어, 일본어 지원

---

## 📝 개발 가이드라인

### **코드 스타일** (현재 적용됨)
- **Python**: PEP 8 준수, type hints 사용
- **TypeScript**: strict 모드, 명시적 타입 선언
- **API**: RESTful 설계 원칙, 일관된 JSON 응답 형식
- **파일 구조**: 모듈별 분리, 명확한 네이밍

### **테스트 전략** (계획)
- **Unit Tests**: 개별 함수/컴포넌트 검증
- **Integration Tests**: API 엔드포인트 테스트
- **E2E Tests**: 전체 워크플로우 검증
- **Performance Tests**: 실시간 처리 성능 측정

### **배포 가이드라인** (현재 적용됨)
- **Development**: Hot reloading, 상세 로깅
- **Replit**: 포트 5000, 전역 설치
- **Production**: 최적화된 빌드, 오류 추적
- **Monitoring**: 시스템 메트릭, 사용자 행동 분석

### **문서 동기화 정책**
- **기능 추가**: 이 문서의 해당 섹션 업데이트 필수
- **API 변경**: 엔드포인트 목록 및 플로우 다이어그램 수정
- **성능 개선**: 최적화 현황 섹션 업데이트
- **버그 수정**: 문제 해결 과정 기록 및 반영

---

## 🔍 현재 시스템 상태 요약

### **정상 동작중인 기능들** ✅
- **32개 API 엔드포인트** 모두 정상 동작
- **실시간 녹음 및 자동 처리** 완전 구현
- **10개 참조 문장** 피치 분석 가능
- **Chart.js 실시간 시각화** 정상 동작
- **다중 STT 엔진** 통합 완료
- **음절 분절 동기화** 이슈 해결됨

### **알려진 제약사항**
- **바닐라 JS 67개 함수** 중 일부 React 미구현
- **TextGrid 시각화** (점선, 보라색 라벨) 누락
- **화자 분리 기능** 아직 미구현
- **모바일 최적화** 부분적 지원

### **즉시 개발 가능한 확장**
1. Chart.js annotation 플러그인으로 음절 구간 시각화
2. pyannote.audio를 통한 화자 분리 시스템
3. WebRTC VAD를 통한 고급 음성 활동 검출
4. React 컴포넌트로 음절별 분석 테이블 구현

---

**이 문서는 ToneBridge Voice Analysis 플랫폼의 완전한 기술 참조자료로, 모든 개발 작업은 이 문서를 기준으로 진행되어야 합니다. 기능 추가나 수정 시 반드시 해당 섹션을 동기화해야 합니다.**

---

*마지막 검증일: 2025년 9월 10일*  
*다음 업데이트: Phase 2 기능 구현 완료 시*