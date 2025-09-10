"""
음성 처리 파이프라인
전체 음성 처리 워크플로우를 관리하는 통합 시스템
"""

import warnings

warnings.filterwarnings('ignore')

import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import uuid

# 오디오 처리
import numpy as np
import librosa

# 프로젝트 모듈
from config import settings
from utils import (FileHandler, file_handler, get_logger, log_execution_time,
                   handle_errors, PerformanceLogger, AuditLogger)

# Core 모듈
from core import (AudioNormalizer, AudioQualityEnhancer, KoreanAudioOptimizer,
                  VoiceAnalyzer, AdvancedSTTProcessor, QualityValidator)

# ToneBridge Core 모듈
from tonebridge_core.models import (ProcessingStatus, AudioFormat, Language,
                                    AudioMetadata, AnalysisResult,
                                    ProcessingConfig)
from tonebridge_core.analysis import PitchAnalyzer, FormantAnalyzer, SpectralAnalyzer
from tonebridge_core.segmentation import KoreanSegmenter
from tonebridge_core.stt import UniversalSTT
from tonebridge_core.textgrid import TextGridGenerator

logger = get_logger(__name__)
performance_logger = PerformanceLogger()
audit_logger = AuditLogger()

# ========== 파이프라인 스테이지 ==========


class PipelineStage(Enum):
    """파이프라인 처리 단계"""
    VALIDATION = "validation"
    PREPROCESSING = "preprocessing"
    NORMALIZATION = "normalization"
    ENHANCEMENT = "enhancement"
    ANALYSIS = "analysis"
    SEGMENTATION = "segmentation"
    TRANSCRIPTION = "transcription"
    TEXTGRID_GENERATION = "textgrid_generation"
    QUALITY_CHECK = "quality_check"
    POSTPROCESSING = "postprocessing"


# ========== 설정 클래스 ==========


@dataclass
class PipelineConfig:
    """파이프라인 설정"""
    # 단계별 활성화
    enable_validation: bool = True
    enable_preprocessing: bool = True
    enable_normalization: bool = True
    enable_enhancement: bool = True
    enable_analysis: bool = True
    enable_segmentation: bool = True
    enable_transcription: bool = True
    enable_textgrid: bool = True
    enable_quality_check: bool = True
    enable_postprocessing: bool = True

    # 처리 옵션
    language: Language = Language.KOREAN
    target_sample_rate: int = 16000
    remove_silence: bool = True
    normalize_volume: bool = True
    denoise: bool = True

    # 분석 옵션
    analyze_pitch: bool = True
    analyze_formants: bool = True
    analyze_spectrum: bool = True

    # STT 옵션
    stt_engine: str = "whisper"
    stt_language: str = "ko"
    enable_multi_engine: bool = False

    # 출력 옵션
    save_intermediate: bool = False
    output_format: str = "json"
    generate_report: bool = True

    # 성능 옵션
    use_cache: bool = True
    parallel_processing: bool = False
    max_workers: int = 4
    timeout: int = 300

    def to_dict(self) -> Dict[str, Any]:
        return {
            'stages': {
                'validation': self.enable_validation,
                'preprocessing': self.enable_preprocessing,
                'normalization': self.enable_normalization,
                'enhancement': self.enable_enhancement,
                'analysis': self.enable_analysis,
                'segmentation': self.enable_segmentation,
                'transcription': self.enable_transcription,
                'textgrid': self.enable_textgrid,
                'quality_check': self.enable_quality_check,
                'postprocessing': self.enable_postprocessing
            },
            'processing': {
                'language': self.language.value,
                'target_sample_rate': self.target_sample_rate,
                'remove_silence': self.remove_silence,
                'normalize_volume': self.normalize_volume,
                'denoise': self.denoise
            },
            'analysis': {
                'pitch': self.analyze_pitch,
                'formants': self.analyze_formants,
                'spectrum': self.analyze_spectrum
            },
            'stt': {
                'engine': self.stt_engine,
                'language': self.stt_language,
                'multi_engine': self.enable_multi_engine
            },
            'output': {
                'save_intermediate': self.save_intermediate,
                'format': self.output_format,
                'generate_report': self.generate_report
            },
            'performance': {
                'use_cache': self.use_cache,
                'parallel': self.parallel_processing,
                'max_workers': self.max_workers,
                'timeout': self.timeout
            }
        }


# ========== 파이프라인 결과 ==========


@dataclass
class StageResult:
    """단계별 처리 결과"""
    stage: PipelineStage
    status: ProcessingStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def duration(self) -> float:
        """처리 시간"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'stage': self.stage.value,
            'status': self.status.value,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': self.duration,
            'data': self.data,
            'error': self.error
        }


@dataclass
class PipelineResult:
    """파이프라인 처리 결과"""
    pipeline_id: str
    config: PipelineConfig
    input_file: str
    stages: List[StageResult]
    final_result: Optional[AnalysisResult] = None
    total_duration: float = 0.0
    status: ProcessingStatus = ProcessingStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        return {
            'pipeline_id': self.pipeline_id,
            'config': self.config.to_dict(),
            'input_file': self.input_file,
            'stages': [s.to_dict() for s in self.stages],
            'final_result':
            self.final_result.to_dict() if self.final_result else None,
            'total_duration': self.total_duration,
            'status': self.status.value
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def get_stage_result(self, stage: PipelineStage) -> Optional[StageResult]:
        """특정 단계 결과 가져오기"""
        for s in self.stages:
            if s.stage == stage:
                return s
        return None


# ========== 음성 처리기 ==========


class VoiceProcessor:
    """통합 음성 처리기"""

    def __init__(self):
        """초기화"""
        # 컴포넌트 초기화
        self.file_handler = file_handler
        self.audio_normalizer = AudioNormalizer()
        self.audio_enhancer = AudioQualityEnhancer()
        self.korean_optimizer = KoreanAudioOptimizer()
        self.voice_analyzer = VoiceAnalyzer()
        self.pitch_analyzer = PitchAnalyzer()
        self.formant_analyzer = FormantAnalyzer()
        self.spectral_analyzer = SpectralAnalyzer()
        self.korean_segmenter = KoreanSegmenter()
        self.stt_processor = AdvancedSTTProcessor()
        self.universal_stt = UniversalSTT()
        self.textgrid_generator = TextGridGenerator()
        self.quality_validator = QualityValidator()

        logger.info("VoiceProcessor 초기화 완료")

    @handle_errors(context="process_audio")
    @log_execution_time
    def process(self,
                audio_path: Union[str, Path],
                config: Optional[PipelineConfig] = None,
                output_dir: Optional[Path] = None) -> PipelineResult:
        """
        오디오 파일 처리

        Args:
            audio_path: 오디오 파일 경로
            config: 파이프라인 설정
            output_dir: 출력 디렉토리

        Returns:
            처리 결과
        """
        audio_path = Path(audio_path)
        config = config or PipelineConfig()

        # 파이프라인 결과 초기화
        result = PipelineResult(pipeline_id=str(uuid.uuid4()),
                                config=config,
                                input_file=str(audio_path),
                                stages=[],
                                status=ProcessingStatus.PROCESSING)

        # 출력 디렉토리 설정
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        start_time = time.time()

        try:
            # 1. 검증
            if config.enable_validation:
                self._run_stage(result, PipelineStage.VALIDATION,
                                lambda: self._validate(audio_path))

            # 2. 전처리
            current_audio = audio_path
            if config.enable_preprocessing:
                stage_result = self._run_stage(
                    result, PipelineStage.PREPROCESSING,
                    lambda: self._preprocess(current_audio, config))
                if stage_result and 'output_path' in stage_result.data:
                    current_audio = Path(stage_result.data['output_path'])

            # 3. 정규화
            if config.enable_normalization:
                stage_result = self._run_stage(
                    result, PipelineStage.NORMALIZATION,
                    lambda: self._normalize(current_audio, config))
                if stage_result and 'output_path' in stage_result.data:
                    current_audio = Path(stage_result.data['output_path'])

            # 4. 향상
            if config.enable_enhancement:
                stage_result = self._run_stage(
                    result, PipelineStage.ENHANCEMENT,
                    lambda: self._enhance(current_audio, config))
                if stage_result and 'output_path' in stage_result.data:
                    current_audio = Path(stage_result.data['output_path'])

            # 5. 분석
            analysis_data = {}
            if config.enable_analysis:
                stage_result = self._run_stage(
                    result, PipelineStage.ANALYSIS,
                    lambda: self._analyze(current_audio, config))
                if stage_result:
                    analysis_data = stage_result.data

            # 6. 분절
            segments = []
            if config.enable_segmentation:
                stage_result = self._run_stage(
                    result, PipelineStage.SEGMENTATION,
                    lambda: self._segment(current_audio, config))
                if stage_result and 'segments' in stage_result.data:
                    segments = stage_result.data['segments']

            # 7. 전사
            transcription = ""
            if config.enable_transcription:
                stage_result = self._run_stage(
                    result, PipelineStage.TRANSCRIPTION,
                    lambda: self._transcribe(current_audio, config))
                if stage_result and 'transcription' in stage_result.data:
                    transcription = stage_result.data['transcription']

            # 8. TextGrid 생성
            textgrid_path = None
            if config.enable_textgrid:
                stage_result = self._run_stage(
                    result, PipelineStage.TEXTGRID_GENERATION,
                    lambda: self._generate_textgrid(current_audio, segments,
                                                    transcription, output_dir))
                if stage_result and 'textgrid_path' in stage_result.data:
                    textgrid_path = stage_result.data['textgrid_path']

            # 9. 품질 검사
            quality_metrics = {}
            if config.enable_quality_check:
                stage_result = self._run_stage(
                    result, PipelineStage.QUALITY_CHECK,
                    lambda: self._check_quality(current_audio, transcription))
                if stage_result:
                    quality_metrics = stage_result.data

            # 10. 후처리
            if config.enable_postprocessing:
                self._run_stage(result, PipelineStage.POSTPROCESSING,
                                lambda: self._postprocess(result, output_dir))

            # 최종 결과 생성
            result.final_result = self._create_final_result(
                audio_path, current_audio, analysis_data, segments,
                transcription, quality_metrics)

            result.total_duration = time.time() - start_time
            result.status = ProcessingStatus.COMPLETED

            # 감사 로깅
            audit_logger.log_action(action="voice_processing_complete",
                                    target=str(audio_path),
                                    result="success",
                                    details={
                                        'pipeline_id': result.pipeline_id,
                                        'duration': result.total_duration
                                    })

            logger.info(
                f"음성 처리 완료: {audio_path.name} ({result.total_duration:.2f}초)")

        except Exception as e:
            result.status = ProcessingStatus.FAILED
            logger.error(f"음성 처리 실패: {str(e)}")

            audit_logger.log_action(action="voice_processing_failed",
                                    target=str(audio_path),
                                    result="failure",
                                    details={
                                        'pipeline_id': result.pipeline_id,
                                        'error': str(e)
                                    })
            raise

        return result

    def _run_stage(self, pipeline_result: PipelineResult, stage: PipelineStage,
                   func: Callable) -> Optional[StageResult]:
        """단계 실행"""
        stage_result = StageResult(stage=stage,
                                   status=ProcessingStatus.PROCESSING,
                                   start_time=datetime.now())

        try:
            logger.info(f"단계 시작: {stage.value}")
            data = func()

            stage_result.data = data if isinstance(data, dict) else {
                'result': data
            }
            stage_result.status = ProcessingStatus.COMPLETED
            stage_result.end_time = datetime.now()

            logger.info(f"단계 완료: {stage.value} ({stage_result.duration:.2f}초)")

        except Exception as e:
            stage_result.status = ProcessingStatus.FAILED
            stage_result.error = str(e)
            stage_result.end_time = datetime.now()

            logger.error(f"단계 실패: {stage.value} - {str(e)}")
            raise

        finally:
            pipeline_result.stages.append(stage_result)

        return stage_result

    def _validate(self, audio_path: Path) -> Dict[str, Any]:
        """검증 단계"""
        valid, issues = self.quality_validator.audio_validator.check_requirements(
            audio_path)

        if not valid:
            raise ValueError(f"오디오 검증 실패: {', '.join(issues)}")

        return {'valid': valid, 'issues': issues}

    def _preprocess(self, audio_path: Path,
                    config: PipelineConfig) -> Dict[str, Any]:
        """전처리 단계"""
        temp_path = self.file_handler.create_temp_file(suffix=".wav")

        # 샘플레이트 조정
        if config.target_sample_rate:
            temp_path = self.audio_normalizer.adjust_sample_rate(
                audio_path, temp_path, config.target_sample_rate)
        else:
            temp_path = audio_path

        return {'output_path': str(temp_path)}

    def _normalize(self, audio_path: Path,
                   config: PipelineConfig) -> Dict[str, Any]:
        """정규화 단계"""
        result = {'steps': []}
        current_path = audio_path

        # 무음 제거
        if config.remove_silence:
            temp_path = self.file_handler.create_temp_file(suffix=".wav")
            current_path, ratio = self.audio_normalizer.remove_silence(
                current_path, temp_path)
            result['steps'].append('silence_removal')
            result['silence_ratio'] = ratio

        # 볼륨 정규화
        if config.normalize_volume:
            temp_path = self.file_handler.create_temp_file(suffix=".wav")
            current_path = self.audio_normalizer.normalize_volume(
                current_path, temp_path)
            result['steps'].append('volume_normalization')

        result['output_path'] = str(current_path)
        return result

    def _enhance(self, audio_path: Path,
                 config: PipelineConfig) -> Dict[str, Any]:
        """향상 단계"""
        temp_path = self.file_handler.create_temp_file(suffix=".wav")

        enhancement_result = self.audio_enhancer.enhance_audio_quality(
            audio_path,
            temp_path,
            denoise=config.denoise,
            enhance_speech=True,
            apply_eq=True)

        if enhancement_result['success']:
            return {
                'output_path': enhancement_result['output_path'],
                'quality_metrics':
                enhancement_result.get('quality_metrics', {})
            }
        else:
            return {'output_path': str(audio_path)}

    def _analyze(self, audio_path: Path,
                 config: PipelineConfig) -> Dict[str, Any]:
        """분석 단계"""
        result = {}

        # 피치 분석
        if config.analyze_pitch:
            pitch_result = self.pitch_analyzer.analyze(audio_path)
            result['pitch'] = pitch_result.to_dict()

        # 포먼트 분석
        if config.analyze_formants:
            formant_result = self.formant_analyzer.analyze(audio_path)
            result['formants'] = formant_result.to_dict()

        # 스펙트럼 분석
        if config.analyze_spectrum:
            spectral_result = self.spectral_analyzer.analyze(audio_path)
            result['spectrum'] = spectral_result.to_dict()

        # 음성 분석
        voice_result = self.voice_analyzer.analyze_audio(audio_path)
        result['voice'] = voice_result

        return result

    def _segment(self, audio_path: Path,
                 config: PipelineConfig) -> Dict[str, Any]:
        """분절 단계"""
        if config.language == Language.KOREAN:
            segments = self.korean_segmenter.segment_audio(audio_path)
            return {'segments': [s.to_dict() for s in segments]}
        else:
            # 기본 분절
            segments = self.voice_analyzer.syllable_segmenter.segment_by_energy(
                audio_path)
            return {
                'segments': [{
                    'start': s[0],
                    'end': s[1]
                } for s in segments]
            }

    def _transcribe(self, audio_path: Path,
                    config: PipelineConfig) -> Dict[str, Any]:
        """전사 단계"""
        stt_result = self.stt_processor.process_audio(
            audio_path,
            language=config.stt_language,
            enhance_audio=False  # 이미 처리됨
        )

        if stt_result['success']:
            return {
                'transcription':
                stt_result.get('corrected_text',
                               stt_result['transcription']['text']),
                'confidence':
                stt_result['transcription'].get('confidence', 0.0),
                'keywords':
                stt_result.get('keywords', [])
            }
        else:
            return {'transcription': '', 'error': stt_result.get('error')}

    def _generate_textgrid(self, audio_path: Path, segments: List[Dict],
                           transcription: str,
                           output_dir: Optional[Path]) -> Dict[str, Any]:
        """TextGrid 생성 단계"""
        # 오디오 정보
        audio_info = self.file_handler.get_audio_info(audio_path)
        duration = audio_info['duration']

        # TextGrid 생성
        textgrid = self.textgrid_generator.generate(
            duration=duration, segments=segments, transcription=transcription)

        # 저장
        if output_dir:
            textgrid_path = output_dir / f"{audio_path.stem}.TextGrid"
        else:
            textgrid_path = audio_path.parent / f"{audio_path.stem}.TextGrid"

        self.textgrid_generator.save(textgrid, textgrid_path)

        return {'textgrid_path': str(textgrid_path)}

    def _check_quality(self, audio_path: Path,
                       transcription: str) -> Dict[str, Any]:
        """품질 검사 단계"""
        validation_result = self.quality_validator.validate_comprehensive(
            audio_path, transcribed_text=transcription)

        return validation_result.to_dict()

    def _postprocess(self, result: PipelineResult,
                     output_dir: Optional[Path]) -> Dict[str, Any]:
        """후처리 단계"""
        if output_dir and result.config.generate_report:
            # 보고서 생성
            report_path = output_dir / f"report_{result.pipeline_id}.json"
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(result.to_json())

            return {'report_path': str(report_path)}

        return {}

    def _create_final_result(self, original_audio: Path, processed_audio: Path,
                             analysis_data: Dict, segments: List,
                             transcription: str,
                             quality_metrics: Dict) -> AnalysisResult:
        """최종 결과 생성"""
        from tonebridge_core.models import (AudioMetadata, AudioSegment,
                                            AnalysisResult, AudioFormat,
                                            Language)

        # 오디오 메타데이터
        audio_info = self.file_handler.get_audio_info(processed_audio)
        metadata = AudioMetadata(file_path=str(processed_audio),
                                 format=AudioFormat.WAV,
                                 duration=audio_info['duration'],
                                 sample_rate=audio_info['sample_rate'],
                                 channels=audio_info['channels'])

        # 세그먼트 변환
        audio_segments = []
        for i, seg in enumerate(segments):
            from tonebridge_core.models import TimeInterval
            audio_segments.append(
                AudioSegment(id=str(i),
                             interval=TimeInterval(seg.get('start', 0),
                                                   seg.get('end', 0)),
                             text=seg.get('text', ''),
                             confidence=seg.get('confidence', 0.0)))

        # 최종 결과
        return AnalysisResult(audio_metadata=metadata,
                              segments=audio_segments,
                              transcription=transcription,
                              language=Language.KOREAN,
                              metadata={
                                  'analysis': analysis_data,
                                  'quality': quality_metrics
                              })


# ========== 처리 파이프라인 ==========


class ProcessingPipeline:
    """처리 파이프라인 관리"""

    def __init__(self, config: Optional[PipelineConfig] = None):
        """
        초기화

        Args:
            config: 파이프라인 설정
        """
        self.config = config or PipelineConfig()
        self.processor = VoiceProcessor()
        self.stages: List[Callable] = []

        logger.info("ProcessingPipeline 초기화 완료")

    def add_stage(self, stage: Callable, name: str = None):
        """
        사용자 정의 단계 추가

        Args:
            stage: 처리 함수
            name: 단계 이름
        """
        self.stages.append((stage, name or stage.__name__))
        logger.debug(f"파이프라인 단계 추가: {name or stage.__name__}")

    def run(self,
            audio_path: Union[str, Path],
            output_dir: Optional[Path] = None) -> PipelineResult:
        """
        파이프라인 실행

        Args:
            audio_path: 오디오 파일 경로
            output_dir: 출력 디렉토리

        Returns:
            처리 결과
        """
        # 기본 처리
        result = self.processor.process(audio_path, self.config, output_dir)

        # 사용자 정의 단계 실행
        for stage_func, stage_name in self.stages:
            try:
                logger.info(f"사용자 정의 단계 실행: {stage_name}")
                stage_result = stage_func(result)

                # 결과에 추가
                if stage_result:
                    result.stages.append(
                        StageResult(stage=PipelineStage.POSTPROCESSING,
                                    status=ProcessingStatus.COMPLETED,
                                    start_time=datetime.now(),
                                    end_time=datetime.now(),
                                    data={
                                        'custom_stage': stage_name,
                                        'result': stage_result
                                    }))

            except Exception as e:
                logger.error(f"사용자 정의 단계 실패 ({stage_name}): {str(e)}")

        return result


# ========== 배치 처리기 ==========


class BatchProcessor:
    """배치 처리 관리"""

    def __init__(self,
                 config: Optional[PipelineConfig] = None,
                 max_workers: Optional[int] = None):
        """
        초기화

        Args:
            config: 파이프라인 설정
            max_workers: 최대 워커 수
        """
        self.config = config or PipelineConfig()
        self.max_workers = max_workers or self.config.max_workers
        self.processor = VoiceProcessor()

        logger.info(f"BatchProcessor 초기화: 최대 {self.max_workers} 워커")

    @handle_errors(context="batch_process")
    @log_execution_time
    def process_batch(self,
                      audio_files: List[Union[str, Path]],
                      output_dir: Optional[Path] = None,
                      parallel: bool = None) -> List[PipelineResult]:
        """
        배치 처리

        Args:
            audio_files: 오디오 파일 리스트
            output_dir: 출력 디렉토리
            parallel: 병렬 처리 여부

        Returns:
            처리 결과 리스트
        """
        parallel = parallel if parallel is not None else self.config.parallel_processing
        results = []

        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        if parallel:
            # 병렬 처리
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                for audio_file in audio_files:
                    future = executor.submit(self.processor.process,
                                             audio_file, self.config,
                                             output_dir)
                    futures.append(future)

                for i, future in enumerate(futures):
                    try:
                        result = future.result(timeout=self.config.timeout)
                        results.append(result)
                        logger.info(f"배치 처리 완료: {i+1}/{len(audio_files)}")
                    except Exception as e:
                        logger.error(f"배치 처리 실패: {str(e)}")
        else:
            # 순차 처리
            for i, audio_file in enumerate(audio_files, 1):
                try:
                    result = self.processor.process(audio_file, self.config,
                                                    output_dir)
                    results.append(result)
                    logger.info(f"배치 처리 진행: {i}/{len(audio_files)}")
                except Exception as e:
                    logger.error(f"파일 처리 실패 ({audio_file}): {str(e)}")

        # 성능 메트릭
        success_count = sum(1 for r in results
                            if r.status == ProcessingStatus.COMPLETED)
        total_time = sum(r.total_duration for r in results)

        performance_logger.log_metric("batch_processing_success_rate",
                                      success_count /
                                      len(audio_files) if audio_files else 0,
                                      tags={'batch_size': len(audio_files)})

        logger.info(f"배치 처리 완료: {success_count}/{len(audio_files)} 성공, "
                    f"총 {total_time:.2f}초")

        return results


# 메인 실행 코드
if __name__ == "__main__":
    from config import settings

    # 테스트
    config = PipelineConfig(enable_validation=True,
                            enable_preprocessing=True,
                            enable_analysis=True,
                            enable_transcription=True,
                            language=Language.KOREAN)

    processor = VoiceProcessor()

    # 참조 파일 테스트
    if settings.REFERENCE_FILES_PATH.exists():
        test_files = list(settings.REFERENCE_FILES_PATH.glob("*.wav"))[:1]

        for test_file in test_files:
            logger.info(f"파이프라인 테스트: {test_file}")

            result = processor.process(test_file, config)

            logger.info(f"파이프라인 상태: {result.status.value}")
            logger.info(f"처리 시간: {result.total_duration:.2f}초")
            logger.info(
                f"완료 단계: {len([s for s in result.stages if s.status == ProcessingStatus.COMPLETED])}/{len(result.stages)}"
            )
