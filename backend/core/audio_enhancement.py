"""
음질 향상 모듈
노이즈 제거, 음성 강화, EQ 조정 등 오디오 품질 개선 기능
"""

import warnings

warnings.filterwarnings('ignore')

from pathlib import Path
from typing import Optional, Tuple, Dict, Any, Union
import numpy as np
from scipy import signal
from scipy.signal import butter, filtfilt, sosfilt

# 오디오 처리
import librosa
import soundfile as sf
import noisereduce as nr
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range

# 프로젝트 모듈
from config import settings
from utils import (FileHandler, file_handler, get_logger, log_execution_time,
                   handle_errors, AudioProcessingError)

logger = get_logger(__name__)


class NoiseReducer:
    """노이즈 제거 클래스"""

    def __init__(self,
                 noise_reduction_strength: float = None,
                 stationary: bool = True):
        """
        초기화

        Args:
            noise_reduction_strength: 노이즈 제거 강도 (0.0 ~ 1.0)
            stationary: 정적 노이즈 가정 여부
        """
        self.strength = noise_reduction_strength or settings.NOISE_REDUCTION_STRENGTH
        self.stationary = stationary

        logger.info(f"NoiseReducer 초기화: 강도={self.strength:.2f}, "
                    f"정적노이즈={self.stationary}")

    @handle_errors(context="reduce_noise")
    @log_execution_time
    def reduce_noise(self,
                     audio_path: Union[str, Path],
                     output_path: Optional[Path] = None,
                     noise_profile_duration: float = 1.0) -> Path:
        """
        노이즈 제거

        Args:
            audio_path: 입력 오디오 파일
            output_path: 출력 파일 경로
            noise_profile_duration: 노이즈 프로파일 추출 구간 (초)

        Returns:
            처리된 오디오 파일 경로
        """
        try:
            audio_path = Path(audio_path)

            # 오디오 로드
            audio, sr = librosa.load(str(audio_path), sr=None)

            # 노이즈 프로파일 추출 (처음 n초)
            noise_profile_samples = int(noise_profile_duration * sr)
            noise_profile = audio[:noise_profile_samples]

            # 노이즈 제거
            reduced_noise = nr.reduce_noise(y=audio,
                                            sr=sr,
                                            y_noise=noise_profile,
                                            prop_decrease=self.strength,
                                            stationary=self.stationary)

            # 출력 경로 설정
            if output_path is None:
                output_path = audio_path.parent / f"{audio_path.stem}_denoised.wav"

            # 저장
            sf.write(str(output_path), reduced_noise, sr)

            logger.info(f"노이즈 제거 완료: {audio_path.name}")
            return output_path

        except Exception as e:
            raise AudioProcessingError(f"노이즈 제거 실패: {str(e)}")

    @handle_errors(context="apply_spectral_subtraction")
    def apply_spectral_subtraction(self,
                                   audio: np.ndarray,
                                   sr: int,
                                   noise_profile: Optional[np.ndarray] = None,
                                   alpha: float = 2.0) -> np.ndarray:
        """
        스펙트럴 차감법으로 노이즈 제거

        Args:
            audio: 오디오 신호
            sr: 샘플레이트
            noise_profile: 노이즈 프로파일
            alpha: 차감 계수

        Returns:
            노이즈 제거된 신호
        """
        # STFT
        D = librosa.stft(audio)
        magnitude = np.abs(D)
        phase = np.angle(D)

        # 노이즈 스펙트럼 추정
        if noise_profile is None:
            # 처음 0.5초를 노이즈로 가정
            noise_frames = int(0.5 * sr / 512)
            noise_spectrum = np.mean(magnitude[:, :noise_frames],
                                     axis=1,
                                     keepdims=True)
        else:
            noise_D = librosa.stft(noise_profile)
            noise_spectrum = np.mean(np.abs(noise_D), axis=1, keepdims=True)

        # 스펙트럴 차감
        clean_magnitude = magnitude - alpha * noise_spectrum
        clean_magnitude = np.maximum(clean_magnitude,
                                     0.1 * magnitude)  # 최소값 유지

        # 역변환
        clean_D = clean_magnitude * np.exp(1j * phase)
        clean_audio = librosa.istft(clean_D)

        return clean_audio


class AudioEnhancer:
    """음성 강화 클래스"""

    def __init__(self):
        """초기화"""
        self.file_handler = file_handler
        logger.info("AudioEnhancer 초기화 완료")

    @handle_errors(context="enhance_speech")
    @log_execution_time
    def enhance_speech(self,
                       audio_path: Union[str, Path],
                       output_path: Optional[Path] = None,
                       enhancement_level: str = "medium") -> Path:
        """
        음성 강화

        Args:
            audio_path: 입력 오디오 파일
            output_path: 출력 파일 경로
            enhancement_level: 강화 수준 ('low', 'medium', 'high')

        Returns:
            처리된 오디오 파일 경로
        """
        try:
            audio_path = Path(audio_path)

            # 강화 파라미터 설정
            params = self._get_enhancement_params(enhancement_level)

            # 오디오 로드
            audio, sr = librosa.load(str(audio_path), sr=None)

            # 1. 프리엠파시스 필터
            enhanced = self._apply_preemphasis(audio, params['preemphasis'])

            # 2. 스펙트럴 강화
            enhanced = self._spectral_enhancement(enhanced, sr,
                                                  params['spectral_floor'])

            # 3. 포먼트 강화
            enhanced = self._enhance_formants(enhanced, sr)

            # 4. 다이나믹 레인지 조정
            enhanced = self._adjust_dynamics(enhanced,
                                             params['compression_ratio'])

            # 정규화
            enhanced = enhanced / np.max(np.abs(enhanced))

            # 출력 경로 설정
            if output_path is None:
                output_path = audio_path.parent / f"{audio_path.stem}_enhanced.wav"

            # 저장
            sf.write(str(output_path), enhanced, sr)

            logger.info(
                f"음성 강화 완료: {audio_path.name} (레벨: {enhancement_level})")
            return output_path

        except Exception as e:
            raise AudioProcessingError(f"음성 강화 실패: {str(e)}")

    def _get_enhancement_params(self, level: str) -> Dict[str, float]:
        """강화 수준별 파라미터"""
        params_map = {
            'low': {
                'preemphasis': 0.95,
                'spectral_floor': 0.1,
                'compression_ratio': 2.0
            },
            'medium': {
                'preemphasis': 0.97,
                'spectral_floor': 0.05,
                'compression_ratio': 3.0
            },
            'high': {
                'preemphasis': 0.98,
                'spectral_floor': 0.02,
                'compression_ratio': 4.0
            }
        }
        return params_map.get(level, params_map['medium'])

    def _apply_preemphasis(self,
                           audio: np.ndarray,
                           alpha: float = 0.97) -> np.ndarray:
        """프리엠파시스 필터 적용"""
        return np.append(audio[0], audio[1:] - alpha * audio[:-1])

    def _spectral_enhancement(self,
                              audio: np.ndarray,
                              sr: int,
                              spectral_floor: float = 0.1) -> np.ndarray:
        """스펙트럴 강화"""
        # STFT
        D = librosa.stft(audio)
        magnitude = np.abs(D)
        phase = np.angle(D)

        # 스펙트럴 플로어 적용
        enhanced_magnitude = np.maximum(magnitude,
                                        spectral_floor * np.max(magnitude))

        # Wiener 필터 근사
        signal_power = enhanced_magnitude**2
        noise_power = np.mean(signal_power[:, :10], axis=1, keepdims=True)
        wiener_gain = signal_power / (signal_power + noise_power)
        enhanced_magnitude = enhanced_magnitude * wiener_gain

        # 역변환
        enhanced_D = enhanced_magnitude * np.exp(1j * phase)
        enhanced_audio = librosa.istft(enhanced_D)

        return enhanced_audio

    def _enhance_formants(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """포먼트 강화"""
        # 포먼트 주파수 대역 강조 (한국어 모음 특성 고려)
        # F1: 300-800Hz, F2: 800-2500Hz

        # F1 대역 필터
        sos_f1 = signal.butter(4, [300, 800],
                               btype='band',
                               fs=sr,
                               output='sos')
        f1_band = sosfilt(sos_f1, audio)

        # F2 대역 필터
        sos_f2 = signal.butter(4, [800, 2500],
                               btype='band',
                               fs=sr,
                               output='sos')
        f2_band = sosfilt(sos_f2, audio)

        # 강화된 신호 = 원본 + 강조된 포먼트 대역
        enhanced = audio + 0.3 * f1_band + 0.2 * f2_band

        return enhanced

    def _adjust_dynamics(self,
                         audio: np.ndarray,
                         ratio: float = 3.0) -> np.ndarray:
        """다이나믹 레인지 조정"""
        # 간단한 컴프레서 구현
        threshold = 0.7

        # 엔벨로프 추출
        envelope = np.abs(audio)

        # 컴프레션 적용
        compressed = np.where(envelope > threshold,
                              threshold + (envelope - threshold) / ratio,
                              envelope)

        # 원본 신호에 적용
        compressed_audio = audio * (compressed / (envelope + 1e-10))

        return compressed_audio


class EQProcessor:
    """EQ 처리 클래스"""

    def __init__(self):
        """초기화"""
        self.low_freq = settings.EQ_LOW_FREQ
        self.high_freq = settings.EQ_HIGH_FREQ
        logger.info(f"EQProcessor 초기화: 대역={self.low_freq}-{self.high_freq}Hz")

    @handle_errors(context="apply_eq")
    @log_execution_time
    def apply_eq(self,
                 audio_path: Union[str, Path],
                 output_path: Optional[Path] = None,
                 eq_preset: str = "speech") -> Path:
        """
        EQ 적용

        Args:
            audio_path: 입력 오디오 파일
            output_path: 출력 파일 경로
            eq_preset: EQ 프리셋 ('speech', 'music', 'flat', 'custom')

        Returns:
            처리된 오디오 파일 경로
        """
        try:
            audio_path = Path(audio_path)

            # 오디오 로드
            audio, sr = librosa.load(str(audio_path), sr=None)

            # EQ 곡선 가져오기
            eq_curve = self._get_eq_curve(eq_preset, sr)

            # 주파수 도메인 변환
            D = librosa.stft(audio)
            magnitude = np.abs(D)
            phase = np.angle(D)

            # EQ 적용
            freqs = librosa.fft_frequencies(sr=sr)
            eq_gains = np.interp(freqs, eq_curve['frequencies'],
                                 eq_curve['gains'])
            eq_gains = eq_gains.reshape(-1, 1)

            equalized_magnitude = magnitude * eq_gains

            # 역변환
            equalized_D = equalized_magnitude * np.exp(1j * phase)
            equalized_audio = librosa.istft(equalized_D)

            # 정규화
            equalized_audio = equalized_audio / np.max(np.abs(equalized_audio))

            # 출력 경로 설정
            if output_path is None:
                output_path = audio_path.parent / f"{audio_path.stem}_eq_{eq_preset}.wav"

            # 저장
            sf.write(str(output_path), equalized_audio, sr)

            logger.info(f"EQ 적용 완료: {audio_path.name} (프리셋: {eq_preset})")
            return output_path

        except Exception as e:
            raise AudioProcessingError(f"EQ 적용 실패: {str(e)}")

    def _get_eq_curve(self, preset: str, sr: int) -> Dict[str, np.ndarray]:
        """EQ 프리셋 곡선"""
        nyquist = sr / 2

        if preset == "speech":
            # 음성 최적화 EQ
            frequencies = np.array(
                [0, 80, 200, 500, 1000, 2000, 4000, 8000, nyquist])
            gains = np.array([0.5, 0.7, 1.0, 1.2, 1.3, 1.2, 0.9, 0.7, 0.5])

        elif preset == "music":
            # 음악 EQ
            frequencies = np.array(
                [0, 60, 250, 1000, 4000, 8000, 16000, nyquist])
            gains = np.array([1.2, 1.1, 0.9, 1.0, 1.1, 1.2, 1.0, 0.8])

        elif preset == "flat":
            # 플랫 EQ
            frequencies = np.array([0, nyquist])
            gains = np.array([1.0, 1.0])

        else:  # custom
            # 사용자 정의 (한국어 음성 최적화)
            frequencies = np.array(
                [0, 100, 300, 800, 1500, 3000, 6000, nyquist])
            gains = np.array([0.6, 0.8, 1.0, 1.3, 1.2, 1.0, 0.8, 0.6])

        return {'frequencies': frequencies, 'gains': gains}

    @handle_errors(context="apply_highpass_filter")
    def apply_highpass_filter(self,
                              audio: np.ndarray,
                              sr: int,
                              cutoff_freq: float = None,
                              order: int = 5) -> np.ndarray:
        """
        하이패스 필터 적용

        Args:
            audio: 오디오 신호
            sr: 샘플레이트
            cutoff_freq: 차단 주파수
            order: 필터 차수

        Returns:
            필터링된 신호
        """
        if cutoff_freq is None:
            cutoff_freq = self.low_freq

        nyquist = sr / 2
        normalized_cutoff = cutoff_freq / nyquist

        sos = signal.butter(order,
                            normalized_cutoff,
                            btype='high',
                            output='sos')
        filtered = sosfilt(sos, audio)

        return filtered

    @handle_errors(context="apply_lowpass_filter")
    def apply_lowpass_filter(self,
                             audio: np.ndarray,
                             sr: int,
                             cutoff_freq: float = None,
                             order: int = 5) -> np.ndarray:
        """
        로우패스 필터 적용

        Args:
            audio: 오디오 신호
            sr: 샘플레이트
            cutoff_freq: 차단 주파수
            order: 필터 차수

        Returns:
            필터링된 신호
        """
        if cutoff_freq is None:
            cutoff_freq = self.high_freq

        nyquist = sr / 2
        normalized_cutoff = cutoff_freq / nyquist

        sos = signal.butter(order,
                            normalized_cutoff,
                            btype='low',
                            output='sos')
        filtered = sosfilt(sos, audio)

        return filtered


class CompressorProcessor:
    """컴프레서/리미터 처리 클래스"""

    def __init__(self):
        """초기화"""
        self.ratio = settings.COMPRESSOR_RATIO
        self.threshold = settings.COMPRESSOR_THRESHOLD
        logger.info(
            f"CompressorProcessor 초기화: 비율={self.ratio}, 임계값={self.threshold}dB"
        )

    @handle_errors(context="apply_compression")
    @log_execution_time
    def apply_compression(self,
                          audio_path: Union[str, Path],
                          output_path: Optional[Path] = None,
                          ratio: Optional[float] = None,
                          threshold: Optional[float] = None,
                          attack: float = 5.0,
                          release: float = 50.0) -> Path:
        """
        다이나믹 컴프레션 적용

        Args:
            audio_path: 입력 오디오 파일
            output_path: 출력 파일 경로
            ratio: 압축 비율
            threshold: 임계값 (dB)
            attack: 어택 시간 (ms)
            release: 릴리즈 시간 (ms)

        Returns:
            처리된 오디오 파일 경로
        """
        try:
            audio_path = Path(audio_path)

            # 파라미터 설정
            if ratio is None:
                ratio = self.ratio
            if threshold is None:
                threshold = self.threshold

            # PyDub으로 로드
            audio = AudioSegment.from_file(str(audio_path))

            # 컴프레션 적용
            compressed = compress_dynamic_range(audio,
                                                threshold=threshold,
                                                ratio=ratio,
                                                attack=attack,
                                                release=release)

            # 메이크업 게인 (자동)
            reduction_db = (audio.dBFS - threshold) * (1 - 1 / ratio)
            makeup_gain = reduction_db * 0.7  # 70% 보상
            compressed = compressed.apply_gain(makeup_gain)

            # 정규화
            compressed = normalize(compressed)

            # 출력 경로 설정
            if output_path is None:
                output_path = audio_path.parent / f"{audio_path.stem}_compressed.wav"

            # 저장
            compressed.export(str(output_path), format="wav")

            logger.info(f"컴프레션 적용 완료: {audio_path.name}")
            return output_path

        except Exception as e:
            raise AudioProcessingError(f"컴프레션 적용 실패: {str(e)}")

    @handle_errors(context="apply_limiter")
    def apply_limiter(self,
                      audio_path: Union[str, Path],
                      output_path: Optional[Path] = None,
                      ceiling: float = -0.3) -> Path:
        """
        리미터 적용

        Args:
            audio_path: 입력 오디오 파일
            output_path: 출력 파일 경로
            ceiling: 최대 레벨 (dB)

        Returns:
            처리된 오디오 파일 경로
        """
        try:
            audio_path = Path(audio_path)

            # 오디오 로드
            audio, sr = librosa.load(str(audio_path), sr=None)

            # dB로 변환
            audio_db = 20 * np.log10(np.abs(audio) + 1e-10)

            # 리미팅 적용
            limited_db = np.minimum(audio_db, ceiling)

            # 선형으로 변환
            limited = np.sign(audio) * (10**(limited_db / 20))

            # 출력 경로 설정
            if output_path is None:
                output_path = audio_path.parent / f"{audio_path.stem}_limited.wav"

            # 저장
            sf.write(str(output_path), limited, sr)

            logger.info(f"리미터 적용 완료: {audio_path.name} (ceiling: {ceiling}dB)")
            return output_path

        except Exception as e:
            raise AudioProcessingError(f"리미터 적용 실패: {str(e)}")


class AudioQualityEnhancer:
    """통합 음질 향상 클래스"""

    def __init__(self):
        """초기화"""
        self.noise_reducer = NoiseReducer()
        self.audio_enhancer = AudioEnhancer()
        self.eq_processor = EQProcessor()
        self.compressor = CompressorProcessor()
        self.file_handler = file_handler

        logger.info("AudioQualityEnhancer 초기화 완료")

    @handle_errors(context="enhance_audio_quality")
    @log_execution_time
    def enhance_audio_quality(
            self,
            audio_path: Union[str, Path],
            output_path: Optional[Path] = None,
            denoise: bool = True,
            enhance_speech: bool = True,
            apply_eq: bool = True,
            apply_compression: bool = True) -> Dict[str, Any]:
        """
        종합 음질 향상

        Args:
            audio_path: 입력 오디오 파일
            output_path: 최종 출력 파일 경로
            denoise: 노이즈 제거 여부
            enhance_speech: 음성 강화 여부
            apply_eq: EQ 적용 여부
            apply_compression: 컴프레션 적용 여부

        Returns:
            처리 결과 정보
        """
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {audio_path}")

        # 임시 파일들
        temp_files = []
        current_path = audio_path

        try:
            result = {
                'original_path': str(audio_path),
                'steps': [],
                'quality_metrics': {}
            }

            # 1. 노이즈 제거
            if denoise and settings.ENABLE_NOISE_GATE:
                logger.debug("노이즈 제거 중...")
                temp_path = self.file_handler.create_temp_file(suffix=".wav")
                current_path = self.noise_reducer.reduce_noise(
                    current_path, temp_path)
                temp_files.append(temp_path)
                result['steps'].append('noise_reduction')

            # 2. 음성 강화
            if enhance_speech:
                logger.debug("음성 강화 중...")
                temp_path = self.file_handler.create_temp_file(suffix=".wav")
                current_path = self.audio_enhancer.enhance_speech(
                    current_path, temp_path)
                temp_files.append(temp_path)
                result['steps'].append('speech_enhancement')

            # 3. EQ 적용
            if apply_eq and settings.ENABLE_EQ:
                logger.debug("EQ 적용 중...")
                temp_path = self.file_handler.create_temp_file(suffix=".wav")
                current_path = self.eq_processor.apply_eq(
                    current_path, temp_path, "speech")
                temp_files.append(temp_path)
                result['steps'].append('eq_processing')

            # 4. 컴프레션 적용
            if apply_compression and settings.ENABLE_COMPRESSOR:
                logger.debug("컴프레션 적용 중...")
                temp_path = self.file_handler.create_temp_file(suffix=".wav")
                current_path = self.compressor.apply_compression(
                    current_path, temp_path)
                temp_files.append(temp_path)
                result['steps'].append('compression')

            # 최종 파일 저장
            if output_path is None:
                output_path = audio_path.parent / f"{audio_path.stem}_enhanced.wav"
            else:
                output_path = Path(output_path)

            # 최종 파일 복사
            self.file_handler.copy_file(current_path,
                                        output_path,
                                        overwrite=True)

            # 품질 메트릭 계산
            result['quality_metrics'] = self._calculate_quality_metrics(
                audio_path, output_path)

            result['output_path'] = str(output_path)
            result['success'] = True

            logger.info(f"음질 향상 완료: {audio_path.name}")
            return result

        finally:
            # 임시 파일 정리
            for temp_file in temp_files:
                self.file_handler.safe_delete(temp_file)

    def _calculate_quality_metrics(self, original_path: Path,
                                   enhanced_path: Path) -> Dict[str, float]:
        """품질 메트릭 계산"""
        try:
            # 오디오 로드
            original, sr1 = librosa.load(str(original_path), sr=None)
            enhanced, sr2 = librosa.load(str(enhanced_path), sr=None)

            # 샘플레이트 맞추기
            if sr1 != sr2:
                enhanced = librosa.resample(enhanced,
                                            orig_sr=sr2,
                                            target_sr=sr1)

            # SNR 계산
            signal_power = np.mean(enhanced**2)
            noise_power = np.mean((original - enhanced)**2)
            snr = 10 * np.log10(signal_power / (noise_power + 1e-10))

            # 다이나믹 레인지
            dynamic_range_original = 20 * np.log10(
                np.max(np.abs(original)) / (np.std(original) + 1e-10))
            dynamic_range_enhanced = 20 * np.log10(
                np.max(np.abs(enhanced)) / (np.std(enhanced) + 1e-10))

            return {
                'snr_improvement':
                float(snr),
                'dynamic_range_original':
                float(dynamic_range_original),
                'dynamic_range_enhanced':
                float(dynamic_range_enhanced),
                'peak_reduction':
                float(np.max(np.abs(original)) - np.max(np.abs(enhanced)))
            }

        except Exception as e:
            logger.warning(f"품질 메트릭 계산 실패: {e}")
            return {}


# 메인 실행 코드
if __name__ == "__main__":
    # 테스트
    enhancer = AudioQualityEnhancer()

    # 참조 파일 처리
    if settings.REFERENCE_FILES_PATH.exists():
        test_files = list(settings.REFERENCE_FILES_PATH.glob("*.wav"))[:1]

        for test_file in test_files:
            logger.info(f"테스트 파일 향상: {test_file}")

            result = enhancer.enhance_audio_quality(
                test_file,
                test_file.parent / f"{test_file.stem}_enhanced_test.wav")

            if result['success']:
                logger.info(f"처리 단계: {result['steps']}")
                if result['quality_metrics']:
                    logger.info(
                        f"SNR 개선: {result['quality_metrics']['snr_improvement']:.1f}dB"
                    )
