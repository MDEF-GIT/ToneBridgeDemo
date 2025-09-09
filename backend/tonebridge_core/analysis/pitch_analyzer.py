"""
통합 피치 분석기
기존 피치 분석 기능들을 통합하여 일관된 결과 제공
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional

# 기존 모듈 임포트 (하위 호환성)
sys.path.append(str(Path(__file__).parent.parent.parent))

try:
    import parselmouth as pm
    import numpy as np
    PARSELMOUTH_AVAILABLE = True
except ImportError:
    PARSELMOUTH_AVAILABLE = False

from ..models import SyllableSegment, PitchAnalysis

class UnifiedPitchAnalyzer:
    """
    통합 피치 분석기 - 모든 차트에서 동일한 분석
    """
    
    def __init__(self):
        self.pitch_floor = 75.0
        self.pitch_ceiling = 600.0
        self.time_step = 0.01
    
    def analyze(self, audio_file: str, syllable_segments: List[SyllableSegment] = None) -> PitchAnalysis:
        """
        피치 분석 - 차트별 동일한 결과
        기존 피치 분석 함수들과 호환
        """
        if not PARSELMOUTH_AVAILABLE:
            return self._create_empty_analysis()
        
        try:
            sound = pm.Sound(audio_file)
            pitch = sound.to_pitch_ac(
                time_step=self.time_step,
                pitch_floor=self.pitch_floor,
                pitch_ceiling=self.pitch_ceiling,
                very_accurate=False
            )
            
            # 전체 피치 포인트 추출
            pitch_points = self._extract_pitch_points(pitch)
            
            # 음절별 피치 분석
            syllable_pitches = []
            if syllable_segments:
                syllable_pitches = self._analyze_syllable_pitches(pitch, syllable_segments)
            
            # 통계 계산
            statistics = self._calculate_statistics(pitch_points)
            
            print(f"🎵 피치 분석 완료: {len(pitch_points)}개 포인트, {len(syllable_pitches)}개 음절")
            
            return PitchAnalysis(
                pitch_points=pitch_points,
                syllable_pitches=syllable_pitches,
                statistics=statistics
            )
            
        except Exception as e:
            print(f"❌ 피치 분석 실패: {e}")
            return self._create_empty_analysis()
    
    def _extract_pitch_points(self, pitch: 'pm.Pitch') -> List[Dict]:
        """전체 피치 포인트 추출 - 기존 형식과 호환"""
        points = []
        times = pitch.xs()
        
        for time in times:
            f0 = pitch.get_value_at_time(time)
            if f0 is not None and not np.isnan(f0):
                points.append({
                    'time': time,
                    'frequency': f0
                })
        
        return points
    
    def _analyze_syllable_pitches(self, pitch: 'pm.Pitch', 
                                 segments: List[SyllableSegment]) -> List[Dict]:
        """음절별 피치 분석 - 기존 형식과 호환"""
        syllable_pitches = []
        
        for segment in segments:
            # 음절 구간 내 피치 값들 추출
            segment_f0_values = []
            times = pitch.xs()
            
            for time in times:
                if segment.start <= time <= segment.end:
                    f0 = pitch.get_value_at_time(time)
                    if f0 is not None and not np.isnan(f0):
                        segment_f0_values.append(f0)
            
            # 대표값 계산
            if segment_f0_values:
                mean_f0 = np.mean(segment_f0_values)
                median_f0 = np.median(segment_f0_values)
                
                # 기존 API 형식과 호환되는 데이터
                syllable_pitches.append({
                    'syllable': segment.label,
                    'time': (segment.start + segment.end) / 2,  # 중점 시간
                    'frequency': mean_f0,
                    'median_frequency': median_f0,
                    'start': segment.start,
                    'end': segment.end,
                    'point_count': len(segment_f0_values)
                })
            else:
                # 무음 구간 처리
                syllable_pitches.append({
                    'syllable': segment.label,
                    'time': (segment.start + segment.end) / 2,
                    'frequency': 0.0,
                    'median_frequency': 0.0,
                    'start': segment.start,
                    'end': segment.end,
                    'point_count': 0
                })
        
        return syllable_pitches
    
    def _calculate_statistics(self, pitch_points: List[Dict]) -> Dict:
        """피치 통계 계산"""
        if not pitch_points:
            return {
                'mean_f0': 0.0,
                'median_f0': 0.0,
                'min_f0': 0.0,
                'max_f0': 0.0,
                'std_f0': 0.0,
                'point_count': 0
            }
        
        frequencies = [p['frequency'] for p in pitch_points]
        
        return {
            'mean_f0': np.mean(frequencies),
            'median_f0': np.median(frequencies),
            'min_f0': np.min(frequencies),
            'max_f0': np.max(frequencies),
            'std_f0': np.std(frequencies),
            'point_count': len(frequencies)
        }
    
    def _create_empty_analysis(self) -> PitchAnalysis:
        """빈 분석 결과"""
        return PitchAnalysis(
            pitch_points=[],
            syllable_pitches=[],
            statistics={
                'mean_f0': 0.0,
                'median_f0': 0.0,
                'min_f0': 0.0,
                'max_f0': 0.0,
                'std_f0': 0.0,
                'point_count': 0
            }
        )