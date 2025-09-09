"""
ToneBridge 음성 분석 핵심 모듈

재사용 가능한 음성 분석 도구들:
- 정밀 음절 분절 (PreciseSyllableSegmenter)
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

class AudioFeatureExtractor:
    """
    음성 특징 추출 전용 클래스
    
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
            boundaries = [region_times[idx] for idx in peak_indices 
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
            boundaries = [region_times[idx] for idx in boundary_indices 
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

class PreciseSyllableSegmenter:
    """
    정밀 음절 분절 메인 클래스
    
    사용법:
        segmenter = PreciseSyllableSegmenter()
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
        sound = pm.Sound(audio_path)
        syllable_labels = split_korean_sentence(syllable_text)
        
        segmenter = PreciseSyllableSegmenter(**kwargs)
        return segmenter.segment(sound, syllable_labels)
        
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