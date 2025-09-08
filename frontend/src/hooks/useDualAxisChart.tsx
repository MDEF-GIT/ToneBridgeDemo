import React, { useRef, useCallback, useEffect } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ChartConfiguration
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

interface DualAxisChartData {
  time: number;
  frequency: number;  // Hz
  convertedValue: number; // Semitone/Q-tone
}

export const useDualAxisChart = (
  canvasRef: React.RefObject<HTMLCanvasElement>,
  API_BASE: string
) => {
  const chartRef = useRef<ChartJS | null>(null);
  const chartDataRef = useRef<DualAxisChartData[]>([]);
  const [yAxisUnit, setYAxisUnitInternal] = React.useState<'semitone' | 'qtone'>('semitone');

  // 🎯 외부에서 Y축 단위를 설정하는 함수
  const setYAxisUnit = useCallback((newUnit: 'semitone' | 'qtone') => {
    setYAxisUnitInternal(newUnit);
  }, []);

  // 🎯 주파수 → 세미톤/큐톤 변환 함수
  const convertFrequencyToUnit = useCallback((frequency: number): number => {
    if (yAxisUnit === 'semitone') {
      // 세미톤: 12 * log2(f/150) (남성 기준), 12 * log2(f/200) (여성 기준)
      const baseFreq = 150; // 기본적으로 남성 기준
      return 12 * Math.log2(frequency / baseFreq);
    } else {
      // Q-톤: 5 * log2(f/130)
      return 5 * Math.log2(frequency / 130);
    }
  }, [yAxisUnit]);

  // 🎯 차트 초기화
  const initChart = useCallback(() => {
    if (!canvasRef.current) return;

    if (chartRef.current) {
      chartRef.current.destroy();
    }

    const ctx = canvasRef.current.getContext('2d');
    if (!ctx) return;

    const config: ChartConfiguration = {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label: '주파수 (Hz)',
            data: [],
            borderColor: 'rgb(255, 99, 132)',
            backgroundColor: 'rgba(255, 99, 132, 0.2)',
            tension: 0.1,
            pointRadius: 2,
            pointHoverRadius: 4,
            yAxisID: 'y-frequency'
          },
          {
            label: '세미톤/큐톤',
            data: [],
            borderColor: 'rgb(54, 162, 235)',
            backgroundColor: 'rgba(54, 162, 235, 0.2)',
            tension: 0.1,
            pointRadius: 2,
            pointHoverRadius: 4,
            yAxisID: 'y-converted'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          intersect: false,
          mode: 'index'
        },
        plugins: {
          title: {
            display: true,
            text: '듀얼 Y축 비교 차트 - 주파수 vs 세미톤/큐톤',
            font: {
              size: 16,
              weight: 'bold'
            }
          },
          tooltip: {
            callbacks: {
              title: (tooltipItems) => {
                const dataIndex = tooltipItems[0].dataIndex;
                const timeValue = chartDataRef.current[dataIndex]?.time || 0;
                return `시간: ${timeValue.toFixed(2)}초`;
              },
              label: (tooltipItem) => {
                const dataIndex = tooltipItem.dataIndex;
                const data = chartDataRef.current[dataIndex];
                if (!data) return '';

                if (tooltipItem.datasetIndex === 0) {
                  return `주파수: ${data.frequency.toFixed(1)} Hz`;
                } else {
                  const unit = yAxisUnit === 'semitone' ? 'st' : 'Q';
                  return `${yAxisUnit === 'semitone' ? '세미톤' : '큐톤'}: ${data.convertedValue.toFixed(1)} ${unit}`;
                }
              }
            }
          },
          legend: {
            display: true,
            position: 'top'
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
            min: 0,
            max: 10
          },
          'y-frequency': {
            type: 'linear',
            position: 'left',
            title: {
              display: true,
              text: '주파수 (Hz)',
              color: 'rgb(255, 99, 132)'
            },
            ticks: {
              color: 'rgb(255, 99, 132)'
            },
            grid: {
              drawOnChartArea: false
            }
            // min, max 제거 - 데이터에 맞게 동적 설정
          },
          'y-converted': {
            type: 'linear',
            position: 'right',
            title: {
              display: true,
              text: '세미톤/큐톤',
              color: 'rgb(54, 162, 235)'
            },
            ticks: {
              color: 'rgb(54, 162, 235)'
            },
            grid: {
              drawOnChartArea: true
            }
            // min, max 제거 - 데이터에 맞게 동적 설정
          }
        }
      }
    };

    chartRef.current = new ChartJS(ctx, config);
    console.log('🎯 듀얼 Y축 차트 초기화 완료');
  }, [canvasRef]);

  // 🎯 데이터 추가 함수
  const addDualAxisData = useCallback((frequency: number, timestamp: number, type: 'reference' | 'live' = 'reference') => {
    if (!chartRef.current) return;

    const convertedValue = convertFrequencyToUnit(frequency);
    const chartData: DualAxisChartData = {
      time: timestamp,
      frequency,
      convertedValue
    };

    chartDataRef.current.push(chartData);

    // 차트 데이터 업데이트
    chartRef.current.data.labels!.push(timestamp.toFixed(2));
    chartRef.current.data.datasets[0].data.push({ x: timestamp, y: frequency });
    chartRef.current.data.datasets[1].data.push({ x: timestamp, y: convertedValue });

    // 🎯 Y축 범위 조정은 충분한 데이터가 쌓인 후에만 수행
    if (chartDataRef.current.length >= 5) {
      updateYAxisRanges();
    }

    // 색상 구분 (참조 vs 실시간) - type assertion으로 해결
    if (type === 'live') {
      (chartRef.current.data.datasets[0] as any).pointBackgroundColor = (chartRef.current.data.datasets[0] as any).pointBackgroundColor || [];
      (chartRef.current.data.datasets[1] as any).pointBackgroundColor = (chartRef.current.data.datasets[1] as any).pointBackgroundColor || [];
      
      ((chartRef.current.data.datasets[0] as any).pointBackgroundColor as string[]).push('rgb(76, 175, 80)'); // 녹색
      ((chartRef.current.data.datasets[1] as any).pointBackgroundColor as string[]).push('rgb(76, 175, 80)'); // 녹색
    }

    chartRef.current.update('none');
    console.log(`📊 듀얼축 데이터 추가: ${frequency.toFixed(1)}Hz → ${convertedValue.toFixed(1)}`);
  }, [convertFrequencyToUnit]);

  // 🎯 Y축 범위 자동 조정 함수
  const updateYAxisRanges = useCallback(() => {
    if (!chartRef.current || chartDataRef.current.length === 0) return;

    const scales = chartRef.current.options.scales;
    if (!scales) return;

    // 주파수 축(왼쪽) 범위 조정
    const frequencyScale = scales['y-frequency'] as any;
    if (frequencyScale) {
      const allFrequencies = chartDataRef.current.map(d => d.frequency).filter(f => f > 0);
      if (allFrequencies.length > 0) {
        const minFreq = Math.min(...allFrequencies);
        const maxFreq = Math.max(...allFrequencies);
        const freqMargin = Math.max(Math.abs(maxFreq - minFreq) * 0.1, 20); // 최소 20Hz 마진
        
        frequencyScale.min = Math.max(50, Math.floor(minFreq - freqMargin)); // 최소 50Hz
        frequencyScale.max = Math.ceil(maxFreq + freqMargin);
        console.log(`📊 듀얼차트 주파수축 범위: ${frequencyScale.min}Hz ~ ${frequencyScale.max}Hz`);
      }
    }
    
    // 변환된 값(오른쪽 Y축) 범위 조정
    const convertedScale = scales['y-converted'] as any;
    if (convertedScale) {
      const allConvertedValues = chartDataRef.current.map(d => d.convertedValue);
      if (allConvertedValues.length > 0) {
        const minConverted = Math.min(...allConvertedValues);
        const maxConverted = Math.max(...allConvertedValues);
        const margin = Math.max(Math.abs(maxConverted - minConverted) * 0.1, 2); // 최소 2 마진
        
        convertedScale.min = Math.floor(minConverted - margin);
        convertedScale.max = Math.ceil(maxConverted + margin);
        console.log(`📊 듀얼차트 변환값축 범위: ${convertedScale.min} ~ ${convertedScale.max}`);
      }
    }
  }, []);

  // 🎯 차트 클리어
  const clearChart = useCallback(() => {
    if (!chartRef.current) return;

    chartDataRef.current = [];
    chartRef.current.data.labels = [];
    chartRef.current.data.datasets[0].data = [];
    chartRef.current.data.datasets[1].data = [];
    (chartRef.current.data.datasets[0] as any).pointBackgroundColor = [];
    (chartRef.current.data.datasets[1] as any).pointBackgroundColor = [];
    
    // 🎯 Y축 범위 초기화 - 올바른 기본값으로 설정
    if (chartRef.current.options.scales) {
      const frequencyScale = chartRef.current.options.scales['y-frequency'] as any;
      const convertedScale = chartRef.current.options.scales['y-converted'] as any;
      
      if (frequencyScale) {
        frequencyScale.min = 100;
        frequencyScale.max = 300;
      }
      if (convertedScale) {
        convertedScale.min = -10;
        convertedScale.max = 15;
      }
      console.log('🎯 듀얼차트 Y축 범위 기본값으로 초기화');
    }
    
    chartRef.current.update();
    console.log('🧹 듀얼 Y축 차트 클리어');
  }, []);

  // 🎯 Y축 단위 변경 시 재계산
  const updateAxisUnit = useCallback(() => {
    if (!chartRef.current) return;

    // 기존 데이터를 새로운 단위로 재계산
    chartDataRef.current = chartDataRef.current.map(data => ({
      ...data,
      convertedValue: convertFrequencyToUnit(data.frequency)
    }));

    // 차트 데이터 업데이트 - 주파수와 변환값 모두 업데이트
    chartRef.current.data.datasets[0].data = chartDataRef.current.map(data => ({ x: data.time, y: data.frequency }));
    chartRef.current.data.datasets[1].data = chartDataRef.current.map(data => ({ x: data.time, y: data.convertedValue }));
    chartRef.current.data.datasets[1].label = yAxisUnit === 'semitone' ? '세미톤 (st)' : '큐톤 (Q)';
    
    // Y축 제목 업데이트 및 범위 재계산
    if (chartRef.current.options.scales && chartRef.current.options.scales['y-converted']) {
      const convertedScale = chartRef.current.options.scales['y-converted'] as any;
      convertedScale.title.text = yAxisUnit === 'semitone' ? '세미톤 (st)' : '큐톤 (Q)';
      
      // 🎯 기존 데이터에 맞게 Y축 범위 재계산
      if (chartDataRef.current.length > 0) {
        const allConvertedValues = chartDataRef.current.map(d => d.convertedValue);
        const minConverted = Math.min(...allConvertedValues);
        const maxConverted = Math.max(...allConvertedValues);
        const margin = Math.abs(maxConverted - minConverted) * 0.1 || 2;
        
        convertedScale.min = Math.floor(minConverted - margin);
        convertedScale.max = Math.ceil(maxConverted + margin);
        console.log(`🎯 단위 변경 후 변환값축 범위: ${convertedScale.min} ~ ${convertedScale.max}`);
      } else {
        // 데이터가 없으면 범위 제거 (자동 설정)
        delete convertedScale.min;
        delete convertedScale.max;
      }
    }

    // 차트 제목 업데이트
    if (chartRef.current.options.plugins?.title) {
      chartRef.current.options.plugins.title.text = `듀얼 Y축 비교 차트 - 주파수 vs ${yAxisUnit === 'semitone' ? '세미톤' : '큐톤'}`;
    }

    chartRef.current.update();
    console.log(`🔄 듀얼축 차트 단위 변경: ${yAxisUnit}`);
  }, [convertFrequencyToUnit, yAxisUnit]);

  // 🎯 초기화 및 Y축 단위 변경 감지
  useEffect(() => {
    initChart();
    
    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
      }
    };
  }, [initChart]);

  useEffect(() => {
    updateAxisUnit();
  }, [updateAxisUnit, yAxisUnit]);

  return {
    addDualAxisData,
    clearChart,
    updateYAxisRanges,
    chartData: chartDataRef.current,
    setYAxisUnit,
    yAxisUnit
  };
};