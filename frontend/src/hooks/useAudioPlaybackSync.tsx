import { useCallback, useRef } from 'react';

/**
 * 🎵 ToneBridge 통합 오디오 재생 동기화 훅
 * 
 * 모든 재생 부분에서 사용할 수 있는 범용적인 오디오-차트 동기화 기능 제공
 * 차트 3에서 검증된 방식을 기반으로 구현
 */

interface PlaybackSyncOptions {
  /** 차트 인스턴스 (updatePlaybackProgress, clearPlaybackProgress 메서드 필요) */
  chartInstance?: {
    updatePlaybackProgress?: (currentTime: number) => void;
    clearPlaybackProgress?: () => void;
  };
  /** 업데이트 간격 (기본: requestAnimationFrame 사용) */
  updateInterval?: 'frame' | number;
  /** 로깅 활성화 여부 */
  enableLogging?: boolean;
}

export const useAudioPlaybackSync = (options: PlaybackSyncOptions = {}) => {
  const {
    chartInstance,
    updateInterval = 'frame',
    enableLogging = true
  } = options;

  const animationFrameRef = useRef<number | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);

  // 🎯 재생 진행 추적 시작
  const startProgressTracking = useCallback((audioElement: HTMLAudioElement) => {
    if (enableLogging) {
      console.log('🎵 AudioPlaybackSync: 재생 진행 추적 시작');
    }

    // 기존 추적 중지
    stopProgressTracking();
    
    // 현재 오디오 요소 저장
    currentAudioRef.current = audioElement;

    const updateProgress = () => {
      if (currentAudioRef.current && !currentAudioRef.current.paused && !currentAudioRef.current.ended) {
        const currentTime = currentAudioRef.current.currentTime;
        
        // 차트에 현재 시점 업데이트
        if (chartInstance?.updatePlaybackProgress) {
          chartInstance.updatePlaybackProgress(currentTime);
        }

        // 다음 프레임에서 계속 업데이트
        if (updateInterval === 'frame') {
          animationFrameRef.current = requestAnimationFrame(updateProgress);
        }
      }
    };

    if (updateInterval === 'frame') {
      // requestAnimationFrame 방식 (권장 - 부드러운 동기화)
      animationFrameRef.current = requestAnimationFrame(updateProgress);
    } else if (typeof updateInterval === 'number') {
      // setInterval 방식
      intervalRef.current = setInterval(() => {
        if (currentAudioRef.current && !currentAudioRef.current.paused) {
          const currentTime = currentAudioRef.current.currentTime;
          if (chartInstance?.updatePlaybackProgress) {
            chartInstance.updatePlaybackProgress(currentTime);
          }
        }
      }, updateInterval);
    }
  }, [chartInstance, updateInterval, enableLogging]);

  // 🎯 재생 진행 추적 중지
  const stopProgressTracking = useCallback(() => {
    if (enableLogging) {
      console.log('🎵 AudioPlaybackSync: 재생 진행 추적 중지');
    }

    // 애니메이션 프레임 정리
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }

    // 인터벌 정리
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    // 차트 진행 표시 제거
    if (chartInstance?.clearPlaybackProgress) {
      chartInstance.clearPlaybackProgress();
    }

    // 오디오 참조 제거
    currentAudioRef.current = null;
  }, [chartInstance, enableLogging]);

  // 🎯 오디오 요소에 자동 이벤트 리스너 연결
  const setupAudioElement = useCallback((audioElement: HTMLAudioElement) => {
    if (enableLogging) {
      console.log('🎵 AudioPlaybackSync: 오디오 요소 설정');
    }

    // 재생 시작 시 추적 시작
    const handlePlay = () => {
      if (enableLogging) {
        console.log('🎵 AudioPlaybackSync: 재생 시작 감지');
      }
      startProgressTracking(audioElement);
    };

    // 재생 완료/일시정지 시 추적 중지
    const handleStop = () => {
      if (enableLogging) {
        console.log('🎵 AudioPlaybackSync: 재생 중지 감지');
      }
      stopProgressTracking();
    };

    // 이벤트 리스너 연결
    audioElement.addEventListener('play', handlePlay);
    audioElement.addEventListener('pause', handleStop);
    audioElement.addEventListener('ended', handleStop);
    audioElement.addEventListener('error', handleStop);

    // 정리 함수 반환
    return () => {
      audioElement.removeEventListener('play', handlePlay);
      audioElement.removeEventListener('pause', handleStop);
      audioElement.removeEventListener('ended', handleStop);
      audioElement.removeEventListener('error', handleStop);
      stopProgressTracking();
    };
  }, [startProgressTracking, stopProgressTracking, enableLogging]);

  // 🎯 수동 제어 함수들
  const manualControls = {
    start: startProgressTracking,
    stop: stopProgressTracking,
    updateNow: useCallback((currentTime: number) => {
      if (chartInstance?.updatePlaybackProgress) {
        chartInstance.updatePlaybackProgress(currentTime);
      }
    }, [chartInstance])
  };

  return {
    // 🎯 자동 모드: 오디오 요소에 이벤트 리스너 연결
    setupAudioElement,
    
    // 🎯 수동 모드: 직접 제어
    ...manualControls,
    
    // 🎯 상태 확인
    isTracking: !!animationFrameRef.current || !!intervalRef.current
  };
};