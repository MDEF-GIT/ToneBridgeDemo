import { useState, useCallback } from 'react';
import { tonebridgeApi } from '../utils/tonebridgeApi';

interface VoiceRangeData {
  measurement_type: string;
  min_frequency: number;
  max_frequency: number;
  geometric_mean: number;
  log_midpoint: number;
  arithmetic_mean: number;
  total_samples: number;
  valid_samples: number;
  range_semitones: number;
}

interface VowelAnalysisData {
  vowel_type: string;
  fundamental_frequency: number;
  f1_formant: number;
  f2_formant: number;
  f0_std_deviation: number;
  stability_score: number;
  sample_count: number;
}

interface ReferenceFrequencyData {
  reference_frequency: number;
  alternative_reference: number;
  confidence_score: number;
  measurement_count: number;
  individual_measurements: Array<{
    value: number;
    weight: number;
  }>;
}

interface SpeakerProfile {
  userId: string;
  personalReference: number;
  lastMeasurement: string;
  voiceRange?: VoiceRangeData;
  vowelAnalysis: VowelAnalysisData[];
  referenceCalculation?: ReferenceFrequencyData;
  confidence: number;
}

export const useSpeakerProfile = () => {
  const [profile, setProfile] = useState<SpeakerProfile | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 🎵 음역대 측정 (최저음/최고음)
  const measureVoiceRange = useCallback(async (audioFile: File): Promise<VoiceRangeData | null> => {
    try {
      setIsLoading(true);
      setError(null);
      
      console.log('🎵 음역대 측정 시작');
      
      const formData = new FormData();
      formData.append('file', audioFile);
      
      const response = await tonebridgeApi.post('/api/voice-range-measurement', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      const data = response.data as VoiceRangeData;
      console.log(`🎵 음역대 측정 완료: ${data.min_frequency}Hz ~ ${data.max_frequency}Hz (기하평균: ${data.geometric_mean}Hz)`);
      
      // 프로필 업데이트
      if (profile) {
        setProfile(prev => prev ? { ...prev, voiceRange: data } : null);
      }
      
      return data;
      
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || '음역대 측정 실패';
      console.error('❌ 음역대 측정 오류:', errorMsg);
      setError(errorMsg);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [profile]);

  // 🗣️ 모음별 분석 (/아/, /이/, /우/)
  const analyzeVowel = useCallback(async (audioFile: File, vowelType: 'a' | 'i' | 'u'): Promise<VowelAnalysisData | null> => {
    try {
      setIsLoading(true);
      setError(null);
      
      console.log(`🗣️ 모음 /${vowelType}/ 분석 시작`);
      
      const formData = new FormData();
      formData.append('file', audioFile);
      formData.append('vowel_type', vowelType);
      
      const response = await tonebridgeApi.post('/api/vowel-analysis', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      const data = response.data as VowelAnalysisData;
      console.log(`🗣️ 모음 /${vowelType}/ 분석 완료: F0=${data.fundamental_frequency}Hz, 안정성=${data.stability_score}`);
      
      // 프로필에 모음 분석 결과 추가
      if (profile) {
        setProfile(prev => {
          if (!prev) return null;
          const newVowelAnalysis = prev.vowelAnalysis.filter(v => v.vowel_type !== vowelType);
          newVowelAnalysis.push(data);
          return { ...prev, vowelAnalysis: newVowelAnalysis };
        });
      }
      
      return data;
      
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || '모음 분석 실패';
      console.error(`❌ 모음 /${vowelType}/ 분석 오류:`, errorMsg);
      setError(errorMsg);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [profile]);

  // 📊 기하평균 기반 최적 기준 주파수 계산
  const calculateOptimalReference = useCallback(async (comfortablePitch?: number): Promise<ReferenceFrequencyData | null> => {
    try {
      setIsLoading(true);
      setError(null);
      
      if (!profile) {
        throw new Error('프로필이 설정되지 않았습니다');
      }
      
      console.log('📊 최적 기준 주파수 계산 시작');
      
      const measurements: any = {};
      
      // 편안한 발화 주파수
      if (comfortablePitch) {
        measurements.comfortable_pitch = comfortablePitch;
      }
      
      // 음역대 데이터
      if (profile.voiceRange) {
        measurements.voice_range = profile.voiceRange;
      }
      
      // 모음별 분석 데이터
      if (profile.vowelAnalysis.length > 0) {
        measurements.vowel_analysis = profile.vowelAnalysis;
      }
      
      if (Object.keys(measurements).length === 0) {
        throw new Error('기준 주파수 계산에 필요한 측정 데이터가 없습니다');
      }
      
      const response = await tonebridgeApi.post('/api/calculate-reference-frequency', measurements);
      const data = response.data as ReferenceFrequencyData;
      
      console.log(`📊 최적 기준 주파수: ${data.reference_frequency}Hz (신뢰도: ${data.confidence_score})`);
      
      // 프로필 업데이트
      setProfile(prev => prev ? {
        ...prev,
        personalReference: data.reference_frequency,
        referenceCalculation: data,
        confidence: data.confidence_score,
        lastMeasurement: new Date().toISOString()
      } : null);
      
      return data;
      
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || '기준 주파수 계산 실패';
      console.error('❌ 기준 주파수 계산 오류:', errorMsg);
      setError(errorMsg);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [profile]);

  // 👤 새로운 화자 프로필 생성
  const createProfile = useCallback((userId: string, initialReference: number = 200) => {
    const newProfile: SpeakerProfile = {
      userId,
      personalReference: initialReference,
      lastMeasurement: new Date().toISOString(),
      vowelAnalysis: [],
      confidence: 0.5
    };
    
    setProfile(newProfile);
    console.log(`👤 새 화자 프로필 생성: ${userId} (기준: ${initialReference}Hz)`);
  }, []);

  // 💾 프로필 로컬 저장
  const saveProfile = useCallback(() => {
    if (profile) {
      localStorage.setItem('tonebridge_speaker_profile', JSON.stringify(profile));
      console.log('💾 화자 프로필 저장 완료');
    }
  }, [profile]);

  // 📂 프로필 로컬 로드
  const loadProfile = useCallback(() => {
    try {
      const saved = localStorage.getItem('tonebridge_speaker_profile');
      if (saved) {
        const loadedProfile = JSON.parse(saved) as SpeakerProfile;
        setProfile(loadedProfile);
        console.log(`📂 화자 프로필 로드: ${loadedProfile.userId} (기준: ${loadedProfile.personalReference}Hz)`);
        return loadedProfile;
      }
    } catch (err) {
      console.error('❌ 프로필 로드 실패:', err);
      setError('프로필 로드에 실패했습니다');
    }
    return null;
  }, []);

  // 🧹 프로필 초기화
  const clearProfile = useCallback(() => {
    setProfile(null);
    setError(null);
    localStorage.removeItem('tonebridge_speaker_profile');
    console.log('🧹 화자 프로필 초기화 완료');
  }, []);

  // 📈 진행 상황 계산
  const getMeasurementProgress = useCallback(() => {
    if (!profile) return { completed: 0, total: 4, percentage: 0 };
    
    let completed = 0;
    const total = 4; // 편안한 발화, 음역대, 모음 3개
    
    if (profile.personalReference !== 200) completed++; // 기본값이 아니면 측정됨
    if (profile.voiceRange) completed++;
    if (profile.vowelAnalysis.length >= 3) completed++; // 모음 3개 모두
    if (profile.referenceCalculation) completed++;
    
    return {
      completed,
      total,
      percentage: Math.round((completed / total) * 100)
    };
  }, [profile]);

  return {
    profile,
    isLoading,
    error,
    
    // 측정 함수들
    measureVoiceRange,
    analyzeVowel,
    calculateOptimalReference,
    
    // 프로필 관리
    createProfile,
    saveProfile,
    loadProfile,
    clearProfile,
    
    // 유틸리티
    getMeasurementProgress,
    
    // 상태 체크
    hasVoiceRange: !!profile?.voiceRange,
    hasAllVowels: (profile?.vowelAnalysis.length || 0) >= 3,
    hasOptimalReference: !!profile?.referenceCalculation,
    currentReference: profile?.personalReference || 200
  };
};