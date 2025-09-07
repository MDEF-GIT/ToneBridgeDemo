/**
 * ToneBridge Pitch Test Mode Component
 * Converted from vanilla JS to TypeScript React component
 * 
 * Original: handleTwoPointPractice, setupPitchTestHandlers, stopPitchTest
 * Lines: 2880-3447 in backend/static/js/audio-analysis.js
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Chart as ChartJS } from 'chart.js';
import { f0ToSemitone, f0ToQt } from '../utils/audioUtils';

interface PitchTestModeProps {
  chartInstance: ChartJS | null;
  isActive: boolean;
  onStart?: () => void;
  onStop?: () => void;
  onTargetHit?: (accuracy: number) => void;
  className?: string;
}

interface PitchTestState {
  isActive: boolean;
  mode: 'single' | 'range' | 'two-point' | 'off';
  targetValue: number | null;
  targetRange: { min: number; max: number } | null;
  currentValue: number;
  accuracy: number;
  feedback: string;
  score: number;
  attempts: number;
  successfulHits: number;
}

interface ReferenceLine {
  id: string;
  value: number;
  color: string;
  label: string;
}

/**
 * 피치 테스트 모드 컴포넌트
 * 원본: handleTwoPointPractice(), setupPitchTestHandlers() (lines 2880-3161)
 */
export const PitchTestMode: React.FC<PitchTestModeProps> = ({
  chartInstance,
  isActive,
  onStart,
  onStop,
  onTargetHit,
  className = ''
}) => {
  const [testState, setTestState] = useState<PitchTestState>({
    isActive: false,
    mode: 'off',
    targetValue: null,
    targetRange: null,
    currentValue: 0,
    accuracy: 0,
    feedback: '피치 테스트를 시작하려면 모드를 선택하세요',
    score: 0,
    attempts: 0,
    successfulHits: 0
  });

  const [referenceLines, setReferenceLines] = useState<ReferenceLine[]>([]);
  const [yAxisUnit, setYAxisUnit] = useState<'semitone' | 'qtone'>('semitone');
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const targetToleranceRef = useRef<number>(0.5); // 세미톤 허용 오차

  /**
   * 피치 참조선 추가
   * 원본: addPitchReferenceLine() (lines 3382-3415)
   */
  const addReferenceLine = useCallback((value: number, label: string, color: string = '#ff6b35') => {
    if (!chartInstance) return;

    const lineId = `pitch-line-${Date.now()}`;
    const newLine: ReferenceLine = {
      id: lineId,
      value,
      color,
      label
    };

    setReferenceLines(prev => [...prev, newLine]);

    // Chart.js annotation 추가
    if (!chartInstance.options.plugins) {
      chartInstance.options.plugins = {};
    }
    if (!chartInstance.options.plugins.annotation) {
      chartInstance.options.plugins.annotation = { annotations: {} };
    }

    const annotations = chartInstance.options.plugins.annotation.annotations as any;
    annotations[lineId] = {
      type: 'line',
      yMin: value,
      yMax: value,
      borderColor: color,
      borderWidth: 2,
      borderDash: [5, 5],
      label: {
        content: `${label}: ${value.toFixed(1)}${yAxisUnit === 'semitone' ? 'st' : 'qt'}`,
        enabled: true,
        position: 'end',
        backgroundColor: color,
        color: 'white',
        font: { size: 11 }
      }
    };

    chartInstance.update('none');
    console.log('🎯 피치 참조선 추가:', { value, label, color });
  }, [chartInstance, yAxisUnit]);

  /**
   * 피치 참조선 제거
   * 원본: removePitchReferenceLine() (lines 3416-3424)
   */
  const removeReferenceLine = useCallback((lineId: string) => {
    if (!chartInstance) return;

    setReferenceLines(prev => prev.filter(line => line.id !== lineId));

    if (chartInstance.options.plugins?.annotation?.annotations) {
      const annotations = chartInstance.options.plugins.annotation.annotations as any;
      delete annotations[lineId];
      chartInstance.update('none');
    }

    console.log('🗑️ 피치 참조선 제거:', lineId);
  }, [chartInstance]);

  /**
   * 모든 참조선 제거
   */
  const clearAllReferenceLines = useCallback(() => {
    if (!chartInstance) return;

    referenceLines.forEach(line => {
      if (chartInstance.options.plugins?.annotation?.annotations) {
        const annotations = chartInstance.options.plugins.annotation.annotations as any;
        delete annotations[line.id];
      }
    });

    setReferenceLines([]);
    chartInstance.update('none');
    console.log('🧹 모든 피치 참조선 제거');
  }, [chartInstance, referenceLines]);

  /**
   * 단일 포인트 테스트 시작
   */
  const startSinglePointTest = useCallback((targetSemitone: number) => {
    const targetValue = yAxisUnit === 'semitone' ? targetSemitone : f0ToQt(Math.pow(2, targetSemitone / 12) * 200);
    
    setTestState(prev => ({
      ...prev,
      isActive: true,
      mode: 'single',
      targetValue,
      targetRange: null,
      feedback: `목표: ${targetValue.toFixed(1)}${yAxisUnit === 'semitone' ? 'st' : 'qt'}에 맞춰주세요`,
      attempts: 0,
      successfulHits: 0,
      score: 0
    }));

    addReferenceLine(targetValue, '목표', '#28a745');
    onStart?.();
    
    console.log('🎯 단일 포인트 테스트 시작:', { targetValue, unit: yAxisUnit });
  }, [yAxisUnit, addReferenceLine, onStart]);

  /**
   * 범위 테스트 시작
   */
  const startRangeTest = useCallback((minSemitone: number, maxSemitone: number) => {
    const minValue = yAxisUnit === 'semitone' ? minSemitone : f0ToQt(Math.pow(2, minSemitone / 12) * 200);
    const maxValue = yAxisUnit === 'semitone' ? maxSemitone : f0ToQt(Math.pow(2, maxSemitone / 12) * 200);
    
    setTestState(prev => ({
      ...prev,
      isActive: true,
      mode: 'range',
      targetValue: null,
      targetRange: { min: minValue, max: maxValue },
      feedback: `목표 범위: ${minValue.toFixed(1)} ~ ${maxValue.toFixed(1)}${yAxisUnit === 'semitone' ? 'st' : 'qt'}`,
      attempts: 0,
      successfulHits: 0,
      score: 0
    }));

    addReferenceLine(minValue, '최소', '#ffc107');
    addReferenceLine(maxValue, '최대', '#ffc107');
    onStart?.();
    
    console.log('🎯 범위 테스트 시작:', { minValue, maxValue, unit: yAxisUnit });
  }, [yAxisUnit, addReferenceLine, onStart]);

  /**
   * 2포인트 연습 시작
   * 원본: handleTwoPointPractice() (lines 2880-2894)
   */
  const startTwoPointPractice = useCallback(() => {
    const point1 = -3; // 낮은 음
    const point2 = 5;  // 높은 음
    
    const value1 = yAxisUnit === 'semitone' ? point1 : f0ToQt(Math.pow(2, point1 / 12) * 200);
    const value2 = yAxisUnit === 'semitone' ? point2 : f0ToQt(Math.pow(2, point2 / 12) * 200);
    
    setTestState(prev => ({
      ...prev,
      isActive: true,
      mode: 'two-point',
      targetValue: value1, // 첫 번째 타겟부터 시작
      targetRange: null,
      feedback: `첫 번째 음: ${value1.toFixed(1)}${yAxisUnit === 'semitone' ? 'st' : 'qt'}에 맞춰주세요`,
      attempts: 0,
      successfulHits: 0,
      score: 0
    }));

    addReferenceLine(value1, '첫 번째', '#28a745');
    addReferenceLine(value2, '두 번째', '#dc3545');
    onStart?.();
    
    console.log('🎯 2포인트 연습 시작:', { value1, value2, unit: yAxisUnit });
  }, [yAxisUnit, addReferenceLine, onStart]);

  /**
   * 피치 테스트 중지
   * 원본: stopPitchTest() (lines 3162-3233)
   */
  const stopTest = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    setTestState(prev => ({
      ...prev,
      isActive: false,
      mode: 'off',
      targetValue: null,
      targetRange: null,
      feedback: '테스트가 종료되었습니다',
      currentValue: 0
    }));

    clearAllReferenceLines();
    onStop?.();
    
    console.log('🛑 피치 테스트 중지');
  }, [clearAllReferenceLines, onStop]);

  /**
   * 현재 피치 값 업데이트 및 정확도 계산
   * 원본: updatePitchTestStatus() (lines 3325-3352)
   */
  const updateCurrentPitch = useCallback((frequency: number) => {
    if (!testState.isActive || frequency <= 0) return;

    const semitoneValue = f0ToSemitone(frequency, 200);
    const currentValue = yAxisUnit === 'semitone' ? semitoneValue : f0ToQt(frequency);
    
    let accuracy = 0;
    let feedback = '';
    let isSuccess = false;

    if (testState.mode === 'single' && testState.targetValue !== null) {
      const diff = Math.abs(currentValue - testState.targetValue);
      accuracy = Math.max(0, 100 - (diff / targetToleranceRef.current) * 100);
      isSuccess = diff <= targetToleranceRef.current;
      
      if (isSuccess) {
        feedback = `🎉 정확합니다! (오차: ${diff.toFixed(2)})`;
      } else {
        const direction = currentValue > testState.targetValue ? '낮춰' : '높여';
        feedback = `${direction}주세요 (오차: ${diff.toFixed(2)})`;
      }
    } else if (testState.mode === 'range' && testState.targetRange !== null) {
      const { min, max } = testState.targetRange;
      isSuccess = currentValue >= min && currentValue <= max;
      
      if (isSuccess) {
        accuracy = 100;
        feedback = `🎉 범위 안에 있습니다!`;
      } else if (currentValue < min) {
        accuracy = Math.max(0, 100 - ((min - currentValue) / targetToleranceRef.current) * 100);
        feedback = `높여주세요 (${(min - currentValue).toFixed(2)} 부족)`;
      } else {
        accuracy = Math.max(0, 100 - ((currentValue - max) / targetToleranceRef.current) * 100);
        feedback = `낮춰주세요 (${(currentValue - max).toFixed(2)} 초과)`;
      }
    } else if (testState.mode === 'two-point') {
      // 2포인트 모드는 별도 로직 필요
      feedback = '2포인트 연습 중...';
      accuracy = 50; // 기본값
    }

    setTestState(prev => {
      const newAttempts = prev.attempts + 1;
      const newSuccessfulHits = prev.successfulHits + (isSuccess ? 1 : 0);
      const newScore = newAttempts > 0 ? Math.round((newSuccessfulHits / newAttempts) * 100) : 0;

      return {
        ...prev,
        currentValue,
        accuracy,
        feedback,
        attempts: newAttempts,
        successfulHits: newSuccessfulHits,
        score: newScore
      };
    });

    if (isSuccess && onTargetHit) {
      onTargetHit(accuracy);
    }
  }, [testState, yAxisUnit, onTargetHit]);

  // Y축 단위 변경 시 타겟 값들 재계산
  useEffect(() => {
    if (!testState.isActive) return;

    if (testState.mode === 'single' && testState.targetValue !== null) {
      // 기존 세미톤 값을 기준으로 새 단위 계산
      const semitoneValue = yAxisUnit === 'semitone' ? testState.targetValue : 
        12 * Math.log2((200 * Math.pow(2, (testState.targetValue - 12) / 12)) / 200);
      
      const newValue = yAxisUnit === 'semitone' ? semitoneValue : f0ToQt(Math.pow(2, semitoneValue / 12) * 200);
      
      setTestState(prev => ({
        ...prev,
        targetValue: newValue,
        feedback: `목표: ${newValue.toFixed(1)}${yAxisUnit === 'semitone' ? 'st' : 'qt'}에 맞춰주세요`
      }));
    }
  }, [yAxisUnit, testState.isActive, testState.mode, testState.targetValue]);

  return (
    <div className={`pitch-test-mode ${className}`}>
      {/* 모드 선택 버튼들 */}
      <div className="card mb-3">
        <div className="card-header">
          <h6 className="mb-0">
            <i className="fas fa-bullseye me-2"></i>피치 테스트 모드
          </h6>
        </div>
        <div className="card-body">
          <div className="row g-2 mb-3">
            <div className="col-md-3">
              <button
                className={`btn btn-sm w-100 ${testState.mode === 'single' ? 'btn-success' : 'btn-outline-success'}`}
                onClick={() => startSinglePointTest(0)}
                disabled={testState.isActive && testState.mode !== 'single'}
              >
                <i className="fas fa-dot-circle me-1"></i>단일 포인트
              </button>
            </div>
            <div className="col-md-3">
              <button
                className={`btn btn-sm w-100 ${testState.mode === 'range' ? 'btn-warning' : 'btn-outline-warning'}`}
                onClick={() => startRangeTest(-2, 3)}
                disabled={testState.isActive && testState.mode !== 'range'}
              >
                <i className="fas fa-arrows-alt-h me-1"></i>범위 테스트
              </button>
            </div>
            <div className="col-md-3">
              <button
                className={`btn btn-sm w-100 ${testState.mode === 'two-point' ? 'btn-info' : 'btn-outline-info'}`}
                onClick={startTwoPointPractice}
                disabled={testState.isActive && testState.mode !== 'two-point'}
              >
                <i className="fas fa-exchange-alt me-1"></i>2포인트 연습
              </button>
            </div>
            <div className="col-md-3">
              <button
                className="btn btn-sm btn-danger w-100"
                onClick={stopTest}
                disabled={!testState.isActive}
              >
                <i className="fas fa-stop me-1"></i>중지
              </button>
            </div>
          </div>

          {/* Y축 단위 선택 */}
          <div className="row g-2 mb-3">
            <div className="col-md-6">
              <label className="form-label">차트 단위:</label>
              <div className="btn-group btn-group-sm w-100">
                <button
                  className={`btn ${yAxisUnit === 'semitone' ? 'btn-primary' : 'btn-outline-primary'}`}
                  onClick={() => setYAxisUnit('semitone')}
                >
                  세미톤 (st)
                </button>
                <button
                  className={`btn ${yAxisUnit === 'qtone' ? 'btn-primary' : 'btn-outline-primary'}`}
                  onClick={() => setYAxisUnit('qtone')}
                >
                  Q-tone (qt)
                </button>
              </div>
            </div>
            <div className="col-md-6">
              <label className="form-label">허용 오차:</label>
              <input
                type="range"
                className="form-range"
                min="0.1"
                max="2.0"
                step="0.1"
                value={targetToleranceRef.current}
                onChange={(e) => {
                  targetToleranceRef.current = parseFloat(e.target.value);
                }}
              />
              <small className="text-muted">{targetToleranceRef.current.toFixed(1)} {yAxisUnit === 'semitone' ? 'st' : 'qt'}</small>
            </div>
          </div>

          {/* 테스트 상태 표시 */}
          {testState.isActive && (
            <div className="row g-2">
              <div className="col-md-8">
                <div className={`alert ${testState.accuracy > 80 ? 'alert-success' : testState.accuracy > 50 ? 'alert-warning' : 'alert-info'} mb-0`}>
                  <strong>{testState.feedback}</strong>
                  <br />
                  <small>
                    현재 값: {testState.currentValue.toFixed(2)}{yAxisUnit === 'semitone' ? 'st' : 'qt'} | 
                    정확도: {testState.accuracy.toFixed(1)}%
                  </small>
                </div>
              </div>
              <div className="col-md-4">
                <div className="text-center">
                  <div className="h5 mb-1">{testState.score}점</div>
                  <small className="text-muted">
                    성공: {testState.successfulHits}/{testState.attempts}
                  </small>
                </div>
              </div>
            </div>
          )}

          {/* 참조선 목록 */}
          {referenceLines.length > 0 && (
            <div className="mt-3">
              <label className="form-label">활성 참조선:</label>
              <div className="d-flex flex-wrap gap-1">
                {referenceLines.map(line => (
                  <span key={line.id} className="badge bg-secondary">
                    {line.label}: {line.value.toFixed(1)}{yAxisUnit === 'semitone' ? 'st' : 'qt'}
                    <button
                      className="btn-close btn-close-white ms-1"
                      style={{ fontSize: '0.6rem' }}
                      onClick={() => removeReferenceLine(line.id)}
                    ></button>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default PitchTestMode;