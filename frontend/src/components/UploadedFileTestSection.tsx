import React, { useState, useEffect, useRef } from 'react';
import Chart from 'chart.js/auto';

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
  const chartRef = useRef<Chart | null>(null);

  // 컴포넌트 마운트 시 차트 초기화
  useEffect(() => {
    initChart();
    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
      }
    };
  }, []);

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

  // 🎯 차트 초기화 함수
  const initChart = () => {
    const canvas = chartCanvasRef.current;
    if (!canvas) return;

    if (chartRef.current) {
      chartRef.current.destroy();
    }

    chartRef.current = new Chart(canvas, {
      type: 'scatter',
      data: {
        datasets: [{
          label: '음절별 피치',
          data: [],
          backgroundColor: 'rgba(54, 162, 235, 0.8)',
          borderColor: 'rgba(54, 162, 235, 1)',
          pointRadius: 8,
          pointHoverRadius: 12,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          intersect: false,
        },
        plugins: {
          title: {
            display: true,
            text: '음절별 피치 분석 - 클릭하여 재생',
            font: { size: 16 }
          },
          legend: {
            display: false
          },
          tooltip: {
            callbacks: {
              title: () => '',
              label: (context: any) => {
                const point = syllablePoints[context.dataIndex];
                if (point) {
                  return `음절: ${point.syllable} | 피치: ${point.frequency.toFixed(1)}Hz | 시간: ${point.time.toFixed(2)}s`;
                }
                return '';
              }
            }
          }
        },
        scales: {
          x: {
            type: 'linear',
            position: 'bottom',
            title: {
              display: true,
              text: '시간 (초)'
            },
            grid: {
              color: 'rgba(0, 0, 0, 0.1)'
            }
          },
          y: {
            title: {
              display: true,
              text: '주파수 (Hz)'
            },
            grid: {
              color: 'rgba(0, 0, 0, 0.1)'
            }
          }
        },
        onClick: (event, elements) => {
          if (elements.length > 0) {
            const dataIndex = elements[0].index;
            handleSyllableClick(dataIndex);
          }
        }
      }
    });

    console.log('📊 음절 분절 차트 초기화 완료');
  };

  // 🎯 음절 클릭 처리
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
      if (chartRef.current) {
        chartRef.current.data.datasets[0].data = [];
        chartRef.current.update();
      }
      return;
    }

    try {
      setLoading(true);
      setSelectedFileId(fileId);
      setError('');

      console.log(`🎯 업로드 파일 분석 시작: ${fileId}`);

      // 1. 음절별 대표 피치 로드 (점 표시용)
      const syllablePitchResponse = await fetch(`/api/uploaded_files/${fileId}/pitch?syllable_only=true`);
      if (!syllablePitchResponse.ok) throw new Error('음절 피치 데이터 조회 실패');
      const syllablePitch = await syllablePitchResponse.json();

      // 2. 음절 구간 정보 로드
      const syllablesResponse = await fetch(`/api/uploaded_files/${fileId}/syllables`);
      let syllables = [];
      if (syllablesResponse.ok) {
        syllables = await syllablesResponse.json();
      }

      // 3. 음절 포인트 데이터 구성
      const points: SyllablePoint[] = syllablePitch.map((sp: any, index: number) => ({
        syllable: sp.syllable,
        start: sp.start,
        end: sp.end,
        frequency: sp.frequency,
        time: (sp.start + sp.end) / 2 // 음절의 중간 시점
      }));

      setSyllablePoints(points);

      // 4. 차트에 음절 포인트 표시
      if (chartRef.current && points.length > 0) {
        const chartData = points.map(point => ({
          x: point.time,
          y: point.frequency
        }));

        chartRef.current.data.datasets[0].data = chartData;
        
        // Y축 범위 자동 조정
        const frequencies = points.map(p => p.frequency);
        const minFreq = Math.min(...frequencies);
        const maxFreq = Math.max(...frequencies);
        const margin = (maxFreq - minFreq) * 0.2;
        
        chartRef.current.options.scales!.y!.min = Math.max(50, minFreq - margin);
        chartRef.current.options.scales!.y!.max = maxFreq + margin;
        
        // X축 범위 자동 조정
        const times = points.map(p => p.time);
        const minTime = Math.min(...times);
        const maxTime = Math.max(...times);
        const timeMargin = (maxTime - minTime) * 0.1;
        
        chartRef.current.options.scales!.x!.min = Math.max(0, minTime - timeMargin);
        chartRef.current.options.scales!.x!.max = maxTime + timeMargin;
        
        chartRef.current.update();
        
        console.log(`📊 음절 포인트 ${points.length}개 차트에 표시 완료`);
      }

      console.log(`✅ 업로드 파일 분석 완료: ${points.length}개 음절`);
      
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

      {/* 음절 정보 및 컨트롤 */}
      {selectedFileId && syllablePoints.length > 0 && (
        <div className="mt-3">
          <div className="row">
            <div className="col-md-8">
              <h6 className="mb-2">
                <i className="fas fa-list me-2"></i>음절별 분석 결과
              </h6>
              <div className="row g-2">
                {syllablePoints.map((point, index) => (
                  <div key={index} className="col-auto">
                    <button
                      className={`btn btn-sm ${
                        currentPlayingSyllable === index 
                          ? 'btn-primary' 
                          : 'btn-outline-primary'
                      }`}
                      onClick={() => handleSyllableClick(index)}
                      title={`${point.syllable}: ${point.frequency.toFixed(1)}Hz`}
                    >
                      <strong>{point.syllable}</strong>
                      <br />
                      <small>{point.frequency.toFixed(1)}Hz</small>
                    </button>
                  </div>
                ))}
              </div>
            </div>
            <div className="col-md-4 text-end">
              <small className="text-muted">
                <i className="fas fa-mouse-pointer me-1"></i>
                음절을 클릭하여 해당 구간 재생
              </small>
              <br />
              <small className="text-muted">
                <i className="fas fa-chart-line me-1"></i>
                차트의 점을 클릭해도 재생됩니다
              </small>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UploadedFileTestSection;