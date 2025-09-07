/**
 * ToneBridge Advanced Pitch Analysis Engine
 * Converted from vanilla JS to TypeScript
 * 
 * Original: backend/static/js/audio-analysis.js (lines 150-308)
 * Advanced YIN pitch detection algorithm implementation
 */

export interface PitchDetectionConfig {
  frameMs: number;
  hopMs: number;
  windowType: 'hanning' | 'hamming' | 'blackman';
  maxF0: number;
  minF0: number;
  voicingThreshold: number;
  confidenceThreshold: number;
}

export interface PitchResult {
  f0: number;
  confidence: number;
  timestamp: number;
  voicing: boolean;
  snr?: number;
  periodicity?: number;
}

/**
 * 고급 YIN 피치 검출 클래스
 * 원본: class YINPitchDetector (lines 150-308)
 */
export class YINPitchDetector {
  private readonly config: PitchDetectionConfig;
  private readonly sampleRate: number;
  private previousF0: number = 0;
  private pitchBuffer: number[] = [];
  private readonly bufferSize: number = 5;

  constructor(sampleRate: number, config?: Partial<PitchDetectionConfig>) {
    this.sampleRate = sampleRate;
    this.config = {
      frameMs: 25,   // 🎯 VocalPitchMonitor 스타일: 20-40ms 최적화
      hopMs: 10,     // 10ms hop for real-time
      windowType: 'hanning',
      maxF0: 500,
      minF0: 50,
      voicingThreshold: 0.45,    // 🎯 음성/무음성 임계값
      confidenceThreshold: 0.6,  // 🎯 신뢰도 임계값
      ...config
    };
  }

  /**
   * 프레임에서 피치 검출
   * 원본: detectPitch() 메서드
   */
  public detectPitch(audioFrame: Float32Array, timestamp: number): PitchResult {
    try {
      // 1. 전처리
      const preprocessedFrame = this.adaptivePreprocess(audioFrame);
      
      // 2. 향상된 YIN 알고리즘 적용
      const f0 = this.enhancedYinPitch(preprocessedFrame);
      
      // 3. 신뢰도 필터링
      const confidence = this.pitchConfidenceFilter(f0, preprocessedFrame);
      
      // 4. 스무딩 필터
      const smoothedF0 = this.pitchSmoothingFilter(f0);
      
      // 5. 음성 활동 감지
      const voicing = confidence > this.config.voicingThreshold;
      
      // 6. SNR 계산
      const snr = this.calculateSNR(preprocessedFrame);
      
      // 7. 주기성 검사
      const periodicity = this.checkPeriodicity(preprocessedFrame, smoothedF0);

      return {
        f0: voicing ? smoothedF0 : 0,
        confidence,
        timestamp,
        voicing,
        snr,
        periodicity
      };
    } catch (error) {
      console.warn('피치 검출 오류:', error);
      return {
        f0: 0,
        confidence: 0,
        timestamp,
        voicing: false
      };
    }
  }

  /**
   * 적응형 전처리
   * 원본: adaptivePreprocess() (lines 587-612)
   */
  private adaptivePreprocess(frame: Float32Array): Float32Array {
    const processed = new Float32Array(frame.length);
    
    // 1. DC 제거
    let sum = 0;
    for (let i = 0; i < frame.length; i++) {
      sum += frame[i];
    }
    const dcOffset = sum / frame.length;
    
    // 2. 윈도윙 적용
    for (let i = 0; i < frame.length; i++) {
      const windowValue = this.getWindowValue(i, frame.length);
      processed[i] = (frame[i] - dcOffset) * windowValue;
    }
    
    // 3. 정규화
    let maxAbs = 0;
    for (let i = 0; i < processed.length; i++) {
      maxAbs = Math.max(maxAbs, Math.abs(processed[i]));
    }
    
    if (maxAbs > 0) {
      for (let i = 0; i < processed.length; i++) {
        processed[i] /= maxAbs;
      }
    }
    
    return processed;
  }

  /**
   * 향상된 YIN 알고리즘
   * 원본: enhancedYinPitch() (lines 531-586)
   */
  private enhancedYinPitch(frame: Float32Array): number {
    const frameLength = frame.length;
    const maxLag = Math.floor(this.sampleRate / this.config.minF0);
    const minLag = Math.floor(this.sampleRate / this.config.maxF0);
    
    // YIN difference function
    const diff = new Float32Array(maxLag);
    for (let tau = minLag; tau < maxLag; tau++) {
      let sum = 0;
      for (let j = 0; j < frameLength - tau; j++) {
        const delta = frame[j] - frame[j + tau];
        sum += delta * delta;
      }
      diff[tau] = sum;
    }
    
    // Cumulative mean normalized difference
    const cmndf = new Float32Array(maxLag);
    cmndf[0] = 1;
    
    let runningSum = 0;
    for (let tau = 1; tau < maxLag; tau++) {
      runningSum += diff[tau];
      if (runningSum === 0) {
        cmndf[tau] = 1;
      } else {
        cmndf[tau] = diff[tau] * tau / runningSum;
      }
    }
    
    // 최소값 찾기 (임계값 이하)
    let minTau = -1;
    const threshold = this.config.voicingThreshold;
    
    for (let tau = minLag; tau < maxLag; tau++) {
      if (cmndf[tau] < threshold) {
        minTau = tau;
        break;
      }
    }
    
    if (minTau === -1) {
      // 절대 최소값 찾기
      let minValue = cmndf[minLag];
      minTau = minLag;
      
      for (let tau = minLag + 1; tau < maxLag; tau++) {
        if (cmndf[tau] < minValue) {
          minValue = cmndf[tau];
          minTau = tau;
        }
      }
    }
    
    // 파라볼릭 보간으로 정밀도 향상
    const refinedTau = this.parabolicInterpolation(cmndf, minTau);
    
    return this.sampleRate / refinedTau;
  }

  /**
   * 파라볼릭 보간
   * 원본: parabolicInterpolation() (lines 612-627)
   */
  private parabolicInterpolation(data: Float32Array, peak: number): number {
    if (peak <= 0 || peak >= data.length - 1) {
      return peak;
    }
    
    const y1 = data[peak - 1];
    const y2 = data[peak];
    const y3 = data[peak + 1];
    
    const a = (y1 - 2 * y2 + y3) / 2;
    const b = (y3 - y1) / 2;
    
    if (Math.abs(a) < 1e-10) {
      return peak;
    }
    
    const xOffset = -b / (2 * a);
    return peak + xOffset;
  }

  /**
   * 피치 신뢰도 필터
   * 원본: pitchConfidenceFilter() (lines 627-645)
   */
  private pitchConfidenceFilter(f0: number, frame: Float32Array): number {
    if (f0 <= 0 || f0 < this.config.minF0 || f0 > this.config.maxF0) {
      return 0;
    }
    
    // SNR 기반 신뢰도
    const snr = this.calculateSNR(frame);
    const snrConfidence = Math.min(1, Math.max(0, (snr - 5) / 15)); // 5-20 dB 범위
    
    // 주기성 기반 신뢰도
    const periodicity = this.checkPeriodicity(frame, f0);
    
    // 일관성 기반 신뢰도 (이전 프레임과 비교)
    let consistencyConfidence = 1;
    if (this.previousF0 > 0) {
      const ratio = Math.max(f0 / this.previousF0, this.previousF0 / f0);
      consistencyConfidence = Math.exp(-Math.pow(ratio - 1, 2) / 0.2);
    }
    
    return snrConfidence * periodicity * consistencyConfidence;
  }

  /**
   * 피치 스무딩 필터
   * 원본: pitchSmoothingFilter() (lines 645-668)
   */
  private pitchSmoothingFilter(f0: number): number {
    this.pitchBuffer.push(f0);
    
    if (this.pitchBuffer.length > this.bufferSize) {
      this.pitchBuffer.shift();
    }
    
    // 미디언 필터 + 평균 필터
    const sorted = [...this.pitchBuffer].sort((a, b) => a - b);
    const median = sorted[Math.floor(sorted.length / 2)];
    
    const average = this.pitchBuffer.reduce((sum, val) => sum + val, 0) / this.pitchBuffer.length;
    
    // 가중 평균 (미디언 70%, 평균 30%)
    const smoothed = median * 0.7 + average * 0.3;
    
    this.previousF0 = smoothed;
    return smoothed;
  }

  /**
   * SNR 계산
   * 원본: calculateSNR() (lines 668-696)
   */
  private calculateSNR(frame: Float32Array): number {
    // 신호 파워 계산
    let signalPower = 0;
    for (let i = 0; i < frame.length; i++) {
      signalPower += frame[i] * frame[i];
    }
    signalPower /= frame.length;
    
    // 잡음 파워 추정 (프레임의 하위 10%ile)
    const sorted = Array.from(frame).map(x => x * x).sort((a, b) => a - b);
    const noiseIndex = Math.floor(sorted.length * 0.1);
    const noisePower = sorted[noiseIndex];
    
    if (noisePower <= 0) {
      return 40; // 높은 SNR 가정
    }
    
    return 10 * Math.log10(signalPower / noisePower);
  }

  /**
   * 주기성 검사
   * 원본: checkPeriodicity() (lines 696-717)
   */
  private checkPeriodicity(frame: Float32Array, f0: number): number {
    if (f0 <= 0) return 0;
    
    const period = Math.round(this.sampleRate / f0);
    if (period >= frame.length / 2) return 0;
    
    // 자기상관 계산
    let correlation = 0;
    let norm1 = 0;
    let norm2 = 0;
    
    const samples = Math.min(frame.length - period, period * 3);
    
    for (let i = 0; i < samples; i++) {
      correlation += frame[i] * frame[i + period];
      norm1 += frame[i] * frame[i];
      norm2 += frame[i + period] * frame[i + period];
    }
    
    const normProduct = Math.sqrt(norm1 * norm2);
    if (normProduct === 0) return 0;
    
    return Math.max(0, correlation / normProduct);
  }

  /**
   * 윈도우 함수 값 계산
   */
  private getWindowValue(index: number, length: number): number {
    const n = index / (length - 1);
    
    switch (this.config.windowType) {
      case 'hanning':
        return 0.5 - 0.5 * Math.cos(2 * Math.PI * n);
      case 'hamming':
        return 0.54 - 0.46 * Math.cos(2 * Math.PI * n);
      case 'blackman':
        return 0.42 - 0.5 * Math.cos(2 * Math.PI * n) + 0.08 * Math.cos(4 * Math.PI * n);
      default:
        return 1; // 사각 윈도우
    }
  }

  /**
   * 설정 업데이트
   */
  public updateConfig(newConfig: Partial<PitchDetectionConfig>): void {
    Object.assign(this.config, newConfig);
  }

  /**
   * 상태 리셋
   */
  public reset(): void {
    this.previousF0 = 0;
    this.pitchBuffer = [];
  }
}