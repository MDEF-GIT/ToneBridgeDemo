import { useState, useCallback, useRef } from 'react';
import { tonebridgeApi } from '../utils/tonebridgeApi';

interface AdaptiveAdjustmentData {
  original_reference: number;
  new_reference: number;
  adjustment_hz: number;
  adjustment_semitones: number;
  effective_factor: number;
  context: string;
  confidence_used: number;
}

interface MovingAverageData {
  updated_reference: number;
  alternative_reference: number;
  stability_coefficient: number;
  sample_count: number;
  effective_window: number;
  pitch_range: {
    min: number;
    max: number;
    std: number;
  };
}

interface PitchHistoryEntry {
  frequency: number;
  timestamp: number;
  confidence: number;
  context?: string;
}

export const useAdaptiveReference = () => {
  const [currentReference, setCurrentReference] = useState<number>(200);
  const [pitchHistory, setPitchHistory] = useState<PitchHistoryEntry[]>([]);
  const [isAdaptive, setIsAdaptive] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // 설정
  const [adjustmentFactor, setAdjustmentFactor] = useState<number>(0.1); // 조정 강도
  const [windowSize, setWindowSize] = useState<number>(20); // 이동평균 윈도우
  const [decayFactor, setDecayFactor] = useState<number>(0.95); // 시간 감쇠
  
  const lastUpdateTime = useRef<number>(Date.now());

  // 🔄 실시간 기준점 조정
  const adjustReference = useCallback(async (
    currentFrequency: number,
    confidence: number = 0.8,
    context: string = 'normal'
  ): Promise<AdaptiveAdjustmentData | null> => {
    try {
      if (!isAdaptive) return null;
      
      setIsLoading(true);
      setError(null);
      
      const adjustmentData = {
        current_frequency: currentFrequency,
        current_reference: currentReference,
        confidence,
        adjustment_factor: adjustmentFactor,
        context
      };
      
      const response = await tonebridgeApi.post('/api/adaptive-reference-adjustment', adjustmentData);
      const data = response.data as AdaptiveAdjustmentData;
      
      // 기준점 업데이트
      setCurrentReference(data.new_reference);
      
      // 히스토리에 추가
      const now = Date.now();
      setPitchHistory(prev => [...prev, {
        frequency: currentFrequency,
        timestamp: now,
        confidence,
        context
      }]);
      
      console.log(`🔄 적응형 조정: ${data.original_reference:.1f}Hz → ${data.new_reference:.1f}Hz (${context})`);
      
      return data;
      
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || '적응형 조정 실패';
      console.error('❌ 적응형 조정 오류:', errorMsg);
      setError(errorMsg);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [currentReference, adjustmentFactor, isAdaptive]);

  // 📈 이동평균 기반 업데이트
  const updateWithMovingAverage = useCallback(async (): Promise<MovingAverageData | null> => {
    try {
      if (pitchHistory.length < 3) {
        throw new Error('이동평균 계산에 충분한 데이터가 없습니다');
      }
      
      setIsLoading(true);
      setError(null);
      
      const historyData = {
        recent_pitches: pitchHistory.map(entry => entry.frequency),
        timestamps: pitchHistory.map(entry => entry.timestamp),
        confidences: pitchHistory.map(entry => entry.confidence),
        window_size: windowSize,
        decay_factor: decayFactor
      };
      
      const response = await tonebridgeApi.post('/api/moving-average-update', historyData);
      const data = response.data as MovingAverageData;
      
      // 기준점 업데이트
      setCurrentReference(data.updated_reference);
      
      console.log(`📈 이동평균 업데이트: ${data.updated_reference:.1f}Hz (안정성: ${data.stability_coefficient:.2f})`);
      
      return data;
      
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || '이동평균 업데이트 실패';
      console.error('❌ 이동평균 업데이트 오류:', errorMsg);
      setError(errorMsg);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [pitchHistory, windowSize, decayFactor]);

  // 🎤 실시간 피치 데이터 추가 (적응형 조정 포함)
  const addPitchData = useCallback(async (
    frequency: number,
    confidence: number = 0.8,
    context: string = 'normal'
  ) => {
    const now = Date.now();
    
    // 히스토리에 추가
    setPitchHistory(prev => {
      const newHistory = [...prev, {
        frequency,
        timestamp: now,
        confidence,
        context
      }];
      
      // 윈도우 크기 제한
      if (newHistory.length > windowSize * 2) {
        return newHistory.slice(-windowSize);
      }
      return newHistory;
    });
    
    // 적응형 조정 (매 1초마다 또는 충분한 신뢰도일 때)
    const timeSinceLastUpdate = now - lastUpdateTime.current;
    if (isAdaptive && confidence > 0.7 && timeSinceLastUpdate > 1000) {
      await adjustReference(frequency, confidence, context);
      lastUpdateTime.current = now;
    }
  }, [adjustReference, isAdaptive, windowSize]);

  // 🔄 자동 이동평균 업데이트 (주기적)
  const enableAutoUpdate = useCallback((intervalSeconds: number = 30) => {
    const interval = setInterval(async () => {
      if (pitchHistory.length >= 10) {
        await updateWithMovingAverage();
      }
    }, intervalSeconds * 1000);
    
    return () => clearInterval(interval);
  }, [pitchHistory.length, updateWithMovingAverage]);

  // ⚙️ 적응형 시스템 활성화/비활성화
  const setAdaptiveMode = useCallback((enabled: boolean) => {
    setIsAdaptive(enabled);
    console.log(`⚙️ 적응형 기준점 시스템: ${enabled ? '활성화' : '비활성화'}`);
  }, []);

  // 🧹 히스토리 정리
  const clearHistory = useCallback(() => {
    setPitchHistory([]);
    setError(null);
    console.log('🧹 피치 히스토리 정리 완료');
  }, []);

  // 📊 통계 계산
  const getStatistics = useCallback(() => {
    if (pitchHistory.length === 0) {
      return {
        count: 0,
        mean: 0,
        std: 0,
        min: 0,
        max: 0,
        range: 0,
        stability: 0
      };
    }
    
    const frequencies = pitchHistory.map(entry => entry.frequency);
    const mean = frequencies.reduce((sum, f) => sum + f, 0) / frequencies.length;
    const variance = frequencies.reduce((sum, f) => sum + (f - mean) ** 2, 0) / frequencies.length;
    const std = Math.sqrt(variance);
    const min = Math.min(...frequencies);
    const max = Math.max(...frequencies);
    
    return {
      count: frequencies.length,
      mean: Math.round(mean * 10) / 10,
      std: Math.round(std * 10) / 10,
      min: Math.round(min * 10) / 10,
      max: Math.round(max * 10) / 10,
      range: Math.round((max - min) * 10) / 10,
      stability: Math.round((1 - std / mean) * 1000) / 1000
    };
  }, [pitchHistory]);

  // 📈 최근 트렌드 분석
  const getTrend = useCallback(() => {
    if (pitchHistory.length < 5) return 'insufficient_data';
    
    const recent = pitchHistory.slice(-5);
    const older = pitchHistory.slice(-10, -5);
    
    if (older.length === 0) return 'stable';
    
    const recentMean = recent.reduce((sum, entry) => sum + entry.frequency, 0) / recent.length;
    const olderMean = older.reduce((sum, entry) => sum + entry.frequency, 0) / older.length;
    
    const diff = recentMean - olderMean;
    const threshold = currentReference * 0.02; // 2% 변화
    
    if (diff > threshold) return 'rising';
    if (diff < -threshold) return 'falling';
    return 'stable';
  }, [pitchHistory, currentReference]);

  return {
    // 상태
    currentReference,
    pitchHistory,
    isAdaptive,
    isLoading,
    error,
    
    // 설정
    adjustmentFactor,
    windowSize,
    decayFactor,
    setAdjustmentFactor,
    setWindowSize,
    setDecayFactor,
    
    // 주요 함수들
    adjustReference,
    updateWithMovingAverage,
    addPitchData,
    setAdaptiveMode,
    enableAutoUpdate,
    
    // 유틸리티
    clearHistory,
    getStatistics,
    getTrend,
    setCurrentReference,
    
    // 상태 체크
    hasEnoughData: pitchHistory.length >= 3,
    isStable: getStatistics().stability > 0.8,
    recentCount: pitchHistory.filter(entry => Date.now() - entry.timestamp < 60000).length // 최근 1분
  };
};