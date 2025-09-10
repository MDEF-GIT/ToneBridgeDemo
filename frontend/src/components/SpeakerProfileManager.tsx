import React, { useState, useEffect } from 'react';
import { useSpeakerProfile } from '../hooks/useSpeakerProfile';
import { useAdaptiveReference } from '../hooks/useAdaptiveReference';

interface SpeakerProfileManagerProps {
  onReferenceFrequencyChange?: (newReference: number) => void;
  currentFrequency?: number;
}

export const SpeakerProfileManager: React.FC<SpeakerProfileManagerProps> = ({
  onReferenceFrequencyChange,
  currentFrequency
}) => {
  const {
    profile,
    isLoading,
    error,
    measureVoiceRange,
    analyzeVowel,
    calculateOptimalReference,
    createProfile,
    saveProfile,
    loadProfile,
    clearProfile,
    getMeasurementProgress,
    hasVoiceRange,
    hasAllVowels,
    hasOptimalReference,
    currentReference
  } = useSpeakerProfile();

  const adaptiveHook = useAdaptiveReference();
  const {
    currentReference: adaptiveReference,
    isAdaptive,
    setAdaptiveMode,
    addPitchData,
    getStatistics,
    getTrend,
    adjustmentFactor,
    setAdjustmentFactor
  } = adaptiveHook;

  const [activeTab, setActiveTab] = useState<'profile' | 'measurement' | 'adaptive'>('profile');
  const [userId, setUserId] = useState('');
  const [recordingType, setRecordingType] = useState<'range' | 'vowel-a' | 'vowel-i' | 'vowel-u' | null>(null);
  const [isRecording, setIsRecording] = useState(false);

  // 컴포넌트 마운트 시 프로필 로드 시도
  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  // 기준 주파수 변경 시 부모 컴포넌트에 알림
  useEffect(() => {
    const reference = isAdaptive ? adaptiveReference : currentReference;
    if (onReferenceFrequencyChange) {
      onReferenceFrequencyChange(reference);
    }
  }, [currentReference, adaptiveReference, isAdaptive, onReferenceFrequencyChange]);

  // 실시간 피치 데이터 추가 (적응형 모드일 때)
  useEffect(() => {
    if (isAdaptive && currentFrequency && currentFrequency > 0) {
      addPitchData(currentFrequency, 0.8, 'normal');
    }
  }, [currentFrequency, isAdaptive, addPitchData]);

  const progress = getMeasurementProgress();
  const stats = getStatistics();
  const trend = getTrend();

  // 🎤 녹음 시작
  const startRecording = async (type: 'range' | 'vowel-a' | 'vowel-i' | 'vowel-u') => {
    setRecordingType(type);
    setIsRecording(true);
    
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      const audioChunks: Blob[] = [];

      mediaRecorder.ondataavailable = (event) => {
        audioChunks.push(event.data);
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
        const audioFile = new File([audioBlob], `${type}-${Date.now()}.wav`, { type: 'audio/wav' });
        
        // 분석 실행
        if (type === 'range') {
          await measureVoiceRange(audioFile);
        } else if (type.startsWith('vowel-')) {
          const vowelType = type.split('-')[1] as 'a' | 'i' | 'u';
          await analyzeVowel(audioFile, vowelType);
        }
        
        setIsRecording(false);
        setRecordingType(null);
        
        // 스트림 정리
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      
      // 자동 정지 (10초 후)
      setTimeout(() => {
        if (mediaRecorder.state === 'recording') {
          mediaRecorder.stop();
        }
      }, 10000);
      
    } catch (err) {
      console.error('녹음 시작 실패:', err);
      setIsRecording(false);
      setRecordingType(null);
    }
  };

  // 🎤 녹음 정지
  const stopRecording = () => {
    setIsRecording(false);
    setRecordingType(null);
  };

  return (
    <div className="card mt-4">
      <div className="card-header">
        <h5 className="mb-0">
          <i className="fas fa-user-circle me-2"></i>
          화자별 맞춤 기준 주파수 설정
        </h5>
        
        {/* 탭 네비게이션 */}
        <ul className="nav nav-tabs mt-3" role="tablist">
          <li className="nav-item">
            <button 
              className={`nav-link ${activeTab === 'profile' ? 'active' : ''}`}
              onClick={() => setActiveTab('profile')}
            >
              <i className="fas fa-user me-1"></i>프로필
            </button>
          </li>
          <li className="nav-item">
            <button 
              className={`nav-link ${activeTab === 'measurement' ? 'active' : ''}`}
              onClick={() => setActiveTab('measurement')}
            >
              <i className="fas fa-microphone me-1"></i>측정
            </button>
          </li>
          <li className="nav-item">
            <button 
              className={`nav-link ${activeTab === 'adaptive' ? 'active' : ''}`}
              onClick={() => setActiveTab('adaptive')}
            >
              <i className="fas fa-brain me-1"></i>적응형
            </button>
          </li>
        </ul>
      </div>

      <div className="card-body">
        {/* 프로필 탭 */}
        {activeTab === 'profile' && (
          <div>
            {!profile ? (
              <div className="text-center py-4">
                <i className="fas fa-user-plus fa-3x text-muted mb-3"></i>
                <h6>새 화자 프로필 생성</h6>
                <div className="row justify-content-center">
                  <div className="col-md-6">
                    <div className="input-group mb-3">
                      <span className="input-group-text">
                        <i className="fas fa-id-badge"></i>
                      </span>
                      <input
                        type="text"
                        className="form-control"
                        placeholder="사용자 ID 입력"
                        value={userId}
                        onChange={(e) => setUserId(e.target.value)}
                      />
                    </div>
                    <button 
                      className="btn btn-primary"
                      onClick={() => createProfile(userId)}
                      disabled={!userId.trim()}
                    >
                      프로필 생성
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div>
                {/* 프로필 정보 */}
                <div className="row mb-4">
                  <div className="col-md-6">
                    <div className="card border-primary">
                      <div className="card-body">
                        <h6 className="card-title">
                          <i className="fas fa-user me-2"></i>
                          {profile.userId}
                        </h6>
                        <p className="card-text">
                          <strong>개인 기준 주파수:</strong> {profile.personalReference.toFixed(1)}Hz<br/>
                          <strong>신뢰도:</strong> {(profile.confidence * 100).toFixed(1)}%<br/>
                          <strong>마지막 측정:</strong> {new Date(profile.lastMeasurement).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="col-md-6">
                    <div className="card border-info">
                      <div className="card-body">
                        <h6 className="card-title">
                          <i className="fas fa-chart-line me-2"></i>
                          측정 진행률
                        </h6>
                        <div className="progress mb-2">
                          <div 
                            className="progress-bar" 
                            style={{ width: `${progress.percentage}%` }}
                          >
                            {progress.percentage}%
                          </div>
                        </div>
                        <small className="text-muted">
                          {progress.completed}/{progress.total} 항목 완료
                        </small>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 측정 상태 */}
                <div className="row mb-3">
                  <div className="col-md-4">
                    <div className={`alert ${hasVoiceRange ? 'alert-success' : 'alert-secondary'}`}>
                      <i className={`fas ${hasVoiceRange ? 'fa-check' : 'fa-times'} me-2`}></i>
                      음역대 측정 {hasVoiceRange ? '완료' : '필요'}
                    </div>
                  </div>
                  <div className="col-md-4">
                    <div className={`alert ${hasAllVowels ? 'alert-success' : 'alert-secondary'}`}>
                      <i className={`fas ${hasAllVowels ? 'fa-check' : 'fa-times'} me-2`}></i>
                      모음 분석 {hasAllVowels ? '완료' : `${profile.vowelAnalysis.length}/3`}
                    </div>
                  </div>
                  <div className="col-md-4">
                    <div className={`alert ${hasOptimalReference ? 'alert-success' : 'alert-secondary'}`}>
                      <i className={`fas ${hasOptimalReference ? 'fa-check' : 'fa-times'} me-2`}></i>
                      최적화 {hasOptimalReference ? '완료' : '필요'}
                    </div>
                  </div>
                </div>

                {/* 프로필 관리 버튼 */}
                <div className="d-flex gap-2">
                  <button 
                    className="btn btn-success" 
                    onClick={saveProfile}
                  >
                    <i className="fas fa-save me-1"></i>저장
                  </button>
                  <button 
                    className="btn btn-info" 
                    onClick={loadProfile}
                  >
                    <i className="fas fa-upload me-1"></i>불러오기
                  </button>
                  <button 
                    className="btn btn-warning" 
                    onClick={clearProfile}
                  >
                    <i className="fas fa-trash me-1"></i>초기화
                  </button>
                  {hasVoiceRange && hasAllVowels && (
                    <button 
                      className="btn btn-primary" 
                      onClick={() => calculateOptimalReference()}
                      disabled={isLoading}
                    >
                      <i className="fas fa-calculator me-1"></i>
                      {isLoading ? '계산 중...' : '최적 기준점 계산'}
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* 측정 탭 */}
        {activeTab === 'measurement' && profile && (
          <div>
            <div className="row">
              {/* 음역대 측정 */}
              <div className="col-md-6 mb-3">
                <div className="card border-warning">
                  <div className="card-header">
                    <h6 className="mb-0">
                      <i className="fas fa-music me-2"></i>음역대 측정
                    </h6>
                  </div>
                  <div className="card-body">
                    <p className="small">최저음과 최고음을 측정하여 기하평균을 계산합니다.</p>
                    <p className="text-muted">
                      <strong>안내:</strong> 가장 낮은 "음~" 소리와 가장 높은 "음~" 소리를 각각 3초씩 내주세요.
                    </p>
                    
                    {hasVoiceRange && profile.voiceRange && (
                      <div className="alert alert-success">
                        <small>
                          <strong>측정 완료:</strong><br/>
                          최저음: {profile.voiceRange.min_frequency}Hz<br/>
                          최고음: {profile.voiceRange.max_frequency}Hz<br/>
                          기하평균: {profile.voiceRange.geometric_mean}Hz
                        </small>
                      </div>
                    )}
                    
                    <button 
                      className={`btn ${hasVoiceRange ? 'btn-outline-warning' : 'btn-warning'} w-100`}
                      onClick={() => startRecording('range')}
                      disabled={isRecording || isLoading}
                    >
                      {isRecording && recordingType === 'range' ? (
                        <>
                          <i className="fas fa-stop me-1"></i>측정 중... (10초)
                        </>
                      ) : (
                        <>
                          <i className="fas fa-microphone me-1"></i>
                          {hasVoiceRange ? '재측정' : '음역대 측정'}
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>

              {/* 모음별 분석 */}
              <div className="col-md-6 mb-3">
                <div className="card border-info">
                  <div className="card-header">
                    <h6 className="mb-0">
                      <i className="fas fa-comment me-2"></i>모음별 분석
                    </h6>
                  </div>
                  <div className="card-body">
                    <p className="small">각 모음의 주파수 특성을 분석합니다.</p>
                    
                    {/* 모음별 측정 버튼 */}
                    <div className="row">
                      {[
                        { vowel: 'a', label: '아', color: 'primary' },
                        { vowel: 'i', label: '이', color: 'success' },
                        { vowel: 'u', label: '우', color: 'danger' }
                      ].map(({ vowel, label, color }) => {
                        const hasVowel = profile.vowelAnalysis.some(v => v.vowel_type === vowel);
                        const vowelData = profile.vowelAnalysis.find(v => v.vowel_type === vowel);
                        
                        return (
                          <div key={vowel} className="col-4 mb-2">
                            <button 
                              className={`btn btn-outline-${color} btn-sm w-100`}
                              onClick={() => startRecording(`vowel-${vowel}` as any)}
                              disabled={isRecording || isLoading}
                            >
                              {isRecording && recordingType === `vowel-${vowel}` ? (
                                <i className="fas fa-circle-notch fa-spin"></i>
                              ) : (
                                <>
                                  {hasVowel && <i className="fas fa-check me-1"></i>}
                                  /{label}/
                                </>
                              )}
                            </button>
                            {hasVowel && vowelData && (
                              <div className="text-center mt-1">
                                <small className="text-muted">
                                  {vowelData.fundamental_frequency.toFixed(1)}Hz
                                </small>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                    
                    <div className="text-center mt-2">
                      <small className="text-muted">
                        {profile.vowelAnalysis.length}/3 모음 완료
                      </small>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 적응형 탭 */}
        {activeTab === 'adaptive' && (
          <div>
            <div className="row">
              <div className="col-md-6">
                <div className="card border-primary">
                  <div className="card-header">
                    <h6 className="mb-0">
                      <i className="fas fa-cogs me-2"></i>적응형 설정
                    </h6>
                  </div>
                  <div className="card-body">
                    <div className="form-check form-switch mb-3">
                      <input 
                        className="form-check-input" 
                        type="checkbox" 
                        id="adaptiveSwitch"
                        checked={isAdaptive}
                        onChange={(e) => setAdaptiveMode(e.target.checked)}
                      />
                      <label className="form-check-label" htmlFor="adaptiveSwitch">
                        실시간 적응형 조정 활성화
                      </label>
                    </div>
                    
                    <div className="mb-3">
                      <label className="form-label">조정 강도: {adjustmentFactor}</label>
                      <input 
                        type="range" 
                        className="form-range" 
                        min="0.01" 
                        max="0.5" 
                        step="0.01"
                        value={adjustmentFactor}
                        onChange={(e) => setAdjustmentFactor(parseFloat(e.target.value))}
                      />
                      <small className="text-muted">낮을수록 보수적, 높을수록 민감하게 조정</small>
                    </div>
                    
                    <div className="alert alert-info">
                      <strong>현재 기준 주파수:</strong><br/>
                      {isAdaptive ? adaptiveReference.toFixed(1) : currentReference.toFixed(1)}Hz
                      {isAdaptive && <small className="text-success"> (적응형)</small>}
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="col-md-6">
                <div className="card border-success">
                  <div className="card-header">
                    <h6 className="mb-0">
                      <i className="fas fa-chart-bar me-2"></i>실시간 통계
                    </h6>
                  </div>
                  <div className="card-body">
                    <div className="row text-center">
                      <div className="col-4">
                        <div className="h6 text-primary">{stats.count}</div>
                        <small className="text-muted">샘플 수</small>
                      </div>
                      <div className="col-4">
                        <div className="h6 text-success">{stats.mean}Hz</div>
                        <small className="text-muted">평균</small>
                      </div>
                      <div className="col-4">
                        <div className="h6 text-warning">{stats.stability.toFixed(2)}</div>
                        <small className="text-muted">안정성</small>
                      </div>
                    </div>
                    
                    <hr/>
                    
                    <div className="text-center">
                      <span className={`badge ${
                        trend === 'rising' ? 'bg-success' : 
                        trend === 'falling' ? 'bg-danger' : 
                        trend === 'stable' ? 'bg-primary' : 'bg-secondary'
                      }`}>
                        {trend === 'rising' && <><i className="fas fa-arrow-up me-1"></i>상승 트렌드</>}
                        {trend === 'falling' && <><i className="fas fa-arrow-down me-1"></i>하락 트렌드</>}
                        {trend === 'stable' && <><i className="fas fa-minus me-1"></i>안정</>}
                        {trend === 'insufficient_data' && <><i className="fas fa-question me-1"></i>데이터 부족</>}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 에러 표시 */}
        {error && (
          <div className="alert alert-danger mt-3">
            <i className="fas fa-exclamation-triangle me-2"></i>
            {error}
          </div>
        )}
      </div>
    </div>
  );
};