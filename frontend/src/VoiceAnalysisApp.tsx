/**
 * ToneBridge Voice Analysis - index.html 완전 재현
 * 한국어 억양 학습 플랫폼의 모든 기능 구현
 */
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { ReferenceFile, LearnerInfo, LearningMethod, SyllableData } from './types/api';
import { useAudioRecording } from './hooks/useAudioRecording';
import { usePitchChart } from './hooks/usePitchChart';
import { useDualAxisChart } from './hooks/useDualAxisChart';
// import { PitchTestMode } from './components/PitchTestMode';
// import { ChartControls } from './components/ChartControls';
import './custom.css';

const VoiceAnalysisApp: React.FC = () => {
  // 🎯 학습자 정보 및 학습 방법
  const [learnerInfo, setLearnerInfo] = useState<LearnerInfo>({
    name: '',
    gender: '',
    ageGroup: ''
  });
  const [learningMethod, setLearningMethod] = useState<LearningMethod>('');
  
  // 🎯 UI 상태 관리
  const [showSentenceDetails, setShowSentenceDetails] = useState<boolean>(false);
  const [showPitchDetails, setShowPitchDetails] = useState<boolean>(false);
  const [showAudioAnalysisSection, setShowAudioAnalysisSection] = useState<boolean>(false);
  const [showSyllableAnalysis] = useState<boolean>(false);
  const [showGenderModal, setShowGenderModal] = useState<boolean>(false);
  const [selectedGender, setSelectedGender] = useState<string>('');
  
  // 🎯 참조 파일 및 분석 상태
  const [referenceFiles, setReferenceFiles] = useState<ReferenceFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [status, setStatus] = useState<string>('');
  
  // const [analysisResult] = useState<AnalysisResult | null>(null);
  const [syllableData] = useState<SyllableData[]>([]);
  
  // 🎯 차트 설정
  const [yAxisUnit, setYAxisUnit] = useState<'semitone' | 'qtone'>('semitone');
  
  // 🎯 API Base URL
  const API_BASE = '';
  
  // 🎯 Refs
  const chartRef = useRef<HTMLCanvasElement>(null);
  const dualAxisCanvasRef = useRef<HTMLCanvasElement>(null);
  
  // 🎯 Hooks  
  const audioRecording = useAudioRecording();
  const pitchChart = usePitchChart(chartRef, API_BASE);
  const dualAxisChart = useDualAxisChart(dualAxisCanvasRef, API_BASE);
  
  // 🎯 애니메이션 스타일 주입
  useEffect(() => {
    const styleElement = document.createElement('style');
    styleElement.textContent = `
      .shake-animation { animation: shake 4s infinite; }
      .bounce-animation { animation: bounce 2s infinite; }
      .blink { animation: blink 1s infinite; }
      @keyframes blink {
        0%, 50% { opacity: 1; }
        51%, 100% { opacity: 0.3; }
      }
    `;
    document.head.appendChild(styleElement);
    
    return () => {
      if (document.head.contains(styleElement)) {
        document.head.removeChild(styleElement);
      }
    };
  }, []);

  // 🎯 초기화 (한 번만 실행)
  useEffect(() => {
    loadReferenceFiles();
    console.log('🎯 ToneBridge Voice Analysis App initialized');
  }, []); // 빈 의존성 배열로 한 번만 실행
  
  // 🎯 피치 콜백 설정 (별도 useEffect)
  useEffect(() => {
    if (audioRecording && audioRecording.setPitchCallback) {
      console.log('🎯 피치 콜백 설정 중...');
      audioRecording.setPitchCallback((frequency: number, timestamp: number) => {
        console.log(`🎤 실시간 피치 데이터: ${frequency.toFixed(2)}Hz, 시간: ${timestamp}`);
        if (pitchChart && pitchChart.addPitchData) {
          pitchChart.addPitchData(frequency, timestamp, 'live');
        }
        // 🎯 듀얼축 차트에도 동시에 데이터 추가
        if (dualAxisChart && dualAxisChart.addDualAxisData) {
          dualAxisChart.addDualAxisData(frequency, timestamp, 'live');
        }
      });
    } else {
      console.warn('⚠️ audioRecording 또는 setPitchCallback이 없습니다');
    }
  }, [audioRecording, pitchChart, dualAxisChart]);

  // 🎯 참조 파일 로딩 (오리지널과 동일한 로직)
  const loadReferenceFiles = async () => {
    try {
      setIsLoading(true);
      setStatus('참조 파일을 로딩 중입니다...');
      
      const response = await fetch(`${API_BASE}/api/reference_files`);
      const data = await response.json();
      
      console.log('🎯 API 응답 데이터:', data);
      
      // 🎯 오리지널처럼 data.files 또는 직접 배열 처리
      let files = [];
      if (data && data.files && Array.isArray(data.files)) {
        files = data.files;
      } else if (Array.isArray(data)) {
        files = data;
      } else {
        console.warn('⚠️ 예상하지 못한 응답 구조:', data);
        setStatus('참조 파일 로딩 실패: 잘못된 응답 구조');
        return;
      }
      
      setReferenceFiles(files);
      console.log(`✅ ToneBridge Backend Service: 연결됨 (참조 파일 ${files.length}개 로드됨)`);
      setStatus('');
      
    } catch (error) {
      console.error('❌ 참조 파일 로딩 실패:', error);
      setStatus('백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.');
    } finally {
      setIsLoading(false);
    }
  };

  // 🎯 학습자 정보 업데이트
  const updateLearnerInfo = useCallback((field: keyof LearnerInfo, value: string) => {
    setLearnerInfo(prev => ({ ...prev, [field]: value }));
  }, []);
  
  // 🎯 학습 방법 선택
  const handleLearningMethodChange = useCallback((method: LearningMethod) => {
    // 🎯 성별 선택 필수 검증 (원본 로직)
    if (!learnerInfo.gender) {
      alert('먼저 학습자 성별을 선택해주세요.\n성별 정보는 정확한 음성 분석을 위해 필요합니다.');
      return;
    }
    
    setLearningMethod(method);
    
    if (method === 'pitch') {
      setShowPitchDetails(true);
      setShowSentenceDetails(false);
      setShowAudioAnalysisSection(false);
    } else if (method === 'sentence') {
      setShowSentenceDetails(true);
      setShowPitchDetails(false);
      setShowAudioAnalysisSection(true);
    } else {
      setShowSentenceDetails(false);
      setShowPitchDetails(false);
      setShowAudioAnalysisSection(false);
    }
  }, [learnerInfo.gender]);
  
  // 🎯 연습 문장 선택 (오리지널과 동일한 로직)
  const handleSentenceSelection = useCallback(async (fileId: string) => {
    if (!fileId) {
      setSelectedFile('');
      setStatus('연습할 문장을 선택해주세요.');
      return;
    }
    
    // 🎯 학습자 성별 확인 (오리지널 로직)
    if (!learnerInfo.gender) {
      alert('먼저 학습자 성별 정보를 선택해주세요.');
      return;
    }
    
    setSelectedFile(fileId);
    setIsLoading(true);
    setStatus(`"${fileId}" 문장을 불러오는 중...`);
    
    try {
      console.log(`🎯 연습 문장 선택됨: ${fileId}`);
      
      // 🎯 오리지널처럼 pitchChart.loadReferenceData 호출
      if (pitchChart && pitchChart.loadReferenceData) {
        await pitchChart.loadReferenceData(fileId);
        
        // 🎯 듀얼축 차트에도 참조 데이터 로딩 (시간 정규화 적용)
        try {
          const response = await fetch(`${API_BASE}/api/reference_files/${encodeURIComponent(fileId)}/pitch`);
          if (response.ok) {
            const pitchData = await response.json();
            // 듀얼축 차트 클리어 후 참조 데이터 추가
            dualAxisChart.clearChart();
            
            // 🎯 시간 정규화: 첫 번째 시간값을 0으로 만들기
            const firstTime = pitchData.length > 0 ? pitchData[0].time : 0;
            console.log(`🎯 듀얼차트 시간 정규화: 첫 번째 시간 ${firstTime.toFixed(2)}s를 0s로 조정`);
            
            pitchData.forEach((point: any) => {
              // 시간값 정규화: 첫 번째 시간을 빼서 0부터 시작
              const normalizedTime = point.time - firstTime;
              dualAxisChart.addDualAxisData(point.frequency, normalizedTime, 'reference');
            });
            console.log(`📊 듀얼축 차트에 참조 데이터 로딩 완료: ${fileId} (${pitchData.length}개 포인트)`);
          }
        } catch (error) {
          console.warn('⚠️ 듀얼축 차트 참조 데이터 로딩 실패:', error);
        }
        
        setStatus(`✅ "${fileId}" 문장이 로드되었습니다. 참조음성 재생 또는 녹음 연습을 시작하세요.`);
        console.log('🎯 차트 업데이트 완료!');
      } else {
        console.warn('⚠️ pitchChart.loadReferenceData가 없습니다');
        setStatus('차트 로딩 중 오류가 발생했습니다.');
      }
      
    } catch (error) {
      console.error('🎯 문장 로딩 오류:', error);
      setStatus('문장 로딩 중 오류가 발생했습니다.');
    } finally {
      setIsLoading(false);
    }
  }, [learnerInfo.gender, pitchChart, dualAxisChart, API_BASE]);
  
  // 🎯 녹음 제어
  const handleRecording = useCallback(() => {
    if (audioRecording.isRecording) {
      audioRecording.stopRecording();
      setStatus('녹음이 완료되었습니다.');
      // 🟢 녹음 중지 시 실시간 가로바 숨김
      if (pitchChart && pitchChart.hideRealtimePitchLine) {
        pitchChart.hideRealtimePitchLine();
      }
    } else {
      audioRecording.startRecording();
      setStatus('🎤 녹음 중... 말씀해 주세요.');
    }
  }, [audioRecording, pitchChart]);
  
  // 🎯 재생 기능
  const handlePlayRecording = useCallback(() => {
    if (audioRecording.recordedBlob) {
      audioRecording.playRecordedAudio();
      setStatus('🔊 녹음된 음성을 재생합니다.');
    } else {
      setStatus('재생할 녹음이 없습니다.');
    }
  }, [audioRecording]);
  
  const handlePlayReference = useCallback(() => {
    if (selectedFile) {
      const audio = new Audio(`${API_BASE}/static/reference_files/${selectedFile}.wav`);
      audio.play().catch(err => console.error('참조 음성 재생 실패:', err));
      setStatus('🔊 참조 음성을 재생합니다.');
    }
  }, [selectedFile, API_BASE]);


  // 🎯 Y축 단위 변경을 두 차트에 전달
  useEffect(() => {
    console.log(`🎯 VoiceAnalysisApp: Y축 단위 변경 감지됨 ${yAxisUnit}, 두 차트에 전달`);
    if (pitchChart && pitchChart.setYAxisUnit) {
      pitchChart.setYAxisUnit(yAxisUnit);
    }
    if (dualAxisChart && dualAxisChart.setYAxisUnit) {
      dualAxisChart.setYAxisUnit(yAxisUnit);
    }
  }, [yAxisUnit, pitchChart, dualAxisChart]);
  
  // 🎯 성별 선택 모달
  const handleGenderSelection = useCallback((gender: string) => {
    setSelectedGender(gender);
  }, []);
  
  const confirmGenderSelection = useCallback(() => {
    if (selectedGender) {
      updateLearnerInfo('gender', selectedGender);
      setShowGenderModal(false);
      setSelectedGender('');
    }
  }, [selectedGender, updateLearnerInfo]);

  // 🎯 파일 업로드 처리
  const [uploadFiles, setUploadFiles] = React.useState<{wav: File | null, textgrid: File | null}>({
    wav: null,
    textgrid: null
  });
  const [isUploading, setIsUploading] = React.useState(false);

  const handleFileUpload = useCallback(async () => {
    if (!uploadFiles.wav || !learnerInfo.gender) {
      alert('WAV 파일을 선택하고 학습자 성별을 설정해주세요.');
      return;
    }

    setIsUploading(true);
    setStatus('파일을 업로드하고 분석 중입니다...');

    try {
      const formData = new FormData();
      formData.append('wav', uploadFiles.wav);
      if (uploadFiles.textgrid) {
        formData.append('textgrid', uploadFiles.textgrid);
      }
      formData.append('learner_gender', learnerInfo.gender);
      formData.append('learner_name', learnerInfo.name || '사용자');

      const response = await fetch(`${API_BASE}/analyze_ref?t=${Date.now()}`, {
        method: 'POST',
        body: formData,
        cache: 'no-cache',
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache'
        }
      });

      if (response.ok) {
        const result = await response.json();
        setStatus('✅ 파일 분석이 완료되었습니다! 차트를 확인해보세요.');
        console.log('🎯 업로드 분석 결과:', result);
        
        // 분석 결과를 차트에 반영
        if (pitchChart && result.pitch_data) {
          // TODO: 업로드된 파일 분석 결과를 차트에 표시
        }
      } else {
        setStatus('파일 업로드 중 오류가 발생했습니다.');
      }
    } catch (error) {
      console.error('파일 업로드 오류:', error);
      setStatus('파일 업로드 중 오류가 발생했습니다.');
    } finally {
      setIsUploading(false);
    }
  }, [uploadFiles, learnerInfo, API_BASE, pitchChart]);

  return (
    <>
      {/* 🎯 base.html 템플릿 구조 준수: {% block content %} 영역 */}
      <div className="container">
        <div className="row justify-content-center">
          <div className="col-lg-10">


          {/* 🎯 개인화 코칭 설문 CTA (오리지날 HTML 구조) */}
          <div className="alert alert-primary d-flex align-items-center mb-4 survey-cta" style={{
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', 
            border: 'none', 
            borderRadius: '12px', 
            boxShadow: '0 4px 15px rgba(102, 126, 234, 0.3)'
          }}>
            <div className="flex-grow-1 text-white">
              <div className="d-flex align-items-center mb-2">
                <i className="fas fa-graduation-cap fa-2x me-3" style={{color: '#ffd700'}}></i>
                <div>
                  <h5 className="mb-1 fw-bold">데모학습 후, 더 정확한 개인화 코칭을 위해</h5>
                  <p className="mb-0 small opacity-90">3분 설문 참여로 서비스 품질 향상에 힘을 보태주세요!</p>
                </div>
              </div>
              <div className="d-flex flex-wrap gap-2 small">
                <span className="badge bg-warning text-dark">
                  <i className="fas fa-check me-1"></i>개선 의견 남기기
                </span>
                <span className="badge bg-info">
                  <i className="fas fa-bell me-1"></i>신기능 알림 신청
                </span>
                <span className="badge bg-success">
                  <i className="fas fa-users me-1"></i>파일럿 프로그램 참여
                </span>
              </div>
            </div>
            <div className="ms-3">
              <Link 
                to="/survey" 
                className="btn btn-warning btn-lg fw-bold px-4 py-2 text-decoration-none" 
                style={{
                  borderRadius: '25px', 
                  boxShadow: '0 3px 10px rgba(255, 193, 7, 0.4)'
                }}
              >
                <i className="fas fa-clipboard-list me-2"></i>3분 설문하기
              </Link>
            </div>
          </div>

          {/* 🎯 휴대폰 가로보기 안내 */}
          <div className="alert border-0 text-center mb-4 mobile-warning" style={{
            background: 'linear-gradient(135deg, #ff6b6b 0%, #ee5a52 100%)',
            borderRadius: '12px',
            boxShadow: '0 2px 15px rgba(255, 107, 107, 0.3)'
          }}>
            <div className="d-flex align-items-center justify-content-center">
              <i 
                className="fas fa-mobile-alt me-2 bounce-animation" 
                style={{color: 'white', fontSize: '1.2em'}}
              ></i>
              <span 
                className="fw-bold text-white" 
                style={{
                  fontSize: '1.1em', 
                  textShadow: '0 1px 3px rgba(0,0,0,0.2)'
                }}
              >
                📱 휴대폰접속은 "
                <span style={{
                  color: '#ffff00', 
                  fontWeight: 'bold', 
                  fontSize: '1.3em', 
                  textShadow: '0 1px 2px rgba(0,0,0,0.7)'
                }}>
                  가로보기<span style={{color: '#ffff00'}}>로</span>
                </span>" !! 📱
              </span>
            </div>
            <div className="mt-2" style={{color: '#ffff00', fontSize: '0.9em', fontWeight: 'normal'}}>
              (PC & 마이크 사용을 더욱 권장합니다)
            </div>
          </div>

          {/* 🎯 학습자 정보 입력 */}
          <div className="card mb-4">
            <div className="card-header">
              <h5 className="mb-0 fw-bold" style={{color: '#ff6b35'}}>
                <i className="fas fa-user me-2"></i>학습자 정보
              </h5>
            </div>
            <div className="card-body">
              <div className="row g-3">
                <div className="col-md-4">
                  <label htmlFor="learner-name" className="form-label">이름 (선택)</label>
                  <input 
                    type="text" 
                    className="form-control" 
                    id="learner-name" 
                    placeholder="예: 김학습"
                    value={learnerInfo.name}
                    onChange={(e) => updateLearnerInfo('name', e.target.value)}
                  />
                </div>
                <div className="col-md-4">
                  <label htmlFor="learner-gender" className="form-label">
                    성별 <span className="text-danger">*</span>
                  </label>
                  <select 
                    className="form-select" 
                    id="learner-gender" 
                    required
                    value={learnerInfo.gender}
                    onChange={(e) => updateLearnerInfo('gender', e.target.value)}
                  >
                    <option value="">선택하세요</option>
                    <option value="male">남성</option>
                    <option value="female">여성</option>
                  </select>
                </div>
                <div className="col-md-4">
                  <label htmlFor="learner-level" className="form-label">연령대 (선택)</label>
                  <select 
                    className="form-select" 
                    id="learner-level"
                    value={learnerInfo.ageGroup}
                    onChange={(e) => updateLearnerInfo('ageGroup', e.target.value)}
                  >
                    <option value="">선택하세요</option>
                    <option value="10대">10대</option>
                    <option value="20대">20대</option>
                    <option value="30대">30대</option>
                    <option value="40대">40대</option>
                    <option value="50대">50대</option>
                    <option value="60대이상">60대이상</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          {/* 🎯 파일 업로드 분석 */}
          <div className="card mb-4">
            <div className="card-header">
              <h5 className="mb-0 fw-bold" style={{color: '#e67e22'}}>
                <i className="fas fa-cloud-upload-alt me-2"></i>내 음성 파일 분석하기
              </h5>
              <small className="text-muted">WAV 파일을 업로드해서 정밀 분석을 받아보세요</small>
            </div>
            <div className="card-body">
              <div className="row g-3">
                <div className="col-md-6">
                  <label htmlFor="wav-file" className="form-label">
                    WAV 파일 <span className="text-danger">*</span>
                  </label>
                  <input 
                    type="file" 
                    className="form-control" 
                    id="wav-file"
                    accept=".wav,audio/wav"
                    onChange={(e) => setUploadFiles(prev => ({
                      ...prev,
                      wav: e.target.files?.[0] || null
                    }))}
                  />
                  <small className="text-muted">한국어 음성이 녹음된 WAV 파일을 선택하세요</small>
                </div>
                <div className="col-md-6">
                  <label htmlFor="textgrid-file" className="form-label">TextGrid 파일 (선택)</label>
                  <input 
                    type="file" 
                    className="form-control" 
                    id="textgrid-file"
                    accept=".TextGrid,.textgrid"
                    onChange={(e) => setUploadFiles(prev => ({
                      ...prev,
                      textgrid: e.target.files?.[0] || null
                    }))}
                  />
                  <small className="text-muted">음절 구간 정보가 포함된 TextGrid 파일 (선택)</small>
                </div>
              </div>
              <div className="mt-3 text-center">
                <button 
                  className="btn btn-primary btn-lg px-4"
                  onClick={handleFileUpload}
                  disabled={!uploadFiles.wav || !learnerInfo.gender || isUploading}
                >
                  {isUploading ? (
                    <>
                      <i className="fas fa-spinner fa-spin me-2"></i>
                      분석 중...
                    </>
                  ) : (
                    <>
                      <i className="fas fa-chart-line me-2"></i>
                      파일 분석하기
                    </>
                  )}
                </button>
              </div>
              {uploadFiles.wav && (
                <div className="mt-3 alert alert-info">
                  <i className="fas fa-file-audio me-2"></i>
                  선택된 파일: <strong>{uploadFiles.wav.name}</strong>
                  {uploadFiles.textgrid && (
                    <span className="ms-3">
                      <i className="fas fa-file-alt me-1"></i>
                      TextGrid: <strong>{uploadFiles.textgrid.name}</strong>
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* 🎯 학습 방법 선택 */}
          <div className="card mb-3">
            <div className="card-header">
              <h5 className="mb-0 fw-bold" style={{color: '#ff6b35'}}>
                <i className="fas fa-graduation-cap me-2"></i>학습 방법 선택
              </h5>
            </div>
            <div className="card-body">
              <div className="row g-2">
                <div className="col-md-6">
                  <div 
                    className={`d-flex align-items-center p-2 border rounded learning-method-toggle ${!learnerInfo.gender ? 'disabled' : ''} ${learningMethod === 'pitch' ? 'border-primary' : ''}`}
                    style={{cursor: learnerInfo.gender ? 'pointer' : 'not-allowed'}}
                    onClick={() => handleLearningMethodChange('pitch')}
                  >
                    <div className="form-check me-3">
                      <input 
                        className="form-check-input" 
                        type="radio" 
                        name="learningMethod" 
                        id="methodPitch" 
                        value="pitch"
                        checked={learningMethod === 'pitch'}
                        disabled={!learnerInfo.gender}
                        onChange={() => handleLearningMethodChange('pitch')}
                      />
                    </div>
                    <div className="flex-grow-1">
                      <h6 className="mb-1">
                        <i className="fas fa-music me-2 text-primary"></i>
                        음높이 학습 <span className="text-danger fw-bold">(준비중)</span>
                      </h6>
                      <small className="text-muted">특정 음높이를 목표로 하여 정확한 높낮이 연습</small>
                    </div>
                  </div>
                  
                  {showPitchDetails && (
                    <div className="mt-2">
                      <div className="ps-4 small">
                        <div className="alert alert-light border-primary mb-3">
                          <strong>🎯 학습목표:</strong> 내 목소리 높낮이 변화를 시청각적으로 인지해봅니다.
                        </div>
                        
                        <h6 className="text-primary mb-2">1. 참조선 미정</h6>
                        <p className="mb-1">
                          <strong>a.</strong> [녹음] 버튼을 누르고, /아/ 소리를 길게 냅니다. 
                          하단 그래프 안에 빨간 선이 나타나면 현재 음의 높낮이를 파악합니다.
                        </p>
                        <p className="mb-1">
                          <strong>b.</strong> 현재 음과 높낮이 차이가 점점 커지도록 소리를 번갈아 내보세요.
                        </p>
                        <p className="mb-3">
                          <strong>c.</strong> 이번엔 음높이 차이가 거의 나지 않을 때까지 소리를 번갈아 내보세요.
                        </p>
                        
                        <h6 className="text-primary mb-2">2. 참조선 정하기</h6>
                        <p className="mb-1">
                          <strong>a.</strong> 하단 그래프 내 한 지점을 클릭합니다.
                        </p>
                        <div className="ps-3 mb-2">
                          <p className="mb-1 text-muted">- 더블클릭 시, 하나의 참조선 생성</p>
                          <p className="mb-0 text-muted">- 드래그 시, 범위 지정 가능</p>
                        </div>
                        <p className="mb-0">
                          <strong>b.</strong> [녹음] 버튼을 누르고, 빨간 선이 상한선과 하한선을 
                          왔다갔다 하도록 높낮이를 번갈아 소리내보세요.
                        </p>
                      </div>
                    </div>
                  )}
                </div>
                
                <div className="col-md-6">
                  <div 
                    className={`d-flex align-items-center p-2 border rounded learning-method-toggle ${!learnerInfo.gender ? 'disabled' : ''} ${learningMethod === 'sentence' ? 'border-primary' : ''}`}
                    style={{cursor: learnerInfo.gender ? 'pointer' : 'not-allowed'}}
                    onClick={() => handleLearningMethodChange('sentence')}
                  >
                    <div className="form-check me-3">
                      <input 
                        className="form-check-input" 
                        type="radio" 
                        name="learningMethod" 
                        id="methodSentence" 
                        value="sentence"
                        checked={learningMethod === 'sentence'}
                        disabled={!learnerInfo.gender}
                        onChange={() => handleLearningMethodChange('sentence')}
                      />
                    </div>
                    <div className="flex-grow-1">
                      <h6 className="mb-1">
                        <i className="fas fa-wave-square me-2 text-success"></i>참조억양학습
                      </h6>
                      <small className="text-muted">참조 음성의 억양 패턴을 따라 자연스럽게 말하기</small>
                    </div>
                  </div>
                  
                  {showSentenceDetails && (
                    <div className="mt-2">
                      <div className="ps-4 small">
                        <div className="alert alert-light border-success mb-3">
                          <strong>🎯 학습목표:</strong> 참조 음성의 억양 패턴을 따라 자연스럽게 말하기
                        </div>
                        
                        <p className="mb-2">
                          <strong>1. 🎯 첫 목표는 참조음성의 
                          <span style={{
                            backgroundColor: '#fff3cd', 
                            color: '#856404', 
                            padding: '2px 6px', 
                            borderRadius: '4px', 
                            fontWeight: 'bold'
                          }}>음도범위(Pitch range)</span> 
                          내에서 최대점과 최소점을 비슷하게 만들어보세요.</strong><br />
                          <small className="text-muted">
                            *바로 이웃한 두 음의 차이보다는, 하나의 리듬을 만들어내는 
                            <span style={{color: '#6f42c1', fontWeight: 'bold'}}>[말토막]</span>의 
                            첫음과 끝음을 목표로 합니다.
                          </small>
                        </p>
                        
                        <p className="mb-2">
                          <strong>2. 🎤 [녹음]클릭 후, /아/ 발음을 길게 내면서 나에게 편안한 첫 음을 잡으세요.</strong><br />
                          <small className="text-muted">
                            이때 <span style={{color: '#28a745', fontWeight: 'bold'}}>
                            🟢 초록색 실시간 음도피드백 곡선</span>이 나타납니다. * 
                            <span style={{color: '#dc3545', fontWeight: 'bold'}}>
                            ⬆️화살표⬇️를 통해 참조음성의 억양 그래프 위치를 나의 음에 맞춥니다</span>.
                          </small>
                        </p>
                        
                        <p className="mb-0">
                          <strong>3. 🎵 점점 서로 가까운 음들과의 
                          <span style={{
                            color: '#17a2b8', 
                            backgroundColor: '#e7f3ff', 
                            padding: '2px 6px', 
                            borderRadius: '4px', 
                            fontWeight: 'bold'
                          }}>상대적인 차이</span>를 보고 들으며 따라 말해보세요.</strong>
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* 🎯 연습 문장 선택 및 안내 동영상 (참조억양학습시에만 표시) */}
          {showAudioAnalysisSection && (
            <div className="mb-4" style={{marginTop: '1.5rem'}}>
              <div className="row g-4 w-100">
                {/* 연습 문장 선택 */}
                <div className="col-md-7">
                  <div className="alert alert-info border-0" style={{
                    background: 'linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%)', 
                    borderRadius: '12px'
                  }}>
                    <div className="d-flex align-items-center mb-3">
                      <i className="fas fa-lightbulb me-2 text-primary"></i>
                      <h6 className="mb-0 fw-bold text-primary">
                        🎯 미리 준비된 연습 문장으로 바로 시작하세요!
                      </h6>
                    </div>
                    <p className="mb-3 small text-primary opacity-75">
                      아래에서 연습하고 싶은 문장을 선택하면 바로 억양 학습을 시작할 수 있습니다.
                    </p>
                    
                    <div>
                      <label className="form-label fw-bold text-primary mb-2">
                        <i className="fas fa-star me-1"></i> 연습 문장 선택
                      </label>
                      <select 
                        className="form-control form-control-sm"
                        value={selectedFile}
                        onChange={(e) => {
          console.log('🎯 드롭다운 변경됨:', e.target.value);
          handleSentenceSelection(e.target.value);
        }}
                      >
                        <option value="">연습할 문장을 선택하세요...</option>
                        {referenceFiles.map((file) => (
                          <option key={file.id} value={file.id}>
                            {file.title || file.filename} ({file.duration?.toFixed(1) || '0.0'}초)
                          </option>
                        ))}
                      </select>
                      <small className="text-primary opacity-75">선택하면 자동으로 분석이 시작됩니다</small>
                    </div>
                  </div>
                </div>
                
                {/* 안내 동영상 */}
                <div className="col-md-5">
                  <div className="alert alert-success border-0" style={{
                    background: 'linear-gradient(135deg, #e8f5e8 0%, #c8e6c8 100%)', 
                    borderRadius: '12px'
                  }}>
                    <div className="d-flex align-items-center mb-3">
                      <i className="fas fa-play-circle me-2 text-success"></i>
                      <h6 className="mb-0 fw-bold text-success">📹 사용법 안내 동영상</h6>
                    </div>
                    <p className="mb-3 small text-success opacity-75">
                      ToneBridge 사용 방법을 영상으로 확인하세요!
                    </p>
                    
                    <div 
                      className="video-container" 
                      style={{
                        position: 'relative', 
                        width: '100%', 
                        height: '180px', 
                        borderRadius: '8px', 
                        overflow: 'hidden', 
                        background: '#000'
                      }}
                    >
                      <video 
                        controls 
                        style={{width: '100%', height: '100%', objectFit: 'cover'}}
                        poster="/static/images/video-thumbnail.jpg"
                      >
                        <source src="/static/videos/tonebridge_guide.mp4" type="video/mp4" />
                        <p className="text-muted p-3">죄송합니다. 브라우저에서 동영상을 지원하지 않습니다.</p>
                      </video>
                    </div>
                    <small className="text-success opacity-75 mt-2 d-block">
                      💡 동영상을 시청하고 효과적으로 학습해보세요
                    </small>
                  </div>
                </div>
              </div>
            </div>
          )}


          {/* 🎯 상태 메시지 */}
          <div className="mb-3">
            {status && <span className="text-muted">{status}</span>}
          </div>

          {/* 🎯 실시간 학습 분석 차트 */}
          <div className="card">
            <div className="card-header">
              {/* 차트 제목과 통합 제어 버튼들 */}
              <div className="d-flex justify-content-between align-items-center mb-2">
                <h5 className="mb-0 fw-bold">실시간 학습 분석 차트</h5>
                <div className="d-flex gap-2">
                  <button 
                    className="btn btn-sm btn-outline-primary" 
                    disabled={!selectedFile}
                    onClick={handlePlayReference}
                  >
                    <i className="fas fa-play me-1"></i> <strong>참조음성</strong>
                  </button>
                  <button 
                    className={`btn btn-sm ${audioRecording.isRecording ? 'btn-danger btn-recording recording-pulse' : ''}`}
                    disabled={isLoading}
                    style={{
                      backgroundColor: audioRecording.isRecording ? '#dc3545' : '#e67e22', 
                      borderColor: audioRecording.isRecording ? '#dc3545' : '#e67e22', 
                      color: 'white'
                    }}
                    onClick={handleRecording}
                  >
                    <i className={`fas ${audioRecording.isRecording ? 'fa-stop' : 'fa-microphone'} me-1`}></i> 
                    <strong>{audioRecording.isRecording ? '⏸️ 정지' : '🎤 녹음'}</strong>
                  </button>
                  <button 
                    className="btn btn-sm btn-outline-danger" 
                    disabled={!audioRecording.isRecording}
                    onClick={() => audioRecording.stopRecording()}
                  >
                    <i className="fas fa-stop me-1"></i> <strong>정지</strong>
                  </button>
                  <button 
                    className="btn btn-sm btn-outline-success" 
                    disabled={!audioRecording.recordedBlob}
                    onClick={handlePlayRecording}
                  >
                    <i className="fas fa-play me-1"></i> <strong>내음성</strong>
                  </button>
                </div>
              </div>
              
              {/* Y축 단위 선택 */}
              <div className="d-flex align-items-center justify-content-end">
                <div className="d-flex align-items-center gap-2">
                  <small className="text-muted">Y축 단위:</small>
                  <div className="btn-group" role="group">
                    <input 
                      type="radio" 
                      className="btn-check" 
                      name="yAxisUnit" 
                      id="yAxisSemitone" 
                      value="semitone" 
                      checked={yAxisUnit === 'semitone'}
                      onChange={(e) => setYAxisUnit(e.target.value as 'semitone' | 'qtone')}
                    />
                    <label className="btn btn-outline-primary btn-sm" htmlFor="yAxisSemitone">
                      Semitone
                    </label>
                    
                    <input 
                      type="radio" 
                      className="btn-check" 
                      name="yAxisUnit" 
                      id="yAxisQtone" 
                      value="qtone" 
                      checked={yAxisUnit === 'qtone'}
                      onChange={(e) => setYAxisUnit(e.target.value as 'semitone' | 'qtone')}
                    />
                    <label className="btn btn-outline-success btn-sm" htmlFor="yAxisQtone">
                      Q-tone
                    </label>
                  </div>
                </div>
              </div>
            </div>
            <div className="card-body px-2 py-2">
              <div className="chart-container" style={{position: 'relative', height: '500px'}}>
                <canvas ref={chartRef}></canvas>
                
                {/* 키 조정 컨트롤 - 차트 내부 우측 하단 */}
                <div 
                  id="pitchAdjustmentButtons" 
                  style={{position: 'absolute', bottom: '10px', right: '10px', zIndex: 1000, display: selectedFile ? 'block' : 'none'}}
                >
                  {/* 키 조정 사용법 강조박스 (컴팩트 버전) */}
                  <div className="p-2" style={{
                    background: 'linear-gradient(135deg, #e8f5e8 0%, #c8e6c8 100%)', 
                    border: '2px solid #4caf50', 
                    borderRadius: '8px', 
                    fontSize: '0.85em', 
                    lineHeight: '1.3', 
                    width: '380px'
                  }}>
                    <div className="d-flex align-items-center justify-content-between">
                      <div className="d-flex align-items-center">
                        <i className="fas fa-info-circle text-success me-2" style={{fontSize: '1.0em'}}></i>
                        <span style={{color: '#1b5e20', fontWeight: '500'}}>
                          <strong>[녹음]</strong> 버튼 클릭후 <strong>/아/</strong> 발성으로 편안한 음도를 찾고, <span style={{color: '#dc3545', fontWeight: 'bold'}}>⬆️<strong>화살표</strong>⬇️를 통해 참조음성의 억양 그래프 위치를 나의 음에 맞춥니다</span>
                        </span>
                      </div>
                      <div className="d-flex gap-1 ms-2">
                        <button 
                          className="btn btn-sm btn-outline-success" 
                          title="그래프를 아래로 이동" 
                          style={{borderColor: '#4caf50', color: '#4caf50'}}
                          onClick={() => pitchChart.adjustPitch('down')}
                        >
                          <i className="fas fa-arrow-down"></i>
                        </button>
                        <button 
                          className="btn btn-sm btn-outline-success" 
                          title="그래프를 위로 이동" 
                          style={{borderColor: '#4caf50', color: '#4caf50'}}
                          onClick={() => pitchChart.adjustPitch('up')}
                        >
                          <i className="fas fa-arrow-up"></i>
                        </button>
                        <button 
                          className="btn btn-sm btn-outline-secondary" 
                          title="그래프 위치 초기화"
                          onClick={() => pitchChart.resetView()}
                        >
                          <i className="fas fa-undo"></i>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 확대/스크롤 컨트롤 - 우측 상단 */}
                <div style={{position: 'absolute', top: '10px', right: '10px', zIndex: 1000}}>
                  <div className="d-flex gap-1 align-items-center">
                    <button 
                      className="btn btn-sm btn-outline-primary" 
                      title="확대 (마우스 휠로도 가능)"
                      onClick={() => pitchChart.zoomIn()}
                    >
                      <i className="fas fa-search-plus"></i>
                    </button>
                    <button 
                      className="btn btn-sm btn-outline-primary" 
                      title="축소 (마우스 휠로도 가능)"
                      onClick={() => pitchChart.zoomOut()}
                    >
                      <i className="fas fa-search-minus"></i>
                    </button>
                    <button 
                      className="btn btn-sm btn-outline-info" 
                      title="왼쪽으로 스크롤"
                      onClick={() => pitchChart.scrollLeft()}
                    >
                      <i className="fas fa-chevron-left"></i>
                    </button>
                    <button 
                      className="btn btn-sm btn-outline-info" 
                      title="오른쪽으로 스크롤"
                      onClick={() => pitchChart.scrollRight()}
                    >
                      <i className="fas fa-chevron-right"></i>
                    </button>
                    <button 
                      className="btn btn-sm btn-outline-secondary" 
                      title="전체 보기로 리셋"
                      onClick={() => pitchChart.resetView()}
                    >
                      <i className="fas fa-expand-arrows-alt"></i>
                    </button>
                  </div>
                </div>

                {/* 초기화 버튼 - 왼쪽 하단 */}
                <div style={{position: 'absolute', bottom: '10px', left: '10px', zIndex: 1000}}>
                  <button 
                    className="btn btn-sm btn-outline-secondary"
                    onClick={() => pitchChart.clearChart()}
                  >
                    <i className="fas fa-refresh me-1"></i> 초기화
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* 🎯 음절별 분석 테이블 */}
          {showSyllableAnalysis && (
            <div className="card mt-4" id="syllable-analysis-card">
              <div className="card-header">
                <h5 className="mb-0 fw-bold">
                  <i className="fas fa-table me-2"></i> 음절별 높낮이 분석 결과
                </h5>
              </div>
              <div className="card-body">
                <div className="table-responsive">
                  <table className="table table-striped table-hover" id="syllable-analysis-table">
                    <thead>
                      <tr>
                        <th>음절</th>
                        <th>지속시간</th>
                        <th>평균 높낮이</th>
                        <th>최대 높낮이</th>
                        <th>강도</th>
                        <th>상태</th>
                      </tr>
                    </thead>
                    <tbody>
                      {syllableData.map((syllable, index) => (
                        <tr key={index}>
                          <td>{syllable.label}</td>
                          <td>{syllable.duration.toFixed(2)}초</td>
                          <td>{syllable.f0_hz.toFixed(1)}Hz</td>
                          <td>{syllable.semitone.toFixed(1)}st</td>
                          <td>-</td>
                          <td><span className="badge bg-success">분석완료</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* 🎯 듀얼 Y축 비교 차트 */}
          <div className="card mt-4" id="dual-axis-chart-card">
            <div className="card-header">
              <div className="d-flex justify-content-between align-items-center">
                <h5 className="mb-0 fw-bold">
                  <i className="fas fa-chart-line me-2"></i>듀얼 Y축 비교 차트
                </h5>
                <div className="d-flex align-items-center gap-3">
                  <small className="text-muted">
                    <i className="fas fa-info-circle me-1"></i>
                    왼쪽: 주파수(Hz), 오른쪽: {yAxisUnit === 'semitone' ? '세미톤' : '큐톤'}
                  </small>
                </div>
              </div>
            </div>
            <div className="card-body">
              <div style={{position: 'relative', height: '400px'}}>
                <canvas
                  ref={dualAxisCanvasRef}
                  id="dual-axis-chart"
                  style={{
                    width: '100%',
                    height: '100%',
                    border: '1px solid #dee2e6',
                    borderRadius: '8px'
                  }}
                ></canvas>
                
                {/* 차트 컨트롤 버튼들 */}
                <div style={{position: 'absolute', top: '10px', right: '10px', zIndex: 1000}}>
                  <div className="d-flex gap-1">
                    <button 
                      className="btn btn-sm btn-outline-secondary"
                      onClick={() => dualAxisChart.clearChart()}
                      title="듀얼축 차트 초기화"
                    >
                      <i className="fas fa-refresh"></i>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* 🎯 하단 연락처 섹션 */}
          <div className="mt-5 py-4 contact-section" style={{
            background: 'linear-gradient(135deg, #2c3e50 0%, #34495e 100%)',
            borderRadius: '15px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.2)'
          }}>
            <div className="container">
              <div className="row align-items-center">
                <div className="col-md-8">
                  <div className="d-flex align-items-center">
                    <div className="me-4">
                      <h6 className="text-white mb-1 fw-bold">THE소리LAB</h6>
                      <p className="text-light mb-0 small opacity-75">
                        당신만의 소리를 위해 끊임없이 연구합니다
                      </p>
                    </div>
                  </div>
                </div>
                <div className="col-md-4 text-md-end">
                  <div className="d-flex align-items-center justify-content-md-end">
                    <i className="fas fa-envelope me-2" style={{color: '#e67e22'}}></i>
                    <a 
                      href="mailto:thesorilab@naver.com" 
                      className="text-white text-decoration-none fw-medium"
                    >
                      thesorilab@naver.com
                    </a>
                  </div>
                  <small className="text-light opacity-75 d-block mt-1">
                    문의사항이 있으시면 언제든 연락주세요
                  </small>
                </div>
              </div>
            </div>
          </div>

          </div>
        </div>
      </div>

      {/* 🎯 성별 선택 모달 */}
      {showGenderModal && (
        <div className="modal fade show" style={{display: 'block'}} tabIndex={-1}>
          <div className="modal-dialog modal-dialog-centered">
            <div className="modal-content">
              <div className="modal-header">
                <h5 className="modal-title">
                  <i className="fas fa-user me-2"></i>학습자 성별 선택
                </h5>
              </div>
              <div className="modal-body">
                <p className="text-muted mb-3">더 정확한 억양 학습을 위해 성별을 선택해주세요.</p>
                
                <div className="row mb-3">
                  <div className="col-12">
                    <div className="alert alert-info">
                      <i className="fas fa-info-circle me-2"></i>
                      <strong>학습 효과:</strong> 성별에 맞게 음높이가 자동 조정됩니다.
                    </div>
                  </div>
                </div>
                
                <div className="row g-3">
                  <div className="col-6">
                    <div 
                      className={`card gender-option ${selectedGender === 'male' ? 'border-primary' : ''}`}
                      style={{cursor: 'pointer'}}
                      onClick={() => handleGenderSelection('male')}
                    >
                      <div className="card-body text-center">
                        <i className="fas fa-mars fa-3x text-primary mb-3"></i>
                        <h6>남성</h6>
                        <small className="text-muted">100-150Hz 범위</small>
                      </div>
                    </div>
                  </div>
                  <div className="col-6">
                    <div 
                      className={`card gender-option ${selectedGender === 'female' ? 'border-danger' : ''}`}
                      style={{cursor: 'pointer'}}
                      onClick={() => handleGenderSelection('female')}
                    >
                      <div className="card-body text-center">
                        <i className="fas fa-venus fa-3x text-danger mb-3"></i>
                        <h6>여성</h6>
                        <small className="text-muted">200-250Hz 범위</small>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button 
                  type="button" 
                  className="btn btn-secondary" 
                  onClick={() => setShowGenderModal(false)}
                >
                  취소
                </button>
                <button 
                  type="button" 
                  className="btn btn-primary" 
                  disabled={!selectedGender}
                  onClick={confirmGenderSelection}
                >
                  <i className="fas fa-check me-2"></i>확인
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 🎯 푸터 (base.html 구조 준수) */}
      <footer className="border-top py-3 mt-5">
        <div className="container-fluid px-2 small text-muted">
          © Tone-Bridge by THE소리LAB · 실시간 억양 피드백 데모
        </div>
      </footer>
    </>
  );
};

export default VoiceAnalysisApp;