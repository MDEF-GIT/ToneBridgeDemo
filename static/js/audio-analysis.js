console.log('🎯 ToneBridge audio-analysis.js loaded');
/**
 * ToneBridge Audio Analysis Frontend
 * Real-time pitch tracking and overlay visualization
 */

// Use API_BASE from window if available, otherwise default to current origin
const API_BASE = window.API_BASE || "";

// DOM Elements - Initialize after DOM is ready
let $wav, $tg, $btnAnalyze, $btnMic, $btnReset, $btnClearChart, $status, $btnPlayRef, $btnPlayRec, $savedFiles, $btnSaveReference, $semitoneMin, $semitoneMax, $btnUpdateRange;
let $btnPitchTest, $btnStopPitchTest, $pitchTestStatus, $freqRangeDisplay, $btnClearRange, $btnReplayPractice;

function initializeElements() {
    $wav = document.getElementById('wav');
    $tg = document.getElementById('tg');
    $btnAnalyze = document.getElementById('btnAnalyze');
    $btnMic = document.getElementById('btnUnifiedRecord'); // 🎯 실제 템플릿의 통합 녹음 버튼 사용
    $btnReset = document.getElementById('btnReset');
    $btnClearChart = document.getElementById('btnClearChart');
    $status = document.getElementById('status');
    $btnPlayRef = document.getElementById('btnPlayRef');
    $btnPlayRec = document.getElementById('btnPlayRec');
    $savedFiles = document.getElementById('savedFiles');
    $btnSaveReference = document.getElementById('btnSaveReference');
    $semitoneMin = document.getElementById('semitoneMin');
    $semitoneMax = document.getElementById('semitoneMax');
    $btnUpdateRange = document.getElementById('btnUpdateRange');
    $btnPitchTest = document.getElementById('btnPitchTest');
    $btnStopPitchTest = document.getElementById('btnStopPitchTest');
    $pitchTestStatus = document.getElementById('pitchTestStatus');
    $freqRangeDisplay = document.getElementById('freqRangeDisplay');
    $btnClearRange = document.getElementById('btnClearRange');
    // $btnDeleteSaved 제거됨
    $btnReplayPractice = document.getElementById('btnReplayPractice');
    $btnTwoPointPractice = document.getElementById('btnTwoPointPractice');
    
    console.log('DOM elements found:', {
        wav: !!$wav,
        tg: !!$tg,
        btnAnalyze: !!$btnAnalyze,
        btnMic: !!$btnMic, // 이제 btnUnifiedRecord를 가리킴
        btnReset: !!$btnReset,
        btnClearChart: !!$btnClearChart,
        status: !!$status,
        btnPlayRef: !!$btnPlayRef,
        btnPlayRec: !!$btnPlayRec,
        savedFiles: !!$savedFiles,
        btnSaveReference: !!$btnSaveReference,
        semitoneMin: !!$semitoneMin,
        semitoneMax: !!$semitoneMax,
        btnUpdateRange: !!$btnUpdateRange,
        btnPitchTest: !!$btnPitchTest,
        btnStopPitchTest: !!$btnStopPitchTest,
        pitchTestStatus: !!$pitchTestStatus,
        freqRangeDisplay: !!$freqRangeDisplay,
        btnClearRange: !!$btnClearRange,
        // btnDeleteSaved 제거됨
        btnReplayPractice: !!$btnReplayPractice,
    });
    
    // DOM 요소 존재 확인 (오류 대신 경고로 변경)
    // DOM 요소 존재 확인 (null 체크로 오류 방지)
    if (!$wav) console.warn('⚠️ WAV input not found');
    if (!$tg) console.warn('⚠️ TextGrid input not found'); 
    if (!$btnAnalyze) console.warn('⚠️ Analyze button not found');
    if (!$status) console.warn('⚠️ Status element not found');
    if (!$btnMic) console.warn('⚠️ Record button not found');
    
    // 🎯 Pitch Test 이벤트 핸들러 설정
    setupPitchTestHandlers();
    
    // 🎯 범위 해제 버튼 핸들러
    if ($btnClearRange) {
        $btnClearRange.onclick = () => {
            if (typeof clearPitchRange === 'function') {
                clearPitchRange();
            }
            pitchRange = null;
            targetPitch = null;
            if (typeof updatePitchTestButtons === 'function') {
                updatePitchTestButtons();
            }
            
            if ($pitchTestStatus) {
                $pitchTestStatus.textContent = "차트를 클릭하고 드래그해서 연습 범위를 설정하거나 한 점을 클릭해서 목표 음높이를 설정하세요";
                $pitchTestStatus.className = "text-center text-danger small fw-bold";
            }
            
            console.log("🎯 음높이 범위 및 목표 해제됨");
        };
    }
    
    // 🎯 초기 Hz 범위 표시
    updateFrequencyRangeDisplay(-6, 12);
}

// Analysis State
let refCurve = [];
let refSyll = [];
let refStats = {meanF0: 0, maxF0: 0, duration: 0};
let liveStats = {meanF0: 0, maxF0: 0};
let spectrogramData = [];
let liveBuffer = [];
let started = false;
let isListening = false; // 🎯 추가: 녹음 상태 추적을 위한 변수
let refMedian = 200; // Reference median for semitone calculation

// 🎵 피치 조정 변수들
let pitchOffsetSemitones = 0;  // 현재 피치 오프셋 (세미톤 단위)
let originalSyllableData = [];  // 원본 음절 데이터 저장

// 🔍 확대/스크롤 관련 변수
let zoomLevel = 1;
let scrollPosition = 0;
let originalXMin = null;
let originalXMax = null;

// Audio Processing Configuration - optimized for pitch tracking
const cfg = {
    sampleRate: 16000,
    frameMs: 25,   // 🎯 VocalPitchMonitor 스타일: 20-40ms 최적화
    hopMs: 5       // 🎯 더 부드러운 추적을 위한 작은 hop
};

// 🎤 실시간 피치 트래킹 설정
const realTimeCfg = {
    bufferSize: 4096,      // 낮은 지연을 위한 작은 버퍼
    fftSize: 2048,         // YIN 알고리즘용 FFT 크기
    minFreq: 80,           // 최소 주파수 (Hz)
    maxFreq: 800,          // 최대 주파수 (Hz)
    threshold: 0.1,        // YIN 임계값
    smoothingFactor: 0.8,  // 피치 스무딩
    confidenceThreshold: 0.85 // 신뢰도 임계값 (소음 필터링 강화)
};

// 🎤 실시간 피치 데이터 저장
let realTimePitchData = [];
let currentPitchValue = 0;
let pitchConfidence = 0;
let lastValidPitch = 0;
let pitchHoldCounter = 0; // 같은 피치 지속 시간 카운터

// 실시간 오디오 관련 변수들 (재작성 예정)
let audioCtx, micNode, procNode, analyserNode;
let tLive = 0;
let sylCuts = [];

// 🎤 YIN 알고리즘 구현 (VocalPitchMonitor 수준의 정확도)
class YINPitchDetector {
    constructor(sampleRate = 16000, bufferSize = 4096) {
        this.sampleRate = sampleRate;
        this.bufferSize = bufferSize;
        this.threshold = 0.15;
        this.probabilityThreshold = 0.1;
        this.yinBuffer = new Float32Array(bufferSize / 2);
    }

    // 🎯 YIN 알고리즘 핵심 - 차분 함수 계산
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

    // 🎯 누적 평균 정규화 함수
    cumulativeMeanNormalizedDifferenceFunction() {
        this.yinBuffer[0] = 1;
        let runningSum = 0;
        
        for (let tau = 1; tau < this.yinBuffer.length; tau++) {
            runningSum += this.yinBuffer[tau];
            this.yinBuffer[tau] *= tau / runningSum;
        }
    }

    // 🎯 절대 임계값 함수
    absoluteThreshold() {
        let tau = 2; // 시작점 (너무 낮은 주파수 방지)
        
        // 첫 번째 최소값 찾기
        while (tau < this.yinBuffer.length) {
            if (this.yinBuffer[tau] < this.threshold) {
                // 지역 최소값인지 확인
                while (tau + 1 < this.yinBuffer.length && this.yinBuffer[tau + 1] < this.yinBuffer[tau]) {
                    tau++;
                }
                return tau;
            }
            tau++;
        }
        
        // 임계값 이하가 없으면 전역 최소값 반환
        let minTau = 2;
        for (let i = 3; i < this.yinBuffer.length; i++) {
            if (this.yinBuffer[i] < this.yinBuffer[minTau]) {
                minTau = i;
            }
        }
        
        return this.yinBuffer[minTau] < this.probabilityThreshold ? minTau : 0;
    }

    // 🎯 포물선 보간으로 정밀도 향상
    parabolicInterpolation(tau) {
        if (tau < 1 || tau >= this.yinBuffer.length - 1) {
            return tau;
        }
        
        const s0 = this.yinBuffer[tau - 1];
        const s1 = this.yinBuffer[tau];
        const s2 = this.yinBuffer[tau + 1];
        
        const a = (s0 - 2 * s1 + s2) / 2;
        const b = (s2 - s0) / 2;
        
        if (a !== 0) {
            return tau - b / (2 * a);
        }
        return tau;
    }

    // 🎯 메인 피치 감지 함수
    detectPitch(buffer) {
        // 1. 차분 함수 계산
        this.differenceFunction(buffer);
        
        // 2. 누적 평균 정규화
        this.cumulativeMeanNormalizedDifferenceFunction();
        
        // 3. 절대 임계값으로 tau 찾기
        const tau = this.absoluteThreshold();
        
        if (tau === 0) {
            return { frequency: 0, confidence: 0 };
        }
        
        // 4. 포물선 보간으로 정밀도 향상
        const betterTau = this.parabolicInterpolation(tau);
        
        // 5. 주파수 계산
        const frequency = this.sampleRate / betterTau;
        const confidence = 1 - this.yinBuffer[tau];
        
        // 유효 주파수 범위 체크 (80Hz ~ 800Hz)
        if (frequency < 80 || frequency > 800) {
            return { frequency: 0, confidence: 0 };
        }
        
        return { frequency, confidence };
    }
}

// 🎤 실시간 피치 감지 관련 변수들 (재작성 예정)
let yinDetector = null;

// Audio playback variables
let refAudioBlob = null;
let recordedAudioBlob = null;
let selectedGender = null;
let detectedReferenceGender = null;
let learningMethod = null;
let learnerGender = null;
let progressStep = 0;
let currentlyPlaying = null;
// 녹음 관련 변수들 (재작성 예정)  
let mediaRecorder = null;

// Pitch Test variables
let pitchTestActive = false;
let targetPitch = null; // Target semitone value
let pitchTestBuffer = [];
let pitchRange = null; // Pitch range for practice
let chartFrozen = false; // 🎯 차트 고정 상태 (음높이 테스트 중)
let originalScales = null; // 🎯 음높이 테스트 시작 전 원본 차트 스케일
let pitchTestLine = null; // Chart reference line
let pitchTestStream = null;
let pitchTestAudioCtx = null;
let pitchTestProcNode = null;
let recordedChunks = [];

// Range selection variables
let isSelecting = false;
let rangeStart = null;
let rangeEnd = null;
let currentLiveHz = 0; // 실시간 Hz 값
// pitchRange는 위에서 이미 선언됨 - 중복 제거됨

// 🎯 지속 발성 추적 변수들 (실시간 녹음용)
let sustainedPitchValue = null;
let pitchHoldStartTime = 0;
let pitchHoldDuration = 0;
const PITCH_STABLE_THRESHOLD = 0.3; // 세미톤 단위 안정성 임계값
const MAX_HOLD_DURATION = 3.0; // 최대 3초까지 두께 증가

// EdTech Learning Progress Variables
let learningProgress = 0;
let pronunciationScore = 0;
let startTime = 0; // 🎯 오디오 시작 시간
let totalSteps = 4; // 파일준비, 분석, 연습, 결과확인

// Update EdTech Progress Elements
function updateLearningProgress(step, score = null) {
    learningProgress = Math.min(step / totalSteps * 100, 100);
    const progressBar = document.getElementById('progressBar');
    const scoreElement = document.getElementById('pronunciationScore');
    
    if (progressBar) {
        progressBar.style.width = `${learningProgress}%`;
        progressBar.setAttribute('aria-valuenow', learningProgress);
    }
    
    if (score !== null) {
        pronunciationScore = score;
        if (scoreElement) {
            scoreElement.textContent = `${score}점`;
            scoreElement.className = `h5 ${score >= 80 ? 'text-success' : score >= 60 ? 'text-warning' : 'text-danger'}`;
        }
    }
}

// Calculate pronunciation similarity score
function calculatePronunciationScore() {
    if (refCurve.length === 0 || liveBuffer.length === 0) return 0;
    
    let similarity = 0;
    let count = 0;
    
    // Compare pitch patterns
    const minLength = Math.min(refCurve.length, liveBuffer.length);
    for (let i = 0; i < minLength; i += 10) { // Sample every 10th point for efficiency
        if (refCurve[i] && liveBuffer[i] && refCurve[i].f0 > 0 && liveBuffer[i].f0 > 0) {
            const refPitch = refCurve[i].f0;
            const livePitch = liveBuffer[i].f0;
            const diff = Math.abs(refPitch - livePitch) / refPitch;
            similarity += Math.max(0, 1 - diff);
            count++;
        }
    }
    
    return count > 0 ? Math.round((similarity / count) * 100) : 0;
}

// Update button states
function updateButtons() {
    const hasWav = $wav && $wav.files && $wav.files.length > 0;
    const hasTextGrid = $tg && $tg.files && $tg.files.length > 0;
    const hasRefData = refCurve.length > 0 && refSyll.length > 0;
    const hasRecording = recordedAudioBlob !== null;
    const canSave = hasWav && hasTextGrid;
    
    console.log('Updating buttons:', {
        hasWav,
        hasTextGrid,
        hasRefData,
        hasRecording,
        wavFiles: $wav ? $wav.files.length : 0,
        tgFiles: $tg ? $tg.files.length : 0
    });
    
    if ($btnAnalyze) {
        // 🎯 학습 방법별 우선 조건 확인
        if (learningMethod === 'sentence') {
            // 문장억양연습: 선택된 문장 또는 파일 업로드 모두 허용
            const hasSelectedSentence = window.currentSelectedSentence;
            $btnAnalyze.disabled = !(hasSelectedSentence || (hasWav && hasTextGrid));
        } else if (learningMethod === 'pitch') {
            // 음높이 학습: 분석 버튼 비활성화
            $btnAnalyze.disabled = true;
        } else {
            // 미선택: WAV + TextGrid 파일이 있으면 활성화
            $btnAnalyze.disabled = !(hasWav && hasTextGrid);
        }
        console.log('Analyze button disabled:', $btnAnalyze.disabled, '(학습방법:', learningMethod + ')');
    }
    
    if ($btnMic) {
        // 🎯 학습 방법별 우선 조건 확인
        if (learningMethod === 'pitch') {
            // 음높이 학습: 모든 녹음 관련 버튼 비활성화
            $btnMic.disabled = true;
        } else if (learningMethod === 'sentence') {
            // 문장억양연습: 참조 데이터 또는 선택된 문장이 있으면 활성화
            const hasSelectedSentence = window.currentSelectedSentence;
            $btnMic.disabled = !(hasRefData || hasSelectedSentence);
        } else {
            // 미선택: 참조 데이터가 있으면 활성화
            $btnMic.disabled = !hasRefData; // 참조 분석이 완료되면 활성화
        }
        console.log('Record button disabled:', $btnMic.disabled, '(학습방법:', learningMethod + ')');
    }
    
    if ($btnPlayRef) {
        // 선택된 문장이 있거나 WAV 파일이 있으면 활성화
        const hasSelectedSentence = window.currentSelectedSentence;
        $btnPlayRef.disabled = !(hasWav || hasSelectedSentence);
        console.log(`🎵 참조음성 재생 버튼 상태: ${$btnPlayRef.disabled ? '비활성화' : '활성화'} (WAV: ${hasWav}, 선택된문장: ${hasSelectedSentence})`);
    }
    
    if ($btnPlayRec) {
        $btnPlayRec.disabled = !hasRecording;
    }
    
    
    if ($btnSaveReference) {
        $btnSaveReference.disabled = !canSave;
    }
    
    // 🎯 피치 테스트 버튼 상태 업데이트
    updatePitchTestButtons();
    
    // 🎯 키 조정 버튼은 항상 활성화 (실제 동작은 adjustChartPosition에서 제어)
    
    // Update EdTech status message with learning context
    if ($status) {
        if (!hasWav && !hasTextGrid) {
            $status.textContent = "📱 휴대폰을 가로보기로 하시면 그래프를 한눈에 볼 수 있습니다.";
            updateLearningProgress(0);
        } else if (!hasWav) {
            $status.textContent = "🎵 표준 억양 WAV 파일을 선택해 주세요.";
            updateLearningProgress(0.5);
        } else if (!hasTextGrid) {
            $status.textContent = "📝 음절 구분 TextGrid 파일을 선택해 주세요.";
            updateLearningProgress(0.5);
        } else if (!hasRefData) {
            $status.textContent = "✅ 학습 자료 준비 완료! 이제 '모델 음성 분석' 버튼을 클릭하여 표준 억양 패턴을 분석하세요.";
            updateLearningProgress(1);
        } else if (!started) {
            $status.textContent = "🎯 분석 완료! '억양 연습 시작' 버튼을 클릭하여 실제 억양 연습을 시작하세요.";
            updateLearningProgress(2);
        } else {
            $status.textContent = "🎤 억양 연습 중... 표준 억양과 비교하며 연습해보세요!";
            updateLearningProgress(3);
        }
    }
    // 🔍 확대/스크롤 버튼 핸들러들
    setupZoomAndScrollHandlers();
}

// 🔍 확대/스크롤 기능 핸들러 설정
function setupZoomAndScrollHandlers() {
    // 확대 버튼 - 더 세밀한 확대
    const btnZoomIn = document.getElementById('btnZoomIn');
    if (btnZoomIn) {
        btnZoomIn.onclick = () => zoomChart(1.2);
    }
    
    // 축소 버튼 - 더 세밀한 축소
    const btnZoomOut = document.getElementById('btnZoomOut');
    if (btnZoomOut) {
        btnZoomOut.onclick = () => zoomChart(0.83);
    }
    
    // 왼쪽 스크롤
    const btnScrollLeft = document.getElementById('btnScrollLeft');
    if (btnScrollLeft) {
        btnScrollLeft.onclick = () => scrollChart(-0.2);
    }
    
    // 오른쪽 스크롤
    const btnScrollRight = document.getElementById('btnScrollRight');
    if (btnScrollRight) {
        btnScrollRight.onclick = () => scrollChart(0.2);
    }
    
    // 전체 보기 리셋
    const btnResetView = document.getElementById('btnResetView');
    if (btnResetView) {
        btnResetView.onclick = () => resetChartView();
    }
    
    // 마우스 휠 이벤트 (차트 캔버스에서) - 더 세밀한 줌
    // 마우스 휠 확대 기능 제거됨 - 버튼으로만 확대/축소 가능
}

// 🔍 차트 확대/축소 함수
function zoomChart(factor) {
    if (!chart) return;
    
    const previousZoomLevel = zoomLevel;
    zoomLevel *= factor;
    zoomLevel = Math.max(0.5, Math.min(10, zoomLevel)); // 0.5배 ~ 10배 제한
    
    // 축소 시 0.9배 이하로 내려가면 전체 보기로 리셋
    if (factor < 1 && zoomLevel <= 0.9) {
        resetChartView();
        return;
    }
    
    // 원본 범위 저장 (처음 한 번만)
    if (originalXMin === null && chart.scales && chart.scales.x) {
        // 현재 차트에서 실제 데이터 범위 확인
        const datasets = chart.data.datasets;
        let minTime = Infinity, maxTime = -Infinity;
        
        datasets.forEach(dataset => {
            if (dataset.data && dataset.data.length > 0) {
                dataset.data.forEach(point => {
                    if (point && typeof point.x === 'number') {
                        minTime = Math.min(minTime, point.x);
                        maxTime = Math.max(maxTime, point.x);
                    }
                });
            }
        });
        
        if (minTime !== Infinity && maxTime !== -Infinity) {
            originalXMin = minTime - (maxTime - minTime) * 0.05; // 약간의 여백 추가
            originalXMax = maxTime + (maxTime - minTime) * 0.05;
        } else {
            // 폴백: 현재 차트 스케일 사용
            originalXMin = chart.scales.x.min || 0;
            originalXMax = chart.scales.x.max || 10;
        }
        
        console.log(`🔍 원본 범위 설정: ${originalXMin.toFixed(2)}s - ${originalXMax.toFixed(2)}s`);
    }
    
    if (originalXMin !== null && originalXMax !== null) {
        const totalRange = originalXMax - originalXMin;
        const viewRange = totalRange / zoomLevel;
        
        // 현재 스크롤 위치를 고려한 범위 계산
        const centerPos = originalXMin + (totalRange * scrollPosition);
        const newMin = Math.max(originalXMin, centerPos - viewRange / 2);
        const newMax = Math.min(originalXMax, centerPos + viewRange / 2);
        
        // 경계 조정 (범위가 원본을 벗어나지 않도록)
        if (newMax - newMin > totalRange) {
            chart.options.scales.x.min = originalXMin;
            chart.options.scales.x.max = originalXMax;
        } else {
            chart.options.scales.x.min = newMin;
            chart.options.scales.x.max = newMax;
        }
        
        chart.update('none');
        console.log(`🔍 차트 확대: ${zoomLevel.toFixed(2)}배, 범위: ${newMin.toFixed(2)}s - ${newMax.toFixed(2)}s`);
    }
}

// 🔍 차트 스크롤 함수
function scrollChart(direction) {
    if (!chart || originalXMin === null || originalXMax === null) return;
    
    const totalRange = originalXMax - originalXMin;
    const viewRange = totalRange / zoomLevel;
    
    // 스크롤 위치 업데이트 (0-1 범위)
    scrollPosition += direction;
    scrollPosition = Math.max(0, Math.min(1 - (viewRange / totalRange), scrollPosition));
    
    // 새로운 범위 계산
    const centerPos = originalXMin + (totalRange * scrollPosition) + (viewRange / 2);
    const newMin = Math.max(originalXMin, centerPos - viewRange / 2);
    const newMax = Math.min(originalXMax, centerPos + viewRange / 2);
    
    // 스케일 업데이트
    chart.options.scales.x.min = newMin;
    chart.options.scales.x.max = newMax;
    
    chart.update('none');
    console.log(`🔍 차트 스크롤: ${scrollPosition.toFixed(2)}, 범위: ${newMin.toFixed(2)}s - ${newMax.toFixed(2)}s`);
}

// 🔍 차트 뷰 초기화 함수
function resetChartView() {
    if (!chart) return;
    
    zoomLevel = 1;
    scrollPosition = 0;
    
    // 원본 범위 재설정 (데이터가 있는 경우)
    originalXMin = null;
    originalXMax = null;
    
    // 자동 스케일링으로 복원
    delete chart.options.scales.x.min;
    delete chart.options.scales.x.max;
    
    chart.update('none');
    console.log('🔍 차트 뷰 초기화: 전체 보기로 복원');
}

// Initialize all event handlers after DOM is ready
function setupEventHandlers() {
    // File upload handlers
    if ($wav) {
        $wav.addEventListener('change', function(e) {
            console.log('WAV file changed:', e.target.files);
            updateButtons();
            if (e.target.files.length > 0) {
                updateLearningProgress(0.5);
            }
        });
    } else {
        console.error('Cannot add WAV listener - element not found');
    }
    
    if ($tg) {
        $tg.addEventListener('change', function(e) {
            console.log('TextGrid file changed:', e.target.files);
            updateButtons();
            if (e.target.files.length > 0) {
                updateLearningProgress(1);
            }
        });
    } else {
        console.error('Cannot add TextGrid listener - element not found');
    }

    // Button click handlers
    if ($btnAnalyze) {
        $btnAnalyze.onclick = function() {
            const analyzeAsync = async () => {
                try {
                    // 🎯 학습자 정보 필수 입력 검증
                    const learnerGender = document.getElementById('learner-gender').value;
                    if (!learnerGender) {
                        alert('학습자 성별 정보를 먼저 입력해주세요.');
                        document.getElementById('learner-gender').focus();
                        return;
                    }
                    
                    console.log("🚀 분석 시작 - 안전한 오류 처리 적용");
                    console.log(`🎯 학습자 정보: 성별=${learnerGender}`);
                    // 🧹 분석 시작 전 완전한 데이터 초기화
                    console.log("🧹 새로운 분석 시작 - 이전 데이터 완전 초기화");
                
                // 차트 데이터 초기화
                if (chart) {
                    chart.data.datasets[0].data = [];  // Reference data (참조 억양 패턴)
                    chart.data.datasets[1].data = [];  // 음절 대표 피치
                    chart.data.datasets[2].data = [];  // 실시간 피치선
                }
                
                // 🎯 maxTime 캐시 초기화 (새로운 분석 시작)
                window.cachedMaxTime = null;
                
                // 분석 데이터 초기화
                refCurve = [];
                refSyll = [];
                refStats = {meanF0: 0, maxF0: 0, duration: 0};
                
                // 음절 표시 완전 제거 
                if (chart && chart.options.plugins && chart.options.plugins.annotation) {
                    chart.options.plugins.annotation.annotations = {};
                    chart.update('none');
                    console.log("🧹 음절 표시 초기화 완료");
                }
                
                // 🎯 학습 방법별 파일 검증
                const selectedMethod = document.querySelector('input[name="learningMethod"]:checked');
                
                if (selectedMethod && selectedMethod.value === 'sentence') {
                    // 문장 억양 연습 모드: 선택된 문장이 있으면 OK
                    if (window.currentSelectedSentence) {
                        console.log(`🎯 문장 모드 분석: ${window.currentSelectedSentence}`);
                        
                        // 선택된 문장에 맞는 차트 데이터 로드
                        await loadSentenceForLearner(window.currentSelectedSentence);
                        $status.textContent = `✅ "${window.currentSelectedSentence}" 문장 분석 완료! 참조음성 재생 또는 녹음 연습을 시작하세요.`;
                        updateButtons();
                        return; // 파일 업로드 로직 건너뛰기
                    } else {
                        throw new Error("먼저 연습할 문장을 선택해주세요.");
                    }
                } else {
                    // 파일 업로드 모드: WAV + TextGrid 파일 필요
                    if (!$wav.files[0] || !$tg.files[0]) {
                        throw new Error("WAV 파일과 TextGrid 파일을 모두 선택해주세요.");
                    }
                }
                
                // 파일 업로드 모드에서만 실행되는 로직
                console.log("📁 파일 확인:", {
                    wav: $wav.files[0].name,
                    textgrid: $tg.files[0].name
                });
                
                const fd = new FormData();
                fd.append("wav", $wav.files[0]);
                fd.append("textgrid", $tg.files[0]);
                
                // 🎯 학습자 정보 전달
                fd.append('learner_gender', learnerGender);
                const learnerName = document.getElementById('learner-name').value || '';
                const learnerLevel = document.getElementById('learner-level').value || '';
                fd.append('learner_name', learnerName);
                fd.append('learner_level', learnerLevel);
            
            // Add sentence text if provided
            const sentenceText = document.getElementById('sentence-text');
            if (sentenceText && sentenceText.value.trim()) {
                fd.append("sentence", sentenceText.value.trim());
            }
            
                $status.textContent = "🔄 참조 데이터 분석 중...";
                $btnAnalyze.disabled = true;
                
                console.log("📡 서버로 분석 요청 전송...");
                
                const resp = await fetch(`${API_BASE}/analyze_ref?t=${Date.now()}&_=${Math.random()}`, {
                    method: "POST",
                    body: fd,
                    cache: 'no-cache',
                    headers: {
                        'Cache-Control': 'no-cache, no-store, must-revalidate',
                        'Pragma': 'no-cache'
                    }
                });
                
                console.log("📡 서버 응답 상태:", resp.status, resp.statusText);
                
                if (!resp.ok) {
                    const errorText = await resp.text();
                    console.error('🚨 서버 응답 오류:', errorText);
                    throw new Error(`서버 오류 (${resp.status}): ${errorText}`);
                }
                
                const js = await resp.json();
                console.log("📄 서버 응답 데이터:", js);
                console.log("🎯 응답 구조 확인:", {
                    curve: js.curve ? js.curve.length : 'undefined',
                    syllables: js.syllables ? js.syllables.length : 'undefined', 
                    syllable_analysis: js.syllable_analysis ? js.syllable_analysis.length : 'undefined',
                    stats: js.stats ? 'exists' : 'undefined'
                });
                
                // Process reference data
                refCurve = js.curve.map(p => ({
                    t: p.t,
                    f0: p.f0,
                    semitone: p.semitone || 0,  // Include semitone for charting
                    int: normInt(p.dB)
                }));
                
                // 🎯 스펙트로그램 배경 처리 (사용자 요청)
                spectrogramData = js.spectrogram || [];
                console.log("🎯 응답 데이터 확인:", {
                    curve_length: js.curve ? js.curve.length : 0,
                    curve_data: js.curve,
                    spectrogram_exists: !!js.spectrogram,
                    spectrogram_length: spectrogramData.length
                });
                
                if (spectrogramData.length > 0) {
                    console.log(`🎯 스펙트로그램 데이터 수신: ${spectrogramData.length}개 시점`);
                    // 스펙트로그램 플러그인 즉시 등록
                    Chart.register({
                        id: 'spectrogramBackground',
                        beforeDraw: function(chartInstance, args, options) {
                            renderSpectrogramOnCanvas(chartInstance, spectrogramData);
                        }
                    });
                } else {
                    console.log("🎯 스펙트로그램 데이터 없음");
                }
                
                refSyll = js.syllables;
                refStats = js.stats;
                refMedian = js.stats.sentence_median || 200; // Set reference median for semitone calculation
                console.log("🎯 Reference median set to:", refMedian);
                
                // 🎯 성별 감지 및 자동 정규화 적용
                detectedReferenceGender = js.stats.detected_gender || (refMedian > 175 ? 'female' : 'male');
                
                // 학습자 성별이 이미 선택된 경우 자동 정규화 적용
                if (learnerGender && learnerGender !== detectedReferenceGender) {
                    console.log(`🎯 자동 성별 정규화: ${detectedReferenceGender} → ${learnerGender}`);
                    analyzeReferenceWithGender(learnerGender);
                    return;
                }
                
                // Calculate optimal range based on semitone data
                const semitoneValues = refCurve.map(p => p.semitone);
                
                // 🎯 syllable_analysis 데이터도 포함해서 범위 계산
                if (js.syllable_analysis && js.syllable_analysis.length > 0) {
                    const syllableSemitones = js.syllable_analysis.map(s => s.semitone || s.semitone_median || 0);
                    semitoneValues.push(...syllableSemitones);
                    console.log("🎯 음절 대표 피치 범위도 포함:", syllableSemitones.slice(0, 5));
                }
                
                const optimalRange = calculateOptimalRange(semitoneValues);
                console.log("🎯 Suggested range (curve + syllables):", optimalRange);
                console.log("🎯 Semitone 값 범위:", Math.min(...semitoneValues).toFixed(2), "~", Math.max(...semitoneValues).toFixed(2));
                
                // 차트 Y축 범위를 적절한 semitone 범위로 설정
                const minSemitone = Math.min(...semitoneValues) - 2;
                const maxSemitone = Math.max(...semitoneValues) + 2;
                console.log(`🎯 Y축 semitone 범위 설정: ${minSemitone.toFixed(1)} ~ ${maxSemitone.toFixed(1)}`);
                
                // X축 시간 범위 계산
                const timeValues = refCurve.map(p => p.t);
                const minTime = Math.min(...timeValues);
                const maxTime = Math.max(...timeValues);
                const timePadding = (maxTime - minTime) * 0.05;
                
                console.log(`🎯 X축 시간 범위 설정: ${minTime.toFixed(2)} ~ ${maxTime.toFixed(2)}초`);
                
                // 차트 축 범위 직접 설정
                if (chart) {
                    chart.options.scales.y.min = minSemitone;
                    chart.options.scales.y.max = maxSemitone;
                    chart.options.scales.x.min = Math.max(0, minTime - timePadding);
                    chart.options.scales.x.max = maxTime + timePadding;
                    
                    // 입력 필드도 업데이트
                    if ($semitoneMin) $semitoneMin.value = minSemitone.toFixed(1);
                    if ($semitoneMax) $semitoneMax.value = maxSemitone.toFixed(1);
                }
                
                // 🎯🎯🎯 CRITICAL: Update Chart.js with reference data  
                console.log("🎯 refCurve 확인:", refCurve ? refCurve.length : "undefined", "points");
                console.log("🎯 chart 객체 확인:", typeof chart, chart ? "exists" : "undefined");
                
                if (refCurve && refCurve.length > 0) {
                    console.log("🔥 ANALYSIS FUNCTION CALLED!");
                    console.log("🔥 refCurve length:", refCurve.length);
                    console.log("🔥 refSyll length:", refSyll ? refSyll.length : "undefined");
                    console.log("🔥 js.syllable_analysis:", js.syllable_analysis ? js.syllable_analysis.length : "undefined");
                    console.log("🎯 Updating chart with reference data:", refCurve.length, "points");
                    console.log("🎯 Sample refCurve data:", refCurve.slice(0, 3));
                    
                    // Update chart data - 올바른 형식으로 변환
                    const chartData = refCurve.map(p => ({x: p.t, y: p.semitone || 0}));
                    chart.data.datasets[0].data = chartData;  // Dataset index 0 (참조 억양 패턴)
                    
                    // 🎯 실시간 피치를 위한 maxTime 캐시 (참조 데이터 접근 최소화)
                    if (chartData.length > 0) {
                        window.cachedMaxTime = Math.max(...chartData.map(p => p.x));
                        console.log("🎯 maxTime 캐시됨:", window.cachedMaxTime);
                    }
                    
                    console.log("🎯 Chart data updated:", chart.data.datasets[0].data.length, "points");
                    console.log("🎯 Sample chart data:", chartData.slice(0, 3));
                    
                    // 강제 차트 업데이트 (동기화)
                    chart.update('none');
                    
                    // 🎯 음절 중심점 데이터 추가 (주황색 점으로 정규화된 대표 피치 표시)
                    console.log("🔥 SYLLABLE CHECK: js.syllable_analysis =", js.syllable_analysis);
                    if (js.syllable_analysis && js.syllable_analysis.length > 0) {
                        console.log("🎯 정규화된 syllable_analysis 전체 데이터:", js.syllable_analysis);
                        console.log("🎯 남성 학습자 선택됨, 서버에서 받은 데이터 구조:");
                        
                        // 🎯 모든 학습자에게 정규화된 음절 대표 피치 표시
                        console.log(`🎯 정규화된 음절 대표 피치 표시 (학습자 성별: ${learnerGender})`);
                        
                        let syllableCenterPoints = [];
                        
                        if (true) {  // 모든 성별에게 정규화된 대표 피치 표시
                            syllableCenterPoints = js.syllable_analysis.map(syl => {
                                // 🎯 정규화된 semitone 값 직접 사용 (우선순위: semitone > semitone_median)
                                const semitoneValue = syl.semitone || syl.semitone_median || 0;
                                const timeValue = syl.center_time || ((syl.start_time || syl.start) + (syl.end_time || syl.end)) / 2;
                                
                                console.log(`🎯 음절 ${syl.label}: 시간=${timeValue.toFixed(3)}s, 세미톤=${semitoneValue.toFixed(2)}st, f0=${syl.f0 || 0}Hz`);
                                console.log(`🎯 CRITICAL - 음절 ${syl.label} 범위 확인: semitone=${semitoneValue} (차트 Y범위 내 여부 확인 필요)`);
                                
                                return {
                                    x: timeValue,
                                    y: semitoneValue,
                                    label: syl.label || syl.syllable || '',
                                    f0: syl.f0 || 0
                                };
                            });
                            
                            // 🎯 컨투어 일치성 검증 - 대표 피치가 곡선에서 너무 벗어나지 않는지 확인
                            syllableCenterPoints.forEach((point, index) => {
                                const nearby_curve_points = chartData.filter(cp => 
                                    Math.abs(cp.x - point.x) <= 0.1  // 100ms 범위 내
                                );
                                
                                if (nearby_curve_points.length > 0) {
                                    const nearby_semitones = nearby_curve_points.map(cp => cp.y);
                                    const curve_median = nearby_semitones.sort((a,b) => a-b)[Math.floor(nearby_semitones.length/2)];
                                    const semitone_diff = Math.abs(point.y - curve_median);
                                    
                                    // 1세미톤 이상 차이나면 로그 출력
                                    if (semitone_diff > 1.0) {
                                        console.log(`🎯 컨투어 일치성: ${point.label} 대표피치 ${point.y.toFixed(2)}st vs 곡선 ${curve_median.toFixed(2)}st (차이: ${semitone_diff.toFixed(2)}st)`);
                                    }
                                }
                            });
                        }
                        
                        // 🔥 중요: 음절 대표 피치 데이터 강제 업데이트
                        console.log("🔥 SYLLABLE CENTER POINTS:", syllableCenterPoints);
                        console.log("🔥 Chart datasets check:", chart.data.datasets.length);
                        console.log("🔥 Dataset 1 exists:", !!chart.data.datasets[1]);
                        
                        if (chart.data.datasets[1] && syllableCenterPoints.length > 0) {
                            chart.data.datasets[1].data = syllableCenterPoints;  // Dataset index 1 (음절 대표 피치)
                            // 🎯 차트 옵션 강제 활성화
                            chart.data.datasets[1].hidden = false;
                            console.log("🔥 ✅ 음절 중심점 추가:", syllableCenterPoints.length, "개 점");
                            console.log("🔥 ✅ Sample syllable center points:", syllableCenterPoints.slice(0, 3));
                            console.log("🔥 ✅ 🟠 음절 대표 피치 데이터셋 활성화됨");
                            
                            // 강제 차트 재렌더링
                            chart.update('none');
                        } else if (!chart.data.datasets[1]) {
                            console.error("🔥 ❌ Dataset 1 (음절 대표 피치)이 존재하지 않습니다!");
                            console.error("🔥 ❌ 현재 datasets 수:", chart.data.datasets.length);
                            console.error("🔥 ❌ Chart datasets:", chart.data.datasets.map((d, i) => `${i}: ${d.label}`));
                        } else {
                            console.error("🔥 ❌ syllableCenterPoints가 비어있습니다:", syllableCenterPoints.length);
                        }
                    } else {
                        console.log("🔥 ❌ syllable_analysis 데이터가 없습니다!");
                        console.log("🔥 ❌ js.syllable_analysis:", js.syllable_analysis);
                        console.log("🔥 ❌ typeof js.syllable_analysis:", typeof js.syllable_analysis);
                        console.log("🔥 ❌ js keys:", Object.keys(js));
                    }
                } else {
                    console.error("🎯 refCurve is empty or undefined:", refCurve);
                }
                
                
                // 🔥 음절별 구분선과 라벨 강제 추가
                try {
                    console.log("🎯 Adding syllable annotations:", refSyll ? refSyll.length : 0, "syllables");
                    console.log("🎯 refSyll 데이터:", refSyll);
                    
                    if (refSyll && refSyll.length > 0) {
                        addSyllableAnnotations(refSyll);
                        console.log("🎯 ✅ 음절 구분선과 보라색 라벨 추가 완료!");
                    } else {
                        console.log("🎯 ❌ refSyll 데이터가 없어서 annotation 건너뜀");
                        console.log("🎯 refSyll 상태:", typeof refSyll, refSyll);
                    }
                } catch (annotError) {
                    console.error("🎯 ❌ Annotation error:", annotError);
                }
                
                // 🔥 최종 차트 업데이트 (모든 변경사항 반영)
                try {
                    chart.update('none'); // 애니메이션 없이 즉시 업데이트
                    console.log("🎯 ✅ Chart updated successfully!");
                    console.log("🎯 현재 datasets 상태:", chart.data.datasets.map((d, i) => `${i}: ${d.label} (${d.data.length}개 점)`));
                    console.log("🎯 현재 annotations 수:", Object.keys(chart.options.plugins.annotation.annotations).length);
                    
                    // 🎯 annotations 목록 출력
                    const annotKeys = Object.keys(chart.options.plugins.annotation.annotations);
                    console.log("🎯 Annotation 키들:", annotKeys);
                    
                    // 🔥 Chart 데이터 확인
                    console.log("🔥 FINAL CHART STATE:");
                    console.log("🔥 Dataset 0 (참조곡선):", chart.data.datasets[0].data.length, "점");
                    console.log("🔥 Dataset 1 (음절피치):", chart.data.datasets[1].data.length, "점");
                    console.log("🔥 Dataset 1 sample data:", chart.data.datasets[1].data.slice(0, 3));
                    console.log("🔥 Annotations count:", Object.keys(chart.options.plugins.annotation.annotations).length);
                    
                } catch (updateError) {
                    console.error("🎯 ❌ Chart update error:", updateError);
                }
                
                // 🎯 녹음 가이드 업데이트
                const guideElement = document.getElementById('guide-text');
                const recordingGuide = document.getElementById('recording-guide');
                if (guideElement && refSyll && refSyll.length > 0) {
                    const syllableText = refSyll.map(s => s.label).join('');
                    guideElement.textContent = syllableText;
                    recordingGuide.style.display = 'block';
                }
                
                // Update syllable analysis table
                if (js.syllable_analysis) {
                    updateSyllableAnalysisTable(js.syllable_analysis);
                }
                
                $status.textContent = `🎯 표준 음성 분석 완료! 길이: ${refStats.duration.toFixed(2)}초, 음절: ${refSyll.length}개`;
                
                // 🎯 음절 라벨을 차트에 표시
                if (refSyll && refSyll.length > 0) {
                    addSyllableAnnotations(refSyll);
                    console.log(`🎯 음절 라벨 표시 완료: ${refSyll.length}개 음절`);
                }
                
                // 🎯 분석 완료 후 녹음 버튼 즉시 활성화
                if ($btnMic && refCurve.length > 0) {
                    $btnMic.disabled = false;
                    console.log("🎯 분석 완료! 녹음 버튼 강제 활성화");
                }
                
                // Update learning progress - analysis completed
                updateLearningProgress(2);
                
                // Save session data
                await saveSessionData({
                    type: 'reference_analysis',
                    stats: refStats,
                    syllable_count: refSyll.length,
                    timestamp: new Date().toISOString()
                });
                
                updateButtons();
                
            } catch (error) {
                console.error('🚨 Analysis error:', error);
                console.error('🚨 Error details:', error.stack);
                $status.textContent = "❌ 분석 실패: " + (error.message || "알 수 없는 오류");
                
                // 오류 상세 정보 추가 로그
                try {
                    if (error.response) {
                        console.error('🚨 Response status:', error.response.status);
                        const responseText = await error.response.text();
                        console.error('🚨 Response text:', responseText);
                    }
                } catch (responseError) {
                    console.error('🚨 Response error handling failed:', responseError);
                }
            } finally {
                $btnAnalyze.disabled = false;
                updateButtons();
            }
            };
            
            // 🛡️ 안전한 Promise 처리 - unhandledrejection 방지
            analyzeAsync().then(function() {
                console.log("✅ 분석 완료");
            }).catch(function(error) {
                console.error('🚨 안전하게 처리된 오류:', error);
                $status.textContent = "❌ 분석 실패: " + (error.message || "알 수 없는 오류");
            });
        };
    }

    // 🎯 통합 녹음 버튼 핸들러 (간단히 재작성)
    if ($btnMic) {
        console.log("🎯 녹음 버튼 이벤트 핸들러 설정 중...");
        
        // 🔥 기존 이벤트 완전 제거
        $btnMic.onclick = null;
        
        // 🎤 실시간 녹음 기능 구현
        $btnMic.addEventListener('click', async function(event) {
            event.preventDefault();
            event.stopPropagation();
            
            if (!started) {
                // 🎤 녹음 시작
                await startRealTimeRecording();
            } else {
                // 🎤 녹음 중지
                stopRealTimeRecording();
            }
        });
    } else {
        console.error('🚨 녹음 버튼을 찾을 수 없습니다!');
    }
    
    // 🎯 정지 버튼 핸들러 추가
    const $btnStopRecord = document.getElementById('btnStopRecord');
    if ($btnStopRecord) {
        $btnStopRecord.addEventListener('click', function(event) {
            event.preventDefault();
            event.stopPropagation();
            
            console.log('🛑 정지 버튼 클릭됨');
            
            // 🎤 실시간 녹음 중이면 중지
            if (started) {
                stopRealTimeRecording();
            }
            
            // 🎯 기존 통합 녹음도 중지 (호환성)
            if (typeof stopUnifiedRecording === 'function') {
                stopUnifiedRecording();
            }
        });
        console.log('🛑 정지 버튼 이벤트 핸들러 등록 완료');
    }

    // Chart Clear button handler
    if ($btnClearChart) {
        $btnClearChart.onclick = () => {
            console.log("🎯 차트 초기화 시작...");
            
            // Clear chart data only
            chart.data.datasets[0].data = [];  // Reference data (참조 억양 패턴)
            chart.data.datasets[1].data = [];  // 음절 대표 피치
            chart.data.datasets[2].data = [];  // 실시간 피치선
            
            // Clear current pitch line annotation
            if (chart.options.plugins.annotation && chart.options.plugins.annotation.annotations.currentPitchLine) {
                delete chart.options.plugins.annotation.annotations.currentPitchLine;
            }
            
            // 🧹 모든 annotation 완전 제거 (안전한 방식)
            if (chart && chart.options && chart.options.plugins && chart.options.plugins.annotation) {
                chart.options.plugins.annotation.annotations = {};
                chart.update('none');
                console.log("🧹 차트 초기화 - 음절 표시 제거 완료");
            }
            
            // 🎯 피치 테스트 상태 초기화
            targetPitch = null;
            pitchTestLine = null;
            
            // Reset analysis data
            refCurve = [];
            refSyll = [];
            refStats = {meanF0: 0, maxF0: 0, duration: 0};
            liveBuffer = [];
            
            // Update chart
            chart.update();
            console.log("🎯 차트 초기화 완료!");
            
            // Update status
            $status.textContent = "차트가 초기화되었습니다. 새로운 분석을 시작하세요.";
            
            // Update buttons
            updateButtons();
            updatePitchTestButtons();
            
            // 피치 테스트 상태 메시지 초기화
            if ($pitchTestStatus) {
                $pitchTestStatus.textContent = "차트에서 연습할 음높이를 클릭하세요";
                $pitchTestStatus.className = "text-center text-danger small fw-bold";
            }
        };
    }

    // Range update button handler
    if ($btnUpdateRange) {
        $btnUpdateRange.onclick = () => {
            const minVal = parseFloat($semitoneMin.value);
            const maxVal = parseFloat($semitoneMax.value);
            if (minVal < maxVal) {
                updateChartRange(minVal, maxVal);
            } else {
                alert('최소값은 최대값보다 작아야 합니다.');
            }
        };
    }

    // Reset button handler  
    if ($btnReset) {
        $btnReset.onclick = () => {
            // Stop recording if in progress
            if (mediaRecorder && mediaRecorder.state === 'recording') {
                mediaRecorder.stop();
            }
            
            if (procNode) {
                try {
                    procNode.disconnect();
                } catch (e) {
                    console.error('Error disconnecting processor:', e);
                }
            }
            
            if (audioCtx) {
                try {
                    audioCtx.close();
                } catch (e) {
                    console.error('Error closing audio context:', e);
                }
            }
            
            // Stop any playing audio
            stopAllAudio();
            
            // Reset audio data
            refAudioBlob = null;
            recordedAudioBlob = null;
            recordedChunks = [];
            
            liveBuffer = [];
            sylCuts = [];
            started = false;
            isListening = false; // 🎯 추가: 리셋 시 녹음 상태도 초기화
            tLive = 0;
            liveStats = {meanF0: 0, maxF0: 0};
            
            // Reset microphone button
            if ($btnMic) {
                $btnMic.innerHTML = '<i class="fas fa-microphone me-1"></i> 마이크 녹음';
                $btnMic.classList.remove('btn-danger');
                $btnMic.classList.add('btn-success');
            }
            
            chart.data.datasets[2].data = [];  // 실시간 피치선 초기화
            
            // Clear syllable annotations
            if (chart.options.plugins.annotation) {
                chart.options.plugins.annotation.annotations = {};
            }
            
            chart.update();
            
            $status.textContent = "초기화 완료. 새로운 분석을 시작할 수 있습니다.";
            
            updateButtons();
        };
    }

    // Audio playback handlers
    if ($btnPlayRef) {
        $btnPlayRef.onclick = playReferenceAudio;
    }
    
    if ($btnPlayRec) {
        $btnPlayRec.onclick = playRecordedAudio;
    }
    
    
    if ($btnReplayPractice) {
        $btnReplayPractice.onclick = function() { replayPracticeSession(); };
    }
    
    // Load saved files list
    loadSavedFilesList();
    
    // Saved files selection handler with auto-analysis
    if ($savedFiles) {
        $savedFiles.onchange = async () => {
            const fileId = $savedFiles.value;
            if (fileId) {
                console.log(`🎯 연습 문장 선택됨: ${fileId}`);
                
                // 🎯 학습자 성별 확인
                const learnerGender = document.getElementById('learner-gender').value;
                if (!learnerGender) {
                    alert('먼저 학습자 성별 정보를 선택해주세요.');
                    document.getElementById('learner-gender').focus();
                    return;
                }
                
                // 현재 선택된 문장 저장 (전역 변수)
                window.currentSelectedSentence = fileId;
                
                // 파일 로드
                await loadSelectedFile();
                updateDeleteButtonState();
                
                // 🎯 선택된 문장에 맞는 차트 데이터 즉시 로드
                try {
                    console.log(`🎯 문장별 데이터 로딩 시작: ${fileId} (학습자: ${learnerGender})`);
                    await loadSentenceForLearner(fileId);
                    console.log('🎯 차트 업데이트 완료!');
                    
                    // 🎯 상태 메시지 업데이트
                    $status.textContent = `✅ "${fileId}" 문장이 로드되었습니다. 참조음성 재생 또는 녹음 연습을 시작하세요.`;
                    
                    // 🎯 버튼 상태 업데이트
                    updateButtons();
                    
                } catch (error) {
                    console.error('🎯 문장 로딩 오류:', error);
                    $status.textContent = '문장 로딩 중 오류가 발생했습니다.';
                }
            } else {
                // 선택 해제시 차트 초기화
                window.currentSelectedSentence = null;
                if (chart) {
                    chart.data.datasets[0].data = [];
                    chart.data.datasets[1].data = [];
                    chart.data.datasets[2].data = [];
                    chart.options.plugins.annotation.annotations = {};
                    chart.update('none');
                }
                updateDeleteButtonState();
                $status.textContent = '연습할 문장을 선택해주세요.';
            }
        };
    }
    
    // Delete 기능 제거됨
    
    // Save reference button
    if ($btnSaveReference) {
        $btnSaveReference.onclick = showSaveModal;
    }
}

// Audio playback functions
function stopAllAudio() {
    if (currentlyPlaying) {
        currentlyPlaying.pause();
        currentlyPlaying = null;
    }
}

function playReferenceAudio() {
    // 🎵 선택된 문장이 있는 경우 해당 문장의 오디오 재생
    if (window.currentSelectedSentence) {
        const sentenceId = window.currentSelectedSentence;
        
        // 현재 재생 중인 오디오가 있으면 정지
        if (currentlyPlaying) {
            currentlyPlaying.pause();
            currentlyPlaying = null;
            $btnPlayRef.innerHTML = '<i class="fas fa-play me-1"></i> 참조음성 재생';
            $btnPlayRef.classList.remove('btn-danger');
            $btnPlayRef.classList.add('btn-info');
            return;
        }
        
        const audioUrl = `${API_BASE}/api/reference_files/${sentenceId}/wav`;
        const audio = new Audio(audioUrl);
        
        // 🎵 피치 조정 적용 (재생 속도 조정으로 피치 변경)
        const playbackRate = Math.pow(2, pitchOffsetSemitones / 12);
        audio.playbackRate = playbackRate;
        
        if (pitchOffsetSemitones !== 0) {
            console.log(`🎵 피치 조정 적용: ${pitchOffsetSemitones}키 (재생속도: ${playbackRate.toFixed(3)})`);
        }
        
        audio.onplay = () => {
            currentlyPlaying = audio;
            $btnPlayRef.innerHTML = '<i class="fas fa-stop me-1"></i> 참조음성 정지';
            $btnPlayRef.classList.remove('btn-info');
            $btnPlayRef.classList.add('btn-danger');
        };
        
        audio.onended = audio.onpause = () => {
            currentlyPlaying = null;
            $btnPlayRef.innerHTML = '<i class="fas fa-play me-1"></i> 참조음성 재생';
            $btnPlayRef.classList.remove('btn-danger');
            $btnPlayRef.classList.add('btn-info');
        };
        
        audio.onerror = () => {
            console.error('Error playing reference audio for', sentenceId);
            $status.textContent = '참조 음성 재생 오류';
            currentlyPlaying = null;
            $btnPlayRef.innerHTML = '<i class="fas fa-play me-1"></i> 참조음성 재생';
            $btnPlayRef.classList.remove('btn-danger');
            $btnPlayRef.classList.add('btn-info');
        };
        
        audio.play().catch(e => {
            console.error('Error playing audio:', e);
            $status.textContent = '음성 재생 오류';
        });
        return;
    }
    
    // 기존 파일 업로드 방식
    if (!$wav || !$wav.files || $wav.files.length === 0) {
        console.log('No reference audio file available');
        return;
    }
    
    stopAllAudio();
    
    const audioFile = $wav.files[0];
    const audioUrl = URL.createObjectURL(audioFile);
    const audio = new Audio(audioUrl);
    
    // 🎵 피치 조정 적용 (재생 속도 조정으로 피치 변경)
    const playbackRate = Math.pow(2, pitchOffsetSemitones / 12);
    audio.playbackRate = playbackRate;
    
    if (pitchOffsetSemitones !== 0) {
        console.log(`🎵 업로드 파일 피치 조정 적용: ${pitchOffsetSemitones}키 (재생속도: ${playbackRate.toFixed(3)})`);
    }
    
    audio.onplay = () => {
        currentlyPlaying = audio;
        $btnPlayRef.innerHTML = '<i class="fas fa-stop me-1"></i> 참조음성 정지';
        $btnPlayRef.classList.remove('btn-info');
        $btnPlayRef.classList.add('btn-danger');
    };
    
    audio.onended = audio.onpause = () => {
        currentlyPlaying = null;
        $btnPlayRef.innerHTML = '<i class="fas fa-play me-1"></i> 참조음성 재생';
        $btnPlayRef.classList.remove('btn-danger');
        $btnPlayRef.classList.add('btn-info');
        URL.revokeObjectURL(audioUrl);
    };
    
    audio.onerror = () => {
        console.error('Error playing reference audio');
        $status.textContent = '참조 음성 재생 오류';
        currentlyPlaying = null;
        $btnPlayRef.innerHTML = '<i class="fas fa-play me-1"></i> 참조음성 재생';
        $btnPlayRef.classList.remove('btn-danger');
        $btnPlayRef.classList.add('btn-info');
        URL.revokeObjectURL(audioUrl);
    };
    
    if (currentlyPlaying === audio) {
        audio.pause();
        currentlyPlaying = null;
    } else {
        audio.play().catch(e => {
            console.error('Error playing audio:', e);
            $status.textContent = '음성 재생 오류';
        });
    }
}

function playRecordedAudio() {
    if (!recordedAudioBlob) {
        console.log('No recorded audio available');
        return;
    }
    
    stopAllAudio();
    
    const audioUrl = URL.createObjectURL(recordedAudioBlob);
    const audio = new Audio(audioUrl);
    
    audio.onplay = () => {
        currentlyPlaying = audio;
        $btnPlayRec.innerHTML = '<i class="fas fa-stop me-1"></i> 녹음음성 정지';
        $btnPlayRec.classList.remove('btn-warning');
        $btnPlayRec.classList.add('btn-danger');
    };
    
    audio.onended = audio.onpause = () => {
        currentlyPlaying = null;
        $btnPlayRec.innerHTML = '<i class="fas fa-play me-1"></i> 녹음음성 재생';
        $btnPlayRec.classList.remove('btn-danger');
        $btnPlayRec.classList.add('btn-warning');
        URL.revokeObjectURL(audioUrl);
    };
    
    audio.onerror = () => {
        console.error('Error playing recorded audio');
        $status.textContent = '녹음 음성 재생 오류';
        currentlyPlaying = null;
        $btnPlayRec.innerHTML = '<i class="fas fa-play me-1"></i> 녹음음성 재생';
        $btnPlayRec.classList.remove('btn-danger');
        $btnPlayRec.classList.add('btn-warning');
        URL.revokeObjectURL(audioUrl);
    };
    
    if (currentlyPlaying === audio) {
        audio.pause();
        currentlyPlaying = null;
    } else {
        audio.play().catch(e => {
            console.error('Error playing audio:', e);
            $status.textContent = '음성 재생 오류';
        });
    }
}

// Add event listeners with better error handling

console.log('ToneBridge audio-analysis.js loaded');

// 🎯 현재 Y축 단위 (semitone 또는 qtone)
let currentYAxisUnit = 'semitone';

// 🎧 실시간 피드백을 위한 초고감도 임계값 - 즉각적인 반응성 우선
const PERCEPTUAL_THRESHOLDS = {
    'semitone': 0.05,  // 0.05 세미톤 - 초고감도 (즉각 반응)
    'qtone': 0.1       // 0.1 Q-tone - 초고감도 (즉각 반응)
};

// 🎵 이전 피치 값 (필터링용)
let lastPerceptiblePitch = null;

// 🎬 실시간 연습 시각화 저장/재생 기능
let practiceRecordingData = []; // 연습 중 실시간 데이터 저장
let isRecordingPractice = false; // 연습 데이터 저장 중인지 여부
let replayInterval = null; // 재생 타이머

// 🎬 연습 세션 재생 기능
function replayPracticeSession() {
    if (!practiceRecordingData || practiceRecordingData.length === 0) {
        alert('저장된 연습 데이터가 없습니다.');
        return;
    }
    
    if (replayInterval) {
        // 재생 중지
        clearInterval(replayInterval);
        replayInterval = null;
        $btnReplayPractice.innerHTML = '<i class="fas fa-history me-1"></i> 연습 재생';
        $btnReplayPractice.classList.remove('btn-danger');
        $btnReplayPractice.classList.add('btn-warning');
        
        // 라이브 데이터 차트 클리어 
        if (chart && chart.data.datasets[2]) {
            chart.data.datasets[2].data = [];  // 실시간 피치선 초기화
            chart.update('none');
        }
        return;
    }
    
    // 재생 시작
    console.log(`🎬 연습 재생 시작: ${practiceRecordingData.length}개 포인트`);
    
    // 버튼 상태 변경
    $btnReplayPractice.innerHTML = '<i class="fas fa-stop me-1"></i> 재생 중지';
    $btnReplayPractice.classList.remove('btn-warning');
    $btnReplayPractice.classList.add('btn-danger');
    
    // 재생용 임시 데이터
    const replayData = [];
    let currentIndex = 0;
    
    // 시작 시간 기준으로 정규화
    const startTime = practiceRecordingData[0].time;
    const endTime = practiceRecordingData[practiceRecordingData.length - 1].time;
    const duration = endTime - startTime;
    
    console.log(`🎬 재생 시간: ${duration.toFixed(1)}초`);
    
    // 재생 타이머 (50ms 간격으로 재생)
    replayInterval = setInterval(() => {
        if (currentIndex >= practiceRecordingData.length) {
            // 재생 완료
            clearInterval(replayInterval);
            replayInterval = null;
            $btnReplayPractice.innerHTML = '<i class="fas fa-history me-1"></i> 연습 재생';
            $btnReplayPractice.classList.remove('btn-danger');
            $btnReplayPractice.classList.add('btn-warning');
            console.log('🎬 연습 재생 완료');
            return;
        }
        
        // 현재 포인트를 차트에 추가
        const currentPoint = practiceRecordingData[currentIndex];
        replayData.push({
            x: currentPoint.time,
            y: currentPoint.pitch
        });
        
        // 차트 업데이트
        if (chart && chart.data.datasets[1]) {
            chart.data.datasets[1].data = [...replayData];
            chart.update('none');
        }
        
        currentIndex++;
        
        // 진행 상황 로그 (가끔씩만)
        if (currentIndex % 20 === 0) {
            const progress = ((currentIndex / practiceRecordingData.length) * 100).toFixed(1);
            console.log(`🎬 재생 진행: ${progress}%`);
        }
    }, 50); // 50ms 간격으로 재생 (부드러운 재생)
}

// 🎯 Y축 단위 토글 이벤트 리스너
function setupYAxisToggle() {
    const semitoneRadio = document.getElementById('yAxisSemitone');
    const qtoneRadio = document.getElementById('yAxisQtone');
    
    if (semitoneRadio) {
        semitoneRadio.addEventListener('change', function() {
            if (this.checked) {
                currentYAxisUnit = 'semitone';
                lastPerceptiblePitch = null; // 단위 변경 시 필터링 초기화
                updateChartYAxis();
            }
        });
    }
        
    if (qtoneRadio) {
        qtoneRadio.addEventListener('change', function() {
            if (this.checked) {
                currentYAxisUnit = 'qtone';
                lastPerceptiblePitch = null; // 단위 변경 시 필터링 초기화
                updateChartYAxis();
            }
        });
    }
        
    console.log('🎯 Y축 단위 토글 이벤트 리스너 설정 완료');
}

// 🎯 차트 Y축 업데이트
function updateChartYAxis() {
    if (!chart) return;
    
    const refFreq = refMedian || 200;
    let minValue, maxValue;
    
    if (currentYAxisUnit === 'qtone') {
        // Q-tone 기본 범위: 0~25 등급 전체 사용
        minValue = 0;
        maxValue = 25;
        
        // Input 필드를 Q-tone 값으로 업데이트
        $semitoneMin.value = Math.round(minValue * 10) / 10;
        $semitoneMax.value = Math.round(maxValue * 10) / 10;
        
        // 단위 표시를 "qt"로 변경
        const unitLabel = document.querySelector('small.text-muted:nth-of-type(3)');
        if (unitLabel) unitLabel.textContent = 'qt';
        
        chart.options.scales.y.min = minValue;
        chart.options.scales.y.max = maxValue;
        chart.options.scales.y.title.text = `Q-tone (0~25 등급, 기준: ${refFreq.toFixed(0)}Hz=12qt)`;
        
    } else {
        // Semitone 기본 범위: -12 ~ 15 세미톤 (기본값 확장)
        minValue = parseFloat($semitoneMin.value) || -12;
        maxValue = parseFloat($semitoneMax.value) || 15;
        
        // Input 필드를 Semitone 값으로 업데이트
        $semitoneMin.value = Math.round(minValue);
        $semitoneMax.value = Math.round(maxValue);
        
        // 단위 표시를 "st"로 변경
        const unitLabel = document.querySelector('small.text-muted:nth-of-type(3)');
        if (unitLabel) unitLabel.textContent = 'st';
        
        chart.options.scales.y.min = minValue;
        chart.options.scales.y.max = maxValue;
        chart.options.scales.y.title.text = `Semitone (기준: ${refFreq.toFixed(0)}Hz)`;
    }
    
    // 🎯 Y축 단위 변경 시 참조 데이터를 새로운 단위로 변환하여 표시
    if (refCurve && refCurve.length > 0) {
        updateChartWithReferenceData();
    }
    
    chart.update();
    console.log(`🎯 Y축 단위 변경: ${currentYAxisUnit}, 범위: ${minValue.toFixed(1)} ~ ${maxValue.toFixed(1)}`);
}

// 🎯 참조 데이터로 차트 업데이트 (Y축 단위 변경에 대응)
function updateChartWithReferenceData() {
    if (!chart || !refCurve || refCurve.length === 0) return;
    
    // 🎯 참조 곡선 데이터를 현재 Y축 단위로 변환
    const convertedRefData = refCurve.map(point => {
        let yValue;
        if (currentYAxisUnit === 'qtone') {
            // f0를 Q-tone으로 변환 (실제 refCurve 구조 사용)
            yValue = f0ToQt(point.f0);
        } else {
            // f0를 semitone으로 변환 (이미 semitone 값이 있으면 사용)
            yValue = point.semitone || f0ToSemitone(point.f0, refMedian || 200);
        }
        return { x: point.t, y: yValue };  // refCurve의 실제 속성명 사용: t, f0, semitone
    });
    
    // 🎯 Y축 단위 변경 시에도 maxTime 캐시 갱신
    if (convertedRefData.length > 0) {
        window.cachedMaxTime = Math.max(...convertedRefData.map(p => p.x));
        console.log("🎯 Y축 변경 - maxTime 캐시됨:", window.cachedMaxTime);
    }
    
    // 🎯 차트에 변환된 데이터 적용
    if (chart.data.datasets[0]) {
        chart.data.datasets[0].data = convertedRefData;
    }
    
    console.log(`🎯 참조 데이터 Y축 단위 변환 완료: ${convertedRefData.length}개 포인트`);
}


document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded - initializing...');
    
    // Initialize DOM elements
    initializeElements();
    
    // Setup all event handlers
    setupEventHandlers();
    
    // Setup Y-axis unit toggle
    setupYAxisToggle();
    
    // Initial button state
    setTimeout(updateButtons, 100);
});

// 🎯 스펙트로그램 배경 렌더링 함수 (사용자 요청)
function renderSpectrogramOnCanvas(chartInstance, spectrogramDataArray) {
    if (!spectrogramDataArray || spectrogramDataArray.length === 0) return;
    
    const ctx = chartInstance.ctx;
    const chartArea = chartInstance.chartArea;
    const xScale = chartInstance.scales.x;
    const yScale = chartInstance.scales.y;
    
    console.log(`🎯 캔버스에 스펙트로그램 그리기: ${spectrogramDataArray.length}개 시점`);
    
    // 스펙트로그램 그리기
    for (let i = 0; i < spectrogramDataArray.length; i++) {
        const specPoint = spectrogramDataArray[i];
        const x = xScale.getPixelForValue(specPoint.t);
        
        if (x < chartArea.left || x > chartArea.right) continue;
        
        // 주파수 대역별로 색상 강도 표시
        if (specPoint.spec && specPoint.spec.length > 0) {
            const freqStep = (specPoint.freq_max || 1000) / specPoint.spec.length;
            const rectWidth = Math.max(3, (chartArea.right - chartArea.left) / spectrogramDataArray.length);
            
            for (let j = 0; j < specPoint.spec.length; j++) {
                const freq = j * freqStep;
                const intensity = specPoint.spec[j];
                
                // 주파수가 Y축 범위 내에 있는지 확인
                if (freq < yScale.min || freq > yScale.max) continue;
                
                const y = yScale.getPixelForValue(freq);
                const rectHeight = Math.max(2, Math.abs(freqStep * (chartArea.bottom - chartArea.top) / (yScale.max - yScale.min)));
                
                // dB 값을 색상 강도로 변환 (-80dB ~ 0dB -> 0 ~ 0.5)
                const alpha = Math.max(0, Math.min(0.5, (intensity + 80) / 80 * 0.5));
                
                // 스펙트로그램 색상 (파란색 계열) - 더 진하게
                if (alpha > 0.1) {  // 너무 약한 신호는 표시하지 않음
                    ctx.fillStyle = `rgba(100, 150, 255, ${alpha})`;
                    ctx.fillRect(x - rectWidth/2, y - rectHeight/2, rectWidth, rectHeight);
                }
            }
        }
    }
}

// Fallback - if DOMContentLoaded already fired
if (document.readyState === 'loading') {
    // Do nothing, DOMContentLoaded will handle it
} else {
    console.log('Document already loaded, initializing immediately');
    setTimeout(function() {
        initializeElements();
        setupEventHandlers();
        setupYAxisToggle();
        updateButtons();
    }, 10);
}

// Initialize Chart.js with annotation plugin
// 플러그인 등록 확인
function checkAnnotationPlugin() {
    if (typeof Chart !== 'undefined') {
        try {
            if (Chart.registry && Chart.registry.plugins.get('annotation')) {
                console.log('🎯 Chart.js annotation 플러그인이 등록되어 있습니다');
                return true;
            } else {
                console.log('🎯 Chart.js annotation 플러그인이 이미 등록되어 있습니다');
                return true; // 기본적으로 true 반환하여 오류 방지
            }
        } catch (e) {
            console.log('🎯 Chart.js annotation 체크 중 오류, 기본값 사용');
            return true;
        }
    } else {
        console.warn('⚠️ Chart.js가 로드되지 않았습니다');
        return false;
    }
}

// 플러그인 체크 (오류 방지)
try {
    checkAnnotationPlugin();
} catch (e) {
    console.log('🎯 Chart.js annotation 플러그인 체크 생략');
}

const chart = new Chart(document.getElementById('chart'), {
    type: "line",
    data: {
        datasets: [
            {
                label: "참조 억양 패턴",
                data: [],
                parsing: false,
                borderWidth: 3,
                pointRadius: 0,  // 점 제거
                borderDash: [8, 4],  // 도트선 패턴
                borderColor: 'rgb(54, 162, 235)',  // 파란색
                backgroundColor: 'transparent',
                tension: 0,
                order: 1
            },
            {
                label: "🟠 음절 대표 음도",
                data: [],
                parsing: false,
                borderWidth: 0,
                pointRadius: 10,
                pointBackgroundColor: 'rgba(255, 140, 0, 0.9)',
                pointBorderColor: 'rgba(255, 255, 255, 1)',
                pointBorderWidth: 3,
                pointHoverRadius: function(context) {
                    // 🎯 녹음 중에는 호버 효과 비활성화
                    return isListening ? 10 : 12;
                },
                pointHoverBackgroundColor: function(context) {
                    // 🎯 녹음 중에는 호버 색상 변경 없음
                    return isListening ? 'rgba(255, 140, 0, 0.9)' : 'rgba(255, 180, 50, 1)';
                },
                pointHoverBorderColor: function(context) {
                    // 🎯 녹음 중에는 호버 테두리 변경 없음
                    return isListening ? 'rgba(255, 255, 255, 1)' : 'rgba(255, 255, 255, 1)';
                },
                showLine: false,
                yAxisID: "y",
                order: 2,
                type: 'scatter'
            },
            {
                label: "🟢 실시간 음도선",
                data: [],
                parsing: false,
                borderWidth: 4,
                pointRadius: 0,  // 점 제거
                borderColor: 'rgba(34, 197, 94, 0.9)',  // 초록색 실선
                backgroundColor: 'transparent',
                yAxisID: "y",
                showLine: true,  // 짧은 가로선 표시
                tension: 0,
                order: 3
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
            duration: 0  // 애니메이션 지연 없이 즉시 업데이트
        },
        plugins: {
            legend: {
                position: 'top',
                align: 'center',  // 중앙 정렬
                labels: {
                    usePointStyle: true,  // 점 스타일 사용
                    pointStyle: 'line',   // 모든 항목을 선 스타일로
                    boxWidth: 40,         // 아이콘 크기
                    padding: 15           // 아이템 간 여백
                }
            },
            tooltip: {
                mode: 'index',
                intersect: false,
                filter: function(tooltipItem) {
                    // 🎯 녹음 중에는 툴팁 비활성화
                    return !isListening;
                }
            },
            annotation: {
                annotations: {},
                // 🔥 annotation plugin 강제 활성화
                display: true
            }
        },
        layout: {
            padding: 10
        },
        backgroundColor: '#ffffff',
        onClick: (event, activeElements, chart) => {
            // 🎯 차트 클릭 시 음높이 테스트 모드
            handleChartClick(event, chart);
        },
        scales: {
            x: {
                type: 'linear',
                title: {
                    display: true,
                    text: '시간 (초)',
                    font: {
                        size: 10
                    },
                    position: 'end',
                    align: 'end'
                }
            },
            y: {
                min: -12,
                max: 15,
                title: {
                    display: true,
                    text: 'Semitone (반음계)'
                }
            },
        },
        interaction: {
            mode: 'nearest',
            axis: 'x',
            intersect: false
        },
        onHover: (evt, elements) => {
            // 🎯 녹음 중에는 호버 기능 비활성화
            if (isListening) return;
            
            // 🎯 음높이 학습 모드에서만 호버 효과 활성화
            const learningMethod = document.querySelector('input[name="learning-method"]:checked')?.value;
            if (learningMethod !== 'pitch' || !chart) return;
            
            const canvasPos = Chart.helpers.getRelativePosition(evt, chart);
            const dataY = chart.scales.y.getValueForPixel(canvasPos.y);
            
            if (isSelecting && rangeStart !== null) {
                // Show preview of selection range
                updateRangePreview(rangeStart, dataY);
            }
        },
        onClick: (evt, elements) => {
            if (!chart) return;
            
            // 🎯 음높이 학습 모드에서만 클릭/드래그 기능 활성화
            const learningMethod = document.querySelector('input[name="learning-method"]:checked')?.value;
            if (learningMethod !== 'pitch') return;
            
            const canvasPos = Chart.helpers.getRelativePosition(evt, chart);
            const dataY = chart.scales.y.getValueForPixel(canvasPos.y);
            
            // 🎯 유효한 세미톤 범위인지 확인
            if (dataY < -15 || dataY > 20) return;
            
            if (!isSelecting) {
                // 🎯 첫 번째 클릭: 단일 피치 또는 범위 시작
                rangeStart = dataY;
                isSelecting = true;
                targetPitch = dataY; // 단일 클릭으로도 목표 피치 설정
                
                // 🎯 단일 피치 선을 즉시 표시
                addPitchReferenceLine(dataY);
                
                console.log(`🎯 목표 피치 설정: ${dataY.toFixed(1)} 세미톤 (단일 클릭)`);
                
                if ($pitchTestStatus) {
                    $pitchTestStatus.innerHTML = `
                        <div class="text-center">
                            <strong>목표 피치: ${dataY.toFixed(1)} 세미톤 설정됨</strong><br>
                            <small>다시 클릭하면 범위 연습 / "음높이 테스트" 버튼으로 시작</small>
                        </div>
                    `;
                    $pitchTestStatus.className = "text-center text-info small";
                }
                
                // 🎯 버튼 상태 업데이트
                updatePitchTestButtons();
                
                // 🎯 3초 후 자동으로 선택 모드 해제 (단일 클릭으로 인식)
                setTimeout(() => {
                    if (isSelecting && rangeStart === dataY) {
                        isSelecting = false;
                        rangeStart = null;
                        console.log('🎯 단일 클릭 모드로 확정');
                    }
                }, 3000);
                
            } else {
                // 🎯 두 번째 클릭: 범위 설정 완료
                rangeEnd = dataY;
                isSelecting = false;
                
                // Ensure start is lower than end
                const minRange = Math.min(rangeStart, rangeEnd);
                const maxRange = Math.max(rangeStart, rangeEnd);
                
                // 🎯 최소 범위 확인 (최소 1 세미톤 차이)
                if (Math.abs(maxRange - minRange) < 1) {
                    // 범위가 너무 작으면 단일 피치로 처리
                    targetPitch = rangeStart;
                    pitchRange = null;
                    
                    if ($pitchTestStatus) {
                        $pitchTestStatus.innerHTML = `
                            <div class="text-center">
                                <strong>목표 피치: ${rangeStart.toFixed(1)} 세미톤</strong><br>
                                <small>범위가 너무 작아서 단일 피치로 설정됨</small>
                            </div>
                        `;
                        $pitchTestStatus.className = "text-center text-info small";
                    }
                } else {
                    // 범위 설정
                    createPitchRange(minRange, maxRange);
                    pitchRange = {min: minRange, max: maxRange};
                    targetPitch = (minRange + maxRange) / 2; // 범위의 중간값
                    
                    console.log(`🎯 범위 연습 설정: ${minRange.toFixed(1)} ~ ${maxRange.toFixed(1)} 세미톤`);
                    
                    if ($pitchTestStatus) {
                        $pitchTestStatus.innerHTML = `
                            <div class="text-center">
                                <strong>연습 범위: ${minRange.toFixed(1)} ~ ${maxRange.toFixed(1)} 세미톤</strong><br>
                                <small>목표: ${targetPitch.toFixed(1)} 세미톤 (중심)</small>
                            </div>
                        `;
                        $pitchTestStatus.className = "text-center text-success small";
                    }
                }
                
                // 🎯 음높이 테스트 버튼 상태 업데이트
                updatePitchTestButtons();
                
                rangeStart = null;
                rangeEnd = null;
            }
        }
    }
});

// Update chart range based on inputs or data
function updateChartRange(minVal = null, maxVal = null) {
    const currentMin = minVal !== null ? minVal : parseFloat($semitoneMin?.value || -12);
    const currentMax = maxVal !== null ? maxVal : parseFloat($semitoneMax?.value || 15);
    
    if (chart) {
        // Y축 범위 설정 (semitone)
        chart.options.scales.y.min = currentMin;
        chart.options.scales.y.max = currentMax;
        
        // X축 범위를 적절한 시간 범위로 설정
        if (refCurve && refCurve.length > 0) {
            const timeValues = refCurve.map(p => p.t || p.x);
            if (timeValues.length > 0 && timeValues.every(t => typeof t === 'number')) {
                const minTime = Math.min(...timeValues);
                const maxTime = Math.max(...timeValues);
                const padding = (maxTime - minTime) * 0.05; // 5% 여백
                
                chart.options.scales.x.min = Math.max(0, minTime - padding);
                chart.options.scales.x.max = maxTime + padding;
                
                console.log(`🔍 X축 시간 범위: ${(minTime - padding).toFixed(2)} ~ ${(maxTime + padding).toFixed(2)}초`);
            }
        }
        
        // 범위가 바뀌면 음절 라벨 위치도 다시 계산
        if (refSyll && refSyll.length > 0) {
            addSyllableAnnotations(refSyll);
        }
        
        const unitName = currentYAxisUnit === 'qtone' ? 'Q-tone' : 'semitone';
        const unitSymbol = currentYAxisUnit === 'qtone' ? 'qt' : 'st';
        
        if ($status) {
            $status.textContent = `표시 범위가 ${currentMin}~${currentMax} ${unitSymbol}로 변경되었습니다`;
            setTimeout(() => $status.textContent = '', 2000);
        }
        
        chart.update();
        console.log(`🎯 Chart range updated: ${currentMin} to ${currentMax} ${unitName}`);
    }
    
    // Update input values
    if ($semitoneMin) $semitoneMin.value = currentMin;
    if ($semitoneMax) $semitoneMax.value = currentMax;
    
}

// 🎯 학습자 성별에 따른 기준 주파수 가져오기
function getGenderBaseFrequency() {
    if (learnerGender === 'male') {
        return 120.0; // 남성 기준
    } else if (learnerGender === 'female') {
        return 220.0; // 여성 기준
    } else {
        return refMedian || 200; // 기본값
    }
}

// 🎯 학습자 성별에 따른 Hz 범위 가져오기
function getGenderHzRange() {
    if (learnerGender === 'male') {
        return {
            min: 60,
            max: 250,
            label: '남성 Hz (60-250Hz)'
        };
    } else if (learnerGender === 'female') {
        return {
            min: 120,
            max: 450,
            label: '여성 Hz (120-450Hz)'
        };
    } else {
        return {
            min: 80,
            max: 400,
            label: '실시간 Hz'
        };
    }
}

// 🎯 세미톤과 Qt를 Hz로 변환해서 범위 표시 (성별 기준 적용)
function updateFrequencyRangeDisplay(minSemitone, maxSemitone) {
    if (!$freqRangeDisplay) return;
    
    const baseFreq = getGenderBaseFrequency(); // 학습자 성별 기준
    const minHz = (baseFreq * Math.pow(2, minSemitone / 12)).toFixed(1);
    const maxHz = (baseFreq * Math.pow(2, maxSemitone / 12)).toFixed(1);
    
    // 🎯 Qt 단위로도 계산 (110 Hz 기준)
    const minQt = f0ToQt(minHz);
    const maxQt = f0ToQt(maxHz);
    
    const genderText = learnerGender === 'male' ? '남성' : learnerGender === 'female' ? '여성' : '기본';
    
    $freqRangeDisplay.innerHTML = `
        <div>Hz: ${minHz}~${maxHz} (${genderText} 기준: ${baseFreq.toFixed(1)}Hz)</div>
        <div class="small text-muted">Qt: ${minQt.toFixed(1)}~${maxQt.toFixed(1)} (음성학 기준: 110Hz)</div>
    `;
    
    console.log(`🎯 Frequency range: ${minHz}-${maxHz} Hz (${genderText} 기준: ${baseFreq}Hz)`);
    console.log(`🎯 Qt range: ${minQt.toFixed(1)}-${maxQt.toFixed(1)} Qt (기준: 110Hz)`);
}

// 🎯 실시간 Hz 표시 업데이트 (음높이 테스트 전용)
function updateLiveHzDisplay(currentHz) {
    if (!chart || !chart.data.datasets[3] || !pitchTestActive) return;
    
    const liveHzDataset = chart.data.datasets[3];
    if (!liveHzDataset.data) liveHzDataset.data = [];
    
    // 🎯 현재 시점에서 Hz 값을 y1 축에 표시 (시간은 현재 차트 범위 중앙)
    const currentTime = Date.now() / 1000;
    const chartTimeRange = 5; // 5초 범위
    const relativeTime = (currentTime % chartTimeRange);
    
    // 기존 데이터 클리어 (실시간 단일 포인트만 표시)
    liveHzDataset.data = [{
        x: relativeTime,
        y: Math.max(80, Math.min(400, parseFloat(currentHz.toFixed(1)))) // y1 축 범위에 맞게 제한, 소수점 1자리
    }];
    
    chart.update('none'); // 애니메이션 없이 업데이트
}

// 🎯 음높이 범위 생성 (노란색 배경)
function createPitchRange(minSemitone, maxSemitone) {
    if (!chart) return;
    
    // 기존 범위 제거
    clearPitchRange();
    
    // Chart.js annotation으로 노란색 배경 영역 추가
    const rangeAnnotation = {
        type: 'box',
        yMin: minSemitone,
        yMax: maxSemitone,
        backgroundColor: 'rgba(255, 255, 0, 0.2)', // 노란색 반투명
        borderColor: 'rgba(255, 255, 0, 0.8)',
        borderWidth: 2,
        label: {
            enabled: true,
            content: `연습 범위: ${minSemitone.toFixed(1)}~${maxSemitone.toFixed(1)}`,
            position: 'start',
            backgroundColor: 'rgba(255, 255, 0, 0.8)',
            color: 'black',
            font: {
                size: 12,
                weight: 'bold'
            }
        }
    };
    
    // 상단 및 하단 참조선 추가
    const topLine = {
        type: 'line',
        yMin: maxSemitone,
        yMax: maxSemitone,
        borderColor: 'rgba(255, 165, 0, 1)',
        borderWidth: 1,
        borderDash: [5, 5]
    };
    
    const bottomLine = {
        type: 'line',
        yMin: minSemitone,
        yMax: minSemitone,
        borderColor: 'rgba(255, 165, 0, 1)',
        borderWidth: 1,
        borderDash: [5, 5]
    };
    
    // annotation 플러그인에 추가
    if (!chart.options.plugins.annotation) {
        chart.options.plugins.annotation = { annotations: {} };
    }
    
    chart.options.plugins.annotation.annotations['pitchRange'] = rangeAnnotation;
    chart.options.plugins.annotation.annotations['topLine'] = topLine;
    chart.options.plugins.annotation.annotations['bottomLine'] = bottomLine;
    
    chart.update();
    
    console.log(`🎯 음높이 연습 범위 생성: ${minSemitone.toFixed(1)}~${maxSemitone.toFixed(1)} 세미톤`);
}

// 🎯 범위 미리보기 (드래그 중)
function updateRangePreview(startY, currentY) {
    if (!chart) return;
    
    const minY = Math.min(startY, currentY);
    const maxY = Math.max(startY, currentY);
    
    // 미리보기 annotation 업데이트
    if (!chart.options.plugins.annotation) {
        chart.options.plugins.annotation = { annotations: {} };
    }
    
    chart.options.plugins.annotation.annotations['previewRange'] = {
        type: 'box',
        yMin: minY,
        yMax: maxY,
        backgroundColor: 'rgba(255, 255, 0, 0.1)',
        borderColor: 'rgba(255, 255, 0, 0.5)',
        borderWidth: 2,
        borderDash: [10, 5]
    };
    
    chart.update('none');
}

// 🎯 음높이 범위 제거
function clearPitchRange() {
    if (!chart || !chart.options.plugins.annotation) return;
    
    delete chart.options.plugins.annotation.annotations['pitchRange'];
    delete chart.options.plugins.annotation.annotations['topLine'];
    delete chart.options.plugins.annotation.annotations['bottomLine'];
    delete chart.options.plugins.annotation.annotations['previewRange'];
    
    chart.update();
    
    console.log('🎯 음높이 연습 범위 제거');
}

// Calculate optimal range based on semitone data
function calculateOptimalRange(semitoneValues) {
    if (!semitoneValues || semitoneValues.length === 0) return {min: -12, max: 15};
    
    const validValues = semitoneValues.filter(v => v !== null && !isNaN(v));
    if (validValues.length === 0) return {min: -12, max: 15};
    
    const minValue = Math.min(...validValues);
    const maxValue = Math.max(...validValues);
    
    // Add padding (약 20% 여유)
    const padding = Math.max(2, (maxValue - minValue) * 0.2);
    const suggestedMin = Math.floor(minValue - padding);
    const suggestedMax = Math.ceil(maxValue + padding);
    
    return {min: suggestedMin, max: suggestedMax};
}

// Function to add syllable annotations to the chart
function addSyllableAnnotations(syllables) {
    if (!syllables || syllables.length === 0) {
        console.log("🎯 addSyllableAnnotations: syllables가 비어있습니다");
        return;
    }
    
    // 🧹 annotation plugin 존재 확인 및 초기화
    if (!chart || !chart.options || !chart.options.plugins) {
        console.error("🎯 Chart 구조 문제:", chart);
        return;
    }
    
    if (!chart.options.plugins.annotation) {
        chart.options.plugins.annotation = { annotations: {}, display: true };
        console.log("🎯 annotation plugin 구조 생성");
    }
    
    chart.options.plugins.annotation.annotations = {};
    console.log("🧹 음절 표시 초기화 완료");
    
    console.log('🎯 Adding annotations for', syllables.length, 'syllables:');
    console.log('🎯 Sample syllables:', syllables.slice(0, 3));
    
    // Position labels at top of chart (inside chart area)
    const chartMax = chart.options.scales.y.max || 15;
    const chartMin = chart.options.scales.y.min || -12;
    const labelY = chartMax - (chartMax - chartMin) * 0.05; // 5% from top (더 상단)
    
    console.log("🎯 Chart Y 범위:", chartMin, "~", chartMax, "labelY:", labelY);
    
    syllables.forEach((syl, index) => {
        const sylStart = syl.start || syl.tmin || 0;
        const sylEnd = syl.end || syl.tmax || 1;
        const sylLabel = syl.label || syl.text || `음절${index+1}`;
        
        console.log(`🎯 음절 ${index}: ${sylLabel} (${sylStart.toFixed(3)}s - ${sylEnd.toFixed(3)}s)`);
        
        // 🔥 첫 번째 음절 시작선
        if (index === 0) {
            chart.options.plugins.annotation.annotations[`start_${index}`] = {
                type: 'line',
                xMin: sylStart,
                xMax: sylStart,
                borderColor: 'rgba(255, 99, 132, 0.8)',
                borderWidth: 3,
                borderDash: [6, 3]
            };
        }
        
        // 🔥 음절 끝선 (다음 음절 시작선)
        chart.options.plugins.annotation.annotations[`end_${index}`] = {
            type: 'line',
            xMin: sylEnd,
            xMax: sylEnd,
            borderColor: 'rgba(255, 99, 132, 0.8)',
            borderWidth: 3,
            borderDash: [6, 3]
        };
        
        // 🔥 보라색 음절 라벨 박스
        const midTime = (sylStart + sylEnd) / 2;
        chart.options.plugins.annotation.annotations[`label_${index}`] = {
            type: 'label',
            xValue: midTime,
            yValue: labelY,
            content: sylLabel,
            backgroundColor: 'rgba(138, 43, 226, 0.9)',  // 보라색 배경
            borderColor: 'rgba(138, 43, 226, 1)',
            borderWidth: 2,
            borderRadius: 6,
            font: {
                size: 14,
                family: 'Noto Sans KR, -apple-system, sans-serif',
                weight: 'bold'
            },
            color: 'white',
            padding: {
                x: 8,
                y: 4
            },
            position: 'center'
        };
    });
    
    // 🔥 강제 차트 업데이트로 annotation 표시
    try {
        chart.update('none');
        console.log("🎯 Syllable annotations added and chart updated!");
        console.log("🎯 현재 annotations 수:", Object.keys(chart.options.plugins.annotation.annotations).length);
    } catch (error) {
        console.error("🎯 Chart update 실패:", error);
    }
}

// Function to update syllable analysis table (horizontal layout)
function updateSyllableAnalysisTable(syllableAnalysis) {
    const table = document.getElementById('syllable-analysis-table');
    const card = document.getElementById('syllable-analysis-card');
    
    if (!table || !syllableAnalysis || syllableAnalysis.length === 0) {
        if (card) card.style.display = 'none';
        return;
    }
    
    // Clear existing content and rebuild table structure
    table.innerHTML = '';
    
    // Create header row with syllables
    const thead = table.createTHead();
    const headerRow = thead.insertRow();
    const firstHeaderCell = headerRow.insertCell();
    firstHeaderCell.textContent = '분석 항목';
    firstHeaderCell.className = 'table-orange-header fw-bold';
    
    // Add syllable headers
    syllableAnalysis.forEach(syl => {
        const headerCell = headerRow.insertCell();
        headerCell.textContent = syl.label || syl.syllable;  // label 또는 syllable 필드 사용
        headerCell.className = 'table-orange-header fw-bold text-center';
    });
    
    // Create tbody for data rows
    const tbody = table.createTBody();
    
    // Helper function to add a data row
    function addDataRow(label, getValue) {
        const row = tbody.insertRow();
        const labelCell = row.insertCell();
        labelCell.textContent = label;
        labelCell.className = 'fw-bold';
        
        syllableAnalysis.forEach(syl => {
            const dataCell = row.insertCell();
            dataCell.innerHTML = getValue(syl);
            dataCell.className = 'text-center';
        });
    }
    
    // Add data rows - 올바른 필드명 사용
    addDataRow('지속시간', (syl) => {
        const duration = ((syl.end_time || syl.end || 0) - (syl.start_time || syl.start || 0)) * 1000; // 초를 ms로 변환
        return `${duration.toFixed(0)}ms`;
    });
    
    addDataRow('평균 높낮이', (syl) => {
        const meanHz = syl.f0_hz || 0;  // f0_hz 필드 사용
        const meanSemitone = syl.semitone || 0;
        return `${meanHz.toFixed(1)}Hz<br><small>(${meanSemitone.toFixed(1)}st)</small>`;
    });
    
    addDataRow('최대 높낮이', (syl) => {
        const maxHz = syl.max_f0_hz || syl.f0_hz || 0;  // 최대값 또는 평균값
        return `${maxHz.toFixed(1)}Hz`;
    });
    
    addDataRow('강도', (syl) => `${(syl.intensity || 0).toFixed(1)}dB`);
    
    addDataRow('구간', (syl) => {
        const start = syl.start_time || 0;
        const end = syl.end_time || 0;
        return `${start.toFixed(2)}s - ${end.toFixed(2)}s`;
    });
    
    // Show the card
    card.style.display = 'block';
    
    console.log(`✅ 음절별 높낮이 분석 테이블 업데이트 완료: ${syllableAnalysis.length}개 음절`);
    console.log('🎯 첫 번째 음절 데이터:', syllableAnalysis[0]);
}

// Utility functions
function mean(arr) {
    return arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
}

function clamp(v, a, b) {
    return Math.min(b, Math.max(a, v));
}

// Convert Hz to semitone relative to reference median
function f0ToSemitone(f0, refMedian = 200) {
    if (f0 <= 0 || refMedian <= 0) return 0;
    return 12 * Math.log2(f0 / refMedian);
}

// 🎯 음성학 연구 표준: Qt 단위 계산 (200Hz 기준으로 조정, 0~25 등급)
function f0ToQt(f0) {
    if (f0 <= 0) return 0;
    // 200Hz 기준 Q-tone 체계 (실제 음성 범위에 맞게 조정)
    const qt = 12 + 12 * Math.log2(f0 / 200); // 200Hz = 12qt로 중앙 설정
    return Math.max(0, Math.min(25, qt)); // 0~25 범위로 제한
}

// 🎯 Qt를 Hz로 변환 (0~25 등급 범위 체크)
function qtToF0(qt) {
    // 0~25 범위로 제한
    const limitedQt = Math.max(0, Math.min(25, qt));
    // 200Hz 기준으로 역계산 (12qt = 200Hz)
    return 200 * Math.pow(2, (limitedQt - 12) / 12);
}


function normF0(f0, meanF0, maxF0) {
    if (f0 <= 0) return 0;
    // Simple linear scaling from 50Hz to 500Hz for better visibility
    const minF0 = 50;
    const maxF0Range = 500;
    return clamp((f0 - minF0) / (maxF0Range - minF0), 0, 1);
}

function normInt(db) {
    return clamp((db + 60) / 60, 0, 1);
}

// Reference analysis - moved to setupEventHandlers function

// 🎯 백엔드 Praat 분석으로 오디오 프레임 전송
async function sendFrameToBackend(frame, sampleRate) {
    try {
        // Float32Array를 WAV 형식으로 변환
        const audioBlob = new Blob([frame.buffer], { type: 'audio/wav' });
        
        const formData = new FormData();
        formData.append('audio', audioBlob, 'frame.wav');
        
        const response = await fetch('http://localhost:8000/analyze_live_audio', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            if (result.success && result.pitch_data.length > 0) {
                // 🎯 Praat 분석 결과로 차트 업데이트
                result.pitch_data.forEach(point => {
                    const f0 = point.f0;
                    const semitone = point.semitone;
                    
                    // Y축 단위에 맞게 변환
                    let yValue;
                    if (currentYAxisUnit === 'qtone') {
                        yValue = f0ToQt(f0);
                    } else {
                        yValue = semitone; // 이미 semitone으로 계산됨
                    }
                    
                    const tNow = Date.now() / 1000 - startTime;
                    
                    liveBuffer.push({
                        t: tNow,
                        f0: f0,
                        semitone: yValue,
                        int: 0.5 // 기본 intensity
                    });
                    
                    // 실시간 차트 업데이트
                    if (tNow > tLive + 0.05) {
                        addLiveDataToChart(yValue, 0.5);
                        tLive = tNow;
                        
                        const unitLabel = currentYAxisUnit === 'qtone' ? 'qt' : 'st';
                        console.log(`🎯 Praat: ${f0.toFixed(0)}Hz→${yValue.toFixed(1)}${unitLabel}`);
                    }
                });
            }
        }
    } catch (error) {
        console.error('🔥 백엔드 Praat 분석 오류:', error);
        // 오류 시 기존 YIN 알고리즘으로 fallback
        const f0 = yinPitch(frame, sampleRate);
        if (f0 > 0 && f0 < 1000) {
            console.log('🔄 YIN fallback 사용');
            // 기존 처리 로직...
        }
    }
}

// 🎯 VocalPitchMonitor 급 고급 YIN 알고리즘 (개선된 버전)
function enhancedYinPitch(frame, sampleRate) {
    const N = frame.length;
    const tauMax = Math.floor(sampleRate / 60);   // 60Hz까지 낮은 피치 감지
    const tauMin = Math.floor(sampleRate / 1000); // 1000Hz까지 높은 피치 감지
    
    // 🎯 적응형 전처리 (Vocal Pitch Monitor 스타일)
    const processed = adaptivePreprocess(frame);
    
    // YIN difference function 계산
    const diff = new Float32Array(tauMax + 1);
    for (let tau = 1; tau <= tauMax; tau++) {
        let sum = 0;
        for (let i = 0; i < N - tau; i++) {
            const delta = processed[i] - processed[i + tau];
            sum += delta * delta;
        }
        diff[tau] = sum;
    }
    
    // 개선된 정규화된 차이 함수
    const cmnd = new Float32Array(tauMax + 1);
    cmnd[0] = 1;
    let cumulativeSum = 0;
    
    for (let tau = 1; tau <= tauMax; tau++) {
        cumulativeSum += diff[tau];
        if (cumulativeSum > 0) {
            cmnd[tau] = diff[tau] / (cumulativeSum / tau);
        } else {
            cmnd[tau] = 1;
        }
    }
    
    // 🎯 VocalPitchMonitor 급 다중 후보 검출
    const candidates = [];
    for (let tau = tauMin; tau <= tauMax; tau++) {
        if (cmnd[tau] < 0.1 && 
            (tau === tauMin || cmnd[tau] < cmnd[tau-1]) && 
            (tau === tauMax || cmnd[tau] < cmnd[tau+1])) {
            candidates.push({tau: tau, score: cmnd[tau]});
        }
    }
    
    if (candidates.length === 0) return 0;
    
    // 가장 신뢰할만한 후보 선택
    candidates.sort((a, b) => a.score - b.score);
    const bestTau = candidates[0].tau;
    
    // 🎯 부분 샘플 보간으로 정밀도 향상
    const refinedTau = parabolicInterpolation(cmnd, bestTau);
    
    return refinedTau > 0 ? sampleRate / refinedTau : 0;
}

// 🎯 적응형 신호 전처리 (잡음 제거 + 강조)
function adaptivePreprocess(frame) {
    const N = frame.length;
    const processed = new Float32Array(N);
    
    // 1. DC 제거
    let mean = 0;
    for (let i = 0; i < N; i++) mean += frame[i];
    mean /= N;
    
    // 2. 적응형 pre-emphasis
    processed[0] = frame[0] - mean;
    for (let i = 1; i < N; i++) {
        processed[i] = (frame[i] - mean) - 0.97 * processed[i-1];
    }
    
    // 3. 윈도우 함수 적용 (Hamming)
    for (let i = 0; i < N; i++) {
        const w = 0.54 - 0.46 * Math.cos(2 * Math.PI * i / (N - 1));
        processed[i] *= w;
    }
    
    return processed;
}

// 🎯 부분 샘플 보간 (정밀도 향상)
function parabolicInterpolation(data, peak) {
    if (peak <= 0 || peak >= data.length - 1) return peak;
    
    const y1 = data[peak - 1];
    const y2 = data[peak];
    const y3 = data[peak + 1];
    
    const a = (y1 - 2*y2 + y3) / 2;
    if (Math.abs(a) < 1e-10) return peak;
    
    const delta = (y3 - y1) / (4 * a);
    return peak + delta;
}

// 🎯 신뢰도 기반 피치 필터링
function pitchConfidenceFilter(f0, frame, sampleRate) {
    // 신호 대 잡음 비 계산
    const snr = calculateSNR(frame);
    
    // 주기성 확인
    const periodicity = checkPeriodicity(frame, f0, sampleRate);
    
    // 신뢰도 점수 계산
    const confidence = (snr * 0.4) + (periodicity * 0.6);
    
    // 낮은 신뢰도면 0 반환
    return confidence > 0.6 ? f0 : 0; // 소음 필터링 강화
}

// 🎯 스무딩 필터 (시간적 일관성)
let pitchHistory = [];
const HISTORY_SIZE = 5;

function pitchSmoothingFilter(f0) {
    pitchHistory.push(f0);
    if (pitchHistory.length > HISTORY_SIZE) {
        pitchHistory.shift();
    }
    
    // 중앙값 필터 (이상값 제거)
    const sorted = [...pitchHistory].sort((a, b) => a - b);
    const median = sorted[Math.floor(sorted.length / 2)];
    
    // 급격한 변화 제한 (20% 이내)
    if (pitchHistory.length > 1) {
        const prev = pitchHistory[pitchHistory.length - 2];
        const maxChange = prev * 0.2;
        if (Math.abs(f0 - prev) > maxChange) {
            return prev + Math.sign(f0 - prev) * maxChange;
        }
    }
    
    return median;
}

// 🎯 신호 대 잡음 비 계산
function calculateSNR(frame) {
    let signal = 0, noise = 0;
    const N = frame.length;
    
    // 자기상관으로 신호 성분 추정
    let maxCorr = 0;
    for (let lag = N/4; lag < N/2; lag++) {
        let corr = 0;
        for (let i = 0; i < N - lag; i++) {
            corr += frame[i] * frame[i + lag];
        }
        maxCorr = Math.max(maxCorr, Math.abs(corr));
    }
    
    signal = maxCorr / (N * N);
    
    // 전체 에너지에서 신호 성분 제외한 것을 잡음으로 간주
    let totalEnergy = 0;
    for (let i = 0; i < N; i++) {
        totalEnergy += frame[i] * frame[i];
    }
    
    noise = Math.max(0.001, totalEnergy / N - signal);
    
    return Math.min(10, signal / noise);
}

// 🎯 주기성 검사
function checkPeriodicity(frame, f0, sampleRate) {
    if (f0 <= 0) return 0;
    
    const period = Math.round(sampleRate / f0);
    if (period >= frame.length / 2) return 0;
    
    let correlation = 0;
    const numPeriods = Math.floor(frame.length / period);
    
    for (let p = 0; p < numPeriods - 1; p++) {
        let sum = 0;
        for (let i = 0; i < period; i++) {
            sum += frame[p * period + i] * frame[(p + 1) * period + i];
        }
        correlation += sum / period;
    }
    
    return Math.min(1, correlation / (numPeriods - 1));
}

// Enhanced YIN-based pitch estimation with better sensitivity (fallback용)
function yinPitch(frame, sampleRate) {
    const N = frame.length;
    const tauMax = Math.floor(sampleRate / 50);   // Lower floor for better low pitch detection
    const tauMin = Math.floor(sampleRate / 800);  // Higher ceiling for better accuracy
    const diff = new Float32Array(tauMax + 1);
    
    // Pre-emphasize signal to improve pitch detection
    const emphasized = new Float32Array(N);
    emphasized[0] = frame[0];
    for (let i = 1; i < N; i++) {
        emphasized[i] = frame[i] - 0.95 * frame[i-1];
    }
    
    // Calculate difference function with emphasized signal
    for (let tau = 1; tau <= tauMax; tau++) {
        let s = 0;
        for (let i = 0; i < N - tau; i++) {
            const d = emphasized[i] - emphasized[i + tau];
            s += d * d;
        }
        diff[tau] = s;
    }
    
    // Calculate cumulative normalized difference with improved formula
    const cmnd = new Float32Array(tauMax + 1);
    let run = 0;
    for (let tau = 1; tau <= tauMax; tau++) {
        run += diff[tau];
        if (run > 0) {
            cmnd[tau] = diff[tau] / (run / tau);
        } else {
            cmnd[tau] = 1;
        }
    }
    
    // 🎯 VoicePitchMonitor 수준의 정확한 임계값 검출
    let best = -1, minv = 1e9;
    for (let t = tauMin; t <= tauMax; t++) {
        if (cmnd[t] < minv) {
            minv = cmnd[t];
            best = t;
        }
    }
    
    // More lenient threshold for better detection (like Praat's voicing_threshold=0.45)
    return (best > 0 && minv < 0.3) ? sampleRate / best : 0;
}

function frameEnergy(frame) {
    let s = 0;
    for (let i = 0; i < frame.length; i++) {
        s += frame[i] * frame[i];
    }
    const rms = Math.sqrt(s / frame.length);
    // Use same reference as Praat for dB calculation
    return 20 * Math.log10(Math.max(rms, 1e-10));
}

function vadSyllableTracker(intDb, time) {
    // More sensitive thresholds for better voice activity detection
    const thrOn = -40, thrOff = -50;
    const last = sylCuts[sylCuts.length - 1];
    const voiced = intDb > thrOn;
    const unvoiced = intDb < thrOff;
    
    if (!last) {
        if (voiced) {
            sylCuts.push({start: time, end: null});
        }
    } else {
        if (last.end === null) {
            if (unvoiced && (time - last.start) > 0.07) {
                last.end = time;
            }
        } else {
            if (voiced) {
                sylCuts.push({start: time, end: null});
            }
        }
    }
}

// 🎯 현재 발화 중인 음절 인덱스 추적
let currentSyllableIndex = 0;
let syllableStartTime = 0;

function syllableBasedTimeWarp(liveSeries) {
    if (!refSyll.length) return liveSeries;
    
    const completedSyllables = sylCuts.filter(s => s.end !== null);
    const currentSyllable = sylCuts.find(s => s.end === null);
    
    // 음절 진행 업데이트
    if (completedSyllables.length > currentSyllableIndex) {
        currentSyllableIndex = Math.min(completedSyllables.length, refSyll.length - 1);
        console.log(`🎯 음절 진행: ${currentSyllableIndex + 1}/${refSyll.length} - "${refSyll[currentSyllableIndex]?.label || 'N/A'}"`);
    }
    
    // 🎯 데이터가 너무 많으면 최근 것만 사용 (성능 향상)
    const recentData = liveSeries.length > 100 ? liveSeries.slice(-100) : liveSeries;
    
    return recentData.map((p, index) => {
        const t = p.x;
        
        // 🎯 현재 진행 중인 음절 인덱스 결정
        let targetSylIndex = Math.min(currentSyllableIndex, refSyll.length - 1);
        
        // 현재 발화 중인 음절이 있고, 유효한 참조 음절이 있는 경우
        if (currentSyllable && targetSylIndex >= 0 && targetSylIndex < refSyll.length) {
            const refSyl = refSyll[targetSylIndex];
            const currentSylStart = currentSyllable.start || 0;
            
            // 🎯 음성 데이터가 현재 음절 시작 이후인지 확인
            if (t >= currentSylStart) {
                const liveDuration = t - currentSylStart;
                const refDuration = Math.max(refSyl.end - refSyl.start, 0.1); // 최소 0.1초
                
                // 음절 내 상대적 위치 계산 (0~1, 최대 1.5까지 허용)
                const relativePos = Math.max(0, Math.min(1.5, liveDuration / refDuration));
                
                // 참조 음절 내 시간으로 매핑
                const mappedTime = refSyl.start + (relativePos * refDuration);
                
                // 🎯 디버깅 로그 (가끔만)
                if (Math.random() < 0.01) {
                    console.log(`🎯 시간 매핑: live=${t.toFixed(2)}s → mapped=${mappedTime.toFixed(2)}s (음절${targetSylIndex+1}: ${refSyl.label})`);
                }
                
                return {x: mappedTime, y: p.y, int: p.int};
            }
        }
        
        // 🎯 완료된 음절들의 경우 - 선형 보간으로 더 자연스럽게
        if (completedSyllables.length > 0 && targetSylIndex >= 0 && targetSylIndex < refSyll.length) {
            const refSyl = refSyll[targetSylIndex];
            
            // 해당하는 완료된 음절 찾기
            const completedSyl = completedSyllables[Math.min(targetSylIndex, completedSyllables.length - 1)];
            if (completedSyl) {
                const liveStart = completedSyl.start || 0;
                const liveEnd = completedSyl.end || (liveStart + 0.3); // 기본 0.3초
                const liveDuration = Math.max(liveEnd - liveStart, 0.1);
                
                // 음절 내에서의 상대적 위치
                const relativeInSyl = Math.max(0, Math.min(1, (t - liveStart) / liveDuration));
                const mappedTime = refSyl.start + (relativeInSyl * (refSyl.end - refSyl.start));
                
                return {x: mappedTime, y: p.y, int: p.int};
            }
        }
        
        // 🎯 기본 매핑 - 비례식으로 전체 시간에 맞춤
        const maxRefTime = refSyll.length > 0 ? refSyll[refSyll.length - 1].end : 2.0;
        const maxLiveTime = Math.max(t, 0.5);
        const scaledTime = (t / maxLiveTime) * maxRefTime;
        
        return {x: scaledTime, y: p.y, int: p.int};
    });
}

// 🎯 ===== PITCH TEST 기능 =====

// 참조음성 부분 연습 버튼 클릭 핸들러
function handleTwoPointPractice() {
    if (!refCurve || refCurve.length === 0) {
        alert('참조음성 분석을 먼저 진행해주세요.\n\n"모델 음성 분석" 버튼을 클릭하여 참조 데이터를 분석한 후 이용하실 수 있습니다.');
        return;
    }
    
    if (!pitchRange) {
        alert('차트에서 드래그하여 연습할 두 음의 범위를 먼저 선택해주세요.');
        return;
    }
    
    // 두 음 연습 로직 실행 (기존 음높이 테스트와 동일)
    startPitchTest();
}

function clearPitchRange() {
    // Clear any visual range indicators on the chart
    if (window.prosodyChart && window.prosodyChart.data && window.prosodyChart.data.datasets) {
        // Remove any range annotations
        window.prosodyChart.options.plugins = window.prosodyChart.options.plugins || {};
        window.prosodyChart.options.plugins.annotation = window.prosodyChart.options.plugins.annotation || {};
        window.prosodyChart.options.plugins.annotation.annotations = {};
        window.prosodyChart.update();
    }
    console.log("🎯 피치 범위 시각적 표시 제거됨");
}

function setupPitchTestHandlers() {
    if (!$btnPitchTest || !$btnStopPitchTest || !$btnTwoPointPractice) return;
    
    // 음높이 테스트 시작 (팝업 없이 바로 시작)
    $btnPitchTest.onclick = async () => {
        // 🎯 팝업 없이 바로 음높이 연습 시작
        await startPitchTest();
    };
    
    // 음높이 테스트 중지
    $btnStopPitchTest.onclick = () => {
        stopPitchTest();
    };
    
    // 참조음성 부분 연습
    $btnTwoPointPractice.onclick = () => {
        handleTwoPointPractice();
    };
}

async function startPitchTest() {
    if (pitchTestActive) return;
    
    try {
        pitchTestActive = true;
        pitchTestBuffer = [];
        chartFrozen = true; // 🎯 차트 완전 고정
        
        // 🎬 연습 데이터 저장 시작
        practiceRecordingData = [];
        isRecordingPractice = true;
        console.log("🎬 연습 시각화 저장 시작");
        
        // 🎯 현재 차트 스케일을 저장 (참조음성 범위 보존)
        if (chart && chart.scales) {
            originalScales = {
                xMin: chart.scales.x.min,
                xMax: chart.scales.x.max,
                yMin: chart.scales.y.min,
                yMax: chart.scales.y.max
            };
            console.log("🎯 원본 차트 스케일 저장:", originalScales);
        }
        
        // 🎯 마이크 접근 전 가이드 메시지
        $pitchTestStatus.innerHTML = `
            <div class="text-center">
                <div class="spinner-border spinner-border-sm me-2"></div>
                <strong>🎤 마이크를 켜는 중...</strong>
            </div>
        `;
        $pitchTestStatus.className = "text-center text-info small fw-bold";
        
        console.log("🎯 차트 완전 고정 모드 시작 - 참조음성 범위 보존");
        
        $btnPitchTest.disabled = true;
        $btnStopPitchTest.disabled = false;
        
        // 🎤 마이크 접근
        console.log("🎯 Pitch Test: 마이크 접근 중...");
        const devices = await navigator.mediaDevices.enumerateDevices();
        const audioInputs = devices.filter(device => device.kind === 'audioinput');
        
        let selectedDeviceId = null;
        const usbMic = audioInputs.find(device => 
            device.label.toLowerCase().includes('usb') || 
            device.label.toLowerCase().includes('external')
        );
        
        if (usbMic) {
            selectedDeviceId = usbMic.deviceId;
            console.log("🎯 Pitch Test: USB 마이크 사용");
        }
        
        const constraints = {
            audio: {
                sampleRate: 16000,
                channelCount: 1,
                echoCancellation: false,
                noiseSuppression: false,
                autoGainControl: false
            }
        };
        
        if (selectedDeviceId) {
            constraints.audio.deviceId = { exact: selectedDeviceId };
        }
        
        pitchTestStream = await navigator.mediaDevices.getUserMedia(constraints);
        
        // AudioContext 설정
        pitchTestAudioCtx = new (window.AudioContext || window.webkitAudioContext)({
            sampleRate: 16000
        });
        
        if (pitchTestAudioCtx.state === 'suspended') {
            await pitchTestAudioCtx.resume();
        }
        
        const src = pitchTestAudioCtx.createMediaStreamSource(pitchTestStream);
        pitchTestProcNode = pitchTestAudioCtx.createScriptProcessor(2048, 1, 1);
        
        const ring = new Float32Array(1600); // 100ms buffer
        let ringPos = 0;
        let accTime = 0;
        
        src.connect(pitchTestProcNode);
        pitchTestProcNode.connect(pitchTestAudioCtx.destination);
        
        // 실시간 피치 분석
        pitchTestProcNode.onaudioprocess = (e) => {
            if (!pitchTestActive) return;
            
            const ch = e.inputBuffer.getChannelData(0);
            
            // Fill ring buffer
            for (let i = 0; i < ch.length; i++) {
                ring[ringPos % ring.length] = ch[i];
                ringPos++;
            }
            
            accTime += ch.length / pitchTestAudioCtx.sampleRate;
            
            // 🚀 실시간 처리: 25ms 간격으로 더 빠른 업데이트 (지연 최소화)
            if (accTime >= 0.025) {
                accTime = 0;
                
                const frame = new Float32Array(800); // 50ms frame
                const start = (ringPos - 800 + ring.length) % ring.length;
                
                for (let j = 0; j < 800; j++) {
                    frame[j] = ring[(start + j) % ring.length];
                }
                
                // 🎯 VocalPitchMonitor 급 정밀 피치 검출
                let f0 = enhancedYinPitch(frame, pitchTestAudioCtx.sampleRate);
                
                // 🎯 신뢰도 및 스무딩 적용
                if (f0 > 0) {
                    f0 = pitchConfidenceFilter(f0, frame, pitchTestAudioCtx.sampleRate);
                    if (f0 > 0) {
                        f0 = pitchSmoothingFilter(f0);
                    }
                }
                
                const dB = frameEnergy(frame);
                
                if (f0 > 0 && f0 < 1000) {
                    // 🎯 현재 Y축 단위에 맞게 변환
                    let yValue;
                    if (currentYAxisUnit === 'qtone') {
                        yValue = f0ToQt(f0);
                    } else {
                        yValue = f0ToSemitone(f0, refMedian);
                    }
                    
                    // 🚀 실시간 피드백: 모든 변화를 즉시 반영 (필터링 최소화)
                    const threshold = PERCEPTUAL_THRESHOLDS[currentYAxisUnit];
                    const isPerceptibleChange = lastPerceptiblePitch === null || 
                        Math.abs(yValue - lastPerceptiblePitch) >= threshold;
                    
                    // 실시간성을 위해 모든 유효한 피치 즉시 처리
                    if (isPerceptibleChange || true) { // 항상 업데이트
                        lastPerceptiblePitch = yValue;
                        currentLiveHz = f0; // 실시간 Hz 업데이트
                        
                        // 🔴 음높이 테스트: 지각 가능한 변화만 표시
                        updatePitchTestChart(yValue);
                        
                        // 🎬 연습 데이터 저장
                        if (isRecordingPractice) {
                            const practicePoint = {
                                timestamp: Date.now(),
                                time: tLive,
                                pitch: yValue,
                                frequency: f0,
                                unit: currentYAxisUnit
                            };
                            practiceRecordingData.push(practicePoint);
                        }
                        
                        // 🎯 실시간 Hz 값을 우측 축에 표시
                        updateLiveHzDisplay(f0);
                    } else {
                        // 지각하기 어려운 미세한 변화는 무시
                        return;
                    }
                    
                    // 범위/목표 체크
                    let feedback = "";
                    if (pitchRange) {
                        // 🎯 범위를 현재 단위로 변환
                        let convertedMin, convertedMax;
                        if (currentYAxisUnit === 'qtone') {
                            convertedMin = f0ToQt((refMedian || 200) * Math.pow(2, pitchRange.min / 12));
                            convertedMax = f0ToQt((refMedian || 200) * Math.pow(2, pitchRange.max / 12));
                        } else {
                            convertedMin = pitchRange.min;
                            convertedMax = pitchRange.max;
                        }
                        
                        const isInRange = yValue >= convertedMin && yValue <= convertedMax;
                        feedback = isInRange ? "🟢 범위 내!" : "🔴 범위 밖";
                        
                        let unitLabel = currentYAxisUnit === 'qtone' ? 'qt' : 'st';
                        
                        // 🚀 로그 최소화 (성능 최우선)
                        if (Math.random() < 0.005) { // 0.5%만 로그
                            console.log(`🎯 ${yValue.toFixed(0)}${unitLabel} (${convertedMin.toFixed(0)}~${convertedMax.toFixed(0)}) → ${feedback}`);
                        }
                    } else if (targetPitch !== null) {
                        // 🎯 목표값을 현재 단위로 변환
                        let convertedTarget;
                        if (currentYAxisUnit === 'qtone') {
                            convertedTarget = f0ToQt((refMedian || 200) * Math.pow(2, targetPitch / 12));
                        } else {
                            convertedTarget = targetPitch;
                        }
                        
                        const diff = Math.abs(yValue - convertedTarget);
                        const threshold = currentYAxisUnit === 'qtone' ? 1.0 : 0.5;
                        const isAccurate = diff <= threshold;
                        feedback = isAccurate ? "🟢 정확!" : "🟡 조정 필요";
                        
                        let unitLabel = currentYAxisUnit === 'qtone' ? 'qt' : 'st';
                        
                        // 🚀 로그 최소화 (성능 최우선)
                        if (Math.random() < 0.005) { // 0.5%만 로그
                            console.log(`🎯 ${yValue.toFixed(0)}${unitLabel} vs ${convertedTarget.toFixed(0)}${unitLabel} → ${feedback}`);
                        }
                    }
                }
            }
        };
        
        // 🎯 마이크 연결 성공 후 사용자 가이드
        $pitchTestStatus.innerHTML = `
            <div class="text-center">
                <strong>🎤 마이크 연결됨!</strong><br>
                <span class="text-success">📢 "아~" 소리를 내보세요. 빨간줄로 현재 음높이가 표시됩니다.</span><br>
                <small class="text-muted">발성 후 차트에서 드래그하여 연습 범위를 설정할 수 있습니다.</small>
            </div>
        `;
        $pitchTestStatus.className = "text-center small fw-bold";
        
        console.log("🎯 Pitch Test 시작됨");
        
    } catch (error) {
        console.error("🎯 Pitch Test 오류:", error);
        $pitchTestStatus.textContent = "마이크 접근 오류: " + error.message;
        $pitchTestStatus.className = "text-center text-danger small";
        stopPitchTest();
    }
}

function stopPitchTest() {
    if (!pitchTestActive) return;
    
    pitchTestActive = false;
    chartFrozen = false; // 🎯 차트 고정 해제
    originalScales = null; // 🎯 저장된 스케일 제거
    
    // 🎯 음성 지속시간 기록 초기화
    currentPitchHistory = [];
    pitchTestLastValue = null;
    pitchStartTime = null;
    
    // 🎬 연습 데이터 저장 종료
    isRecordingPractice = false;
    if (practiceRecordingData.length > 0) {
        console.log(`🎬 연습 시각화 저장 완료: ${practiceRecordingData.length}개 데이터 포인트`);
        updateButtons(); // 재생 버튼 활성화
    }
    
    if (pitchTestStream) {
        pitchTestStream.getTracks().forEach(track => track.stop());
        pitchTestStream = null;
    }
    
    if (pitchTestProcNode) {
        pitchTestProcNode.disconnect();
        pitchTestProcNode = null;
    }
    
    if (pitchTestAudioCtx) {
        pitchTestAudioCtx.close();
        pitchTestAudioCtx = null;
    }
    
    $btnPitchTest.disabled = false;
    $btnStopPitchTest.disabled = true;
    
    // 🎯 음높이 연습 종료 메시지 개선
    $pitchTestStatus.innerHTML = `
        <div class="text-center">
            <strong>🎤 음높이 연습이 종료되었습니다.</strong><br>
            <small class="text-muted">다시 시작하려면 "음높이 연습" 버튼을 누르세요.</small>
        </div>
    `;
    $pitchTestStatus.className = "text-center text-success small";
    
    // 실시간 피치선 제거
    if (chart && chart.data.datasets[2]) {
        chart.data.datasets[2].data = [];
    }
    
    // 🎯 현재 음높이 가로선 제거
    if (chart && chart.options.plugins.annotation && chart.options.plugins.annotation.annotations.currentPitchLine) {
        delete chart.options.plugins.annotation.annotations.currentPitchLine;
    }
    
    // 실시간 피치선 제거 (중복 방지)
    if (chart && chart.data.datasets[2]) {
        chart.data.datasets[2].data = [];
    }
    
    chart.update('none');
    
    console.log("🎯 Pitch Test 종료 - 차트 고정 해제");
}

// 🎯 음성 지속시간 기록을 위한 변수들
let currentPitchHistory = [];
let pitchTestLastValue = null;  // 🎯 음높이 테스트용 변수 (다른 기능과 분리)
let pitchStartTime = null;

// 🎯 음높이 테스트: 완전 고정 차트에서 지속시간을 선 굵기로 표현
function updatePitchTestChart(currentValue) {
    if (!chart || !pitchTestActive || chartFrozen === false) return;
    
    // 🎯 차트 스케일을 원본으로 완전 고정 (절대 변경되지 않도록)
    if (originalScales) {
        chart.scales.x.min = originalScales.xMin;
        chart.scales.x.max = originalScales.xMax;
        chart.scales.y.min = originalScales.yMin;
        chart.scales.y.max = originalScales.yMax;
        
        // 스케일 옵션도 고정
        chart.options.scales.x.min = originalScales.xMin;
        chart.options.scales.x.max = originalScales.xMax;
        chart.options.scales.y.min = originalScales.yMin;
        chart.options.scales.y.max = originalScales.yMax;
    }
    
    // 🔴 빨간 포인트 데이터셋 (5번째 데이터셋, index 4)
    const redPointDataset = chart.data.datasets[4];
    if (!redPointDataset) return;
    
    // 🎯 차트 중앙 고정 위치 (절대 변하지 않음)
    const refMidTime = originalScales ? (originalScales.xMin + originalScales.xMax) / 2 : 1.0;
    
    // 🎯 지속시간 계산을 위한 단위별 허용 오차
    const currentTime = Date.now();
    const pitchTolerance = currentYAxisUnit === 'cent' ? 30 : (currentYAxisUnit === 'qtone' ? 0.5 : 0.3);
    
    if (pitchTestLastValue === null || Math.abs(currentValue - pitchTestLastValue) > pitchTolerance) {
        // 새로운 음높이 시작
        pitchTestLastValue = currentValue;
        pitchStartTime = currentTime;
    }
    
    // 현재 음높이 지속시간 계산 (초 단위)
    const sustainDuration = pitchStartTime ? (currentTime - pitchStartTime) / 1000 : 0;
    
    // 🎯 지속시간에 따른 시각적 강도 계산 (0.1초 ~ 2초 범위)
    const minDuration = 0.1;
    const maxDuration = 2.0;
    const normalizedDuration = Math.min(sustainDuration, maxDuration) / maxDuration;
    
    // 선 굵기: 지속시간에 따라 2~8px (더 세련되게)
    const lineWidth = 2 + (normalizedDuration * 6);
    
    // 투명도: 지속시간에 따라 0.7~1.0 (더 선명하게)
    const alpha = 0.7 + (normalizedDuration * 0.3);
    
    // 🔴 빨간 포인트만 업데이트
    redPointDataset.data = [{
        x: refMidTime,
        y: currentValue
    }];
    
    // 🎯 현재 단위에 맞는 표시
    let unitLabel = currentYAxisUnit === 'qtone' ? 'qt' : 'st';
    
    // 🎯 현재 음높이 가로선 (지속시간으로 굵기 표현)
    if (!chart.options.plugins.annotation) {
        chart.options.plugins.annotation = { annotations: {} };
    }
    
    chart.options.plugins.annotation.annotations.currentPitchLine = {
        type: 'line',
        yMin: currentValue,
        yMax: currentValue,
        borderColor: `rgba(255, 0, 0, ${alpha})`,
        borderWidth: lineWidth,
        borderDash: sustainDuration > 0.2 ? [] : [4, 2], // 0.2초 이상 지속시 실선
        label: {
            content: sustainDuration > 0.1 ? 
                `${currentValue.toFixed(1)}${unitLabel} (${sustainDuration.toFixed(1)}s)` : 
                `${currentValue.toFixed(1)}${unitLabel}`,
            enabled: true,
            position: 'end',
            backgroundColor: `rgba(255, 0, 0, ${Math.min(alpha + 0.2, 1.0)})`,
            color: 'white',
            font: { size: 11, weight: 'bold' },
            padding: 4
        }
    };
    
    // 🎯 차트 업데이트 (스케일은 절대 변경 안됨)
    chart.update('none');
    
    // 🚀 로그 최소화 (실시간 성능 최우선)
    if (sustainDuration > 0.2 && Math.random() < 0.01) { // 로그 대폭 감소
        console.log(`🔴 ${currentValue.toFixed(0)}${unitLabel} ${sustainDuration.toFixed(1)}s`);
    }
}

function updatePitchTestStatus(currentValue, diff) {
    const accuracy = Math.max(0, 100 - (diff * 20)); // 차이에 따른 정확도
    
    // 단위별 표시
    let unitLabel = currentYAxisUnit === 'qtone' ? 'qt' : 'st';
    
    let message = `현재: ${currentValue.toFixed(1)}${unitLabel} | 목표: ${targetPitch.toFixed(1)}${unitLabel}`;
    let className = "text-center small fw-bold";
    
    if (diff < 0.5) {
        message += " | ✅ 완벽합니다!";
        className += " text-success";
    } else if (diff < 1.0) {
        message += " | 🎯 거의 맞습니다!";
        className += " text-primary";
    } else if (diff < 2.0) {
        message += " | 📈 조금 더 " + (currentValue < targetPitch ? "높게" : "낮게");
        className += " text-warning";
    } else {
        message += " | 🔄 " + (currentValue < targetPitch ? "더 높게" : "더 낮게") + " 발성하세요";
        className += " text-danger";
    }
    
    $pitchTestStatus.textContent = message;
    $pitchTestStatus.className = className;
}

// 🎯 차트 클릭 이벤트 핸들러
function handleChartClick(event, chartInstance) {
    if (!chartInstance || pitchTestActive) return;
    
    const canvasPosition = Chart.helpers.getRelativePosition(event, chartInstance);
    const dataX = chartInstance.scales.x.getValueForPixel(canvasPosition.x);
    const dataY = chartInstance.scales.y.getValueForPixel(canvasPosition.y);
    
    // 유효한 세미톤 범위인지 확인
    if (dataY >= -10 && dataY <= 15) {
        targetPitch = dataY;
        
        // 참조선 추가/업데이트
        addPitchReferenceLine(dataY);
        
        // UI 업데이트
        $pitchTestStatus.textContent = `목표 음높이: ${dataY.toFixed(1)} 세미톤 선택됨. "음높이 테스트" 버튼을 누르세요`;
        $pitchTestStatus.className = "text-center text-info small fw-bold";
        
        if ($btnPitchTest) {
            $btnPitchTest.disabled = false;
            $btnPitchTest.classList.remove('btn-outline-success');
            $btnPitchTest.classList.add('btn-success');
        }
        
        console.log(`🎯 목표 음높이 설정: ${dataY.toFixed(1)} 세미톤`);
    }
}

// 🎯 피치 참조선 추가
function addPitchReferenceLine(semitoneValue) {
    if (!chart || !chart.options.plugins.annotation) return;
    
    // 기존 참조선 제거
    if (chart.options.plugins.annotation.annotations.pitchTarget) {
        delete chart.options.plugins.annotation.annotations.pitchTarget;
    }
    
    // 새 참조선 추가
    chart.options.plugins.annotation.annotations.pitchTarget = {
        type: 'line',
        yMin: semitoneValue,
        yMax: semitoneValue,
        borderColor: '#e74c3c',
        borderWidth: 1,
        borderDash: [10, 5],
        label: {
            enabled: true,
            content: `목표: ${semitoneValue.toFixed(1)}st`,
            position: 'start',
            backgroundColor: '#e74c3c',
            color: 'white',
            font: {
                size: 12,
                weight: 'bold'
            }
        }
    };
    
    chart.update('none');
    console.log(`🎯 참조선 추가: ${semitoneValue.toFixed(1)} 세미톤`);
}

// 🎯 피치 테스트 참조선 제거
function removePitchReferenceLine() {
    if (chart && chart.options.plugins.annotation && chart.options.plugins.annotation.annotations.pitchTarget) {
        delete chart.options.plugins.annotation.annotations.pitchTarget;
        chart.update('none');
        console.log("🎯 참조선 제거됨");
    }
}

// 🎯 updateButtons 함수 확장 - 피치 테스트 버튼 상태도 관리
function updatePitchTestButtons() {
    if (!$btnPitchTest || !$btnStopPitchTest) return;
    
    if (pitchTestActive) {
        $btnPitchTest.disabled = true;
        $btnStopPitchTest.disabled = false;
    } else {
        $btnPitchTest.disabled = false; // 항상 활성화
        $btnStopPitchTest.disabled = true;
        
        // 목표 피치가 설정되었으면 버튼 스타일 변경
        if (targetPitch !== null) {
            $btnPitchTest.classList.remove('btn-outline-success');
            $btnPitchTest.classList.add('btn-success');
        } else {
            $btnPitchTest.classList.remove('btn-success');
            $btnPitchTest.classList.add('btn-outline-success');
        }
    }
}

// 기존 함수는 백업용으로 유지
function timeWarpToRef_backup(liveSeries) {
    const liveSyl = sylCuts.filter(s => s.end !== null);
    if (!liveSyl.length || !refSyll.length) return liveSeries;
    
    const n = Math.min(liveSyl.length, refSyll.length);
    const anchors = [];
    
    for (let i = 0; i < n; i++) {
        const L = liveSyl[i], R = refSyll[i];
        const lMid = (L.start + L.end) / 2;
        const rMid = (R.start + R.end) / 2;
        anchors.push({l: lMid, r: rMid});
    }
    
    return liveSeries.map(p => {
        const t = p.x;
        let k = 0;
        while (k < anchors.length && anchors[k].l < t) k++;
        
        if (k === 0) {
            const a0 = anchors[0];
            const scale = (a0.r) / (a0.l || 1e-6);
            return {x: t * scale, y: p.y, int: p.int};
        } else if (k >= anchors.length) {
            const a1 = anchors[anchors.length - 1];
            const scale = ((refStats.duration - a1.r) / ((t) - a1.l || 1e-6));
            return {x: a1.r + (t - a1.l) * scale, y: p.y, int: p.int};
        } else {
            const a0 = anchors[k - 1], a1 = anchors[k];
            const alpha = (t - a0.l) / ((a1.l - a0.l) || 1e-6);
            const x = a0.r + alpha * (a1.r - a0.r);
            return {x, y: p.y, int: p.int};
        }
    });
}

// Microphone handler - moved to setupEventHandlers function

// Reset handler - moved to setupEventHandlers function

// Save session data
async function saveSessionData(data) {
    try {
        const response = await fetch('/api/save_session', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        
        if (response.ok) {
            console.log('Session data saved successfully');
        }
    } catch (e) {
        console.error('Error saving session data:', e);
    }
}

// Initialize - removed from here since it's now in DOMContentLoaded

// Load saved files from server
async function loadSavedFilesList() {
    try {
        const response = await fetch(`${API_BASE}/api/reference_files`);
        const data = await response.json();
        
        if ($savedFiles) {
            $savedFiles.innerHTML = '<option value="">저장된 파일을 선택하세요</option>';
            
            if (data.files && data.files.length > 0) {
                data.files.forEach(file => {
                    const option = document.createElement('option');
                    option.value = file.id;
                    // 더 친근한 표시 형식 (시간 정보 포함)
                    const sentence = file.sentence_text || file.title;
                    const duration = file.duration && file.duration > 0 ? `${file.duration.toFixed(1)}초` : '시간미상';
                    option.textContent = `${sentence} (${duration})`;
                    $savedFiles.appendChild(option);
                });
                $savedFiles.disabled = false;
                console.log(`🎯 ${data.files.length}개의 연습 문장이 로드되었습니다`);
            } else {
                $savedFiles.innerHTML = '<option value="">연습할 문장이 준비되지 않았습니다</option>';
                $savedFiles.disabled = true;
            }
            
            // Update delete button state
            updateDeleteButtonState();
        }
    } catch (error) {
        console.error('Failed to load saved files:', error);
        if ($savedFiles) {
            $savedFiles.innerHTML = '<option value="">파일 목록 로드 실패</option>';
            $savedFiles.disabled = true;
        }
    }
}

// Load selected file from saved files
async function loadSelectedFile() {
    const fileId = $savedFiles.value;
    if (!fileId) return;
    
    try {
        $status.textContent = `${fileId} 문장을 불러오는 중...`;
        
        // 🎯 기존 연습 문장 로딩 함수 사용
        const sentenceId = fileId; // fileId가 실제로는 문장 ID
        await loadSentenceForLearner(sentenceId);
        
        $status.textContent = `${sentenceId} 문장을 성공적으로 불러왔습니다.`;
        
    } catch (error) {
        console.error('Failed to load selected file:', error);
        $status.textContent = '문장 로드 중 오류가 발생했습니다.';
    }
}

// Update delete button state (삭제 버튼 제거됨)
function updateDeleteButtonState() {
    // $btnDeleteSaved 기능 제거됨
    if ($btnReplayPractice) {
        $btnReplayPractice.disabled = !practiceRecordingData || practiceRecordingData.length === 0;
    }
}

// Confirm delete saved file
async function confirmDeleteSavedFile() {
    const fileId = $savedFiles.value;
    if (!fileId) return;
    
    const selectedOption = $savedFiles.options[$savedFiles.selectedIndex];
    const fileName = selectedOption.textContent;
    
    if (confirm(`정말로 "${fileName}" 파일을 삭제하시겠습니까?\n\n이 작업은 되돌릴 수 없습니다.`)) {
        await deleteSavedFile(fileId);
    }
}

// Delete saved file from server
async function deleteSavedFile(fileId) {
    try {
        $status.textContent = '파일을 삭제하는 중...';
        
        const response = await fetch(`${API_BASE}/api/reference_files/${fileId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            $status.textContent = '파일이 성공적으로 삭제되었습니다.';
            
            // Reload saved files list
            await loadSavedFilesList();
            
            console.log(`🗑️ 저장된 파일 삭제 성공: ${fileId}`);
            
        } else {
            throw new Error(result.message || 'Unknown error');
        }
        
    } catch (error) {
        console.error('Delete error:', error);
        $status.textContent = '파일 삭제 중 오류가 발생했습니다.';
        alert('파일 삭제에 실패했습니다: ' + error.message);
    }
}

// Show save modal
function showSaveModal() {
    const modal = createSaveModal();
    document.body.appendChild(modal);
    
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    // Remove modal from DOM when closed
    modal.addEventListener('hidden.bs.modal', () => {
        document.body.removeChild(modal);
    });
}

// Create save modal
function createSaveModal() {
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.innerHTML = `
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">참조 파일 저장</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form id="saveForm">
                        <div class="mb-3">
                            <label for="saveTitle" class="form-label">제목 *</label>
                            <input type="text" class="form-control" id="saveTitle" required 
                                   placeholder="예: 한국어 기본 문장 연습">
                        </div>
                        <div class="mb-3">
                            <label for="saveDescription" class="form-label">설명</label>
                            <textarea class="form-control" id="saveDescription" rows="3"
                                      placeholder="파일에 대한 설명을 입력하세요"></textarea>
                        </div>
                        <div class="mb-3">
                            <label for="saveSentence" class="form-label">문장 내용</label>
                            <input type="text" class="form-control" id="saveSentence"
                                   placeholder="예: 내 친구가 면접에 합격했대">
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">취소</button>
                    <button type="button" class="btn btn-success" onclick="saveReferenceFile()">저장</button>
                </div>
            </div>
        </div>
    `;
    return modal;
}

// Save reference file to server
async function saveReferenceFile() {
    const title = document.getElementById('saveTitle').value.trim();
    const description = document.getElementById('saveDescription').value.trim();
    const sentence = document.getElementById('saveSentence').value.trim();
    
    if (!title) {
        alert('제목을 입력해주세요.');
        return;
    }
    
    if (!$wav.files[0] || !$tg.files[0]) {
        alert('WAV 파일과 TextGrid 파일이 모두 필요합니다.');
        return;
    }
    
    try {
        const formData = new FormData();
        formData.append('title', title);
        formData.append('description', description);
        formData.append('sentence_text', sentence);
        formData.append('wav_file', $wav.files[0]);
        formData.append('textgrid_file', $tg.files[0]);
        
        $status.textContent = '파일을 저장하는 중...';
        
        const response = await fetch(`${API_BASE}/api/save_reference`, {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            $status.textContent = '파일이 성공적으로 저장되었습니다!';
            
            // Close modal safely
            const modalElement = document.querySelector('.modal.show');
            if (modalElement) {
                const modal = bootstrap.Modal.getInstance(modalElement);
                if (modal) {
                    modal.hide();
                } else {
                    // Fallback: manually remove modal
                    modalElement.remove();
                }
            }
            
            // Reload saved files list
            await loadSavedFilesList();
            
        } else {
            throw new Error(result.message || 'Unknown error');
        }
        
    } catch (error) {
        console.error('Save error:', error);
        $status.textContent = '파일 저장 중 오류가 발생했습니다.';
        alert('파일 저장에 실패했습니다: ' + error.message);
    }
}

// 🎯 성별 선택 모달 기능
document.addEventListener('DOMContentLoaded', function() {
    initializeGenderSelection();
    initializeLearningInterface();
});

function initializeGenderSelection() {
    // 성별 옵션 선택 이벤트
    document.addEventListener('click', function(e) {
        if (e.target.closest('.gender-option')) {
            const genderOption = e.target.closest('.gender-option');
            const gender = genderOption.dataset.gender;
            
            // 모든 선택 해제
            document.querySelectorAll('.gender-option').forEach(opt => {
                if (opt.classList.contains('card')) {
                    opt.style.border = '2px solid transparent';
                } else {
                    opt.classList.remove('btn-primary');
                    opt.classList.add('btn-outline-secondary');
                }
            });
            
            // 선택한 옵션 강조
            if (genderOption.classList.contains('card')) {
                genderOption.style.border = '2px solid #0d6efd';
            } else {
                genderOption.classList.remove('btn-outline-secondary');
                genderOption.classList.add('btn-primary');
            }
            
            selectedGender = gender;
            document.getElementById('confirmGenderSelection').disabled = false;
        }
    });
    
    // 성별 선택 확인
    document.getElementById('confirmGenderSelection')?.addEventListener('click', function() {
        if (selectedGender) {
            // 🎯 성별 변경 시 완전 초기화
            resetAllSettingsForGenderChange(selectedGender);
            
            applyGenderNormalization(selectedGender);
            const modal = bootstrap.Modal.getInstance(document.getElementById('genderSelectionModal'));
            modal.hide();
        }
    });
}

function showGenderSelectionModal(refGender, refMedian) {
    const modal = new bootstrap.Modal(document.getElementById('genderSelectionModal'));
    const genderText = refGender === 'female' ? 
        `여성 음성 (평균 ${refMedian.toFixed(0)}Hz)` : 
        `남성 음성 (평균 ${refMedian.toFixed(0)}Hz)`;
    
    document.getElementById('referenceGenderInfo').textContent = genderText;
    
    // 선택 초기화
    selectedGender = null;
    document.getElementById('confirmGenderSelection').disabled = true;
    document.querySelectorAll('.gender-option').forEach(opt => {
        if (opt.classList.contains('card')) {
            opt.style.border = '2px solid transparent';
        } else {
            opt.classList.remove('btn-primary');
            opt.classList.add('btn-outline-secondary');
        }
    });
    
    modal.show();
}

function applyGenderNormalization(targetGender) {
    console.log(`🎯 성별 정규화 적용: ${detectedReferenceGender} → ${targetGender}`);
    
    // 학습자 성별 업데이트
    learnerGender = targetGender;
    
    // 차트 Y축 범위 업데이트
    updateChartGenderSettings();
    
    // 정규화된 매개변수로 다시 분석 요청
    analyzeReferenceWithGender(targetGender);
}

// 🎯 학습자 성별 변경 시 차트 설정 업데이트
function updateChartGenderSettings() {
    if (!chart) return;
    
    const genderRange = getGenderHzRange();
    
    // Hz 범위는 더 이상 사용하지 않음 (semitone 단일 축 사용)
    
    console.log(`🎯 성별 설정 업데이트 완료: ${learnerGender}`);
    
    // 차트 업데이트
    chart.update('resize');
    
    // 현재 설정된 semitone 범위가 있다면 Hz 표시도 업데이트
    const currentMin = parseFloat(document.getElementById('semitone-min')?.value || -12);
    const currentMax = parseFloat(document.getElementById('semitone-max')?.value || 15);
    updateFrequencyRangeDisplay(currentMin, currentMax);
}

// 🎯 학습 방법에 따른 버튼 활성화/비활성화
function updateButtonsByLearningMethod(method) {
    console.log(`🎯 학습 방법에 따른 버튼 상태 업데이트: ${method}`);
    
    if (method === 'pitch') {
        // 음높이 학습: 모든 녹음 관련 버튼 비활성화
        if ($btnMic) {
            $btnMic.disabled = true; // 🎯 음높이 학습에서 녹음 비활성화
            $btnMic.classList.add('disabled');
            $btnMic.style.opacity = '0.5';
        }
        if ($btnAnalyze) {
            $btnAnalyze.disabled = true; // 🎯 음높이 학습에서 분석 비활성화
            $btnAnalyze.classList.add('disabled');
            $btnAnalyze.style.opacity = '0.5';
        }
        
        // 🎯 음높이 학습 모드는 위에서 별도 처리하므로 여기서는 제거
        
        // 🎯 음높이 학습 모드에서는 피치 테스트와 녹음 기능 모두 활성화
        if ($btnPitchTest) {
            $btnPitchTest.disabled = false;
        }
        if ($btnStopPitchTest) {
            $btnStopPitchTest.disabled = true;
        }
        
        // 🎯 음높이 학습 모드에서 녹음 버튼들 활성화
        const $btnStopRecord = document.getElementById('btnStopRecord');
        const $btnUnifiedRecord = document.getElementById('btnUnifiedRecord');
        if ($btnStopRecord) {
            $btnStopRecord.disabled = true; // 처음에는 비활성화
        }
        if ($btnUnifiedRecord) {
            $btnUnifiedRecord.disabled = false; // 녹음 버튼 활성화
        }
        
        console.log('🎯 음높이 학습 모드: 녹음 및 피치 테스트 기능 활성화');
        
        // 🎯 즉시 updateButtons 호출하여 상태 강제 업데이트
        updateButtons();
        
    } else if (method === 'sentence') {
        // 문장억양연습: 분석 버튼 활성화, 녹음 버튼 활성화
        if ($btnAnalyze) {
            $btnAnalyze.disabled = false;
            $btnAnalyze.classList.remove('disabled');
            $btnAnalyze.style.opacity = '1';
        }
        if ($btnMic) {
            // 문장억양연습: 항상 활성화
            $btnMic.disabled = false;
            $btnMic.classList.remove('disabled');
            $btnMic.style.opacity = '1';
        }
        console.log('🎯 문장억양연습 모드: 분석 활성화, 녹음 활성화');
        
        // 🎯 즉시 updateButtons 호출하여 상태 강제 업데이트
        updateButtons();
        
    } else {
        // 방법이 선택되지 않은 경우: 모든 버튼 비활성화
        if ($btnMic) {
            $btnMic.disabled = true;
            $btnMic.classList.add('disabled');
            $btnMic.style.opacity = '0.5';
        }
        if ($btnAnalyze) {
            $btnAnalyze.disabled = false; // 🎯 기본적으로 활성화
            $btnAnalyze.classList.remove('disabled');
            $btnAnalyze.style.opacity = '1';
        }
        console.log('🎯 학습 방법 미선택: 분석 버튼 활성화, 녹음 버튼 비활성화');
    }
}

// 🎯 새로운 학습 인터페이스 초기화
function initializeLearningInterface() {
    // 학습자 성별 선택 이벤트
    document.getElementById('learner-gender')?.addEventListener('change', function(e) {
        learnerGender = e.target.value;
        console.log(`🎯 학습자 성별 선택: ${learnerGender}`);
        
        // 차트 성별 설정 업데이트
        updateChartGenderSettings();
        
        // 🎯 성별 선택 완료 시 학습 방법 섹션 활성화 표시
        const methodCards = document.querySelectorAll('.learning-method-toggle');
        console.log(`🎯 성별 변경: ${learnerGender}, 카드 수: ${methodCards.length}`);
        
        if (learnerGender) {
            // 성별 선택 완료 - 학습 방법 선택 가능 상태로 표시
            methodCards.forEach(card => {
                card.style.opacity = '1';
                card.style.pointerEvents = 'auto';
                card.classList.remove('disabled');
            });
            console.log('🎯 학습 방법 카드 활성화 완료');
            
            // 성공 메시지 표시
            const genderSelect = document.getElementById('learner-gender');
            genderSelect.style.border = '2px solid #28a745';
            setTimeout(() => {
                genderSelect.style.border = '';
            }, 2000);
            
        } else {
            // 성별 미선택 - 학습 방법 비활성화
            methodCards.forEach(card => {
                card.style.opacity = '0.6';
                card.style.pointerEvents = 'none';
                card.classList.add('disabled');
            });
            console.log('🎯 학습 방법 카드 비활성화 완료');
        }
        
        updateProgress();
    });
    
    // 학습 방법 선택 이벤트 (새로운 토글 형태)
    document.addEventListener('click', function(e) {
        if (e.target.closest('.learning-method-toggle')) {
            const toggle = e.target.closest('.learning-method-toggle');
            const method = toggle.dataset.method;
            const radio = toggle.querySelector('input[type="radio"]');
            
            console.log(`🎯 학습 방법 선택 시도: ${method}`);
            
            // 🎯 성별 선택 필수 검증
            if (!learnerGender) {
                alert('먼저 학습자 성별을 선택해주세요.\n성별 정보는 정확한 음성 분석을 위해 필요합니다.');
                // 성별 선택 드롭다운으로 포커스 이동
                const genderSelect = document.getElementById('learner-gender');
                if (genderSelect) {
                    genderSelect.focus();
                    genderSelect.style.border = '2px solid #ff6b6b';
                    setTimeout(() => {
                        genderSelect.style.border = '';
                    }, 3000);
                }
                return;
            }
            
            // 라디오 버튼 선택
            radio.checked = true;
            
            // 모든 토글 스타일 초기화
            document.querySelectorAll('.learning-method-toggle').forEach(t => {
                t.classList.remove('border-primary', 'bg-light');
                t.classList.add('border');
            });
            
            // 선택한 토글 강조
            toggle.classList.remove('border');
            toggle.classList.add('border-primary', 'bg-light');
            
            // 상세 정보 토글
            const detailsId = method === 'pitch' ? 'pitchDetails' : 'sentenceDetails';
            const otherDetailsId = method === 'pitch' ? 'sentenceDetails' : 'pitchDetails';
            
            // 다른 상세 정보 숨기기
            document.getElementById(otherDetailsId).classList.remove('show');
            
            // 선택한 상세 정보 표시
            const details = document.getElementById(detailsId);
            details.classList.toggle('show');
            
            learningMethod = method;
            
            // 학습 방법에 따라 음성 분석 섹션 표시/숨김
            const audioAnalysisSection = document.getElementById('audioAnalysisSection');
            if (audioAnalysisSection) {
                // 🎯 문장억양연습만 음성 분석 섹션 표시, 음높이 학습은 숨김
                if (method === 'sentence') {
                    audioAnalysisSection.classList.remove('d-none');
                } else {
                    audioAnalysisSection.classList.add('d-none');
                }
            }
            
            // 🎯 학습 방법에 따른 버튼 활성화/비활성화
            updateButtonsByLearningMethod(method);
            
            updateProgress();
        }
    });
    
    // 토글 헤더 클릭시 화살표 회전 (기본 상태: 접혀짐)
    const chevron = document.getElementById('learningMethodChevron');
    if (chevron) {
        // 기본 상태를 0도로 설정 (접혀진 상태)
        chevron.style.transform = 'rotate(0deg)';
    }
    
    document.querySelector('[data-bs-target="#learningMethodCollapse"]')?.addEventListener('click', function() {
        setTimeout(() => {
            const isExpanded = document.getElementById('learningMethodCollapse').classList.contains('show');
            chevron.style.transform = isExpanded ? 'rotate(180deg)' : 'rotate(0deg)';
        }, 150);
    });
    
    // 🎯 중복 제거됨 - onclick 이벤트로 통합 처리
    
    // 초기 상태 설정 - 아무것도 선택되지 않은 상태로 시작
    learningMethod = null; // 명시적으로 null로 설정
    updateButtonsByLearningMethod(null); // 초기 버튼 상태 설정
    
    // 🎯 초기 상태: DOM 로드 후 실행
    setTimeout(() => {
        const methodCards = document.querySelectorAll('.learning-method-toggle');
        console.log(`🎯 초기화: learnerGender=${learnerGender}, 카드 수: ${methodCards.length}`);
        
        if (!learnerGender) {
            methodCards.forEach(card => {
                card.style.opacity = '0.6';
                card.style.pointerEvents = 'none';
                card.classList.add('disabled');
            });
            console.log('🎯 초기 상태: 학습 방법 카드 비활성화');
        } else {
            // 성별이 이미 선택되어 있다면 활성화
            methodCards.forEach(card => {
                card.style.opacity = '1';
                card.style.pointerEvents = 'auto';
                card.classList.remove('disabled');
            });
            console.log('🎯 초기 상태: 학습 방법 카드 활성화 (성별 선택됨)');
        }
    }, 500); // DOM 완전 로드 후 실행
    
    updateProgress();
    
    // 🔥 학습 방법 선택 이벤트 리스너 추가 (중요!)
    const methodToggles = document.querySelectorAll('.learning-method-toggle');
    methodToggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const method = this.dataset.method;
            const radio = this.querySelector('input[type="radio"]');
            
            console.log('🎯 학습 방법 선택 시도:', method);
            
            // 🎯 성별 선택 필수 검증
            if (!learnerGender) {
                alert('먼저 학습자 성별을 선택해주세요.\n성별 정보는 정확한 음성 분석을 위해 필요합니다.');
                // 성별 선택 드롭다운으로 포커스 이동
                const genderSelect = document.getElementById('learner-gender');
                if (genderSelect) {
                    genderSelect.focus();
                    genderSelect.style.border = '2px solid #ff6b6b';
                    setTimeout(() => {
                        genderSelect.style.border = '';
                    }, 3000);
                }
                return;
            }
            
            radio.checked = true;
            console.log('🎯 학습 방법 선택됨:', method);
            
            // 🔥 중요: 전역 변수 업데이트 (이게 빠져있었음!)
            learningMethod = method;
            
            // 모든 토글에서 active 클래스 제거
            methodToggles.forEach(t => t.classList.remove('border-primary', 'bg-light'));
            
            // 현재 토글에 active 클래스 추가
            this.classList.add('border-primary', 'bg-light');
            
            // 학습 방법에 따른 버튼 상태 업데이트
            updateButtonsByLearningMethod(method);
        });
    });
}

// 토글 상세 정보는 HTML에서 직접 관리하므로 이 함수는 제거

function updateProgress() {
    const recordBtn = document.getElementById('btnUnifiedRecord');
    
    // 🎯 간단한 조건으로 변경: 학습방법만 선택되면 활성화
    const canRecord = learningMethod === 'sentence'; // 문장억양연습일 때만 녹음 가능
    
    if (recordBtn) {
        recordBtn.disabled = !canRecord;
        console.log(`🎯 녹음 버튼 상태: ${canRecord ? '활성화' : '비활성화'} (학습방법: ${learningMethod})`);
    }
    
    // 상태 텍스트는 표시하지 않음 (완전 삭제)
}

function startUnifiedRecording() {
    if (learningMethod === 'pitch') {
        // 음높이 학습 모드
        console.log('🎯 음높이 학습 녹음 시작');
        const learningStatus = document.getElementById('learning-status');
        if (learningStatus) {
            learningStatus.textContent = '음높이 연습 중';
        }
        // 기존 피치 테스트 로직 활용
        startPitchTest();
    } else if (learningMethod === 'sentence') {
        // 문장 억양 학습 모드
        console.log('🎯 문장 억양 학습 녹음 시작');
        const learningStatus = document.getElementById('learning-status');
        if (learningStatus) {
            learningStatus.textContent = '문장 억양 연습 중';
        }
        // 기존 마이크 녹음 로직 활용
        startMicRecording();
    }
    
    document.getElementById('btnUnifiedRecord').disabled = true;
    document.getElementById('btnStopRecord').disabled = false;
}

function stopUnifiedRecording() {
    console.log('🎯 통합 녹음 정지');
    
    // 모든 녹음 정지
    if (pitchTestActive) {
        stopPitchTest();
    }
    if (isListening) {
        stopMicRecording();
    }
    
    document.getElementById('btnUnifiedRecord').disabled = false;
    document.getElementById('btnStopRecord').disabled = true;
    
    // 🎯 안전한 DOM 접근
    const learningStatus = document.getElementById('learning-status');
    if (learningStatus) {
        learningStatus.textContent = '녹음 완료';
    }
}

async function analyzeReferenceWithGender(targetGender) {
    if (!$wav.files[0] || !$tg.files[0]) return;
    
    try {
        $status.textContent = `성별 정규화 적용 중... (${detectedReferenceGender} → ${targetGender})`;
        
        // 🎯 성별 정규화는 백엔드에서 자동으로 처리되므로 별도 요청 불필요
        console.log("🎯 성별 정규화는 메인 분석에서 이미 처리되었습니다.");
        
        // 🎯 차트 업데이트만 수행 (이미 정규화된 데이터 사용)
        if (chart && refCurve.length > 0) {
            chart.update('none');
            console.log("🎯 정규화된 차트 업데이트 완료");
        }
        
        $status.textContent = `🎯 성별 정규화 완료! (${detectedReferenceGender} → ${targetGender})`;
        updateButtons();
        return;
        
        // 정규화된 데이터로 차트 업데이트
        if (js.curve && js.syllables) {
            refCurve = js.curve;
            refSyll = js.syllables;
            refStats = js.stats;
            refMedian = js.stats.sentence_median || 200;
            
            console.log('🎯 정규화된 데이터 수신:', refCurve.length, '포인트');
            
            // 차트 업데이트
            if (chart && refCurve.length > 0) {
                const chartData = refCurve.map(p => ({x: p.t, y: p.semitone || 0}));
                chart.data.datasets[0].data = chartData;
                chart.update();
            }
            
            // 음절 분석 테이블 업데이트
            if (js.syllable_analysis) {
                updateSyllableAnalysisTable(js.syllable_analysis);
            }
            
            updateButtons();
            updateProgress(); // 진행률 업데이트
            $status.textContent = `성별 정규화 완료 (${detectedReferenceGender} → ${targetGender})`;
        }
        
    } catch (error) {
        console.error('성별 정규화 오류:', error);
        $status.textContent = '성별 정규화 중 오류가 발생했습니다.';
    }
}
window.addEventListener("load", function() { console.log("페이지 로드 완료"); });

// 🎯 백엔드에서 성별별 음절 피치 데이터 가져오기
async function loadGenderBasedSyllableData() {
    try {
        if (!learnerGender) {
            console.log('🎯 학습자 성별이 선택되지 않았습니다.');
            return null;
        }
        
        console.log(`🎯 성별별 음절 데이터 로딩 시작 (학습자: ${learnerGender})`);
        
        const response = await fetch(`${API_BASE}/api/syllable_pitch_analysis`);
        const data = await response.json();
        
        if (data.analysis && data.analysis.length > 0) {
            console.log(`🎯 백엔드에서 ${data.analysis.length}개 문장 데이터 수신`);
            
            // 학습자 성별에 맞는 버전 선택
            const genderBasedData = data.analysis.map(sentence => {
                const selectedVersion = learnerGender === 'male' ? sentence.male_version : sentence.female_version;
                
                return {
                    sentence_id: sentence.sentence_id,
                    reference_gender: sentence.reference_gender,
                    duration: sentence.duration,
                    base_frequency: selectedVersion.base_frequency,
                    syllables: selectedVersion.syllables
                };
            });
            
            console.log(`🎯 ${learnerGender} 버전 데이터 준비 완료`);
            return genderBasedData;
            
        } else {
            console.error('🎯 백엔드에서 분석 결과가 없습니다.');
            return null;
        }
        
    } catch (error) {
        console.error('🎯 성별별 음절 데이터 로딩 오류:', error);
        return null;
    }
}

// 🎯 선택된 문장의 성별별 데이터를 차트에 표시
async function loadSentenceForLearner(sentenceId) {
    try {
        if (!learnerGender) {
            alert('먼저 학습자 성별을 선택해주세요.');
            return;
        }
        
        console.log(`🎯 문장 로딩: ${sentenceId} (학습자: ${learnerGender})`);
        
        const genderBasedData = await loadGenderBasedSyllableData();
        if (!genderBasedData) {
            alert('음절 데이터를 불러올 수 없습니다.');
            return;
        }
        
        // 선택된 문장 찾기
        const selectedSentence = genderBasedData.find(s => s.sentence_id === sentenceId);
        if (!selectedSentence) {
            alert('선택된 문장을 찾을 수 없습니다.');
            return;
        }
        
        console.log(`🎯 문장 발견: ${selectedSentence.sentence_id}, 기준주파수: ${selectedSentence.base_frequency}Hz`);
        console.log(`🎯 음절 수: ${selectedSentence.syllables.length}개`);
        
        // 🔥 차트에 음절 대표 피치와 구분선 표시
        if (chart) {
            console.log("🔥 CHART UPDATE START");
            
            // 차트 데이터 초기화
            chart.data.datasets[0].data = [];
            chart.data.datasets[1].data = [];
            
            // 🔥 음절 대표 피치를 차트 포인트로 변환 (주황색 점)
            const syllablePoints = selectedSentence.syllables.map(syl => ({
                x: syl.center_time,
                y: syl.semitone,
                label: syl.label || syl.syllable
            }));
            
            console.log("🔥 syllablePoints created:", syllablePoints);
            
            // 🔥 참조 곡선 데이터 (파란 점선) - 연결된 선으로 표시
            const curveData = selectedSentence.syllables.map(syl => ({
                x: syl.center_time,
                y: syl.semitone
            }));
            
            chart.data.datasets[0].data = curveData;
            chart.data.datasets[0].label = `참조음성`;
            
            // 🎯 실시간 피치를 위한 maxTime 캐시 (문장 로드 시)
            if (curveData.length > 0) {
                window.cachedMaxTime = Math.max(...curveData.map(p => p.x));
                console.log("🎯 문장 로드 - maxTime 캐시됨:", window.cachedMaxTime);
            }
            
            // 🔥 음절 대표 피치 점들 (주황색 점)
            chart.data.datasets[1].data = syllablePoints;
            chart.data.datasets[1].hidden = false;
            
            console.log("🔥 Chart datasets updated:");
            console.log("🔥 Dataset 0 (curve):", chart.data.datasets[0].data.length);
            console.log("🔥 Dataset 1 (points):", chart.data.datasets[1].data.length);
            
            // 🔥 음절별 구분선과 보라색 라벨 추가
            try {
                if (selectedSentence.syllables && selectedSentence.syllables.length > 0) {
                    // syllables 구조를 맞춤
                    const syllablesForAnnotation = selectedSentence.syllables.map(syl => ({
                        start: syl.start_time || syl.start || 0,
                        end: syl.end_time || syl.end || 1,
                        label: syl.label || syl.syllable,
                        text: syl.label || syl.syllable
                    }));
                    
                    console.log("🔥 Adding annotations for syllables:", syllablesForAnnotation);
                    addSyllableAnnotations(syllablesForAnnotation);
                }
            } catch (annotError) {
                console.error("🔥 Annotation error:", annotError);
            }
            
            chart.update('none');
            
            console.log("🔥 차트 업데이트 완료: 곡선 + 점 + 구분선");
            
            // 🎵 원본 데이터 저장 (피치 조정용)
            originalSyllableData = selectedSentence.syllables.map(syl => ({
                ...syl,
                original_semitone: syl.semitone
            }));
            
            // 피치 조정 카드 표시
            showPitchAdjustmentCard();
            
            // 음절 분석 테이블 업데이트
            updateSyllableAnalysisTable(selectedSentence.syllables);
            
            // 🎵 참조음성 재생 버튼 활성화
            enableAudioButtons(sentenceId);
            
            // 상태 메시지 업데이트
            const $status = document.getElementById('status');
            if ($status) {
                $status.textContent = `${sentenceId} 문장 로딩 완료 (${selectedSentence.base_frequency}Hz 기준)`;
                $status.style.display = 'block';
            }
        }
        
    } catch (error) {
        console.error('🎯 문장 로딩 오류:', error);
        alert('문장 로딩 중 오류가 발생했습니다.');
    }
}

// 🎵 차트 위치 조정 관련 함수들 (피치변조 제거)
let chartPositionOffset = 0; // 차트 Y축 위치 오프셋

function showPitchAdjustmentCard() {
    const buttons = document.getElementById('pitchAdjustmentButtons');
    if (buttons) {
        buttons.style.display = 'block';
        
        // 버튼 이벤트 리스너 추가 (중복 방지) - 위치 이동만 가능
        const btnPitchDown = document.getElementById('btnPitchDown');
        const btnPitchUp = document.getElementById('btnPitchUp');
        const btnPitchReset = document.getElementById('btnPitchReset');
        
        // 🎯 키 조정 버튼은 항상 활성화 (기능은 adjustChartPosition에서 제어)
        
        if (btnPitchDown && !btnPitchDown.dataset.listenerAdded) {
            btnPitchDown.addEventListener('click', () => {
                console.log('🎯 아래 화살표 버튼 클릭됨');
                adjustChartPosition(-0.5);
            });
            btnPitchDown.dataset.listenerAdded = 'true';
            console.log('🎯 아래 화살표 버튼 이벤트 핸들러 등록 완료');
        }
        if (btnPitchUp && !btnPitchUp.dataset.listenerAdded) {
            btnPitchUp.addEventListener('click', () => {
                console.log('🎯 위 화살표 버튼 클릭됨');
                adjustChartPosition(0.5);
            });
            btnPitchUp.dataset.listenerAdded = 'true';
            console.log('🎯 위 화살표 버튼 이벤트 핸들러 등록 완료');
        }
        if (btnPitchReset && !btnPitchReset.dataset.listenerAdded) {
            btnPitchReset.addEventListener('click', resetChartPosition);
            btnPitchReset.dataset.listenerAdded = 'true';
        }
        
        updateChartPositionDisplay();
    }
}

// 🎯 성별 변경 시 모든 설정 초기화 함수
function resetAllSettingsForGenderChange(newGender) {
    console.log(`🎯 성별 변경으로 인한 전체 초기화: ${newGender}`);
    
    // 1. 피치 조정 설정 초기화
    pitchOffsetSemitones = 0;
    updateChartPositionDisplay();
    
    // 2. 차트 완전 초기화
    if (chart) {
        // 모든 데이터셋 초기화
        chart.data.datasets.forEach(dataset => {
            dataset.data = [];
        });
        
        // 어노테이션 초기화
        if (chart.options.plugins.annotation && chart.options.plugins.annotation.annotations) {
            chart.options.plugins.annotation.annotations = {};
        }
        
        chart.update('none');
    }
    
    // 3. 전역 변수들 초기화
    originalSyllableData = [];
    refCurve = [];
    currentSelectedSentence = null;
    window.currentSelectedSentence = null;
    
    // 4. 오디오 상태 초기화
    stopAllAudio();
    
    // 5. 녹음 관련 초기화
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
    }
    isRecording = false;
    tLive = 0;
    liveStats = {meanF0: 0, maxF0: 0};
    
    // 6. 음높이 테스트 상태 초기화
    pitchTestActive = false;
    targetPitch = null;
    pitchRange = null;
    isSelecting = false;
    rangeStart = null;
    rangeEnd = null;
    chartFrozen = false;
    originalScales = null;
    
    // 7. 버튼 상태 초기화
    if ($btnMic) {
        $btnMic.innerHTML = '<i class="fas fa-microphone me-1"></i> 마이크 녹음';
        $btnMic.classList.remove('btn-danger');
        $btnMic.classList.add('btn-success');
        $btnMic.disabled = true; // 학습방법 선택 전까지 비활성화
    }
    
    if ($btnPlayRef) {
        $btnPlayRef.innerHTML = '<i class="fas fa-play me-1"></i> 참조음성 재생';
        $btnPlayRef.disabled = true;
    }
    
    if ($btnPlayRec) {
        $btnPlayRec.innerHTML = '<i class="fas fa-play me-1"></i> 녹음 재생';
        $btnPlayRec.disabled = true;
    }
    
    // 8. 음절 분석 테이블 숨기기 (음높이 학습 모드에서만)
    const syllableCard = document.getElementById('syllable-analysis-card');
    if (syllableCard && currentLearningMethod !== '참조억양학습') {
        syllableCard.style.display = 'none';
    }
    
    // 9. 피치 조정 버튼 숨기기
    const pitchButtons = document.getElementById('pitchAdjustmentButtons');
    if (pitchButtons) {
        pitchButtons.style.display = 'none';
    }
    
    // 10. 상태 메시지 초기화
    updateStatus(`학습자 성별이 설정되었습니다. 학습 방법을 선택해주세요.`);
    
    // 11. 학습 방법 카드들 활성화 (성별 선택 완료 후)
    const learningCards = document.querySelectorAll('[data-learning-method]');
    learningCards.forEach(card => {
        card.classList.remove('disabled');
        card.style.opacity = '1';
        card.style.pointerEvents = 'auto';
    });
    
    console.log(`🎯 ${newGender} 성별 초기화 완료 - 새로운 학습 세션 시작 준비됨`);
}

function adjustPitch(semitones) {
    pitchOffsetSemitones += semitones;
    console.log(`🎵 피치 조정: ${semitones > 0 ? '+' : ''}${semitones}키, 총 ${pitchOffsetSemitones}키`);
    
    // 🎵 현재 재생 중인 참조음성에 즉시 피치 조정 적용
    if (currentlyPlaying && currentlyPlaying.tagName === 'AUDIO') {
        const playbackRate = Math.pow(2, pitchOffsetSemitones / 12);
        currentlyPlaying.playbackRate = playbackRate;
        console.log(`🎵 실시간 피치 조정 적용: ${pitchOffsetSemitones}키 (재생속도: ${playbackRate.toFixed(3)})`);
    }
    
    // 차트 데이터 업데이트
    if (chart && originalSyllableData.length > 0) {
        // 참조 곡선 업데이트
        const adjustedCurveData = originalSyllableData.map(syl => ({
            x: syl.center_time,
            y: syl.original_semitone + pitchOffsetSemitones
        }));
        
        // 음절 대표 피치 업데이트  
        const adjustedSyllablePoints = originalSyllableData.map(syl => ({
            x: syl.center_time,
            y: syl.original_semitone + pitchOffsetSemitones,
            label: syl.label || syl.syllable
        }));
        
        // 차트 데이터 적용
        chart.data.datasets[0].data = adjustedCurveData;
        chart.data.datasets[1].data = adjustedSyllablePoints;
        
        chart.update('none');
        
        // 테이블도 업데이트
        const adjustedSyllables = originalSyllableData.map(syl => ({
            ...syl,
            semitone: syl.original_semitone + pitchOffsetSemitones
        }));
        updateSyllableAnalysisTable(adjustedSyllables);
        
        console.log(`🎵 차트 업데이트 완료: ${adjustedCurveData.length}개 포인트, 오프셋 ${pitchOffsetSemitones}키`);
    }
    
    updatePitchDisplay();
}

function resetPitch() {
    pitchOffsetSemitones = 0;
    console.log('🎵 피치 초기화');
    
    // 원본 데이터로 복원
    if (chart && originalSyllableData.length > 0) {
        const originalCurveData = originalSyllableData.map(syl => ({
            x: syl.center_time,
            y: syl.original_semitone
        }));
        
        const originalSyllablePoints = originalSyllableData.map(syl => ({
            x: syl.center_time,
            y: syl.original_semitone,
            label: syl.label || syl.syllable
        }));
        
        chart.data.datasets[0].data = originalCurveData;
        chart.data.datasets[1].data = originalSyllablePoints;
        
        chart.update('none');
        
        // 테이블도 원본으로 복원
        updateSyllableAnalysisTable(originalSyllableData);
    }
    
    updatePitchDisplay();
}

function updatePitchDisplay() {
    const offsetElement = document.getElementById('pitchOffset');
    const infoElement = document.getElementById('pitchAdjustInfo');
    
    if (offsetElement) {
        offsetElement.textContent = `${pitchOffsetSemitones > 0 ? '+' : ''}${pitchOffsetSemitones}키`;
        
        // 색상 변경
        offsetElement.className = 'badge mx-2 px-3 py-2';
        if (pitchOffsetSemitones > 0) {
            offsetElement.classList.add('bg-success');
        } else if (pitchOffsetSemitones < 0) {
            offsetElement.classList.add('bg-danger');
        } else {
            offsetElement.classList.add('bg-secondary');
        }
    }
    
    if (infoElement) {
        if (pitchOffsetSemitones === 0) {
            infoElement.textContent = '조정 없음';
            infoElement.className = 'text-primary';
        } else {
            const direction = pitchOffsetSemitones > 0 ? '상승' : '하강';
            infoElement.textContent = `${Math.abs(pitchOffsetSemitones)}키 ${direction}`;
            infoElement.className = pitchOffsetSemitones > 0 ? 'text-success' : 'text-danger';
        }
    }
}

// 🎵 오디오 버튼 활성화 함수
function enableAudioButtons(sentenceId) {
    // 현재 선택된 문장에 대한 참조 오디오 정보 설정
    window.currentSelectedSentence = sentenceId;
    console.log(`🎵 문장 선택됨: ${sentenceId}`);
    
    // 참조음성 재생 버튼 직접 활성화
    if ($btnPlayRef) {
        $btnPlayRef.disabled = false;
        console.log(`🎵 참조음성 재생 버튼 강제 활성화: ${sentenceId}`);
    }
    
    // updateButtons 함수 호출로 전체 버튼 상태 업데이트
    updateButtons();
}

// 🎯 전체 음절 피치 분석 함수 (개발자용 디버깅)
async function performSyllablePitchAnalysis() {
    try {
        console.log('🎯 전체 음절 피치 분석 시작...');
        
        const response = await fetch(`${API_BASE}/api/syllable_pitch_analysis`);
        const data = await response.json();
        
        if (data.analysis && data.analysis.length > 0) {
            console.log(`🎯 분석 완료: ${data.analysis.length}개 문장`);
            
            // 결과를 콘솔에 출력
            data.analysis.forEach(sentence => {
                console.log(`\n📝 ${sentence.sentence_id} (참조성별: ${sentence.reference_gender}, 지속시간: ${sentence.duration.toFixed(2)}초)`);
                
                console.log(`   👨 남성 버전 (기준: ${sentence.male_version.base_frequency}Hz):`);
                sentence.male_version.syllables.forEach(syl => {
                    console.log(`      ${syl.label}: ${syl.f0_hz.toFixed(1)}Hz (${syl.semitone.toFixed(2)}st) [${syl.start_time.toFixed(2)}s-${syl.end_time.toFixed(2)}s]`);
                });
                
                console.log(`   👩 여성 버전 (기준: ${sentence.female_version.base_frequency}Hz):`);
                sentence.female_version.syllables.forEach(syl => {
                    console.log(`      ${syl.label}: ${syl.f0_hz.toFixed(1)}Hz (${syl.semitone.toFixed(2)}st) [${syl.start_time.toFixed(2)}s-${syl.end_time.toFixed(2)}s]`);
                });
            });
            
            // 분석 결과를 전역 변수에 저장 (추후 활용 가능)
            window.syllablePitchAnalysisResults = data.analysis;
            
            console.log(`✅ 음절 피치 분석이 완료되었습니다! ${data.analysis.length}개 문장의 남성/여성 버전 분석 결과를 콘솔에서 확인하세요.`);
            
        } else {
            console.error('🎯 분석 결과가 없습니다.');
        }
        
    } catch (error) {
        console.error('🎯 음절 피치 분석 오류:', error);
    }
}


// 🎤 실시간 녹음 기능 구현
let realtimeAudioContext = null;
let realtimeStream = null;
let realtimeAnalyser = null;
let realtimeDataArray = null;
let realtimeAnimationFrame = null;
let currentTime = 0;

// 🎤 실시간 녹음 시작
async function startRealTimeRecording() {
    try {
        console.log('🎤 실시간 녹음 시작...');
        
        // 🎯 학습자 성별 확인
        const learnerGender = document.getElementById('learner-gender').value;
        if (!learnerGender) {
            alert('먼저 학습자 성별 정보를 선택해주세요.');
            document.getElementById('learner-gender').focus();
            return;
        }
        
        // 🎯 참조 데이터 확인
        const hasRefData = (chart && chart.data.datasets[0].data.length > 0) || window.currentSelectedSentence;
        if (!hasRefData) {
            alert('먼저 참조 음성을 분석하거나 연습 문장을 선택해주세요.');
            return;
        }
        
        // 🎤 마이크 권한 요청
        console.log('🎤 마이크 권한 요청 중...');
        const constraints = {
            audio: {
                sampleRate: 44100,
                channelCount: 1,
                echoCancellation: false,
                noiseSuppression: false,
                autoGainControl: false
            }
        };
        
        realtimeStream = await navigator.mediaDevices.getUserMedia(constraints);
        console.log('🎤 마이크 권한 획득 성공');
        
        realtimeAudioContext = new (window.AudioContext || window.webkitAudioContext)({
            sampleRate: 44100
        });
        console.log('🎤 오디오 컨텍스트 생성 완료');
        
        if (realtimeAudioContext.state === 'suspended') {
            await realtimeAudioContext.resume();
            console.log('🎤 오디오 컨텍스트 재개 완료');
        }
        
        // 🎯 실제 오디오 녹음을 위한 MediaRecorder 설정
        if (!mediaRecorder || mediaRecorder.state === 'inactive') {
            recordedChunks = []; // 초기화
            mediaRecorder = new MediaRecorder(realtimeStream, {
                mimeType: 'audio/webm;codecs=opus'
            });
            
            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    recordedChunks.push(event.data);
                }
            };
            
            mediaRecorder.onstop = () => {
                recordedAudioBlob = new Blob(recordedChunks, { type: 'audio/webm' });
                updateButtons(); // 재생 버튼 활성화
                console.log('🎯 실제 오디오 녹음 완료, 재생 버튼 활성화');
            };
            
            mediaRecorder.start();
            console.log('🎯 MediaRecorder 시작');
        }
        
        // 🎤 오디오 분석 설정
        const source = realtimeAudioContext.createMediaStreamSource(realtimeStream);
        realtimeAnalyser = realtimeAudioContext.createAnalyser();
        realtimeAnalyser.fftSize = 4096;
        realtimeAnalyser.smoothingTimeConstant = 0.8;
        
        source.connect(realtimeAnalyser);
        
        realtimeDataArray = new Float32Array(realtimeAnalyser.fftSize);
        
        // 🎯 녹음 상태 업데이트
        started = true;
        isListening = true; // 🎯 추가: 녹음 중 상태
        currentTime = 0;
        
        // 🎯 버튼 상태 변경
        $btnMic.innerHTML = '<i class="fas fa-record-vinyl me-2 recording-pulse"></i> 녹음중';
        $btnMic.classList.remove('btn-success');
        $btnMic.classList.add('btn-danger', 'btn-recording');
        
        // 🎯 정지 버튼 활성화 (통합 제어 버튼들)
        const $btnStopRecord = document.getElementById('btnStopRecord');
        const $btnUnifiedRecord = document.getElementById('btnUnifiedRecord');
        if ($btnStopRecord) {
            $btnStopRecord.disabled = false;
            $btnStopRecord.innerHTML = '<i class="fas fa-stop me-1"></i> <strong>정지</strong>';
        }
        if ($btnUnifiedRecord) {
            $btnUnifiedRecord.disabled = true;
        }
        
        // 🎯 상태 메시지
        $status.textContent = '🎤 실시간 억양 연습 중... 참조 음성과 비슷하게 발화해보세요!';
        
        // 🎯 실시간 피치 분석 시작
        console.log('🎤 실시간 피치 분석 시작...');
        startRealtimePitchAnalysis();
        
        console.log('🎤 실시간 녹음 시작 완료');
        
    } catch (error) {
        console.error('🎤 녹음 시작 오류:', error);
        
        let errorMsg = "마이크 접근 실패: ";
        if (error.name === 'NotAllowedError') {
            errorMsg += "브라우저에서 마이크 권한을 허용해 주세요.";
        } else if (error.name === 'NotFoundError') {
            errorMsg += "마이크를 찾을 수 없습니다.";
        } else {
            errorMsg += error.message;
        }
        
        $status.textContent = errorMsg;
        stopRealTimeRecording();
    }
}

// 🎤 실시간 녹음 중지
function stopRealTimeRecording() {
    console.log('🎤 실시간 녹음 중지...');
    
    // 🎯 MediaRecorder 정지
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        console.log('🎯 MediaRecorder 정지');
    }
    
    // 🎤 스트림 정리
    if (realtimeStream) {
        realtimeStream.getTracks().forEach(track => track.stop());
        realtimeStream = null;
    }
    
    // 🎤 오디오 컨텍스트 정리
    if (realtimeAudioContext) {
        realtimeAudioContext.close();
        realtimeAudioContext = null;
    }
    
    // 🎤 애니메이션 프레임 정리
    if (realtimeAnimationFrame) {
        cancelAnimationFrame(realtimeAnimationFrame);
        realtimeAnimationFrame = null;
    }
    
    // 🎯 녹음 상태 리셋
    started = false;
    isListening = false; // 🎯 추가: 녹음 정지 상태
    
    // 🎯 버튼 상태 복원
    $btnMic.innerHTML = '<i class="fas fa-microphone me-2"></i> 녹음';
    $btnMic.classList.remove('btn-danger', 'btn-recording');
    $btnMic.classList.add('btn-success');
    
    // 🎯 정지 버튼 비활성화 (통합 제어 버튼들)
    const $btnStopRecord = document.getElementById('btnStopRecord');
    const $btnUnifiedRecord = document.getElementById('btnUnifiedRecord');
    if ($btnStopRecord) {
        $btnStopRecord.disabled = true;
        $btnStopRecord.innerHTML = '<i class="fas fa-stop me-1"></i> <strong>정지</strong>';
    }
    if ($btnUnifiedRecord) {
        $btnUnifiedRecord.disabled = false;
    }
    
    // 🎯 상태 메시지
    $status.textContent = '녹음이 완료되었습니다.';
    
    // 🎯 피치 데이터가 있으면 백업으로 가짜 오디오 생성 (MediaRecorder 실패 시)
    if (liveBuffer.length > 0 && !recordedAudioBlob) {
        console.log('🎯 백업: 피치 데이터로 가짜 오디오 생성');
        const sampleRate = realtimeAudioContext ? realtimeAudioContext.sampleRate : 16000;
        recordedAudioBlob = createWavBlob(liveBuffer, sampleRate);
        updateButtons(); // 재생 버튼 활성화
        console.log('🎯 백업 오디오 데이터 저장 완료, 재생 버튼 활성화');
    }
    
    console.log('🎤 실시간 녹음 중지 완료');
}

// 🎯 liveBuffer를 WAV Blob으로 변환하는 함수
function createWavBlob(audioBuffer, sampleRate) {
    // liveBuffer는 {time, pitch, frequency} 객체 배열이므로
    // 실제 오디오 데이터가 필요함. 대신 음성 합성으로 톤 생성
    const duration = audioBuffer.length * 0.02; // 20ms 간격
    const numSamples = Math.floor(duration * sampleRate);
    const samples = new Float32Array(numSamples);
    
    // 각 pitch 값을 사인파로 변환하여 오디오 생성
    for (let i = 0; i < audioBuffer.length && i < numSamples / (sampleRate * 0.02); i++) {
        const pitch = audioBuffer[i];
        if (pitch && pitch.frequency && pitch.frequency > 0) {
            const frequency = pitch.frequency;
            const startSample = Math.floor(i * sampleRate * 0.02);
            const endSample = Math.min(startSample + Math.floor(sampleRate * 0.02), numSamples);
            
            for (let j = startSample; j < endSample; j++) {
                const t = j / sampleRate;
                samples[j] = 0.3 * Math.sin(2 * Math.PI * frequency * t);
            }
        }
    }
    
    // WAV 헤더 생성
    const wavHeader = createWavHeader(numSamples, sampleRate);
    const wavData = new Int16Array(numSamples);
    
    // Float32 -> Int16 변환
    for (let i = 0; i < numSamples; i++) {
        wavData[i] = Math.max(-32768, Math.min(32767, samples[i] * 32767));
    }
    
    // 최종 WAV Blob 생성
    const wavBlob = new Blob([wavHeader, wavData], {type: 'audio/wav'});
    console.log(`🎯 WAV Blob 생성 완료: ${duration.toFixed(2)}초, ${numSamples}샘플`);
    return wavBlob;
}

// WAV 헤더 생성 함수
function createWavHeader(numSamples, sampleRate) {
    const buffer = new ArrayBuffer(44);
    const view = new DataView(buffer);
    
    // RIFF header
    view.setUint32(0, 0x52494646, false); // "RIFF"
    view.setUint32(4, 36 + numSamples * 2, true); // file size
    view.setUint32(8, 0x57415645, false); // "WAVE"
    
    // fmt chunk
    view.setUint32(12, 0x666d7420, false); // "fmt "
    view.setUint32(16, 16, true); // chunk size
    view.setUint16(20, 1, true); // PCM format
    view.setUint16(22, 1, true); // mono
    view.setUint32(24, sampleRate, true); // sample rate
    view.setUint32(28, sampleRate * 2, true); // byte rate
    view.setUint16(32, 2, true); // block align
    view.setUint16(34, 16, true); // bits per sample
    
    // data chunk
    view.setUint32(36, 0x64617461, false); // "data"
    view.setUint32(40, numSamples * 2, true); // data size
    
    return buffer;
}

// 🎤 실시간 피치 분석
function startRealtimePitchAnalysis() {
    function analyzeFrame() {
        if (!started || !realtimeAnalyser) {
            return;
        }
        
        // 🎤 오디오 데이터 가져오기
        realtimeAnalyser.getFloatTimeDomainData(realtimeDataArray);
        
        // 🎤 YIN 알고리즘으로 피치 추정
        const f0 = estimatePitchYIN(realtimeDataArray, realtimeAudioContext.sampleRate);
        
        if (f0 > 0 && f0 >= 60 && f0 <= 1000) {
            // 🎯 학습자 성별에 맞는 기준 주파수 사용
            const learnerGender = document.getElementById('learner-gender').value;
            const baseFreq = learnerGender === 'male' ? 120 : 220;
            
            // 🎯 Semitone 변환
            const semitone = 12 * Math.log2(f0 / baseFreq);
            
            // 🎯 시간축 고정으로 현재 시간 위치에서 Y축으로만 이동
            updateRealtimePitchDisplay(currentTime, semitone);
        }
        
        // 🎯 시간 증가 (20ms 간격)
        currentTime += 0.02;
        
        // 🎤 다음 프레임 예약
        realtimeAnimationFrame = requestAnimationFrame(analyzeFrame);
    }
    
    analyzeFrame();
}

// 🎯 실시간 피치 표시 업데이트 (시간축 고정, Y축으로만 이동)
let lastUpdateTime = 0;
function updateRealtimePitchDisplay(time, semitone) {
    if (!chart) return;
    
    // 🎯 차트 업데이트 빈도 제한 (50ms마다 한 번 = 20fps)
    const now = performance.now();
    if (now - lastUpdateTime < 50) {
        // 데이터는 계속 저장하되 차트 업데이트는 건너뜀
        const currentLearnerGender = document.getElementById('learner-gender').value;
        liveBuffer.push({
            time: currentTime,
            f0: Math.pow(2, semitone / 12) * (currentLearnerGender === 'male' ? 120 : 220),
            semitone: semitone
        });
        return;
    }
    lastUpdateTime = now;
    
    // 🎯 초록색 실시간 피치선 (Dataset 2)
    const realtimeDataset = chart.data.datasets[2];
    if (!realtimeDataset) return;
    
    // 🎯 maxTime 캐시: 참조 데이터를 실시간으로 읽지 않고 미리 계산된 값 사용
    let maxTime = 10; // 기본값
    
    // 🎯 참조 데이터가 로드될 때 계산된 maxTime 사용 (실시간 중에는 참조 데이터 접근 금지!)
    if (window.cachedMaxTime) {
        maxTime = window.cachedMaxTime;
    } else if (chart.data.datasets[0].data.length > 0) {
        // 처음 한 번만 계산하고 캐시
        maxTime = Math.max(...chart.data.datasets[0].data.map(p => p.x));
        window.cachedMaxTime = maxTime;
    }
    
    // 🎯 현재 보이는 차트 뷰포트 범위에 맞춘 안정적인 가로선
    let viewMinTime = 0;
    let viewMaxTime = maxTime;
    
    // 현재 차트의 실제 표시 범위 가져오기 (줌/스크롤 고려)
    if (chart && chart.scales && chart.scales.x) {
        viewMinTime = chart.scales.x.min || 0;
        viewMaxTime = chart.scales.x.max || maxTime;
    }
    
    // 안정적인 뷰포트 기반 가로선
    realtimeDataset.data = [{
        x: viewMinTime,
        y: semitone
    }, {
        x: viewMaxTime,
        y: semitone
    }];
    
    // 🎯 차트 업데이트 최적화 - 애니메이션 완전 비활성화
    chart.update('none');
    
    // 🎤 실시간 피치 로그 (10번에 1번만 출력)
    if (Math.floor(currentTime * 50) % 10 === 0) {
        console.log(`🎤 실시간 피치: ${semitone.toFixed(2)} 세미톤`);
    }
    
    // 🎯 liveBuffer에 데이터 추가 (재생용)
    const currentLearnerGender = document.getElementById('learner-gender').value;
    liveBuffer.push({
        time: currentTime,
        f0: Math.pow(2, semitone / 12) * (currentLearnerGender === 'male' ? 120 : 220),
        semitone: semitone
    });
}

// 🎤 YIN 알고리즘 피치 추정
function estimatePitchYIN(buffer, sampleRate) {
    const minPeriod = Math.floor(sampleRate / 1000); // 1000Hz 최대
    const maxPeriod = Math.floor(sampleRate / 60);   // 60Hz 최소
    
    if (buffer.length < maxPeriod * 2) return 0;
    
    let bestPeriod = 0;
    let minError = Infinity;
    
    for (let period = minPeriod; period < maxPeriod; period++) {
        let error = 0;
        let count = 0;
        
        for (let i = 0; i < buffer.length - period; i++) {
            const diff = buffer[i] - buffer[i + period];
            error += diff * diff;
            count++;
        }
        
        if (count > 0) {
            error /= count;
            
            if (error < minError) {
                minError = error;
                bestPeriod = period;
            }
        }
    }
    
    if (bestPeriod > 0 && minError < 0.1) {
        return sampleRate / bestPeriod;
    }
    
    return 0;
}

// 🎵 차트 위치 조정 함수들 (데이터만 이동, Y축 고정)
function adjustChartPosition(semitones) {
    console.log(`🎯 키 조정 요청: ${semitones}st, started=${started}, pitchTestActive=${pitchTestActive}`);
    
    // 🎯 키 조정은 항상 허용하되, 실시간 피치 데이터는 절대 건드리지 않음
    
    chartPositionOffset += semitones;
    console.log(`📊 참조 데이터만 위치 조정: ${semitones > 0 ? '+' : ''}${semitones}st, 총 ${chartPositionOffset.toFixed(1)}st`);
    
    if (chart && chart.data && chart.data.datasets) {
        // 🎯 중요: 참조 데이터 (Dataset 0)와 음절 포인트 (Dataset 1)만 이동
        // 실시간 피치선 (Dataset 2)는 절대 이동하지 않음!
        for (let i = 0; i < 2; i++) {
            if (chart.data.datasets[i] && chart.data.datasets[i].data) {
                chart.data.datasets[i].data.forEach(point => {
                    if (point && typeof point.y === 'number') {
                        point.y += semitones;
                    }
                });
            }
        }
        
        // 🎯 어노테이션(음절 라벨)도 이동 - 참조 음성 관련만
        if (chart.options.plugins.annotation && chart.options.plugins.annotation.annotations) {
            Object.values(chart.options.plugins.annotation.annotations).forEach(annotation => {
                // 실시간 피치 관련 어노테이션은 제외 (currentPitchLine, pitchTarget 등)
                if (annotation.id && (annotation.id.includes('currentPitch') || annotation.id.includes('pitchTarget'))) {
                    return; // 실시간 피치 관련은 이동하지 않음
                }
                
                if (annotation.yMin !== undefined) {
                    annotation.yMin += semitones;
                }
                if (annotation.yMax !== undefined) {
                    annotation.yMax += semitones;
                }
                if (annotation.y !== undefined) {
                    annotation.y += semitones;
                }
            });
        }
        
        chart.update('none');
        updateChartPositionDisplay();
        
        console.log(`📊 참조 데이터만 이동 완료: ${chartPositionOffset}st 오프셋, 실시간 피치는 고정 유지`);
    }
}

function resetChartPosition() {
    // 🚨 중요: 녹음 중이거나 음높이 테스트 중에는 키 조정 비활성화
    if (started || pitchTestActive) {
        console.log('🚨 녹음 중이거나 음높이 테스트 중에는 키 조정을 할 수 없습니다');
        return;
    }
    
    if (chartPositionOffset === 0) {
        console.log('📊 이미 초기 위치입니다');
        return;
    }
    
    const resetOffset = -chartPositionOffset; // 원래 위치로 되돌리기
    console.log(`📊 참조 데이터 위치 초기화: ${resetOffset}st 이동`);
    
    if (chart && chart.data && chart.data.datasets) {
        // 🎯 참조 데이터 (Dataset 0)와 음절 포인트 (Dataset 1)만 원위치
        // 실시간 피치선 (Dataset 2)는 절대 건드리지 않음!
        for (let i = 0; i < 2; i++) {
            if (chart.data.datasets[i] && chart.data.datasets[i].data) {
                chart.data.datasets[i].data.forEach(point => {
                    if (point && typeof point.y === 'number') {
                        point.y += resetOffset;
                    }
                });
            }
        }
        
        // 어노테이션(음절 라벨)도 원위치
        if (chart.options.plugins.annotation && chart.options.plugins.annotation.annotations) {
            Object.values(chart.options.plugins.annotation.annotations).forEach(annotation => {
                if (annotation.yMin !== undefined) {
                    annotation.yMin += resetOffset;
                }
                if (annotation.yMax !== undefined) {
                    annotation.yMax += resetOffset;
                }
                if (annotation.y !== undefined) {
                    annotation.y += resetOffset;
                }
            });
        }
        
        chartPositionOffset = 0;
        chart.update('none');
        updateChartPositionDisplay();
        
        console.log('📊 데이터 위치 초기화 완료');
    }
}

function updateChartPositionDisplay() {
    // 기존 함수와 호환성을 위해 빈 함수로 유지
    console.log(`📊 차트 위치 오프셋: ${chartPositionOffset.toFixed(1)}st`);
}
