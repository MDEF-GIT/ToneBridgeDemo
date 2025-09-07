/**
 * ToneBridge Chart Controls Component
 * Converted from vanilla JS to TypeScript React component
 * 
 * Original: setupZoomAndScrollHandlers, zoomChart, scrollChart, resetChartView
 * Lines: 448-593 in backend/static/js/audio-analysis.js
 */

import * as React from 'react';
import { Chart as ChartJS } from 'chart.js';

interface ChartControlsProps {
  chartInstance: ChartJS | null;
  onZoom?: (factor: number, newRange: { min: number; max: number }) => void;
  onScroll?: (direction: 'left' | 'right', newRange: { min: number; max: number }) => void;
  onReset?: () => void;
  className?: string;
}

interface ChartViewState {
  currentZoom: number;
  minX: number;
  maxX: number;
  originalMinX: number;
  originalMaxX: number;
  isZoomed: boolean;
}

/**
 * 차트 확대/스크롤 컨트롤 컴포넌트
 * 원본: setupZoomAndScrollHandlers() (lines 448-483)
 */
export const ChartControls: React.FC<ChartControlsProps> = ({
  chartInstance,
  onZoom,
  onScroll,
  onReset,
  className = ''
}) => {
  const viewStateRef = React.useRef<ChartViewState>({
    currentZoom: 1,
    minX: 0,
    maxX: 100,
    originalMinX: 0,
    originalMaxX: 100,
    isZoomed: false
  });

  // 차트 인스턴스 변경 시 원본 범위 저장
  React.useEffect(() => {
    if (chartInstance && chartInstance.data.datasets.length > 0) {
      const dataset = chartInstance.data.datasets[0];
      if (dataset.data.length > 0) {
        const firstPoint = dataset.data[0] as any;
        const lastPoint = dataset.data[dataset.data.length - 1] as any;
        
        viewStateRef.current.originalMinX = firstPoint.x || 0;
        viewStateRef.current.originalMaxX = lastPoint.x || 100;
        viewStateRef.current.minX = viewStateRef.current.originalMinX;
        viewStateRef.current.maxX = viewStateRef.current.originalMaxX;
        
        console.log('🎯 차트 범위 초기화:', {
          originalMin: viewStateRef.current.originalMinX,
          originalMax: viewStateRef.current.originalMaxX
        });
      }
    }
  }, [chartInstance]);

  /**
   * 차트 확대 기능
   * 원본: zoomChart(factor) (lines 484-549)
   */
  const handleZoom = (factor: number) => {
    if (!chartInstance) {
      console.warn('차트 인스턴스가 없습니다');
      return;
    }

    const viewState = viewStateRef.current;
    const currentRange = viewState.maxX - viewState.minX;
    const center = (viewState.maxX + viewState.minX) / 2;
    
    // 새로운 범위 계산
    const newRange = currentRange / factor;
    const newMinX = center - newRange / 2;
    const newMaxX = center + newRange / 2;
    
    // 원본 범위를 벗어나지 않도록 제한
    const clampedMinX = Math.max(newMinX, viewState.originalMinX);
    const clampedMaxX = Math.min(newMaxX, viewState.originalMaxX);
    
    // 최소 범위 보장 (원본의 1% 이상)
    const minRangeAllowed = (viewState.originalMaxX - viewState.originalMinX) * 0.01;
    if (clampedMaxX - clampedMinX < minRangeAllowed) {
      console.log('🚫 최소 확대 범위에 도달했습니다');
      return;
    }
    
    viewState.minX = clampedMinX;
    viewState.maxX = clampedMaxX;
    viewState.currentZoom = factor;
    viewState.isZoomed = factor > 1.1; // 10% 이상 확대 시 확대 상태로 간주
    
    // Chart.js 옵션 업데이트
    if (chartInstance.options.scales?.x) {
      chartInstance.options.scales.x.min = clampedMinX;
      chartInstance.options.scales.x.max = clampedMaxX;
      chartInstance.update('none'); // 애니메이션 없이 즉시 업데이트
    }
    
    console.log('🔍 차트 확대:', { 
      factor, 
      newRange: { min: clampedMinX, max: clampedMaxX },
      zoom: viewState.currentZoom 
    });
    
    onZoom?.(factor, { min: clampedMinX, max: clampedMaxX });
  };

  /**
   * 차트 스크롤 기능
   * 원본: scrollChart(direction) (lines 550-573)
   */
  const handleScroll = (direction: 'left' | 'right') => {
    if (!chartInstance) {
      console.warn('차트 인스턴스가 없습니다');
      return;
    }

    const viewState = viewStateRef.current;
    const currentRange = viewState.maxX - viewState.minX;
    const scrollStep = currentRange * 0.1; // 현재 범위의 10%씩 스크롤
    
    let newMinX = viewState.minX;
    let newMaxX = viewState.maxX;
    
    if (direction === 'left') {
      newMinX = Math.max(viewState.minX - scrollStep, viewState.originalMinX);
      newMaxX = newMinX + currentRange;
    } else {
      newMaxX = Math.min(viewState.maxX + scrollStep, viewState.originalMaxX);
      newMinX = newMaxX - currentRange;
    }
    
    // 원본 범위 내에서만 스크롤 허용
    if (newMinX < viewState.originalMinX) {
      newMinX = viewState.originalMinX;
      newMaxX = newMinX + currentRange;
    }
    if (newMaxX > viewState.originalMaxX) {
      newMaxX = viewState.originalMaxX;
      newMinX = newMaxX - currentRange;
    }
    
    viewState.minX = newMinX;
    viewState.maxX = newMaxX;
    
    // Chart.js 옵션 업데이트
    if (chartInstance.options.scales?.x) {
      chartInstance.options.scales.x.min = newMinX;
      chartInstance.options.scales.x.max = newMaxX;
      chartInstance.update('none');
    }
    
    console.log('↔️ 차트 스크롤:', { 
      direction, 
      newRange: { min: newMinX, max: newMaxX } 
    });
    
    onScroll?.(direction, { min: newMinX, max: newMaxX });
  };

  /**
   * 차트 뷰 리셋
   * 원본: resetChartView() (lines 574-592)
   */
  const handleReset = () => {
    if (!chartInstance) {
      console.warn('차트 인스턴스가 없습니다');
      return;
    }

    const viewState = viewStateRef.current;
    
    viewState.minX = viewState.originalMinX;
    viewState.maxX = viewState.originalMaxX;
    viewState.currentZoom = 1;
    viewState.isZoomed = false;
    
    // Chart.js 옵션 리셋
    if (chartInstance.options.scales?.x) {
      chartInstance.options.scales.x.min = undefined;
      chartInstance.options.scales.x.max = undefined;
      chartInstance.update('none');
    }
    
    console.log('🔄 차트 뷰 리셋:', {
      originalRange: { min: viewState.originalMinX, max: viewState.originalMaxX }
    });
    
    onReset?.();
  };

  // 키보드 단축키 처리
  React.useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!chartInstance) return;
      
      switch (event.key) {
        case '+':
        case '=':
          event.preventDefault();
          handleZoom(1.2);
          break;
        case '-':
          event.preventDefault();
          handleZoom(0.8);
          break;
        case 'ArrowLeft':
          if (event.ctrlKey || event.metaKey) {
            event.preventDefault();
            handleScroll('left');
          }
          break;
        case 'ArrowRight':
          if (event.ctrlKey || event.metaKey) {
            event.preventDefault();
            handleScroll('right');
          }
          break;
        case 'Home':
          event.preventDefault();
          handleReset();
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [chartInstance]);

  return (
    <div className={`chart-controls d-flex gap-2 mb-3 ${className}`}>
      <div className="btn-group" role="group" aria-label="차트 확대/축소">
        <button
          type="button"
          className="btn btn-outline-primary btn-sm"
          onClick={() => handleZoom(1.2)}
          title="확대 (+)"
        >
          <i className="fas fa-search-plus"></i>
        </button>
        <button
          type="button"
          className="btn btn-outline-primary btn-sm"
          onClick={() => handleZoom(0.8)}
          title="축소 (-)"
        >
          <i className="fas fa-search-minus"></i>
        </button>
      </div>
      
      <div className="btn-group" role="group" aria-label="차트 스크롤">
        <button
          type="button"
          className="btn btn-outline-secondary btn-sm"
          onClick={() => handleScroll('left')}
          title="왼쪽으로 스크롤 (Ctrl+←)"
        >
          <i className="fas fa-arrow-left"></i>
        </button>
        <button
          type="button"
          className="btn btn-outline-secondary btn-sm"
          onClick={() => handleScroll('right')}
          title="오른쪽으로 스크롤 (Ctrl+→)"
        >
          <i className="fas fa-arrow-right"></i>
        </button>
      </div>
      
      <button
        type="button"
        className="btn btn-outline-info btn-sm"
        onClick={handleReset}
        title="원래 크기로 리셋 (Home)"
      >
        <i className="fas fa-home"></i> 리셋
      </button>
      
      {viewStateRef.current.isZoomed && (
        <span className="badge bg-info ms-2 align-self-center">
          확대됨 ({(viewStateRef.current.currentZoom * 100).toFixed(0)}%)
        </span>
      )}
    </div>
  );
};

export default ChartControls;