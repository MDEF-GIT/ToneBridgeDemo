import React, { useState, useEffect, useRef } from 'react';
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
    console.log('📊 업로드 파일 테스트: 듀얼축 차트 초기화');
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

  // 파일 선택 시 차트 업데이트
  const handleFileSelect = async (fileId: string) => {
    if (!fileId) {
      setSelectedFileId('');
      setSyllablePoints([]);
      setCurrentPlayingSyllable(-1);
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

      // 2. 음절별 대표 피치 로드 (음절 정보 포함)
      const syllablePitchResponse = await fetch(`/api/uploaded_files/${fileId}/pitch?syllable_only=true`);
      if (!syllablePitchResponse.ok) throw new Error('음절 피치 데이터 조회 실패');
      const syllablePitch = await syllablePitchResponse.json();

      // 3. 음절 구간 정보 로드
      const syllablesResponse = await fetch(`/api/uploaded_files/${fileId}/syllables`);
      let syllables = [];
      if (syllablesResponse.ok) {
        syllables = await syllablesResponse.json();
      }

      // 4. 음절 포인트 데이터 구성
      const points: SyllablePoint[] = syllablePitch.map((sp: any, index: number) => ({
        syllable: sp.syllable,
        start: sp.start,
        end: sp.end,
        frequency: sp.frequency,
        time: (sp.start + sp.end) / 2 // 음절의 중간 시점
      }));

      setSyllablePoints(points);

      // 5. 차트 클리어 후 데이터 추가
      testDualAxisChart.clearChart();
      
      // 6. 전체 피치 데이터를 듀얼축 차트에 추가
      pitchData.forEach((point: any) => {
        testDualAxisChart.addDualAxisData(point.frequency, point.time, 'reference');
      });

      // 7. 음절 annotation 추가
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
                    // 재생 진행 상황 추적
                    const updateProgress = () => {
                      if (audioRef.current && !audioRef.current.paused) {
                        const currentTime = audioRef.current.currentTime;
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
                    setCurrentPlayingSyllable(-1);
                  }}
                  onEnded={() => {
                    console.log('🎵 업로드 파일 재생 완료');
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
      {selectedFileId && syllablePoints.length > 0 && (
        <div className="mt-3">
          <h6 className="mb-3">
            <i className="fas fa-table me-2"></i>분절별 음성 파라메터 분석
          </h6>
          <div className="table-responsive">
            <table className="table table-sm table-bordered table-hover">
              <thead className="table-light">
                <tr>
                  <th style={{width: '8%'}} className="text-center">음절</th>
                  <th style={{width: '15%'}} className="text-center">주파수 (Hz)</th>
                  <th style={{width: '15%'}} className="text-center">
                    {testDualAxisChart.yAxisUnit === 'semitone' ? '세미톤 (st)' : '큐톤 (Q)'}
                  </th>
                  <th style={{width: '20%'}} className="text-center">시간 구간 (초)</th>
                  <th style={{width: '12%'}} className="text-center">지속 시간</th>
                  <th style={{width: '30%'}} className="text-center">분석 결과</th>
                </tr>
              </thead>
              <tbody>
                {syllablePoints.map((point, index) => {
                  const duration = point.end - point.start;
                  const convertedValue = testDualAxisChart.yAxisUnit === 'semitone' 
                    ? 12 * Math.log2(point.frequency / 440) + 69 // A4 = 440Hz = 69 semitones
                    : Math.log2(point.frequency / 440) * 1200; // cents
                  
                  const getFrequencyLevel = (freq: number) => {
                    if (freq < 100) return { level: '낮음', color: 'text-info' };
                    if (freq < 200) return { level: '중간', color: 'text-success' };
                    return { level: '높음', color: 'text-warning' };
                  };
                  
                  const freqLevel = getFrequencyLevel(point.frequency);
                  
                  return (
                    <tr 
                      key={index}
                      className={currentPlayingSyllable === index ? 'table-primary' : ''}
                      style={{ cursor: 'pointer' }}
                      onClick={() => handleSyllableClick(index)}
                      title="클릭하여 해당 구간 재생"
                    >
                      <td className="text-center fw-bold">{point.syllable}</td>
                      <td className="text-center">
                        <span className={freqLevel.color}>
                          {point.frequency.toFixed(1)}
                        </span>
                      </td>
                      <td className="text-center">
                        {convertedValue.toFixed(1)}
                      </td>
                      <td className="text-center">
                        <small>
                          {point.start.toFixed(2)}s - {point.end.toFixed(2)}s
                        </small>
                      </td>
                      <td className="text-center">
                        <small>{duration.toFixed(2)}s</small>
                      </td>
                      <td className="text-center">
                        <small>
                          <span className={`badge ${freqLevel.color.replace('text-', 'bg-')}`}>
                            {freqLevel.level} 주파수
                          </span>
                          <br />
                          <span className="text-muted">
                            {duration < 0.2 ? '빠름' : duration > 0.5 ? '느림' : '보통'}
                          </span>
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