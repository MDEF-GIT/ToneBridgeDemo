import React, { useState, useEffect, useRef } from 'react';
import { useDualAxisChart } from '../hooks/useDualAxisChart';

interface UploadedFile {
  file_id: string;
  filename: string;
  expected_text: string;
  has_textgrid: boolean;
  file_size: number;
  modified_time: number;
}

interface SyllablePoint {
  syllable: string;
  start: number;
  end: number;
  frequency: number;
  time: number; // 중간 시점
}

const UploadedFileTestSection: React.FC = () => {
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [selectedFileId, setSelectedFileId] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [syllablePoints, setSyllablePoints] = useState<SyllablePoint[]>([]);
  const [currentPlayingSyllable, setCurrentPlayingSyllable] = useState<number>(-1);
  
  const chartCanvasRef = useRef<HTMLCanvasElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const testDualAxisChart = useDualAxisChart(chartCanvasRef, 'uploaded-file-test');

  // 컴포넌트 마운트 시 듀얼축 차트 초기화
  useEffect(() => {
    console.log('🚀🚀🚀 업로드 파일 테스트 컴포넌트 마운트됨 🚀🚀🚀');
    console.log('📊 업로드 파일 테스트: 듀얼축 차트 초기화');
  }, [testDualAxisChart]);

  // 업로드된 파일 목록 불러오기 (한 번만)
  useEffect(() => {
    loadUploadedFiles();
  }, []); // 빈 dependency array로 한 번만 실행

  const loadUploadedFiles = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/uploaded_files');
      if (!response.ok) throw new Error('파일 목록 조회 실패');
      
      const data = await response.json();
      
      // 🎯 개선된 파일만 필터링 (TextGrid가 있고, _original/_trimmed가 아닌 파일)
      const processedFiles = (data.files || []).filter((file: UploadedFile) => {
        // TextGrid가 있는 파일만
        if (!file.has_textgrid) return false;
        
        // _original, _trimmed 접미사가 없는 파일만 (최종 개선된 버전)
        if (file.file_id.endsWith('_original') || file.file_id.endsWith('_trimmed')) {
          return false;
        }
        
        return true;
      });
      
      setUploadedFiles(processedFiles);
      console.log(`📁 개선된 업로드 파일 ${processedFiles.length}개 로드됨 (전체 ${data.files?.length || 0}개 중 필터링)`);
    } catch (err) {
      setError(err instanceof Error ? err.message : '파일 목록 조회 실패');
      console.error('❌ 업로드 파일 목록 조회 오류:', err);
    } finally {
      setLoading(false);
    }
  };


  // 🎯 음절 클릭 처리 (버튼 클릭 시)
  const handleSyllableClick = (syllableIndex: number) => {
    const syllable = syllablePoints[syllableIndex];
    if (syllable && audioRef.current) {
      console.log(`🎵 음절 클릭: ${syllable.syllable} (${syllable.start}s - ${syllable.end}s)`);
      audioRef.current.currentTime = syllable.start;
      audioRef.current.play();
      setCurrentPlayingSyllable(syllableIndex);
    }
  };

  // 파일 선택 시 차트 업데이트 (자동 최적화 포함)
  const handleFileSelect = async (fileId: string) => {
    console.log('🔥🔥🔥 handleFileSelect 호출됨 🔥🔥🔥', fileId);
    
    if (!fileId) {
      console.log('📝 파일 선택 해제');
      setSelectedFileId('');
      setSyllablePoints([]);
      setCurrentPlayingSyllable(-1);
      try {
        testDualAxisChart.clearChart();
      } catch (err) {
        console.warn('⚠️ 차트 클리어 실패 (빈 선택):', err);
      }
      return;
    }

    try {
      console.log('🚀 파일 선택 처리 시작:', fileId);
      setLoading(true);
      setSelectedFileId(fileId);
      setError('');
      
      // 🛡️ 차트 상태 검증
      if (!testDualAxisChart) {
        throw new Error('차트가 초기화되지 않았습니다');
      }

      console.log(`🎯🎯🎯 업로드 파일 분석 시작: ${fileId} 🎯🎯🎯`);

      // 🎯 첫 번째: 자동 최적화 실행 (reference 파일과 동일한 품질 보장)
      console.log(`🚀 파일 최적화 시작: ${fileId}`);
      const formData = new FormData();
      formData.append('file_id', fileId);
      
      const optimizeResponse = await fetch(`/api/optimize-uploaded-file`, {
        method: 'POST',
        body: formData
      });

      if (optimizeResponse.ok) {
        const optimizeResult = await optimizeResponse.json();
        console.log(`✅ 최적화 완료: ${optimizeResult.syllables?.length || 0}개 음절`);
      } else {
        console.warn(`⚠️ 최적화 실패, 기존 데이터로 진행`);
      }

      // 🎯 이제 최적화된 데이터로 분석 진행
      // 1. 전체 피치 데이터 로드
      console.log(`🔍 피치 데이터 요청: ${fileId}`);
      const pitchResponse = await fetch(`/api/uploaded_files/${fileId}/pitch`);
      if (!pitchResponse.ok) throw new Error(`피치 데이터 조회 실패: ${pitchResponse.status}`);
      const pitchData = await pitchResponse.json();
      
      // 🛡️ 피치 데이터 검증
      if (!Array.isArray(pitchData)) {
        throw new Error('피치 데이터가 배열이 아닙니다');
      }
      console.log(`✅ 피치 데이터 로드: ${pitchData.length}개 포인트`);

      // 2. 음절별 대표 피치 로드 (음절 정보 포함)
      console.log(`🔍 음절 피치 데이터 요청: ${fileId}`);
      const syllablePitchResponse = await fetch(`/api/uploaded_files/${fileId}/pitch?syllable_only=true`);
      if (!syllablePitchResponse.ok) throw new Error(`음절 피치 데이터 조회 실패: ${syllablePitchResponse.status}`);
      const syllablePitch = await syllablePitchResponse.json();
      
      // 🛡️ 음절 피치 데이터 검증
      if (!Array.isArray(syllablePitch)) {
        throw new Error('음절 피치 데이터가 배열이 아닙니다');
      }
      console.log(`✅ 음절 피치 데이터 로드: ${syllablePitch.length}개 음절`);

      // 3. 음절 구간 정보 로드
      console.log(`🔍 음절 구간 데이터 요청: ${fileId}`);
      const syllablesResponse = await fetch(`/api/uploaded_files/${fileId}/syllables`);
      let syllables = [];
      if (syllablesResponse.ok) {
        syllables = await syllablesResponse.json();
        console.log(`✅ 음절 구간 데이터 로드: ${syllables.length}개`);
      } else {
        console.warn('⚠️ 음절 구간 데이터 로드 실패, 빈 배열로 진행');
      }

      // 4. 음절 포인트 데이터 구성
      console.log(`🔄 음절 포인트 데이터 구성 시작`);
      console.log(`🔍 syllablePitch 구조:`, syllablePitch);
      console.log(`🔍 syllables 구조:`, syllables);
      
      const points: SyllablePoint[] = [];
      
      // 🎯 두 가지 데이터 소스를 결합하여 완전한 음절 정보 구성
      if (syllablePitch.length > 0 && syllables.length > 0) {
        // syllables에서 시간 구간, syllablePitch에서 주파수 정보 가져오기
        for (let i = 0; i < Math.min(syllablePitch.length, syllables.length); i++) {
          const pitchInfo = syllablePitch[i];
          const syllableInfo = syllables[i];
          
          if (typeof pitchInfo.frequency === 'number' && typeof syllableInfo === 'string') {
            // syllables는 단순 문자열 배열인 경우
            points.push({
              syllable: syllableInfo,
              start: pitchInfo.time - 0.1, // 임시로 시간 중심에서 ±0.1초
              end: pitchInfo.time + 0.1,
              frequency: pitchInfo.frequency,
              time: pitchInfo.time
            });
          } else if (typeof pitchInfo.frequency === 'number' && syllableInfo.start !== undefined) {
            // syllables가 객체 배열인 경우
            points.push({
              syllable: pitchInfo.syllable || syllableInfo.syllable || `음절${i + 1}`,
              start: syllableInfo.start,
              end: syllableInfo.end,
              frequency: pitchInfo.frequency,
              time: pitchInfo.time || (syllableInfo.start + syllableInfo.end) / 2
            });
          }
        }
      } else if (syllablePitch.length > 0) {
        // syllablePitch만 있는 경우 (fallback)
        syllablePitch.forEach((sp: any, index: number) => {
          if (typeof sp.frequency === 'number') {
            points.push({
              syllable: sp.syllable || `음절${index + 1}`,
              start: sp.time - 0.1,
              end: sp.time + 0.1,
              frequency: sp.frequency,
              time: sp.time
            });
          }
        });
      }

      console.log(`✅ 음절 포인트 데이터 구성 완료: ${points.length}개`);
      console.log(`🎯 설정된 음절 포인트:`, points);
      setSyllablePoints(points);
      console.log(`🔄 syllablePoints 상태 업데이트 완료: ${points.length}개`);

      // 5. 차트 클리어 후 데이터 추가
      try {
        console.log('🎯 차트 클리어 시작');
        testDualAxisChart.clearChart();
        console.log('✅ 차트 클리어 완료');
      } catch (clearError) {
        console.error('❌ 차트 클리어 오류:', clearError);
        throw new Error(`차트 클리어 실패: ${clearError}`);
      }
      
      // 6. 전체 피치 데이터를 듀얼축 차트에 추가
      try {
        console.log(`🎯 피치 데이터 추가 시작: ${pitchData.length}개 포인트`);
        pitchData.forEach((point: any, index: number) => {
          if (point && typeof point.frequency === 'number' && typeof point.time === 'number') {
            testDualAxisChart.addDualAxisData(point.frequency, point.time, 'reference');
          } else {
            console.warn(`⚠️ 잘못된 피치 데이터 [${index}]:`, point);
          }
        });
        console.log('✅ 피치 데이터 추가 완료');
      } catch (pitchError) {
        console.error('❌ 피치 데이터 추가 오류:', pitchError);
        throw new Error(`피치 데이터 추가 실패: ${pitchError}`);
      }

      // 7. 음절 annotation 추가
      try {
        if (points.length > 0) {
          const annotationData = points.map((point) => ({
            label: point.syllable,
            start: point.start,
            end: point.end,
            frequency: point.frequency,
            time: point.time
          }));
          
          console.log(`🎯 업로드 파일 음절 annotation 추가: ${annotationData.length}개`);
          testDualAxisChart.addSyllableAnnotations(annotationData);
          console.log('✅ 음절 annotation 추가 완료');
        } else {
          console.log('⚠️ 음절 데이터가 없어서 annotation 추가 생략');
        }
      } catch (annotationError) {
        console.error('❌ 음절 annotation 추가 오류:', annotationError);
        // annotation 오류는 치명적이지 않으므로 계속 진행
        console.warn('⚠️ annotation 추가 실패했지만 차트는 표시됩니다');
      }

      console.log(`✅ 업로드 파일 분석 완료: ${pitchData.length}개 피치 포인트, ${points.length}개 음절`);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : '파일 분석 실패');
      console.error('❌ 업로드 파일 분석 오류:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {/* 파일 선택 드롭다운 */}
      <div className="row mb-4">
        <div className="col-md-8">
          <label htmlFor="uploadedFileSelect" className="form-label">
            <i className="fas fa-file-audio me-2"></i>업로드된 파일 선택
          </label>
          <select
            id="uploadedFileSelect"
            className="form-select"
            value={selectedFileId}
            onChange={(e) => handleFileSelect(e.target.value)}
            disabled={false}
          >
            <option value="">파일을 선택하세요</option>
            {uploadedFiles.map((file) => {
              // 파일명에서 정보 추출하여 표시용 이름 생성
              const parts = file.file_id.split('_');
              const learnerName = parts[0] || '익명';
              const gender = parts[1] || '';
              const ageGroup = parts[2] || '';
              const sentence = file.expected_text || parts[3] || '';
              const timestamp = parts[4] || '';
              const displayName = `${learnerName} (${gender}, ${ageGroup}) - ${sentence}`;
              
              return (
                <option key={file.file_id} value={file.file_id}>
                  {displayName} {timestamp && `(${timestamp})`}
                </option>
              );
            })}
          </select>
          {uploadedFiles.length === 0 && !loading && (
            <div className="text-muted small mt-1">
              <i className="fas fa-info-circle me-1"></i>
              개선된 업로드 파일이 없습니다. 위에서 녹음 후 자동 처리를 기다려주세요!
            </div>
          )}
        </div>
        <div className="col-md-4 d-flex align-items-end">
          <button
            className="btn btn-outline-success"
            onClick={loadUploadedFiles}
            disabled={loading}
          >
            <i className="fas fa-sync-alt me-2"></i>새로고침
          </button>
        </div>
      </div>

      {/* 에러 메시지 */}
      {error && (
        <div className="alert alert-danger" role="alert">
          <i className="fas fa-exclamation-triangle me-2"></i>
          {error}
        </div>
      )}

      {/* 로딩 상태 */}
      {loading && selectedFileId && (
        <div className="text-center text-muted">
          <i className="fas fa-spinner fa-spin me-2"></i>
          파일 분석 중... ({selectedFileId})
        </div>
      )}

      {/* 선택된 파일 정보 */}
      {selectedFileId && (
        <div className="alert alert-info mb-4">
          <div className="row">
            <div className="col-md-6">
              <h6 className="mb-1">
                <i className="fas fa-file-audio me-2"></i>
                선택된 파일: {(() => {
                  const file = uploadedFiles.find(f => f.file_id === selectedFileId);
                  if (!file) return selectedFileId;
                  const parts = file.file_id.split('_');
                  const learnerName = parts[0] || '익명';
                  const sentence = file.expected_text || parts[3] || '';
                  return `${learnerName} - ${sentence}`;
                })()}
              </h6>
              <small className="text-muted">
                파일명: {selectedFileId}.wav {uploadedFiles.find(f => f.file_id === selectedFileId)?.has_textgrid ? '/ TextGrid 있음' : '/ TextGrid 없음'}
              </small>
              <br />
              <small className="text-muted">
                업로드 시간: {(() => {
                  const file = uploadedFiles.find(f => f.file_id === selectedFileId);
                  if (!file) return '';
                  return new Date(file.modified_time * 1000).toLocaleString();
                })()}
              </small>
            </div>
            <div className="col-md-6">
              <div className="mt-2">
                <label className="form-label mb-1">
                  <i className="fas fa-play me-2"></i>음성 파일 재생
                </label>
                <audio
                  ref={audioRef}
                  controls
                  className="w-100"
                  style={{ height: '35px' }}
                  src={`/static/uploads/${selectedFileId}.wav`}
                  onError={() => console.error('오디오 로드 실패:', selectedFileId)}
                  onLoadedData={() => console.log('오디오 로드 완료:', selectedFileId)}
                  onPlay={() => {
                    console.log('🎵 업로드 파일 재생 시작');
                    // 재생 진행 상황 추적
                    const updateProgress = () => {
                      if (audioRef.current && !audioRef.current.paused) {
                        const currentTime = audioRef.current.currentTime;
                        
                        // 🎯 차트에 현재 재생 시점 표시
                        testDualAxisChart.updatePlaybackProgress(currentTime);
                        
                        // 현재 재생 중인 음절 찾기
                        const currentSyllableIndex = syllablePoints.findIndex(
                          point => currentTime >= point.start && currentTime <= point.end
                        );
                        setCurrentPlayingSyllable(currentSyllableIndex);
                        requestAnimationFrame(updateProgress);
                      }
                    };
                    requestAnimationFrame(updateProgress);
                  }}
                  onPause={() => {
                    console.log('🎵 업로드 파일 재생 일시정지');
                    testDualAxisChart.clearPlaybackProgress();
                    setCurrentPlayingSyllable(-1);
                  }}
                  onEnded={() => {
                    console.log('🎵 업로드 파일 재생 완료');
                    testDualAxisChart.clearPlaybackProgress();
                    setCurrentPlayingSyllable(-1);
                  }}
                >
                  브라우저가 오디오 재생을 지원하지 않습니다.
                </audio>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 차트 영역 */}
      <div className="position-relative" style={{ height: '400px' }}>
        <canvas
          ref={chartCanvasRef}
          className="border rounded"
          style={{ width: '100%', height: '100%' }}
        />
        {!selectedFileId && (
          <div className="position-absolute top-50 start-50 translate-middle text-center text-muted">
            <i className="fas fa-chart-line fa-3x mb-3 opacity-50"></i>
            <div>파일을 선택하면 피치 차트가 표시됩니다</div>
          </div>
        )}
      </div>

      {/* 차트 컨트롤 버튼들 */}
      {selectedFileId && (
        <div className="mt-3">
          <div className="row align-items-center">
            <div className="col-md-6">
              <h6 className="mb-2">
                <i className="fas fa-cog me-2"></i>차트 설정
              </h6>
              <div className="btn-group btn-group-sm" role="group">
                <button
                  className={`btn ${testDualAxisChart.yAxisUnit === 'semitone' ? 'btn-primary' : 'btn-outline-primary'}`}
                  onClick={() => testDualAxisChart.setYAxisUnit('semitone')}
                  title="세미톤 단위로 표시"
                >
                  <i className="fas fa-music me-1"></i>세미톤
                </button>
                <button
                  className={`btn ${testDualAxisChart.yAxisUnit === 'qtone' ? 'btn-primary' : 'btn-outline-primary'}`}
                  onClick={() => testDualAxisChart.setYAxisUnit('qtone')}
                  title="큐톤 단위로 표시"
                >
                  <i className="fas fa-adjust me-1"></i>큐톤
                </button>
              </div>
            </div>
            <div className="col-md-6 text-end">
              <small className="text-muted">
                <i className="fas fa-info-circle me-1"></i>
                우측 Y축 단위 변경 가능
              </small>
            </div>
          </div>
        </div>
      )}

      {/* 음절별 분석 결과 표 */}
      {(() => {
        console.log(`🎯🎯🎯 렌더링 조건 확인: selectedFileId=${selectedFileId}, syllablePoints.length=${syllablePoints.length} 🎯🎯🎯`);
        console.log('🔍 syllablePoints 상태:', syllablePoints);
        return null;
      })()}
      {selectedFileId && syllablePoints.length > 0 && (
        <div className="mt-3">
          <h6 className="mb-3">
            <i className="fas fa-table me-2"></i>분절별 음성 파라메터 분석
          </h6>
          <div className="table-responsive">
            <table className="table table-sm table-bordered table-hover">
              <thead className="table-light">
                <tr>
                  <th style={{width: '6%'}} className="text-center">음절</th>
                  <th style={{width: '10%'}} className="text-center">F0 (Hz)</th>
                  <th style={{width: '10%'}} className="text-center">
                    {testDualAxisChart.yAxisUnit === 'semitone' ? '세미톤' : '큐톤'}
                  </th>
                  <th style={{width: '12%'}} className="text-center">시간구간 (s)</th>
                  <th style={{width: '8%'}} className="text-center">지속시간</th>
                  <th style={{width: '10%'}} className="text-center">피치범위</th>
                  <th style={{width: '10%'}} className="text-center">발음속도</th>
                  <th style={{width: '12%'}} className="text-center">음성품질</th>
                  <th style={{width: '12%'}} className="text-center">상대레벨</th>
                  <th style={{width: '10%'}} className="text-center">특성</th>
                </tr>
              </thead>
              <tbody>
                {syllablePoints.map((point, index) => {
                  const duration = point.end - point.start;
                  const convertedValue = testDualAxisChart.yAxisUnit === 'semitone' 
                    ? 12 * Math.log2(point.frequency / 440) + 69 // A4 = 440Hz = 69 semitones
                    : 1200 * Math.log2(point.frequency / 261.63); // cents from C4 (261.63Hz)
                  
                  // 🎯 전체 음절의 평균 주파수 계산 (상대 레벨용)
                  const avgFreq = syllablePoints.reduce((sum, p) => sum + p.frequency, 0) / syllablePoints.length;
                  const freqDeviation = ((point.frequency - avgFreq) / avgFreq * 100);
                  
                  // 🎯 주파수 레벨 분류
                  const getFrequencyLevel = (freq: number) => {
                    if (freq < 100) return { level: '저음', color: 'text-info', badge: 'info' };
                    if (freq < 150) return { level: '중저음', color: 'text-primary', badge: 'primary' };
                    if (freq < 200) return { level: '중음', color: 'text-success', badge: 'success' };
                    if (freq < 300) return { level: '중고음', color: 'text-warning', badge: 'warning' };
                    return { level: '고음', color: 'text-danger', badge: 'danger' };
                  };
                  
                  // 🎯 피치 범위 계산 (임시: 현재 음절 주변 변동성)
                  const pitchRange = Math.abs(freqDeviation);
                  const getRangeLevel = (range: number) => {
                    if (range < 5) return { level: '안정', color: 'success' };
                    if (range < 15) return { level: '보통', color: 'warning' };
                    return { level: '변동', color: 'danger' };
                  };
                  
                  // 🎯 발음 속도 분석
                  const getSpeedAnalysis = (dur: number) => {
                    if (dur < 0.15) return { speed: '빠름', level: 'fast', color: 'danger' };
                    if (dur < 0.3) return { speed: '보통', level: 'normal', color: 'success' };
                    if (dur < 0.5) return { speed: '느림', level: 'slow', color: 'warning' };
                    return { speed: '매우느림', level: 'very-slow', color: 'info' };
                  };
                  
                  // 🎯 음성 품질 지표 (임시: 주파수 안정성 기반)
                  const getQualityAnalysis = (freq: number, dur: number) => {
                    const stability = freq > 80 && freq < 500 ? 'good' : 'poor';
                    const clarity = dur > 0.1 && dur < 0.8 ? 'clear' : 'unclear';
                    
                    if (stability === 'good' && clarity === 'clear') {
                      return { quality: '우수', score: '85+', color: 'success' };
                    } else if (stability === 'good') {
                      return { quality: '양호', score: '70+', color: 'primary' };
                    } else {
                      return { quality: '개선필요', score: '<70', color: 'warning' };
                    }
                  };
                  
                  // 🎯 상대 레벨 분석
                  const getRelativeLevel = (deviation: number) => {
                    if (Math.abs(deviation) < 5) return { level: '표준', color: 'success' };
                    if (deviation > 0) return { level: `+${deviation.toFixed(1)}%`, color: 'warning' };
                    return { level: `${deviation.toFixed(1)}%`, color: 'info' };
                  };
                  
                  // 🎯 음절 특성 분석
                  const getSyllableCharacteristics = (syllable: string, freq: number) => {
                    const vowels = ['ㅏ', 'ㅓ', 'ㅗ', 'ㅜ', 'ㅡ', 'ㅣ', 'ㅐ', 'ㅔ', 'ㅚ', 'ㅟ'];
                    const hasVowel = vowels.some(v => syllable.includes(v));
                    
                    if (freq > 200) return { char: '명료음', type: '고주파' };
                    if (freq < 120) return { char: '저음역', type: '안정음' };
                    return { char: '중간음', type: '표준음' };
                  };
                  
                  const freqLevel = getFrequencyLevel(point.frequency);
                  const rangeLevel = getRangeLevel(pitchRange);
                  const speedAnalysis = getSpeedAnalysis(duration);
                  const qualityAnalysis = getQualityAnalysis(point.frequency, duration);
                  const relativeLevel = getRelativeLevel(freqDeviation);
                  const characteristics = getSyllableCharacteristics(point.syllable, point.frequency);
                  
                  return (
                    <tr 
                      key={index}
                      className={currentPlayingSyllable === index ? 'table-primary' : ''}
                      style={{ cursor: 'pointer' }}
                      onClick={() => handleSyllableClick(index)}
                      title="클릭하여 해당 구간 재생"
                    >
                      {/* 음절 */}
                      <td className="text-center fw-bold fs-6">{point.syllable}</td>
                      
                      {/* F0 주파수 */}
                      <td className="text-center">
                        <span className={freqLevel.color} style={{fontSize: '0.9em'}}>
                          <strong>{point.frequency.toFixed(1)}</strong>
                        </span>
                      </td>
                      
                      {/* 세미톤/큐톤 */}
                      <td className="text-center">
                        <small>{convertedValue.toFixed(1)}</small>
                      </td>
                      
                      {/* 시간 구간 */}
                      <td className="text-center">
                        <small style={{fontSize: '0.75em'}}>
                          {point.start.toFixed(2)}-{point.end.toFixed(2)}
                        </small>
                      </td>
                      
                      {/* 지속 시간 */}
                      <td className="text-center">
                        <small>{duration.toFixed(2)}s</small>
                      </td>
                      
                      {/* 피치 범위 */}
                      <td className="text-center">
                        <span className={`badge bg-${rangeLevel.color} bg-opacity-75`} style={{fontSize: '0.7em'}}>
                          {rangeLevel.level}
                        </span>
                        <br />
                        <small className="text-muted" style={{fontSize: '0.65em'}}>
                          ±{pitchRange.toFixed(1)}%
                        </small>
                      </td>
                      
                      {/* 발음 속도 */}
                      <td className="text-center">
                        <span className={`badge bg-${speedAnalysis.color} bg-opacity-75`} style={{fontSize: '0.7em'}}>
                          {speedAnalysis.speed}
                        </span>
                        <br />
                        <small className="text-muted" style={{fontSize: '0.65em'}}>
                          {(1/duration).toFixed(1)} syl/s
                        </small>
                      </td>
                      
                      {/* 음성 품질 */}
                      <td className="text-center">
                        <span className={`badge bg-${qualityAnalysis.color} bg-opacity-75`} style={{fontSize: '0.7em'}}>
                          {qualityAnalysis.quality}
                        </span>
                        <br />
                        <small className="text-muted" style={{fontSize: '0.65em'}}>
                          {qualityAnalysis.score}
                        </small>
                      </td>
                      
                      {/* 상대 레벨 */}
                      <td className="text-center">
                        <span className={`badge bg-${relativeLevel.color} bg-opacity-75`} style={{fontSize: '0.7em'}}>
                          {relativeLevel.level}
                        </span>
                        <br />
                        <small className="text-muted" style={{fontSize: '0.65em'}}>
                          vs 평균
                        </small>
                      </td>
                      
                      {/* 특성 */}
                      <td className="text-center">
                        <small style={{fontSize: '0.75em'}}>
                          <div>{characteristics.char}</div>
                          <div className="text-muted" style={{fontSize: '0.9em'}}>
                            {characteristics.type}
                          </div>
                        </small>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="row mt-2">
            <div className="col-md-8">
              <small className="text-muted">
                <i className="fas fa-info-circle me-1"></i>
                표의 행을 클릭하면 해당 음절 구간을 재생할 수 있습니다.
              </small>
            </div>
            <div className="col-md-4 text-end">
              <small className="text-muted">
                총 {syllablePoints.length}개 음절 분석 완료
              </small>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UploadedFileTestSection;