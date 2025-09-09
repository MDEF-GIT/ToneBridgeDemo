"""
ToneBridge 음성 분석 핵심 모듈

재사용 가능한 음성 분석 도구들:
- STT 기반 정밀 분절 (STTBasedSegmenter)
- 음성학적 분절 폴백 (FallbackSyllableSegmenter)
- 음성 특징 추출 (AudioFeatureExtractor) 
- 음절 경계 탐지 (SyllableBoundaryDetector)
- TextGrid 생성 (TextGridGenerator)

의존성 없이 어디서든 import하여 사용 가능
"""

import numpy as np
import parselmouth as pm
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass
import tempfile
import os

# STT 기반 정확한 분절을 위한 모듈
try:
    from advanced_stt_processor import AdvancedSTTProcessor
    STT_AVAILABLE = True
except ImportError:
    STT_AVAILABLE = False
    print("⚠️ STT 모듈 미설치 - 폴백 분절 사용")

@dataclass
class SyllableSegment:
    """음절 구간 정보"""
    label: str
    start: float
    end: float
    duration: float
    confidence: float = 1.0

@dataclass
class AudioFeatures:
    """음성 특징 데이터"""
    intensity_times: np.ndarray
    intensity_values: np.ndarray
    pitch_times: np.ndarray
    pitch_values: np.ndarray
    duration: float
    valid_speech_start: float
    valid_speech_end: float

class HighPrecisionAudioAnalyzer:
    """
    고정밀 음성학적 분석 클래스
    - 스펙트럼 분석
    - 포먼트 분석  
    - 에너지/피치 정밀 분석
    - 음성학적 경계 탐지
    
    사용법:
        analyzer = HighPrecisionAudioAnalyzer()
        segments = analyzer.analyze_and_segment(audio_file, sentence)
    """
    
    def __init__(self, 
                 pitch_floor: float = 75.0, 
                 pitch_ceiling: float = 600.0,
                 formant_max_freq: float = 5500.0,
                 window_length: float = 0.025,
                 time_step: float = 0.01):
        self.pitch_floor = pitch_floor
        self.pitch_ceiling = pitch_ceiling
        self.formant_max_freq = formant_max_freq
        self.window_length = window_length
        self.time_step = time_step
        
    def analyze_and_segment(self, audio_file: str, sentence: str) -> List[SyllableSegment]:
        """
        WAV 파일을 정밀 분석하여 고정밀 음절 분절 수행
        
        Args:
            audio_file: WAV 파일 경로
            sentence: 목표 문장
            
        Returns:
            고정밀 음절 분절 결과
        """
        try:
            print(f"🔬 고정밀 음성학적 분석 시작: {sentence}")
            
            # 1. 음성 로드 및 기본 정보
            sound = pm.Sound(audio_file)
            syllables = list(sentence.replace(' ', ''))
            duration = sound.get_total_duration()
            
            print(f"📊 음성 길이: {duration:.3f}초, 목표 음절: {len(syllables)}개")
            
            # 2. 다차원 음성학적 분석
            audio_features = self._extract_comprehensive_features(sound)
            
            # 3. 정밀 음절 경계 탐지
            boundaries = self._detect_precise_syllable_boundaries(
                audio_features, len(syllables)
            )
            
            # 4. 음절 분절 결과 생성
            segments = []
            for i, syllable in enumerate(syllables):
                start = boundaries[i]
                end = boundaries[i + 1] if i + 1 < len(boundaries) else duration
                
                # 음절별 품질 점수 계산
                quality_score = self._calculate_segment_quality(
                    audio_features, start, end
                )
                
                segments.append(SyllableSegment(
                    label=syllable,
                    start=start,
                    end=end,
                    duration=end - start,
                    confidence=quality_score
                ))
                
                print(f"   🎯 '{syllable}': {start:.3f}s ~ {end:.3f}s (품질: {quality_score:.2f})")
            
            print(f"✅ 고정밀 분절 완료: {len(segments)}개 음절")
            return segments
            
        except Exception as e:
            print(f"❌ 고정밀 분석 실패: {e}")
            raise
    
    def _extract_comprehensive_features(self, sound: pm.Sound) -> Dict[str, Any]:
        """음성의 종합적 특징 추출"""
        try:
            print("📈 종합 음성학적 특징 추출 중...")
            
            # 1. 기본 피치/강도 분석
            pitch = sound.to_pitch(
                pitch_floor=self.pitch_floor, 
                pitch_ceiling=self.pitch_ceiling,
                time_step=self.time_step
            )
            intensity = sound.to_intensity(time_step=self.time_step)
            
            # 2. 포먼트 분석
            formant = sound.to_formant_burg(
                time_step=self.time_step,
                max_formant=self.formant_max_freq
            )
            
            # 3. 스펙트럼 분석
            spectrogram = sound.to_spectrogram(
                window_length=self.window_length,
                time_step=self.time_step
            )
            
            # 4. 시간 축 정렬
            times = pitch.xs()
            
            # 5. 특징 데이터 추출
            features = {
                'times': times,
                'pitch_values': pitch.selected_array['frequency'],
                'intensity_values': intensity.values.T.flatten(),
                'formant_data': self._extract_formant_features(formant),
                'spectral_data': self._extract_spectral_features(spectrogram, times),
                'energy_change': self._calculate_energy_changes(intensity),
                'pitch_change': self._calculate_pitch_changes(pitch),
                'duration': sound.get_total_duration()
            }
            
            print(f"✅ 특징 추출 완료: {len(times)}개 시간 프레임")
            return features
            
        except Exception as e:
            print(f"❌ 특징 추출 실패: {e}")
            raise
    
    def _extract_formant_features(self, formant) -> Dict[str, np.ndarray]:
        """포먼트 특징 추출"""
        try:
            times = formant.xs()
            
            # F1, F2, F3 추출
            f1_values = []
            f2_values = []
            f3_values = []
            
            for t in times:
                try:
                    f1 = formant.get_value_at_time(1, t)
                    f2 = formant.get_value_at_time(2, t) 
                    f3 = formant.get_value_at_time(3, t)
                    
                    f1_values.append(f1 if f1 != None else 0)
                    f2_values.append(f2 if f2 != None else 0)
                    f3_values.append(f3 if f3 != None else 0)
                except:
                    f1_values.append(0)
                    f2_values.append(0)
                    f3_values.append(0)
            
            return {
                'f1': np.array(f1_values),
                'f2': np.array(f2_values),
                'f3': np.array(f3_values),
                'times': times
            }
            
        except Exception as e:
            print(f"⚠️ 포먼트 추출 실패: {e}")
            return {'f1': np.array([]), 'f2': np.array([]), 'f3': np.array([])}
    
    def _extract_spectral_features(self, spectrogram, times) -> Dict[str, np.ndarray]:
        """스펙트럼 특징 추출"""
        try:
            # 스펙트럴 중심, 롤오프, 플럭스 등 계산
            spectral_centroid = []
            spectral_rolloff = []
            spectral_flux = []
            
            n_frames = len(times)
            freq_resolution = spectrogram.get_frequency_from_bin_number(1)
            
            for i in range(n_frames):
                try:
                    # 해당 시간 프레임의 스펙트럼
                    spectrum = spectrogram.values[:, i] if i < spectrogram.values.shape[1] else np.zeros(spectrogram.values.shape[0])
                    
                    # 스펙트럴 중심
                    freqs = np.arange(len(spectrum)) * freq_resolution
                    if np.sum(spectrum) > 0:
                        centroid = np.sum(freqs * spectrum) / np.sum(spectrum)
                    else:
                        centroid = 0
                    spectral_centroid.append(centroid)
                    
                    # 스펙트럴 롤오프 (85% 에너지 지점)
                    cumsum = np.cumsum(spectrum)
                    total_energy = cumsum[-1]
                    if total_energy > 0:
                        rolloff_idx = np.where(cumsum >= 0.85 * total_energy)[0]
                        rolloff = rolloff_idx[0] * freq_resolution if len(rolloff_idx) > 0 else 0
                    else:
                        rolloff = 0
                    spectral_rolloff.append(rolloff)
                    
                    # 스펙트럴 플럭스 (이전 프레임과의 차이)
                    if i > 0:
                        prev_spectrum = spectrogram.values[:, i-1] if i-1 < spectrogram.values.shape[1] else np.zeros_like(spectrum)
                        flux = np.sum((spectrum - prev_spectrum) ** 2)
                    else:
                        flux = 0
                    spectral_flux.append(flux)
                    
                except:
                    spectral_centroid.append(0)
                    spectral_rolloff.append(0)
                    spectral_flux.append(0)
            
            return {
                'centroid': np.array(spectral_centroid),
                'rolloff': np.array(spectral_rolloff),
                'flux': np.array(spectral_flux)
            }
            
        except Exception as e:
            print(f"⚠️ 스펙트럼 분석 실패: {e}")
            return {'centroid': np.array([]), 'rolloff': np.array([]), 'flux': np.array([])}
    
    def _calculate_energy_changes(self, intensity) -> np.ndarray:
        """에너지 변화율 계산"""
        try:
            values = intensity.values.T.flatten()
            # 1차 미분 (변화율)
            energy_diff = np.abs(np.diff(values))
            # 패딩으로 길이 맞춤
            energy_changes = np.pad(energy_diff, (1, 0), mode='constant', constant_values=0)
            return energy_changes
        except:
            return np.array([])
    
    def _calculate_pitch_changes(self, pitch) -> np.ndarray:
        """피치 변화율 계산 (세미톤 단위)"""
        try:
            values = pitch.selected_array['frequency']
            valid_mask = values > 0
            
            if np.sum(valid_mask) < 2:
                return np.zeros_like(values)
            
            # 세미톤 변환
            semitones = np.zeros_like(values)
            semitones[valid_mask] = 12 * np.log2(values[valid_mask] / 440) + 69
            
            # 변화율 계산
            pitch_diff = np.abs(np.diff(semitones))
            pitch_changes = np.pad(pitch_diff, (1, 0), mode='constant', constant_values=0)
            
            return pitch_changes
        except:
            return np.array([])
    
    def _detect_precise_syllable_boundaries(self, features: Dict[str, Any], num_syllables: int) -> List[float]:
        """
        다차원 음성학적 특징을 종합한 정밀 음절 경계 탐지
        """
        try:
            print("🎯 정밀 경계 탐지 중...")
            
            times = features['times']
            duration = features['duration']
            
            # 1. 유효 음성 구간 탐지 (무음 제거)
            speech_start, speech_end = self._detect_speech_region(features)
            print(f"🔇 음성 구간: {speech_start:.3f}s ~ {speech_end:.3f}s")
            
            # 2. 다차원 경계 점수 계산
            boundary_scores = self._calculate_boundary_scores(features, speech_start, speech_end)
            
            # 3. 피크 탐지로 후보 경계점 추출
            candidate_boundaries = self._find_boundary_candidates(boundary_scores, times, speech_start, speech_end)
            
            # 4. 목표 음절 수에 맞게 최적화
            optimized_boundaries = self._optimize_boundaries_for_syllables(
                candidate_boundaries, num_syllables, speech_start, speech_end
            )
            
            print(f"✅ 경계 탐지 완료: {len(optimized_boundaries)-1}개 구간")
            return optimized_boundaries
            
        except Exception as e:
            print(f"❌ 경계 탐지 실패, 균등 분할 사용: {e}")
            # 폴백: 균등 분할
            boundaries = []
            for i in range(num_syllables + 1):
                boundaries.append(i * duration / num_syllables)
            return boundaries
    
    def _detect_speech_region(self, features: Dict[str, Any]) -> Tuple[float, float]:
        """유효 음성 구간 탐지"""
        try:
            times = features['times']
            intensity_values = features['intensity_values']
            
            # 강도 기반 무음 임계값 설정
            valid_intensity = intensity_values[intensity_values > 0]
            if len(valid_intensity) == 0:
                return 0.0, features['duration']
            
            mean_intensity = np.mean(valid_intensity)
            silence_threshold = mean_intensity * 0.3  # 30% 이하를 무음으로 판정
            
            # 연속된 음성 구간 찾기
            speech_mask = intensity_values > silence_threshold
            
            if not np.any(speech_mask):
                return 0.0, features['duration']
            
            # 첫 번째와 마지막 음성 프레임 찾기
            speech_indices = np.where(speech_mask)[0]
            start_idx = speech_indices[0]
            end_idx = speech_indices[-1]
            
            # 시간으로 변환 (약간의 마진 추가)
            start_time = max(0, times[start_idx] - 0.05)
            end_time = min(features['duration'], times[end_idx] + 0.05)
            
            return start_time, end_time
            
        except Exception as e:
            print(f"⚠️ 음성 구간 탐지 실패: {e}")
            return 0.0, features['duration']
    
    def _calculate_boundary_scores(self, features: Dict[str, Any], start_time: float, end_time: float) -> np.ndarray:
        """다차원 특징을 종합한 경계 점수 계산"""
        try:
            times = features['times']
            
            # 관심 구간 마스크
            time_mask = (times >= start_time) & (times <= end_time)
            
            if not np.any(time_mask):
                return np.zeros(len(times))
            
            # 각 특징별 경계 점수 계산
            scores = np.zeros(len(times))
            
            # 1. 에너지 변화 점수 (가중치: 0.3)
            energy_scores = self._normalize_array(features['energy_change'])
            scores += 0.3 * energy_scores
            
            # 2. 피치 변화 점수 (가중치: 0.25)
            pitch_scores = self._normalize_array(features['pitch_change'])
            scores += 0.25 * pitch_scores
            
            # 3. 스펙트럴 플럭스 점수 (가중치: 0.2)
            if 'spectral_data' in features and 'flux' in features['spectral_data']:
                flux_scores = self._normalize_array(features['spectral_data']['flux'])
                if len(flux_scores) == len(scores):
                    scores += 0.2 * flux_scores
            
            # 4. 포먼트 변화 점수 (가중치: 0.15)
            if 'formant_data' in features:
                formant_scores = self._calculate_formant_change_scores(features['formant_data'])
                if len(formant_scores) == len(scores):
                    scores += 0.15 * formant_scores
            
            # 5. 스펙트럴 중심 변화 점수 (가중치: 0.1)
            if 'spectral_data' in features and 'centroid' in features['spectral_data']:
                centroid_change = np.abs(np.diff(features['spectral_data']['centroid']))
                centroid_scores = np.pad(centroid_change, (1, 0), mode='constant', constant_values=0)
                centroid_scores = self._normalize_array(centroid_scores)
                if len(centroid_scores) == len(scores):
                    scores += 0.1 * centroid_scores
            
            # 관심 구간 외부는 0으로 설정
            scores[~time_mask] = 0
            
            return scores
            
        except Exception as e:
            print(f"⚠️ 경계 점수 계산 실패: {e}")
            return np.zeros(len(features['times']))
    
    def _normalize_array(self, arr: np.ndarray) -> np.ndarray:
        """배열 정규화 (0~1 범위)"""
        try:
            if len(arr) == 0:
                return arr
            
            arr_min, arr_max = np.min(arr), np.max(arr)
            if arr_max == arr_min:
                return np.zeros_like(arr)
            
            return (arr - arr_min) / (arr_max - arr_min)
        except:
            return np.zeros_like(arr)
    
    def _calculate_formant_change_scores(self, formant_data: Dict[str, np.ndarray]) -> np.ndarray:
        """포먼트 변화 기반 점수 계산"""
        try:
            f1, f2 = formant_data['f1'], formant_data['f2']
            
            if len(f1) == 0 or len(f2) == 0:
                return np.array([])
            
            # F1, F2 변화율 계산
            f1_change = np.abs(np.diff(f1))
            f2_change = np.abs(np.diff(f2))
            
            # 조합된 포먼트 변화 점수
            formant_change = np.sqrt(f1_change**2 + f2_change**2)
            formant_scores = np.pad(formant_change, (1, 0), mode='constant', constant_values=0)
            
            return self._normalize_array(formant_scores)
            
        except Exception as e:
            return np.array([])
    
    def _find_boundary_candidates(self, boundary_scores: np.ndarray, times: np.ndarray, 
                                  start_time: float, end_time: float) -> List[float]:
        """경계 점수에서 후보 경계점 추출"""
        try:
            if len(boundary_scores) == 0:
                return [start_time, end_time]
            
            # 적응적 임계값 설정
            score_mean = np.mean(boundary_scores[boundary_scores > 0])
            score_std = np.std(boundary_scores[boundary_scores > 0])
            threshold = score_mean + 0.5 * score_std
            
            # 피크 탐지 (local maxima)
            candidates = []
            window_size = max(3, len(boundary_scores) // 50)  # 적응적 윈도우 크기
            
            for i in range(window_size, len(boundary_scores) - window_size):
                if boundary_scores[i] > threshold:
                    # 지역 최대값 확인
                    local_region = boundary_scores[i-window_size:i+window_size+1]
                    if boundary_scores[i] == np.max(local_region):
                        candidates.append(times[i])
            
            # 시작점과 끝점 추가
            candidates = [start_time] + [c for c in candidates if start_time < c < end_time] + [end_time]
            
            return sorted(list(set(candidates)))
            
        except Exception as e:
            print(f"⚠️ 후보 경계점 추출 실패: {e}")
            return [start_time, end_time]
    
    def _optimize_boundaries_for_syllables(self, candidates: List[float], target_syllables: int,
                                           start_time: float, end_time: float) -> List[float]:
        """목표 음절 수에 맞게 경계점 최적화"""
        try:
            current_segments = len(candidates) - 1
            
            if current_segments == target_syllables:
                return candidates
            elif current_segments > target_syllables:
                # 너무 많은 경계 - 가장 중요한 것들만 선택
                return self._select_best_boundaries(candidates, target_syllables)
            else:
                # 부족한 경계 - 추가 분할
                return self._add_boundaries(candidates, target_syllables, start_time, end_time)
                
        except Exception as e:
            print(f"⚠️ 경계 최적화 실패: {e}")
            # 폴백: 균등 분할
            boundaries = []
            for i in range(target_syllables + 1):
                boundaries.append(start_time + (end_time - start_time) * i / target_syllables)
            return boundaries
    
    def _select_best_boundaries(self, candidates: List[float], target_syllables: int) -> List[float]:
        """가장 적절한 경계점들 선택"""
        if len(candidates) <= target_syllables + 1:
            return candidates
        
        # 첫 번째와 마지막은 항상 유지
        result = [candidates[0]]
        
        # 중간 경계들을 균등하게 선택
        middle_candidates = candidates[1:-1]
        if middle_candidates and target_syllables > 1:
            indices = np.linspace(0, len(middle_candidates)-1, target_syllables-1, dtype=int)
            for idx in indices:
                result.append(middle_candidates[idx])
        
        result.append(candidates[-1])
        return sorted(result)
    
    def _add_boundaries(self, candidates: List[float], target_syllables: int,
                       start_time: float, end_time: float) -> List[float]:
        """부족한 경계점 추가"""
        result = candidates[:]
        
        while len(result) - 1 < target_syllables:
            # 가장 긴 구간 찾기
            max_length = 0
            max_idx = 0
            
            for i in range(len(result) - 1):
                length = result[i + 1] - result[i]
                if length > max_length:
                    max_length = length
                    max_idx = i
            
            # 중간점 추가
            mid_point = (result[max_idx] + result[max_idx + 1]) / 2
            result.insert(max_idx + 1, mid_point)
        
        return sorted(result)
    
    def _calculate_segment_quality(self, features: Dict[str, Any], start: float, end: float) -> float:
        """음절 구간의 품질 점수 계산"""
        try:
            times = features['times']
            
            # 구간 마스크
            segment_mask = (times >= start) & (times <= end)
            
            if not np.any(segment_mask):
                return 0.5  # 기본 점수
            
            quality_scores = []
            
            # 1. 강도 일관성 (높을수록 좋음)
            segment_intensity = features['intensity_values'][segment_mask]
            if len(segment_intensity) > 1:
                intensity_consistency = 1.0 - (np.std(segment_intensity) / (np.mean(segment_intensity) + 1e-6))
                quality_scores.append(max(0, min(1, intensity_consistency)))
            
            # 2. 피치 안정성
            segment_pitch = features['pitch_values'][segment_mask]
            valid_pitch = segment_pitch[segment_pitch > 0]
            if len(valid_pitch) > 1:
                pitch_stability = 1.0 - (np.std(valid_pitch) / (np.mean(valid_pitch) + 1e-6))
                quality_scores.append(max(0, min(1, pitch_stability)))
            
            # 3. 구간 길이 적절성 (0.1~0.8초가 적절)
            duration = end - start
            if 0.1 <= duration <= 0.8:
                duration_score = 1.0
            elif duration < 0.1:
                duration_score = duration / 0.1
            else:
                duration_score = max(0.3, 0.8 / duration)
            quality_scores.append(duration_score)
            
            # 4. 스펙트럼 일관성
            if 'spectral_data' in features and 'centroid' in features['spectral_data']:
                segment_centroid = features['spectral_data']['centroid'][segment_mask]
                if len(segment_centroid) > 1:
                    centroid_consistency = 1.0 - (np.std(segment_centroid) / (np.mean(segment_centroid) + 1e-6))
                    quality_scores.append(max(0, min(1, centroid_consistency)))
            
            # 평균 품질 점수
            if quality_scores:
                return np.mean(quality_scores)
            else:
                return 0.5
                
        except Exception as e:
            print(f"⚠️ 품질 점수 계산 실패: {e}")
            return 0.5

class AudioFeatureExtractor:
    """
    음성 특징 추출 전용 클래스 (기존 호환성 유지)
    
    사용법:
        extractor = AudioFeatureExtractor()
        features = extractor.extract(sound)
    """
    
    def __init__(self, 
                 pitch_floor: float = 75.0, 
                 pitch_ceiling: float = 600.0,
                 silence_threshold_ratio: float = 0.25):
        self.pitch_floor = pitch_floor
        self.pitch_ceiling = pitch_ceiling
        self.silence_threshold_ratio = silence_threshold_ratio
    
    def extract(self, sound: pm.Sound) -> AudioFeatures:
        """음성에서 핵심 특징들 추출"""
        try:
            # 기본 정보
            duration = sound.get_total_duration()
            start_time = sound.xmin
            end_time = sound.xmax
            
            # 강도(에너지) 분석
            intensity = sound.to_intensity(minimum_pitch=self.pitch_floor)
            intensity_times = intensity.xs()
            intensity_values = intensity.values.T.flatten()
            
            # 피치 분석
            pitch = sound.to_pitch(
                pitch_floor=self.pitch_floor, 
                pitch_ceiling=self.pitch_ceiling
            )
            pitch_times = pitch.xs()
            pitch_values = pitch.selected_array['frequency']
            
            # 유효한 음성 구간 탐지
            valid_start, valid_end = self._find_valid_speech_region(
                intensity_times, intensity_values, start_time, end_time
            )
            
            return AudioFeatures(
                intensity_times=intensity_times,
                intensity_values=intensity_values,
                pitch_times=pitch_times,
                pitch_values=pitch_values,
                duration=duration,
                valid_speech_start=valid_start,
                valid_speech_end=valid_end
            )
            
        except Exception as e:
            raise Exception(f"음성 특징 추출 실패: {e}")
    
    def _find_valid_speech_region(self, times: np.ndarray, values: np.ndarray, 
                                  start_time: float, end_time: float) -> Tuple[float, float]:
        """유효한 음성 구간 탐지 (무음 제거)"""
        try:
            # 무음 임계값 계산
            mean_intensity = np.mean(values[values > 0])
            silence_threshold = mean_intensity * self.silence_threshold_ratio
            
            # 유효한 음성 구간 찾기
            valid_regions = []
            in_speech = False
            speech_start = None
            
            for t, intensity_val in zip(times, values):
                if intensity_val > silence_threshold and not in_speech:
                    speech_start = t
                    in_speech = True
                elif intensity_val <= silence_threshold and in_speech:
                    if speech_start is not None:
                        valid_regions.append((speech_start, t))
                    in_speech = False
                    speech_start = None
            
            # 마지막 구간 처리
            if in_speech and speech_start is not None:
                valid_regions.append((speech_start, end_time))
            
            if not valid_regions:
                return start_time, end_time
            
            # 전체 음성 구간 병합
            speech_start_time = min(r[0] for r in valid_regions)
            speech_end_time = max(r[1] for r in valid_regions)
            
            return speech_start_time, speech_end_time
            
        except Exception as e:
            print(f"⚠️ 음성 구간 탐지 실패: {e}")
            return start_time, end_time

class SyllableBoundaryDetector:
    """
    음절 경계 탐지 전용 클래스
    
    사용법:
        detector = SyllableBoundaryDetector()
        boundaries = detector.detect(features, target_syllable_count)
    """
    
    def __init__(self, 
                 energy_percentile: float = 70.0,
                 pitch_threshold_semitones: float = 1.0):
        self.energy_percentile = energy_percentile
        self.pitch_threshold_semitones = pitch_threshold_semitones
    
    def detect(self, features: AudioFeatures, target_count: int) -> List[float]:
        """음성학적 특징을 종합한 음절 경계 탐지"""
        try:
            # 1. 에너지 변화 기반 경계 탐지
            energy_boundaries = self._find_energy_boundaries(
                features.intensity_times, features.intensity_values,
                features.valid_speech_start, features.valid_speech_end
            )
            
            # 2. 피치 변화 기반 경계 탐지
            pitch_boundaries = self._find_pitch_boundaries(
                features.pitch_times, features.pitch_values,
                features.valid_speech_start, features.valid_speech_end
            )
            
            # 3. 경계점 통합 및 최적화
            all_boundaries = sorted(set(energy_boundaries + pitch_boundaries))
            
            # 시작/끝 보장
            boundaries = [features.valid_speech_start]
            for b in all_boundaries:
                if features.valid_speech_start < b < features.valid_speech_end:
                    boundaries.append(b)
            boundaries.append(features.valid_speech_end)
            
            # 4. 목표 음절 수에 맞춤
            optimized_boundaries = self._optimize_boundaries(boundaries, target_count)
            
            return optimized_boundaries
            
        except Exception as e:
            print(f"❌ 경계 탐지 실패: {e}")
            # 폴백: 균등 분할
            return self._equal_division_fallback(
                features.valid_speech_start, features.valid_speech_end, target_count
            )
    
    def _find_energy_boundaries(self, times: np.ndarray, values: np.ndarray, 
                               start_time: float, end_time: float) -> List[float]:
        """에너지 변화 기반 경계 탐지"""
        try:
            # 관심 구간만 추출
            mask = (times >= start_time) & (times <= end_time)
            region_times = times[mask]
            region_values = values[mask]
            
            if len(region_values) < 10:
                return []
            
            # 1차 미분으로 변화율 계산
            energy_diff = np.abs(np.diff(region_values))
            
            # 변화가 큰 지점 탐지
            threshold = np.percentile(energy_diff, self.energy_percentile)
            peak_indices = []
            
            for i in range(1, len(energy_diff) - 1):
                if (energy_diff[i] > threshold and 
                    energy_diff[i] > energy_diff[i-1] and 
                    energy_diff[i] > energy_diff[i+1]):
                    peak_indices.append(i)
            
            # 시간으로 변환
            boundaries = [float(region_times[idx]) for idx in peak_indices 
                         if idx < len(region_times)]
            
            return boundaries
            
        except Exception as e:
            print(f"❌ 에너지 경계 탐지 실패: {e}")
            return []
    
    def _find_pitch_boundaries(self, times: np.ndarray, values: np.ndarray,
                              start_time: float, end_time: float) -> List[float]:
        """피치 변화 기반 경계 탐지"""
        try:
            # 관심 구간만 추출 (유효한 피치만)
            mask = (times >= start_time) & (times <= end_time) & (values > 0)
            region_times = times[mask]
            region_values = values[mask]
            
            if len(region_values) < 5:
                return []
            
            # 피치 변화율 계산 (세미톤 단위)
            pitch_semitones = 12 * np.log2(region_values / 440) + 69
            pitch_diff = np.abs(np.diff(pitch_semitones))
            
            # 큰 피치 변화 지점 탐지
            boundary_indices = []
            for i in range(len(pitch_diff)):
                if pitch_diff[i] > self.pitch_threshold_semitones:
                    boundary_indices.append(i)
            
            # 시간으로 변환
            boundaries = [float(region_times[idx]) for idx in boundary_indices 
                         if idx < len(region_times)]
            
            return boundaries
            
        except Exception as e:
            print(f"❌ 피치 경계 탐지 실패: {e}")
            return []
    
    def _optimize_boundaries(self, boundaries: List[float], target_count: int) -> List[float]:
        """경계점을 목표 음절 수에 맞게 최적화"""
        try:
            if len(boundaries) <= 2:
                return self._equal_division_fallback(
                    boundaries[0], boundaries[-1], target_count
                )
            
            current_segments = len(boundaries) - 1
            
            if current_segments == target_count:
                return boundaries
            elif current_segments > target_count:
                # 너무 많은 경계 - 가장 강한 것들만 선택
                return self._select_strongest_boundaries(boundaries, target_count)
            else:
                # 부족한 경계 - 긴 구간을 분할
                return self._add_missing_boundaries(boundaries, target_count)
                
        except Exception as e:
            print(f"❌ 경계 최적화 실패: {e}")
            return self._equal_division_fallback(
                boundaries[0], boundaries[-1], target_count
            )
    
    def _select_strongest_boundaries(self, boundaries: List[float], target_count: int) -> List[float]:
        """가장 강한 경계점들만 선택"""
        if len(boundaries) <= target_count + 1:
            return boundaries
            
        # 첫 번째와 마지막은 항상 유지
        result = [boundaries[0]]
        
        # 중간 경계들 중에서 균등하게 선택
        middle = boundaries[1:-1]
        if middle and target_count > 1:
            step = len(middle) / (target_count - 1)
            for i in range(target_count - 1):
                idx = int(i * step)
                if idx < len(middle):
                    result.append(middle[idx])
        
        result.append(boundaries[-1])
        return sorted(result)
    
    def _add_missing_boundaries(self, boundaries: List[float], target_count: int) -> List[float]:
        """부족한 경계점 추가"""
        result = boundaries[:]
        
        while len(result) - 1 < target_count:
            # 가장 긴 구간 찾기
            max_length = 0
            max_idx = 0
            
            for i in range(len(result) - 1):
                length = result[i + 1] - result[i]
                if length > max_length:
                    max_length = length
                    max_idx = i
            
            # 중간점 추가
            mid_point = (result[max_idx] + result[max_idx + 1]) / 2
            result.insert(max_idx + 1, mid_point)
        
        return sorted(result)
    
    def _equal_division_fallback(self, start: float, end: float, target_count: int) -> List[float]:
        """폴백: 균등 분할"""
        result = []
        for i in range(target_count + 1):
            result.append(start + (end - start) * i / target_count)
        return result

class STTBasedSegmenter:
    """
    STT 엔진 기반 정확한 음절 분절 클래스
    
    사용법:
        segmenter = STTBasedSegmenter()
        segments = segmenter.segment_from_audio_file("audio.wav", "반가워요")
    """
    
    def __init__(self):
        if STT_AVAILABLE:
            try:
                self.stt_processor = AdvancedSTTProcessor()
                print("🎯 STT 기반 정밀 분절 활성화")
            except Exception as e:
                print(f"❌ STT 프로세서 초기화 실패: {e}")
                self.stt_processor = None
        else:
            self.stt_processor = None
        
        # 폴백을 위한 기존 분절기
        self.fallback_segmenter = FallbackSyllableSegmenter()
    
    def segment_from_audio_file(self, audio_file: str, sentence: str) -> List[SyllableSegment]:
        """
        오디오 파일에서 STT 기반 정확한 음절 분절
        
        Args:
            audio_file: 오디오 파일 경로
            sentence: 예상 문장 (예: "반가워요")
            
        Returns:
            List[SyllableSegment]: 정확한 타임스탬프가 포함된 음절 분절
        """
        if not self.stt_processor:
            print("⚠️ STT 비활성 - 폴백 분절 사용")
            sound = pm.Sound(audio_file)
            syllables_text = list(sentence.replace(' ', ''))
            return self.fallback_segmenter.segment(sound, syllables_text)
        
        try:
            print(f"🎤 STT 기반 정밀 분절 시작: {sentence}")
            
            # 1. STT로 음성 전사 (타임스탬프 포함)
            transcription_result = self.stt_processor.stt.transcribe(
                audio_file, language='ko', return_timestamps=True
            )
            
            print(f"🎯 STT 결과: '{transcription_result.text}'")
            print(f"🎯 단어 타임스탬프: {len(transcription_result.words)}개")
            
            # 2. 음절 정렬 (STT 타임스탬프 활용)
            syllable_alignments = self.stt_processor.syllable_aligner.align_syllables_with_timestamps(
                transcription_result, audio_file
            )
            
            # 3. SyllableSegment 형식으로 변환
            segments = []
            for alignment in syllable_alignments:
                segments.append(SyllableSegment(
                    label=alignment.syllable,
                    start=alignment.start_time,
                    end=alignment.end_time,
                    duration=alignment.end_time - alignment.start_time,
                    confidence=alignment.confidence
                ))
                
                print(f"   🎯 '{alignment.syllable}': {alignment.start_time:.3f}s ~ {alignment.end_time:.3f}s (신뢰도: {alignment.confidence:.2f})")
            
            print(f"✅ STT 기반 분절 완료: {len(segments)}개 음절")
            return segments
            
        except Exception as e:
            print(f"❌ STT 분절 실패, 폴백 사용: {e}")
            sound = pm.Sound(audio_file)
            syllables_text = list(sentence.replace(' ', ''))
            return self.fallback_segmenter.segment(sound, syllables_text)

class FallbackSyllableSegmenter:
    """
    정밀 음절 분절 메인 클래스
    
    사용법:
        segmenter = FallbackSyllableSegmenter()
        segments = segmenter.segment(sound, syllable_labels)
    """
    
    def __init__(self, **kwargs):
        self.feature_extractor = AudioFeatureExtractor(**kwargs)
        self.boundary_detector = SyllableBoundaryDetector(**kwargs)
    
    def segment(self, sound: pm.Sound, syllable_labels: List[str]) -> List[SyllableSegment]:
        """음성을 정밀하게 음절별로 분절"""
        try:
            print("🔬 정밀 음성학적 분절 시작")
            
            # 1. 음성 특징 추출
            features = self.feature_extractor.extract(sound)
            print(f"🔇 무음 제거: {features.valid_speech_start:.3f}s ~ {features.valid_speech_end:.3f}s")
            
            # 2. 음절 경계 탐지
            boundaries = self.boundary_detector.detect(features, len(syllable_labels))
            print(f"🎯 경계점 탐지: {len(boundaries)-1}개 구간")
            
            # 3. 음절 구간 생성
            segments = []
            for i, label in enumerate(syllable_labels):
                segment = SyllableSegment(
                    label=label,
                    start=boundaries[i],
                    end=boundaries[i + 1],
                    duration=boundaries[i + 1] - boundaries[i]
                )
                segments.append(segment)
                print(f"   🎯 '{label}': {segment.start:.3f}s ~ {segment.end:.3f}s")
            
            print(f"✅ 정밀 분절 완료: {len(segments)}개 음절")
            return segments
            
        except Exception as e:
            print(f"❌ 정밀 분절 실패, 기본 분절로 폴백: {e}")
            return self._fallback_equal_segmentation(sound, syllable_labels)
    
    def _fallback_equal_segmentation(self, sound: pm.Sound, syllable_labels: List[str]) -> List[SyllableSegment]:
        """폴백: 기본 균등 분할"""
        duration = sound.get_total_duration()
        syllable_duration = duration / len(syllable_labels)
        
        segments = []
        for i, label in enumerate(syllable_labels):
            start_time = i * syllable_duration
            end_time = (i + 1) * syllable_duration
            
            if i == len(syllable_labels) - 1:
                end_time = duration
            
            segment = SyllableSegment(
                label=label,
                start=start_time,
                end=end_time,
                duration=end_time - start_time
            )
            segments.append(segment)
        
        return segments

class TextGridGenerator:
    """
    TextGrid 파일 생성 전용 클래스
    
    사용법:
        generator = TextGridGenerator()
        generator.save(segments, output_path, total_duration)
    """
    
    def save(self, segments: List[SyllableSegment], output_path: str, total_duration: float):
        """음절 정보를 TextGrid 파일로 저장"""
        try:
            print(f"💾 TextGrid 저장: {output_path}")
            
            # TextGrid 문자열 생성
            textgrid_content = f'''File type = "ooTextFile"
Object class = "TextGrid"

xmin = 0 
xmax = {total_duration} 
tiers? <exists> 
size = 1 
item []: 
    item [1]:
        class = "IntervalTier" 
        name = "syllables" 
        xmin = 0 
        xmax = {total_duration} 
        intervals: size = {len(segments)} 
'''
            
            # 각 음절 구간 추가
            for i, segment in enumerate(segments):
                textgrid_content += f'''        intervals [{i+1}]:
            xmin = {segment.start} 
            xmax = {segment.end} 
            text = "{segment.label}" 
'''
            
            # 파일 저장
            with open(output_path, 'w', encoding='utf-16') as f:
                f.write(textgrid_content)
            
            print(f"✅ TextGrid 저장 완료: {len(segments)}개 음절")
            
        except Exception as e:
            raise Exception(f"TextGrid 저장 실패: {e}")

def split_korean_sentence(sentence: str) -> List[str]:
    """한국어 문장을 음절 단위로 분리"""
    return [char for char in sentence.strip() if char.strip()]

# 편의 함수들
def analyze_audio_file(audio_path: str, syllable_text: str, **kwargs) -> List[SyllableSegment]:
    """
    오디오 파일을 분석하여 정밀한 음절 분절 수행
    
    Args:
        audio_path: 오디오 파일 경로
        syllable_text: 목표 문장 (예: "반가워요")
        **kwargs: 분석 파라메터 (pitch_floor, pitch_ceiling 등)
    
    Returns:
        음절 구간 리스트
    """
    try:
        print(f"🎯 고정밀 오디오 분석 시작: {syllable_text}")
        
        # 1. 최우선: STT 기반 분절 시도
        try:
            stt_segmenter = STTBasedSegmenter()
            segments = stt_segmenter.segment_from_audio_file(audio_path, syllable_text)
            print("✅ STT 기반 분절 성공")
            return segments
        except Exception as stt_error:
            print(f"⚠️ STT 분절 실패: {stt_error}, 고정밀 분석으로 전환")
        
        # 2. 폴백: 고정밀 음성학적 분석
        analyzer = HighPrecisionAudioAnalyzer(**kwargs)
        segments = analyzer.analyze_and_segment(audio_path, syllable_text)
        
        print("✅ 고정밀 음성학적 분절 완료")
        return segments
        
    except Exception as e:
        raise Exception(f"오디오 분석 실패: {e}")

def create_textgrid_from_audio(audio_path: str, syllable_text: str, 
                              output_path: Optional[str] = None, **kwargs) -> str:
    """
    오디오 파일에서 TextGrid 생성
    
    Args:
        audio_path: 오디오 파일 경로
        syllable_text: 목표 문장
        output_path: TextGrid 저장 경로 (None이면 자동 생성)
        **kwargs: 분석 파라메터
    
    Returns:
        생성된 TextGrid 파일 경로
    """
    try:
        # 음절 분절 수행
        segments = analyze_audio_file(audio_path, syllable_text, **kwargs)
        
        # 출력 경로 생성
        if output_path is None:
            base_name = os.path.splitext(audio_path)[0]
            output_path = f"{base_name}.TextGrid"
        
        # 음성 길이 계산
        sound = pm.Sound(audio_path)
        total_duration = sound.get_total_duration()
        
        # TextGrid 저장
        generator = TextGridGenerator()
        generator.save(segments, output_path, total_duration)
        
        return output_path
        
    except Exception as e:
        raise Exception(f"TextGrid 생성 실패: {e}")