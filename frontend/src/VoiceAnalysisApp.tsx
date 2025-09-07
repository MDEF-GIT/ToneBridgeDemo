import React, { useState, useEffect, useRef } from 'react';
import { useAudioRecording } from './hooks/useAudioRecording';
import { usePitchChart } from './hooks/usePitchChart';
import './custom.css';

// Types
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
  const [learnerInfo, setLearnerInfo] = useState<LearnerInfo>({
    name: '',
    gender: '',
    level: ''
  });
  const [learningMethod, setLearningMethod] = useState<string>('');
  const [referenceFiles, setReferenceFiles] = useState<ReferenceFile[]>([]);
  const [selectedSentence, setSelectedSentence] = useState<string>('');
  const [isPlayingReference, setIsPlayingReference] = useState<boolean>(false);
  
  // API base URL (voice-analysis-demo 독립성 유지)
  const API_BASE = '';
  
  // Refs
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  
  // Custom hooks
  const audioRecording = useAudioRecording();
  const pitchChart = usePitchChart(canvasRef);

  useEffect(() => {
    // Load reference files when component mounts
    loadReferenceFiles();
    
    // Set up pitch callback for audio recording
    audioRecording.setPitchCallback((frequency: number, timestamp: number) => {
      pitchChart.addPitchData(frequency, timestamp, 'live');
    });
  }, [audioRecording, pitchChart]);

  // Clean up audio when component unmounts or selectedSentence changes
  useEffect(() => {
    return () => {
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
        currentAudioRef.current = null;
      }
      setIsPlayingReference(false);
    };
  }, [selectedSentence]);

  // Clean up on component unmount
  useEffect(() => {
    return () => {
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
        currentAudioRef.current = null;
      }
    };
  }, []);

  const loadReferenceFiles = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/reference_files`);
      const data = await response.json();
      if (data.files) {
        setReferenceFiles(data.files);
      }
    } catch (error) {
      console.error('Failed to load reference files:', error);
    }
  };

  const handleLearnerInfoChange = (field: keyof LearnerInfo, value: string) => {
    setLearnerInfo(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleRecordingToggle = async () => {
    if (audioRecording.isRecording) {
      audioRecording.stopRecording();
      
      // 녹음 중지 시 참조음성도 정지
      if (isPlayingReference && currentAudioRef.current) {
        currentAudioRef.current.pause();
        currentAudioRef.current.currentTime = 0;
        currentAudioRef.current = null;
        setIsPlayingReference(false);
      }
      
    } else {
      // 🎯 재생 중일 때는 녹음 시작 불가 (React 재생)
      if (isPlayingReference) {
        alert('재생 중에는 녹음할 수 없습니다. 먼저 재생을 정지해주세요.');
        return;
      }
      
      
      pitchChart.resetForNewRecording();
      await audioRecording.startRecording();
    }
  };

  const stopCurrentAudio = () => {
    if (currentAudioRef.current) {
      console.log('🛑 오디오 강제 정지');
      currentAudioRef.current.pause();
      currentAudioRef.current.currentTime = 0;
      currentAudioRef.current.removeEventListener('ended', () => {});
      currentAudioRef.current.removeEventListener('error', () => {});
      currentAudioRef.current = null;
    }
    setIsPlayingReference(false);
  };

  const handlePlayReference = async () => {
    console.log('🔄 참조음성 버튼 클릭, 현재상태:', { isPlayingReference, hasAudio: !!currentAudioRef.current });
    
    // 현재 재생 중이면 무조건 정지
    if (isPlayingReference) {
      console.log('🛑 참조음성 정지 실행');
      stopCurrentAudio();
      return;
    }
    
    // 🎯 녹음 중일 때는 재생 시작 불가
    if (audioRecording.isRecording) {
      alert('녹음 중에는 재생할 수 없습니다. 먼저 녹음을 정지해주세요.');
      return;
    }

    if (!selectedSentence) {
      console.log('⚠️ 선택된 문장이 없습니다');
      return;
    }

    try {
      console.log('▶️ 참조음성 재생 시작:', selectedSentence);
      
      // 기존 오디오 완전 정리
      stopCurrentAudio();

      const audioUrl = `${API_BASE}/api/reference_files/${selectedSentence}/wav`;
      console.log('🎵 오디오 URL:', audioUrl);
      
      const audio = new Audio(audioUrl);
      currentAudioRef.current = audio;
      
      // 즉시 재생 상태로 변경 (로딩 시작과 함께)
      setIsPlayingReference(true);
      
      audio.addEventListener('loadstart', () => {
        console.log('📥 오디오 로딩 시작');
      });

      audio.addEventListener('canplay', () => {
        console.log('✅ 오디오 재생 준비 완료');
      });
      
      audio.addEventListener('play', () => {
        console.log('🎵 오디오 재생 시작됨');
        setIsPlayingReference(true);
      });
      
      audio.addEventListener('ended', () => {
        console.log('🏁 오디오 재생 완료');
        setIsPlayingReference(false);
        currentAudioRef.current = null;
      });
      
      audio.addEventListener('pause', () => {
        console.log('⏸️ 오디오 일시정지됨');
      });
      
      audio.addEventListener('error', (e) => {
        console.error('❌ 오디오 재생 오류:', e);
        setIsPlayingReference(false);
        currentAudioRef.current = null;
      });
      
      await audio.play();
      console.log('🎯 audio.play() 호출 완료');
      
    } catch (error) {
      console.error('❌ 참조음성 재생 실패:', error);
      setIsPlayingReference(false);
      currentAudioRef.current = null;
    }
  };

  const handleSentenceChange = (sentenceId: string) => {
    // 문장 변경 시 현재 재생중인 오디오 정지
    stopCurrentAudio();
    
    setSelectedSentence(sentenceId);
    if (sentenceId) {
      pitchChart.loadReferenceData(sentenceId);
    }
  };

  return (
    <div className="container">
      <div className="row justify-content-center">
        <div className="col-lg-10">
          {/* 개인화 코칭 설문 CTA */}
          <div 
            className="alert alert-primary d-flex align-items-center mb-4 survey-cta" 
            style={{
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              border: 'none',
              borderRadius: '12px',
              boxShadow: '0 4px 15px rgba(102, 126, 234, 0.3)'
            }}
          >
            <div className="flex-grow-1 text-white">
              <div className="d-flex align-items-center mb-2">
                <i className="fas fa-graduation-cap fa-2x me-3" style={{ color: '#ffd700' }}></i>
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

          {/* 휴대폰 가로보기 안내 */}
          <div 
            className="alert border-0 text-center mb-4"
            style={{
              background: 'linear-gradient(135deg, #ff6b6b 0%, #ee5a52 100%)',
              borderRadius: '12px',
              boxShadow: '0 2px 15px rgba(255, 107, 107, 0.3)',
              animation: 'shake 4s infinite'
            }}
          >
            <div className="d-flex align-items-center justify-content-center">
              <i 
                className="fas fa-mobile-alt me-2" 
                style={{
                  color: 'white',
                  fontSize: '1.2em',
                  animation: 'bounce 2s infinite'
                }}
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
                  가로보기<span style={{ color: '#ffff00' }}>로</span>
                </span>
                " !! 📱
              </span>
            </div>
            <div className="mt-2" style={{
              color: '#ffff00',
              fontSize: '0.9em',
              fontWeight: 'normal'
            }}>
              (PC & 마이크 사용을 더욱 권장합니다)
            </div>
          </div>

          {/* 학습자 정보 입력 */}
          <div className="card mb-4">
            <div className="card-header">
              <h5 
                className="mb-0 fw-bold" 
                style={{
                  color: '#ff6b35',
                  fontFamily: "'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif"
                }}
              >
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
                    onChange={(e) => handleLearnerInfoChange('name', e.target.value)}
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
                    onChange={(e) => handleLearnerInfoChange('gender', e.target.value)}
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
                    value={learnerInfo.level}
                    onChange={(e) => handleLearnerInfoChange('level', e.target.value)}
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

          {/* 학습 방법 선택 */}
          <div className="card mb-3">
            <div className="card-header">
              <h5 
                className="mb-0 fw-bold" 
                style={{
                  color: '#ff6b35',
                  fontFamily: "'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif"
                }}
              >
                <i className="fas fa-graduation-cap me-2"></i>학습 방법 선택
              </h5>
            </div>
            <div className="card-body">
              <div className="row g-2">
                <div className="col-md-6">
                  <div 
                    className="d-flex align-items-center p-2 border rounded learning-method-toggle disabled" 
                    data-method="pitch" 
                    style={{
                      cursor: 'pointer',
                      opacity: 0.6,
                      pointerEvents: 'none'
                    }}
                  >
                    <div className="form-check me-3">
                      <input 
                        className="form-check-input" 
                        type="radio" 
                        name="learningMethod" 
                        id="methodPitch" 
                        value="pitch"
                        disabled
                      />
                    </div>
                    <div className="flex-grow-1">
                      <h6 className="mb-1">
                        <i className="fas fa-music me-2 text-primary"></i>
                        음높이 학습 
                        <span className="text-danger fw-bold">(준비중)</span>
                      </h6>
                      <small className="text-muted">특정 음높이를 목표로 하여 정확한 높낮이 연습</small>
                    </div>
                  </div>
                </div>
                <div className="col-md-6">
                  <div 
                    className={`d-flex align-items-center p-2 border rounded learning-method-toggle ${
                      learnerInfo.gender ? '' : 'disabled'
                    }`}
                    data-method="practice" 
                    style={{
                      cursor: learnerInfo.gender ? 'pointer' : 'not-allowed',
                      opacity: learnerInfo.gender ? 1 : 0.6,
                      pointerEvents: learnerInfo.gender ? 'auto' : 'none'
                    }}
                    onClick={() => learnerInfo.gender && setLearningMethod('practice')}
                  >
                    <div className="form-check me-3">
                      <input 
                        className="form-check-input" 
                        type="radio" 
                        name="learningMethod" 
                        id="methodPractice" 
                        value="practice"
                        checked={learningMethod === 'practice'}
                        onChange={(e) => setLearningMethod(e.target.value)}
                        disabled={!learnerInfo.gender}
                      />
                    </div>
                    <div className="flex-grow-1">
                      <h6 className="mb-1">
                        <i className="fas fa-microphone me-2 text-success"></i>
                        실시간 연습
                        <span className="text-success fw-bold ms-2">
                          <i className="fas fa-check-circle"></i> 추천
                        </span>
                      </h6>
                      <small className="text-muted">실시간 음성분석으로 더 빠른 학습효과</small>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* 연습 문장 선택 (실시간 연습 모드일 때만) */}
          {learningMethod === 'practice' && (
            <div className="card mb-4">
              <div className="card-header">
                <h5 
                  className="mb-0 fw-bold" 
                  style={{
                    color: '#ff6b35',
                    fontFamily: "'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif"
                  }}
                >
                  <i className="fas fa-list me-2"></i>연습 문장 선택
                </h5>
              </div>
              <div className="card-body">
                <div className="mb-3">
                  <label htmlFor="saved-files" className="form-label">
                    문장을 선택하세요 <span className="text-danger">*</span>
                  </label>
                  <select 
                    className="form-select" 
                    id="saved-files"
                    value={selectedSentence}
                    onChange={(e) => handleSentenceChange(e.target.value)}
                  >
                    <option value="">연습할 문장을 선택하세요</option>
                    {referenceFiles.map((file) => (
                      <option key={file.id} value={file.id}>
                        {file.sentence_text} ({file.duration?.toFixed(1)}초)
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          )}

          {/* 차트 영역 */}
          <div className="card mb-4">
            <div className="card-header d-flex justify-content-between align-items-center">
              <h5 className="mb-0 fw-bold" style={{ color: '#ff6b35' }}>
                <i className="fas fa-chart-line me-2"></i>실시간 음성 분석
              </h5>
              <div className="btn-group btn-group-sm">
                <button 
                  className="btn btn-outline-secondary" 
                  onClick={pitchChart.clearChart}
                >
                  <i className="fas fa-eraser me-1"></i>차트 지우기
                </button>
              </div>
            </div>
            <div className="card-body">
              <canvas 
                ref={canvasRef}
                width="800" 
                height="400"
                style={{ maxWidth: '100%', height: 'auto' }}
              ></canvas>
            </div>
          </div>

          {/* 제어 버튼들 */}
          <div className="card mb-4">
            <div className="card-body">
              <div className="row g-3">
                <div className="col-md-6">
                  <button 
                    className={`btn btn-lg w-100 ${audioRecording.isRecording ? 'btn-danger' : 'btn-success'}`}
                    disabled={!learningMethod || !selectedSentence}
                    onClick={handleRecordingToggle}
                  >
                    <i className={`fas ${audioRecording.isRecording ? 'fa-stop' : 'fa-microphone'} me-2`}></i>
                    {audioRecording.isRecording ? '녹음 중지' : '녹음 시작'}
                  </button>
                </div>
                <div className="col-md-6">
                  <button 
                    className={`btn btn-lg w-100 ${isPlayingReference ? 'btn-danger' : 'btn-info'}`}
                    disabled={!selectedSentence}
                    onClick={handlePlayReference}
                  >
                    <i className={`fas ${isPlayingReference ? 'fa-stop' : 'fa-play'} me-2`}></i>
                    {isPlayingReference ? '참조음성 중지' : '참조음성 재생'}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* 상태 표시 */}
          <div className={`alert ${audioRecording.error ? 'alert-danger' : 'alert-light'}`}>
            {audioRecording.error ? 
              audioRecording.error :
              learnerInfo.gender ? 
                learningMethod ? 
                  selectedSentence ? 
                    audioRecording.isRecording ? 
                      '🎤 녹음 중... 마이크에 대고 말해보세요!' :
                      '녹음을 시작할 준비가 되었습니다.' :
                    '연습할 문장을 선택해주세요.' :
                  '학습 방법을 선택해주세요.' :
                '성별을 먼저 선택해주세요.'
            }
          </div>
        </div>
      </div>
    </div>
  );
};

export default VoiceAnalysisApp;