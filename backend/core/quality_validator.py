"""
품질 검증 모듈
오디오 품질, STT 정확도, 발음 평가 등 품질 검증 기능
"""

import warnings

warnings.filterwarnings('ignore')

from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
import numpy as np
from dataclasses import dataclass
from enum import Enum
import json

# 오디오 처리
import librosa
import soundfile as sf
try:
    import parselmouth
    HAS_PARSELMOUTH = True
except ImportError:
    parselmouth = None
    HAS_PARSELMOUTH = False
try:
    from scipy import signal
    from scipy.stats import pearsonr
except ImportError:
    signal = None
    pearsonr = None

# 텍스트 처리
from difflib import SequenceMatcher
try:
    import Levenshtein
except ImportError:
    Levenshtein = None
import re

# 프로젝트 모듈
from config import settings
from utils import (FileHandler, file_handler, get_logger, log_execution_time,
                   handle_errors, ValidationError)

logger = get_logger(__name__)

# ========== 품질 레벨 정의 ==========


class QualityLevel(Enum):
    """품질 수준"""
    EXCELLENT = "excellent"  # 90% 이상
    GOOD = "good"  # 75-90%
    FAIR = "fair"  # 60-75%
    POOR = "poor"  # 40-60%
    VERY_POOR = "very_poor"  # 40% 미만

    @classmethod
    def from_score(cls, score: float) -> 'QualityLevel':
        """점수로부터 품질 수준 결정"""
        if score >= 0.9:
            return cls.EXCELLENT
        elif score >= 0.75:
            return cls.GOOD
        elif score >= 0.6:
            return cls.FAIR
        elif score >= 0.4:
            return cls.POOR
        else:
            return cls.VERY_POOR


# ========== 데이터 클래스 ==========


@dataclass
class AudioQualityMetrics:
    """오디오 품질 메트릭"""
    snr: float  # Signal-to-Noise Ratio
    thd: float  # Total Harmonic Distortion
    clarity: float  # 명료도
    dynamic_range: float  # 다이나믹 레인지
    peak_level: float  # 피크 레벨
    rms_level: float  # RMS 레벨

    @property
    def overall_score(self) -> float:
        """전체 품질 점수 (0-1)"""
        # 각 메트릭을 정규화하고 가중 평균
        snr_score = min(max(self.snr / 40, 0), 1)  # 40dB를 최대로
        thd_score = 1 - min(max(self.thd, 0), 1)  # THD는 낮을수록 좋음
        clarity_score = self.clarity
        dr_score = min(max(self.dynamic_range / 20, 0), 1)  # 20dB를 최대로

        # 가중 평균
        weights = [0.3, 0.2, 0.3, 0.2]  # SNR, THD, Clarity, DR
        scores = [snr_score, thd_score, clarity_score, dr_score]

        return sum(w * s for w, s in zip(weights, scores))

    def to_dict(self) -> Dict[str, float]:
        return {
            'snr': self.snr,
            'thd': self.thd,
            'clarity': self.clarity,
            'dynamic_range': self.dynamic_range,
            'peak_level': self.peak_level,
            'rms_level': self.rms_level,
            'overall_score': self.overall_score
        }


@dataclass
class STTAccuracyMetrics:
    """STT 정확도 메트릭"""
    wer: float  # Word Error Rate
    cer: float  # Character Error Rate
    similarity: float  # 문자열 유사도
    confidence: float  # STT 신뢰도

    @property
    def accuracy(self) -> float:
        """정확도 (0-1)"""
        # WER과 CER의 역수 평균
        wer_accuracy = max(1 - self.wer, 0)
        cer_accuracy = max(1 - self.cer, 0)

        return (wer_accuracy + cer_accuracy + self.similarity) / 3

    def to_dict(self) -> Dict[str, float]:
        return {
            'wer': self.wer,
            'cer': self.cer,
            'similarity': self.similarity,
            'confidence': self.confidence,
            'accuracy': self.accuracy
        }


@dataclass
class PronunciationMetrics:
    """발음 평가 메트릭"""
    pitch_accuracy: float  # 피치 정확도
    timing_accuracy: float  # 타이밍 정확도
    intensity_match: float  # 강도 일치도
    spectral_similarity: float  # 스펙트럼 유사도

    @property
    def overall_score(self) -> float:
        """전체 발음 점수 (0-1)"""
        return np.mean([
            self.pitch_accuracy, self.timing_accuracy, self.intensity_match,
            self.spectral_similarity
        ])

    def to_dict(self) -> Dict[str, float]:
        return {
            'pitch_accuracy': self.pitch_accuracy,
            'timing_accuracy': self.timing_accuracy,
            'intensity_match': self.intensity_match,
            'spectral_similarity': self.spectral_similarity,
            'overall_score': self.overall_score
        }


@dataclass
class QualityValidationResult:
    """품질 검증 종합 결과"""
    audio_quality: Optional[AudioQualityMetrics] = None
    stt_accuracy: Optional[STTAccuracyMetrics] = None
    pronunciation: Optional[PronunciationMetrics] = None
    overall_quality: Optional[QualityLevel] = None
    recommendations: List[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'audio_quality':
            self.audio_quality.to_dict() if self.audio_quality else None,
            'stt_accuracy':
            self.stt_accuracy.to_dict() if self.stt_accuracy else None,
            'pronunciation':
            self.pronunciation.to_dict() if self.pronunciation else None,
            'overall_quality':
            self.overall_quality.value if self.overall_quality else None,
            'recommendations':
            self.recommendations or []
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ========== 오디오 품질 검증 ==========


class AudioQualityValidator:
    """오디오 품질 검증 클래스"""

    def __init__(self):
        """초기화"""
        self.file_handler = file_handler
        logger.info("AudioQualityValidator 초기화 완료")

    @handle_errors(context="validate_audio_quality")
    @log_execution_time
    def validate_audio_quality(
            self, audio_path: Union[str, Path]) -> AudioQualityMetrics:
        """
        오디오 품질 검증

        Args:
            audio_path: 오디오 파일 경로

        Returns:
            오디오 품질 메트릭
        """
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {audio_path}")

        # 오디오 로드
        y, sr = librosa.load(str(audio_path), sr=None)

        # 메트릭 계산
        snr = self._calculate_snr(y, sr)
        thd = self._calculate_thd(y, sr)
        clarity = self._calculate_clarity(y, sr)
        dynamic_range = self._calculate_dynamic_range(y)
        peak_level = 20 * np.log10(np.max(np.abs(y)) + 1e-10)
        rms_level = 20 * np.log10(np.sqrt(np.mean(y**2)) + 1e-10)

        metrics = AudioQualityMetrics(snr=snr,
                                      thd=thd,
                                      clarity=clarity,
                                      dynamic_range=dynamic_range,
                                      peak_level=peak_level,
                                      rms_level=rms_level)

        logger.info(f"오디오 품질 검증 완료: 전체 점수 {metrics.overall_score:.2f}")
        return metrics

    def _calculate_snr(self, y: np.ndarray, sr: int) -> float:
        """SNR 계산"""
        # 신호와 노이즈 분리 (간단한 방법)
        # 고주파 필터로 노이즈 추정
        sos = signal.butter(10, 1000, btype='high', fs=sr, output='sos')
        noise = signal.sosfilt(sos, y)

        signal_power = np.mean(y**2)
        noise_power = np.mean(noise**2)

        if noise_power > 0:
            snr = 10 * np.log10(signal_power / noise_power)
        else:
            snr = 100.0  # 노이즈가 없으면 매우 높은 SNR

        return float(snr)

    def _calculate_thd(self, y: np.ndarray, sr: int) -> float:
        """Total Harmonic Distortion 계산"""
        # FFT
        fft = np.fft.rfft(y)
        magnitude = np.abs(fft)

        # 기본 주파수 찾기
        fundamental_idx = np.argmax(magnitude[1:]) + 1
        fundamental_power = magnitude[fundamental_idx]**2

        # 하모닉 파워 계산 (2차~5차)
        harmonic_power = 0
        for n in range(2, 6):
            harmonic_idx = fundamental_idx * n
            if harmonic_idx < len(magnitude):
                harmonic_power += magnitude[harmonic_idx]**2

        # THD 계산
        if fundamental_power > 0:
            thd = np.sqrt(harmonic_power / fundamental_power)
        else:
            thd = 0.0

        return float(thd)

    def _calculate_clarity(self, y: np.ndarray, sr: int) -> float:
        """명료도 계산"""
        # 에너지 분포 분석
        # 음성 주파수 대역(300-3400Hz)의 에너지 비율
        fft = np.fft.rfft(y)
        freqs = np.fft.rfftfreq(len(y), 1 / sr)

        speech_band = (freqs >= 300) & (freqs <= 3400)
        speech_energy = np.sum(np.abs(fft[speech_band])**2)
        total_energy = np.sum(np.abs(fft)**2)

        if total_energy > 0:
            clarity = speech_energy / total_energy
        else:
            clarity = 0.0

        return float(clarity)

    def _calculate_dynamic_range(self, y: np.ndarray) -> float:
        """다이나믹 레인지 계산"""
        # 상위 95%와 하위 5% 레벨 차이
        sorted_abs = np.sort(np.abs(y))

        if len(sorted_abs) > 0:
            peak_95 = sorted_abs[int(len(sorted_abs) * 0.95)]
            peak_5 = sorted_abs[int(len(sorted_abs) * 0.05)]

            if peak_5 > 0:
                dynamic_range = 20 * np.log10(peak_95 / peak_5)
            else:
                dynamic_range = 60.0  # 기본값
        else:
            dynamic_range = 0.0

        return float(dynamic_range)

    @handle_errors(context="check_audio_requirements")
    def check_requirements(
            self, audio_path: Union[str, Path]) -> Tuple[bool, List[str]]:
        """
        오디오 요구사항 확인

        Args:
            audio_path: 오디오 파일 경로

        Returns:
            (통과 여부, 문제점 리스트)
        """
        audio_path = Path(audio_path)
        issues = []

        try:
            # 파일 정보 가져오기
            info = self.file_handler.get_audio_info(audio_path)

            # 샘플레이트 확인
            if info['sample_rate'] < 16000:
                issues.append(
                    f"샘플레이트가 너무 낮습니다: {info['sample_rate']}Hz (권장: 16000Hz 이상)"
                )

            # 길이 확인
            if info['duration'] < 0.5:
                issues.append(
                    f"오디오가 너무 짧습니다: {info['duration']:.2f}초 (최소: 0.5초)")
            elif info['duration'] > 300:
                issues.append(
                    f"오디오가 너무 깁니다: {info['duration']:.2f}초 (최대: 300초)")

            # 채널 확인
            if info['channels'] > 2:
                issues.append(f"채널 수가 너무 많습니다: {info['channels']} (최대: 2)")

            # 오디오 로드하여 추가 검사
            y, sr = librosa.load(str(audio_path), sr=None)

            # 무음 확인
            if np.max(np.abs(y)) < 0.001:
                issues.append("오디오가 거의 무음입니다")

            # 클리핑 확인
            if np.sum(np.abs(y) > 0.99) > len(y) * 0.01:
                issues.append("오디오 클리핑이 감지되었습니다")

        except Exception as e:
            issues.append(f"오디오 파일 검사 실패: {str(e)}")

        return len(issues) == 0, issues


# ========== STT 정확도 검증 ==========


class STTAccuracyValidator:
    """STT 정확도 검증 클래스"""

    def __init__(self):
        """초기화"""
        logger.info("STTAccuracyValidator 초기화 완료")

    @handle_errors(context="validate_stt_accuracy")
    def validate_accuracy(self,
                          transcribed_text: str,
                          reference_text: str,
                          confidence: float = 0.0) -> STTAccuracyMetrics:
        """
        STT 정확도 검증

        Args:
            transcribed_text: 전사된 텍스트
            reference_text: 참조 텍스트
            confidence: STT 신뢰도

        Returns:
            STT 정확도 메트릭
        """
        # 정규화
        transcribed = self._normalize_text(transcribed_text)
        reference = self._normalize_text(reference_text)

        # WER 계산
        wer = self._calculate_wer(transcribed, reference)

        # CER 계산
        cer = self._calculate_cer(transcribed, reference)

        # 유사도 계산
        similarity = SequenceMatcher(None, transcribed, reference).ratio()

        metrics = STTAccuracyMetrics(wer=wer,
                                     cer=cer,
                                     similarity=similarity,
                                     confidence=confidence)

        logger.info(f"STT 정확도 검증 완료: {metrics.accuracy:.2%}")
        return metrics

    def _normalize_text(self, text: str) -> str:
        """텍스트 정규화"""
        # 소문자 변환
        text = text.lower()

        # 구두점 제거
        text = re.sub(r'[^\w\s가-힣]', '', text)

        # 중복 공백 제거
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def _calculate_wer(self, transcribed: str, reference: str) -> float:
        """Word Error Rate 계산"""
        transcribed_words = transcribed.split()
        reference_words = reference.split()

        if not reference_words:
            return 0.0 if not transcribed_words else 1.0

        # Levenshtein 거리 계산
        distance = Levenshtein.distance(transcribed_words, reference_words)
        wer = distance / len(reference_words)

        return min(wer, 1.0)

    def _calculate_cer(self, transcribed: str, reference: str) -> float:
        """Character Error Rate 계산"""
        if not reference:
            return 0.0 if not transcribed else 1.0

        # 문자 단위 Levenshtein 거리
        distance = Levenshtein.distance(transcribed, reference)
        cer = distance / len(reference)

        return min(cer, 1.0)

    @handle_errors(context="evaluate_transcription_quality")
    def evaluate_quality(self,
                         transcription: str,
                         language: str = "ko") -> Dict[str, Any]:
        """
        전사 품질 평가 (참조 텍스트 없이)

        Args:
            transcription: 전사 텍스트
            language: 언어 코드

        Returns:
            품질 평가 결과
        """
        quality_checks = {
            'has_content':
            len(transcription.strip()) > 0,
            'min_length':
            len(transcription) >= 10,
            'no_repetition':
            not self._has_excessive_repetition(transcription),
            'valid_characters':
            self._has_valid_characters(transcription, language),
            'sentence_structure':
            self._check_sentence_structure(transcription, language)
        }

        # 점수 계산
        score = sum(1 for check in quality_checks.values()
                    if check) / len(quality_checks)

        return {
            'quality_score': score,
            'quality_level': QualityLevel.from_score(score).value,
            'checks': quality_checks
        }

    def _has_excessive_repetition(self, text: str) -> bool:
        """과도한 반복 확인"""
        words = text.split()

        if len(words) < 3:
            return False

        # 연속된 동일 단어 확인
        for i in range(len(words) - 2):
            if words[i] == words[i + 1] == words[i + 2]:
                return True

        return False

    def _has_valid_characters(self, text: str, language: str) -> bool:
        """유효한 문자 확인"""
        if language == "ko":
            # 한글, 영문, 숫자, 기본 문장부호만 허용
            pattern = r'^[가-힣a-zA-Z0-9\s\.\,\!\?\-]+$'
        else:
            # 영문, 숫자, 기본 문장부호
            pattern = r'^[a-zA-Z0-9\s\.\,\!\?\-]+$'

        return bool(re.match(pattern, text))

    def _check_sentence_structure(self, text: str, language: str) -> bool:
        """문장 구조 확인"""
        if language == "ko":
            # 한국어: 최소한 주어나 동사가 있어야 함
            # 간단한 휴리스틱: 조사나 어미 확인
            particles = [
                '은', '는', '이', '가', '을', '를', '에', '에서', '으로', '와', '과'
            ]
            endings = ['다', '요', '까', '죠', '네', '군', '구나']

            has_particle = any(p in text for p in particles)
            has_ending = any(text.endswith(e) for e in endings)

            return has_particle or has_ending
        else:
            # 영어: 최소한 주어와 동사
            words = text.split()
            return len(words) >= 2


# ========== 발음 평가 ==========


class PronunciationValidator:
    """발음 평가 클래스"""

    def __init__(self):
        """초기화"""
        self.file_handler = file_handler
        logger.info("PronunciationValidator 초기화 완료")

    @handle_errors(context="evaluate_pronunciation")
    @log_execution_time
    def evaluate_pronunciation(
            self, student_audio: Union[str, Path],
            reference_audio: Union[str, Path]) -> PronunciationMetrics:
        """
        발음 평가

        Args:
            student_audio: 학습자 오디오
            reference_audio: 참조 오디오

        Returns:
            발음 평가 메트릭
        """
        student_path = Path(student_audio)
        reference_path = Path(reference_audio)

        # 피치 정확도
        pitch_accuracy = self._evaluate_pitch_accuracy(student_path,
                                                       reference_path)

        # 타이밍 정확도
        timing_accuracy = self._evaluate_timing_accuracy(
            student_path, reference_path)

        # 강도 일치도
        intensity_match = self._evaluate_intensity_match(
            student_path, reference_path)

        # 스펙트럼 유사도
        spectral_similarity = self._evaluate_spectral_similarity(
            student_path, reference_path)

        metrics = PronunciationMetrics(pitch_accuracy=pitch_accuracy,
                                       timing_accuracy=timing_accuracy,
                                       intensity_match=intensity_match,
                                       spectral_similarity=spectral_similarity)

        logger.info(f"발음 평가 완료: 전체 점수 {metrics.overall_score:.2f}")
        return metrics

    def _evaluate_pitch_accuracy(self, student_path: Path,
                                 reference_path: Path) -> float:
        """피치 정확도 평가"""
        try:
            # Parselmouth로 피치 추출
            student_sound = parselmouth.Sound(str(student_path))
            reference_sound = parselmouth.Sound(str(reference_path))

            student_pitch = student_sound.to_pitch()
            reference_pitch = reference_sound.to_pitch()

            # 피치 값 추출
            student_values = []
            reference_values = []

            times = np.arange(
                0, min(student_sound.duration, reference_sound.duration), 0.01)

            for t in times:
                s_val = student_pitch.get_value_at_time(t)
                r_val = reference_pitch.get_value_at_time(t)

                if s_val and r_val and not np.isnan(s_val) and not np.isnan(
                        r_val):
                    student_values.append(s_val)
                    reference_values.append(r_val)

            if not student_values:
                return 0.0

            # 상관계수 계산
            correlation, _ = pearsonr(student_values, reference_values)

            # 정규화 (0-1)
            accuracy = max(0, correlation)

            return float(accuracy)

        except Exception as e:
            logger.warning(f"피치 정확도 평가 실패: {e}")
            return 0.0

    def _evaluate_timing_accuracy(self, student_path: Path,
                                  reference_path: Path) -> float:
        """타이밍 정확도 평가"""
        try:
            # 오디오 로드
            student_y, student_sr = librosa.load(str(student_path), sr=None)
            reference_y, reference_sr = librosa.load(str(reference_path),
                                                     sr=None)

            # 템포 추출
            student_tempo, _ = librosa.beat.beat_track(y=student_y,
                                                       sr=student_sr)
            reference_tempo, _ = librosa.beat.beat_track(y=reference_y,
                                                         sr=reference_sr)

            # 길이 비율
            duration_ratio = len(student_y) / len(reference_y)

            # 템포 비율
            if reference_tempo > 0:
                tempo_ratio = student_tempo / reference_tempo
            else:
                tempo_ratio = 1.0

            # 정확도 계산 (1에 가까울수록 좋음)
            duration_accuracy = 1 - min(abs(1 - duration_ratio), 1)
            tempo_accuracy = 1 - min(abs(1 - tempo_ratio), 1)

            return float((duration_accuracy + tempo_accuracy) / 2)

        except Exception as e:
            logger.warning(f"타이밍 정확도 평가 실패: {e}")
            return 0.0

    def _evaluate_intensity_match(self, student_path: Path,
                                  reference_path: Path) -> float:
        """강도 일치도 평가"""
        try:
            # Parselmouth로 강도 추출
            student_sound = parselmouth.Sound(str(student_path))
            reference_sound = parselmouth.Sound(str(reference_path))

            student_intensity = student_sound.to_intensity()
            reference_intensity = reference_sound.to_intensity()

            # 평균 강도
            student_mean = student_intensity.get_average(
                0, student_sound.duration)
            reference_mean = reference_intensity.get_average(
                0, reference_sound.duration)

            if reference_mean == 0:
                return 0.0

            # 비율 계산
            ratio = student_mean / reference_mean

            # 정확도 (1에 가까울수록 좋음)
            accuracy = 1 - min(abs(1 - ratio), 1)

            return float(accuracy)

        except Exception as e:
            logger.warning(f"강도 일치도 평가 실패: {e}")
            return 0.0

    def _evaluate_spectral_similarity(self, student_path: Path,
                                      reference_path: Path) -> float:
        """스펙트럼 유사도 평가"""
        try:
            # 오디오 로드
            student_y, student_sr = librosa.load(str(student_path), sr=16000)
            reference_y, reference_sr = librosa.load(str(reference_path),
                                                     sr=16000)

            # MFCC 추출
            student_mfcc = librosa.feature.mfcc(y=student_y,
                                                sr=student_sr,
                                                n_mfcc=13)
            reference_mfcc = librosa.feature.mfcc(y=reference_y,
                                                  sr=reference_sr,
                                                  n_mfcc=13)

            # 길이 맞추기
            min_len = min(student_mfcc.shape[1], reference_mfcc.shape[1])
            student_mfcc = student_mfcc[:, :min_len]
            reference_mfcc = reference_mfcc[:, :min_len]

            # 코사인 유사도
            from sklearn.metrics.pairwise import cosine_similarity

            similarity_matrix = cosine_similarity(student_mfcc.T,
                                                  reference_mfcc.T)

            # 대각선 평균 (프레임별 유사도)
            diagonal_similarity = np.diag(similarity_matrix).mean()

            return float(max(0, diagonal_similarity))

        except Exception as e:
            logger.warning(f"스펙트럼 유사도 평가 실패: {e}")
            return 0.0


# ========== 통합 품질 검증 ==========


class QualityValidator:
    """통합 품질 검증 클래스"""

    def __init__(self):
        """초기화"""
        self.audio_validator = AudioQualityValidator()
        self.stt_validator = STTAccuracyValidator()
        self.pronunciation_validator = PronunciationValidator()

        logger.info("QualityValidator 초기화 완료")

    @handle_errors(context="validate_comprehensive")
    @log_execution_time
    def validate_comprehensive(
        self,
        audio_path: Union[str, Path],
        transcribed_text: Optional[str] = None,
        reference_text: Optional[str] = None,
        reference_audio: Optional[Union[str, Path]] = None
    ) -> QualityValidationResult:
        """
        종합 품질 검증

        Args:
            audio_path: 오디오 파일 경로
            transcribed_text: 전사된 텍스트
            reference_text: 참조 텍스트
            reference_audio: 참조 오디오

        Returns:
            종합 품질 검증 결과
        """
        result = QualityValidationResult()
        recommendations = []

        # 1. 오디오 품질 검증
        try:
            audio_metrics = self.audio_validator.validate_audio_quality(
                audio_path)
            result.audio_quality = audio_metrics

            # 권장사항 추가
            if audio_metrics.snr < 20:
                recommendations.append("배경 소음을 줄여주세요")
            if audio_metrics.clarity < 0.7:
                recommendations.append("더 명확하게 발음해주세요")
            if audio_metrics.peak_level > -3:
                recommendations.append("녹음 볼륨을 낮춰주세요")

        except Exception as e:
            logger.error(f"오디오 품질 검증 실패: {e}")

        # 2. STT 정확도 검증
        if transcribed_text and reference_text:
            try:
                stt_metrics = self.stt_validator.validate_accuracy(
                    transcribed_text, reference_text)
                result.stt_accuracy = stt_metrics

                # 권장사항 추가
                if stt_metrics.wer > 0.3:
                    recommendations.append("발음을 더 정확하게 해주세요")
                if stt_metrics.confidence < 0.7:
                    recommendations.append("더 자신있게 말해주세요")

            except Exception as e:
                logger.error(f"STT 정확도 검증 실패: {e}")

        # 3. 발음 평가
        if reference_audio:
            try:
                pronunciation_metrics = self.pronunciation_validator.evaluate_pronunciation(
                    audio_path, reference_audio)
                result.pronunciation = pronunciation_metrics

                # 권장사항 추가
                if pronunciation_metrics.pitch_accuracy < 0.7:
                    recommendations.append("억양을 참조 음성과 비슷하게 맞춰주세요")
                if pronunciation_metrics.timing_accuracy < 0.7:
                    recommendations.append("말하는 속도를 조절해주세요")

            except Exception as e:
                logger.error(f"발음 평가 실패: {e}")

        # 전체 품질 수준 결정
        scores = []
        if result.audio_quality:
            scores.append(result.audio_quality.overall_score)
        if result.stt_accuracy:
            scores.append(result.stt_accuracy.accuracy)
        if result.pronunciation:
            scores.append(result.pronunciation.overall_score)

        if scores:
            overall_score = np.mean(scores)
            result.overall_quality = QualityLevel.from_score(overall_score)

        # 권장사항 정리
        result.recommendations = recommendations if recommendations else [
            "좋은 품질입니다!"
        ]

        logger.info(
            f"종합 품질 검증 완료: {result.overall_quality.value if result.overall_quality else 'N/A'}"
        )
        return result

    @handle_errors(context="generate_quality_report")
    def generate_report(self,
                        validation_result: QualityValidationResult,
                        output_path: Optional[Path] = None) -> str:
        """
        품질 검증 보고서 생성

        Args:
            validation_result: 검증 결과
            output_path: 출력 파일 경로

        Returns:
            보고서 내용
        """
        report_lines = ["=" * 50, "음성 품질 검증 보고서", "=" * 50, ""]

        # 오디오 품질
        if validation_result.audio_quality:
            report_lines.extend([
                "[ 오디오 품질 ]",
                f"  - SNR: {validation_result.audio_quality.snr:.1f} dB",
                f"  - THD: {validation_result.audio_quality.thd:.3f}",
                f"  - 명료도: {validation_result.audio_quality.clarity:.2%}",
                f"  - 다이나믹 레인지: {validation_result.audio_quality.dynamic_range:.1f} dB",
                f"  - 전체 점수: {validation_result.audio_quality.overall_score:.2%}",
                ""
            ])

        # STT 정확도
        if validation_result.stt_accuracy:
            report_lines.extend([
                "[ STT 정확도 ]",
                f"  - WER: {validation_result.stt_accuracy.wer:.2%}",
                f"  - CER: {validation_result.stt_accuracy.cer:.2%}",
                f"  - 유사도: {validation_result.stt_accuracy.similarity:.2%}",
                f"  - 정확도: {validation_result.stt_accuracy.accuracy:.2%}", ""
            ])

        # 발음 평가
        if validation_result.pronunciation:
            report_lines.extend([
                "[ 발음 평가 ]",
                f"  - 피치 정확도: {validation_result.pronunciation.pitch_accuracy:.2%}",
                f"  - 타이밍 정확도: {validation_result.pronunciation.timing_accuracy:.2%}",
                f"  - 강도 일치도: {validation_result.pronunciation.intensity_match:.2%}",
                f"  - 스펙트럼 유사도: {validation_result.pronunciation.spectral_similarity:.2%}",
                f"  - 전체 점수: {validation_result.pronunciation.overall_score:.2%}",
                ""
            ])

        # 종합 평가
        if validation_result.overall_quality:
            report_lines.extend([
                "[ 종합 평가 ]",
                f"  품질 수준: {validation_result.overall_quality.value.upper()}",
                ""
            ])

        # 권장사항
        if validation_result.recommendations:
            report_lines.extend(["[ 권장사항 ]"])
            for rec in validation_result.recommendations:
                report_lines.append(f"  • {rec}")

        report_lines.append("=" * 50)

        report = "\n".join(report_lines)

        # 파일로 저장
        if output_path:
            output_path = Path(output_path)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"보고서 저장: {output_path}")

        return report


# 메인 실행 코드
if __name__ == "__main__":
    # 테스트
    validator = QualityValidator()

    # 참조 파일 테스트
    if settings.REFERENCE_FILES_PATH.exists():
        test_files = list(settings.REFERENCE_FILES_PATH.glob("*.wav"))[:1]

        for test_file in test_files:
            logger.info(f"품질 검증 테스트: {test_file}")

            # 종합 검증
            result = validator.validate_comprehensive(
                test_file,
                transcribed_text="테스트 전사 텍스트",
                reference_text="테스트 참조 텍스트")

            # 보고서 생성
            report = validator.generate_report(result)
            print(report)
