"""
고급 STT 처리 모듈
Whisper 기반 음성 인식 및 후처리 기능
"""

import warnings
warnings.filterwarnings('ignore')

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np
from dataclasses import dataclass
import time

# 오디오 처리
import librosa
import soundfile as sf
from pydub import AudioSegment

# Environment-aware STT import strategy
try:
    from utils import get_stt_config, get_environment
    env_config = get_stt_config()
    current_env = get_environment()
except ImportError:
    # Fallback for environments without utils
    env_config = {'prefer_faster_whisper': True}
    current_env = 'unknown'

# Dynamic STT engine selection based on environment
faster_whisper_available = False
openai_whisper_available = False

if env_config.get('prefer_faster_whisper', True):
    # Try faster-whisper first (preferred for Pure Nix)
    try:
        from faster_whisper import WhisperModel
        faster_whisper_available = True
        print(f"✅ faster-whisper loaded (환경: {current_env})")
    except ImportError:
        pass

if not faster_whisper_available or env_config.get('fallback_to_openai_whisper', True):
    # Try openai-whisper as fallback (or primary for Ubuntu)
    try:
        import whisper
        openai_whisper_available = True
        print(f"✅ openai-whisper loaded (환경: {current_env})")
    except ImportError:
        pass

# Final status
if not faster_whisper_available and not openai_whisper_available:
    print(f"❌ STT 엔진을 찾을 수 없습니다 (환경: {current_env})")
    whisper = None
    faster_whisper = False
else:
    faster_whisper = faster_whisper_available

# Torch for device detection
try:
    import torch
except ImportError:
    torch = None

# 텍스트 처리
import re
from difflib import SequenceMatcher

# 프로젝트 모듈
from config import settings
from utils import (
    FileHandler,
    file_handler,
    get_logger,
    log_execution_time,
    handle_errors,
    STTError,
    ErrorRecovery
)

logger = get_logger(__name__)


# ========== 데이터 클래스 ==========

@dataclass
class TranscriptionSegment:
    """전사 세그먼트"""
    id: int
    start: float
    end: float
    text: str
    confidence: float = 0.0
    words: Optional[List[Dict]] = None

    @property
    def duration(self) -> float:
        return self.end - self.start

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'id': self.id,
            'start': self.start,
            'end': self.end,
            'text': self.text,
            'duration': self.duration,
            'confidence': self.confidence
        }
        if self.words:
            result['words'] = self.words
        return result


@dataclass
class TranscriptionResult:
    """전사 결과"""
    text: str
    segments: List[TranscriptionSegment]
    language: str
    duration: float
    confidence: float = 0.0
    model_name: str = "whisper"
    processing_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'text': self.text,
            'segments': [s.to_dict() for s in self.segments],
            'language': self.language,
            'duration': self.duration,
            'confidence': self.confidence,
            'model_name': self.model_name,
            'processing_time': self.processing_time
        }

    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ========== Whisper STT 프로세서 ==========

class WhisperProcessor:
    """Whisper 기반 STT 처리 클래스"""

    def __init__(
        self,
        model_size: str = None,
        device: str = None,
        download_root: str = None
    ):
        """
        초기화

        Args:
            model_size: 모델 크기 (tiny, base, small, medium, large, large-v3)
            device: 연산 장치 (cuda, cpu)
            download_root: 모델 다운로드 경로
        """
        self.model_size = model_size or settings.WHISPER_MODEL
        self.device = device or self._get_device()
        self.download_root = download_root

        # 모델 로드
        self.model = None
        self._load_model()

        logger.info(
            f"WhisperProcessor 초기화: "
            f"모델={self.model_size}, 장치={self.device}"
        )

    def _get_device(self) -> str:
        """사용 가능한 장치 감지"""
        if torch is None:
            return "cpu"
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        else:
            return "cpu"

    @handle_errors(context="load_whisper_model")
    def _load_model(self):
        """Whisper 모델 로드 - faster-whisper 우선 사용"""
        global faster_whisper
        
        if faster_whisper:
            try:
                logger.info(f"Faster Whisper 모델 로딩 중: {self.model_size}")
                
                # Faster Whisper 모델 로드 (Pure Nix 호환)
                self.model = WhisperModel(
                    self.model_size, 
                    device=self.device,
                    download_root=self.download_root,
                    compute_type="int8" if self.device == "cpu" else "float16"
                )
                
                logger.info("Faster Whisper 모델 로드 완료")
                return
                
            except Exception as e:
                logger.warning(f"Faster Whisper 모델 로드 실패: {str(e)}")
                faster_whisper = False
        
        # 폴백: 기존 openai-whisper 사용
        if whisper is not None:
            try:
                logger.info(f"OpenAI Whisper 모델 로딩 중: {self.model_size}")

                self.model = whisper.load_model(
                    self.model_size,
                    device=self.device,
                    download_root=self.download_root
                )

                logger.info("OpenAI Whisper 모델 로드 완료")

            except Exception as e:
                logger.warning(f"OpenAI Whisper 모델 로드 실패: {str(e)}. STT 기능 제한됨.")
                self.model = None
        else:
            logger.warning("Whisper 라이브러리가 설치되지 않음. STT 기능 제한됨.")
            self.model = None

    @handle_errors(context="transcribe_audio")
    @log_execution_time
    def transcribe(
        self,
        audio_path: Union[str, Path],
        language: str = None,
        task: str = None,
        initial_prompt: str = None,
        temperature: float = 0.0,
        verbose: bool = False
    ) -> TranscriptionResult:
        """
        오디오 전사

        Args:
            audio_path: 오디오 파일 경로
            language: 언어 코드 (None이면 자동 감지)
            task: 작업 유형 ('transcribe' 또는 'translate')
            initial_prompt: 초기 프롬프트
            temperature: 샘플링 온도
            verbose: 상세 출력 여부

        Returns:
            전사 결과
        """
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {audio_path}")

        try:
            start_time = time.time()

            # 기본 설정
            language = language or settings.WHISPER_LANGUAGE
            task = task or settings.WHISPER_TASK

            # 전사 실행 - faster-whisper vs openai-whisper 호환성 처리
            global faster_whisper
            if faster_whisper and hasattr(self.model, 'transcribe') and 'WhisperModel' in str(type(self.model)):
                # Faster Whisper API
                segments, info = self.model.transcribe(
                    str(audio_path),
                    language=language,
                    task=task,
                    initial_prompt=initial_prompt,
                    temperature=temperature,
                    word_timestamps=True,
                    condition_on_previous_text=True
                )
                
                # Faster Whisper 결과를 OpenAI Whisper 형식으로 변환
                result = {
                    'text': '',
                    'segments': [],
                    'language': info.language if hasattr(info, 'language') else language
                }
                
                segment_list = []
                full_text_parts = []
                
                for i, segment in enumerate(segments):
                    seg_dict = {
                        'id': i,
                        'start': segment.start,
                        'end': segment.end,
                        'text': segment.text,
                        'confidence': getattr(segment, 'avg_logprob', 0.0),
                        'words': []
                    }
                    
                    # 단어별 정보 추가
                    if hasattr(segment, 'words') and segment.words:
                        for word in segment.words:
                            word_dict = {
                                'start': word.start,
                                'end': word.end,
                                'word': word.word,
                                'probability': getattr(word, 'probability', 0.0)
                            }
                            seg_dict['words'].append(word_dict)
                    
                    segment_list.append(seg_dict)
                    full_text_parts.append(segment.text)
                
                result['segments'] = segment_list
                result['text'] = ''.join(full_text_parts)
                
            else:
                # OpenAI Whisper API (기존)
                result = self.model.transcribe(
                    str(audio_path),
                    language=language,
                    task=task,
                    initial_prompt=initial_prompt,
                    temperature=temperature,
                    verbose=verbose,
                    word_timestamps=True,
                    condition_on_previous_text=True,
                    fp16=self.device != "cpu"
                )

            # 결과 파싱
            transcription = self._parse_transcription_result(result)

            # 처리 시간 기록
            transcription.processing_time = time.time() - start_time

            # 오디오 길이 가져오기
            audio_info = file_handler.get_audio_info(audio_path)
            transcription.duration = audio_info.get('duration', 0.0)

            logger.info(
                f"전사 완료: {audio_path.name} "
                f"({transcription.processing_time:.2f}초 소요)"
            )

            return transcription

        except Exception as e:
            raise STTError("whisper", f"전사 실패: {str(e)}")

    def _parse_transcription_result(self, result: Dict) -> TranscriptionResult:
        """Whisper 결과 파싱"""
        segments = []

        for i, seg in enumerate(result.get('segments', [])):
            segment = TranscriptionSegment(
                id=seg.get('id', i),
                start=seg.get('start', 0.0),
                end=seg.get('end', 0.0),
                text=seg.get('text', '').strip(),
                confidence=seg.get('confidence', seg.get('avg_logprob', 0.0)),
                words=seg.get('words', None)
            )
            segments.append(segment)

        # 전체 신뢰도 계산
        if segments:
            avg_confidence = np.mean([s.confidence for s in segments])
        else:
            avg_confidence = 0.0

        return TranscriptionResult(
            text=result.get('text', '').strip(),
            segments=segments,
            language=result.get('language', 'unknown'),
            duration=0.0,  # 나중에 설정
            confidence=avg_confidence,
            model_name=f"whisper-{self.model_size}"
        )

    @handle_errors(context="transcribe_with_vad")
    def transcribe_with_vad(
        self,
        audio_path: Union[str, Path],
        use_silero_vad: bool = True,
        **whisper_kwargs
    ) -> TranscriptionResult:
        """
        VAD를 활용한 전사 (성능 향상)

        Args:
            audio_path: 오디오 파일 경로
            use_silero_vad: Silero VAD 사용 여부
            **whisper_kwargs: Whisper 전사 옵션

        Returns:
            전사 결과
        """
        if use_silero_vad:
            # VAD로 음성 구간만 추출
            segments = self._extract_speech_segments(audio_path)

            if not segments:
                logger.warning("VAD가 음성을 감지하지 못함")
                return self.transcribe(audio_path, **whisper_kwargs)

            # 음성 구간만 포함하는 임시 파일 생성
            temp_audio = self._create_vad_audio(audio_path, segments)

            try:
                # 전사 실행
                result = self.transcribe(temp_audio, **whisper_kwargs)

                # 시간 정보 복원
                result = self._restore_timestamps(result, segments)

                return result

            finally:
                # 임시 파일 삭제
                file_handler.safe_delete(temp_audio)
        else:
            return self.transcribe(audio_path, **whisper_kwargs)

    def _extract_speech_segments(self, audio_path: Path) -> List[Tuple[float, float]]:
        """음성 구간 추출 (VAD)"""
        try:
            import webrtcvad

            # 오디오 로드 (16kHz, 모노)
            y, sr = librosa.load(str(audio_path), sr=16000, mono=True)

            # WebRTC VAD
            vad = webrtcvad.Vad(2)

            # 프레임 단위 처리
            frame_duration_ms = 30
            frame_length = int(sr * frame_duration_ms / 1000)

            segments = []
            in_speech = False
            start_time = 0

            for i in range(0, len(y), frame_length):
                frame = y[i:i+frame_length]

                if len(frame) < frame_length:
                    frame = np.pad(frame, (0, frame_length - len(frame)))

                # 16비트 PCM 변환
                frame_16bit = (frame * 32768).astype(np.int16)

                is_speech = vad.is_speech(frame_16bit.tobytes(), sr)

                if is_speech and not in_speech:
                    in_speech = True
                    start_time = i / sr
                elif not is_speech and in_speech:
                    in_speech = False
                    end_time = i / sr
                    segments.append((start_time, end_time))

            if in_speech:
                segments.append((start_time, len(y) / sr))

            return segments

        except Exception as e:
            logger.warning(f"VAD 실패: {e}")
            return []

    def _create_vad_audio(
        self,
        audio_path: Path,
        segments: List[Tuple[float, float]]
    ) -> Path:
        """VAD 세그먼트만 포함하는 오디오 생성"""
        # 오디오 로드
        y, sr = librosa.load(str(audio_path), sr=None)

        # 세그먼트 추출 및 결합
        vad_audio = []
        for start, end in segments:
            start_sample = int(start * sr)
            end_sample = int(end * sr)
            vad_audio.append(y[start_sample:end_sample])

        # 결합
        if vad_audio:
            combined = np.concatenate(vad_audio)
        else:
            combined = y

        # 임시 파일로 저장
        temp_path = file_handler.create_temp_file(suffix=".wav")
        sf.write(str(temp_path), combined, sr)

        return temp_path

    def _restore_timestamps(
        self,
        result: TranscriptionResult,
        vad_segments: List[Tuple[float, float]]
    ) -> TranscriptionResult:
        """VAD 처리 후 타임스탬프 복원"""
        # VAD 세그먼트 오프셋 계산
        offsets = []
        accumulated = 0
        for start, end in vad_segments:
            offsets.append((accumulated, start))
            accumulated += (end - start)

        # 세그먼트 시간 조정
        for segment in result.segments:
            # 원본 시간으로 매핑
            for vad_offset, original_start in offsets:
                if segment.start >= vad_offset:
                    time_diff = segment.start - vad_offset
                    segment.start = original_start + time_diff
                    segment.end = segment.start + (segment.end - segment.start)
                    break

        return result


# ========== STT 후처리 ==========

class STTPostProcessor:
    """STT 결과 후처리 클래스"""

    def __init__(self):
        """초기화"""
        logger.info("STTPostProcessor 초기화 완료")

    @handle_errors(context="correct_transcription")
    def correct_transcription(
        self,
        text: str,
        language: str = "ko"
    ) -> str:
        """
        전사 텍스트 교정

        Args:
            text: 원본 텍스트
            language: 언어 코드

        Returns:
            교정된 텍스트
        """
        if language == "ko":
            return self._correct_korean(text)
        else:
            return self._correct_general(text)

    def _correct_korean(self, text: str) -> str:
        """한국어 텍스트 교정"""
        # 공백 정규화
        text = re.sub(r'\s+', ' ', text)

        # 구두점 정규화
        text = re.sub(r'([가-힣])\s*([.,!?])', r'\1\2', text)
        text = re.sub(r'([.,!?])\s*([가-힣])', r'\1 \2', text)

        # 반복 문자 제거
        text = re.sub(r'([가-힣])\1{3,}', r'\1\1', text)

        # 일반적인 오타 수정
        corrections = {
            '그더': '그래',
            '너두': '너도',
            '뭐야': '뭐야',
            '어떻해': '어떻게',
            '괜찬': '괜찮'
        }

        for wrong, correct in corrections.items():
            text = text.replace(wrong, correct)

        return text.strip()

    def _correct_general(self, text: str) -> str:
        """일반 텍스트 교정"""
        # 공백 정규화
        text = re.sub(r'\s+', ' ', text)

        # 대소문자 정규화
        text = '. '.join(s.capitalize() for s in text.split('. '))

        return text.strip()

    @handle_errors(context="align_with_reference")
    def align_with_reference(
        self,
        transcribed: str,
        reference: str,
        threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        참조 텍스트와 정렬

        Args:
            transcribed: 전사된 텍스트
            reference: 참조 텍스트
            threshold: 유사도 임계값

        Returns:
            정렬 결과
        """
        # 정규화
        transcribed = self._normalize_for_comparison(transcribed)
        reference = self._normalize_for_comparison(reference)

        # 유사도 계산
        matcher = SequenceMatcher(None, transcribed, reference)
        similarity = matcher.ratio()

        # 차이점 찾기
        differences = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != 'equal':
                differences.append({
                    'type': tag,
                    'transcribed': transcribed[i1:i2],
                    'reference': reference[j1:j2],
                    'position': i1
                })

        # 정렬 결과
        return {
            'similarity': similarity,
            'is_match': similarity >= threshold,
            'differences': differences,
            'transcribed_normalized': transcribed,
            'reference_normalized': reference
        }

    def _normalize_for_comparison(self, text: str) -> str:
        """비교를 위한 텍스트 정규화"""
        # 소문자 변환
        text = text.lower()

        # 구두점 제거
        text = re.sub(r'[^\w\s가-힣]', '', text)

        # 공백 정규화
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    @handle_errors(context="extract_keywords")
    def extract_keywords(
        self,
        text: str,
        language: str = "ko",
        max_keywords: int = 10
    ) -> List[str]:
        """
        키워드 추출

        Args:
            text: 텍스트
            language: 언어 코드
            max_keywords: 최대 키워드 수

        Returns:
            키워드 리스트
        """
        if language == "ko":
            return self._extract_korean_keywords(text, max_keywords)
        else:
            return self._extract_general_keywords(text, max_keywords)

    def _extract_korean_keywords(self, text: str, max_keywords: int) -> List[str]:
        """한국어 키워드 추출"""
        try:
            from konlpy.tag import Okt
            okt = Okt()

            # 명사 추출
            nouns = okt.nouns(text)

            # 빈도 계산
            from collections import Counter
            counter = Counter(nouns)

            # 상위 키워드
            keywords = [word for word, count in counter.most_common(max_keywords)]

            return keywords

        except:
            # KoNLPy 없을 경우 간단한 추출
            words = text.split()
            return [w for w in words if len(w) > 1][:max_keywords]

    def _extract_general_keywords(self, text: str, max_keywords: int) -> List[str]:
        """일반 키워드 추출"""
        # 단어 분리
        words = re.findall(r'\w+', text.lower())

        # 불용어 제거
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        words = [w for w in words if w not in stopwords and len(w) > 2]

        # 빈도 계산
        from collections import Counter
        counter = Counter(words)

        # 상위 키워드
        keywords = [word for word, count in counter.most_common(max_keywords)]

        return keywords


# ========== 고급 STT 프로세서 ==========

class AdvancedSTTProcessor:
    """고급 STT 처리 통합 클래스"""

    def __init__(
        self,
        model_size: str = None,
        enable_vad: bool = True,
        enable_post_processing: bool = True
    ):
        """
        초기화

        Args:
            model_size: Whisper 모델 크기
            enable_vad: VAD 사용 여부
            enable_post_processing: 후처리 사용 여부
        """
        self.whisper = WhisperProcessor(model_size)
        self.post_processor = STTPostProcessor()
        self.enable_vad = enable_vad
        self.enable_post_processing = enable_post_processing
        self.file_handler = file_handler

        logger.info(
            f"AdvancedSTTProcessor 초기화: "
            f"VAD={enable_vad}, 후처리={enable_post_processing}"
        )

    @handle_errors(context="process_audio")
    @log_execution_time
    def process_audio(
        self,
        audio_path: Union[str, Path],
        language: str = None,
        reference_text: str = None,
        enhance_audio: bool = False
    ) -> Dict[str, Any]:
        """
        오디오 종합 처리

        Args:
            audio_path: 오디오 파일 경로
            language: 언어 코드
            reference_text: 참조 텍스트
            enhance_audio: 오디오 향상 여부

        Returns:
            처리 결과
        """
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {audio_path}")

        result = {
            'audio_path': str(audio_path),
            'language': language or settings.WHISPER_LANGUAGE
        }

        try:
            # 1. 오디오 전처리
            if enhance_audio:
                logger.debug("오디오 향상 중...")
                from core.audio_enhancement import AudioQualityEnhancer
                enhancer = AudioQualityEnhancer()

                temp_audio = self.file_handler.create_temp_file(suffix=".wav")
                enhancement_result = enhancer.enhance_audio_quality(
                    audio_path,
                    temp_audio,
                    denoise=True,
                    enhance_speech=True
                )

                if enhancement_result['success']:
                    audio_path = Path(enhancement_result['output_path'])
                    result['audio_enhanced'] = True

            # 2. STT 실행
            logger.debug("음성 인식 중...")
            if self.enable_vad:
                transcription = self.whisper.transcribe_with_vad(
                    audio_path,
                    language=result['language']
                )
            else:
                transcription = self.whisper.transcribe(
                    audio_path,
                    language=result['language']
                )

            result['transcription'] = transcription.to_dict()

            # 3. 후처리
            if self.enable_post_processing:
                logger.debug("텍스트 후처리 중...")

                # 텍스트 교정
                corrected_text = self.post_processor.correct_transcription(
                    transcription.text,
                    transcription.language
                )
                result['corrected_text'] = corrected_text

                # 키워드 추출
                keywords = self.post_processor.extract_keywords(
                    corrected_text,
                    transcription.language
                )
                result['keywords'] = keywords

                # 참조 텍스트와 비교
                if reference_text:
                    alignment = self.post_processor.align_with_reference(
                        corrected_text,
                        reference_text
                    )
                    result['alignment'] = alignment

            result['success'] = True

            logger.info(f"STT 처리 완료: {audio_path.name}")

        except Exception as e:
            result['success'] = False
            result['error'] = str(e)
            logger.error(f"STT 처리 실패: {str(e)}")

        finally:
            # 임시 파일 정리
            if enhance_audio and 'temp_audio' in locals():
                self.file_handler.safe_delete(temp_audio)

        return result

    @handle_errors(context="batch_process")
    @log_execution_time
    def batch_process(
        self,
        audio_files: List[Union[str, Path]],
        output_dir: Optional[Path] = None,
        **process_kwargs
    ) -> List[Dict[str, Any]]:
        """
        배치 처리

        Args:
            audio_files: 오디오 파일 리스트
            output_dir: 출력 디렉토리
            **process_kwargs: process_audio 옵션

        Returns:
            처리 결과 리스트
        """
        results = []

        # 출력 디렉토리 생성
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        for i, audio_file in enumerate(audio_files, 1):
            logger.info(f"배치 처리 중: {i}/{len(audio_files)}")

            # 처리
            result = self.process_audio(audio_file, **process_kwargs)

            # 결과 저장
            if output_dir and result.get('success'):
                audio_path = Path(audio_file)
                output_file = output_dir / f"{audio_path.stem}_stt.json"

                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

                result['output_file'] = str(output_file)

            results.append(result)

        # 요약
        success_count = sum(1 for r in results if r.get('success'))
        logger.info(f"배치 처리 완료: {success_count}/{len(audio_files)} 성공")

        return results


# 메인 실행 코드
if __name__ == "__main__":
    # 테스트
    processor = AdvancedSTTProcessor(
        model_size="base",
        enable_vad=True,
        enable_post_processing=True
    )

    # 참조 파일 테스트
    if settings.REFERENCE_FILES_PATH.exists():
        test_files = list(settings.REFERENCE_FILES_PATH.glob("*.wav"))[:1]

        for test_file in test_files:
            logger.info(f"STT 테스트: {test_file}")

            result = processor.process_audio(
                test_file,
                language="ko",
                enhance_audio=True
            )

            if result['success']:
                transcription = result['transcription']
                logger.info(f"인식 결과: {transcription['text']}")
                logger.info(f"신뢰도: {transcription['confidence']:.2f}")
                if 'keywords' in result:
                    logger.info(f"키워드: {', '.join(result['keywords'])}")