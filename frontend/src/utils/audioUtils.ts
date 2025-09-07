/**
 * ToneBridge Audio Utility Functions
 * Converted from vanilla JS to TypeScript
 * 
 * Original: backend/static/js/audio-analysis.js (lines 2424-2530)
 * Core mathematical and audio processing utilities
 */

/**
 * 배열의 평균 계산
 * 원본: mean() (line 2424)
 */
export function mean(arr: number[]): number {
  if (arr.length === 0) return 0;
  return arr.reduce((sum, val) => sum + val, 0) / arr.length;
}

/**
 * 값을 범위 내로 제한
 * 원본: clamp() (line 2428)
 */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/**
 * F0를 세미톤으로 변환
 * 원본: f0ToSemitone() (line 2433)
 */
export function f0ToSemitone(f0: number, refMedian: number = 200): number {
  if (f0 <= 0 || refMedian <= 0) return 0;
  return 12 * Math.log2(f0 / refMedian);
}

/**
 * F0를 Q-tone으로 변환 (5-등급 시스템)
 * 원본: f0ToQt() (line 2439)
 */
export function f0ToQt(f0: number): number {
  if (f0 <= 0) return 0;
  // Q-tone 공식: 베이스 주파수 대비 로그 스케일
  const baseFreq = 130; // 기준 주파수 (Hz)
  return 5 * Math.log2(f0 / baseFreq);
}

/**
 * Q-tone을 F0로 변환
 * 원본: qtToF0() (line 2447)
 */
export function qtToF0(qt: number): number {
  const baseFreq = 130;
  return baseFreq * Math.pow(2, qt / 5);
}

/**
 * F0 정규화 (0-1 범위)
 * 원본: normF0() (line 2455)
 */
export function normF0(f0: number, meanF0: number, maxF0: number): number {
  if (maxF0 <= 0 || meanF0 <= 0) return 0;
  return Math.min(1, Math.max(0, f0 / maxF0));
}

/**
 * 강도(dB) 정규화
 * 원본: normInt() (line 2463)
 */
export function normInt(db: number): number {
  // -40dB ~ 0dB 범위를 0-1로 정규화
  return Math.min(1, Math.max(0, (db + 40) / 40));
}

/**
 * 프레임 에너지 계산
 * 원본: frameEnergy() (line 2765)
 */
export function frameEnergy(frame: Float32Array): number {
  let energy = 0;
  for (let i = 0; i < frame.length; i++) {
    energy += frame[i] * frame[i];
  }
  return energy / frame.length;
}

/**
 * 성별별 기준 주파수 반환
 * 원본: getGenderBaseFrequency() (line 2057)
 */
export function getGenderBaseFrequency(gender: 'male' | 'female'): number {
  return gender === 'female' ? 220 : 120; // Hz
}

/**
 * 성별별 Hz 범위 반환
 * 원본: getGenderHzRange() (line 2068)
 */
export function getGenderHzRange(gender: 'male' | 'female'): { min: number; max: number } {
  if (gender === 'female') {
    return { min: 165, max: 330 }; // 여성 음성 범위
  } else {
    return { min: 85, max: 180 };  // 남성 음성 범위
  }
}

/**
 * 최적 피치 범위 계산
 * 원본: calculateOptimalRange() (line 2235)
 */
export function calculateOptimalRange(semitoneValues: number[]): { min: number; max: number } {
  if (semitoneValues.length === 0) {
    return { min: -12, max: 15 }; // 기본 범위
  }
  
  const validValues = semitoneValues.filter(val => !isNaN(val) && isFinite(val));
  if (validValues.length === 0) {
    return { min: -12, max: 15 };
  }
  
  const sortedValues = validValues.sort((a, b) => a - b);
  
  // IQR 기반 범위 계산
  const q1Index = Math.floor(sortedValues.length * 0.25);
  const q3Index = Math.floor(sortedValues.length * 0.75);
  const q1 = sortedValues[q1Index];
  const q3 = sortedValues[q3Index];
  const iqr = q3 - q1;
  
  // 아웃라이어 제거를 위한 확장 범위
  const minValue = q1 - 1.5 * iqr;
  const maxValue = q3 + 1.5 * iqr;
  
  return {
    min: Math.max(-20, Math.floor(minValue) - 2), // 최소 -20 세미톤
    max: Math.min(20, Math.ceil(maxValue) + 2)    // 최대 +20 세미톤
  };
}

/**
 * 음성 활동 감지 및 음절 추적
 * 원본: vadSyllableTracker() (line 2775)
 */
export interface SyllableEvent {
  type: 'start' | 'end';
  timestamp: number;
  intensity: number;
}

export class VADSyllableTracker {
  private readonly energyThreshold: number;
  private readonly minSyllableDuration: number; // ms
  private readonly minPauseDuration: number;    // ms
  
  private isInSyllable: boolean = false;
  private syllableStartTime: number = 0;
  private lastEnergyTime: number = 0;
  
  constructor(
    energyThreshold: number = 0.01,
    minSyllableDuration: number = 100,
    minPauseDuration: number = 50
  ) {
    this.energyThreshold = energyThreshold;
    this.minSyllableDuration = minSyllableDuration;
    this.minPauseDuration = minPauseDuration;
  }
  
  /**
   * 프레임 처리 및 음절 이벤트 감지
   */
  public process(intDb: number, timestamp: number): SyllableEvent | null {
    const energy = this.dbToLinear(intDb);
    const isVoiced = energy > this.energyThreshold;
    
    if (isVoiced && !this.isInSyllable) {
      // 음절 시작
      if (timestamp - this.lastEnergyTime > this.minPauseDuration) {
        this.isInSyllable = true;
        this.syllableStartTime = timestamp;
        return {
          type: 'start',
          timestamp,
          intensity: intDb
        };
      }
    } else if (!isVoiced && this.isInSyllable) {
      // 음절 종료
      const syllableDuration = timestamp - this.syllableStartTime;
      if (syllableDuration > this.minSyllableDuration) {
        this.isInSyllable = false;
        return {
          type: 'end',
          timestamp,
          intensity: intDb
        };
      }
    }
    
    if (isVoiced) {
      this.lastEnergyTime = timestamp;
    }
    
    return null;
  }
  
  private dbToLinear(db: number): number {
    return Math.pow(10, db / 20);
  }
  
  public reset(): void {
    this.isInSyllable = false;
    this.syllableStartTime = 0;
    this.lastEnergyTime = 0;
  }
}

/**
 * WAV 파일 생성 유틸리티
 * 원본: createWavBlob(), createWavHeader() (lines 4877-4941)
 */
export class WAVFileGenerator {
  /**
   * AudioBuffer를 WAV Blob으로 변환
   */
  public static createWavBlob(audioBuffer: AudioBuffer, sampleRate: number = 44100): Blob {
    const numChannels = audioBuffer.numberOfChannels;
    const length = audioBuffer.length * numChannels * 2; // 16-bit
    const buffer = new ArrayBuffer(44 + length);
    const view = new DataView(buffer);
    
    // WAV 헤더 작성
    this.writeWavHeader(view, audioBuffer.length, numChannels, sampleRate);
    
    // 오디오 데이터 작성
    let offset = 44;
    for (let i = 0; i < audioBuffer.length; i++) {
      for (let channel = 0; channel < numChannels; channel++) {
        const sample = Math.max(-1, Math.min(1, audioBuffer.getChannelData(channel)[i]));
        const intSample = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
        view.setInt16(offset, intSample, true);
        offset += 2;
      }
    }
    
    return new Blob([buffer], { type: 'audio/wav' });
  }
  
  /**
   * WAV 헤더 작성
   */
  private static writeWavHeader(
    view: DataView, 
    numSamples: number, 
    numChannels: number, 
    sampleRate: number
  ): void {
    const byteRate = sampleRate * numChannels * 2;
    const blockAlign = numChannels * 2;
    const dataSize = numSamples * numChannels * 2;
    
    // RIFF 헤더
    view.setUint32(0, 0x46464952, false); // "RIFF"
    view.setUint32(4, 36 + dataSize, true);
    view.setUint32(8, 0x45564157, false); // "WAVE"
    
    // fmt 청크
    view.setUint32(12, 0x20746d66, false); // "fmt "
    view.setUint32(16, 16, true);          // 청크 크기
    view.setUint16(20, 1, true);           // PCM 포맷
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, 16, true);          // 비트 당 샘플
    
    // data 청크
    view.setUint32(36, 0x61746164, false); // "data"
    view.setUint32(40, dataSize, true);
  }
}

/**
 * 오디오 재생 제어 유틸리티
 */
export class AudioPlaybackController {
  private audioElement: HTMLAudioElement | null = null;
  private onEndCallback?: () => void;
  
  /**
   * 오디오 재생 시작
   */
  public async play(audioBlob: Blob, onEnd?: () => void): Promise<void> {
    this.stop(); // 기존 재생 중지
    
    const audioUrl = URL.createObjectURL(audioBlob);
    this.audioElement = new Audio(audioUrl);
    this.onEndCallback = onEnd;
    
    this.audioElement.onended = () => {
      this.cleanup();
      if (this.onEndCallback) {
        this.onEndCallback();
      }
    };
    
    this.audioElement.onerror = () => {
      console.error('오디오 재생 오류');
      this.cleanup();
    };
    
    try {
      await this.audioElement.play();
    } catch (error) {
      console.error('오디오 재생 실패:', error);
      this.cleanup();
      throw error;
    }
  }
  
  /**
   * 오디오 재생 중지
   */
  public stop(): void {
    if (this.audioElement) {
      this.audioElement.pause();
      this.audioElement.currentTime = 0;
      this.cleanup();
    }
  }
  
  /**
   * 현재 재생 중인지 확인
   */
  public get isPlaying(): boolean {
    return !!(this.audioElement && !this.audioElement.paused);
  }
  
  private cleanup(): void {
    if (this.audioElement) {
      URL.revokeObjectURL(this.audioElement.src);
      this.audioElement = null;
    }
    this.onEndCallback = undefined;
  }
}