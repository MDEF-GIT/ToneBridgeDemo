import { useRef, useEffect, useCallback } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
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

export const usePitchChart = (canvasRef: React.RefObject<HTMLCanvasElement>) => {
  const chartRef = useRef<ChartJS | null>(null);
  const pitchDataRef = useRef<PitchData[]>([]);
  const startTimeRef = useRef<number>(0);

  const initChart = useCallback(() => {
    if (!canvasRef.current) return;

    const ctx = canvasRef.current.getContext('2d');
    if (!ctx) return;

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
          borderColor: 'rgb(255, 99, 132)',
          backgroundColor: 'rgba(255, 99, 132, 0.2)',
          tension: 0.4,
          pointRadius: 0,
          borderWidth: 2
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
        pitchData.forEach((point: any) => {
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
    pitchData: pitchDataRef.current
  };
};