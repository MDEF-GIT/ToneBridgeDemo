"""
음성 분석 모듈
피치 분석, 포먼트 추출, 음절 분절 등 음성학적 분석 기능
"""

import warnings

warnings.filterwarnings('ignore')

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np
from dataclasses import dataclass
from enum import Enum

# 오디오 처리
import librosa
import soundfile as sf
try:
    import parselmouth
    from parselmouth.praat import call
    PARSELMOUTH_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Parselmouth 라이브러리 로딩 실패: {e}")
    parselmouth = None
    call = None
    PARSELMOUTH_AVAILABLE = False

# 음성 분석
# Optional webrtcvad import (Pure Nix compatibility)
try:
    import webrtcvad
    HAS_WEBRTCVAD = True
except ImportError:
    webrtcvad = None
    HAS_WEBRTCVAD = False
try:
    from scipy import signal
except ImportError:
    signal = None
try:
    from scipy.interpolate import interp1d
except ImportError:
    interp1d = None

# 프로젝트 모듈
from config import settings
from utils import (FileHandler, file_handler, get_logger, log_execution_time,
                   handle_errors, AudioProcessingError)

logger = get_logger(__name__)

# ========== 데이터 클래스 ==========


@dataclass
class PitchPoint:
    """피치 포인트 데이터"""
    time: float
    frequency: float
    strength: float

    def to_dict(self) -> Dict[str, float]:
        return {
            'time': self.time,
            'frequency': self.frequency,
            'strength': self.strength
        }


@dataclass
class FormantPoint:
    """포먼트 포인트 데이터"""
    time: float
    f1: float
    f2: float
    f3: float
    f4: Optional[float] = None

    def to_dict(self) -> Dict[str, float]:
        result = {
            'time': self.time,
            'f1': self.f1,
            'f2': self.f2,
            'f3': self.f3
        }
        if self.f4 is not None:
            result['f4'] = self.f4
        return result


@dataclass
class Syllable:
    """음절 데이터"""
    start_time: float
    end_time: float
    text: str
    pitch_mean: Optional[float] = None
    pitch_std: Optional[float] = None
    intensity_mean: Optional[float] = None

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        return {
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': self.duration,
            'text': self.text,
            'pitch_mean': self.pitch_mean,
            'pitch_std': self.pitch_std,
            'intensity_mean': self.intensity_mean
        }


class Gender(Enum):
    """성별 열거형"""
    MALE = "male"
    FEMALE = "female"
    CHILD = "child"
    UNKNOWN = "unknown"


# ========== 피치 분석기 ==========


class PitchAnalyzer:
    """피치 분석 클래스"""

    def __init__(self,
                 pitch_floor: float = None,
                 pitch_ceiling: float = None,
                 time_step: float = None):
        """
        초기화

        Args:
            pitch_floor: 최소 피치 (Hz)
            pitch_ceiling: 최대 피치 (Hz)
            time_step: 시간 간격 (초)
        """
        self.pitch_floor = pitch_floor or settings.PITCH_FLOOR
        self.pitch_ceiling = pitch_ceiling or settings.PITCH_CEILING
        self.time_step = time_step or settings.PITCH_TIME_STEP

        logger.info(f"PitchAnalyzer 초기화: "
                    f"범위={self.pitch_floor:.1f}-{self.pitch_ceiling:.1f}Hz, "
                    f"간격={self.time_step:.3f}s")

    @handle_errors(context="extract_pitch")
    @log_execution_time
    def extract_pitch(self,
                      audio_path: Union[str, Path],
                      method: str = "praat") -> List[PitchPoint]:
        """
        피치 추출

        Args:
            audio_path: 오디오 파일 경로
            method: 추출 방법 ('praat', 'librosa')

        Returns:
            피치 포인트 리스트
        """
        audio_path = Path(audio_path)

        if method == "praat":
            return self._extract_pitch_praat(audio_path)
        elif method == "librosa":
            return self._extract_pitch_librosa(audio_path)
        else:
            raise ValueError(f"지원하지 않는 방법: {method}")

    def _extract_pitch_praat(self, audio_path: Path) -> List[PitchPoint]:
        """Praat을 사용한 피치 추출"""
        try:
            # Parselmouth로 오디오 로드
            sound = parselmouth.Sound(str(audio_path))

            # 피치 추출
            pitch = sound.to_pitch(time_step=self.time_step,
                                   pitch_floor=self.pitch_floor,
                                   pitch_ceiling=self.pitch_ceiling)

            # 시간 배열 생성
            times = pitch.xs()

            # 피치 포인트 생성
            pitch_points = []
            for t in times:
                f0 = pitch.get_value_at_time(t)
                if f0 and not np.isnan(f0):
                    strength = pitch.get_strength_at_time(t)
                    pitch_points.append(
                        PitchPoint(time=t,
                                   frequency=f0,
                                   strength=strength if strength else 0.0))

            logger.debug(f"Praat 피치 추출 완료: {len(pitch_points)} 포인트")
            return pitch_points

        except Exception as e:
            raise AudioProcessingError(f"Praat 피치 추출 실패: {str(e)}")

    def _extract_pitch_librosa(self, audio_path: Path) -> List[PitchPoint]:
        """Librosa를 사용한 피치 추출"""
        try:
            # 오디오 로드
            y, sr = librosa.load(str(audio_path), sr=None)

            # 피치 추출 (pyin 알고리즘)
            f0, voiced_flag, voiced_probs = librosa.pyin(
                y,
                fmin=self.pitch_floor,
                fmax=self.pitch_ceiling,
                sr=sr,
                frame_length=2048,
                hop_length=int(sr * self.time_step))

            # 시간 배열 생성
            times = librosa.frames_to_time(np.arange(len(f0)),
                                           sr=sr,
                                           hop_length=int(sr * self.time_step))

            # 피치 포인트 생성
            pitch_points = []
            for i, (t, freq, prob) in enumerate(zip(times, f0, voiced_probs)):
                if freq and not np.isnan(freq):
                    pitch_points.append(
                        PitchPoint(time=t, frequency=freq, strength=prob))

            logger.debug(f"Librosa 피치 추출 완료: {len(pitch_points)} 포인트")
            return pitch_points

        except Exception as e:
            raise AudioProcessingError(f"Librosa 피치 추출 실패: {str(e)}")

    @handle_errors(context="analyze_pitch_statistics")
    def analyze_pitch_statistics(
            self, pitch_points: List[PitchPoint]) -> Dict[str, float]:
        """
        피치 통계 분석

        Args:
            pitch_points: 피치 포인트 리스트

        Returns:
            통계 정보
        """
        if not pitch_points:
            return {
                'mean': 0.0,
                'std': 0.0,
                'min': 0.0,
                'max': 0.0,
                'median': 0.0,
                'range': 0.0
            }

        frequencies = [p.frequency for p in pitch_points]

        return {
            'mean': float(np.mean(frequencies)),
            'std': float(np.std(frequencies)),
            'min': float(np.min(frequencies)),
            'max': float(np.max(frequencies)),
            'median': float(np.median(frequencies)),
            'range': float(np.max(frequencies) - np.min(frequencies))
        }

    @handle_errors(context="detect_gender")
    def detect_gender(self, pitch_points: List[PitchPoint]) -> Gender:
        """
        피치 기반 성별 추정

        Args:
            pitch_points: 피치 포인트 리스트

        Returns:
            추정된 성별
        """
        if not pitch_points:
            return Gender.UNKNOWN

        stats = self.analyze_pitch_statistics(pitch_points)
        mean_pitch = stats['mean']

        # 성별 판정 (한국어 기준)
        if mean_pitch < settings.KOREAN_PITCH_RANGE_MALE[1]:
            return Gender.MALE
        elif mean_pitch > settings.KOREAN_PITCH_RANGE_FEMALE[0]:
            if mean_pitch > settings.KOREAN_PITCH_RANGE_CHILD[0]:
                return Gender.CHILD
            return Gender.FEMALE
        else:
            # 중간 영역 - 더 정밀한 분석
            if stats['std'] > 30:  # 변동이 큰 경우
                return Gender.FEMALE
            else:
                return Gender.MALE


# ========== 포먼트 분석기 ==========


class FormantAnalyzer:
    """포먼트 분석 클래스"""

    def __init__(self, max_formant_freq: float = 5500.0):
        """
        초기화

        Args:
            max_formant_freq: 최대 포먼트 주파수 (Hz)
        """
        self.max_formant_freq = max_formant_freq
        logger.info(f"FormantAnalyzer 초기화: 최대 주파수={max_formant_freq}Hz")

    @handle_errors(context="extract_formants")
    @log_execution_time
    def extract_formants(self,
                         audio_path: Union[str, Path],
                         num_formants: int = 4,
                         time_step: float = 0.01) -> List[FormantPoint]:
        """
        포먼트 추출

        Args:
            audio_path: 오디오 파일 경로
            num_formants: 추출할 포먼트 개수
            time_step: 시간 간격

        Returns:
            포먼트 포인트 리스트
        """
        try:
            audio_path = Path(audio_path)

            # Parselmouth로 오디오 로드
            sound = parselmouth.Sound(str(audio_path))

            # 포먼트 추출
            formant = sound.to_formant_burg(
                time_step=time_step,
                max_number_of_formants=num_formants,
                maximum_formant=self.max_formant_freq,
                window_length=0.025,
                pre_emphasis_from=50.0)

            # 시간 배열
            times = formant.xs()

            # 포먼트 포인트 생성
            formant_points = []
            for t in times:
                point_data = {'time': t}

                # 각 포먼트 값 추출
                for i in range(1, min(num_formants + 1, 5)):
                    freq = formant.get_value_at_time(i, t)
                    if freq and not np.isnan(freq):
                        point_data[f'f{i}'] = freq

                # 최소 F1, F2가 있는 경우만 추가
                if 'f1' in point_data and 'f2' in point_data:
                    formant_points.append(
                        FormantPoint(time=point_data['time'],
                                     f1=point_data['f1'],
                                     f2=point_data['f2'],
                                     f3=point_data.get('f3', 0.0),
                                     f4=point_data.get('f4', None)))

            logger.debug(f"포먼트 추출 완료: {len(formant_points)} 포인트")
            return formant_points

        except Exception as e:
            raise AudioProcessingError(f"포먼트 추출 실패: {str(e)}")

    @handle_errors(context="analyze_vowel_space")
    def analyze_vowel_space(
            self, formant_points: List[FormantPoint]) -> Dict[str, Any]:
        """
        모음 공간 분석

        Args:
            formant_points: 포먼트 포인트 리스트

        Returns:
            모음 공간 분석 결과
        """
        if not formant_points:
            return {}

        f1_values = [p.f1 for p in formant_points]
        f2_values = [p.f2 for p in formant_points]

        return {
            'f1_mean':
            float(np.mean(f1_values)),
            'f1_std':
            float(np.std(f1_values)),
            'f2_mean':
            float(np.mean(f2_values)),
            'f2_std':
            float(np.std(f2_values)),
            'vowel_space_area':
            self._calculate_vowel_space_area(f1_values, f2_values)
        }

    def _calculate_vowel_space_area(self, f1_values: List[float],
                                    f2_values: List[float]) -> float:
        """모음 공간 면적 계산"""
        try:
            from scipy.spatial import ConvexHull

            points = np.column_stack((f1_values, f2_values))
            hull = ConvexHull(points)
            return float(hull.volume)  # 2D에서는 면적
        except:
            return 0.0


# ========== 음절 분절기 ==========


class SyllableSegmenter:
    """음절 분절 클래스"""

    def __init__(self):
        """초기화"""
        # WebRTC VAD 초기화 (Pure Nix 호환)
        if HAS_WEBRTCVAD:
            self.vad = webrtcvad.Vad(2)  # 중간 공격성
        else:
            self.vad = None
            logger.warning("WebRTC VAD가 사용 불가능합니다. VAD 기능이 제한됩니다.")
        logger.info("SyllableSegmenter 초기화 완료")

    @handle_errors(context="segment_by_energy")
    @log_execution_time
    def segment_by_energy(
            self,
            audio_path: Union[str, Path],
            min_duration: float = 0.05,
            max_duration: float = 0.8) -> List[Tuple[float, float]]:
        """
        에너지 기반 음절 분절

        Args:
            audio_path: 오디오 파일 경로
            min_duration: 최소 음절 길이
            max_duration: 최대 음절 길이

        Returns:
            음절 구간 리스트 [(start, end), ...]
        """
        try:
            # 오디오 로드
            y, sr = librosa.load(str(audio_path), sr=16000)

            # 에너지 계산
            hop_length = int(sr * 0.01)  # 10ms
            energy = librosa.feature.rms(y=y, hop_length=hop_length)[0]

            # 에너지 임계값 설정
            threshold = np.mean(energy) * 0.5

            # 음절 구간 검출
            segments = []
            in_segment = False
            start_frame = 0

            for i, e in enumerate(energy):
                if e > threshold and not in_segment:
                    # 음절 시작
                    in_segment = True
                    start_frame = i
                elif e <= threshold and in_segment:
                    # 음절 종료
                    in_segment = False
                    start_time = start_frame * hop_length / sr
                    end_time = i * hop_length / sr

                    duration = end_time - start_time
                    if min_duration <= duration <= max_duration:
                        segments.append((start_time, end_time))

            # 마지막 세그먼트 처리
            if in_segment:
                start_time = start_frame * hop_length / sr
                end_time = len(energy) * hop_length / sr
                duration = end_time - start_time
                if min_duration <= duration <= max_duration:
                    segments.append((start_time, end_time))

            logger.debug(f"에너지 기반 분절 완료: {len(segments)} 음절")
            return segments

        except Exception as e:
            raise AudioProcessingError(f"에너지 기반 분절 실패: {str(e)}")

    @handle_errors(context="segment_by_vad")
    @log_execution_time
    def segment_by_vad(
            self,
            audio_path: Union[str, Path],
            frame_duration_ms: int = 30) -> List[Tuple[float, float]]:
        """
        VAD 기반 음절 분절

        Args:
            audio_path: 오디오 파일 경로
            frame_duration_ms: 프레임 길이 (ms)

        Returns:
            음절 구간 리스트
        """
        try:
            # 오디오 로드 (16kHz, 모노)
            y, sr = librosa.load(str(audio_path), sr=16000, mono=True)

            # 16비트 PCM으로 변환
            y_16bit = (y * 32768).astype(np.int16)

            # 프레임 단위로 처리
            frame_length = int(sr * frame_duration_ms / 1000)
            segments = []
            in_speech = False
            start_frame = 0

            for i in range(0, len(y_16bit), frame_length):
                frame = y_16bit[i:i + frame_length]

                # 프레임 크기 맞추기
                if len(frame) < frame_length:
                    frame = np.pad(frame, (0, frame_length - len(frame)))

                # VAD 판정
                is_speech = self.vad.is_speech(frame.tobytes(), sr)

                if is_speech and not in_speech:
                    # 음성 시작
                    in_speech = True
                    start_frame = i
                elif not is_speech and in_speech:
                    # 음성 종료
                    in_speech = False
                    start_time = start_frame / sr
                    end_time = i / sr
                    segments.append((start_time, end_time))

            # 마지막 세그먼트 처리
            if in_speech:
                start_time = start_frame / sr
                end_time = len(y_16bit) / sr
                segments.append((start_time, end_time))

            logger.debug(f"VAD 기반 분절 완료: {len(segments)} 구간")
            return segments

        except Exception as e:
            raise AudioProcessingError(f"VAD 기반 분절 실패: {str(e)}")


# ========== 통합 음성 분석기 ==========


class VoiceAnalyzer:
    """통합 음성 분석 클래스"""

    def __init__(self):
        """초기화"""
        self.pitch_analyzer = PitchAnalyzer()
        self.formant_analyzer = FormantAnalyzer()
        self.syllable_segmenter = SyllableSegmenter()
        self.file_handler = file_handler

        logger.info("VoiceAnalyzer 초기화 완료")

    @handle_errors(context="analyze_audio")
    @log_execution_time
    def analyze_audio(self,
                      audio_path: Union[str, Path],
                      extract_pitch: bool = True,
                      extract_formants: bool = True,
                      segment_syllables: bool = True) -> Dict[str, Any]:
        """
        종합 음성 분석

        Args:
            audio_path: 오디오 파일 경로
            extract_pitch: 피치 추출 여부
            extract_formants: 포먼트 추출 여부
            segment_syllables: 음절 분절 여부

        Returns:
            분석 결과
        """
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {audio_path}")

        result = {
            'file_name': audio_path.name,
            'file_info': self.file_handler.get_audio_info(audio_path)
        }

        # 피치 분석
        if extract_pitch:
            pitch_points = self.pitch_analyzer.extract_pitch(audio_path)
            result['pitch'] = {
                'points': [p.to_dict() for p in pitch_points],
                'statistics':
                self.pitch_analyzer.analyze_pitch_statistics(pitch_points),
                'gender':
                self.pitch_analyzer.detect_gender(pitch_points).value
            }

        # 포먼트 분석
        if extract_formants:
            formant_points = self.formant_analyzer.extract_formants(audio_path)
            result['formants'] = {
                'points': [p.to_dict() for p in formant_points],
                'vowel_space':
                self.formant_analyzer.analyze_vowel_space(formant_points)
            }

        # 음절 분절
        if segment_syllables:
            segments = self.syllable_segmenter.segment_by_energy(audio_path)
            result['syllables'] = {
                'segments': [{
                    'start': s,
                    'end': e,
                    'duration': e - s
                } for s, e in segments],
                'count':
                len(segments)
            }

        logger.info(f"음성 분석 완료: {audio_path.name}")
        return result

    @handle_errors(context="compare_audio_files")
    @log_execution_time
    def compare_audio_files(self, reference_path: Union[str, Path],
                            target_path: Union[str, Path]) -> Dict[str, Any]:
        """
        두 오디오 파일 비교 분석

        Args:
            reference_path: 참조 오디오 경로
            target_path: 대상 오디오 경로

        Returns:
            비교 결과
        """
        # 각각 분석
        ref_analysis = self.analyze_audio(reference_path)
        target_analysis = self.analyze_audio(target_path)

        comparison = {
            'reference': ref_analysis,
            'target': target_analysis,
            'comparison': {}
        }

        # 피치 비교
        if 'pitch' in ref_analysis and 'pitch' in target_analysis:
            ref_stats = ref_analysis['pitch']['statistics']
            target_stats = target_analysis['pitch']['statistics']

            comparison['comparison']['pitch'] = {
                'mean_difference': target_stats['mean'] - ref_stats['mean'],
                'std_difference': target_stats['std'] - ref_stats['std'],
                'range_difference': target_stats['range'] - ref_stats['range']
            }

        # 음절 수 비교
        if 'syllables' in ref_analysis and 'syllables' in target_analysis:
            comparison['comparison']['syllables'] = {
                'count_difference':
                target_analysis['syllables']['count'] -
                ref_analysis['syllables']['count']
            }

        logger.info(
            f"오디오 비교 완료: {Path(reference_path).name} vs {Path(target_path).name}"
        )
        return comparison


# Template: backend/core/audio_analysis.py
class RhythmAnalyzer:
    """리듬 분석 클래스"""

    def __init__(self):
        logger.debug("RhythmAnalyzer initialized")

    def analyze(self, audio_data, sample_rate):
        return {"tempo": 0, "beats": []}


class PronunciationScorer:
    """발음 평가 클래스"""

    def __init__(self):
        logger.debug("PronunciationScorer initialized")

    def score(self, audio_data, reference_text):
        return {"score": 0.0, "details": {}}


class VADProcessor:
    """Voice Activity Detection 처리 클래스"""

    def __init__(self):
        logger.debug("VADProcessor initialized")

    def process(self, audio_data, sample_rate):
        return []


class IntensityAnalyzer:
    """음성 강도 분석 클래스"""

    def __init__(self):
        logger.debug("IntensityAnalyzer initialized")

    def analyze(self, audio_data, sample_rate):
        return {"mean": 0.0, "max": 0.0, "min": 0.0}


class SpectralAnalyzer:
    """스펙트럼 분석 클래스"""

    def __init__(self):
        logger.debug("SpectralAnalyzer initialized")

    def analyze(self, audio_data, sample_rate):
        return {"spectral_centroid": 0.0, "spectral_rolloff": 0.0}


# 메인 실행 코드
if __name__ == "__main__":
    # 테스트
    analyzer = VoiceAnalyzer()

    # 참조 파일 분석
    if settings.REFERENCE_FILES_PATH.exists():
        test_file = list(
            settings.REFERENCE_FILES_PATH.glob("*.wav"))[0] if list(
                settings.REFERENCE_FILES_PATH.glob("*.wav")) else None

        if test_file:
            logger.info(f"테스트 파일 분석: {test_file}")
            result = analyzer.analyze_audio(test_file)

            # 결과 출력
            if 'pitch' in result:
                stats = result['pitch']['statistics']
                logger.info(
                    f"피치: 평균={stats['mean']:.1f}Hz, 범위={stats['range']:.1f}Hz")
                logger.info(f"추정 성별: {result['pitch']['gender']}")

            if 'syllables' in result:
                logger.info(f"음절 수: {result['syllables']['count']}")
        else:
            logger.warning("테스트할 WAV 파일이 없습니다")
