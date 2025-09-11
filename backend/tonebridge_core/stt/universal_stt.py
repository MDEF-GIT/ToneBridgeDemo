"""
통합 STT 시스템
다양한 STT 엔진을 통합 관리하는 유니버설 시스템
"""

import warnings

warnings.filterwarnings('ignore')

import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib

# 오디오 처리
import librosa
import soundfile as sf

# 텍스트 처리
from difflib import SequenceMatcher
# Optional Levenshtein import (Pure Nix compatibility)
try:
    import Levenshtein
    HAS_LEVENSHTEIN = True
except ImportError:
    Levenshtein = None
    HAS_LEVENSHTEIN = False
import re

# 프로젝트 모듈
from config import settings
from utils import (FileHandler, file_handler, get_logger, log_execution_time,
                   handle_errors, STTError, ErrorRecovery)

# Core STT 모듈
from core.advanced_stt_processor import WhisperProcessor
from core.multi_engine_stt import (GoogleSTTEngine, AzureSTTEngine,
                                   NaverSTTEngine, STTEngine as CoreSTTEngine)

logger = get_logger(__name__)

# ========== 열거형 정의 ==========


class STTEngine(Enum):
    """STT 엔진 타입"""
    WHISPER = "whisper"
    GOOGLE = "google"
    AZURE = "azure"
    NAVER = "naver"
    KAKAO = "kakao"
    CUSTOM = "custom"


class ConsensusMethod(Enum):
    """합의 방법"""
    MAJORITY_VOTE = "majority_vote"  # 다수결
    CONFIDENCE_WEIGHTED = "confidence_weighted"  # 신뢰도 가중
    LONGEST_COMMON = "longest_common"  # 최장 공통 부분
    ENSEMBLE = "ensemble"  # 앙상블


# ========== 데이터 클래스 ==========


@dataclass
class TranscriptionSegment:
    """전사 세그먼트"""
    id: int
    start: float
    end: float
    text: str
    confidence: float = 0.0
    words: Optional[List[Dict[str, Any]]] = None
    speaker: Optional[str] = None

    @property
    def duration(self) -> float:
        return self.end - self.start

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'start': self.start,
            'end': self.end,
            'duration': self.duration,
            'text': self.text,
            'confidence': self.confidence,
            'words': self.words,
            'speaker': self.speaker
        }


@dataclass
class STTResult:
    """STT 결과"""
    text: str
    segments: List[TranscriptionSegment]
    language: str
    engine: str
    confidence: float
    processing_time: float
    word_count: int = 0
    char_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """통계 계산"""
        self.word_count = len(self.text.split())
        self.char_count = len(self.text.replace(' ', ''))

    @property
    def average_confidence(self) -> float:
        """평균 신뢰도"""
        if not self.segments:
            return self.confidence
        return np.mean([s.confidence for s in self.segments])

    def to_dict(self) -> Dict[str, Any]:
        return {
            'text': self.text,
            'segments': [s.to_dict() for s in self.segments],
            'language': self.language,
            'engine': self.engine,
            'confidence': self.confidence,
            'average_confidence': self.average_confidence,
            'processing_time': self.processing_time,
            'statistics': {
                'word_count': self.word_count,
                'char_count': self.char_count,
                'segment_count': len(self.segments)
            },
            'metadata': self.metadata
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_srt(self) -> str:
        """SRT 자막 형식 변환"""
        srt_lines = []
        for i, segment in enumerate(self.segments, 1):
            start = self._format_srt_time(segment.start)
            end = self._format_srt_time(segment.end)

            srt_lines.append(f"{i}")
            srt_lines.append(f"{start} --> {end}")
            srt_lines.append(segment.text)
            srt_lines.append("")

        return "\n".join(srt_lines)

    def to_vtt(self) -> str:
        """WebVTT 자막 형식 변환"""
        vtt_lines = ["WEBVTT", ""]

        for segment in self.segments:
            start = self._format_vtt_time(segment.start)
            end = self._format_vtt_time(segment.end)

            vtt_lines.append(f"{start} --> {end}")
            vtt_lines.append(segment.text)
            vtt_lines.append("")

        return "\n".join(vtt_lines)

    def _format_srt_time(self, seconds: float) -> str:
        """SRT 시간 형식"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace('.', ',')

    def _format_vtt_time(self, seconds: float) -> str:
        """WebVTT 시간 형식"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


@dataclass
class STTConfig:
    """STT 설정"""
    # 엔진 설정
    primary_engine: STTEngine = STTEngine.WHISPER
    fallback_engines: List[STTEngine] = field(
        default_factory=lambda: [STTEngine.GOOGLE])
    enable_multi_engine: bool = False
    consensus_method: ConsensusMethod = ConsensusMethod.CONFIDENCE_WEIGHTED

    # 언어 설정
    language: str = "ko"
    auto_detect_language: bool = False

    # 처리 설정
    enable_vad: bool = True
    enable_punctuation: bool = True
    enable_diarization: bool = False  # 화자 분리
    enable_noise_reduction: bool = True

    # 품질 설정
    min_confidence: float = 0.5
    max_alternatives: int = 3

    # 성능 설정
    use_gpu: bool = False
    batch_size: int = 1
    num_workers: int = 1
    timeout: int = 60

    # 캐싱 설정
    enable_cache: bool = True
    cache_ttl: int = 3600

    def to_dict(self) -> Dict[str, Any]:
        return {
            'engines': {
                'primary': self.primary_engine.value,
                'fallback': [e.value for e in self.fallback_engines],
                'multi_engine': self.enable_multi_engine,
                'consensus_method': self.consensus_method.value
            },
            'language': {
                'code': self.language,
                'auto_detect': self.auto_detect_language
            },
            'processing': {
                'vad': self.enable_vad,
                'punctuation': self.enable_punctuation,
                'diarization': self.enable_diarization,
                'noise_reduction': self.enable_noise_reduction
            },
            'quality': {
                'min_confidence': self.min_confidence,
                'max_alternatives': self.max_alternatives
            },
            'performance': {
                'use_gpu': self.use_gpu,
                'batch_size': self.batch_size,
                'num_workers': self.num_workers,
                'timeout': self.timeout
            },
            'cache': {
                'enabled': self.enable_cache,
                'ttl': self.cache_ttl
            }
        }


# ========== 엔진 관리자 ==========


class EngineManager:
    """STT 엔진 관리자"""

    def __init__(self):
        """초기화"""
        self.engines = {}
        self._initialize_engines()
        logger.info(f"EngineManager 초기화: {list(self.engines.keys())} 엔진 활성화")

    def _initialize_engines(self):
        """엔진 초기화"""
        # Whisper
        try:
            self.engines[STTEngine.WHISPER] = WhisperProcessor(
                model_size=settings.WHISPER_MODEL)
            logger.info("Whisper 엔진 초기화 성공")
        except Exception as e:
            logger.warning(f"Whisper 엔진 초기화 실패: {e}")

        # Google
        if settings.ENABLE_GOOGLE_STT:
            try:
                self.engines[STTEngine.GOOGLE] = GoogleSTTEngine()
                logger.info("Google 엔진 초기화 성공")
            except Exception as e:
                logger.warning(f"Google 엔진 초기화 실패: {e}")

        # Azure
        if settings.ENABLE_AZURE_STT:
            try:
                self.engines[STTEngine.AZURE] = AzureSTTEngine()
                logger.info("Azure 엔진 초기화 성공")
            except Exception as e:
                logger.warning(f"Azure 엔진 초기화 실패: {e}")

        # Naver
        if settings.ENABLE_NAVER_STT:
            try:
                self.engines[STTEngine.NAVER] = NaverSTTEngine()
                logger.info("Naver 엔진 초기화 성공")
            except Exception as e:
                logger.warning(f"Naver 엔진 초기화 실패: {e}")

    def get_engine(self, engine_type: STTEngine):
        """엔진 가져오기"""
        return self.engines.get(engine_type)

    def is_available(self, engine_type: STTEngine) -> bool:
        """엔진 사용 가능 여부"""
        return engine_type in self.engines

    def get_available_engines(self) -> List[STTEngine]:
        """사용 가능한 엔진 목록"""
        return list(self.engines.keys())


# ========== 합의 빌더 ==========


class ConsensusBuilder:
    """전사 결과 합의 빌더"""

    @staticmethod
    def build_consensus(
        results: List[STTResult],
        method: ConsensusMethod = ConsensusMethod.CONFIDENCE_WEIGHTED
    ) -> STTResult:
        """
        여러 STT 결과에서 합의 도출

        Args:
            results: STT 결과 리스트
            method: 합의 방법

        Returns:
            합의된 STT 결과
        """
        if not results:
            raise ValueError("결과가 없습니다")

        if len(results) == 1:
            return results[0]

        if method == ConsensusMethod.MAJORITY_VOTE:
            return ConsensusBuilder._majority_vote(results)
        elif method == ConsensusMethod.CONFIDENCE_WEIGHTED:
            return ConsensusBuilder._confidence_weighted(results)
        elif method == ConsensusMethod.LONGEST_COMMON:
            return ConsensusBuilder._longest_common(results)
        else:  # ENSEMBLE
            return ConsensusBuilder._ensemble(results)

    @staticmethod
    def _majority_vote(results: List[STTResult]) -> STTResult:
        """다수결 방식"""
        from collections import Counter

        # 텍스트 투표
        texts = [r.text for r in results]
        text_counts = Counter(texts)
        consensus_text = text_counts.most_common(1)[0][0]

        # 해당 텍스트를 가진 결과 중 최고 신뢰도 선택
        matching_results = [r for r in results if r.text == consensus_text]
        best_result = max(matching_results, key=lambda x: x.confidence)

        # 평균 신뢰도 계산
        avg_confidence = np.mean([r.confidence for r in results])
        best_result.confidence = avg_confidence

        return best_result

    @staticmethod
    def _confidence_weighted(results: List[STTResult]) -> STTResult:
        """신뢰도 가중 방식"""
        # 신뢰도가 가장 높은 결과 선택
        best_result = max(results, key=lambda x: x.confidence)

        # 단어별 신뢰도 가중 투표
        if all(r.segments for r in results):
            # 세그먼트 정렬 및 병합
            merged_segments = ConsensusBuilder._merge_segments(results)
            best_result.segments = merged_segments

            # 텍스트 재구성
            best_result.text = ' '.join(s.text for s in merged_segments)

        return best_result

    @staticmethod
    def _longest_common(results: List[STTResult]) -> STTResult:
        """최장 공통 부분 방식"""
        # 모든 텍스트 쌍의 최장 공통 부분 찾기
        texts = [r.text for r in results]

        # 가장 긴 공통 부분 찾기
        common_text = texts[0]
        for text in texts[1:]:
            matcher = SequenceMatcher(None, common_text, text)
            match = matcher.find_longest_match(0, len(common_text), 0,
                                               len(text))
            common_text = common_text[match.a:match.a + match.size]

        # 새 결과 생성
        consensus_result = results[0]  # 기본 구조 복사
        consensus_result.text = common_text
        consensus_result.confidence = np.mean([r.confidence for r in results])

        return consensus_result

    @staticmethod
    def _ensemble(results: List[STTResult]) -> STTResult:
        """앙상블 방식 (여러 방법 조합)"""
        # 각 방법으로 합의 구성
        majority = ConsensusBuilder._majority_vote(results)
        weighted = ConsensusBuilder._confidence_weighted(results)

        # 두 결과가 같으면 그대로 반환
        if majority.text == weighted.text:
            return weighted

        # 다르면 신뢰도가 높은 것 선택
        if weighted.confidence > majority.confidence:
            return weighted
        else:
            return majority

    @staticmethod
    def _merge_segments(
            results: List[STTResult]) -> List[TranscriptionSegment]:
        """세그먼트 병합"""
        all_segments = []
        for result in results:
            for segment in result.segments:
                all_segments.append((segment, result.confidence))

        # 시간순 정렬
        all_segments.sort(key=lambda x: x[0].start)

        # 중복 제거 및 병합
        merged = []
        for segment, conf in all_segments:
            if not merged or segment.start > merged[-1].end + 0.1:
                # 새 세그먼트
                merged.append(segment)
            else:
                # 기존 세그먼트와 병합
                if conf > merged[-1].confidence:
                    merged[-1] = segment

        return merged


# ========== 통합 STT 시스템 ==========


class UniversalSTT:
    """유니버설 STT 시스템"""

    def __init__(self, config: Optional[STTConfig] = None):
        """
        초기화

        Args:
            config: STT 설정
        """
        self.config = config or STTConfig()
        self.engine_manager = EngineManager()
        self.consensus_builder = ConsensusBuilder()
        self.file_handler = file_handler

        # 캐시
        self.cache = {} if self.config.enable_cache else None

        logger.info("UniversalSTT 초기화 완료")

    @handle_errors(context="transcribe")
    @log_execution_time
    def transcribe(self,
                   audio_path: Union[str, Path],
                   language: Optional[str] = None,
                   engine: Optional[STTEngine] = None) -> STTResult:
        """
        음성 인식

        Args:
            audio_path: 오디오 파일 경로
            language: 언어 코드
            engine: 사용할 엔진

        Returns:
            STT 결과
        """
        audio_path = Path(audio_path)
        language = language or self.config.language
        engine = engine or self.config.primary_engine

        # 캐시 확인
        if self.cache is not None:
            cache_key = self._get_cache_key(audio_path, language, engine)
            if cache_key in self.cache:
                logger.debug("캐시된 결과 사용")
                return self.cache[cache_key]

        # 전처리
        if self.config.enable_noise_reduction:
            audio_path = self._preprocess_audio(audio_path)

        # STT 실행
        if self.config.enable_multi_engine:
            result = self._transcribe_multi_engine(audio_path, language)
        else:
            result = self._transcribe_single_engine(audio_path, language,
                                                    engine)

        # 후처리
        if self.config.enable_punctuation:
            result = self._add_punctuation(result)

        # 캐시 저장
        if self.cache is not None:
            self.cache[cache_key] = result

        return result

    def _get_cache_key(self, audio_path: Path, language: str,
                       engine: STTEngine) -> str:
        """캐시 키 생성"""
        file_hash = file_handler.get_file_hash(audio_path, 'md5')
        return f"{file_hash}_{language}_{engine.value}"

    def _preprocess_audio(self, audio_path: Path) -> Path:
        """오디오 전처리"""
        from core.audio_enhancement import NoiseReducer

        noise_reducer = NoiseReducer()
        temp_path = self.file_handler.create_temp_file(suffix=".wav")

        processed_path = noise_reducer.reduce_noise(audio_path, temp_path)

        return processed_path

    def _transcribe_single_engine(self, audio_path: Path, language: str,
                                  engine_type: STTEngine) -> STTResult:
        """단일 엔진 전사"""
        engine = self.engine_manager.get_engine(engine_type)

        if not engine:
            # 폴백 엔진 시도
            for fallback in self.config.fallback_engines:
                engine = self.engine_manager.get_engine(fallback)
                if engine:
                    engine_type = fallback
                    break

            if not engine:
                raise STTError(engine_type.value, "사용 가능한 엔진이 없습니다")

        start_time = time.time()

        # 엔진별 전사 실행
        if engine_type == STTEngine.WHISPER:
            result = self._transcribe_whisper(engine, audio_path, language)
        elif engine_type == STTEngine.GOOGLE:
            result = self._transcribe_google(engine, audio_path, language)
        elif engine_type == STTEngine.AZURE:
            result = self._transcribe_azure(engine, audio_path, language)
        elif engine_type == STTEngine.NAVER:
            result = self._transcribe_naver(engine, audio_path, language)
        else:
            raise STTError(engine_type.value, "지원하지 않는 엔진")

        result.processing_time = time.time() - start_time

        return result

    def _transcribe_multi_engine(self, audio_path: Path,
                                 language: str) -> STTResult:
        """다중 엔진 전사"""
        results = []
        engines = [self.config.primary_engine] + self.config.fallback_engines

        # 병렬 처리
        with ThreadPoolExecutor(max_workers=len(engines)) as executor:
            futures = {}

            for engine_type in engines:
                if self.engine_manager.is_available(engine_type):
                    future = executor.submit(self._transcribe_single_engine,
                                             audio_path, language, engine_type)
                    futures[future] = engine_type

            for future in as_completed(futures):
                try:
                    result = future.result(timeout=self.config.timeout)
                    results.append(result)
                except Exception as e:
                    logger.warning(f"{futures[future].value} 전사 실패: {e}")

        if not results:
            raise STTError("multi", "모든 엔진에서 전사 실패")

        # 합의 구성
        consensus = self.consensus_builder.build_consensus(
            results, self.config.consensus_method)

        return consensus

    def _transcribe_whisper(self, engine: WhisperProcessor, audio_path: Path,
                            language: str) -> STTResult:
        """Whisper 전사"""
        # Whisper 전사
        transcription = engine.transcribe(audio_path,
                                          language=language,
                                          task="transcribe")

        # 세그먼트 변환
        segments = []
        for i, seg in enumerate(transcription.segments):
            segments.append(
                TranscriptionSegment(id=i,
                                     start=seg.start,
                                     end=seg.end,
                                     text=seg.text,
                                     confidence=seg.confidence,
                                     words=seg.words))

        return STTResult(text=transcription.text,
                         segments=segments,
                         language=transcription.language,
                         engine=STTEngine.WHISPER.value,
                         confidence=transcription.confidence,
                         processing_time=transcription.processing_time)

    def _transcribe_google(self, engine: GoogleSTTEngine, audio_path: Path,
                           language: str) -> STTResult:
        """Google STT 전사"""
        # 언어 코드 변환
        if language == "ko":
            language_code = "ko-KR"
        elif language == "en":
            language_code = "en-US"
        else:
            language_code = language

        # Google STT 실행
        result = engine.transcribe(audio_path, language_code)

        # 세그먼트 생성
        segments = []
        if result.segments:
            for i, word in enumerate(result.segments):
                segments.append(
                    TranscriptionSegment(id=i,
                                         start=word['start_time'],
                                         end=word['end_time'],
                                         text=word['word'],
                                         confidence=result.confidence))

        return STTResult(text=result.text,
                         segments=segments,
                         language=language,
                         engine=STTEngine.GOOGLE.value,
                         confidence=result.confidence,
                         processing_time=result.processing_time)

    def _transcribe_azure(self, engine: AzureSTTEngine, audio_path: Path,
                          language: str) -> STTResult:
        """Azure STT 전사"""
        # 언어 코드 변환
        if language == "ko":
            language_code = "ko-KR"
        elif language == "en":
            language_code = "en-US"
        else:
            language_code = language

        # Azure STT 실행
        result = engine.transcribe(audio_path, language_code)

        return STTResult(
            text=result.text,
            segments=[],  # Azure는 기본적으로 세그먼트 미제공
            language=language,
            engine=STTEngine.AZURE.value,
            confidence=result.confidence,
            processing_time=result.processing_time)

    def _transcribe_naver(self, engine: NaverSTTEngine, audio_path: Path,
                          language: str) -> STTResult:
        """Naver STT 전사"""
        # 언어 코드 변환
        language_map = {"ko": "Kor", "en": "Eng", "ja": "Jpn", "zh": "Chn"}
        naver_lang = language_map.get(language, "Kor")

        # Naver STT 실행
        result = engine.transcribe(audio_path, naver_lang)

        return STTResult(
            text=result.text,
            segments=[],  # Naver는 세그먼트 미제공
            language=language,
            engine=STTEngine.NAVER.value,
            confidence=result.confidence,
            processing_time=result.processing_time)

    def _add_punctuation(self, result: STTResult) -> STTResult:
        """구두점 추가"""
        # 간단한 규칙 기반 구두점 추가
        text = result.text

        # 문장 끝 처리
        text = re.sub(r'([가-힣a-zA-Z0-9]) ([가-힣A-Z])', r'\1. \2', text)

        # 의문문 처리
        question_words = ['뭐', '어디', '언제', '누구', '왜', '어떻게', '얼마']
        for word in question_words:
            if word in text and not text.endswith('?'):
                text = text + '?'
                break

        # 마지막 문장부호 추가
        if text and text[-1] not in '.!?':
            text = text + '.'

        result.text = text

        # 세그먼트 텍스트도 업데이트
        for segment in result.segments:
            if segment.text and segment.text[-1] not in '.!?':
                segment.text = segment.text + '.'

        return result

    @handle_errors(context="batch_transcribe")
    @log_execution_time
    def batch_transcribe(self,
                         audio_files: List[Union[str, Path]],
                         language: Optional[str] = None,
                         parallel: bool = True) -> List[STTResult]:
        """
        배치 전사

        Args:
            audio_files: 오디오 파일 리스트
            language: 언어 코드
            parallel: 병렬 처리 여부

        Returns:
            STT 결과 리스트
        """
        results = []

        if parallel:
            with ThreadPoolExecutor(
                    max_workers=self.config.num_workers) as executor:
                futures = []

                for audio_file in audio_files:
                    future = executor.submit(self.transcribe, audio_file,
                                             language)
                    futures.append(future)

                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=self.config.timeout)
                        results.append(result)
                    except Exception as e:
                        logger.error(f"배치 전사 실패: {e}")
        else:
            for audio_file in audio_files:
                try:
                    result = self.transcribe(audio_file, language)
                    results.append(result)
                except Exception as e:
                    logger.error(f"파일 전사 실패 ({audio_file}): {e}")

        logger.info(f"배치 전사 완료: {len(results)}/{len(audio_files)} 성공")

        return results


# 메인 실행 코드
if __name__ == "__main__":
    from config import settings

    # 테스트
    config = STTConfig(primary_engine=STTEngine.WHISPER,
                       enable_multi_engine=False,
                       language="ko")

    stt = UniversalSTT(config)

    # 참조 파일 테스트
    if settings.REFERENCE_FILES_PATH.exists():
        test_files = list(settings.REFERENCE_FILES_PATH.glob("*.wav"))[:1]

        for test_file in test_files:
            logger.info(f"STT 테스트: {test_file}")

            result = stt.transcribe(test_file)

            logger.info(f"전사 결과: {result.text}")
            logger.info(f"신뢰도: {result.confidence:.2f}")
            logger.info(f"처리 시간: {result.processing_time:.2f}초")
            logger.info(f"세그먼트 수: {len(result.segments)}")
