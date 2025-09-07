/**
 * ToneBridge Voice Analysis - index.html 완전 재현
 * 한국어 억양 학습 플랫폼의 모든 기능 구현
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { ReferenceFile, LearnerInfo, LearningMethod, AnalysisResult, SyllableData } from './types/api';
import { useAudioRecording } from './hooks/useAudioRecording';
import { usePitchChart } from './hooks/usePitchChart';
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
  const [showSyllableAnalysis, setShowSyllableAnalysis] = useState<boolean>(false);
  const [showGenderModal, setShowGenderModal] = useState<boolean>(false);
  const [selectedGender, setSelectedGender] = useState<string>('');
  
  // 🎯 참조 파일 및 분석 상태
  const [referenceFiles, setReferenceFiles] = useState<ReferenceFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [status, setStatus] = useState<string>('');
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [syllableData, setSyllableData] = useState<SyllableData[]>([]);
  
  // 🎯 차트 설정
  const [semitoneMin, setSemitoneMin] = useState<number>(-12);
  const [semitoneMax, setSemitoneMax] = useState<number>(15);
  const [yAxisUnit, setYAxisUnit] = useState<string>('semitone');
  
  // 🎯 Refs
  const chartRef = useRef<HTMLCanvasElement>(null);
  
  // 🎯 Hooks
  const audioRecording = useAudioRecording();
  const pitchChart = usePitchChart(chartRef);

  // 🎯 API Base URL
  const API_BASE = '';
  
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

  // 🎯 초기화
  useEffect(() => {
    loadReferenceFiles();
    audioRecording.setPitchCallback((frequency: number, timestamp: number) => {
      pitchChart.addPitchData(frequency, timestamp, 'live');
    });
  }, []);

  // 🎯 참조 파일 로딩
  const loadReferenceFiles = async () => {
    try {
      setIsLoading(true);
      setStatus('참조 파일을 로딩 중입니다...');
      
      const response = await fetch(`${API_BASE}/api/reference_files`);
      const data = await response.json();
      
      if (data && data.files && Array.isArray(data.files)) {
        setReferenceFiles(data.files);
        console.log(`✅ ToneBridge Backend Service: 연결됨 (참조 파일 ${data.files.length}개 로드됨)`);
        setStatus('');
      } else {
        setStatus('참조 파일 로딩 실패: 잘못된 응답 구조');
      }
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
  }, []);
  
  // 🎯 연습 문장 선택
  const handleSentenceSelection = useCallback(async (fileId: string) => {
    if (!fileId) return;
    
    setSelectedFile(fileId);
    setIsLoading(true);
    setStatus('참조 음성을 분석 중입니다...');
    
    try {
      const response = await fetch(`${API_BASE}/api/analyze/${fileId}`);
      const data = await response.json();
      
      if (data && data.pitch_data) {
        pitchChart.clearChart();
        data.pitch_data.forEach((point: [number, number]) => {
          pitchChart.addPitchData(point[1], point[0], 'reference');
        });
        setStatus('참조 음성 분석 완료. 녹음을 시작하세요!');
      }
    } catch (error) {
      console.error('❌ 참조 오디오 로딩 실패:', error);
      setStatus('참조 음성 로딩에 실패했습니다.');
    } finally {
      setIsLoading(false);
    }
  }, [pitchChart, API_BASE]);
  
  // 🎯 녹음 제어
  const handleRecording = useCallback(() => {
    if (audioRecording.isRecording) {
      audioRecording.stopRecording();
      setStatus('녹음이 완료되었습니다.');
    } else {
      audioRecording.startRecording();
      setStatus('🎤 녹음 중... 말씀해 주세요.');
    }
  }, [audioRecording]);
  
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
  
  // 🎯 차트 범위 업데이트
  const updateChartRange = useCallback(() => {
    // pitchChart.updateRange(semitoneMin, semitoneMax); // 훅에 구현 필요
    console.log('차트 범위 업데이트:', semitoneMin, semitoneMax);
  }, [semitoneMin, semitoneMax]);
  
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


  return (
    <>
      {/* 🎯 ToneBridge 브랜딩 헤더 - base.html 완전 재현 */}
      <div className="py-5 mb-4" style={{
        background: 'linear-gradient(135deg, #e67e22 0%, #d35400 100%)',
        boxShadow: '0 4px 20px rgba(230, 126, 34, 0.25)',
        position: 'relative'
      }}>
        <div className="container">
          <div className="text-center">
            <h1 className="display-3 fw-bold mb-3" style={{
              color: 'white',
              fontFamily: "'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif",
              textShadow: '0 3px 6px rgba(0,0,0,0.3)'
            }}>
              <i className="fas fa-microphone me-3" style={{color: 'white'}}></i>
              Tone-Bridge
            </h1>
            <p className="lead mb-4" style={{
              color: 'white',
              fontWeight: 'bold',
              fontFamily: "'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif",
              opacity: 0.95
            }}>
              실시간 피드백 한국어 억양학습 솔루션 <span style={{fontSize: '0.95em'}}>데모ver.</span>
            </p>
            <div className="text-end">
              <div className="mb-1" style={{
                color: 'white',
                fontFamily: "'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif",
                marginTop: '1.5rem'
              }}>
                <small style={{fontWeight: 600, fontSize: '0.85rem'}}>THE소리LAB</small>
              </div>
              <div style={{
                color: 'white',
                fontFamily: "'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif"
              }}>
                <small style={{fontStyle: 'italic', fontSize: '0.8rem'}}>"당신만의 소리를 위해 끊임없이 연구합니다"</small>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 🎯 메인 컨텐츠 */}
      <main className="container-fluid px-2 py-4">
        <div className="container">
          <div className="row justify-content-center">
            <div className="col-lg-10">

          {/* 🎯 개인화 코칭 설문 CTA */}
          <div className="alert alert-primary d-flex align-items-center mb-4 survey-cta">
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
              <a 
                href="/survey" 
                className="btn btn-warning btn-lg fw-bold px-4 py-2"
                style={{
                  borderRadius: '25px',
                  boxShadow: '0 3px 10px rgba(255, 193, 7, 0.4)'
                }}
              >
                <i className="fas fa-clipboard-list me-2"></i>3분 설문하기
              </a>
            </div>
          </div>

          {/* 🎯 휴대폰 가로보기 안내 */}
          <div className="alert border-0 text-center mb-4 mobile-warning shake-animation">
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
                    onClick={() => learnerInfo.gender && handleLearningMethodChange('pitch')}
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
                    onClick={() => learnerInfo.gender && handleLearningMethodChange('sentence')}
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

          {/* 🎯 연습 문장 선택 및 안내 동영상 */}
          {showAudioAnalysisSection && (
            <div className="mb-4 d-flex justify-content-center" style={{marginTop: '1.5rem'}}>
              <div className="row g-4 w-100">
                {/* 연습 문장 선택 */}
                <div className="col-md-7">
                  <div className="alert alert-info border-0 practice-info">
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
                        onChange={(e) => handleSentenceSelection(e.target.value)}
                      >
                        <option value="">연습할 문장을 선택하세요...</option>
                        {referenceFiles.map((file) => (
                          <option key={file.id} value={file.id}>
                            {file.title}
                          </option>
                        ))}
                      </select>
                      <small className="text-primary opacity-75">선택하면 자동으로 분석이 시작됩니다</small>
                    </div>
                  </div>
                </div>
                
                {/* 안내 동영상 */}
                <div className="col-md-5">
                  <div className="alert alert-success border-0 video-guide">
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
                    className="btn btn-sm" 
                    disabled={isLoading}
                    style={{backgroundColor: '#e67e22', borderColor: '#e67e22', color: 'white'}}
                    onClick={handleRecording}
                  >
                    <i className={`fas ${audioRecording.isRecording ? 'fa-stop' : 'fa-microphone'} me-1`}></i> 
                    <strong>{audioRecording.isRecording ? '정지' : '녹음'}</strong>
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
              
              {/* 두 번째 줄: 범위 설정 및 Y축 단위 선택 */}
              <div className="d-flex align-items-center justify-content-between">
                <div className="d-flex align-items-center gap-2">
                  <small className="text-muted">표시범위 조정으로 그래프를 좀더 확대/축소 할수 있어요.</small>
                  <i 
                    className="fas fa-question-circle text-muted ms-1" 
                    style={{fontSize: '0.8em', cursor: 'help'}} 
                    title="차트의 상하 범위를 조정하여 원하는 구간을 확대하거나 전체적인 패턴을 볼 수 있습니다."
                  ></i>
                  <input 
                    type="number" 
                    className="form-control form-control-sm" 
                    style={{width: '55px'}} 
                    value={semitoneMin} 
                    step="1"
                    onChange={(e) => setSemitoneMin(Number(e.target.value))}
                  />
                  <small className="text-muted">~</small>
                  <input 
                    type="number" 
                    className="form-control form-control-sm" 
                    style={{width: '55px'}} 
                    value={semitoneMax} 
                    step="1"
                    onChange={(e) => setSemitoneMax(Number(e.target.value))}
                  />
                  <small className="text-muted">st</small>
                  <button 
                    className="btn btn-sm btn-outline-primary"
                    onClick={updateChartRange}
                  >
                    적용
                  </button>
                </div>
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
                      onChange={(e) => setYAxisUnit(e.target.value)}
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
                      onChange={(e) => setYAxisUnit(e.target.value)}
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

          {/* 🎯 하단 연락처 섹션 */}
          <div className="mt-5 py-4 contact-section">
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

            </div>
          </div>
        </div>
      </main>

    </>
  );
};

export default VoiceAnalysisApp;