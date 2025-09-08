import React, { useState, useEffect, useRef } from 'react';
import { usePitchChart } from '../hooks/usePitchChart';
import { useDualAxisChart } from '../hooks/useDualAxisChart';

interface UploadedFile {
  id: string;
  wav_file: string;
  textgrid_file: string;
  name: string;
  gender: string;
  age_group: string;
  sentence: string;
  timestamp: string;
  display_name: string;
}

const UploadedFileTestSection: React.FC = () => {
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [selectedFileId, setSelectedFileId] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  
  const chartCanvasRef = useRef<HTMLCanvasElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const testPitchChart = usePitchChart(chartCanvasRef);
  const testDualAxisChart = useDualAxisChart(chartCanvasRef, '');

  // 컴포넌트 마운트 시 듀얼 축 차트 초기화
  useEffect(() => {
    console.log('📊 업로드 파일 테스트: 듀얼 축 차트 초기화');
  }, [testDualAxisChart]);

  // 업로드된 파일 목록 불러오기
  useEffect(() => {
    loadUploadedFiles();
  }, []);

  const loadUploadedFiles = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/uploaded_files');
      if (!response.ok) throw new Error('파일 목록 조회 실패');
      
      const data = await response.json();
      setUploadedFiles(data.files || []);
      console.log(`📁 업로드 파일 ${data.files?.length || 0}개 로드됨`);
    } catch (err) {
      setError(err instanceof Error ? err.message : '파일 목록 조회 실패');
      console.error('❌ 업로드 파일 목록 조회 오류:', err);
    } finally {
      setLoading(false);
    }
  };

  // 파일 선택 시 차트 업데이트
  const handleFileSelect = async (fileId: string) => {
    if (!fileId) {
      setSelectedFileId('');
      testDualAxisChart.clearChart();
      return;
    }

    try {
      setLoading(true);
      setSelectedFileId(fileId);
      setError('');

      console.log(`🎯 업로드 파일 분석 시작: ${fileId}`);

      // 1. 전체 피치 데이터 로드
      const pitchResponse = await fetch(`/api/uploaded_files/${fileId}/pitch`);
      if (!pitchResponse.ok) throw new Error('피치 데이터 조회 실패');
      const pitchData = await pitchResponse.json();

      // 2. 음절 데이터 로드 (annotation용)
      const syllablesResponse = await fetch(`/api/uploaded_files/${fileId}/syllables`);
      let syllables = [];
      if (syllablesResponse.ok) {
        syllables = await syllablesResponse.json();
      }

      // 3. 음절별 대표 피치 로드 (점 표시용)
      const syllablePitchResponse = await fetch(`/api/uploaded_files/${fileId}/pitch?syllable_only=true`);
      let syllablePitch = [];
      if (syllablePitchResponse.ok) {
        syllablePitch = await syllablePitchResponse.json();
      }

      // 4. 차트에 피치 데이터 추가 (기존 데이터 클리어 후)
      testDualAxisChart.clearChart();
      
      // 5. X축, Y축 범위 계산 (최소/최대값 기반 여유 공간 추가)
      if (pitchData.length > 0) {
        // Y축 (주파수) 범위 계산
        const frequencies = pitchData.map((p: any) => p.frequency);
        const minFreq = Math.min(...frequencies);
        const maxFreq = Math.max(...frequencies);
        const freqMargin = (maxFreq - minFreq) * 0.1; // 10% 여유 공간
        const yMin = Math.max(50, minFreq - freqMargin); // 최소 50Hz
        const yMax = maxFreq + freqMargin;
        
        // X축 (시간) 범위 계산
        const times = pitchData.map((p: any) => p.time);
        const minTime = Math.min(...times);
        const maxTime = Math.max(...times);
        const timeMargin = (maxTime - minTime) * 0.05; // 5% 여유 공간
        const xMin = Math.max(0, minTime - timeMargin); // 최소 0초
        const xMax = maxTime + timeMargin;
        
        console.log(`📊 축 자동 조정:`);
        console.log(`   Y축: ${yMin.toFixed(1)}Hz ~ ${yMax.toFixed(1)}Hz (데이터: ${minFreq.toFixed(1)}~${maxFreq.toFixed(1)})`);
        console.log(`   X축: ${xMin.toFixed(2)}초 ~ ${xMax.toFixed(2)}초 (데이터: ${minTime.toFixed(2)}~${maxTime.toFixed(2)})`);
        
        // 차트 축 범위 설정 (듀얼 축 차트는 자동 조정)
        console.log('📊 듀얼 축 차트 - 자동 범위 조정');
      }
      
      // 6. 듀얼 축 차트에 피치 데이터 추가
      pitchData.forEach((point: any) => {
        testDualAxisChart.addDualAxisData(point.frequency, point.time, 'reference');
      });
      
      // 7. 음절 annotation 추가 - 업로드 파일용 데이터 구조 변환
      if (syllables.length > 0 && syllablePitch.length > 0) {
        // syllablePitch 데이터를 SyllableData 형식으로 변환
        const annotationData = syllablePitch.map((sp: any) => ({
          label: sp.syllable,
          start: sp.start,
          end: sp.end,
          frequency: sp.frequency,
          semitone: sp.frequency // Hz 모드에서는 frequency 그대로 사용
        }));
        
        console.log(`🎯 업로드 파일 음절 annotation 추가: ${annotationData.length}개`);
        console.log(`🎯 annotation 데이터:`, annotationData);
        
        testPitchChart.addSyllableAnnotations(annotationData);
      } else {
        console.log(`⚠️ 음절 annotation 생략: syllables=${syllables.length}, syllablePitch=${syllablePitch.length}`);
      }

      console.log(`✅ 업로드 파일 분석 완료: ${pitchData.length}개 피치 포인트, ${syllables.length}개 음절`);
      
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
            disabled={loading}
          >
            <option value="">파일을 선택하세요</option>
            {uploadedFiles.map((file) => (
              <option key={file.id} value={file.id}>
                {file.display_name} ({file.timestamp})
              </option>
            ))}
          </select>
          {uploadedFiles.length === 0 && !loading && (
            <div className="text-muted small mt-1">
              <i className="fas fa-info-circle me-1"></i>
              업로드된 파일이 없습니다. 위에서 녹음을 먼저 해보세요!
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
      {loading && (
        <div className="text-center text-muted">
          <i className="fas fa-spinner fa-spin me-2"></i>
          처리 중...
        </div>
      )}

      {/* 선택된 파일 정보 */}
      {selectedFileId && (
        <div className="alert alert-info mb-4">
          <div className="row">
            <div className="col-md-6">
              <h6 className="mb-1">
                <i className="fas fa-file-audio me-2"></i>
                선택된 파일: {uploadedFiles.find(f => f.id === selectedFileId)?.display_name}
              </h6>
              <small className="text-muted">
                파일명: {selectedFileId}.wav / {selectedFileId}.TextGrid
              </small>
              <br />
              <small className="text-muted">
                업로드 시간: {uploadedFiles.find(f => f.id === selectedFileId)?.timestamp}
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
                    // 차트와 연동하여 재생 위치 표시
                    const updateProgress = () => {
                      if (audioRef.current && testPitchChart.updatePlaybackProgress) {
                        testPitchChart.updatePlaybackProgress(audioRef.current.currentTime);
                        if (!audioRef.current.paused) {
                          requestAnimationFrame(updateProgress);
                        }
                      }
                    };
                    requestAnimationFrame(updateProgress);
                  }}
                  onPause={() => {
                    console.log('🎵 업로드 파일 재생 일시정지');
                    if (testPitchChart.clearPlaybackProgress) {
                      testPitchChart.clearPlaybackProgress();
                    }
                  }}
                  onEnded={() => {
                    console.log('🎵 업로드 파일 재생 완료');
                    if (testPitchChart.clearPlaybackProgress) {
                      testPitchChart.clearPlaybackProgress();
                    }
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
          <div className="row">
            <div className="col-md-8">
              <div className="btn-group btn-group-sm" role="group">
                <button
                  className="btn btn-outline-primary"
                  onClick={() => testPitchChart.adjustPitch('up')}
                  title="피치 위로 조정"
                >
                  <i className="fas fa-arrow-up"></i> 위로
                </button>
                <button
                  className="btn btn-outline-primary"
                  onClick={() => testPitchChart.adjustPitch('down')}
                  title="피치 아래로 조정"
                >
                  <i className="fas fa-arrow-down"></i> 아래로
                </button>
                <button
                  className="btn btn-outline-secondary"
                  onClick={() => testPitchChart.zoomIn()}
                  title="확대"
                >
                  <i className="fas fa-search-plus"></i> 확대
                </button>
                <button
                  className="btn btn-outline-secondary"
                  onClick={() => testPitchChart.zoomOut()}
                  title="축소"
                >
                  <i className="fas fa-search-minus"></i> 축소
                </button>
                <button
                  className="btn btn-outline-info"
                  onClick={() => testPitchChart.scrollLeft()}
                  title="왼쪽으로"
                >
                  <i className="fas fa-arrow-left"></i> 왼쪽
                </button>
                <button
                  className="btn btn-outline-info"
                  onClick={() => testPitchChart.scrollRight()}
                  title="오른쪽으로"
                >
                  <i className="fas fa-arrow-right"></i> 오른쪽
                </button>
                <button
                  className="btn btn-outline-warning"
                  onClick={() => testPitchChart.resetView()}
                  title="전체 보기"
                >
                  <i className="fas fa-expand-arrows-alt"></i> 전체보기
                </button>
              </div>
            </div>
            <div className="col-md-4 text-end">
              <small className="text-muted">
                <i className="fas fa-mouse-pointer me-1"></i>
                차트를 클릭/드래그하여 상호작용 가능
              </small>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UploadedFileTestSection;