"""
음성 자동 분절 및 TextGrid 생성 시스템

이 모듈은 한국어 음성의 자동 음절 분절과 TextGrid 생성을 위한
고급 음성 처리 시스템을 구현합니다.

주요 기능:
1. 다중 특징 기반 음절 분절 (에너지, 스펙트럴, 피치)
2. 동적 프로그래밍을 통한 최적 경계 탐지
3. 자동 TextGrid 생성 및 최적화
4. STT 통합을 통한 완전 자동화
"""

import numpy as np
import parselmouth
from parselmouth.praat import call
import librosa
import scipy.signal
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from pathlib import Path
import json

@dataclass
class Syllable:
    """음절 정보 클래스"""
    start_time: float
    end_time: float
    text: str = ""
    pitch_mean: float = 0.0
    intensity_mean: float = 0.0
    confidence: float = 0.0
    phonemes: List[str] = field(default_factory=list)
    
class SyllableSegmentation:
    """
    음절 자동 분절 시스템
    """
    
    def __init__(self):
        self.sample_rate = None
        self.audio = None
        self.sound = None
        
    def segment_syllables(self, audio_file: str, method: str = 'energy_based') -> List[Syllable]:
        """
        음절 분절 메인 함수
        
        Parameters:
        -----------
        audio_file : str
            입력 오디오 파일
        method : str
            분절 방법 ('energy_based', 'spectral_based', 'hybrid')
        
        Returns:
        --------
        List[Syllable] : 분절된 음절 리스트
        """
        # 오디오 로드
        self.sound = parselmouth.Sound(audio_file)
        self.audio, self.sample_rate = librosa.load(audio_file, sr=None)
        
        if method == 'energy_based':
            return self._energy_based_segmentation()
        elif method == 'spectral_based':
            return self._spectral_based_segmentation()
        elif method == 'hybrid':
            return self._hybrid_segmentation()
        else:
            raise ValueError(f"Unknown method: {method}")
    
    def _energy_based_segmentation(self) -> List[Syllable]:
        """
        에너지 기반 음절 분절
        """
        # 1. 에너지 엔벨로프 계산
        intensity = self.sound.to_intensity(time_step=0.01)
        times = intensity.xs()
        values = intensity.values[0]
        
        # 2. 에너지 피크와 밸리 찾기
        peaks, valleys = self._find_peaks_and_valleys(values)
        
        # 3. 음절 경계 결정
        boundaries = self._determine_boundaries_from_energy(
            times, values, peaks, valleys
        )
        
        # 4. 음절 객체 생성
        syllables = []
        for i in range(len(boundaries) - 1):
            syllable = Syllable(
                start_time=boundaries[i],
                end_time=boundaries[i + 1],
                intensity_mean=np.mean(values[
                    int(boundaries[i] * 100):int(boundaries[i + 1] * 100)
                ])
            )
            syllables.append(syllable)
        
        return syllables
    
    def _spectral_based_segmentation(self) -> List[Syllable]:
        """
        스펙트럴 특징 기반 음절 분절
        """
        # 1. 스펙트럴 특징 추출
        spectral_flux = self._compute_spectral_flux()
        spectral_centroid = librosa.feature.spectral_centroid(
            y=self.audio, sr=self.sample_rate
        )[0]
        
        # 2. 변화점 검출
        change_points = self._detect_spectral_changes(
            spectral_flux, spectral_centroid
        )
        
        # 3. 음절 경계로 변환
        boundaries = change_points / self.sample_rate
        
        # 4. 음절 생성
        syllables = []
        for i in range(len(boundaries) - 1):
            syllables.append(
                Syllable(
                    start_time=boundaries[i],
                    end_time=boundaries[i + 1]
                )
            )
        
        return syllables
    
    def _hybrid_segmentation(self) -> List[Syllable]:
        """
        하이브리드 음절 분절 (에너지 + 스펙트럴 + 피치)
        """
        # 1. 다중 특징 추출
        features = self._extract_multiple_features()
        
        # 2. 특징 융합
        combined_score = self._fuse_features(features)
        
        # 3. 동적 프로그래밍으로 최적 경계 찾기
        boundaries = self._dynamic_programming_segmentation(combined_score)
        
        # 4. 음절 정보 추출
        syllables = self._extract_syllable_info(boundaries)
        
        return syllables
    
    def _find_peaks_and_valleys(self, signal: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        신호에서 피크와 밸리 찾기
        """
        # 스무딩
        smoothed = scipy.signal.savgol_filter(signal, 11, 3)
        
        # 피크 찾기
        peaks, _ = scipy.signal.find_peaks(
            smoothed, 
            prominence=np.std(smoothed) * 0.3,
            distance=20  # 최소 200ms 간격
        )
        
        # 밸리 찾기 (반전 신호의 피크)
        valleys, _ = scipy.signal.find_peaks(
            -smoothed,
            prominence=np.std(smoothed) * 0.2,
            distance=10
        )
        
        return peaks, valleys
    
    def _determine_boundaries_from_energy(self, times, values, peaks, valleys):
        """
        에너지 피크와 밸리로부터 음절 경계 결정
        """
        boundaries = [0.0]  # 시작점
        
        # 밸리를 경계로 사용
        for valley_idx in valleys:
            # 밸리가 두 피크 사이에 있는지 확인
            if valley_idx < len(times):
                time = times[valley_idx]
                
                # 너무 짧은 음절 방지 (최소 50ms)
                if len(boundaries) == 0 or time - boundaries[-1] > 0.05:
                    boundaries.append(time)
        
        boundaries.append(times[-1])  # 끝점
        
        return boundaries
    
    def _compute_spectral_flux(self):
        """
        스펙트럴 플럭스 계산
        """
        stft = librosa.stft(self.audio)
        magnitude = np.abs(stft)
        
        # 스펙트럴 플럭스
        flux = np.sum(np.diff(magnitude, axis=1) ** 2, axis=0)
        flux = np.pad(flux, (1, 0), mode='constant', constant_values=0)
        
        return flux
    
    def _detect_spectral_changes(self, flux, centroid):
        """
        스펙트럴 변화점 검출
        """
        # 정규화
        flux_norm = (flux - np.mean(flux)) / np.std(flux)
        centroid_norm = (centroid - np.mean(centroid)) / np.std(centroid)
        
        # 변화 스코어
        change_score = np.abs(np.diff(flux_norm)) + np.abs(np.diff(centroid_norm))
        
        # 피크 검출
        peaks, _ = scipy.signal.find_peaks(
            change_score,
            prominence=1.0,
            distance=int(0.05 * self.sample_rate)  # 최소 50ms
        )
        
        return peaks
    
    def _extract_multiple_features(self):
        """
        다중 특징 추출
        """
        features = {}
        
        # 1. 에너지
        features['energy'] = librosa.feature.rms(
            y=self.audio, 
            frame_length=2048, 
            hop_length=512
        )[0]
        
        # 2. 영교차율
        features['zcr'] = librosa.feature.zero_crossing_rate(
            self.audio,
            frame_length=2048,
            hop_length=512
        )[0]
        
        # 3. 스펙트럴 중심
        features['spectral_centroid'] = librosa.feature.spectral_centroid(
            y=self.audio,
            sr=self.sample_rate
        )[0]
        
        # 4. 피치 (Praat)
        pitch = self.sound.to_pitch(time_step=0.01)
        features['pitch'] = pitch.selected_array['frequency']
        
        # 5. 포먼트
        formant = self.sound.to_formant_burg()
        f1_values = []
        for i in range(formant.n_frames):
            time = formant.get_time_from_frame_number(i + 1)
            f1 = formant.get_value_at_time(1, time)
            f1_values.append(f1 if f1 else 0)
        features['formant'] = np.array(f1_values)
        
        return features
    
    def _fuse_features(self, features):
        """
        특징 융합
        """
        # 모든 특징을 동일한 시간 해상도로 리샘플링
        target_length = min(len(v) for v in features.values())
        
        fused = np.zeros(target_length)
        weights = {
            'energy': 0.3,
            'zcr': 0.1,
            'spectral_centroid': 0.2,
            'pitch': 0.25,
            'formant': 0.15
        }
        
        for name, feature in features.items():
            # 리샘플링
            if len(feature) != target_length:
                feature = scipy.signal.resample(feature, target_length)
            
            # 정규화
            if np.std(feature) > 0:
                feature = (feature - np.mean(feature)) / np.std(feature)
            
            # 가중 합
            fused += weights.get(name, 0.1) * np.abs(np.diff(np.pad(feature, (1, 0))))
        
        return fused
    
    def _dynamic_programming_segmentation(self, score, min_duration=0.05, max_duration=0.5):
        """
        동적 프로그래밍을 이용한 최적 분절
        """
        n = len(score)
        hop_length = 512
        time_per_frame = hop_length / self.sample_rate
        
        min_frames = int(min_duration / time_per_frame)
        max_frames = int(max_duration / time_per_frame)
        
        # DP 테이블
        dp = np.full(n + 1, np.inf)
        dp[0] = 0
        parent = np.zeros(n + 1, dtype=int)
        
        # DP 실행
        for i in range(n):
            if dp[i] == np.inf:
                continue
                
            for j in range(i + min_frames, min(i + max_frames + 1, n + 1)):
                # 세그먼트 비용
                segment_cost = -np.sum(score[i:j])
                
                # 길이 페널티
                length = j - i
                optimal_length = (min_frames + max_frames) / 2
                length_penalty = abs(length - optimal_length) * 0.1
                
                total_cost = dp[i] + segment_cost + length_penalty
                
                if total_cost < dp[j]:
                    dp[j] = total_cost
                    parent[j] = i
        
        # 백트래킹
        boundaries = []
        i = n
        while i > 0:
            boundaries.append(i * time_per_frame)
            i = parent[i]
        boundaries.append(0)
        
        return list(reversed(boundaries))
    
    def _extract_syllable_info(self, boundaries):
        """
        경계로부터 음절 정보 추출
        """
        syllables = []
        
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            
            # 구간 내 특징 추출
            start_frame = int(start * self.sample_rate)
            end_frame = int(end * self.sample_rate)
            
            if end_frame > start_frame:
                segment = self.audio[start_frame:end_frame]
                
                # 피치 평균
                pitch = self.sound.to_pitch(time_step=0.01)
                pitch_values = []
                for t in np.linspace(start, end, 10):
                    p = pitch.get_value_at_time(t)
                    if p:
                        pitch_values.append(p)
                
                pitch_mean = np.mean(pitch_values) if pitch_values else 0
                
                # 강도 평균
                intensity = self.sound.to_intensity()
                intensity_values = []
                for t in np.linspace(start, end, 10):
                    intensity_values.append(
                        call(intensity, "Get value at time", t, "cubic")
                    )
                intensity_mean = np.mean(intensity_values)
                
                syllables.append(
                    Syllable(
                        start_time=start,
                        end_time=end,
                        pitch_mean=pitch_mean,
                        intensity_mean=intensity_mean,
                        confidence=0.8  # 임시 신뢰도
                    )
                )
        
        return syllables


class TextGridManager:
    """
    TextGrid 파일 생성 및 관리
    """
    
    def __init__(self):
        self.textgrid = None
        self.tiers = {}
        
    def create_textgrid(self, duration: float, tiers_config: Dict = None):
        """
        새 TextGrid 생성
        """
        if tiers_config is None:
            tiers_config = {
                'syllables': 'IntervalTier',
                'phonemes': 'IntervalTier', 
                'words': 'IntervalTier'
            }
        
        # TextGrid 초기화
        self.textgrid = {
            'xmin': 0.0,
            'xmax': duration,
            'tiers': []
        }
        
        # 각 tier 생성
        for tier_name, tier_type in tiers_config.items():
            tier = {
                'name': tier_name,
                'class': tier_type,
                'xmin': 0.0,
                'xmax': duration,
                'intervals': []
            }
            self.textgrid['tiers'].append(tier)
            self.tiers[tier_name] = len(self.textgrid['tiers']) - 1
    
    def add_syllable_intervals(self, syllables: List[Syllable]):
        """
        음절 구간을 TextGrid에 추가
        """
        if 'syllables' not in self.tiers:
            raise ValueError("syllables tier not found")
        
        tier_idx = self.tiers['syllables']
        intervals = []
        
        for syllable in syllables:
            intervals.append({
                'xmin': syllable.start_time,
                'xmax': syllable.end_time,
                'text': syllable.text
            })
        
        self.textgrid['tiers'][tier_idx]['intervals'] = intervals
    
    def save_textgrid(self, output_path: str):
        """
        TextGrid를 파일로 저장
        """
        content = self._format_textgrid()
        
        with open(output_path, 'w', encoding='utf-16') as f:
            f.write(content)
    
    def _format_textgrid(self) -> str:
        """
        TextGrid 형식으로 포맷팅
        """
        content = f'''File type = "ooTextFile"
Object class = "TextGrid"

xmin = {self.textgrid['xmin']} 
xmax = {self.textgrid['xmax']} 
tiers? <exists> 
size = {len(self.textgrid['tiers'])} 
item []: 
'''
        
        for i, tier in enumerate(self.textgrid['tiers']):
            content += f'''    item [{i+1}]:
        class = "{tier['class']}" 
        name = "{tier['name']}" 
        xmin = {tier['xmin']} 
        xmax = {tier['xmax']} 
        intervals: size = {len(tier['intervals'])} 
'''
            
            for j, interval in enumerate(tier['intervals']):
                content += f'''        intervals [{j+1}]:
            xmin = {interval['xmin']} 
            xmax = {interval['xmax']} 
            text = "{interval['text']}" 
'''
        
        return content


class STTProcessor:
    """
    음성-텍스트 변환 처리기
    """
    
    def __init__(self, model_type: str = 'whisper'):
        self.model_type = model_type
        self.model = None
        
    def transcribe_audio(self, audio_file: str, language: str = 'ko') -> str:
        """
        오디오 파일을 텍스트로 변환
        """
        if self.model_type == 'whisper':
            return self._whisper_transcribe(audio_file, language)
        else:
            raise ValueError(f"Unsupported model type: {self.model_type}")
    
    def _whisper_transcribe(self, audio_file: str, language: str) -> str:
        """
        OpenAI Whisper를 사용한 음성 인식
        """
        try:
            import whisper
            
            if self.model is None:
                self.model = whisper.load_model("base")
            
            result = self.model.transcribe(audio_file, language=language)
            return result["text"].strip()
            
        except ImportError:
            raise ImportError("whisper library not installed. Run: pip install openai-whisper")
    
    def segment_with_timestamps(self, audio_file: str, language: str = 'ko') -> List[Dict]:
        """
        타임스탬프와 함께 음성 인식
        """
        try:
            import whisper
            
            if self.model is None:
                self.model = whisper.load_model("base")
            
            result = self.model.transcribe(audio_file, language=language, word_timestamps=True)
            
            segments = []
            for segment in result["segments"]:
                segments.append({
                    'start': segment['start'],
                    'end': segment['end'], 
                    'text': segment['text'].strip()
                })
            
            return segments
            
        except ImportError:
            raise ImportError("whisper library not installed")


class AutomatedAudioProcessor:
    """
    완전 자동화된 오디오 처리 시스템
    """
    
    def __init__(self):
        self.segmenter = SyllableSegmentation()
        self.textgrid_manager = TextGridManager()
        self.stt_processor = STTProcessor()
    
    def process_audio_file(self, audio_file: str, output_dir: str = None) -> Dict:
        """
        오디오 파일 완전 자동 처리
        
        Returns:
        --------
        Dict : 처리 결과
            - transcription: 음성 인식 결과
            - syllables: 분절된 음절 리스트
            - textgrid_path: 생성된 TextGrid 파일 경로
        """
        if output_dir is None:
            output_dir = Path(audio_file).parent
        
        audio_path = Path(audio_file)
        base_name = audio_path.stem
        
        # 1. 음성 인식
        print("🎤 음성 인식 시작...")
        transcription = self.stt_processor.transcribe_audio(audio_file)
        print(f"📝 인식 결과: {transcription}")
        
        # 2. 음절 분절
        print("✂️ 음절 분절 시작...")
        syllables = self.segmenter.segment_syllables(audio_file, method='hybrid')
        
        # 3. 텍스트와 음절 매칭
        print("🔗 텍스트-음절 매칭...")
        syllables = self._match_text_to_syllables(transcription, syllables)
        
        # 4. TextGrid 생성
        print("📋 TextGrid 생성...")
        duration = self.segmenter.sound.duration
        self.textgrid_manager.create_textgrid(duration)
        self.textgrid_manager.add_syllable_intervals(syllables)
        
        # 5. 파일 저장
        textgrid_path = Path(output_dir) / f"{base_name}.TextGrid"
        self.textgrid_manager.save_textgrid(str(textgrid_path))
        
        print(f"✅ 처리 완료: {textgrid_path}")
        
        return {
            'transcription': transcription,
            'syllables': [
                {
                    'text': s.text,
                    'start': s.start_time,
                    'end': s.end_time,
                    'pitch_mean': s.pitch_mean,
                    'intensity_mean': s.intensity_mean
                }
                for s in syllables
            ],
            'textgrid_path': str(textgrid_path)
        }
    
    def _match_text_to_syllables(self, text: str, syllables: List[Syllable]) -> List[Syllable]:
        """
        인식된 텍스트를 음절 분절 결과와 매칭
        """
        # 한국어 음절 분리
        clean_text = ''.join(c for c in text if c.strip() and not c.isascii())
        korean_syllables = list(clean_text)
        
        print(f"🎯 인식된 음절: {korean_syllables} ({len(korean_syllables)}개)")
        print(f"🎯 분절된 구간: {len(syllables)}개")
        
        # 매칭 전략: 길이가 다르면 균등 분배
        if len(korean_syllables) != len(syllables):
            print("⚠️ 음절 수 불일치 - 균등 분배 적용")
            
            # 새로운 음절 리스트 생성
            new_syllables = []
            total_duration = syllables[-1].end_time - syllables[0].start_time
            syllable_duration = total_duration / len(korean_syllables)
            
            for i, syllable_text in enumerate(korean_syllables):
                start_time = syllables[0].start_time + i * syllable_duration
                end_time = start_time + syllable_duration
                
                new_syllables.append(
                    Syllable(
                        start_time=start_time,
                        end_time=end_time,
                        text=syllable_text,
                        confidence=0.7
                    )
                )
            
            return new_syllables
        
        # 길이가 같으면 직접 매칭
        for i, syllable in enumerate(syllables):
            if i < len(korean_syllables):
                syllable.text = korean_syllables[i]
                syllable.confidence = 0.9
        
        return syllables