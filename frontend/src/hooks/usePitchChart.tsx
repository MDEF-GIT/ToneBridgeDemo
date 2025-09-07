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
          borderColor: 'rgb(54, 162, 235)',
          backgroundColor: 'rgba(54, 162, 235, 0.2)',
          tension: 0.4,
          pointRadius: 0,
          borderWidth: 2
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
            text: '주파수 (Hz)'
          },
          min: 50,
          max: 500
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
              return `${context.dataset.label}: ${context.parsed.y.toFixed(1)} Hz`;
            }
          }
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

  const addPitchData = useCallback((frequency: number, timestamp: number, type: 'reference' | 'live' = 'live') => {
    if (!chartRef.current) return;

    if (startTimeRef.current === 0) {
      startTimeRef.current = timestamp;
    }

    const relativeTime = (timestamp - startTimeRef.current) / 1000; // Convert to seconds
    
    const newData: PitchData = {
      time: relativeTime,
      frequency,
      type
    };

    pitchDataRef.current.push(newData);

    // Update chart data
    const chart = chartRef.current;
    const datasetIndex = type === 'reference' ? 0 : 1;
    
    chart.data.datasets[datasetIndex].data.push({
      x: relativeTime,
      y: frequency
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
      // Load reference pitch data from backend
      const response = await fetch(`/api/reference_files/${fileId}/pitch`);
      const pitchData = await response.json();
      
      if (pitchData && pitchData.length > 0) {
        // Clear existing reference data
        if (chartRef.current) {
          chartRef.current.data.datasets[0].data = [];
        }
        
        // Add reference data points  
        pitchData.forEach((point: {time: number, frequency: number}) => {
          addPitchData(point.frequency, point.time * 1000, 'reference');
        });
      }
    } catch (error) {
      console.error('Failed to load reference pitch data:', error);
    }
  }, [addPitchData]);

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
    resetView
  };
};