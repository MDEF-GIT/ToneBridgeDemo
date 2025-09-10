"""
다중 엔진 STT 모듈
Google, Azure, Naver 등 여러 STT 엔진을 통합 관리
"""

import warnings

warnings.filterwarnings('ignore')

import os
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import numpy as np
from dataclasses import dataclass
from enum import Enum
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

# 오디오 처리
import librosa
import soundfile as sf
from pydub import AudioSegment

# STT 엔진들
try:
    from google.cloud import speech_v1 as speech
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

try:
    import azure.cognitiveservices.speech as speechsdk
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

import requests  # Naver API용

# 프로젝트 모듈
from config import settings
from utils import (FileHandler, file_handler, get_logger, log_execution_time,
                   handle_errors, STTError, ErrorRecovery)

logger = get_logger(__name__)

# ========== 열거형 정의 ==========


class STTEngine(Enum):
    """STT 엔진 타입"""
    WHISPER = "whisper"
    GOOGLE = "google"
    AZURE = "azure"
    NAVER = "naver"


# ========== 데이터 클래스 ==========


@dataclass
class STTResult:
    """STT 결과 데이터"""
    engine: str
    text: str
    confidence: float
    language: str
    processing_time: float
    segments: Optional[List[Dict]] = None
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.error is None and self.text != ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'engine': self.engine,
            'text': self.text,
            'confidence': self.confidence,
            'language': self.language,
            'processing_time': self.processing_time,
            'segments': self.segments,
            'error': self.error,
            'is_success': self.is_success
        }


@dataclass
class MultiSTTResult:
    """다중 STT 통합 결과"""
    results: List[STTResult]
    best_result: Optional[STTResult]
    consensus_text: Optional[str]
    combined_confidence: float
    total_processing_time: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'results': [r.to_dict() for r in self.results],
            'best_result':
            self.best_result.to_dict() if self.best_result else None,
            'consensus_text': self.consensus_text,
            'combined_confidence': self.combined_confidence,
            'total_processing_time': self.total_processing_time
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ========== Google Cloud STT ==========


class GoogleSTTEngine:
    """Google Cloud Speech-to-Text 엔진"""

    def __init__(self, credentials_path: Optional[str] = None):
        """
        초기화

        Args:
            credentials_path: 서비스 계정 키 파일 경로
        """
        if not GOOGLE_AVAILABLE:
            raise ImportError("google-cloud-speech 패키지가 설치되지 않았습니다")

        if not settings.ENABLE_GOOGLE_STT:
            raise ValueError("Google STT가 비활성화되어 있습니다")

        # 인증 설정
        if credentials_path:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        elif settings.GOOGLE_CLOUD_API_KEY:
            os.environ[
                'GOOGLE_APPLICATION_CREDENTIALS'] = settings.GOOGLE_CLOUD_API_KEY

        self.client = speech.SpeechClient()
        logger.info("GoogleSTTEngine 초기화 완료")

    @handle_errors(context="google_stt_transcribe")
    def transcribe(self,
                   audio_path: Union[str, Path],
                   language_code: str = "ko-KR",
                   enable_automatic_punctuation: bool = True,
                   enable_word_time_offsets: bool = True) -> STTResult:
        """
        Google STT로 전사

        Args:
            audio_path: 오디오 파일 경로
            language_code: 언어 코드
            enable_automatic_punctuation: 자동 구두점
            enable_word_time_offsets: 단어 타임스탬프

        Returns:
            STT 결과
        """
        start_time = time.time()

        try:
            # 오디오 파일 읽기
            with open(audio_path, 'rb') as audio_file:
                content = audio_file.read()

            # 오디오 설정
            audio = speech.RecognitionAudio(content=content)

            # 인식 설정
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                language_code=language_code,
                enable_automatic_punctuation=enable_automatic_punctuation,
                enable_word_time_offsets=enable_word_time_offsets,
                model="latest_long",  # 최신 모델 사용
                use_enhanced=True,  # 향상된 모델 사용
            )

            # STT 실행
            response = self.client.recognize(config=config, audio=audio)

            # 결과 파싱
            if response.results:
                result = response.results[0]
                alternative = result.alternatives[0]

                # 세그먼트 정보 추출
                segments = []
                if enable_word_time_offsets:
                    for word in alternative.words:
                        segments.append({
                            'word':
                            word.word,
                            'start_time':
                            word.start_time.total_seconds(),
                            'end_time':
                            word.end_time.total_seconds()
                        })

                return STTResult(engine=STTEngine.GOOGLE.value,
                                 text=alternative.transcript,
                                 confidence=alternative.confidence,
                                 language=language_code,
                                 processing_time=time.time() - start_time,
                                 segments=segments if segments else None)
            else:
                return STTResult(engine=STTEngine.GOOGLE.value,
                                 text="",
                                 confidence=0.0,
                                 language=language_code,
                                 processing_time=time.time() - start_time,
                                 error="No transcription results")

        except Exception as e:
            return STTResult(engine=STTEngine.GOOGLE.value,
                             text="",
                             confidence=0.0,
                             language=language_code,
                             processing_time=time.time() - start_time,
                             error=str(e))


# ========== Azure STT ==========


class AzureSTTEngine:
    """Azure Speech Services STT 엔진"""

    def __init__(self,
                 subscription_key: Optional[str] = None,
                 region: Optional[str] = None):
        """
        초기화

        Args:
            subscription_key: Azure 구독 키
            region: Azure 지역
        """
        if not AZURE_AVAILABLE:
            raise ImportError("azure-cognitiveservices-speech 패키지가 설치되지 않았습니다")

        if not settings.ENABLE_AZURE_STT:
            raise ValueError("Azure STT가 비활성화되어 있습니다")

        self.subscription_key = subscription_key or settings.AZURE_SPEECH_KEY
        self.region = region or settings.AZURE_SPEECH_REGION

        if not self.subscription_key:
            raise ValueError("Azure 구독 키가 설정되지 않았습니다")

        # Speech 설정
        self.speech_config = speechsdk.SpeechConfig(
            subscription=self.subscription_key, region=self.region)

        logger.info(f"AzureSTTEngine 초기화 완료 (지역: {self.region})")

    @handle_errors(context="azure_stt_transcribe")
    def transcribe(self,
                   audio_path: Union[str, Path],
                   language: str = "ko-KR") -> STTResult:
        """
        Azure STT로 전사

        Args:
            audio_path: 오디오 파일 경로
            language: 언어 코드

        Returns:
            STT 결과
        """
        start_time = time.time()

        try:
            # 언어 설정
            self.speech_config.speech_recognition_language = language

            # 오디오 설정
            audio_config = speechsdk.AudioConfig(filename=str(audio_path))

            # 인식기 생성
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.speech_config, audio_config=audio_config)

            # 상세 결과를 위한 설정
            recognizer.properties.set_property(
                speechsdk.PropertyId.
                SpeechServiceResponse_RequestDetailedResultTrueFalse, 'true')

            # 동기 인식 실행
            result = recognizer.recognize_once()

            # 결과 처리
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                # JSON 결과 파싱
                json_result = json.loads(result.json)

                # 신뢰도 추출
                confidence = 0.0
                if 'NBest' in json_result and json_result['NBest']:
                    confidence = json_result['NBest'][0].get('Confidence', 0.0)

                return STTResult(engine=STTEngine.AZURE.value,
                                 text=result.text,
                                 confidence=confidence,
                                 language=language,
                                 processing_time=time.time() - start_time)

            elif result.reason == speechsdk.ResultReason.NoMatch:
                return STTResult(engine=STTEngine.AZURE.value,
                                 text="",
                                 confidence=0.0,
                                 language=language,
                                 processing_time=time.time() - start_time,
                                 error="No speech could be recognized")

            else:
                return STTResult(
                    engine=STTEngine.AZURE.value,
                    text="",
                    confidence=0.0,
                    language=language,
                    processing_time=time.time() - start_time,
                    error=f"Speech recognition canceled: {result.reason}")

        except Exception as e:
            return STTResult(engine=STTEngine.AZURE.value,
                             text="",
                             confidence=0.0,
                             language=language,
                             processing_time=time.time() - start_time,
                             error=str(e))


# ========== Naver Clova STT ==========


class NaverSTTEngine:
    """Naver Clova Speech STT 엔진"""

    def __init__(self,
                 client_id: Optional[str] = None,
                 client_secret: Optional[str] = None):
        """
        초기화

        Args:
            client_id: Naver API 클라이언트 ID
            client_secret: Naver API 클라이언트 시크릿
        """
        if not settings.ENABLE_NAVER_STT:
            raise ValueError("Naver STT가 비활성화되어 있습니다")

        self.client_id = client_id or settings.NAVER_CLIENT_ID
        self.client_secret = client_secret or settings.NAVER_CLIENT_SECRET

        if not self.client_id or not self.client_secret:
            raise ValueError("Naver API 인증 정보가 설정되지 않았습니다")

        self.api_url = "https://naveropenapi.apigw.ntruss.com/recog/v1/stt"

        logger.info("NaverSTTEngine 초기화 완료")

    @handle_errors(context="naver_stt_transcribe")
    def transcribe(self,
                   audio_path: Union[str, Path],
                   language: str = "Kor") -> STTResult:
        """
        Naver STT로 전사

        Args:
            audio_path: 오디오 파일 경로
            language: 언어 코드 (Kor, Eng, Jpn, Chn)

        Returns:
            STT 결과
        """
        start_time = time.time()

        try:
            # 오디오 파일 읽기
            with open(audio_path, 'rb') as f:
                audio_data = f.read()

            # 헤더 설정
            headers = {
                "X-NCP-APIGW-API-KEY-ID": self.client_id,
                "X-NCP-APIGW-API-KEY": self.client_secret,
                "Content-Type": "application/octet-stream"
            }

            # 파라미터
            params = {"lang": language}

            # API 요청
            response = requests.post(self.api_url,
                                     params=params,
                                     headers=headers,
                                     data=audio_data,
                                     timeout=30)

            # 응답 처리
            if response.status_code == 200:
                result_text = response.text

                return STTResult(
                    engine=STTEngine.NAVER.value,
                    text=result_text,
                    confidence=0.9,  # Naver는 신뢰도를 제공하지 않음
                    language=language,
                    processing_time=time.time() - start_time)
            else:
                return STTResult(engine=STTEngine.NAVER.value,
                                 text="",
                                 confidence=0.0,
                                 language=language,
                                 processing_time=time.time() - start_time,
                                 error=f"API error: {response.status_code}")

        except Exception as e:
            return STTResult(engine=STTEngine.NAVER.value,
                             text="",
                             confidence=0.0,
                             language=language,
                             processing_time=time.time() - start_time,
                             error=str(e))


# ========== 다중 엔진 STT 관리자 ==========


class MultiEngineSTT:
    """다중 STT 엔진 통합 관리 클래스"""

    def __init__(self,
                 engines: Optional[List[str]] = None,
                 enable_whisper: bool = True):
        """
        초기화

        Args:
            engines: 사용할 엔진 리스트
            enable_whisper: Whisper 엔진 포함 여부
        """
        self.engines = {}
        self.file_handler = file_handler

        # Whisper 엔진
        if enable_whisper:
            try:
                from core.advanced_stt_processor import WhisperProcessor
                self.engines[STTEngine.WHISPER.value] = WhisperProcessor()
                logger.info("Whisper 엔진 활성화")
            except Exception as e:
                logger.warning(f"Whisper 엔진 로드 실패: {e}")

        # 엔진 리스트가 지정되지 않으면 설정에서 가져옴
        if engines is None:
            engines = []
            if settings.ENABLE_GOOGLE_STT:
                engines.append(STTEngine.GOOGLE.value)
            if settings.ENABLE_AZURE_STT:
                engines.append(STTEngine.AZURE.value)
            if settings.ENABLE_NAVER_STT:
                engines.append(STTEngine.NAVER.value)

        # 각 엔진 초기화
        for engine_name in engines:
            self._initialize_engine(engine_name)

        logger.info(f"MultiEngineSTT 초기화 완료: {list(self.engines.keys())}")

    def _initialize_engine(self, engine_name: str):
        """개별 엔진 초기화"""
        try:
            if engine_name == STTEngine.GOOGLE.value and GOOGLE_AVAILABLE:
                self.engines[engine_name] = GoogleSTTEngine()

            elif engine_name == STTEngine.AZURE.value and AZURE_AVAILABLE:
                self.engines[engine_name] = AzureSTTEngine()

            elif engine_name == STTEngine.NAVER.value:
                self.engines[engine_name] = NaverSTTEngine()

            logger.info(f"{engine_name} 엔진 초기화 성공")

        except Exception as e:
            logger.warning(f"{engine_name} 엔진 초기화 실패: {e}")

    @handle_errors(context="transcribe_single_engine")
    def transcribe_single(self,
                          audio_path: Union[str, Path],
                          engine_name: str,
                          language: Optional[str] = None) -> STTResult:
        """
        단일 엔진으로 전사

        Args:
            audio_path: 오디오 파일 경로
            engine_name: 엔진 이름
            language: 언어 코드

        Returns:
            STT 결과
        """
        if engine_name not in self.engines:
            return STTResult(engine=engine_name,
                             text="",
                             confidence=0.0,
                             language=language or "unknown",
                             processing_time=0.0,
                             error=f"Engine {engine_name} not available")

        engine = self.engines[engine_name]

        # 언어 코드 변환 (엔진별 형식)
        if language is None:
            language = self._get_default_language(engine_name)
        else:
            language = self._convert_language_code(language, engine_name)

        # 전사 실행
        if engine_name == STTEngine.WHISPER.value:
            # Whisper는 다른 인터페이스 사용
            result = engine.transcribe(audio_path, language=language)
            return STTResult(engine=STTEngine.WHISPER.value,
                             text=result.text,
                             confidence=result.confidence,
                             language=result.language,
                             processing_time=result.processing_time,
                             segments=[s.to_dict() for s in result.segments]
                             if result.segments else None)
        else:
            return engine.transcribe(audio_path, language)

    @handle_errors(context="transcribe_multiple_engines")
    @log_execution_time
    def transcribe_multiple(self,
                            audio_path: Union[str, Path],
                            engines: Optional[List[str]] = None,
                            language: Optional[str] = None,
                            parallel: bool = True) -> MultiSTTResult:
        """
        다중 엔진으로 전사

        Args:
            audio_path: 오디오 파일 경로
            engines: 사용할 엔진 리스트 (None이면 모든 엔진)
            language: 언어 코드
            parallel: 병렬 처리 여부

        Returns:
            통합 STT 결과
        """
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {audio_path}")

        # 사용할 엔진 결정
        if engines is None:
            engines = list(self.engines.keys())
        else:
            engines = [e for e in engines if e in self.engines]

        if not engines:
            raise ValueError("사용 가능한 엔진이 없습니다")

        start_time = time.time()
        results = []

        if parallel and len(engines) > 1:
            # 병렬 처리
            with ThreadPoolExecutor(max_workers=len(engines)) as executor:
                futures = {
                    executor.submit(self.transcribe_single, audio_path, engine, language):
                    engine
                    for engine in engines
                }

                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=60)
                        results.append(result)
                    except Exception as e:
                        engine = futures[future]
                        logger.error(f"{engine} 전사 실패: {e}")
                        results.append(
                            STTResult(engine=engine,
                                      text="",
                                      confidence=0.0,
                                      language=language or "unknown",
                                      processing_time=0.0,
                                      error=str(e)))
        else:
            # 순차 처리
            for engine in engines:
                result = self.transcribe_single(audio_path, engine, language)
                results.append(result)

        # 결과 분석
        best_result = self._select_best_result(results)
        consensus_text = self._get_consensus_text(results)
        combined_confidence = self._calculate_combined_confidence(results)

        return MultiSTTResult(results=results,
                              best_result=best_result,
                              consensus_text=consensus_text,
                              combined_confidence=combined_confidence,
                              total_processing_time=time.time() - start_time)

    def _select_best_result(self,
                            results: List[STTResult]) -> Optional[STTResult]:
        """최적 결과 선택"""
        valid_results = [r for r in results if r.is_success]

        if not valid_results:
            return None

        # 신뢰도 기준 정렬
        return max(valid_results, key=lambda x: x.confidence)

    def _get_consensus_text(self, results: List[STTResult]) -> Optional[str]:
        """합의 텍스트 도출"""
        valid_texts = [r.text for r in results if r.is_success and r.text]

        if not valid_texts:
            return None

        if len(valid_texts) == 1:
            return valid_texts[0]

        # 가장 많이 나온 텍스트 선택
        from collections import Counter
        text_counts = Counter(valid_texts)
        most_common = text_counts.most_common(1)[0]

        # 과반수 이상이면 합의로 간주
        if most_common[1] > len(valid_texts) / 2:
            return most_common[0]

        # 아니면 최고 신뢰도 텍스트 반환
        best_result = self._select_best_result(results)
        return best_result.text if best_result else None

    def _calculate_combined_confidence(self,
                                       results: List[STTResult]) -> float:
        """통합 신뢰도 계산"""
        valid_results = [r for r in results if r.is_success]

        if not valid_results:
            return 0.0

        # 가중 평균 (신뢰도가 높을수록 가중치 증가)
        total_weight = 0
        weighted_sum = 0

        for result in valid_results:
            weight = result.confidence**2  # 제곱으로 가중치
            weighted_sum += result.confidence * weight
            total_weight += weight

        if total_weight > 0:
            return weighted_sum / total_weight

        return np.mean([r.confidence for r in valid_results])

    def _get_default_language(self, engine_name: str) -> str:
        """엔진별 기본 언어 코드"""
        language_map = {
            STTEngine.WHISPER.value: "ko",
            STTEngine.GOOGLE.value: "ko-KR",
            STTEngine.AZURE.value: "ko-KR",
            STTEngine.NAVER.value: "Kor"
        }
        return language_map.get(engine_name, "ko")

    def _convert_language_code(self, language: str, engine_name: str) -> str:
        """언어 코드 변환"""
        # 한국어 변환
        if language in ["ko", "korean", "한국어"]:
            if engine_name == STTEngine.WHISPER.value:
                return "ko"
            elif engine_name == STTEngine.NAVER.value:
                return "Kor"
            else:
                return "ko-KR"

        # 영어 변환
        elif language in ["en", "english", "영어"]:
            if engine_name == STTEngine.WHISPER.value:
                return "en"
            elif engine_name == STTEngine.NAVER.value:
                return "Eng"
            else:
                return "en-US"

        # 기본값
        return language

    @handle_errors(context="evaluate_engines")
    def evaluate_engines(self,
                         audio_path: Union[str, Path],
                         reference_text: str,
                         language: Optional[str] = None) -> Dict[str, Any]:
        """
        엔진 성능 평가

        Args:
            audio_path: 오디오 파일 경로
            reference_text: 참조 텍스트
            language: 언어 코드

        Returns:
            평가 결과
        """
        # 모든 엔진으로 전사
        multi_result = self.transcribe_multiple(audio_path, language=language)

        # 각 엔진 평가
        evaluations = []
        for result in multi_result.results:
            if result.is_success:
                # 정확도 계산 (편집 거리)
                from difflib import SequenceMatcher
                similarity = SequenceMatcher(None, result.text.lower(),
                                             reference_text.lower()).ratio()

                evaluations.append({
                    'engine': result.engine,
                    'accuracy': similarity,
                    'confidence': result.confidence,
                    'processing_time': result.processing_time,
                    'text': result.text
                })
            else:
                evaluations.append({
                    'engine': result.engine,
                    'accuracy': 0.0,
                    'confidence': 0.0,
                    'processing_time': result.processing_time,
                    'error': result.error
                })

        # 순위 결정
        evaluations.sort(key=lambda x: x.get('accuracy', 0), reverse=True)

        return {
            'reference_text': reference_text,
            'evaluations': evaluations,
            'best_engine': evaluations[0]['engine'] if evaluations else None,
            'consensus_text': multi_result.consensus_text
        }


# 메인 실행 코드
if __name__ == "__main__":
    # 테스트
    multi_stt = MultiEngineSTT(enable_whisper=True)

    # 참조 파일 테스트
    if settings.REFERENCE_FILES_PATH.exists():
        test_files = list(settings.REFERENCE_FILES_PATH.glob("*.wav"))[:1]

        for test_file in test_files:
            logger.info(f"다중 STT 테스트: {test_file}")

            # 다중 엔진 전사
            result = multi_stt.transcribe_multiple(test_file,
                                                   language="ko",
                                                   parallel=True)

            logger.info(f"활성 엔진: {[r.engine for r in result.results]}")

            if result.best_result:
                logger.info(
                    f"최적 결과 ({result.best_result.engine}): {result.best_result.text}"
                )
                logger.info(f"신뢰도: {result.best_result.confidence:.2f}")

            if result.consensus_text:
                logger.info(f"합의 텍스트: {result.consensus_text}")
                logger.info(f"통합 신뢰도: {result.combined_confidence:.2f}")
