"""
한국어 음성 최적화 모듈
한국어 특성에 맞춘 음성 처리 및 최적화 기능
"""

import warnings
warnings.filterwarnings('ignore')

import re
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
except ImportError:
    parselmouth = None
from pydub import AudioSegment

# 한국어 처리
import jamo
try:
    from konlpy.tag import Okt, Komoran
except ImportError:
    Okt = Komoran = None

# 텍스트 처리
import unicodedata

# 프로젝트 모듈
from config import settings
from utils import (
    FileHandler,
    file_handler,
    get_logger,
    log_execution_time,
    handle_errors,
    AudioProcessingError
)

logger = get_logger(__name__)


# ========== 한국어 음성학 상수 ==========

class KoreanPhonemes:
    """한국어 음소 정의"""

    # 초성 (자음)
    INITIAL_CONSONANTS = [
        'ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ',
        'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'
    ]

    # 중성 (모음)
    VOWELS = [
        'ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ',
        'ㅗ', 'ㅘ', 'ㅙ', 'ㅚ', 'ㅛ', 'ㅜ', 'ㅝ', 'ㅞ',
        'ㅟ', 'ㅠ', 'ㅡ', 'ㅢ', 'ㅣ'
    ]

    # 종성 (받침)
    FINAL_CONSONANTS = [
        '', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ',
        'ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ',
        'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'
    ]

    # 음성학적 분류
    PLOSIVES = ['ㄱ', 'ㄲ', 'ㄷ', 'ㄸ', 'ㅂ', 'ㅃ']  # 파열음
    FRICATIVES = ['ㅅ', 'ㅆ', 'ㅎ']  # 마찰음
    AFFRICATES = ['ㅈ', 'ㅉ', 'ㅊ']  # 파찰음
    NASALS = ['ㄴ', 'ㅁ', 'ㅇ']  # 비음
    LIQUIDS = ['ㄹ']  # 유음

    # 모음 분류
    FRONT_VOWELS = ['ㅣ', 'ㅔ', 'ㅐ', 'ㅖ', 'ㅒ']  # 전설모음
    BACK_VOWELS = ['ㅡ', 'ㅓ', 'ㅏ', 'ㅜ', 'ㅗ']  # 후설모음
    HIGH_VOWELS = ['ㅣ', 'ㅡ', 'ㅜ']  # 고모음
    LOW_VOWELS = ['ㅏ', 'ㅓ']  # 저모음


@dataclass
class KoreanSyllable:
    """한국어 음절 데이터"""
    text: str
    initial: str  # 초성
    vowel: str    # 중성
    final: str    # 종성
    start_time: float
    end_time: float
    pitch: Optional[float] = None
    intensity: Optional[float] = None

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def has_final(self) -> bool:
        return self.final != ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'text': self.text,
            'initial': self.initial,
            'vowel': self.vowel,
            'final': self.final,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': self.duration,
            'pitch': self.pitch,
            'intensity': self.intensity
        }


class TonePattern(Enum):
    """한국어 운율 패턴"""
    STATEMENT = "statement"      # 평서문
    QUESTION = "question"        # 의문문
    EXCLAMATION = "exclamation"  # 감탄문
    COMMAND = "command"          # 명령문


# ========== 한국어 텍스트 처리 ==========

class KoreanTextProcessor:
    """한국어 텍스트 처리 클래스"""

    def __init__(self):
        """초기화"""
        try:
            self.okt = Okt()
            self.komoran = Komoran()
            self.use_nlp = True
        except:
            logger.warning("한국어 형태소 분석기 로딩 실패")
            self.use_nlp = False

        logger.info("KoreanTextProcessor 초기화 완료")

    @handle_errors(context="normalize_korean_text")
    def normalize_korean_text(self, text: str) -> str:
        """
        한국어 텍스트 정규화

        Args:
            text: 입력 텍스트

        Returns:
            정규화된 텍스트
        """
        # Unicode 정규화 (NFC)
        text = unicodedata.normalize('NFC', text)

        # 특수문자 제거 (한글, 공백, 기본 문장부호만 유지)
        text = re.sub(r'[^가-힣ㄱ-ㅎㅏ-ㅣ\s\.\,\!\?]', '', text)

        # 중복 공백 제거
        text = re.sub(r'\s+', ' ', text)

        # 앞뒤 공백 제거
        text = text.strip()

        return text

    @handle_errors(context="decompose_syllables")
    def decompose_syllables(self, text: str) -> List[Tuple[str, str, str, str]]:
        """
        한글 음절 분해

        Args:
            text: 한글 텍스트

        Returns:
            [(음절, 초성, 중성, 종성), ...]
        """
        syllables = []

        for char in text:
            if '가' <= char <= '힣':
                # 자모 분해
                decomposed = jamo.h2j(char)
                jamos = list(jamo.j2hcj(decomposed))

                # 초성, 중성, 종성 분리
                initial = jamos[0] if len(jamos) > 0 else ''
                vowel = jamos[1] if len(jamos) > 1 else ''
                final = jamos[2] if len(jamos) > 2 else ''

                syllables.append((char, initial, vowel, final))
            elif char in 'ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ':
                # 단독 자음
                syllables.append((char, char, '', ''))
            elif char in 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ':
                # 단독 모음
                syllables.append((char, '', char, ''))
            else:
                # 기타 문자 (공백, 문장부호 등)
                if char.strip():
                    syllables.append((char, '', '', ''))

        return syllables

    @handle_errors(context="analyze_morphemes")
    def analyze_morphemes(self, text: str) -> List[Tuple[str, str]]:
        """
        형태소 분석

        Args:
            text: 한글 텍스트

        Returns:
            [(형태소, 품사), ...]
        """
        if not self.use_nlp:
            return [(text, 'UNKNOWN')]

        try:
            # Komoran 우선 사용
            morphemes = self.komoran.pos(text)
        except:
            try:
                # Okt 대체 사용
                morphemes = self.okt.pos(text)
            except:
                logger.warning("형태소 분석 실패")
                morphemes = [(text, 'UNKNOWN')]

        return morphemes

    @handle_errors(context="syllabify_text")
    def syllabify_text(self, text: str) -> List[str]:
        """
        텍스트를 음절 단위로 분리

        Args:
            text: 한글 텍스트

        Returns:
            음절 리스트
        """
        text = self.normalize_korean_text(text)
        syllables = []

        for char in text:
            if '가' <= char <= '힣':
                syllables.append(char)
            elif char == ' ':
                # 공백은 유지 (단어 경계)
                if syllables and syllables[-1] != ' ':
                    syllables.append(' ')

        return syllables


# ========== 한국어 음성 분석 ==========

class KoreanSpeechAnalyzer:
    """한국어 음성 분석 클래스"""

    def __init__(self):
        """초기화"""
        self.text_processor = KoreanTextProcessor()
        logger.info("KoreanSpeechAnalyzer 초기화 완료")

    @handle_errors(context="analyze_korean_prosody")
    @log_execution_time
    def analyze_korean_prosody(
        self,
        audio_path: Union[str, Path],
        text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        한국어 운율 분석

        Args:
            audio_path: 오디오 파일 경로
            text: 발화 텍스트 (옵션)

        Returns:
            운율 분석 결과
        """
        audio_path = Path(audio_path)

        try:
            # 오디오 로드
            sound = parselmouth.Sound(str(audio_path))

            # 피치 추출
            pitch = sound.to_pitch(
                time_step=0.01,
                pitch_floor=settings.PITCH_FLOOR,
                pitch_ceiling=settings.PITCH_CEILING
            )

            # 인텐시티 추출
            intensity = sound.to_intensity()

            # 운율 특징 추출
            prosody_features = {
                'pitch': self._extract_pitch_features(pitch),
                'intensity': self._extract_intensity_features(intensity),
                'duration': float(sound.duration),
                'speech_rate': self._calculate_speech_rate(sound, text)
            }

            # 운율 패턴 분류
            prosody_features['tone_pattern'] = self._classify_tone_pattern(
                prosody_features['pitch']
            )

            # 텍스트가 있으면 음절별 분석
            if text:
                syllables = self.text_processor.syllabify_text(text)
                prosody_features['syllable_count'] = len(syllables)
                prosody_features['syllables'] = self._analyze_syllable_prosody(
                    sound, pitch, intensity, syllables
                )

            return prosody_features

        except Exception as e:
            raise AudioProcessingError(f"한국어 운율 분석 실패: {str(e)}")

    def _extract_pitch_features(self, pitch) -> Dict[str, float]:
        """피치 특징 추출"""
        pitch_values = []
        for t in pitch.xs():
            value = pitch.get_value_at_time(t)
            if value and not np.isnan(value):
                pitch_values.append(value)

        if not pitch_values:
            return {
                'mean': 0.0, 'std': 0.0, 'min': 0.0, 'max': 0.0,
                'range': 0.0, 'slope': 0.0
            }

        pitch_array = np.array(pitch_values)

        # 선형 회귀로 기울기 계산
        x = np.arange(len(pitch_array))
        slope, _ = np.polyfit(x, pitch_array, 1) if len(pitch_array) > 1 else (0.0, 0.0)

        return {
            'mean': float(np.mean(pitch_array)),
            'std': float(np.std(pitch_array)),
            'min': float(np.min(pitch_array)),
            'max': float(np.max(pitch_array)),
            'range': float(np.max(pitch_array) - np.min(pitch_array)),
            'slope': float(slope)  # 피치 변화 기울기
        }

    def _extract_intensity_features(self, intensity) -> Dict[str, float]:
        """인텐시티 특징 추출"""
        intensity_values = []
        for t in np.arange(0, intensity.duration, 0.01):
            value = intensity.get(t)
            if value and not np.isnan(value):
                intensity_values.append(value)

        if not intensity_values:
            return {'mean': 0.0, 'std': 0.0, 'min': 0.0, 'max': 0.0}

        intensity_array = np.array(intensity_values)

        return {
            'mean': float(np.mean(intensity_array)),
            'std': float(np.std(intensity_array)),
            'min': float(np.min(intensity_array)),
            'max': float(np.max(intensity_array))
        }

    def _calculate_speech_rate(self, sound, text: Optional[str]) -> float:
        """발화 속도 계산 (음절/초)"""
        if not text:
            return 0.0

        syllables = self.text_processor.syllabify_text(text)
        syllable_count = len([s for s in syllables if s != ' '])

        return syllable_count / sound.duration if sound.duration > 0 else 0.0

    def _classify_tone_pattern(self, pitch_features: Dict[str, float]) -> str:
        """운율 패턴 분류"""
        slope = pitch_features.get('slope', 0)
        pitch_range = pitch_features.get('range', 0)

        # 기울기와 범위로 패턴 분류
        if slope > 5:  # 상승 운율
            if pitch_range > 100:
                return TonePattern.QUESTION.value
            else:
                return TonePattern.EXCLAMATION.value
        elif slope < -5:  # 하강 운율
            if pitch_range > 80:
                return TonePattern.COMMAND.value
            else:
                return TonePattern.STATEMENT.value
        else:  # 평탄한 운율
            return TonePattern.STATEMENT.value

    def _analyze_syllable_prosody(
        self,
        sound,
        pitch,
        intensity,
        syllables: List[str]
    ) -> List[Dict[str, Any]]:
        """음절별 운율 분석"""
        if not syllables:
            return []

        # 음절 경계 추정 (균등 분할)
        duration_per_syllable = sound.duration / len(syllables)

        syllable_prosody = []
        for i, syllable in enumerate(syllables):
            if syllable == ' ':
                continue

            start_time = i * duration_per_syllable
            end_time = (i + 1) * duration_per_syllable

            # 해당 구간의 피치와 인텐시티
            pitch_value = pitch.get_mean(start_time, end_time)
            intensity_value = intensity.get_average(start_time, end_time)

            syllable_prosody.append({
                'text': syllable,
                'start_time': start_time,
                'end_time': end_time,
                'duration': duration_per_syllable,
                'pitch': pitch_value if pitch_value else 0.0,
                'intensity': intensity_value if intensity_value else 0.0
            })

        return syllable_prosody


# ========== 한국어 음성 최적화 ==========

class KoreanAudioOptimizer:
    """한국어 음성 최적화 클래스"""

    def __init__(self):
        """초기화"""
        self.text_processor = KoreanTextProcessor()
        self.speech_analyzer = KoreanSpeechAnalyzer()
        self.file_handler = file_handler

        logger.info("KoreanAudioOptimizer 초기화 완료")

    @handle_errors(context="optimize_korean_speech")
    @log_execution_time
    def optimize_korean_speech(
        self,
        audio_path: Union[str, Path],
        output_path: Optional[Path] = None,
        text: Optional[str] = None,
        target_gender: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        한국어 음성 최적화

        Args:
            audio_path: 입력 오디오 파일
            output_path: 출력 파일 경로
            text: 발화 텍스트
            target_gender: 목표 성별 ('male', 'female', 'child')

        Returns:
            최적화 결과
        """
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {audio_path}")

        try:
            result = {
                'original_path': str(audio_path),
                'optimization_steps': []
            }

            # 1. 음성 분석
            logger.debug("음성 분석 중...")
            analysis = self.speech_analyzer.analyze_korean_prosody(audio_path, text)
            result['analysis'] = analysis

            # 2. 피치 범위 조정
            logger.debug("피치 범위 조정 중...")
            temp_path = self._adjust_pitch_range(audio_path, target_gender)
            result['optimization_steps'].append('pitch_adjustment')

            # 3. 발화 속도 최적화
            if analysis['speech_rate'] > 0:
                logger.debug("발화 속도 최적화 중...")
                temp_path = self._optimize_speech_rate(
                    temp_path,
                    current_rate=analysis['speech_rate']
                )
                result['optimization_steps'].append('speech_rate_optimization')

            # 4. 한국어 포먼트 강화
            logger.debug("한국어 포먼트 강화 중...")
            temp_path = self._enhance_korean_formants(temp_path)
            result['optimization_steps'].append('formant_enhancement')

            # 5. 자음 강화
            logger.debug("자음 강화 중...")
            temp_path = self._enhance_consonants(temp_path)
            result['optimization_steps'].append('consonant_enhancement')

            # 최종 파일 저장
            if output_path is None:
                output_path = audio_path.parent / f"{audio_path.stem}_optimized.wav"
            else:
                output_path = Path(output_path)

            self.file_handler.copy_file(temp_path, output_path, overwrite=True)
            self.file_handler.safe_delete(temp_path)

            result['output_path'] = str(output_path)
            result['success'] = True

            logger.info(f"한국어 음성 최적화 완료: {audio_path.name}")
            return result

        except Exception as e:
            raise AudioProcessingError(f"한국어 음성 최적화 실패: {str(e)}")

    def _adjust_pitch_range(
        self,
        audio_path: Path,
        target_gender: Optional[str]
    ) -> Path:
        """피치 범위 조정"""
        # 목표 피치 범위 설정
        if target_gender == 'male':
            target_range = settings.KOREAN_PITCH_RANGE_MALE
        elif target_gender == 'female':
            target_range = settings.KOREAN_PITCH_RANGE_FEMALE
        elif target_gender == 'child':
            target_range = settings.KOREAN_PITCH_RANGE_CHILD
        else:
            # 자동 감지
            return audio_path

        try:
            # Parselmouth로 피치 조정
            sound = parselmouth.Sound(str(audio_path))

            # 현재 피치 분석
            pitch = sound.to_pitch()
            current_mean = parselmouth.praat.call(pitch, "Get mean", 0, 0, "Hertz")

            if np.isnan(current_mean) or current_mean == 0:
                return audio_path

            # 목표 평균 피치
            target_mean = (target_range[0] + target_range[1]) / 2

            # 피치 시프트 비율
            shift_factor = target_mean / current_mean

            # 피치 변경 (PSOLA)
            manipulated = parselmouth.praat.call(
                sound, "To Manipulation", 0.01,
                settings.PITCH_FLOOR, settings.PITCH_CEILING
            )

            pitch_tier = parselmouth.praat.call(manipulated, "Extract pitch tier")
            parselmouth.praat.call(pitch_tier, "Multiply frequencies", 
                                 sound.xmin, sound.xmax, shift_factor)
            parselmouth.praat.call([pitch_tier, manipulated], "Replace pitch tier")

            result_sound = parselmouth.praat.call(manipulated, "Get resynthesis (overlap-add)")

            # 임시 파일로 저장
            temp_path = self.file_handler.create_temp_file(suffix=".wav")
            result_sound.save(str(temp_path), "WAV")

            return temp_path

        except Exception as e:
            logger.warning(f"피치 조정 실패: {e}")
            return audio_path

    def _optimize_speech_rate(
        self,
        audio_path: Path,
        current_rate: float,
        target_rate: float = 4.0  # 목표: 초당 4음절
    ) -> Path:
        """발화 속도 최적화"""
        if abs(current_rate - target_rate) < 0.5:
            return audio_path

        try:
            # 속도 조정 비율
            rate_factor = current_rate / target_rate

            # PyDub으로 속도 조정
            audio = AudioSegment.from_file(str(audio_path))

            # 속도 변경 (피치 유지)
            if rate_factor > 1.0:  # 너무 빠름 -> 느리게
                adjusted = audio._spawn(
                    audio.raw_data,
                    overrides={
                        "frame_rate": int(audio.frame_rate * rate_factor)
                    }
                ).set_frame_rate(audio.frame_rate)
            else:  # 너무 느림 -> 빠르게
                adjusted = audio._spawn(
                    audio.raw_data,
                    overrides={
                        "frame_rate": int(audio.frame_rate * rate_factor)
                    }
                ).set_frame_rate(audio.frame_rate)

            # 임시 파일로 저장
            temp_path = self.file_handler.create_temp_file(suffix=".wav")
            adjusted.export(str(temp_path), format="wav")

            return temp_path

        except Exception as e:
            logger.warning(f"발화 속도 최적화 실패: {e}")
            return audio_path

    def _enhance_korean_formants(self, audio_path: Path) -> Path:
        """한국어 포먼트 강화"""
        try:
            # 오디오 로드
            y, sr = librosa.load(str(audio_path), sr=None)

            # 한국어 모음 포먼트 주파수 대역
            # F1: 300-800Hz (저모음), F2: 900-2500Hz (전설/후설)
            from scipy.signal import butter, sosfilt

            # F1 강화 필터
            sos_f1 = butter(2, [300, 800], btype='band', fs=sr, output='sos')
            f1_enhanced = sosfilt(sos_f1, y)

            # F2 강화 필터
            sos_f2 = butter(2, [900, 2500], btype='band', fs=sr, output='sos')
            f2_enhanced = sosfilt(sos_f2, y)

            # 원본과 합성 (한국어 특성 강조)
            enhanced = y + 0.2 * f1_enhanced + 0.15 * f2_enhanced

            # 정규화
            enhanced = enhanced / np.max(np.abs(enhanced))

            # 임시 파일로 저장
            temp_path = self.file_handler.create_temp_file(suffix=".wav")
            sf.write(str(temp_path), enhanced, sr)

            return temp_path

        except Exception as e:
            logger.warning(f"포먼트 강화 실패: {e}")
            return audio_path

    def _enhance_consonants(self, audio_path: Path) -> Path:
        """한국어 자음 강화"""
        try:
            # 오디오 로드
            y, sr = librosa.load(str(audio_path), sr=None)

            # 고주파 강조 (자음 영역: 2000Hz 이상)
            from scipy.signal import butter, sosfilt

            # 고주파 통과 필터
            sos_high = butter(2, 2000, btype='high', fs=sr, output='sos')
            high_freq = sosfilt(sos_high, y)

            # 파열음/마찰음 검출 및 강화
            # 에너지가 급격히 변하는 구간 찾기
            energy = librosa.feature.rms(y=y, hop_length=int(sr*0.01))[0]
            energy_diff = np.diff(energy)

            # 자음 구간 마스크 생성
            consonant_mask = np.abs(energy_diff) > np.std(energy_diff) * 1.5

            # 강화 적용
            enhanced = y.copy()
            hop_length = int(sr * 0.01)

            for i, is_consonant in enumerate(consonant_mask):
                if is_consonant:
                    start = i * hop_length
                    end = min((i + 1) * hop_length, len(y))
                    enhanced[start:end] += 0.3 * high_freq[start:end]

            # 정규화
            enhanced = enhanced / np.max(np.abs(enhanced))

            # 임시 파일로 저장
            temp_path = self.file_handler.create_temp_file(suffix=".wav")
            sf.write(str(temp_path), enhanced, sr)

            return temp_path

        except Exception as e:
            logger.warning(f"자음 강화 실패: {e}")
            return audio_path


# ========== 한국어 운율 생성 ==========

class KoreanProsodyGenerator:
    """한국어 운율 생성 클래스"""

    def __init__(self):
        """초기화"""
        self.text_processor = KoreanTextProcessor()
        logger.info("KoreanProsodyGenerator 초기화 완료")

    @handle_errors(context="generate_prosody_pattern")
    def generate_prosody_pattern(
        self,
        text: str,
        pattern_type: str = "statement"
    ) -> Dict[str, Any]:
        """
        텍스트에 대한 운율 패턴 생성

        Args:
            text: 한글 텍스트
            pattern_type: 문장 유형

        Returns:
            운율 패턴 정보
        """
        # 텍스트 정규화 및 음절 분리
        normalized_text = self.text_processor.normalize_korean_text(text)
        syllables = self.text_processor.syllabify_text(normalized_text)

        if not syllables:
            return {}

        # 패턴별 운율 곡선 생성
        if pattern_type == TonePattern.QUESTION.value:
            pitch_pattern = self._generate_question_pattern(len(syllables))
        elif pattern_type == TonePattern.EXCLAMATION.value:
            pitch_pattern = self._generate_exclamation_pattern(len(syllables))
        elif pattern_type == TonePattern.COMMAND.value:
            pitch_pattern = self._generate_command_pattern(len(syllables))
        else:  # statement
            pitch_pattern = self._generate_statement_pattern(len(syllables))

        # 음절별 운율 정보 생성
        prosody_info = []
        for i, syllable in enumerate(syllables):
            if syllable == ' ':
                continue

            prosody_info.append({
                'syllable': syllable,
                'index': i,
                'relative_pitch': pitch_pattern[i],
                'intensity': self._calculate_syllable_intensity(syllable, i, len(syllables))
            })

        return {
            'text': normalized_text,
            'pattern_type': pattern_type,
            'syllables': prosody_info,
            'pitch_contour': pitch_pattern.tolist()
        }

    def _generate_statement_pattern(self, length: int) -> np.ndarray:
        """평서문 운율 패턴 (하강)"""
        x = np.linspace(0, 1, length)
        # 완만한 하강 곡선
        pattern = 1.0 - 0.3 * x - 0.1 * np.sin(2 * np.pi * x)
        return pattern

    def _generate_question_pattern(self, length: int) -> np.ndarray:
        """의문문 운율 패턴 (상승)"""
        x = np.linspace(0, 1, length)
        # 끝부분 급격한 상승
        pattern = 0.8 + 0.4 * x + 0.3 * np.exp(2 * (x - 0.5))
        return pattern

    def _generate_exclamation_pattern(self, length: int) -> np.ndarray:
        """감탄문 운율 패턴 (높은 시작, 급하강)"""
        x = np.linspace(0, 1, length)
        # 높게 시작해서 급격히 하강
        pattern = 1.3 * np.exp(-2 * x) + 0.2
        return pattern

    def _generate_command_pattern(self, length: int) -> np.ndarray:
        """명령문 운율 패턴 (강한 강세)"""
        x = np.linspace(0, 1, length)
        # 중간에 강한 피크
        pattern = 1.0 + 0.5 * np.exp(-10 * (x - 0.3) ** 2)
        return pattern

    def _calculate_syllable_intensity(
        self,
        syllable: str,
        position: int,
        total: int
    ) -> float:
        """음절 강도 계산"""
        # 위치별 기본 강도
        if position == 0:  # 첫 음절
            base_intensity = 1.1
        elif position == total - 1:  # 마지막 음절
            base_intensity = 0.9
        else:
            base_intensity = 1.0

        # 음절 구조별 조정
        decomposed = self.text_processor.decompose_syllables(syllable)
        if decomposed:
            _, initial, vowel, final = decomposed[0]

            # 종성이 있으면 강도 증가
            if final:
                base_intensity *= 1.1

            # 강한 자음(파열음, 파찰음)이면 강도 증가
            if initial in KoreanPhonemes.PLOSIVES + KoreanPhonemes.AFFRICATES:
                base_intensity *= 1.15

        return base_intensity


# 메인 실행 코드
if __name__ == "__main__":
    # 테스트
    optimizer = KoreanAudioOptimizer()

    # 테스트 텍스트
    test_text = "안녕하세요. 반갑습니다."

    # 참조 파일 테스트
    if settings.REFERENCE_FILES_PATH.exists():
        test_files = list(settings.REFERENCE_FILES_PATH.glob("*.wav"))[:1]

        for test_file in test_files:
            logger.info(f"한국어 음성 최적화 테스트: {test_file}")

            result = optimizer.optimize_korean_speech(
                test_file,
                text=test_text,
                target_gender='female'
            )

            if result['success']:
                logger.info(f"최적화 단계: {result['optimization_steps']}")
                if 'analysis' in result:
                    analysis = result['analysis']
                    logger.info(f"발화 속도: {analysis.get('speech_rate', 0):.1f} 음절/초")
                    logger.info(f"운율 패턴: {analysis.get('tone_pattern', 'unknown')}")