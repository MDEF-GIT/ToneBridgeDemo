/**
 * ToneBridge Voice Analysis - 원본 HTML 구조 완전 재현
 * 기존 react-complete-voice-analysis.html과 동일한 UI/UX
 */
import React, { useState, useEffect, useRef } from 'react';
import { useAudioRecording } from './hooks/useAudioRecording';
import { usePitchChart } from './hooks/usePitchChart';
// ChartControls와 PitchTestMode는 일단 제외하고 기본 기능부터 구현
import './custom.css';

// Types - 백엔드 API 응답에 맞춘 인터페이스
interface ReferenceFile {
  id: string;
  title: string;
  sentence_text: string;
  duration: number;
  detected_gender: string;
  average_f0: number;
  wav: string;
  textgrid: string;
}

interface AnalysisResult {
  duration: number;
  mean_f0: number;
  max_f0: number;
  syllable_count: number;
  gender: 'male' | 'female';
}

const VoiceAnalysisApp: React.FC = () => {
  // 🎯 원본 HTML 구조에 맞는 State들
  const [selectedGender, setSelectedGender] = useState<'male' | 'female'>('female');
  const [referenceFiles, setReferenceFiles] = useState<ReferenceFile[]>([]);
  const [selectedSentence, setSelectedSentence] = useState<string>('');
  
  // 🎯 단계별 상태 관리 (원본 HTML의 3단계 워크플로우)
  const [textGridFile, setTextGridFile] = useState<File | null>(null);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [analysisComplete, setAnalysisComplete] = useState<boolean>(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  
  // 🎯 백엔드 연결 상태
  const [backendConnected, setBackendConnected] = useState<boolean>(false);
  
  // 🎯 Refs
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // 🎯 Hooks
  const audioRecording = useAudioRecording();
  const pitchChart = usePitchChart(canvasRef);

  // 🎯 API Base URL
  const API_BASE = '';

  // 🎯 백엔드 연결 및 참조 파일 로딩
  useEffect(() => {
    loadReferenceFiles();
    
    // Set up pitch callback for audio recording
    audioRecording.setPitchCallback((frequency: number, timestamp: number) => {
      pitchChart.addPitchData(frequency, timestamp, 'live');
    });
  }, [audioRecording, pitchChart]);

  // 🎯 참조 파일 로딩 (백엔드 API 호출)
  const loadReferenceFiles = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/reference_files`);
      if (response.ok) {
        const data = await response.json();
        console.log('🔍 API 응답 데이터:', data);
        
        // API 응답에서 files 배열 추출
        if (data && data.files && Array.isArray(data.files)) {
          console.log('✅ ToneBridge Backend Service: 연결됨 (참조 파일', data.files.length + '개 로드됨)');
          setReferenceFiles(data.files);
          setBackendConnected(true);
        } else {
          console.error('❌ API 응답에 files 배열이 없음:', data);
          setReferenceFiles([]);
          setBackendConnected(false);
        }
      } else {
        console.error('❌ 백엔드 연결 실패');
        setReferenceFiles([]);
        setBackendConnected(false);
      }
    } catch (error) {
      console.error('❌ 백엔드 연결 오류:', error);
      setReferenceFiles([]);
      setBackendConnected(false);
    }
  };

  // 🎯 1단계: TextGrid 파일 업로드 처리
  const handleTextGridUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file && file.name.endsWith('.TextGrid')) {
      setTextGridFile(file);
      console.log('📄 TextGrid 파일 업로드됨:', file.name);
    } else {
      alert('TextGrid 파일을 선택해주세요.');
    }
  };

  // 🎯 2단계: 녹음 시작/중지
  const handleRecordToggle = async () => {
    if (isRecording) {
      // 녹음 중지
      audioRecording.stopRecording();
      setIsRecording(false);
      console.log('🎤 녹음 완료');
    } else {
      // 녹음 시작
      try {
        await audioRecording.startRecording();
        setIsRecording(true);
        console.log('🎤 녹음 시작');
      } catch (error) {
        console.error('녹음 시작 실패:', error);
        alert('마이크 접근 권한이 필요합니다.');
      }
    }
  };

  // 🎯 녹음된 오디오 재생
  const handlePlayRecorded = () => {
    // recordedBlob이 있으면 재생
    if (audioRecording.recordedBlob) {
      audioRecording.playRecordedAudio();
      console.log('🔊 녹음된 음성 재생');
    }
  };

  // 🎯 3단계: 음성 분석 실행
  const handleAnalyze = async () => {
    if (!audioRecording.recordedBlob) {
      alert('먼저 음성을 녹음해주세요.');
      return;
    }

    setIsAnalyzing(true);
    
    try {
      // 실제 분석 로직은 나중에 구현
      // 일단 기본 결과를 표시
      setTimeout(() => {
        const mockResult: AnalysisResult = {
          duration: 2.5,
          mean_f0: 200,
          max_f0: 250,
          syllable_count: 3,
          gender: selectedGender
        };
        
        setAnalysisResult(mockResult);
        setAnalysisComplete(true);
        setIsAnalyzing(false);
        console.log('📊 분석 완료:', mockResult);
      }, 2000);
      
    } catch (error) {
      console.error('❌ 분석 오류:', error);
      setIsAnalyzing(false);
    }
  };

  // 🎯 차트 컨테이너 내용 결정
  const renderChartContent = () => {
    if (analysisComplete) {
      return (
        <canvas
          ref={canvasRef}
          width={800}
          height={400}
          style={{ width: '100%', height: '100%' }}
        />
      );
    } else {
      return (
        <div className="text-center text-muted">
          <i className="fas fa-chart-line fa-3x mb-3"></i>
          <p>분석 데이터가 없습니다</p>
          <small>문장을 선택하고 음성을 분석해보세요</small>
        </div>
      );
    }
  };

  return (
    <div className="container-fluid">
      <div className="row justify-content-center">
        <div className="col-lg-10">
          
          <h2 className="text-center mb-4 fw-bold text-white">
            완전한 음성 분석 데모 (React 기능 통합)
          </h2>

          {/* 🎯 설정 패널 */}
          <div className="card mb-4">
            <div className="card-header">
              <h5 className="mb-0 fw-bold" style={{ color: '#ff6b35' }}>
                <i className="fas fa-cog me-2"></i>분석 설정
              </h5>
            </div>
            <div className="card-body">
              <div className="row g-3">
                <div className="col-md-6">
                  <label className="form-label">성별</label>
                  <select 
                    className="form-select" 
                    value={selectedGender}
                    onChange={(e) => setSelectedGender(e.target.value as 'male' | 'female')}
                  >
                    <option value="male">남성</option>
                    <option value="female">여성</option>
                  </select>
                </div>
                <div className="col-md-6">
                  <label className="form-label">연습 문장</label>
                  <select 
                    className="form-select"
                    value={selectedSentence}
                    onChange={(e) => setSelectedSentence(e.target.value)}
                  >
                    <option value="">문장을 선택하세요</option>
                    {referenceFiles.map((file) => (
                      <option key={file.id} value={file.id}>
                        {file.title}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          </div>

          {/* 🎯 1단계: TextGrid 파일 업로드 */}
          <div className="card mb-4">
            <div className="card-header">
              <h5 className="mb-0 fw-bold" style={{ color: '#28a745' }}>
                <i className="fas fa-upload me-2"></i>1단계: TextGrid 파일 업로드
              </h5>
            </div>
            <div className="card-body">
              <input 
                type="file" 
                className="form-control" 
                accept=".TextGrid" 
                ref={fileInputRef}
                onChange={handleTextGridUpload}
              />
              {textGridFile && (
                <div className="mt-2 text-success">
                  <i className="fas fa-check-circle me-2"></i>
                  <span>{textGridFile.name}</span>
                </div>
              )}
              <small className="text-muted d-block mt-2">
                음성과 함께 업로드할 TextGrid 파일을 선택하세요
              </small>
            </div>
          </div>

          {/* 🎯 2단계: 음성 녹음 */}
          <div className="card mb-4">
            <div className="card-header">
              <h5 className="mb-0 fw-bold" style={{ color: '#dc3545' }}>
                <i className="fas fa-microphone me-2"></i>2단계: 음성 녹음
              </h5>
            </div>
            <div className="card-body text-center">
              <div className="mb-3">
                <button 
                  className={`btn ${isRecording ? 'btn-warning' : 'btn-danger'} btn-lg px-5 me-3`}
                  onClick={handleRecordToggle}
                >
                  <i className={`fas fa-${isRecording ? 'stop' : 'microphone'} me-2`}></i>
                  {isRecording ? '녹음 중지' : '녹음 시작'}
                </button>

                {audioRecording.recordedBlob && (
                  <button 
                    className="btn btn-outline-primary"
                    onClick={handlePlayRecorded}
                  >
                    <i className="fas fa-play me-2"></i>
                    재생
                  </button>
                )}
              </div>

              {isRecording && (
                <div className="text-danger">
                  <i className="fas fa-circle me-2 blink"></i>
                  녹음 중...
                </div>
              )}

              {audioRecording.recordedBlob && !isRecording && (
                <div className="text-success">
                  <i className="fas fa-check-circle me-2"></i>
                  녹음 완료
                </div>
              )}
            </div>
          </div>

          {/* 🎯 3단계: 분석 실행 */}
          <div className="card mb-4">
            <div className="card-header">
              <h5 className="mb-0 fw-bold" style={{ color: '#007bff' }}>
                <i className="fas fa-chart-line me-2"></i>3단계: 음성 분석
              </h5>
            </div>
            <div className="card-body text-center">
              <button 
                className="btn btn-primary btn-lg px-5" 
                onClick={handleAnalyze}
                disabled={!audioRecording.recordedBlob || isAnalyzing}
              >
                <i className="fas fa-chart-line me-2"></i>
                {isAnalyzing ? '분석 중...' : '음성 분석 시작'}
              </button>

              {isAnalyzing && (
                <div className="alert alert-info mt-3">
                  <i className="fas fa-spinner fa-spin me-2"></i>
                  <span>분석 중입니다. 잠시만 기다려주세요...</span>
                </div>
              )}
              
              {!backendConnected && (
                <div className="alert alert-warning mt-3">
                  <i className="fas fa-exclamation-triangle me-2"></i>
                  <span>백엔드 서버에 연결할 수 없습니다.</span>
                </div>
              )}
            </div>
          </div>

          {/* 🎯 피치 분석 결과 차트 */}
          <div className="card mb-4">
            <div className="card-header">
              <h5 className="mb-0 fw-bold" style={{ color: '#6f42c1' }}>
                <i className="fas fa-chart-area me-2"></i>피치 분석 결과
              </h5>
            </div>
            <div className="card-body">
              <div 
                style={{ 
                  height: '400px', 
                  background: '#f8f9fa', 
                  borderRadius: '8px', 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center' 
                }}
              >
                {renderChartContent()}
              </div>
            </div>
          </div>

          {/* 🎯 분석 결과 상세 정보 */}
          {analysisComplete && analysisResult && (
            <div className="card mb-4">
              <div className="card-header">
                <h5 className="mb-0 fw-bold" style={{ color: '#fd7e14' }}>
                  <i className="fas fa-clipboard-list me-2"></i>분석 결과 상세
                </h5>
              </div>
              <div className="card-body">
                <div className="row text-center">
                  <div className="col-md-3">
                    <div className="border rounded p-3">
                      <h4 className="text-primary">{analysisResult.duration.toFixed(2)}초</h4>
                      <small className="text-muted">지속 시간</small>
                    </div>
                  </div>
                  <div className="col-md-3">
                    <div className="border rounded p-3">
                      <h4 className="text-success">{analysisResult.mean_f0}Hz</h4>
                      <small className="text-muted">기준 주파수</small>
                    </div>
                  </div>
                  <div className="col-md-3">
                    <div className="border rounded p-3">
                      <h4 className="text-warning">{analysisResult.syllable_count}개</h4>
                      <small className="text-muted">음절 수</small>
                    </div>
                  </div>
                  <div className="col-md-3">
                    <div className="border rounded p-3">
                      <h4 className="text-info">{analysisResult.gender === 'male' ? '남성' : '여성'}</h4>
                      <small className="text-muted">감지된 성별</small>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
};

export default VoiceAnalysisApp;