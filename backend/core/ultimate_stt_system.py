"""
통합 STT 시스템
모든 STT 기능을 통합한 최종 시스템
"""

import warnings

warnings.filterwarnings('ignore')

import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
import numpy as np
from dataclasses import dataclass, field
from datetime import datetime
import hashlib

# 오디오 처리
import librosa
import soundfile as sf
from pydub import AudioSegment

# 텍스트 처리
from difflib import SequenceMatcher
import re

# 프로젝트 모듈
from config import settings
from utils import (FileHandler, file_handler, get_logger, log_execution_time,
                   handle_errors, STTError, PerformanceLogger, AuditLogger)

# Core 모듈
from core.audio_normalization import AudioNormalizer
from core.audio_enhancement import AudioQualityEnhancer
from core.korean_audio_optimizer import KoreanAudioOptimizer
from core.advanced_stt_processor import AdvancedSTTProcessor, TranscriptionResult
from core.multi_engine_stt import MultiEngineSTT, MultiSTTResult

logger = get_logger(__name__)
performance_logger = PerformanceLogger()
audit_logger = AuditLogger()

# ========== 데이터 클래스 ==========


@dataclass
class STTConfig:
    """STT 시스템 설정"""
    # 전처리 설정
    enable_preprocessing: bool = True
    remove_silence: bool = True
    normalize_audio: bool = True
    enhance_audio: bool = True

    # STT 엔진 설정
    primary_engine: str = "whisper"
    fallback_engines: List[str] = field(
        default_factory=lambda: ["google", "azure"])
    enable_multi_engine: bool = False
    consensus_threshold: float = 0.7

    # 언어 설정
    language: str = "ko"
    enable_language_detection: bool = False

    # 후처리 설정
    enable_postprocessing: bool = True
    correct_spelling: bool = True
    extract_keywords: bool = True

    # 성능 설정
    enable_caching: bool = True
    max_retries: int = 3
    timeout: int = 60

    # 출력 설정
    save_intermediate: bool = False
    output_format: str = "json"  # json, text, srt, vtt

    def to_dict(self) -> Dict[str, Any]:
        return {
            'preprocessing': {
                'enabled': self.enable_preprocessing,
                'remove_silence': self.remove_silence,
                'normalize_audio': self.normalize_audio,
                'enhance_audio': self.enhance_audio
            },
            'engines': {
                'primary': self.primary_engine,
                'fallback': self.fallback_engines,
                'multi_engine': self.enable_multi_engine,
                'consensus_threshold': self.consensus_threshold
            },
            'language': {
                'code': self.language,
                'auto_detect': self.enable_language_detection
            },
            'postprocessing': {
                'enabled': self.enable_postprocessing,
                'spell_correction': self.correct_spelling,
                'keyword_extraction': self.extract_keywords
            },
            'performance': {
                'caching': self.enable_caching,
                'max_retries': self.max_retries,
                'timeout': self.timeout
            },
            'output': {
                'save_intermediate': self.save_intermediate,
                'format': self.output_format
            }
        }


@dataclass
class STTSession:
    """STT 세션 정보"""
    session_id: str
    start_time: datetime
    config: STTConfig
    audio_file: str
    status: str = "initialized"

    # 처리 단계별 결과
    preprocessing_result: Optional[Dict] = None
    transcription_result: Optional[Dict] = None
    postprocessing_result: Optional[Dict] = None

    # 메트릭
    total_duration: float = 0.0
    processing_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'start_time': self.start_time.isoformat(),
            'config': self.config.to_dict(),
            'audio_file': self.audio_file,
            'status': self.status,
            'results': {
                'preprocessing': self.preprocessing_result,
                'transcription': self.transcription_result,
                'postprocessing': self.postprocessing_result
            },
            'metrics': {
                'total_duration': self.total_duration,
                'processing_time': self.processing_time
            }
        }


@dataclass
class UltimateSTTResult:
    """최종 STT 결과"""
    session: STTSession
    final_text: str
    confidence: float
    segments: List[Dict]
    keywords: Optional[List[str]] = None
    language: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'session': self.session.to_dict(),
            'final_text': self.final_text,
            'confidence': self.confidence,
            'segments': self.segments,
            'keywords': self.keywords,
            'language': self.language,
            'metadata': self.metadata
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_srt(self) -> str:
        """SRT 자막 형식으로 변환"""
        srt_lines = []
        for i, segment in enumerate(self.segments, 1):
            start = self._format_srt_time(segment['start'])
            end = self._format_srt_time(segment['end'])
            text = segment['text']

            srt_lines.append(f"{i}")
            srt_lines.append(f"{start} --> {end}")
            srt_lines.append(text)
            srt_lines.append("")

        return "\n".join(srt_lines)

    def to_vtt(self) -> str:
        """WebVTT 자막 형식으로 변환"""
        vtt_lines = ["WEBVTT", ""]

        for segment in self.segments:
            start = self._format_vtt_time(segment['start'])
            end = self._format_vtt_time(segment['end'])
            text = segment['text']

            vtt_lines.append(f"{start} --> {end}")
            vtt_lines.append(text)
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


# ========== 캐시 시스템 ==========


class STTCache:
    """STT 결과 캐시"""

    def __init__(self, cache_dir: Optional[Path] = None):
        """초기화"""
        self.cache_dir = cache_dir or settings.CACHE_DIR / "stt"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"STTCache 초기화: {self.cache_dir}")

    def get_cache_key(self, audio_path: Path, config: STTConfig) -> str:
        """캐시 키 생성"""
        # 파일 해시
        file_hash = file_handler.get_file_hash(audio_path, 'md5')

        # 설정 해시
        config_str = json.dumps(config.to_dict(), sort_keys=True)
        config_hash = hashlib.md5(config_str.encode()).hexdigest()

        return f"{file_hash}_{config_hash}"

    def get(self, cache_key: str) -> Optional[Dict]:
        """캐시에서 결과 가져오기"""
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 캐시 유효성 검사 (TTL)
                cached_time = datetime.fromisoformat(data.get('cached_at', ''))
                age = (datetime.now() - cached_time).total_seconds()

                if age < settings.CACHE_TTL:
                    logger.debug(f"캐시 히트: {cache_key}")
                    return data
                else:
                    logger.debug(f"캐시 만료: {cache_key}")
                    cache_file.unlink()

            except Exception as e:
                logger.warning(f"캐시 읽기 실패: {e}")

        return None

    def set(self, cache_key: str, data: Dict):
        """캐시에 결과 저장"""
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            data['cached_at'] = datetime.now().isoformat()

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug(f"캐시 저장: {cache_key}")

        except Exception as e:
            logger.warning(f"캐시 저장 실패: {e}")

    def clear(self):
        """캐시 전체 삭제"""
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
            except:
                pass
        logger.info("캐시 삭제 완료")


# ========== 통합 STT 시스템 ==========


class UltimateSTTSystem:
    """최종 통합 STT 시스템"""

    def __init__(self, config: Optional[STTConfig] = None):
        """
        초기화

        Args:
            config: STT 시스템 설정
        """
        self.config = config or STTConfig()

        # 컴포넌트 초기화
        self.audio_normalizer = AudioNormalizer()
        self.audio_enhancer = AudioQualityEnhancer()
        self.korean_optimizer = KoreanAudioOptimizer()
        self.advanced_stt = AdvancedSTTProcessor()
        self.multi_engine = MultiEngineSTT()

        # 캐시 시스템
        self.cache = STTCache() if self.config.enable_caching else None

        # 파일 핸들러
        self.file_handler = file_handler

        logger.info("UltimateSTTSystem 초기화 완료")

    @handle_errors(context="process_audio")
    @log_execution_time
    def process_audio(
            self,
            audio_path: Union[str, Path],
            config: Optional[STTConfig] = None,
            reference_text: Optional[str] = None) -> UltimateSTTResult:
        """
        오디오 파일 종합 처리

        Args:
            audio_path: 오디오 파일 경로
            config: 처리 설정 (None이면 기본 설정 사용)
            reference_text: 참조 텍스트

        Returns:
            최종 STT 결과
        """
        audio_path = Path(audio_path)
        config = config or self.config

        # 세션 생성
        session = self._create_session(audio_path, config)

        # 감사 로깅
        audit_logger.log_action(action="stt_process_start",
                                target=str(audio_path),
                                details={'session_id': session.session_id})

        try:
            # 캐시 확인
            if self.cache and config.enable_caching:
                cache_key = self.cache.get_cache_key(audio_path, config)
                cached_result = self.cache.get(cache_key)

                if cached_result:
                    logger.info("캐시된 결과 사용")
                    return self._create_result_from_cache(
                        cached_result, session)

            # 1. 전처리
            if config.enable_preprocessing:
                audio_path = self._preprocess_audio(audio_path, session)

            # 2. STT 실행
            transcription = self._transcribe_audio(audio_path, session)

            # 3. 후처리
            if config.enable_postprocessing:
                transcription = self._postprocess_transcription(
                    transcription, session)

            # 4. 결과 생성
            result = self._create_final_result(session, transcription)

            # 5. 캐시 저장
            if self.cache and config.enable_caching:
                self.cache.set(cache_key, result.to_dict())

            # 성능 메트릭 기록
            performance_logger.log_metric(
                "stt_processing_time",
                session.processing_time,
                unit="seconds",
                tags={'engine': config.primary_engine})

            # 감사 로깅
            audit_logger.log_action(action="stt_process_complete",
                                    target=str(audio_path),
                                    result="success",
                                    details={
                                        'session_id': session.session_id,
                                        'confidence': result.confidence
                                    })

            return result

        except Exception as e:
            session.status = "failed"

            # 감사 로깅
            audit_logger.log_action(action="stt_process_failed",
                                    target=str(audio_path),
                                    result="failure",
                                    details={
                                        'session_id': session.session_id,
                                        'error': str(e)
                                    })

            raise

    def _create_session(self, audio_path: Path,
                        config: STTConfig) -> STTSession:
        """세션 생성"""
        import uuid

        session = STTSession(session_id=str(uuid.uuid4()),
                             start_time=datetime.now(),
                             config=config,
                             audio_file=str(audio_path),
                             status="processing")

        # 오디오 정보
        audio_info = self.file_handler.get_audio_info(audio_path)
        session.total_duration = audio_info.get('duration', 0.0)

        return session

    @handle_errors(context="preprocess_audio")
    def _preprocess_audio(self, audio_path: Path, session: STTSession) -> Path:
        """오디오 전처리"""
        logger.info("오디오 전처리 시작")
        start_time = time.time()

        config = session.config
        current_path = audio_path
        temp_files = []

        try:
            # 무음 제거
            if config.remove_silence:
                temp_path = self.file_handler.create_temp_file(suffix=".wav")
                current_path, ratio = self.audio_normalizer.remove_silence(
                    current_path, temp_path)
                temp_files.append(temp_path)

            # 정규화
            if config.normalize_audio:
                temp_path = self.file_handler.create_temp_file(suffix=".wav")
                current_path = self.audio_normalizer.normalize_volume(
                    current_path, temp_path)
                temp_files.append(temp_path)

            # 음질 향상
            if config.enhance_audio:
                temp_path = self.file_handler.create_temp_file(suffix=".wav")
                enhancement_result = self.audio_enhancer.enhance_audio_quality(
                    current_path, temp_path, denoise=True, enhance_speech=True)

                if enhancement_result['success']:
                    current_path = Path(enhancement_result['output_path'])
                    temp_files.append(current_path)

            # 한국어 최적화
            if config.language == "ko":
                temp_path = self.file_handler.create_temp_file(suffix=".wav")
                optimization_result = self.korean_optimizer.optimize_korean_speech(
                    current_path, temp_path)

                if optimization_result['success']:
                    current_path = Path(optimization_result['output_path'])
                    temp_files.append(current_path)

            # 중간 결과 저장
            if config.save_intermediate:
                intermediate_path = audio_path.parent / f"{audio_path.stem}_preprocessed.wav"
                self.file_handler.copy_file(current_path,
                                            intermediate_path,
                                            overwrite=True)

            # 세션 업데이트
            session.preprocessing_result = {
                'original_path': str(audio_path),
                'processed_path': str(current_path),
                'processing_time': time.time() - start_time,
                'steps': []
            }

            if config.remove_silence:
                session.preprocessing_result['steps'].append('silence_removal')
            if config.normalize_audio:
                session.preprocessing_result['steps'].append('normalization')
            if config.enhance_audio:
                session.preprocessing_result['steps'].append('enhancement')
            if config.language == "ko":
                session.preprocessing_result['steps'].append(
                    'korean_optimization')

            logger.info(f"전처리 완료: {time.time() - start_time:.2f}초")
            return current_path

        finally:
            # 임시 파일 정리 (최종 파일 제외)
            for temp_file in temp_files[:-1]:
                self.file_handler.safe_delete(temp_file)

    @handle_errors(context="transcribe_audio")
    def _transcribe_audio(self, audio_path: Path,
                          session: STTSession) -> TranscriptionResult:
        """오디오 전사"""
        logger.info("음성 인식 시작")
        start_time = time.time()

        config = session.config

        if config.enable_multi_engine:
            # 다중 엔진 사용
            engines = [config.primary_engine] + config.fallback_engines
            multi_result = self.multi_engine.transcribe_multiple(
                audio_path,
                engines=engines,
                language=config.language,
                parallel=True)

            # 최적 결과 선택
            if multi_result.best_result:
                transcription = TranscriptionResult(
                    text=multi_result.best_result.text,
                    segments=[],  # 세그먼트 변환 필요
                    language=multi_result.best_result.language,
                    duration=session.total_duration,
                    confidence=multi_result.best_result.confidence,
                    model_name=multi_result.best_result.engine,
                    processing_time=multi_result.total_processing_time)
            else:
                raise STTError("multi", "모든 엔진에서 전사 실패")
        else:
            # 단일 엔진 사용
            if config.primary_engine == "whisper":
                result = self.advanced_stt.process_audio(
                    audio_path,
                    language=config.language,
                    enhance_audio=False  # 이미 전처리됨
                )

                if result['success']:
                    trans_dict = result['transcription']
                    transcription = TranscriptionResult(
                        text=trans_dict['text'],
                        segments=[],  # 변환 필요
                        language=trans_dict['language'],
                        duration=trans_dict['duration'],
                        confidence=trans_dict['confidence'],
                        model_name=trans_dict['model_name'],
                        processing_time=trans_dict['processing_time'])

                    # 세그먼트 변환
                    for seg in trans_dict.get('segments', []):
                        from core.advanced_stt_processor import TranscriptionSegment
                        segment = TranscriptionSegment(id=seg['id'],
                                                       start=seg['start'],
                                                       end=seg['end'],
                                                       text=seg['text'],
                                                       confidence=seg.get(
                                                           'confidence', 0.0))
                        transcription.segments.append(segment)
                else:
                    raise STTError("whisper", result.get('error', '전사 실패'))
            else:
                # 다른 단일 엔진
                stt_result = self.multi_engine.transcribe_single(
                    audio_path, config.primary_engine, config.language)

                if stt_result.is_success:
                    transcription = TranscriptionResult(
                        text=stt_result.text,
                        segments=[],
                        language=stt_result.language,
                        duration=session.total_duration,
                        confidence=stt_result.confidence,
                        model_name=stt_result.engine,
                        processing_time=stt_result.processing_time)
                else:
                    raise STTError(config.primary_engine, stt_result.error)

        # 세션 업데이트
        session.transcription_result = transcription.to_dict()

        logger.info(f"음성 인식 완료: {time.time() - start_time:.2f}초")
        return transcription

    @handle_errors(context="postprocess_transcription")
    def _postprocess_transcription(self, transcription: TranscriptionResult,
                                   session: STTSession) -> TranscriptionResult:
        """전사 결과 후처리"""
        logger.info("후처리 시작")
        start_time = time.time()

        config = session.config

        # 텍스트 교정
        if config.correct_spelling:
            from core.advanced_stt_processor import STTPostProcessor
            post_processor = STTPostProcessor()

            corrected_text = post_processor.correct_transcription(
                transcription.text, transcription.language)
            transcription.text = corrected_text

        # 키워드 추출
        keywords = None
        if config.extract_keywords:
            from core.advanced_stt_processor import STTPostProcessor
            post_processor = STTPostProcessor()

            keywords = post_processor.extract_keywords(transcription.text,
                                                       transcription.language)

        # 세션 업데이트
        session.postprocessing_result = {
            'corrected_text': transcription.text,
            'keywords': keywords,
            'processing_time': time.time() - start_time
        }

        logger.info(f"후처리 완료: {time.time() - start_time:.2f}초")
        return transcription

    def _create_final_result(
            self, session: STTSession,
            transcription: TranscriptionResult) -> UltimateSTTResult:
        """최종 결과 생성"""
        session.status = "completed"
        session.processing_time = (datetime.now() -
                                   session.start_time).total_seconds()

        # 세그먼트 변환
        segments = []
        for seg in transcription.segments:
            segments.append({
                'id': seg.id,
                'start': seg.start,
                'end': seg.end,
                'text': seg.text,
                'confidence': seg.confidence
            })

        # 키워드 가져오기
        keywords = None
        if session.postprocessing_result:
            keywords = session.postprocessing_result.get('keywords')

        # 메타데이터 생성
        metadata = {
            'model': transcription.model_name,
            'processing_steps': [],
            'audio_duration': session.total_duration,
            'processing_time': session.processing_time
        }

        if session.preprocessing_result:
            metadata['processing_steps'].extend(
                session.preprocessing_result.get('steps', []))

        if session.config.enable_postprocessing:
            metadata['processing_steps'].append('postprocessing')

        return UltimateSTTResult(session=session,
                                 final_text=transcription.text,
                                 confidence=transcription.confidence,
                                 segments=segments,
                                 keywords=keywords,
                                 language=transcription.language,
                                 metadata=metadata)

    def _create_result_from_cache(self, cached_data: Dict,
                                  session: STTSession) -> UltimateSTTResult:
        """캐시에서 결과 생성"""
        session.status = "cached"

        return UltimateSTTResult(session=session,
                                 final_text=cached_data.get('final_text', ''),
                                 confidence=cached_data.get('confidence', 0.0),
                                 segments=cached_data.get('segments', []),
                                 keywords=cached_data.get('keywords'),
                                 language=cached_data.get(
                                     'language', 'unknown'),
                                 metadata=cached_data.get('metadata', {}))

    @handle_errors(context="batch_process")
    @log_execution_time
    def batch_process(self,
                      audio_files: List[Union[str, Path]],
                      config: Optional[STTConfig] = None,
                      output_dir: Optional[Path] = None,
                      parallel: bool = False) -> List[UltimateSTTResult]:
        """
        배치 처리

        Args:
            audio_files: 오디오 파일 리스트
            config: 처리 설정
            output_dir: 출력 디렉토리
            parallel: 병렬 처리 여부

        Returns:
            결과 리스트
        """
        config = config or self.config
        results = []

        # 출력 디렉토리 생성
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        if parallel:
            # 병렬 처리
            from concurrent.futures import ProcessPoolExecutor

            with ProcessPoolExecutor(
                    max_workers=settings.MAX_WORKERS) as executor:
                futures = [
                    executor.submit(self.process_audio, audio_file, config)
                    for audio_file in audio_files
                ]

                for future in futures:
                    try:
                        result = future.result(timeout=config.timeout)
                        results.append(result)
                    except Exception as e:
                        logger.error(f"배치 처리 실패: {e}")
        else:
            # 순차 처리
            for i, audio_file in enumerate(audio_files, 1):
                logger.info(f"배치 처리: {i}/{len(audio_files)}")

                try:
                    result = self.process_audio(audio_file, config)
                    results.append(result)

                    # 결과 저장
                    if output_dir:
                        self._save_result(result, output_dir)

                except Exception as e:
                    logger.error(f"파일 처리 실패 ({audio_file}): {e}")

        # 요약 통계
        success_count = len(
            [r for r in results if r.session.status == "completed"])
        logger.info(f"배치 처리 완료: {success_count}/{len(audio_files)} 성공")

        return results

    def _save_result(self, result: UltimateSTTResult, output_dir: Path):
        """결과 저장"""
        audio_path = Path(result.session.audio_file)
        base_name = audio_path.stem

        # 형식별 저장
        if result.session.config.output_format == "json":
            output_file = output_dir / f"{base_name}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result.to_json())

        elif result.session.config.output_format == "text":
            output_file = output_dir / f"{base_name}.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result.final_text)

        elif result.session.config.output_format == "srt":
            output_file = output_dir / f"{base_name}.srt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result.to_srt())

        elif result.session.config.output_format == "vtt":
            output_file = output_dir / f"{base_name}.vtt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result.to_vtt())

        logger.debug(f"결과 저장: {output_file}")

# 메인 실행 코드
if __name__ == "__main__":
    # 테스트
    config = STTConfig(enable_preprocessing=True,
                       enable_multi_engine=False,
                       primary_engine="whisper",
                       language="ko",
                       enable_postprocessing=True,
                       output_format="json")

    system = UltimateSTTSystem(config)

    # 참조 파일 테스트
    if settings.REFERENCE_FILES_PATH.exists():
        test_files = list(settings.REFERENCE_FILES_PATH.glob("*.wav"))[:1]

        for test_file in test_files:
            logger.info(f"통합 STT 테스트: {test_file}")

            result = system.process_audio(test_file)

            logger.info(f"최종 텍스트: {result.final_text}")
            logger.info(f"신뢰도: {result.confidence:.2f}")
            logger.info(f"언어: {result.language}")

            if result.keywords:
                logger.info(f"키워드: {', '.join(result.keywords)}")

            logger.info(f"처리 시간: {result.session.processing_time:.2f}초")
