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

export const usePitchChart = (canvasRef: React.RefObject<HTMLCanvasElement | null>, API_BASE: string = '') => {
  const chartRef = useRef<ChartJS | null>(null);
  const pitchDataRef = useRef<PitchData[]>([]);
  const startTimeRef = useRef<number>(0);
  const realtimeLineRef = useRef<number | null>(null); // 🎯 실시간 수직선 위치 추적
  const [yAxisUnit, setYAxisUnitInternal] = React.useState<'semitone' | 'qtone'>('semitone');

  // 🎯 외부에서 Y축 단위를 설정하는 함수
  const setYAxisUnit = useCallback((newUnit: 'semitone' | 'qtone') => {
    console.log(`🎯 usePitchChart: Y축 단위 변경 요청 → ${newUnit}`);
    setYAxisUnitInternal(newUnit);
  }, []);

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
          borderColor: 'rgba(34, 197, 94, 1)',  // 🟢 녹색
          backgroundColor: 'rgba(34, 197, 94, 0.3)',
          showLine: false,
          pointRadius: 12,  // 큰 포인트로 표시
          pointHoverRadius: 15,
          borderWidth: 3,
          pointBorderColor: 'rgba(34, 197, 94, 1)',
          pointBackgroundColor: 'rgba(34, 197, 94, 0.8)'
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
            text: 'Semitone (세미톤)' // 기본값, Y축 단위 변경 시 업데이트됨
          }
          // min, max 제거 - 데이터 로딩 시 동적으로 설정됨
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
              const unit = yAxisUnit === 'qtone' ? 'Q-tone' : 'Semitone';
              return `${context.dataset.label}: ${context.parsed.y.toFixed(1)} ${unit}`;
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
  }, [canvasRef]); // yAxisUnit 의존성 제거하여 차트 재초기화 방지

  // 🎯 주파수를 semitone 또는 Q-tone으로 변환하는 함수
  const frequencyToSemitone = (frequency: number, baseFrequency: number = 200): number => {
    if (frequency <= 0 || baseFrequency <= 0) return 0;
    return 12 * Math.log2(frequency / baseFrequency);
  };

  const frequencyToQtone = (frequency: number, baseFrequency: number = 200): number => {
    if (frequency <= 0 || baseFrequency <= 0) return 0;
    // Q-tone = Quarter-tone = 1/4 semitone = 24 * log2(f/f0)
    // 1 semitone = 2 Q-tones
    return 24 * Math.log2(frequency / baseFrequency);
  };

  const convertFrequency = useCallback((frequency: number): number => {
    const result = yAxisUnit === 'qtone' ? frequencyToQtone(frequency) : frequencyToSemitone(frequency);
    console.log(`🔄 변환: ${frequency.toFixed(1)}Hz → ${result.toFixed(2)} ${yAxisUnit} (함수=${yAxisUnit === 'qtone' ? 'Q-tone' : 'Semitone'})`);
    return result;
  }, [yAxisUnit]);

  // 🎯 Y축 단위 변경 시 차트 업데이트 (강제 업데이트)
  const updateYAxisUnit = useCallback(() => {
    if (!chartRef.current) {
      console.log('⚠️ 차트가 아직 초기화되지 않았습니다.');
      return;
    }
    
    const chart = chartRef.current;
    const yAxisTitle = yAxisUnit === 'qtone' ? 'Q-tone' : 'Semitone (세미톤)';
    console.log(`🔄 Y축 단위 변경됨: ${yAxisUnit}, 기존 데이터 ${pitchDataRef.current.length}개 재변환 중...`);
    
    // Y축 제목 및 범위 강제 업데이트
    if (chart.options.scales && chart.options.scales.y) {
      const yScale = chart.options.scales.y as any;
      if (yScale.title) {
        console.log(`🔄 Y축 라벨 변경: "${yScale.title.text}" → "${yAxisTitle}"`);
        yScale.title.text = yAxisTitle;
      }
      
      // Y축 범위 업데이트 - Q-tone은 세미톤의 2배 값
      const newRange = yAxisUnit === 'qtone' 
        ? { min: -20, max: 30 }  // 큐톤 범위 (세미톤 × 2)
        : { min: -10, max: 15 }; // 세미톤 범위
        
      yScale.min = newRange.min;
      yScale.max = newRange.max;
      console.log(`🔄 Y축 범위 변경: ${newRange.min} ~ ${newRange.max} (${yAxisUnit})`);
    }
    
    // 🎯 툴팁 콜백 업데이트 - 단위 표시 수정
    if (chart.options.plugins?.tooltip?.callbacks) {
      chart.options.plugins.tooltip.callbacks.label = function(context: any) {
        const unit = yAxisUnit === 'qtone' ? 'Q-tone' : 'Semitone';
        return `${context.dataset.label}: ${context.parsed.y.toFixed(1)} ${unit}`;
      };
      console.log(`🔄 툴팁 단위 변경: ${yAxisUnit === 'qtone' ? 'Q-tone' : 'Semitone'}`);
    }
    
    // 🎯 음절 라벨 위치 업데이트 - 고정 위치로 표시
    if (chart.options.plugins?.annotation?.annotations) {
      const annotations = chart.options.plugins.annotation.annotations;
      const yAxisScale = chart.options.scales.y as any;
      const chartMax = yAxisScale.max;
      const chartMin = yAxisScale.min;
      
      // 음절 라벨을 차트 상단 고정 위치(90% 지점)에 표시
      const fixedLabelY = chartMin + (chartMax - chartMin) * 0.9;
      
      Object.keys(annotations).forEach(key => {
        if (key.startsWith('label_')) {
          const annotation = annotations[key] as any;
          if (annotation.type === 'label') {
            annotation.yValue = fixedLabelY;
            console.log(`🔄 음절 라벨 '${annotation.content}' 위치 업데이트: ${fixedLabelY.toFixed(1)}`);
          }
        }
      });
    }
    
    // 데이터가 있으면 재변환 및 Y축 범위 재계산
    if (pitchDataRef.current.length > 0) {
      const convertedValues: number[] = [];
      
      chart.data.datasets.forEach((dataset, datasetIndex) => {
        const dataArray = dataset.data as Array<{x: number, y: number}>;
        
        dataArray.forEach((point, pointIndex) => {
          const originalData = pitchDataRef.current.find(data => 
            Math.abs(data.time - point.x) < 0.001
          );
          
          if (originalData && originalData.frequency) {
            const convertedValue = convertFrequency(originalData.frequency);
            point.y = convertedValue;
            convertedValues.push(convertedValue);
          }
        });
      });
      
      // 🎯 Y축 범위 재계산 - 단위 변경에 따른 범위 조정
      if (convertedValues.length > 0) {
        const minValue = Math.min(...convertedValues);
        const maxValue = Math.max(...convertedValues);
        const margin = Math.abs(maxValue - minValue) * 0.1 || 2; // 10% 여유분 또는 최소 2
        
        if (chart.options.scales && chart.options.scales.y) {
          const yAxisScale = chart.options.scales.y as any;
          yAxisScale.min = Math.floor(minValue - margin);
          yAxisScale.max = Math.ceil(maxValue + margin);
          console.log(`🔄 현재 원본 데이터 샘플:`, pitchDataRef.current.slice(0, 3));
          console.log(`🔄 Y축 범위 재계산: ${yAxisScale.min} ~ ${yAxisScale.max} (변환된 범위: ${minValue.toFixed(1)} ~ ${maxValue.toFixed(1)})`);
        }
      }
    }
    
    // 차트 강제 업데이트
    chart.update('active');
    console.log(`✅ 차트 데이터 재변환 완료: ${yAxisUnit} 단위, Y축 라벨: ${yAxisTitle}`);
  }, [yAxisUnit, convertFrequency]);

  // Y축 단위 변경 시 업데이트
  useEffect(() => {
    console.log(`🎯 useEffect 트리거됨 - yAxisUnit: ${yAxisUnit}, 차트존재: ${!!chartRef.current}, 데이터개수: ${pitchDataRef.current.length}`);
    updateYAxisUnit();
  }, [updateYAxisUnit, yAxisUnit]);

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
    const chart = chartRef.current;

    if (type === 'reference') {
      // 🎯 참조 데이터는 포인트로 표시
      const convertedValue = convertFrequency(frequency);
      
      chart.data.datasets[0].data.push({
        x: relativeTime,
        y: convertedValue
      });
    } else {
      // 🎯 실시간 데이터는 Y축에만 고정 표시 (x=0 위치)
      const convertedValue = convertFrequency(frequency);
      
      console.log(`🎤 실시간 데이터: ${frequency.toFixed(1)}Hz → ${convertedValue.toFixed(1)} ${yAxisUnit} (고정표시)`);
      
      // 🎯 실시간 데이터를 dataset[1]에 업데이트 (x=0 고정)
      chart.data.datasets[1].data = [{
        x: 0, // 시간과 무관하게 x=0에 고정
        y: convertedValue
      }];
      
      // 🎯 Y축 자동 스케일링 - 실시간 데이터가 범위 밖이면 확장
      const yScale = chart.options.scales?.y as any;
      if (yScale) {
        let needsUpdate = false;
        
        if (convertedValue < yScale.min) {
          yScale.min = Math.floor(convertedValue - 2);
          needsUpdate = true;
        }
        if (convertedValue > yScale.max) {
          yScale.max = Math.ceil(convertedValue + 2);
          needsUpdate = true;
        }
        
        if (needsUpdate) {
          console.log(`📈 Y축 자동 스케일링: ${yScale.min} ~ ${yScale.max} (실시간 값: ${convertedValue.toFixed(1)})`);
        }
      }
      
      // 🎯 실시간 값을 Y축 고정 위치에 annotation으로 라벨 표시
      if (chart.options.plugins?.annotation?.annotations) {
        (chart.options.plugins.annotation.annotations as any).realtimeValue = {
          type: 'point',
          xValue: 0,
          yValue: convertedValue,
          backgroundColor: 'rgba(34, 197, 94, 0.8)',
          borderColor: 'rgba(34, 197, 94, 1)',
          borderWidth: 3,
          radius: 8,
          label: {
            display: true,
            position: 'end',
            content: `실시간: ${convertedValue.toFixed(1)}`,
            backgroundColor: 'rgba(34, 197, 94, 0.9)',
            color: 'white',
            font: {
              size: 11
            }
          }
        };
      }
    }

    chart.update('none');
  }, [convertFrequency, startTimeRef]);

  const clearChart = useCallback(() => {
    if (!chartRef.current) return;

    chartRef.current.data.datasets.forEach(dataset => {
      dataset.data = [];
    });
    
    pitchDataRef.current = [];
    startTimeRef.current = 0;
    realtimeLineRef.current = null;

    // 🎯 실시간 데이터 제거
    if (chartRef.current.options.plugins?.annotation?.annotations) {
      delete (chartRef.current.options.plugins.annotation.annotations as any).realtimeValue;
    }

    chartRef.current.update();
  }, []);

  // 🎯 실시간 데이터 숨기기 (녹음 중지 시)
  const hideRealtimePitchLine = useCallback(() => {
    if (!chartRef.current) return;
    
    // 실시간 데이터셋 클리어
    chartRef.current.data.datasets[1].data = [];
    
    // 실시간 annotation 제거
    if (chartRef.current.options.plugins?.annotation?.annotations) {
      delete (chartRef.current.options.plugins.annotation.annotations as any).realtimeValue;
      chartRef.current.update('none');
      console.log('🎯 실시간 데이터 숨김');
    }
  }, []);

  // 🎯 실시간 데이터 업데이트 (녹음 중)
  const updateRealtimePitchLine = useCallback((time: number, value: number) => {
    if (!chartRef.current) return;
    
    // Y축 단위에 맞게 값 변환
    const convertedValue = convertFrequency(value); // value는 이미 Hz 값
    
    // 실시간 데이터를 x=0에 고정하여 업데이트
    chartRef.current.data.datasets[1].data = [{
      x: 0,
      y: convertedValue
    }];
    
    // 실시간 annotation 업데이트
    if (chartRef.current.options.plugins?.annotation?.annotations) {
      (chartRef.current.options.plugins.annotation.annotations as any).realtimeValue = {
        type: 'point',
        xValue: 0,
        yValue: convertedValue,
        backgroundColor: 'rgba(34, 197, 94, 0.8)',
        borderColor: 'rgba(34, 197, 94, 1)',
        borderWidth: 3,
        radius: 8,
        label: {
          display: true,
          position: 'end',
          content: `실시간: ${convertedValue.toFixed(1)}`,
          backgroundColor: 'rgba(34, 197, 94, 0.9)',
          color: 'white',
          font: {
            size: 11
          }
        }
      };
      chartRef.current.update('none');
    }
  }, [convertFrequency]);

  const loadReferenceData = useCallback(async (fileId: string) => {
    try {
      // Load syllable-only pitch data (오리지널과 동일한 음절별 대표값)
      const pitchUrl = `${API_BASE}/api/reference_files/${fileId}/pitch?syllable_only=true`;
      const syllableUrl = `${API_BASE}/api/reference_files/${fileId}/syllables`;
      
      const [pitchResponse, syllableResponse] = await Promise.all([
        fetch(pitchUrl),
        fetch(syllableUrl)
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
        const convertedValues: number[] = [];
        
        // Add reference data points and collect converted values
        pitchData.forEach((point: {time: number, frequency: number, syllable?: string}) => {
          // 🎯 백엔드에서 이미 초 단위로 온 데이터를 그대로 사용 (1000 곱하지 않음)
          addPitchData(point.frequency, point.time, 'reference');
          
          // Y축 범위 계산을 위해 변환된 값 수집
          const convertedValue = convertFrequency(point.frequency);
          convertedValues.push(convertedValue);
          
          maxTime = Math.max(maxTime, point.time);
          if (point.syllable) {
            }
        });
        
        // 🎯 Y축 범위 자동 조정 - 데이터에 맞는 범위 계산
        if (convertedValues.length > 0 && chartRef.current?.options?.scales?.y) {
          const minValue = Math.min(...convertedValues);
          const maxValue = Math.max(...convertedValues);
          const margin = Math.abs(maxValue - minValue) * 0.1 || 2; // 10% 여유분 또는 최소 2
          
          const yScale = chartRef.current.options.scales.y as any;
          yScale.min = Math.floor(minValue - margin);
          yScale.max = Math.ceil(maxValue + margin);
          
          console.log(`📊 Y축 범위 자동 조정: ${yScale.min} ~ ${yScale.max} (데이터 범위: ${minValue.toFixed(1)} ~ ${maxValue.toFixed(1)})`);
        }
        
        // 실제 오디오 길이에 맞게 x축 범위 조정
        if (chartRef.current?.options?.scales?.x && maxTime > 0) {
          const newMax = maxTime + 0.3; // 실제 길이 + 0.3초 여유분
          chartRef.current.options.scales.x.min = 0;
          chartRef.current.options.scales.x.max = newMax;
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
    
    // 🎯 Position labels at fixed position (90% from bottom) 
    const yScale = chart.options.scales?.y;
    const chartMax = (yScale?.max as number) || 500;
    const chartMin = (yScale?.min as number) || 50;
    const labelY = chartMin + (chartMax - chartMin) * 0.9; // 90% from bottom (고정 위치)
    
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

  // 🎯 피치 위치 초기화 - 현재 데이터에 맞게 자동 조정
  const resetPitch = useCallback(() => {
    if (!chartRef.current) return;

    const yScale = chartRef.current.options.scales?.y;
    if (!yScale) return;

    // 🎯 현재 데이터에 맞는 범위로 재설정
    if (pitchDataRef.current.length > 0) {
      const convertedValues = pitchDataRef.current.map(data => 
        yAxisUnit === 'qtone' ? frequencyToQtone(data.frequency) : frequencyToSemitone(data.frequency)
      );
      const minValue = Math.min(...convertedValues);
      const maxValue = Math.max(...convertedValues);
      const margin = Math.abs(maxValue - minValue) * 0.1 || 2;
      
      yScale.min = Math.floor(minValue - margin);
      yScale.max = Math.ceil(maxValue + margin);
      console.log(`🎯 피치 범위 자동 재설정: ${yScale.min} ~ ${yScale.max}`);
    } else {
      // 데이터가 없으면 기본 범위로 설정
      const defaultRange = yAxisUnit === 'qtone' 
        ? { min: -20, max: 30 }  // Q-tone 기본 범위
        : { min: -10, max: 15 }; // Semitone 기본 범위
      yScale.min = defaultRange.min;
      yScale.max = defaultRange.max;
      console.log(`🎯 피치 범위 기본값으로 재설정: ${yScale.min} ~ ${yScale.max}`);
    }

    chartRef.current.update('none');
  }, [yAxisUnit, frequencyToQtone, frequencyToSemitone]);

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

  // 🎯 Y축 범위 업데이트 (세미톤/큐톤 범위 설정)
  const updateRange = useCallback((min: number, max: number) => {
    if (!chartRef.current) return;

    const yScale = chartRef.current.options.scales?.y;
    if (!yScale) return;

    yScale.min = min;
    yScale.max = max;

    chartRef.current.update('none');
    console.log(`📊 Y축 범위 업데이트: ${min} ~ ${max} (${yAxisUnit})`);
  }, [yAxisUnit]);

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
    addSyllableAnnotations,
    adjustPitch,
    zoomIn,
    zoomOut,
    scrollLeft,
    scrollRight,
    resetView,
    updateRealtimePitchLine,
    hideRealtimePitchLine,
    updateRange,
    setYAxisUnit, // Y축 단위 설정 메서드 추가
    yAxisUnit    // 현재 Y축 단위 반환
  };
};