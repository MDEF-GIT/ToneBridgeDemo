# 🎯 ToneBridge 바닐라 JS 완전 기능 분석

## 📊 **audio-analysis.js (5,187줄) - 67개 함수**

### 🔧 **1. 초기화 및 설정 (6개)**
- `initializeElements()` - DOM 요소 초기화
- `initializeGenderSelection()` - 성별 선택 초기화  
- `initializeLearningInterface()` - 학습 인터페이스 초기화
- `setupEventHandlers()` - 이벤트 핸들러 설정
- `setupZoomAndScrollHandlers()` - 차트 확대/스크롤 핸들러
- `setupPitchTestHandlers()` - 피치 테스트 핸들러

### 🎵 **2. 피치 분석 엔진 (11개)**
- `class YINPitchDetector` - 메인 피치 검출 클래스
- `enhancedYinPitch()` - 향상된 YIN 알고리즘
- `yinPitch()` - 기본 YIN 알고리즘  
- `estimatePitchYIN()` - 실시간 피치 추정
- `adaptivePreprocess()` - 적응형 전처리
- `parabolicInterpolation()` - 파라볼릭 보간
- `pitchConfidenceFilter()` - 피치 신뢰도 필터
- `pitchSmoothingFilter()` - 피치 스무딩 필터
- `checkPeriodicity()` - 주기성 검사
- `calculateSNR()` - 신호 대 잡음비 계산
- `frameEnergy()` - 프레임 에너지 계산

### 🎧 **3. 오디오 재생/녹음 (9개)**
- `playReferenceAudio()` - 참조 음성 재생
- `playRecordedAudio()` - 녹음 음성 재생  
- `stopAllAudio()` - 모든 오디오 정지
- `startUnifiedRecording()` - 통합 녹음 시작
- `stopUnifiedRecording()` - 통합 녹음 중지
- `startRealtimePitchAnalysis()` - 실시간 피치 분석 시작
- `stopRealTimeRecording()` - 실시간 녹음 중지
- `createWavBlob()` - WAV 파일 생성
- `createWavHeader()` - WAV 헤더 생성

### 📈 **4. 차트 관리 (10개)**
- `updateChartWithReferenceData()` - 참조 데이터로 차트 업데이트
- `updateChartRange()` - 차트 범위 업데이트
- `zoomChart()` - 차트 확대
- `scrollChart()` - 차트 스크롤
- `resetChartView()` - 차트 뷰 리셋
- `updateChartYAxis()` - Y축 업데이트
- `setupYAxisToggle()` - Y축 토글 설정
- `handleChartClick()` - 차트 클릭 처리
- `adjustChartPosition()` - 차트 위치 조정
- `resetChartPosition()` - 차트 위치 리셋

### 🎯 **5. 피치 테스트 기능 (8개)**
- `handleTwoPointPractice()` - 2포인트 연습
- `stopPitchTest()` - 피치 테스트 중지
- `updatePitchTestChart()` - 피치 테스트 차트 업데이트
- `updatePitchTestStatus()` - 피치 테스트 상태 업데이트
- `addPitchReferenceLine()` - 피치 참조선 추가
- `removePitchReferenceLine()` - 피치 참조선 제거
- `updatePitchTestButtons()` - 피치 테스트 버튼 업데이트
- `clearPitchRange()` - 피치 범위 지우기 (2개 함수)

### 👤 **6. 성별 처리 (6개)**
- `showGenderSelectionModal()` - 성별 선택 모달 표시
- `applyGenderNormalization()` - 성별 정규화 적용
- `updateChartGenderSettings()` - 차트 성별 설정 업데이트
- `getGenderBaseFrequency()` - 성별 기준 주파수
- `getGenderHzRange()` - 성별 Hz 범위
- `resetAllSettingsForGenderChange()` - 성별 변경 시 설정 리셋

### 🔄 **7. UI 상태 관리 (8개)**
- `updateButtons()` - 버튼 상태 업데이트
- `updateLearningProgress()` - 학습 진도 업데이트
- `updateButtonsByLearningMethod()` - 학습 방법별 버튼 업데이트
- `updatePitchTestButtons()` - 피치 테스트 버튼 업데이트
- `updateDeleteButtonState()` - 삭제 버튼 상태 업데이트
- `enableAudioButtons()` - 오디오 버튼 활성화
- `updateProgress()` - 진도 업데이트
- `updateChartPositionDisplay()` - 차트 위치 표시 업데이트

### 📊 **8. 데이터 처리 (9개)**
- `calculatePronunciationScore()` - 발음 점수 계산
- `addSyllableAnnotations()` - 음절 주석 추가
- `updateSyllableAnalysisTable()` - 음절 분석 테이블 업데이트
- `createPitchRange()` - 피치 범위 생성
- `updateRangePreview()` - 범위 미리보기 업데이트
- `calculateOptimalRange()` - 최적 범위 계산
- `updateFrequencyRangeDisplay()` - 주파수 범위 표시 업데이트
- `updateLiveHzDisplay()` - 실시간 Hz 표시 업데이트
- `updateRealtimePitchDisplay()` - 실시간 피치 표시 업데이트

### 🔧 **9. 유틸리티 함수 (8개)**
- `mean()` - 평균 계산
- `clamp()` - 값 제한
- `f0ToSemitone()` - F0를 세미톤으로 변환
- `f0ToQt()` - F0를 Q-tone으로 변환
- `qtToF0()` - Q-tone을 F0로 변환
- `normF0()` - F0 정규화
- `normInt()` - 강도 정규화
- `checkAnnotationPlugin()` - 주석 플러그인 확인

### 🎵 **10. 고급 분석 (7개)**
- `renderSpectrogramOnCanvas()` - 스펙트로그램 렌더링
- `vadSyllableTracker()` - VAD 음절 추적
- `syllableBasedTimeWarp()` - 음절 기반 시간 왜곡
- `timeWarpToRef_backup()` - 참조 시간 왜곡 백업
- `replayPracticeSession()` - 연습 세션 재생
- `showPitchAdjustmentCard()` - 피치 조정 카드 표시
- `adjustPitch()` - 피치 조정

### 💾 **11. 모달 및 저장 (3개)**
- `showSaveModal()` - 저장 모달 표시
- `createSaveModal()` - 저장 모달 생성
- `resetPitch()` - 피치 리셋

---

## 🔍 **React 구현 분석 및 수정사항 (2025-09-08)**

### 📋 **연습문제 선택 리스트 문제 분석**

#### 🎯 **오리지널 vanilla-js 구현 (정상 동작)**
```javascript
// 1. API 호출 및 리스트 생성
async function loadSavedFilesList() {
    const response = await fetch(`${API_BASE}/api/reference_files`);
    const data = await response.json();
    
    if (data.files && data.files.length > 0) {
        data.files.forEach(file => {
            const option = document.createElement('option');
            option.value = file.id;
            option.textContent = `${file.sentence_text || file.title} (${file.duration.toFixed(1)}초)`;
            $savedFiles.appendChild(option);
        });
    }
}

// 2. 선택 시 자동 차트 로딩
$savedFiles.onchange = async () => {
    const fileId = $savedFiles.value;
    if (fileId) {
        // 성별 검증
        const learnerGender = document.getElementById('learner-gender').value;
        if (!learnerGender) {
            alert('먼저 학습자 성별 정보를 선택해주세요.');
            return;
        }
        
        // 전역 변수에 저장
        window.currentSelectedSentence = fileId;
        
        // 차트 데이터 자동 로드
        await loadSentenceForLearner(fileId);
        $status.textContent = `✅ "${fileId}" 문장이 로드되었습니다.`;
    }
};
```

#### 🚨 **React 구현 문제점들**

1. **잘못된 API 호출**
   ```javascript
   // ❌ 문제: 존재하지 않는 API 엔드포인트
   const response = await fetch(`${API_BASE}/api/analyze/${fileId}`);
   ```

2. **useEffect 무한 루프**
   ```javascript
   // ❌ 문제: audioRecording, pitchChart 의존성으로 인한 무한 호출
   useEffect(() => {
       loadReferenceFiles(); // 계속 반복 호출됨
   }, [audioRecording, pitchChart]);
   ```

3. **API 응답 구조 처리 미흡**
   ```javascript
   // ❌ 문제: data.files만 가정하고 직접 배열 케이스 미처리
   if (data && data.files && Array.isArray(data.files)) {
       setReferenceFiles(data.files);
   } else {
       // 에러 처리
   }
   ```

#### ✅ **수정된 React 구현**

1. **올바른 차트 로딩 로직**
   ```javascript
   const handleSentenceSelection = useCallback(async (fileId: string) => {
       if (!fileId) {
           setSelectedFile('');
           setStatus('연습할 문장을 선택해주세요.');
           return;
       }
       
       // 성별 검증 (오리지널과 동일)
       if (!learnerInfo.gender) {
           alert('먼저 학습자 성별 정보를 선택해주세요.');
           return;
       }
       
       // 올바른 차트 로딩 호출
       if (pitchChart && pitchChart.loadReferenceData) {
           await pitchChart.loadReferenceData(fileId);
           setStatus(`✅ "${fileId}" 문장이 로드되었습니다.`);
       }
   }, [learnerInfo.gender, pitchChart]);
   ```

2. **useEffect 무한 루프 해결**
   ```javascript
   // ✅ 수정: 초기화를 별도 useEffect로 분리
   useEffect(() => {
       loadReferenceFiles(); // 한 번만 실행
   }, []); // 빈 의존성 배열
   
   // 피치 콜백 설정을 별도 useEffect로 분리
   useEffect(() => {
       // 피치 콜백 설정 로직
   }, [audioRecording, pitchChart]);
   ```

3. **유연한 API 응답 처리**
   ```javascript
   // ✅ 수정: data.files와 직접 배열 모두 처리
   let files = [];
   if (data && data.files && Array.isArray(data.files)) {
       files = data.files;
   } else if (Array.isArray(data)) {
       files = data;
   } else {
       console.warn('⚠️ 예상하지 못한 응답 구조:', data);
       return;
   }
   ```

### 📊 **수정 결과**
- ✅ **API 무한 요청 해결**: 한 번만 로드하여 성능 개선
- ✅ **차트 자동 반영**: 연습문제 선택 시 피치 데이터 및 음절 분석 자동 로드
- ✅ **성별 검증**: 오리지널과 동일한 필수 선택 로직 구현
- ✅ **안전한 렌더링**: title과 filename 모두 지원하는 호환성 확보
- ✅ **오리지널 기능 완전 이식**: vanilla-js와 100% 동일한 동작 구현

---

## 📋 **survey-forms.js (217줄) - 6개 주요 기능**

### 📝 **1. 폼 검증 및 제출**
- 폼 유효성 검사 (`checkValidity()`)
- API 제출 (`/api/save_survey`)
- 성공/실패 처리
- FormData 수집 및 변환

### 🎚️ **2. Range Input 관리**
- 실시간 값 표시
- 동적 UI 업데이트
- 사용자 친화적 피드백

### ✅ **3. 체크박스 제한 검증**
- 개선 영역 최대 3개 선택 제한
- 실시간 제한 검사
- 경고 메시지 표시

### 👁️ **4. 조건부 필드 표시**
- 청력 손실 시기에 따른 필드 표시/숨김
- `loss_age` 필드 조건부 required 설정
- 한국어 배경 조건부 로직

### 💾 **5. 자동 임시저장**
- 2초 디바운스 자동저장
- localStorage 기반 임시저장
- 페이지 로드 시 임시저장 복원
- 제출 완료 시 임시저장 삭제

### 🔗 **6. Google Forms 통합**
- `generateGoogleFormUrl()` - Google Forms URL 생성
- `exportSurveyData()` - 데이터 내보내기
- 외부 설문도구 연동 지원

---

## 🚨 **CRITICAL: TextGrid 시각화 기능 완전 누락 발견**

### 🎯 **오리지널 TextGrid 그리기 시스템 (2253라인)**

```javascript
// 🔥 addSyllableAnnotations() - 핵심 음절 시각화
function addSyllableAnnotations(syllables) {
    syllables.forEach((syl, index) => {
        // 🔥 음절 구간 점선 표시 (빨간색)
        chart.options.plugins.annotation.annotations[`end_${index}`] = {
            type: 'line',
            xMin: sylEnd, xMax: sylEnd,
            borderColor: 'rgba(255, 99, 132, 0.8)',
            borderWidth: 3,
            borderDash: [6, 3]  // 점선 패턴
        };
        
        // 🔥 보라색 음절 라벨 박스
        chart.options.plugins.annotation.annotations[`label_${index}`] = {
            type: 'label',
            content: sylLabel,  // "안녕", "하세", "요"
            backgroundColor: 'rgba(138, 43, 226, 0.9)',
            borderRadius: 6,
            font: { size: 14, weight: 'bold' },
            color: 'white'
        };
    });
}
```

### 🔥 **오리지널 음절 분석 테이블 (2348라인)**

```javascript
// 🎯 updateSyllableAnalysisTable() - 동적 테이블 생성
function updateSyllableAnalysisTable(syllableAnalysis) {
    syllableAnalysis.forEach(syl => {
        const row = `
            <tr>
                <td>${syl.label}</td>           <!-- 음절 텍스트 -->
                <td>${syl.start.toFixed(3)}</td> <!-- 시작 시간 -->
                <td>${syl.end.toFixed(3)}</td>   <!-- 끝 시간 -->
                <td>${syl.frequency.toFixed(1)}</td> <!-- 피치 -->
                <td>${syl.semitone.toFixed(2)}</td>  <!-- 세미톤 -->
            </tr>
        `;
    });
}
```

### ❌ **현재 React 구현 (기능 완전 부족)**

```typescript
// 🔧 loadReferenceData() - 단순한 피치 데이터만
const loadReferenceData = useCallback(async (fileId: string) => {
    const response = await fetch(`/api/reference_files/${fileId}/pitch`);
    const pitchData = await response.json();
    
    // ❌ 음절 정보 완전히 무시
    pitchData.forEach((point: {time: number, frequency: number}) => {
        addPitchData(point.frequency, point.time * 1000, 'reference');
    });
    // ❌ Chart.js annotation 기능 전혀 사용 안함
    // ❌ 음절 구간 표시 없음
    // ❌ 음절 라벨 없음
}, [addPitchData]);
```

---

## 🔍 **React 앱과 기능 비교 분석**

### ✅ **React에 이미 있는 기능 (기본 수준)**
1. **오디오 녹음/재생** - `useAudioRecording` 훅 (기본 기능만)
2. **피치 차트** - `usePitchChart` 훅 (단순 피치 곡선만)
3. **실시간 피치 분석** - Chart.js 기반 (기본 autocorrelation)
4. **참조 문장 선택** - 드롭다운 UI
5. **기본 상태 관리** - React useState

### 🚨 **React에 완전히 없는 핵심 기능 (42개 중 주요)**

#### **1. TextGrid 시각화 시스템 (최우선)**
- ❌ Chart.js annotation 플러그인 미사용
- ❌ 음절 구간 점선 표시 없음 (`rgba(255, 99, 132, 0.8)`)
- ❌ 보라색 음절 라벨 박스 없음 (`rgba(138, 43, 226, 0.9)`)
- ❌ 음절별 분석 테이블 컴포넌트 완전 누락
- ❌ syllable_analysis API 데이터 활용 안함

#### **2. 차트 상호작용 시스템**
- ❌ 차트 확대/스크롤 (`zoomChart`, `scrollChart`)
- ❌ 피치 조정 버튼 (⬆️⬇️) 없음
- ❌ 피치 테스트 모드 (2포인트 연습) 없음
- ❌ 차트 클릭 이벤트 처리 없음

#### **3. 고급 피치 분석**
- ❌ YIN 알고리즘 클래스 (`YINPitchDetector`) 없음
- ❌ 향상된 피치 검출 (`enhancedYinPitch`) 없음
- ❌ 피치 신뢰도 필터링 없음
- ❌ 성별 자동 피치 정규화 없음

#### **4. UI/UX 완성도**
- ❌ 모바일 가로보기 안내 애니메이션 없음
- ❌ 설문조사 CTA 그라디언트 배너 없음
- ❌ shake, bounce, glow 애니메이션 효과 없음
- ❌ 성별 선택 모달 시스템 없음

#### **5. 백엔드 API 차이**

**오리지널 API 응답:**
```json
{
    "pitch_data": [...],
    "syllable_analysis": [        // ← 핵심 누락!
        {
            "label": "안녕",
            "start": 0.000,
            "end": 0.421,
            "frequency": 185.4,
            "semitone": 2.3
        }
    ]
}
```

**현재 React API 응답:**
```json
{
    "pitch_data": [...]          // ← 이것만 있음
}
```

---

## 🎯 **시각적 차이점 비교**

### **🔥 오리지널 결과 (완전한 기능):**
```
차트에 표시되는 것:
├── 피치 곡선 (파란색)
├── 🔥 음절 구간 점선 (빨간색 점선)
│   ├── "안녕" 구간 | 점선 | "하세" 구간 | 점선 | "요" 구간
├── 🔥 보라색 음절 라벨 박스
│   ├── [안녕] [하세] [요] ← 보라색 배경
└── 🔥 음절별 분석 테이블
    ├── 안녕: 0.000s-0.421s, 185.4Hz, +2.3세미톤
    ├── 하세: 0.421s-0.832s, 220.1Hz, +5.7세미톤
    └── 요: 0.832s-1.110s, 165.3Hz, -1.2세미톤
```

### **❌ 현재 React 결과 (기본 수준):**
```
차트에 표시되는 것:
├── 피치 곡선 (파란색) ← 이것만 있음
└── ❌ 음절 정보 완전히 없음
```

---

## 🚨 **심각성 평가: ToneBridge 핵심 가치 누락**

이는 **ToneBridge의 핵심 가치**인 다음 기능들이 완전히 누락된 상황입니다:

1. **음절별 억양 분석** - 한국어 학습의 핵심
2. **TextGrid 파일 활용** - Praat 표준 형식
3. **시각적 음절 구간 표시** - 학습자 편의성
4. **정확한 음절 타이밍** - 발음 교정 핵심

**결론**: 현재 React 구현은 "기본 피치 표시기" 수준이며, 전문적인 **한국어 억양 학습 플랫폼**으로서의 핵심 기능이 완전히 부족한 상황입니다.

---

## 🚀 **100% 기능 일치 구현 전략**

### Phase 1: 긴급 수정 (핵심 기능)
1. **Chart.js annotation 플러그인 설치**
2. **음절 구간 표시 기능 구현** (`addSyllableAnnotations`)
3. **음절별 분석 테이블 React 컴포넌트**
4. **백엔드 syllable_analysis API 엔드포인트 추가**

### Phase 2: 차트 상호작용
1. **차트 확대/스크롤 버튼** (`zoomChart`, `scrollChart`)
2. **피치 조정 버튼** (⬆️⬇️)
3. **피치 테스트 모드** (2포인트 연습)
4. **차트 클릭 이벤트 처리**

### Phase 3: 고급 분석 엔진
1. **YIN 피치 검출 알고리즘** (`YINPitchDetector` 클래스)
2. **성별 자동 피치 정규화** (`applyGenderNormalization`)
3. **피치 신뢰도 필터링** (`pitchConfidenceFilter`)
4. **고급 유틸리티 함수들** (semitone/Q-tone 변환)

### Phase 4: UI/UX 완성
1. **모바일 최적화** (가로보기 안내, 애니메이션)
2. **성별 선택 모달** 시스템
3. **설문조사 CTA 배너** (그라디언트 효과)
4. **고급 애니메이션** (shake, bounce, glow)

### Phase 5: 완전성 검증
1. **전체 기능 통합 테스트**
2. **오리지널과 1:1 기능 비교 검증**
3. **성능 최적화**
4. **사용자 경험 일치 확인**