import React, { useState, useEffect, useRef } from 'react';
import { usePitchChart } from '../hooks/usePitchChart';

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
  const testPitchChart = usePitchChart(chartCanvasRef);

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
      testPitchChart.clearChart();
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
      testPitchChart.clearChart();
      
      // 5. Y축 범위 계산 (최소/최대값 기반 여유 공간 추가)
      if (pitchData.length > 0) {
        const frequencies = pitchData.map((p: any) => p.frequency);
        const minFreq = Math.min(...frequencies);
        const maxFreq = Math.max(...frequencies);
        const margin = (maxFreq - minFreq) * 0.1; // 10% 여유 공간
        const yMin = Math.max(50, minFreq - margin); // 최소 50Hz
        const yMax = maxFreq + margin;
        
        console.log(`📊 Y축 자동 조정: ${yMin.toFixed(1)}Hz ~ ${yMax.toFixed(1)}Hz (데이터: ${minFreq.toFixed(1)}~${maxFreq.toFixed(1)})`);
        
        // 차트 Y축 범위 설정
        testPitchChart.setYAxisRange(yMin, yMax);
      }
      
      // 6. 피치 데이터 추가
      pitchData.forEach((point: any) => {
        testPitchChart.addPitchData(point.frequency, point.time, 'reference');
      });
      
      // 7. 음절 annotation 추가
      if (syllables.length > 0 && syllablePitch.length > 0) {
        testPitchChart.addSyllableAnnotations(syllablePitch);
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
            <div className="col-md-8">
              <h6 className="mb-1">
                <i className="fas fa-file-audio me-2"></i>
                선택된 파일: {uploadedFiles.find(f => f.id === selectedFileId)?.display_name}
              </h6>
              <small className="text-muted">
                파일명: {selectedFileId}.wav / {selectedFileId}.TextGrid
              </small>
            </div>
            <div className="col-md-4 text-end">
              <small className="text-muted">
                업로드 시간: {uploadedFiles.find(f => f.id === selectedFileId)?.timestamp}
              </small>
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
                  className="btn btn-outline-secondary"
                  onClick={() => testPitchChart.scrollLeft()}
                  title="왼쪽으로"
                >
                  <i className="fas fa-arrow-left"></i> 왼쪽
                </button>
                <button
                  className="btn btn-outline-secondary"
                  onClick={() => testPitchChart.scrollRight()}
                  title="오른쪽으로"
                >
                  <i className="fas fa-arrow-right"></i> 오른쪽
                </button>
                <button
                  className="btn btn-outline-info"
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