import React, { useRef, useCallback, useEffect } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  LineController,
  Title,
  Tooltip,
  Legend,
  ChartOptions,
  ChartData
} from 'chart.js';
import annotationPlugin from 'chartjs-plugin-annotation';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  LineController,
  Title,
  Tooltip,
  Legend,
  annotationPlugin
);

interface PitchData {
  time: number;
  frequency: number;
  type: 'reference' | 'live';
}

interface SyllableData {
  label: string;
  start: number;
  end: number;
  frequency?: number;
  semitone?: number;
}

export const usePitchChart = (canvasRef: React.RefObject<HTMLCanvasElement | null>) => {
  const chartRef = useRef<ChartJS | null>(null);
  const pitchDataRef = useRef<PitchData[]>([]);
  const startTimeRef = useRef<number>(0);

  const initChart = useCallback(() => {
    if (!canvasRef || !canvasRef.current) {
      console.warn('⚠️ Canvas ref not available');
      return;
    }

    const ctx = canvasRef.current.getContext('2d');
    if (!ctx) {
      console.warn('⚠️ Canvas context not available');
      return;
    }

    // Destroy existing chart
    if (chartRef.current) {
      chartRef.current.destroy();
    }

    const data: ChartData<'line'> = {
      labels: [],
      datasets: [
        {
          label: '참조 음성',
          data: [],
          borderColor: 'rgb(255, 159, 64)',
          backgroundColor: 'rgb(255, 159, 64)',
          showLine: false,  // 🎯 연결선 제거 (음절별 포인트만 표시)
          pointRadius: 8,   // 🎯 포인트 크기 증가
          pointHoverRadius: 12,
          borderWidth: 0,   // 🎯 테두리 제거
          tension: 0
        },
        {
          label: '실시간 음성',
          data: [],
          borderColor: 'rgb(40, 167, 69)',  // 🟢 초록색
          backgroundColor: 'rgba(40, 167, 69, 0.2)',
          tension: 0,  // 직선 연결
          pointRadius: 1,
          borderWidth: 3,
          stepped: true  // 가로선 스타일
        }
      ]
    };

    const options: ChartOptions<'line'> = {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          type: 'linear',
          title: {
            display: true,
            text: '시간 (초)'
          },
          min: 0,
          max: 10
        },
        y: {
          title: {
            display: true,
            text: 'Semitone (세미톤)'
          },
          min: -10,  // 🎯 오리지널과 유사한 범위로 조정
          max: 15
        }
      },
      plugins: {
        legend: {
          display: true,
          position: 'top'
        },
        tooltip: {
          mode: 'index',
          intersect: false,
          callbacks: {
            label: function(context) {
              return `${context.dataset.label}: ${context.parsed.y.toFixed(1)} semitone`;
            }
          }
        },
        annotation: {
          annotations: {}
        }
      },
      interaction: {
        mode: 'nearest',
        axis: 'x',
        intersect: false
      },
      animation: {
        duration: 0
      }
    };

    chartRef.current = new ChartJS(ctx, {
      type: 'line',
      data,
      options
    });
  }, [canvasRef]);

  // 🎯 주파수를 semitone으로 변환하는 함수 (기존 완성본과 동일한 공식)
  const frequencyToSemitone = (frequency: number, baseFrequency: number = 200): number => {
    if (frequency <= 0 || baseFrequency <= 0) return 0;
    return 12 * Math.log2(frequency / baseFrequency);
  };

  const addPitchData = useCallback((frequency: number, timestamp: number, type: 'reference' | 'live' = 'live') => {
    if (!chartRef.current) return;

    let relativeTime: number;
    
    if (type === 'reference') {
      // 🎯 참조 데이터는 이미 초 단위이므로 그대로 사용
      relativeTime = timestamp;
    } else {
      // 🎯 실시간 데이터는 밀리초 단위이므로 초로 변환
      if (startTimeRef.current === 0) {
        startTimeRef.current = timestamp;
      }
      relativeTime = (timestamp - startTimeRef.current) / 1000;
    }
    
    const newData: PitchData = {
      time: relativeTime,
      frequency,
      type
    };

    pitchDataRef.current.push(newData);

    // Update chart data
    const chart = chartRef.current;
    const datasetIndex = type === 'reference' ? 0 : 1;
    
    // 🎯 주파수를 semitone으로 변환해서 차트에 표시
    const semitoneValue = frequencyToSemitone(frequency);
    
    chart.data.datasets[datasetIndex].data.push({
      x: relativeTime,
      y: semitoneValue  // 🎯 semitone 값으로 변경
    });

    // Update time axis to follow the data
    if (chart.options.scales?.x) {
      chart.options.scales.x.max = Math.max(10, relativeTime + 2);
    }

    chart.update('none'); // Update without animation for real-time performance
  }, []);

  const clearChart = useCallback(() => {
    if (!chartRef.current) return;

    chartRef.current.data.datasets.forEach(dataset => {
      dataset.data = [];
    });
    
    pitchDataRef.current = [];
    startTimeRef.current = 0;

    if (chartRef.current.options.scales?.x) {
      chartRef.current.options.scales.x.max = 10;
    }

    chartRef.current.update();
  }, []);

  const loadReferenceData = useCallback(async (fileId: string) => {
    try {
      // 🎯 Load syllable-only pitch data (오리지널과 동일한 음절별 대표값)
      const [pitchResponse, syllableResponse] = await Promise.all([
        fetch(`/api/reference_files/${fileId}/pitch?syllable_only=true`),
        fetch(`/api/reference_files/${fileId}/syllables`)
      ]);
      
      const pitchData = await pitchResponse.json();
      let syllableData: SyllableData[] = [];
      
      try {
        syllableData = await syllableResponse.json();
      } catch (e) {
        console.log('📝 No syllable data available for this file');
      }
      
      if (pitchData && pitchData.length > 0) {
        // Clear existing reference data
        if (chartRef.current) {
          chartRef.current.data.datasets[0].data = [];
          // 🧹 Clear existing annotations
          if (chartRef.current.options.plugins?.annotation) {
            chartRef.current.options.plugins.annotation.annotations = {};
          }
        }
        
        let maxTime = 0;
        
        // Add reference data points  
        pitchData.forEach((point: {time: number, frequency: number}) => {
          // 🎯 백엔드에서 이미 초 단위로 온 데이터를 그대로 사용 (1000 곱하지 않음)
          addPitchData(point.frequency, point.time, 'reference');
          maxTime = Math.max(maxTime, point.time);
        });
        
        console.log(`🎯 Loaded ${pitchData.length} reference pitch points, maxTime: ${maxTime}s`);
        
        // 🎯 참조 데이터 길이에 맞게 x축 범위 조정
        if (chartRef.current?.options?.scales?.x && maxTime > 0) {
          chartRef.current.options.scales.x.min = 0;
          chartRef.current.options.scales.x.max = Math.max(maxTime + 0.5, 3); // 여유 0.5초, 최소 3초
          console.log(`🎯 X-axis adjusted: 0 - ${chartRef.current.options.scales.x.max} seconds`);
          chartRef.current.update('none');
        }
        
        // 🎯 Add syllable annotations to chart
        if (syllableData && syllableData.length > 0) {
          addSyllableAnnotations(syllableData);
        }
      }
    } catch (error) {
      console.error('Failed to load reference data:', error);
    }
  }, [addPitchData]);

  // 🎯 핵심 기능: 음절 구간 표시 (오리지널과 동일한 로직)
  const addSyllableAnnotations = useCallback((syllables: SyllableData[]) => {
    if (!chartRef.current || !syllables || syllables.length === 0) {
      console.log("🎯 addSyllableAnnotations: syllables가 비어있습니다");
      return;
    }

    const chart = chartRef.current;
    
    // 🧹 annotation plugin 존재 확인 및 초기화
    if (!chart.options.plugins?.annotation) {
      chart.options.plugins = { ...chart.options.plugins, annotation: { annotations: {} } };
    }
    
    chart.options.plugins.annotation.annotations = {};
    console.log("🧹 음절 표시 초기화 완료");
    
    console.log('🎯 Adding annotations for', syllables.length, 'syllables:');
    console.log('🎯 Sample syllables:', syllables.slice(0, 3));
    
    // Position labels at top of chart (inside chart area) 
    const yScale = chart.options.scales?.y;
    const chartMax = (yScale?.max as number) || 500;
    const chartMin = (yScale?.min as number) || 50;
    const labelY = chartMax - (chartMax - chartMin) * 0.05; // 5% from top
    
    console.log("🎯 Chart Y 범위:", chartMin, "~", chartMax, "labelY:", labelY);
    
    syllables.forEach((syl, index) => {
      const sylStart = syl.start;
      const sylEnd = syl.end;
      const sylLabel = syl.label;
      
      console.log(`🎯 음절 ${index}: ${sylLabel} (${sylStart.toFixed(3)}s - ${sylEnd.toFixed(3)}s)`);
      
      // 🔥 첫 번째 음절 시작선
      if (index === 0) {
        chart.options.plugins.annotation.annotations[`start_${index}`] = {
          type: 'line',
          xMin: sylStart,
          xMax: sylStart,
          borderColor: 'rgba(255, 99, 132, 0.8)',
          borderWidth: 3,
          borderDash: [6, 3]
        };
      }
      
      // 🔥 음절 끝선 (다음 음절 시작선)
      chart.options.plugins.annotation.annotations[`end_${index}`] = {
        type: 'line',
        xMin: sylEnd,
        xMax: sylEnd,
        borderColor: 'rgba(255, 99, 132, 0.8)',
        borderWidth: 3,
        borderDash: [6, 3]
      };
      
      // 🔥 보라색 음절 라벨 박스
      const midTime = (sylStart + sylEnd) / 2;
      chart.options.plugins.annotation.annotations[`label_${index}`] = {
        type: 'label',
        xValue: midTime,
        yValue: labelY,
        content: sylLabel,
        backgroundColor: 'rgba(138, 43, 226, 0.9)',  // 보라색 배경
        borderColor: 'rgba(138, 43, 226, 1)',
        borderWidth: 2,
        borderRadius: 6,
        font: {
          size: 14,
          family: 'Noto Sans KR, -apple-system, sans-serif',
          weight: 'bold'
        },
        color: 'white',
        padding: {
          x: 8,
          y: 4
        }
      };
    });
    
    // 🔥 강제 차트 업데이트로 annotation 표시
    try {
      chart.update('none');
      console.log("🎯 Syllable annotations added and chart updated!");
      console.log("🎯 현재 annotations 수:", Object.keys(chart.options.plugins.annotation.annotations).length);
    } catch (error) {
      console.error("🎯 Chart update 실패:", error);
    }
  }, []);

  const resetForNewRecording = useCallback(() => {
    if (!chartRef.current) return;

    // Clear only live data, keep reference data
    chartRef.current.data.datasets[1].data = [];
    startTimeRef.current = 0;
    
    // Filter pitch data to keep only reference data
    pitchDataRef.current = pitchDataRef.current.filter(data => data.type === 'reference');
    
    chartRef.current.update();
  }, []);

  // 🎯 Y축 피치 조정 (오리지널 기능)
  const adjustPitch = useCallback((direction: 'up' | 'down') => {
    if (!chartRef.current) return;

    const yScale = chartRef.current.options.scales?.y;
    if (!yScale || typeof yScale.min !== 'number' || typeof yScale.max !== 'number') return;

    const range = yScale.max - yScale.min;
    const step = range * 0.1; // 10% 이동

    if (direction === 'up') {
      yScale.min += step;
      yScale.max += step;
    } else {
      yScale.min -= step;
      yScale.max -= step;
    }

    chartRef.current.update('none');
    console.log(`🎯 피치 ${direction === 'up' ? '위로' : '아래로'} 조정:`, {
      min: yScale.min.toFixed(1),
      max: yScale.max.toFixed(1)
    });
  }, []);

  // 🎯 피치 위치 초기화
  const resetPitch = useCallback(() => {
    if (!chartRef.current) return;

    const yScale = chartRef.current.options.scales?.y;
    if (!yScale) return;

    yScale.min = 50;
    yScale.max = 500;

    chartRef.current.update('none');
    console.log('🔄 피치 위치 초기화: 50-500Hz');
  }, []);

  // 🎯 차트 확대/축소
  const zoomIn = useCallback(() => {
    if (!chartRef.current) return;

    const xScale = chartRef.current.options.scales?.x;
    if (!xScale || typeof xScale.min !== 'number' || typeof xScale.max !== 'number') return;

    const center = (xScale.max + xScale.min) / 2;
    const range = xScale.max - xScale.min;
    const newRange = range * 0.8; // 20% 확대

    xScale.min = center - newRange / 2;
    xScale.max = center + newRange / 2;

    chartRef.current.update('none');
    console.log('🔍 확대:', { min: xScale.min.toFixed(2), max: xScale.max.toFixed(2) });
  }, []);

  const zoomOut = useCallback(() => {
    if (!chartRef.current) return;

    const xScale = chartRef.current.options.scales?.x;
    if (!xScale || typeof xScale.min !== 'number' || typeof xScale.max !== 'number') return;

    const center = (xScale.max + xScale.min) / 2;
    const range = xScale.max - xScale.min;
    const newRange = range * 1.25; // 25% 축소

    xScale.min = Math.max(0, center - newRange / 2);
    xScale.max = center + newRange / 2;

    chartRef.current.update('none');
    console.log('🔍 축소:', { min: xScale.min.toFixed(2), max: xScale.max.toFixed(2) });
  }, []);

  // 🎯 좌우 스크롤
  const scrollLeft = useCallback(() => {
    if (!chartRef.current) return;

    const xScale = chartRef.current.options.scales?.x;
    if (!xScale || typeof xScale.min !== 'number' || typeof xScale.max !== 'number') return;

    const range = xScale.max - xScale.min;
    const step = range * 0.1; // 10% 이동

    if (xScale.min > step) {
      xScale.min -= step;
      xScale.max -= step;
      
      chartRef.current.update('none');
      console.log('⬅️ 왼쪽 스크롤:', { min: xScale.min.toFixed(2), max: xScale.max.toFixed(2) });
    }
  }, []);

  const scrollRight = useCallback(() => {
    if (!chartRef.current) return;

    const xScale = chartRef.current.options.scales?.x;
    if (!xScale || typeof xScale.min !== 'number' || typeof xScale.max !== 'number') return;

    const range = xScale.max - xScale.min;
    const step = range * 0.1; // 10% 이동

    xScale.min += step;
    xScale.max += step;

    chartRef.current.update('none');
    console.log('➡️ 오른쪽 스크롤:', { min: xScale.min.toFixed(2), max: xScale.max.toFixed(2) });
  }, []);

  // 🎯 전체 보기 리셋
  const resetView = useCallback(() => {
    if (!chartRef.current) return;

    const xScale = chartRef.current.options.scales?.x;
    if (!xScale) return;

    xScale.min = 0;
    xScale.max = 10;

    chartRef.current.update('none');
    console.log('🔄 전체 보기 리셋: 0-10초');
  }, []);

  useEffect(() => {
    initChart();
    
    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
      }
    };
  }, [initChart]);

  // 🟢 실시간 피치 가로바 업데이트 (녹음 중)
  const updateRealtimePitchLine = useCallback((frequency: number) => {
    if (!chartRef.current) return;
    
    const chart = chartRef.current;
    const semitoneValue = frequencyToSemitone(frequency);
    
    // annotation plugin 확인
    if (!chart.options.plugins?.annotation) {
      chart.options.plugins = { ...chart.options.plugins, annotation: { annotations: {} } };
    }
    
    // 실시간 가로바 annotation 업데이트
    chart.options.plugins.annotation.annotations['realtimePitchLine'] = {
      type: 'line',
      yMin: semitoneValue,
      yMax: semitoneValue,
      borderColor: 'rgb(40, 167, 69)',  // 🟢 초록색
      borderWidth: 3,
      borderDash: [],  // 실선
      label: {
        display: false
      }
    };
    
    chart.update('none');  // 애니메이션 없이 즉시 업데이트
  }, []);

  // 🟢 실시간 피치 가로바 숨김
  const hideRealtimePitchLine = useCallback(() => {
    if (!chartRef.current) return;
    
    const chart = chartRef.current;
    if (chart.options.plugins?.annotation?.annotations) {
      delete chart.options.plugins.annotation.annotations['realtimePitchLine'];
      chart.update('none');
    }
  }, []);

  return {
    addPitchData,
    clearChart,
    loadReferenceData,
    resetForNewRecording,
    pitchData: pitchDataRef.current,
    // 🎯 차트 인스턴스 노출 (ChartControls에서 사용)
    chartInstance: chartRef.current,
    // 🎯 새로 추가된 컨트롤 기능들
    adjustPitch,
    resetPitch,
    zoomIn,
    zoomOut,
    scrollLeft,
    scrollRight,
    resetView,
    addSyllableAnnotations,  // 🎯 핵심 함수 export
    updateRealtimePitchLine,  // 🟢 실시간 가로바 업데이트
    hideRealtimePitchLine     // 🟢 실시간 가로바 숨김
  };
};