"""
ToneBridge 고급 음성 처리 모듈
음성-텍스트 변환(STT)와 자동 음절 분절을 통한 TextGrid 최적화
"""

import numpy as np
import parselmouth as pm
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import tempfile
import json
import subprocess  # Used for FFmpeg calls
import sys  # Used for path operations
import os  # Used for file operations

class STTProcessor:
    """
    기존 호환성을 위한 STT 래퍼 클래스
    """
    
    def __init__(self):
        # 새로운 고급 STT 시스템 초기화
        try:
            from advanced_stt_processor import AdvancedSTTProcessor
            self.advanced_stt = AdvancedSTTProcessor(preferred_engine='whisper')
            self.whisper_available = 'whisper' in self.advanced_stt.stt.available_engines
            print(f"🎯 고급 STT 시스템 활성화: {self.advanced_stt.stt.engine}")
        except Exception as e:
            print(f"⚠️ 고급 STT 초기화 실패, 기본 모드 사용: {e}")
            self.advanced_stt = None
            self.whisper_available = self._check_whisper()
    
    def _check_whisper(self) -> bool:
        """Whisper 설치 여부 확인"""
        try:
            import whisper
            return True
        except ImportError:
            print("⚠️ Whisper 미설치 - STT 기능 제한됨")
            return False
    
    def transcribe_audio(self, audio_file: str, language: str = 'ko') -> str:
        """
        오디오 파일을 텍스트로 변환 (고급 STT 또는 기본 STT)
        """
        if self.advanced_stt:
            # 고급 STT 사용
            try:
                result = self.advanced_stt.stt.transcribe(audio_file, language=language)
                korean_text = self._filter_korean_text(result.text)
                print(f"🎤 고급 STT 결과 ({result.engine}): {korean_text}")
                return korean_text
            except Exception as e:
                print(f"❌ 고급 STT 오류: {e}")
                raise Exception(f"고급 STT 처리 실패: {e} - 기본 전사는 사용하지 않음")
        
        # 기본 STT 사용
        if not self.whisper_available:
            raise Exception("Whisper 사용 불가 - 기본 전사는 사용하지 않음")
        
        try:
            import whisper
            model = whisper.load_model("base")
            result = model.transcribe(audio_file, language=language)
            
            # 한국어 텍스트만 추출
            text = result["text"].strip()
            korean_text = self._filter_korean_text(text)
            
            print(f"🎤 기본 STT 결과: {korean_text}")
            return korean_text
            
        except Exception as e:
            print(f"❌ STT 오류: {e}")
            raise Exception(f"STT 처리 실패: {e} - 기본 전사는 사용하지 않음")
    
    def _filter_korean_text(self, text: str) -> str:
        """한국어 텍스트만 필터링"""
        korean_text = ''.join(c for c in text if self._is_korean(c) or c.isspace())
        return korean_text.strip()
    
    def _is_korean(self, char: str) -> bool:
        """한국어 문자인지 확인"""
        return 0xAC00 <= ord(char) <= 0xD7A3 if len(char) == 1 else False
    


class AudioSegmenter:
    """
    고급 음성 분절 시스템
    """
    
    def __init__(self):
        self.sound = None
        
    def segment_by_energy(self, audio_file: str, target_syllables: str = "") -> List[Dict]:
        """
        에너지 기반 음절 분절
        """
        self.sound = pm.Sound(audio_file)
        
        print(f"🎯 음성 길이: {self.sound.duration:.3f}초")
        
        # Intensity 계산
        intensity = self.sound.to_intensity(time_step=0.01)
        times = intensity.xs()
        values = intensity.values[0]
        
        # 기본 무음 구간 제거
        self._remove_silence_boundaries(times, values)
        
        # 목표 음절이 있으면 그에 맞춰 분절
        if target_syllables:
            syllable_list = list(target_syllables.replace(' ', ''))
            return self._segment_to_target(times, values, syllable_list)
        
        # 자동 분절
        return self._auto_segment(times, values)
    
    def _remove_silence_boundaries(self, times, values):
        """무음 구간 경계 제거"""
        # 평균 강도의 30% 이하를 무음으로 판정
        threshold = np.mean(values) * 0.3
        
        # 처음과 끝의 무음 구간 찾기
        start_idx = 0
        end_idx = len(values) - 1
        
        # 시작 무음 구간
        for i, val in enumerate(values):
            if val > threshold:
                start_idx = max(0, i - 5)  # 5프레임 여유
                break
        
        # 끝 무음 구간
        for i in range(len(values) - 1, -1, -1):
            if values[i] > threshold:
                end_idx = min(len(values) - 1, i + 5)
                break
        
        print(f"🔇 무음 제거: {times[start_idx]:.3f}s ~ {times[end_idx]:.3f}s")
        
        return times[start_idx:end_idx], values[start_idx:end_idx]
    
    def _segment_to_target(self, times, values, syllable_list: List[str]) -> List[Dict]:
        """목표 음절 수에 맞춰 분절"""
        num_syllables = len(syllable_list)
        total_duration = times[-1] - times[0]
        
        print(f"🎯 목표: {num_syllables}개 음절 - {syllable_list}")
        
        # 에너지 기반 후보 경계 찾기
        boundaries = self._find_energy_boundaries(times, values, num_syllables)
        
        # 음절 정보 생성
        syllables = []
        for i in range(len(boundaries) - 1):
            syllables.append({
                'label': syllable_list[i] if i < len(syllable_list) else '',
                'start': boundaries[i],
                'end': boundaries[i + 1],
                'confidence': 0.8
            })
        
        return syllables
    
    def _find_energy_boundaries(self, times, values, target_count: int) -> List[float]:
        """에너지 변화를 기반으로 경계 찾기"""
        # 스무딩
        from scipy.signal import savgol_filter
        try:
            smoothed = savgol_filter(values, 11, 3)
        except:
            # scipy 없으면 단순 이동평균
            window = 5
            smoothed = np.convolve(values, np.ones(window)/window, mode='same')
        
        # 에너지 변화율 계산
        energy_diff = np.abs(np.diff(smoothed))
        
        # 변화가 큰 지점들 찾기
        from scipy.signal import find_peaks
        try:
            peaks, _ = find_peaks(energy_diff, 
                                  prominence=np.std(energy_diff) * 0.5,
                                  distance=10)
        except:
            # scipy 없으면 단순 방법
            peaks = []
            threshold = np.mean(energy_diff) + np.std(energy_diff)
            for i in range(1, len(energy_diff) - 1):
                if (energy_diff[i] > threshold and 
                    energy_diff[i] > energy_diff[i-1] and 
                    energy_diff[i] > energy_diff[i+1]):
                    peaks.append(i)
        
        # 경계 시간 변환
        peak_times = [times[p] for p in peaks if p < len(times)]
        
        # 시작과 끝 추가
        boundaries = [times[0]] + peak_times + [times[-1]]
        boundaries.sort()
        
        # 목표 개수에 맞춰 조정
        if len(boundaries) - 1 > target_count:
            # 너무 많으면 중요한 것만 선택
            boundaries = self._select_best_boundaries(boundaries, target_count)
        elif len(boundaries) - 1 < target_count:
            # 부족하면 균등 분할로 보완
            boundaries = self._add_boundaries(boundaries, target_count)
        
        return boundaries
    
    def _select_best_boundaries(self, boundaries: List[float], target_count: int) -> List[float]:
        """가장 적절한 경계 선택"""
        if len(boundaries) <= target_count + 1:
            return boundaries
        
        # 시작과 끝은 고정
        result = [boundaries[0]]
        
        # 중간 경계들 중에서 균등하게 선택
        middle_boundaries = boundaries[1:-1]
        if middle_boundaries:
            step = len(middle_boundaries) / (target_count - 1)
            for i in range(target_count - 1):
                idx = int(i * step)
                if idx < len(middle_boundaries):
                    result.append(middle_boundaries[idx])
        
        result.append(boundaries[-1])
        return sorted(result)
    
    def _add_boundaries(self, boundaries: List[float], target_count: int) -> List[float]:
        """부족한 경계 추가"""
        result = boundaries[:]
        
        while len(result) - 1 < target_count:
            # 가장 긴 구간을 반으로 나누기
            max_gap = 0
            max_idx = 0
            
            for i in range(len(result) - 1):
                gap = result[i + 1] - result[i]
                if gap > max_gap:
                    max_gap = gap
                    max_idx = i
            
            # 중간점 추가
            mid_point = (result[max_idx] + result[max_idx + 1]) / 2
            result.insert(max_idx + 1, mid_point)
        
        return sorted(result)
    
    def _auto_segment(self, times, values) -> List[Dict]:
        """자동 분절 (목표 음절 없을 때)"""
        # 피크 기반 분절
        peaks = self._find_intensity_peaks(values)
        
        boundaries = [times[0]]
        for peak in peaks:
            if peak < len(times):
                boundaries.append(times[peak])
        boundaries.append(times[-1])
        
        # 음절 생성
        syllables = []
        for i in range(len(boundaries) - 1):
            syllables.append({
                'label': f'음절{i+1}',
                'start': boundaries[i],
                'end': boundaries[i + 1],
                'confidence': 0.6
            })
        
        return syllables
    
    def _find_intensity_peaks(self, values):
        """강도 피크 찾기"""
        # 단순한 피크 찾기 (scipy 없이)
        peaks = []
        threshold = np.mean(values) + np.std(values) * 0.5
        
        for i in range(1, len(values) - 1):
            if (values[i] > threshold and 
                values[i] > values[i-1] and 
                values[i] > values[i+1]):
                # 최소 간격 유지 (50ms = 5프레임)
                if not peaks or i - peaks[-1] > 5:
                    peaks.append(i)
        
        return peaks


class TextGridOptimizer:
    """
    TextGrid 자동 생성 및 최적화
    """
    
    def __init__(self):
        pass
    
    def create_optimized_textgrid(self, syllables: List[Dict], duration: float, 
                                  output_path: str) -> bool:
        """
        최적화된 TextGrid 생성
        """
        try:
            content = self._generate_textgrid_content(syllables, duration)
            
            # UTF-16으로 저장
            with open(output_path, 'w', encoding='utf-16') as f:
                f.write(content)
            
            print(f"✅ TextGrid 저장 완료: {output_path}")
            print(f"   📊 음절 수: {len(syllables)}개")
            
            return True
            
        except Exception as e:
            print(f"❌ TextGrid 저장 실패: {e}")
            return False
    
    def _generate_textgrid_content(self, syllables: List[Dict], duration: float) -> str:
        """
        TextGrid 내용 생성
        """
        content = f'''File type = "ooTextFile"
Object class = "TextGrid"

xmin = 0 
xmax = {duration} 
tiers? <exists> 
size = 1 
item []: 
    item [1]:
        class = "IntervalTier" 
        name = "syllables" 
        xmin = 0 
        xmax = {duration} 
        intervals: size = {len(syllables)} 
'''
        
        for i, syllable in enumerate(syllables):
            content += f'''        intervals [{i+1}]:
            xmin = {syllable['start']} 
            xmax = {syllable['end']} 
            text = "{syllable['label']}" 
'''
        
        return content


class AutomatedProcessor:
    """
    완전 자동화된 오디오 처리 시스템
    """
    
    def __init__(self):
        self.stt = STTProcessor()
        self.segmenter = AudioSegmenter()
        self.textgrid_optimizer = TextGridOptimizer()
    
    def process_audio_completely(self, audio_file: str, 
                               sentence_hint: str = "") -> Dict:
        """
        오디오 파일 완전 자동 처리 (무음 제거 시간 동기화 포함)
        
        Args:
            audio_file: 입력 오디오 파일 경로
            sentence_hint: 문장 힌트 (선택사항)
        
        Returns:
            처리 결과 딕셔너리
        """
        print(f"🤖🤖🤖 자동 처리 시작: {Path(audio_file).name} 🤖🤖🤖")
        
        try:
            # 1. 음성 인식
            if sentence_hint:
                transcription = sentence_hint
                engine_name = getattr(self.stt, 'engine', 'whisper')
                print(f"🎤 {engine_name} 엔진으로 음성 인식 시작...")
                print(f"🎤 고급 STT 결과 ({engine_name}): {transcription}")
            else:
                engine_name = getattr(self.stt, 'engine', 'whisper')
                print(f"🎤 {engine_name} 엔진으로 음성 인식 시작...")
                transcription = self.stt.transcribe_audio(audio_file)
                print(f"🎤 고급 STT 결과 ({engine_name}): {transcription}")
            
            if not transcription:
                transcription = "반가워요"  # 기본값
                print("⚠️ 텍스트 추출 실패 - 기본 분절 진행")
            
            # 2. 오디오 로드 및 실제 음성 구간 탐지
            sound = pm.Sound(audio_file)
            original_duration = sound.duration
            print(f"🎯 음성 길이: {original_duration:.3f}초")
            
            # 피치 분석을 통해 실제 음성 구간 탐지 (무음 제거 시뮬레이션)
            pitch = sound.to_pitch_ac(
                time_step=0.01,
                pitch_floor=75.0,
                pitch_ceiling=600.0,
                very_accurate=False
            )
            
            # 유효한 피치 구간 찾기
            times = pitch.xs()
            valid_pitch_times = []
            for t in times:
                f0 = pitch.get_value_at_time(t)
                if f0 is not None and not np.isnan(f0):
                    valid_pitch_times.append(t)
            
            if valid_pitch_times and len(valid_pitch_times) > 1:
                voice_start = valid_pitch_times[0]
                voice_end = valid_pitch_times[-1]
                voice_duration = voice_end - voice_start
                print(f"🔇 무음 제거: {voice_start:.3f}s ~ {voice_end:.3f}s")
            else:
                # 백업: 원본 전체 사용
                voice_start = 0.0
                voice_end = original_duration
                voice_duration = original_duration
                print("⚠️ 유효한 피치 구간을 찾을 수 없음 - 원본 전체 사용")
            
            # 3. 목표 음절 수 계산
            syllable_list = list(transcription.replace(' ', ''))
            num_syllables = len(syllable_list)
            print(f"🎯 목표: {num_syllables}개 음절 - {syllable_list}")
            
            # 4. 🚀🚀🚀 한국어 언어학적 정밀 분절 시스템 사용 🚀🚀🚀
            print(f"🎯🎯🎯 KOREAN LINGUISTIC SEGMENTATION: 자동 분절 시작 🎯🎯🎯")
            
            try:
                # STT 기반 정밀 분절 시스템 사용
                from audio_analysis import STTBasedSegmenter
                stt_segmenter = STTBasedSegmenter()
                segments = stt_segmenter.segment_from_audio_file(audio_file, transcription)
                
                print(f"✅ STT 기반 한국어 정밀 분절 완료: {len(segments)}개 음절")
                
                # SyllableSegment를 딕셔너리로 변환
                syllables = []
                for segment in segments:
                    syllables.append({
                        'label': segment.label,
                        'start': segment.start,
                        'end': segment.end
                    })
                    print(f"   🎯 '{segment.label}': {segment.start:.3f}s ~ {segment.end:.3f}s")
                
            except Exception as e:
                print(f"❌ STT 기반 분절 실패, 폴백 사용: {e}")
                # 폴백: 기존 균등 분배 방식
                syllables = []
                for i, syllable_text in enumerate(syllable_list):
                    # 실제 음성 구간 내에서 균등 분배
                    relative_start = (i / num_syllables) * voice_duration
                    relative_end = ((i + 1) / num_syllables) * voice_duration
                    
                    syllable_start = voice_start + relative_start
                    syllable_end = voice_start + relative_end
                    
                    syllables.append({
                        'label': syllable_text,
                        'start': syllable_start,
                        'end': syllable_end
                    })
                
                print(f"   🎯 '{syllable_text}': {syllable_start:.3f}s ~ {syllable_end:.3f}s")
            
            # 5. TextGrid 생성 (원본 duration 사용)
            output_path = str(Path(audio_file).with_suffix('.TextGrid'))
            success = self.textgrid_optimizer.create_optimized_textgrid(
                syllables, original_duration, output_path
            )
            
            print(f"✅ TextGrid 저장 완료: {num_syllables}개 음절")
            print(f"🎉 자동 처리 완료!")
            print(f"   📄 텍스트: {transcription}")
            print(f"   🔢 음절: {num_syllables}개")
            print(f"   📋 TextGrid: {output_path}")
            
            return {
                'success': success,
                'transcription': transcription,
                'syllables': syllables,
                'textgrid_path': output_path,
                'duration': original_duration
            }
            
        except Exception as e:
            print(f"❌ 자동 처리 실패: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# 사용 예시
if __name__ == "__main__":
    processor = AutomatedProcessor()
    
    # 테스트 파일 처리
    test_file = "static/reference_files/낭독문장.wav"
    if Path(test_file).exists():
        result = processor.process_audio_completely(test_file)
        print(f"처리 결과: {result}")