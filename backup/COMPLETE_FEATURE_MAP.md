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

## 🔍 **React 앱과 기능 비교 분석**

### ✅ **React에 이미 있는 기능**
1. **오디오 녹음/재생** - `useAudioRecording` 훅
2. **피치 차트** - `usePitchChart` 훅  
3. **실시간 피치 분석** - Chart.js 기반
4. **참조 문장 선택** - 드롭다운 UI
5. **기본 상태 관리** - React useState

### ❌ **React에 없는 중요 기능 (이전 필요)**
1. **고급 피치 분석** - YINPitchDetector, enhancedYinPitch
2. **차트 확대/스크롤** - zoomChart, scrollChart  
3. **피치 테스트 모드** - 2포인트 연습, 범위 설정
4. **성별 정규화** - 성별별 피치 조정
5. **음절 주석** - 음절별 분석 테이블
6. **스펙트로그램** - 고급 시각화
7. **설문조사 시스템** - 완전한 폼 관리
8. **자동저장** - 임시저장 기능
9. **고급 유틸리티** - semitone/Q-tone 변환
10. **VAD 음절 추적** - 음성 활동 감지

---

## 🚀 **TypeScript 변환 전략**

### Phase 1: Core 기능 변환
- YINPitchDetector 클래스 → TypeScript 클래스
- 피치 분석 함수들 → 별도 유틸리티 모듈
- 오디오 재생/녹음 → 기존 훅 확장

### Phase 2: UI 컴포넌트 변환  
- 차트 확대/스크롤 → Chart.js 플러그인
- 피치 테스트 → 별도 컴포넌트
- 성별 선택 → 모달 컴포넌트

### Phase 3: 고급 기능 변환
- 설문조사 → React 폼 컴포넌트  
- 음절 분석 → 테이블 컴포넌트
- 스펙트로그램 → Canvas 컴포넌트