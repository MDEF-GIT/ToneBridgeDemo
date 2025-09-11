"""
피치 분석 모듈
Praat 알고리즘 기반 정밀 피치 분석 및 포먼트, 스펙트럼 분석
"""

import warnings

warnings.filterwarnings('ignore')

from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
import numpy as np
from dataclasses import dataclass
import json

# 오디오 처리
import librosa
import soundfile as sf
# Optional parselmouth import (Pure Nix compatibility)
try:
    import parselmouth
    from parselmouth.praat import call
    HAS_PARSELMOUTH = True
except ImportError:
    parselmouth = None
    call = None
    HAS_PARSELMOUTH = False
try:
    from scipy import signal, stats
    from scipy.interpolate import interp1d
except ImportError:
    signal = stats = interp1d = None

# 프로젝트 모듈
from config import settings
from utils import get_logger, log_execution_time, handle_errors
from tonebridge_core.models import (PitchData, PitchPoint, FormantData,
                                    SpectralFeatures, Gender, TimeInterval)

logger = get_logger(__name__)

# ========== 설정 클래스 ==========


@dataclass
class PitchAnalysisConfig:
    """피치 분석 설정"""
    pitch_floor: float = 75.0  # Hz
    pitch_ceiling: float = 600.0  # Hz
    time_step: float = 0.01  # 초
    max_candidates: int = 15
    very_accurate: bool = True
    silence_threshold: float = 0.03
    voicing_threshold: float = 0.45
    octave_cost: float = 0.01
    octave_jump_cost: float = 0.35
    voiced_unvoiced_cost: float = 0.14

    def to_dict(self) -> Dict[str, Any]:
        return {
            'pitch_floor': self.pitch_floor,
            'pitch_ceiling': self.pitch_ceiling,
            'time_step': self.time_step,
            'max_candidates': self.max_candidates,
            'very_accurate': self.very_accurate,
            'silence_threshold': self.silence_threshold,
            'voicing_threshold': self.voicing_threshold,
            'octave_cost': self.octave_cost,
            'octave_jump_cost': self.octave_jump_cost,
            'voiced_unvoiced_cost': self.voiced_unvoiced_cost
        }


# ========== 결과 클래스 ==========


@dataclass
class PitchStatistics:
    """피치 통계"""
    mean: float
    median: float
    std: float
    min: float
    max: float
    range: float
    q25: float  # 1사분위수
    q75: float  # 3사분위수
    iqr: float  # 사분위수 범위

    def to_dict(self) -> Dict[str, float]:
        return {
            'mean': self.mean,
            'median': self.median,
            'std': self.std,
            'min': self.min,
            'max': self.max,
            'range': self.range,
            'q25': self.q25,
            'q75': self.q75,
            'iqr': self.iqr
        }


@dataclass
class PitchContour:
    """피치 컨투어"""
    times: np.ndarray
    frequencies: np.ndarray
    strengths: np.ndarray
    voiced_frames: np.ndarray  # 유성음 프레임

    def get_smoothed(self, window_size: int = 5) -> np.ndarray:
        """스무딩된 피치 컨투어"""
        from scipy.ndimage import median_filter
        return median_filter(self.frequencies, size=window_size)

    def get_interpolated(self, new_times: np.ndarray) -> np.ndarray:
        """보간된 피치 값"""
        # 유성음 구간만 사용
        voiced_indices = self.voiced_frames.astype(bool)
        if not np.any(voiced_indices):
            return np.zeros_like(new_times)

        f = interp1d(self.times[voiced_indices],
                     self.frequencies[voiced_indices],
                     kind='linear',
                     bounds_error=False,
                     fill_value=0.0)
        return f(new_times)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'times': self.times.tolist(),
            'frequencies': self.frequencies.tolist(),
            'strengths': self.strengths.tolist(),
            'voiced_frames': self.voiced_frames.tolist()
        }


@dataclass
class PitchAnalysisResult:
    """피치 분석 결과"""
    pitch_data: PitchData
    contour: PitchContour
    statistics: PitchStatistics
    gender_estimate: Gender
    jitter: float  # 지터 (pitch perturbation)
    shimmer: float  # 쉬머 (amplitude perturbation)
    hnr: float  # Harmonics-to-Noise Ratio

    def to_dict(self) -> Dict[str, Any]:
        return {
            'pitch_data': self.pitch_data.to_dict(),
            'contour': self.contour.to_dict(),
            'statistics': self.statistics.to_dict(),
            'gender_estimate': self.gender_estimate.value,
            'jitter': self.jitter,
            'shimmer': self.shimmer,
            'hnr': self.hnr
        }


# ========== 피치 분석기 ==========


class PitchAnalyzer:
    """고급 피치 분석기"""

    def __init__(self, config: Optional[PitchAnalysisConfig] = None):
        """
        초기화

        Args:
            config: 피치 분석 설정
        """
        self.config = config or PitchAnalysisConfig()
        logger.info(
            f"PitchAnalyzer 초기화: {self.config.pitch_floor}-{self.config.pitch_ceiling}Hz"
        )

    @handle_errors(context="analyze_pitch")
    @log_execution_time
    def analyze(
            self,
            audio_path: Union[str, Path],
            time_range: Optional[TimeInterval] = None) -> PitchAnalysisResult:
        """
        피치 분석

        Args:
            audio_path: 오디오 파일 경로
            time_range: 분석할 시간 범위

        Returns:
            피치 분석 결과
        """
        audio_path = Path(audio_path)

        # Parselmouth로 로드
        sound = parselmouth.Sound(str(audio_path))

        # 시간 범위 적용
        if time_range:
            sound = sound.extract_part(from_time=time_range.start,
                                       to_time=time_range.end,
                                       preserve_times=True)

        # 피치 추출
        pitch = self._extract_pitch(sound)

        # 피치 컨투어 생성
        contour = self._create_contour(pitch)

        # 통계 계산
        statistics = self._calculate_statistics(contour)

        # PitchData 생성
        pitch_points = []
        for t, f, s in zip(contour.times, contour.frequencies,
                           contour.strengths):
            if f > 0:  # 유성음만
                pitch_points.append(PitchPoint(time=t, frequency=f,
                                               strength=s))

        pitch_data = PitchData(points=pitch_points,
                               time_step=self.config.time_step,
                               min_pitch=self.config.pitch_floor,
                               max_pitch=self.config.pitch_ceiling)

        # 성별 추정
        gender_estimate = self._estimate_gender(statistics)

        # 음성 품질 메트릭 계산
        jitter = self._calculate_jitter(sound)
        shimmer = self._calculate_shimmer(sound)
        hnr = self._calculate_hnr(sound)

        return PitchAnalysisResult(pitch_data=pitch_data,
                                   contour=contour,
                                   statistics=statistics,
                                   gender_estimate=gender_estimate,
                                   jitter=jitter,
                                   shimmer=shimmer,
                                   hnr=hnr)

    def _extract_pitch(self, sound: "parselmouth.Sound"):
        """Praat 피치 추출"""
        return sound.to_pitch_ac(
            time_step=self.config.time_step,
            pitch_floor=self.config.pitch_floor,
            pitch_ceiling=self.config.pitch_ceiling,
            max_number_of_candidates=self.config.max_candidates,
            very_accurate=self.config.very_accurate,
            silence_threshold=self.config.silence_threshold,
            voicing_threshold=self.config.voicing_threshold,
            octave_cost=self.config.octave_cost,
            octave_jump_cost=self.config.octave_jump_cost,
            voiced_unvoiced_cost=self.config.voiced_unvoiced_cost)

    def _create_contour(self, pitch) -> PitchContour:
        """피치 컨투어 생성"""
        times = pitch.xs()
        frequencies = []
        strengths = []
        voiced_frames = []

        for t in times:
            f = pitch.get_value_at_time(t)
            s = pitch.get_strength_at_time(t)

            if f is not None and not np.isnan(f):
                frequencies.append(f)
                strengths.append(s if s is not None else 0.0)
                voiced_frames.append(1.0)
            else:
                frequencies.append(0.0)
                strengths.append(0.0)
                voiced_frames.append(0.0)

        return PitchContour(times=np.array(times),
                            frequencies=np.array(frequencies),
                            strengths=np.array(strengths),
                            voiced_frames=np.array(voiced_frames))

    def _calculate_statistics(self, contour: PitchContour) -> PitchStatistics:
        """피치 통계 계산"""
        # 유성음 프레임만 사용
        voiced_freqs = contour.frequencies[contour.voiced_frames > 0]

        if len(voiced_freqs) == 0:
            return PitchStatistics(mean=0.0,
                                   median=0.0,
                                   std=0.0,
                                   min=0.0,
                                   max=0.0,
                                   range=0.0,
                                   q25=0.0,
                                   q75=0.0,
                                   iqr=0.0)

        return PitchStatistics(
            mean=float(np.mean(voiced_freqs)),
            median=float(np.median(voiced_freqs)),
            std=float(np.std(voiced_freqs)),
            min=float(np.min(voiced_freqs)),
            max=float(np.max(voiced_freqs)),
            range=float(np.max(voiced_freqs) - np.min(voiced_freqs)),
            q25=float(np.percentile(voiced_freqs, 25)),
            q75=float(np.percentile(voiced_freqs, 75)),
            iqr=float(
                np.percentile(voiced_freqs, 75) -
                np.percentile(voiced_freqs, 25)))

    def _estimate_gender(self, statistics: PitchStatistics) -> Gender:
        """성별 추정"""
        mean_pitch = statistics.mean

        if mean_pitch == 0:
            return Gender.UNKNOWN

        # 한국어 화자 기준
        if mean_pitch < 140:  # 남성
            return Gender.MALE
        elif mean_pitch < 200:  # 여성
            return Gender.FEMALE
        elif mean_pitch < 300:  # 아동
            return Gender.CHILD
        else:
            return Gender.FEMALE  # 높은 피치는 일반적으로 여성

    def _calculate_jitter(self, sound: "parselmouth.Sound") -> float:
        """지터 계산 (pitch perturbation)"""
        try:
            point_process = call(sound, "To PointProcess (periodic, cc)",
                                 self.config.pitch_floor,
                                 self.config.pitch_ceiling)
            jitter = call(point_process, "Get jitter (local)", 0, 0, 0.0001,
                          0.02, 1.3)
            return float(jitter * 100) if jitter else 0.0  # 퍼센트로 변환
        except:
            return 0.0

    def _calculate_shimmer(self, sound: "parselmouth.Sound") -> float:
        """쉬머 계산 (amplitude perturbation)"""
        try:
            point_process = call(sound, "To PointProcess (periodic, cc)",
                                 self.config.pitch_floor,
                                 self.config.pitch_ceiling)
            shimmer = call([sound, point_process], "Get shimmer (local)", 0, 0,
                           0.0001, 0.02, 1.3, 1.6)
            return float(shimmer * 100) if shimmer else 0.0  # 퍼센트로 변환
        except:
            return 0.0

    def _calculate_hnr(self, sound: "parselmouth.Sound") -> float:
        """HNR 계산 (Harmonics-to-Noise Ratio)"""
        try:
            harmonicity = call(sound, "To Harmonicity (cc)", 0.01,
                               self.config.pitch_floor, 0.1, 1.0)
            hnr = call(harmonicity, "Get mean", 0, 0)
            return float(hnr) if hnr else 0.0
        except:
            return 0.0

    @handle_errors(context="compare_pitch")
    def compare(self, audio1: Union[str, Path],
                audio2: Union[str, Path]) -> Dict[str, Any]:
        """
        두 오디오의 피치 비교

        Args:
            audio1: 첫 번째 오디오
            audio2: 두 번째 오디오

        Returns:
            비교 결과
        """
        # 각각 분석
        result1 = self.analyze(audio1)
        result2 = self.analyze(audio2)

        # DTW (Dynamic Time Warping) 거리 계산
        from scipy.spatial.distance import euclidean
        from fastdtw import fastdtw

        # 유성음 프레임만 사용
        freq1 = result1.contour.frequencies[result1.contour.voiced_frames > 0]
        freq2 = result2.contour.frequencies[result2.contour.voiced_frames > 0]

        if len(freq1) > 0 and len(freq2) > 0:
            distance, path = fastdtw(freq1, freq2, dist=euclidean)
            similarity = 1.0 / (1.0 + distance / max(len(freq1), len(freq2)))
        else:
            distance = float('inf')
            similarity = 0.0

        # 통계 비교
        stat_diff = {
            'mean_diff': result2.statistics.mean - result1.statistics.mean,
            'range_diff': result2.statistics.range - result1.statistics.range,
            'std_diff': result2.statistics.std - result1.statistics.std
        }

        return {
            'audio1': result1.to_dict(),
            'audio2': result2.to_dict(),
            'dtw_distance': distance,
            'similarity': similarity,
            'statistics_difference': stat_diff
        }


# ========== 포먼트 분석기 ==========


@dataclass
class FormantAnalysisResult:
    """포먼트 분석 결과"""
    formants: List[FormantData]
    average_formants: Dict[str, float]  # F1, F2, F3, F4 평균
    vowel_space_area: float  # 모음 공간 면적

    def to_dict(self) -> Dict[str, Any]:
        return {
            'formants': [f.to_dict() for f in self.formants],
            'average_formants': self.average_formants,
            'vowel_space_area': self.vowel_space_area
        }


class FormantAnalyzer:
    """포먼트 분석기"""

    def __init__(self, max_formant: float = 5500.0, num_formants: int = 4):
        """
        초기화

        Args:
            max_formant: 최대 포먼트 주파수
            num_formants: 추출할 포먼트 개수
        """
        self.max_formant = max_formant
        self.num_formants = num_formants
        logger.info(
            f"FormantAnalyzer 초기화: 최대 {max_formant}Hz, {num_formants}개 포먼트")

    @handle_errors(context="analyze_formants")
    @log_execution_time
    def analyze(self,
                audio_path: Union[str, Path],
                time_step: float = 0.01) -> FormantAnalysisResult:
        """
        포먼트 분석

        Args:
            audio_path: 오디오 파일 경로
            time_step: 시간 간격

        Returns:
            포먼트 분석 결과
        """
        # Parselmouth로 로드
        sound = parselmouth.Sound(str(audio_path))

        # 포먼트 추출
        formant = sound.to_formant_burg(
            time_step=time_step,
            max_number_of_formants=self.num_formants,
            maximum_formant=self.max_formant,
            window_length=0.025,
            pre_emphasis_from=50.0)

        # 포먼트 데이터 수집
        formants = []
        times = np.arange(0, sound.duration, time_step)

        for t in times:
            formant_values = {}
            for i in range(1, self.num_formants + 1):
                freq = formant.get_value_at_time(i, t)
                if freq and not np.isnan(freq):
                    formant_values[f'f{i}'] = freq

            if 'f1' in formant_values and 'f2' in formant_values:
                formants.append(
                    FormantData(time=t,
                                f1=formant_values['f1'],
                                f2=formant_values['f2'],
                                f3=formant_values.get('f3', 0.0),
                                f4=formant_values.get('f4')))

        # 평균 계산
        if formants:
            average_formants = {
                'f1': np.mean([f.f1 for f in formants]),
                'f2': np.mean([f.f2 for f in formants]),
                'f3': np.mean([f.f3 for f in formants if f.f3 > 0]),
                'f4': np.mean([f.f4 for f in formants if f.f4])
            }
        else:
            average_formants = {'f1': 0.0, 'f2': 0.0, 'f3': 0.0, 'f4': 0.0}

        # 모음 공간 면적 계산
        vowel_space_area = self._calculate_vowel_space_area(formants)

        return FormantAnalysisResult(formants=formants,
                                     average_formants=average_formants,
                                     vowel_space_area=vowel_space_area)

    def _calculate_vowel_space_area(self,
                                    formants: List[FormantData]) -> float:
        """모음 공간 면적 계산"""
        if not formants:
            return 0.0

        try:
            from scipy.spatial import ConvexHull

            # F1, F2 좌표
            points = np.array([[f.f1, f.f2] for f in formants])

            # Convex Hull 계산
            hull = ConvexHull(points)
            return float(hull.volume)  # 2D에서는 면적
        except:
            return 0.0


# ========== 스펙트럼 분석기 ==========


@dataclass
class SpectralAnalysisResult:
    """스펙트럼 분석 결과"""
    spectral_features: SpectralFeatures
    spectral_envelope: np.ndarray
    frequency_bins: np.ndarray

    def to_dict(self) -> Dict[str, Any]:
        return {
            'spectral_features': self.spectral_features.to_dict(),
            'spectral_envelope': self.spectral_envelope.tolist(),
            'frequency_bins': self.frequency_bins.tolist()
        }


class SpectralAnalyzer:
    """스펙트럼 분석기"""

    def __init__(self, n_fft: int = 2048, hop_length: int = 512):
        """
        초기화

        Args:
            n_fft: FFT 크기
            hop_length: 홉 길이
        """
        self.n_fft = n_fft
        self.hop_length = hop_length
        logger.info(f"SpectralAnalyzer 초기화: FFT={n_fft}, hop={hop_length}")

    @handle_errors(context="analyze_spectrum")
    @log_execution_time
    def analyze(self, audio_path: Union[str, Path]) -> SpectralAnalysisResult:
        """
        스펙트럼 분석

        Args:
            audio_path: 오디오 파일 경로

        Returns:
            스펙트럼 분석 결과
        """
        # 오디오 로드
        y, sr = librosa.load(str(audio_path), sr=None)

        # 스펙트럼 특징 추출
        spectral_centroid = librosa.feature.spectral_centroid(
            y=y, sr=sr, n_fft=self.n_fft, hop_length=self.hop_length)
        spectral_bandwidth = librosa.feature.spectral_bandwidth(
            y=y, sr=sr, n_fft=self.n_fft, hop_length=self.hop_length)
        spectral_rolloff = librosa.feature.spectral_rolloff(
            y=y, sr=sr, n_fft=self.n_fft, hop_length=self.hop_length)
        zero_crossing_rate = librosa.feature.zero_crossing_rate(
            y, frame_length=self.n_fft, hop_length=self.hop_length)

        # MFCC
        mfcc = librosa.feature.mfcc(y=y,
                                    sr=sr,
                                    n_mfcc=13,
                                    n_fft=self.n_fft,
                                    hop_length=self.hop_length)

        # 평균값 계산
        spectral_features = SpectralFeatures(
            spectral_centroid=float(np.mean(spectral_centroid)),
            spectral_bandwidth=float(np.mean(spectral_bandwidth)),
            spectral_rolloff=float(np.mean(spectral_rolloff)),
            zero_crossing_rate=float(np.mean(zero_crossing_rate)),
            mfcc=np.mean(mfcc, axis=1).tolist())

        # 스펙트럼 엔벨로프
        D = librosa.stft(y, n_fft=self.n_fft, hop_length=self.hop_length)
        spectral_envelope = np.mean(np.abs(D), axis=1)
        frequency_bins = librosa.fft_frequencies(sr=sr, n_fft=self.n_fft)

        return SpectralAnalysisResult(spectral_features=spectral_features,
                                      spectral_envelope=spectral_envelope,
                                      frequency_bins=frequency_bins)


# 메인 실행 코드
if __name__ == "__main__":
    from config import settings

    # 테스트
    analyzer = PitchAnalyzer()

    # 참조 파일 테스트
    if settings.REFERENCE_FILES_PATH.exists():
        test_files = list(settings.REFERENCE_FILES_PATH.glob("*.wav"))[:1]

        for test_file in test_files:
            logger.info(f"피치 분석 테스트: {test_file}")

            result = analyzer.analyze(test_file)

            logger.info(f"평균 피치: {result.statistics.mean:.1f}Hz")
            logger.info(f"피치 범위: {result.statistics.range:.1f}Hz")
            logger.info(f"성별 추정: {result.gender_estimate.value}")
            logger.info(f"Jitter: {result.jitter:.2f}%")
            logger.info(f"Shimmer: {result.shimmer:.2f}%")
            logger.info(f"HNR: {result.hnr:.1f}dB")
