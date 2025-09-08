# ToneBridge Voice Analysis Demo - 완전 구현 가이드

## 📁 프로젝트 구조 개요

```
voice-analysis-demo/
├── backend_server.py          # FastAPI 백엔드 서버 (1765줄)
├── models.py                  # SQLAlchemy 데이터베이스 모델 (51줄)
├── templates/                 # Jinja2 HTML 템플릿
│   ├── base.html             # 기본 레이아웃 (122줄)
│   └── index.html            # 메인 페이지 (467줄)
├── static/                   # 정적 파일들
│   ├── css/custom.css        # 사용자 정의 스타일 (714줄)
│   └── js/audio-analysis.js  # 메인 JavaScript (5188줄)
├── react-app/                # React TypeScript 버전
│   └── src/
│       ├── VoiceAnalysisApp.tsx  # 메인 React 컴포넌트 (451줄)
│       └── hooks/                # 커스텀 훅들
└── reference_files/          # 참조 음성 파일들 (WAV + TextGrid)
```

## 🎯 핵심 기능별 상세 구현 분석

### 1. WAV 파일 처리 시스템

#### 1.1 백엔드 WAV 처리 (backend_server.py)
**파일:** `voice-analysis-demo/backend_server.py`
**라인:** 965-1050

```python
# WAV 파일 업로드 엔드포인트
@app.post("/analyze_ref", response_model=RefAnalysis)
async def analyze_ref(
    wav: UploadFile = File(..., description="Reference WAV"),
    textgrid: UploadFile = File(..., description="Reference TextGrid"),
    # ... 기타 파라미터들
):
    # 파일 검증 (라인 984-988)
    if wav.filename and not wav.filename.lower().endswith('.wav'):
        raise HTTPException(status_code=400, detail="WAV 파일만 업로드 가능합니다")
    
    # 바이트 데이터 읽기 (라인 990-993)
    wav_bytes = await wav.read()
    tg_bytes = await textgrid.read()
    
    # 임시 파일 생성 (라인 996-1002)
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as wav_temp:
        wav_temp.write(wav_bytes)
        wav_temp_path = wav_temp.name
```

#### 1.2 Parselmouth를 이용한 음성 분석
**파일:** `voice-analysis-demo/backend_server.py`
**라인:** 1005-1010

```python
# Parselmouth로 WAV 파일 로딩
import parselmouth as pm
snd = pm.Sound(wav_temp_path)

# 피치 분석 설정
pitch_floor = 75.0    # 최소 주파수 (Hz)
pitch_ceiling = 600.0 # 최대 주파수 (Hz)
time_step = 0.01      # 시간 간격 (초)
```

#### 1.3 프론트엔드 WAV 업로드 (audio-analysis.js)
**파일:** `voice-analysis-demo/static/js/audio-analysis.js`
**라인:** 675-720

```javascript
// WAV 파일 검증 및 FormData 생성
if (!$wav.files[0] || !$tg.files[0]) {
    throw new Error("WAV 파일과 TextGrid 파일을 모두 선택해주세요.");
}

const fd = new FormData();
fd.append("wav", $wav.files[0]);
fd.append("textgrid", $tg.files[0]);

// 서버로 업로드
const resp = await fetch(`${API_BASE}/analyze_ref?t=${Date.now()}`, {
    method: "POST",
    body: fd,
    cache: 'no-cache',
    headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache'
    }
});
```

### 2. TextGrid 파일 처리 시스템

#### 2.1 TextGrid 파싱 (backend_server.py)
**파일:** `voice-analysis-demo/backend_server.py`
**라인:** 140-210

```python
def parse_textgrid_praat_call(textgrid_path):
    """Parselmouth를 이용한 TextGrid 파싱"""
    try:
        import parselmouth as pm
        
        # TextGrid 로딩
        tg = pm.TextGrid.read(textgrid_path)
        
        # 티어 정보 추출
        with open(textgrid_path, 'r', encoding='utf-8') as f:
            tg_content = f.read()
            
        # 정규식을 이용한 음절 추출
        import re
        interval_pattern = r'intervals\s*\[\s*(\d+)\s*\]:\s*\n\s*xmin\s*=\s*([0-9.]+)\s*\n\s*xmax\s*=\s*([0-9.]+)\s*\n\s*text\s*=\s*"([^"]*)"'
        
        intervals = re.findall(interval_pattern, tg_content)
        syllables = []
        
        for match in intervals:
            index, xmin, xmax, text = match
            if text.strip():  # 빈 텍스트 제외
                syllables.append({
                    "label": text.strip(),
                    "start": float(xmin),
                    "end": float(xmax)
                })
        
        return syllables
    except Exception as e:
        print(f"❌ TextGrid 파싱 실패: {e}")
        return []
```

#### 2.2 TextGrid HTML 입력 요소
**파일:** `voice-analysis-demo/templates/index.html`
**라인:** 없음 (파일 업로드 방식 사용)

TextGrid는 WAV와 함께 FormData로 업로드됩니다.

### 3. 실시간 녹음 시스템

#### 3.1 WebAudio API 기반 실시간 녹음
**파일:** `voice-analysis-demo/static/js/audio-analysis.js`
**라인:** 1200-1400 (추정)

```javascript
// AudioContext 초기화
let audioCtx, micNode, procNode, analyserNode;

// 마이크 접근 및 녹음 시작
async function startRecording() {
    try {
        // 사용자 미디어 접근
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                sampleRate: realTimeCfg.sampleRate,
                channelCount: 1,
                echoCancellation: false,
                noiseSuppression: false,
                autoGainControl: false
            }
        });
        
        // AudioContext 생성
        audioCtx = new (window.AudioContext || window.webkitAudioContext)({
            sampleRate: realTimeCfg.sampleRate
        });
        
        // 마이크 노드 생성
        micNode = audioCtx.createMediaStreamSource(stream);
        analyserNode = audioCtx.createAnalyser();
        analyserNode.fftSize = realTimeCfg.fftSize;
        
        // 오디오 프로세싱 노드 생성
        procNode = audioCtx.createScriptProcessor(
            realTimeCfg.bufferSize, 1, 1
        );
        
        // 실시간 피치 분석 콜백
        procNode.onaudioprocess = function(e) {
            const inputBuffer = e.inputBuffer.getChannelData(0);
            const pitch = yinPitchDetector.getPitch(inputBuffer);
            
            if (pitch > 0) {
                const currentTime = audioCtx.currentTime;
                const semitone = 12 * Math.log2(pitch / refMedian);
                
                // 차트에 실시간 데이터 추가
                addRealTimePitchData({
                    x: currentTime,
                    y: semitone,
                    frequency: pitch
                });
            }
        };
        
        // 오디오 노드 연결
        micNode.connect(analyserNode);
        analyserNode.connect(procNode);
        procNode.connect(audioCtx.destination);
        
        isRecording = true;
        
    } catch (error) {
        console.error('🚨 녹음 시작 실패:', error);
        throw error;
    }
}
```

#### 3.2 YIN 피치 검출 알고리즘
**파일:** `voice-analysis-demo/static/js/audio-analysis.js`
**라인:** 149-250

```javascript
class YINPitchDetector {
    constructor(sampleRate = 16000, bufferSize = 4096) {
        this.sampleRate = sampleRate;
        this.bufferSize = bufferSize;
        this.threshold = 0.15;
        this.yinBuffer = new Float32Array(bufferSize / 2);
    }

    // 차분 함수 계산 (라인 160-171)
    differenceFunction(buffer) {
        const N = this.bufferSize;
        const maxTau = this.yinBuffer.length;
        
        for (let tau = 0; tau < maxTau; tau++) {
            this.yinBuffer[tau] = 0;
            for (let i = 0; i < N - maxTau; i++) {
                const delta = buffer[i] - buffer[i + tau];
                this.yinBuffer[tau] += delta * delta;
            }
        }
    }

    // 누적 평균 정규화 (라인 173-182)
    cumulativeMeanNormalizedDifferenceFunction() {
        this.yinBuffer[0] = 1;
        let runningSum = 0;
        
        for (let tau = 1; tau < this.yinBuffer.length; tau++) {
            runningSum += this.yinBuffer[tau];
            this.yinBuffer[tau] *= tau / runningSum;
        }
    }

    // 피치 검출 메인 함수
    getPitch(buffer) {
        this.differenceFunction(buffer);
        this.cumulativeMeanNormalizedDifferenceFunction();
        const tau = this.absoluteThreshold();
        
        if (tau !== 0) {
            const betterTau = this.parabolicInterpolation(tau);
            return this.sampleRate / betterTau;
        }
        
        return 0; // 피치 검출 실패
    }
}
```

#### 3.3 실시간 녹음 버튼 UI
**파일:** `voice-analysis-demo/templates/index.html`
**라인:** 229-237

```html
<!-- 통합 녹음 버튼 -->
<button id="btnUnifiedRecord" class="btn btn-sm" disabled 
        style="background-color: #e67e22; border-color: #e67e22; color: white;">
    <i class="fas fa-microphone me-1"></i> <strong>녹음</strong>
</button>

<!-- 정지 버튼 -->
<button id="btnStopRecord" class="btn btn-sm btn-outline-danger" disabled>
    <i class="fas fa-stop me-1"></i> <strong>정지</strong>
</button>
```

### 4. Chart.js를 이용한 실시간 시각화

#### 4.1 Chart.js 설정 및 초기화
**파일:** `voice-analysis-demo/templates/base.html`
**라인:** 41-59

```html
<!-- Chart.js 라이브러리 로딩 -->
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3"></script>

<script>
// annotation 플러그인 등록
document.addEventListener('DOMContentLoaded', function() {
    if (typeof Chart !== 'undefined' && typeof window.chartjs !== 'undefined') {
        Chart.register(window.chartjs.annotation);
        console.log('🎯 Chart.js annotation 플러그인 등록 완료');
    }
});
</script>
```

#### 4.2 차트 캔버스 HTML
**파일:** `voice-analysis-demo/templates/index.html`
**라인:** 268-324

```html
<div class="card-body px-2 py-2">
    <div class="chart-container" style="position: relative; height: 500px;">
        <!-- 메인 차트 캔버스 -->
        <canvas id="chart"></canvas>
        
        <!-- 키 조정 컨트롤 (우측 하단) -->
        <div id="pitchAdjustmentButtons" style="position: absolute; bottom: 10px; right: 10px;">
            <button id="btnPitchDown" class="btn btn-sm btn-outline-success">
                <i class="fas fa-arrow-down"></i>
            </button>
            <button id="btnPitchUp" class="btn btn-sm btn-outline-success">
                <i class="fas fa-arrow-up"></i>
            </button>
        </div>
        
        <!-- 확대/스크롤 컨트롤 (우측 상단) -->
        <div style="position: absolute; top: 10px; right: 10px;">
            <button id="btnZoomIn" class="btn btn-sm btn-outline-primary">
                <i class="fas fa-search-plus"></i>
            </button>
            <button id="btnZoomOut" class="btn btn-sm btn-outline-primary">
                <i class="fas fa-search-minus"></i>
            </button>
        </div>
    </div>
</div>
```

#### 4.3 차트 데이터 업데이트 (JavaScript)
**파일:** `voice-analysis-demo/static/js/audio-analysis.js`
**라인:** 833-850

```javascript
// 참조 곡선 데이터 업데이트
const chartData = refCurve.map(p => ({x: p.t, y: p.semitone || 0}));
chart.data.datasets[0].data = chartData;  // Dataset 0: 참조 억양 패턴

// 음절 대표 피치 데이터 업데이트 (라인 901-910)
if (chart.data.datasets[1] && syllableCenterPoints.length > 0) {
    chart.data.datasets[1].data = syllableCenterPoints;  // Dataset 1: 음절 대표 피치
    chart.data.datasets[1].hidden = false;
    
    // 강제 차트 재렌더링
    chart.update('none');
}
```

### 5. 데이터베이스 모델

#### 5.1 SQLAlchemy 모델 정의
**파일:** `voice-analysis-demo/models.py`
**라인:** 1-51

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

# 사용자 모델 (라인 9-15)
class User(UserMixin, Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(256))
    created_at = Column(DateTime, default=datetime.utcnow)

# 분석 세션 모델 (라인 17-24)
class AnalysisSession(Base):
    __tablename__ = 'analysis_session'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=True)
    session_data = Column(Text)  # JSON 데이터
    created_at = Column(DateTime, default=datetime.utcnow)
    session_type = Column(String(50))  # 'reference', 'realtime' 등

# 참조 파일 모델 (라인 34-50)
class ReferenceFile(Base):
    __tablename__ = 'reference_file'
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    wav_filename = Column(String(255), nullable=False)
    textgrid_filename = Column(String(255), nullable=False)
    duration = Column(Float)  # 오디오 길이 (초)
    average_f0 = Column(Float)  # 평균 기본 주파수 (Hz)
    detected_gender = Column(String(10))  # 'male'/'female'
    is_public = Column(Boolean, default=True)
```

### 6. CSS 스타일링 시스템

#### 6.1 기본 스타일 설정
**파일:** `voice-analysis-demo/static/css/custom.css`
**라인:** 6-42

```css
/* Pretendard 폰트 적용 */
body {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, 
                 Roboto, 'Helvetica Neue', 'Segoe UI', 'Apple SD Gothic Neo', 
                 'Noto Sans KR', 'Malgun Gothic', sans-serif;
    font-feature-settings: 'tnum';
    font-variant-numeric: tabular-nums;
    font-weight: 400;
}

/* 헤딩 요소 폰트 */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif !important;
    font-weight: 600;
}
```

#### 6.2 녹음 버튼 애니메이션
**파일:** `voice-analysis-demo/static/css/custom.css`
**라인:** 74-130

```css
/* 녹음 중 펄스 애니메이션 */
.recording-pulse {
    animation: recording-pulse 1.5s ease-in-out infinite;
}

@keyframes recording-pulse {
    0% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.1); opacity: 0.7; }
    100% { transform: scale(1); opacity: 1; }
}

/* 녹음 버튼 글로우 효과 */
.btn-recording {
    animation: btn-recording-glow 2s ease-in-out infinite;
    position: relative;
    overflow: hidden;
}

@keyframes btn-recording-glow {
    0% { box-shadow: 0 0 5px rgba(220, 53, 69, 0.5); }
    50% { box-shadow: 0 0 20px rgba(220, 53, 69, 0.8); }
    100% { box-shadow: 0 0 5px rgba(220, 53, 69, 0.5); }
}
```

#### 6.3 차트 컨테이너 스타일
**파일:** `voice-analysis-demo/static/css/custom.css`
**라인:** 66-72

```css
/* Chart container for light mode */
.chart-container {
    background: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 0.5rem;
    padding: 1rem;
}
```

### 7. React 컴포넌트 구조

#### 7.1 메인 React 컴포넌트
**파일:** `voice-analysis-demo/react-app/src/VoiceAnalysisApp.tsx`
**라인:** 1-50

```typescript
import React, { useState, useEffect, useRef } from 'react';
import { useAudioRecording } from './hooks/useAudioRecording';
import { usePitchChart } from './hooks/usePitchChart';

// 타입 정의
interface LearnerInfo {
    name: string;
    gender: 'male' | 'female' | '';
    level: string;
}

interface ReferenceFile {
    id: string;
    sentence_text: string;
    duration: number;
    detected_gender: string;
    average_f0: number;
}

const VoiceAnalysisApp: React.FC = () => {
    // 상태 관리
    const [learnerInfo, setLearnerInfo] = useState<LearnerInfo>({
        name: '', gender: '', level: ''
    });
    const [learningMethod, setLearningMethod] = useState<string>('');
    
    // 커스텀 훅 사용
    const audioRecording = useAudioRecording();
    const pitchChart = usePitchChart(canvasRef);
    
    // 컴포넌트 초기화
    useEffect(() => {
        loadReferenceFiles();
        audioRecording.setPitchCallback((frequency: number, timestamp: number) => {
            pitchChart.addPitchData(frequency, timestamp, 'live');
        });
    }, []);
    
    return (
        // JSX 렌더링...
    );
};
```

## 🔧 주요 라이브러리 및 의존성

### JavaScript/Frontend
- **Chart.js 4.4.0**: 실시간 차트 시각화
- **chartjs-plugin-annotation 3.0.1**: 차트 주석 기능
- **Bootstrap 5.3.3**: UI 프레임워크
- **Font Awesome 6.5.1**: 아이콘 라이브러리
- **Pretendard 폰트**: 한국어 최적화 폰트

### Python/Backend
- **FastAPI 0.104.1**: 고성능 웹 API 프레임워크
- **uvicorn 0.24.0**: ASGI 서버
- **praat-parselmouth 0.4.3**: 음성 분석 라이브러리
- **SQLAlchemy 2.0.23**: ORM 데이터베이스
- **numpy 1.25.2**: 수치 연산
- **jinja2 3.1.2**: 템플릿 엔진

### React (선택사항)
- **React 19.1.1**: UI 라이브러리
- **TypeScript 4.9.5**: 정적 타입 언어
- **axios 1.6.0**: HTTP 클라이언트
- **@tanstack/react-query 5.0.0**: 서버 상태 관리

## 🚀 실행 및 배포

### 개발 환경 실행
```bash
# Python 의존성 설치
pip install -r requirements.txt

# Node.js 의존성 설치
npm install concurrently
cd react-app && npm install && cd ..

# 서버 실행 (포트 5000)
uvicorn backend_server:app --host 0.0.0.0 --port 5000 --reload
```

### 프로덕션 배포
```bash
# 가상환경 설정
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 또는 venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt

# 서버 실행
./run.sh  # 또는 run.bat (Windows)
```

## 📝 구현 시 주의사항

1. **CORS 설정**: 개발/프로덕션 환경에 맞는 CORS 정책 설정
2. **파일 업로드 제한**: WAV/TextGrid 파일 크기 및 형식 검증
3. **브라우저 호환성**: WebAudio API 브라우저 지원 확인
4. **메모리 관리**: 실시간 오디오 처리 시 메모리 누수 방지
5. **에러 핸들링**: 마이크 접근 권한 및 오디오 컨텍스트 오류 처리

이 가이드를 따라 ToneBridge와 동일한 음성 분석 애플리케이션을 완전히 구현할 수 있습니다.