// 🎯 ToneBridge API 타입 정의
export interface ReferenceFile {
  id: string;
  title: string;
  sentence_text: string;
  duration: number;
  detected_gender: string;
  average_f0: number;
  wav: string;
  textgrid: string;
}

export interface AnalysisResult {
  status: string;
  message?: string;
  duration?: number;
  base_frequency?: number;
  syllable_count?: number;
  pitch_data?: [number, number][];
  syllables?: SyllableData[];
}

export interface SyllableData {
  label: string;
  start_time: number;
  end_time: number;
  duration: number;
  f0_hz: number;
  semitone: number;
}

export interface LearnerInfo {
  name: string;
  gender: string;
  ageGroup: string;
}

export type LearningMethod = 'pitch' | 'sentence' | '';

export interface ChartRange {
  min: number;
  max: number;
}

export interface PitchData {
  time: number;
  frequency: number;
  type: 'reference' | 'live';
}