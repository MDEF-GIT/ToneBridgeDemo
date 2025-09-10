"""
한국어 음절 분절 모듈
음성 신호에서 한국어 음절 단위로 분절하는 기능
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
    from scipy import signal
    from scipy.signal import find_peaks
except ImportError:
    signal = None
    find_peaks = None
import parselmouth
import webrtcvad

# 한국어 처리
import jamo
import re

# 프로젝트 모듈
from config import settings
from utils import get_logger, log_execution_time, handle_errors
from tonebridge_core.models import TimeInterval, AudioSegment

logger = get_logger(__name__)

# ========== 열거형 정의 ==========


class SegmentationType(Enum):
    """분절 타입"""
    SYLLABLE = "syllable"  # 음절
    WORD = "word"  # 단어
    PHRASE = "phrase"  # 구
    SENTENCE = "sentence"  # 문장
    PHONEME = "phoneme"  # 음소


# ========== 데이터 클래스 ==========


@dataclass
class SyllableSegment:
    """음절 세그먼트"""
    index: int
    start_time: float
    end_time: float
    text: Optional[str] = None
    confidence: float = 0.0

    # 한국어 음절 구성
    initial: Optional[str] = None  # 초성
    medial: Optional[str] = None  # 중성
    final: Optional[str] = None  # 종성

    # 음향 특징
    pitch_mean: Optional[float] = None
    pitch_std: Optional[float] = None
    intensity_mean: Optional[float] = None
    energy: Optional[float] = None

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def has_final_consonant(self) -> bool:
        """종성 유무"""
        return self.final is not None and self.final != ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'index': self.index,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': self.duration,
            'text': self.text,
            'confidence': self.confidence,
            'phonemes': {
                'initial': self.initial,
                'medial': self.medial,
                'final': self.final
            },
            'features': {
                'pitch_mean': self.pitch_mean,
                'pitch_std': self.pitch_std,
                'intensity_mean': self.intensity_mean,
                'energy': self.energy
            }
        }


@dataclass
class SegmentationResult:
    """분절 결과"""
    segments: List[SyllableSegment]
    segmentation_type: SegmentationType
    total_duration: float
    sample_rate: int
    confidence: float = 0.0
    metadata: Dict[str, Any] = None

    @property
    def segment_count(self) -> int:
        return len(self.segments)

    def get_segment_at_time(self, time: float) -> Optional[SyllableSegment]:
        """특정 시간의 세그먼트 찾기"""
        for segment in self.segments:
            if segment.start_time <= time <= segment.end_time:
                return segment
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'segments': [s.to_dict() for s in self.segments],
            'segmentation_type': self.segmentation_type.value,
            'total_duration': self.total_duration,
            'sample_rate': self.sample_rate,
            'segment_count': self.segment_count,
            'confidence': self.confidence,
            'metadata': self.metadata or {}
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ========== 한국어 음소 추출기 ==========


class KoreanPhonemeExtractor:
    """한국어 음소 추출기"""

    # 한국어 자모
    INITIALS = [
        'ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ',
        'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'
    ]

    MEDIALS = [
        'ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ', 'ㅙ', 'ㅚ', 'ㅛ', 'ㅜ',
        'ㅝ', 'ㅞ', 'ㅟ', 'ㅠ', 'ㅡ', 'ㅢ', 'ㅣ'
    ]

    FINALS = [
        '', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ',
        'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'
    ]

    @staticmethod
    def decompose_syllable(syllable: str) -> Tuple[str, str, str]:
        """
        한글 음절을 자모로 분해

        Args:
            syllable: 한글 음절

        Returns:
            (초성, 중성, 종성)
        """
        if not syllable or not '가' <= syllable <= '힣':
            return '', '', ''

        # 유니코드 분해
        code = ord(syllable) - 0xAC00
        initial_index = code // (21 * 28)
        medial_index = (code % (21 * 28)) // 28
        final_index = code % 28

        initial = KoreanPhonemeExtractor.INITIALS[initial_index]
        medial = KoreanPhonemeExtractor.MEDIALS[medial_index]
        final = KoreanPhonemeExtractor.FINALS[final_index]

        return initial, medial, final

    @staticmethod
    def compose_syllable(initial: str, medial: str, final: str = '') -> str:
        """
        자모를 한글 음절로 조합

        Args:
            initial: 초성
            medial: 중성
            final: 종성

        Returns:
            한글 음절
        """
        try:
            initial_index = KoreanPhonemeExtractor.INITIALS.index(initial)
            medial_index = KoreanPhonemeExtractor.MEDIALS.index(medial)
            final_index = KoreanPhonemeExtractor.FINALS.index(
                final) if final else 0

            code = 0xAC00 + initial_index * 21 * 28 + medial_index * 28 + final_index
            return chr(code)
        except (ValueError, IndexError):
            return ''

    @staticmethod
    def extract_phonemes_from_text(
            text: str) -> List[Tuple[str, str, str, str]]:
        """
        텍스트에서 음소 추출

        Args:
            text: 한글 텍스트

        Returns:
            [(음절, 초성, 중성, 종성), ...]
        """
        phonemes = []

        for char in text:
            if '가' <= char <= '힣':
                initial, medial, final = KoreanPhonemeExtractor.decompose_syllable(
                    char)
                phonemes.append((char, initial, medial, final))

        return phonemes


# ========== 음절 경계 검출기 ==========


class SyllableBoundaryDetector:
    """음절 경계 검출기"""

    def __init__(self):
        """초기화"""
        self.vad = webrtcvad.Vad(2)  # 중간 감도
        logger.info("SyllableBoundaryDetector 초기화 완료")

    @handle_errors(context="detect_boundaries_energy")
    def detect_boundaries_energy(
            self,
            audio: np.ndarray,
            sr: int,
            min_duration: float = 0.05,
            max_duration: float = 0.8) -> List[Tuple[float, float]]:
        """
        에너지 기반 경계 검출

        Args:
            audio: 오디오 신호
            sr: 샘플레이트
            min_duration: 최소 음절 길이
            max_duration: 최대 음절 길이

        Returns:
            경계 리스트 [(start, end), ...]
        """
        # 에너지 계산
        hop_length = int(sr * 0.01)  # 10ms
        energy = librosa.feature.rms(y=audio, hop_length=hop_length)[0]

        # 동적 임계값
        threshold = np.mean(energy) * 0.3

        # 피크 검출
        peaks, properties = find_peaks(energy,
                                       height=threshold,
                                       distance=int(min_duration * sr /
                                                    hop_length),
                                       prominence=threshold * 0.5)

        # 음절 경계 생성
        boundaries = []

        for i in range(len(peaks)):
            # 시작점: 피크 이전 valley
            if i > 0:
                valley_start = np.argmin(
                    energy[peaks[i - 1]:peaks[i]]) + peaks[i - 1]
            else:
                valley_start = max(0, peaks[i] - int(0.05 * sr / hop_length))

            # 끝점: 피크 이후 valley
            if i < len(peaks) - 1:
                valley_end = np.argmin(
                    energy[peaks[i]:peaks[i + 1]]) + peaks[i]
            else:
                valley_end = min(
                    len(energy) - 1, peaks[i] + int(0.05 * sr / hop_length))

            start_time = valley_start * hop_length / sr
            end_time = valley_end * hop_length / sr

            # 길이 제약 확인
            duration = end_time - start_time
            if min_duration <= duration <= max_duration:
                boundaries.append((start_time, end_time))

        return boundaries

    @handle_errors(context="detect_boundaries_spectral")
    def detect_boundaries_spectral(self, audio: np.ndarray,
                                   sr: int) -> List[Tuple[float, float]]:
        """
        스펙트럼 변화 기반 경계 검출

        Args:
            audio: 오디오 신호
            sr: 샘플레이트

        Returns:
            경계 리스트
        """
        # MFCC 추출
        mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=13)

        # MFCC 델타 (변화율)
        mfcc_delta = librosa.feature.delta(mfcc)

        # 변화 강도 계산
        change_strength = np.sum(np.abs(mfcc_delta), axis=0)

        # 피크 검출 (변화가 큰 지점)
        peaks, _ = find_peaks(change_strength,
                              prominence=np.std(change_strength))

        # 경계 생성
        boundaries = []
        hop_length = 512

        for i in range(len(peaks) - 1):
            start_time = peaks[i] * hop_length / sr
            end_time = peaks[i + 1] * hop_length / sr
            boundaries.append((start_time, end_time))

        return boundaries

    @handle_errors(context="detect_boundaries_vad")
    def detect_boundaries_vad(
            self,
            audio: np.ndarray,
            sr: int,
            frame_duration_ms: int = 30) -> List[Tuple[float, float]]:
        """
        VAD 기반 경계 검출

        Args:
            audio: 오디오 신호
            sr: 샘플레이트
            frame_duration_ms: 프레임 길이 (ms)

        Returns:
            경계 리스트
        """
        # 16kHz로 리샘플링 (WebRTC VAD 요구사항)
        if sr != 16000:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
            sr = 16000

        # 16비트 PCM 변환
        audio_16bit = (audio * 32768).astype(np.int16)

        frame_length = int(sr * frame_duration_ms / 1000)
        boundaries = []
        in_speech = False
        start_frame = 0

        for i in range(0, len(audio_16bit), frame_length):
            frame = audio_16bit[i:i + frame_length]

            if len(frame) < frame_length:
                frame = np.pad(frame, (0, frame_length - len(frame)))

            is_speech = self.vad.is_speech(frame.tobytes(), sr)

            if is_speech and not in_speech:
                in_speech = True
                start_frame = i
            elif not is_speech and in_speech:
                in_speech = False
                start_time = start_frame / sr
                end_time = i / sr
                boundaries.append((start_time, end_time))

        # 마지막 세그먼트 처리
        if in_speech:
            boundaries.append((start_frame / sr, len(audio_16bit) / sr))

        return boundaries


# ========== 한국어 음절 분절기 ==========


class KoreanSegmenter:
    """한국어 음절 분절기"""

    def __init__(self):
        """초기화"""
        self.phoneme_extractor = KoreanPhonemeExtractor()
        self.boundary_detector = SyllableBoundaryDetector()
        logger.info("KoreanSegmenter 초기화 완료")

    @handle_errors(context="segment_audio")
    @log_execution_time
    def segment_audio(self,
                      audio_path: Union[str, Path],
                      text: Optional[str] = None,
                      method: str = "hybrid") -> List[SyllableSegment]:
        """
        오디오를 음절 단위로 분절

        Args:
            audio_path: 오디오 파일 경로
            text: 텍스트 (있으면 정렬에 사용)
            method: 분절 방법 ("energy", "spectral", "vad", "hybrid")

        Returns:
            음절 세그먼트 리스트
        """
        audio_path = Path(audio_path)

        # 오디오 로드
        audio, sr = librosa.load(str(audio_path), sr=None)

        # 경계 검출
        if method == "energy":
            boundaries = self.boundary_detector.detect_boundaries_energy(
                audio, sr)
        elif method == "spectral":
            boundaries = self.boundary_detector.detect_boundaries_spectral(
                audio, sr)
        elif method == "vad":
            boundaries = self.boundary_detector.detect_boundaries_vad(
                audio, sr)
        else:  # hybrid
            boundaries = self._detect_boundaries_hybrid(audio, sr)

        # 세그먼트 생성
        segments = []
        for i, (start, end) in enumerate(boundaries):
            segment = SyllableSegment(index=i, start_time=start, end_time=end)

            # 음향 특징 추출
            self._extract_acoustic_features(segment, audio, sr)

            segments.append(segment)

        # 텍스트가 있으면 정렬
        if text:
            segments = self._align_with_text(segments, text)

        logger.info(f"음절 분절 완료: {len(segments)}개 세그먼트")
        return segments

    def _detect_boundaries_hybrid(self, audio: np.ndarray,
                                  sr: int) -> List[Tuple[float, float]]:
        """하이브리드 경계 검출"""
        # 여러 방법으로 경계 검출
        energy_boundaries = self.boundary_detector.detect_boundaries_energy(
            audio, sr)
        spectral_boundaries = self.boundary_detector.detect_boundaries_spectral(
            audio, sr)

        # 경계 통합 (투표 방식)
        all_boundaries = energy_boundaries + spectral_boundaries

        # 중복 제거 및 정렬
        merged_boundaries = self._merge_boundaries(all_boundaries)

        return merged_boundaries

    def _merge_boundaries(
            self,
            boundaries: List[Tuple[float, float]],
            threshold: float = 0.05) -> List[Tuple[float, float]]:
        """경계 병합"""
        if not boundaries:
            return []

        # 정렬
        boundaries = sorted(boundaries, key=lambda x: x[0])

        # 병합
        merged = [boundaries[0]]

        for start, end in boundaries[1:]:
            last_start, last_end = merged[-1]

            # 겹치거나 가까운 경우 병합
            if start - last_end < threshold:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))

        return merged

    def _extract_acoustic_features(self, segment: SyllableSegment,
                                   audio: np.ndarray, sr: int):
        """음향 특징 추출"""
        # 세그먼트 오디오 추출
        start_sample = int(segment.start_time * sr)
        end_sample = int(segment.end_time * sr)
        segment_audio = audio[start_sample:end_sample]

        if len(segment_audio) == 0:
            return

        # 에너지
        segment.energy = float(np.sqrt(np.mean(segment_audio**2)))

        # 피치 (Parselmouth 사용)
        try:
            import parselmouth
            sound = parselmouth.Sound(segment_audio, sr)
            pitch = sound.to_pitch()

            pitch_values = []
            for t in pitch.xs():
                value = pitch.get_value_at_time(t)
                if value and not np.isnan(value):
                    pitch_values.append(value)

            if pitch_values:
                segment.pitch_mean = float(np.mean(pitch_values))
                segment.pitch_std = float(np.std(pitch_values))
        except:
            pass

        # 강도
        try:
            segment.intensity_mean = float(
                20 * np.log10(np.mean(np.abs(segment_audio)) + 1e-10))
        except:
            pass

    def _align_with_text(self, segments: List[SyllableSegment],
                         text: str) -> List[SyllableSegment]:
        """텍스트와 정렬"""
        # 텍스트에서 음절 추출
        syllables = []
        for char in text:
            if '가' <= char <= '힣':
                syllables.append(char)

        # 세그먼트 수와 음절 수 맞추기
        if len(segments) == len(syllables):
            # 1:1 매핑
            for segment, syllable in zip(segments, syllables):
                segment.text = syllable

                # 음소 분해
                initial, medial, final = self.phoneme_extractor.decompose_syllable(
                    syllable)
                segment.initial = initial
                segment.medial = medial
                segment.final = final

        elif len(segments) > len(syllables):
            # 세그먼트가 더 많은 경우: 병합
            ratio = len(segments) / len(syllables)

            for i, syllable in enumerate(syllables):
                start_idx = int(i * ratio)
                end_idx = int((i + 1) * ratio)

                if start_idx < len(segments):
                    segments[start_idx].text = syllable

                    # 음소 분해
                    initial, medial, final = self.phoneme_extractor.decompose_syllable(
                        syllable)
                    segments[start_idx].initial = initial
                    segments[start_idx].medial = medial
                    segments[start_idx].final = final

        else:
            # 음절이 더 많은 경우: 분할
            ratio = len(syllables) / len(segments)

            for i, segment in enumerate(segments):
                start_idx = int(i * ratio)
                end_idx = int((i + 1) * ratio)

                # 해당 구간의 음절들 결합
                segment_text = ''.join(syllables[start_idx:end_idx])
                segment.text = segment_text

                # 첫 음절의 음소만 저장
                if start_idx < len(syllables):
                    initial, medial, final = self.phoneme_extractor.decompose_syllable(
                        syllables[start_idx])
                    segment.initial = initial
                    segment.medial = medial
                    segment.final = final

        return segments

    @handle_errors(context="segment_with_stt")
    @log_execution_time
    def segment_with_stt(self, audio_path: Union[str, Path],
                         stt_result: Dict[str, Any]) -> SegmentationResult:
        """
        STT 결과를 활용한 정밀 분절

        Args:
            audio_path: 오디오 파일 경로
            stt_result: STT 결과 (단어 타임스탬프 포함)

        Returns:
            분절 결과
        """
        audio_path = Path(audio_path)

        # 오디오 정보
        audio, sr = librosa.load(str(audio_path), sr=None)
        duration = len(audio) / sr

        segments = []

        # STT 세그먼트에서 음절 추출
        if 'segments' in stt_result:
            for stt_segment in stt_result['segments']:
                text = stt_segment.get('text', '')
                start_time = stt_segment.get('start', 0.0)
                end_time = stt_segment.get('end', 0.0)

                # 텍스트에서 음절 추출
                syllables = []
                for char in text:
                    if '가' <= char <= '힣':
                        syllables.append(char)

                if not syllables:
                    continue

                # 음절별 시간 균등 분할
                syllable_duration = (end_time - start_time) / len(syllables)

                for i, syllable in enumerate(syllables):
                    syllable_start = start_time + i * syllable_duration
                    syllable_end = start_time + (i + 1) * syllable_duration

                    # 음소 분해
                    initial, medial, final = self.phoneme_extractor.decompose_syllable(
                        syllable)

                    segment = SyllableSegment(index=len(segments),
                                              start_time=syllable_start,
                                              end_time=syllable_end,
                                              text=syllable,
                                              confidence=stt_segment.get(
                                                  'confidence', 0.0),
                                              initial=initial,
                                              medial=medial,
                                              final=final)

                    # 음향 특징 추출
                    self._extract_acoustic_features(segment, audio, sr)

                    segments.append(segment)

        # 결과 생성
        result = SegmentationResult(
            segments=segments,
            segmentation_type=SegmentationType.SYLLABLE,
            total_duration=duration,
            sample_rate=sr,
            confidence=np.mean([s.confidence
                                for s in segments]) if segments else 0.0,
            metadata={'method': 'stt_based'})

        logger.info(f"STT 기반 분절 완료: {len(segments)}개 음절")
        return result

    @handle_errors(context="refine_segmentation")
    def refine_segmentation(
            self, segments: List[SyllableSegment],
            audio_path: Union[str, Path]) -> List[SyllableSegment]:
        """
        분절 결과 정제

        Args:
            segments: 초기 세그먼트
            audio_path: 오디오 파일 경로

        Returns:
            정제된 세그먼트
        """
        # 오디오 로드
        audio, sr = librosa.load(str(audio_path), sr=None)

        refined_segments = []

        for segment in segments:
            # 세그먼트 오디오 추출
            start_sample = int(segment.start_time * sr)
            end_sample = int(segment.end_time * sr)
            segment_audio = audio[start_sample:end_sample]

            if len(segment_audio) < sr * 0.03:  # 30ms 미만은 제거
                continue

            # 정확한 경계 찾기 (zero-crossing)
            # 시작 부분
            zc_start = librosa.zero_crossings(segment_audio[:int(sr * 0.01)])
            if np.any(zc_start):
                first_zc = np.where(zc_start)[0][0]
                segment.start_time += first_zc / sr

            # 끝 부분
            zc_end = librosa.zero_crossings(segment_audio[-int(sr * 0.01):])
            if np.any(zc_end):
                last_zc = np.where(zc_end)[0][-1]
                segment.end_time -= (int(sr * 0.01) - last_zc) / sr

            refined_segments.append(segment)

        return refined_segments


# 메인 실행 코드
if __name__ == "__main__":
    from config import settings

    # 테스트
    segmenter = KoreanSegmenter()

    # 참조 파일 테스트
    if settings.REFERENCE_FILES_PATH.exists():
        test_files = list(settings.REFERENCE_FILES_PATH.glob("*.wav"))[:1]

        for test_file in test_files:
            logger.info(f"음절 분절 테스트: {test_file}")

            # 기본 분절
            segments = segmenter.segment_audio(test_file, method="hybrid")

            logger.info(f"분절 결과: {len(segments)}개 음절")

            # 처음 5개 세그먼트 정보 출력
            for i, seg in enumerate(segments[:5]):
                logger.info(
                    f"  음절 {i}: {seg.start_time:.3f}-{seg.end_time:.3f}s "
                    f"(길이: {seg.duration:.3f}s, 에너지: {seg.energy:.3f})")
