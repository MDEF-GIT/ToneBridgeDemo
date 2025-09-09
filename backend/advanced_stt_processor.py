"""
ToneBridge 고급 STT 처리 시스템
다중 STT 엔진 지원 및 한국어 특화 음절 정렬
"""

import numpy as np
import parselmouth as pm
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import json
import os
import sys
import requests

@dataclass
class TranscriptionResult:
    """전사 결과 클래스"""
    text: str
    language: str
    confidence: float
    words: List[Dict] = field(default_factory=list)  # [{'word': str, 'start': float, 'end': float, 'confidence': float}]
    segments: List[Dict] = field(default_factory=list)  # 문장/구 단위 세그먼트
    engine: str = "whisper"

@dataclass
class SyllableAlignment:
    """음절 정렬 결과"""
    syllable: str
    start_time: float
    end_time: float
    confidence: float
    word_context: str = ""
    phonetic_features: Dict = field(default_factory=dict)

class UniversalSTT:
    """
    다중 STT 엔진 통합 클래스
    """
    
    def __init__(self, engine: str = 'whisper', **kwargs):
        """
        Parameters:
        -----------
        engine : str
            STT 엔진 선택 ('whisper', 'google', 'azure', 'naver_clova', 'local_fallback')
        """
        self.engine = engine
        self.model = None
        self.config = kwargs
        
        # 각 엔진의 사용 가능 여부 확인
        self.available_engines = self._check_available_engines()
        
        # 선택된 엔진 초기화
        if engine in self.available_engines:
            self._initialize_engine(engine, **kwargs)
        else:
            print(f"⚠️ {engine} 사용 불가, fallback 모드로 전환")
            self.engine = 'local_fallback'
    
    def _check_available_engines(self) -> List[str]:
        """사용 가능한 STT 엔진 확인"""
        available = ['local_fallback']  # 항상 사용 가능
        
        # Whisper 확인
        try:
            import whisper
            available.append('whisper')
            print("✅ Whisper 사용 가능")
        except ImportError:
            print("❌ Whisper 미설치")
        
        # Google Cloud STT 확인
        try:
            from google.cloud import speech_v1
            available.append('google')
            print("✅ Google Cloud STT 사용 가능")
        except ImportError:
            print("❌ Google Cloud STT 미설치")
        
        # Azure 확인
        try:
            import azure.cognitiveservices.speech as speechsdk
            available.append('azure')
            print("✅ Azure Speech Services 사용 가능")
        except ImportError:
            print("❌ Azure Speech Services 미설치")
        
        # Naver CLOVA는 API 키가 있으면 사용 가능
        if self.config.get('naver_client_id') and self.config.get('naver_client_secret'):
            available.append('naver_clova')
            print("✅ Naver CLOVA STT 사용 가능")
        
        return available
    
    def _initialize_engine(self, engine: str, **kwargs):
        """엔진 초기화"""
        if engine == 'whisper':
            self._init_whisper(**kwargs)
        elif engine == 'google':
            self._init_google(**kwargs)
        elif engine == 'azure':
            self._init_azure(**kwargs)
        elif engine == 'naver_clova':
            self._init_naver_clova(**kwargs)
        elif engine == 'local_fallback':
            self._init_local_fallback()
    
    def _init_whisper(self, model_size: str = 'small', **kwargs):
        """OpenAI Whisper 초기화 (정밀도 개선을 위해 small 모델 사용)"""
        try:
            import whisper
            # 한국어 성능 향상을 위해 더 큰 모델 사용
            self.model = whisper.load_model(model_size)
            print(f"🎤 Whisper {model_size} 모델 로드 완료")
        except Exception as e:
            print(f"❌ Whisper 초기화 실패: {e}")
            self.engine = 'local_fallback'
    
    def _init_google(self, credentials_path: str = None, **kwargs):
        """Google Cloud Speech-to-Text 초기화"""
        try:
            from google.cloud import speech_v1
            
            if credentials_path and os.path.exists(credentials_path):
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            
            self.client = speech_v1.SpeechClient()
            print("🎤 Google Cloud STT 초기화 완료")
        except Exception as e:
            print(f"❌ Google STT 초기화 실패: {e}")
            self.engine = 'local_fallback'
    
    def _init_azure(self, subscription_key: str = None, region: str = None, **kwargs):
        """Azure Speech Services 초기화"""
        try:
            import azure.cognitiveservices.speech as speechsdk
            
            if not subscription_key or not region:
                raise ValueError("Azure 설정 정보 부족")
            
            speech_config = speechsdk.SpeechConfig(
                subscription=subscription_key,
                region=region
            )
            self.speech_config = speech_config
            print("🎤 Azure Speech Services 초기화 완료")
        except Exception as e:
            print(f"❌ Azure STT 초기화 실패: {e}")
            self.engine = 'local_fallback'
    
    def _init_naver_clova(self, naver_client_id: str = None, naver_client_secret: str = None, **kwargs):
        """Naver CLOVA Speech 초기화"""
        try:
            if not naver_client_id or not naver_client_secret:
                raise ValueError("Naver CLOVA 설정 정보 부족")
            
            self.clova_config = {
                'client_id': naver_client_id,
                'client_secret': naver_client_secret,
                'url': 'https://naveropenapi.apigw.ntruss.com/recog/v1/stt'
            }
            print("🎤 Naver CLOVA STT 초기화 완료")
        except Exception as e:
            print(f"❌ Naver CLOVA STT 초기화 실패: {e}")
            self.engine = 'local_fallback'
    
    def _init_local_fallback(self):
        """로컬 fallback 모드 초기화"""
        print("🎤 로컬 fallback 모드 활성화")
    
    def transcribe(self, audio_file: str, language: str = 'ko', 
                  return_timestamps: bool = True) -> TranscriptionResult:
        """
        음성 파일 전사
        
        Parameters:
        -----------
        audio_file : str
            입력 오디오 파일 경로
        language : str
            언어 코드 (예: 'ko', 'en')
        return_timestamps : bool
            타임스탬프 반환 여부
        
        Returns:
        --------
        TranscriptionResult : 전사 결과
        """
        print(f"🎤 {self.engine} 엔진으로 음성 인식 시작...")
        
        if self.engine == 'whisper':
            result = self._transcribe_whisper(audio_file, language, return_timestamps)
        elif self.engine == 'google':
            result = self._transcribe_google(audio_file, language, return_timestamps)
        elif self.engine == 'azure':
            result = self._transcribe_azure(audio_file, language, return_timestamps)
        elif self.engine == 'naver_clova':
            result = self._transcribe_naver_clova(audio_file, language)
        else:
            result = self._transcribe_local_fallback(audio_file)
        
        # 🔍 STT 결과 디버깅 정보 출력
        print(f"📝 STT 텍스트 결과: '{result.text}'")
        if result.words:
            print(f"🕐 Word-level 타임스탬프 ({len(result.words)}개):")
            for i, word in enumerate(result.words):
                if hasattr(word, 'word'):
                    word_text = word.word
                    start_time = word.start
                    end_time = word.end
                elif isinstance(word, dict):
                    word_text = word.get('word', '')
                    start_time = word.get('start', 0.0)
                    end_time = word.get('end', 0.0)
                else:
                    word_text = str(word)
                    start_time = 0.0
                    end_time = 0.0
                print(f"  {i+1:2d}. '{word_text}' [{start_time:.3f}s ~ {end_time:.3f}s] (지속: {end_time-start_time:.3f}s)")
        else:
            print("❌ Word-level 타임스탬프 없음")
        
        return result
    
    def _transcribe_whisper(self, audio_file: str, language: str = 'ko',
                           return_timestamps: bool = True) -> TranscriptionResult:
        """Whisper로 전사"""
        try:
            # 전사 옵션 설정
            options = {
                'word_timestamps': return_timestamps,
                'verbose': False,
                'language': language
            }
            
            # 전사 실행
            result = self.model.transcribe(audio_file, **options)
            
            # 단어 타임스탬프 추출
            words = []
            if return_timestamps and 'segments' in result:
                for segment in result['segments']:
                    if 'words' in segment:
                        for word_info in segment['words']:
                            words.append({
                                'word': word_info['word'].strip(),
                                'start': word_info['start'],
                                'end': word_info['end'],
                                'confidence': word_info.get('probability', 0.0)
                            })
            
            # 세그먼트 정보
            segments = []
            if 'segments' in result:
                for segment in result['segments']:
                    segments.append({
                        'id': segment['id'],
                        'text': segment['text'].strip(),
                        'start': segment['start'],
                        'end': segment['end'],
                        'confidence': segment.get('avg_logprob', 0.0)
                    })
            
            # 한국어 텍스트 필터링
            text = result['text'].strip()
            if language == 'ko':
                text = self._filter_korean_text(text)
            
            confidence = np.mean([s['confidence'] for s in segments]) if segments else 0.0
            
            return TranscriptionResult(
                text=text,
                language=result.get('language', language),
                confidence=confidence,
                words=words,
                segments=segments,
                engine='whisper'
            )
            
        except Exception as e:
            print(f"❌ Whisper 전사 실패: {e}")
            return self._transcribe_local_fallback(audio_file)
    
    def _transcribe_google(self, audio_file: str, language: str = 'ko-KR',
                         return_timestamps: bool = True) -> TranscriptionResult:
        """Google Cloud Speech-to-Text로 전사"""
        try:
            # 오디오 파일 읽기
            with open(audio_file, 'rb') as f:
                content = f.read()
            
            from google.cloud import speech_v1
            
            # 오디오 설정
            audio = speech_v1.RecognitionAudio(content=content)
            
            # 설정
            config = speech_v1.RecognitionConfig(
                encoding=speech_v1.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=language if '-' in language else f"{language}-KR",
                enable_word_time_offsets=return_timestamps,
                enable_automatic_punctuation=True,
                model='latest_long'
            )
            
            # 전사 실행
            response = self.client.recognize(config=config, audio=audio)
            
            # 결과 파싱
            text = ""
            words = []
            segments = []
            
            for result in response.results:
                text += result.alternatives[0].transcript + " "
                
                segments.append({
                    'text': result.alternatives[0].transcript,
                    'confidence': result.alternatives[0].confidence,
                    'start': 0,  # Google API는 세그먼트 타임스탬프 제공 안함
                    'end': 0
                })
                
                if return_timestamps and hasattr(result.alternatives[0], 'words'):
                    for word_info in result.alternatives[0].words:
                        words.append({
                            'word': word_info.word,
                            'start': word_info.start_time.total_seconds(),
                            'end': word_info.end_time.total_seconds(),
                            'confidence': result.alternatives[0].confidence
                        })
            
            confidence = np.mean([s['confidence'] for s in segments]) if segments else 0.0
            
            return TranscriptionResult(
                text=text.strip(),
                language=language,
                confidence=confidence,
                words=words,
                segments=segments,
                engine='google'
            )
            
        except Exception as e:
            print(f"❌ Google STT 전사 실패: {e}")
            return self._transcribe_local_fallback(audio_file)
    
    def _transcribe_azure(self, audio_file: str, language: str = 'ko-KR',
                         return_timestamps: bool = True) -> TranscriptionResult:
        """Azure Speech Services로 전사"""
        try:
            import azure.cognitiveservices.speech as speechsdk
            
            # 오디오 설정
            audio_config = speechsdk.audio.AudioConfig(filename=audio_file)
            
            # 음성 인식기 생성
            speech_recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.speech_config,
                audio_config=audio_config,
                language=language if '-' in language else f"{language}-KR"
            )
            
            # 전사 실행
            result = speech_recognizer.recognize_once()
            
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                return TranscriptionResult(
                    text=result.text,
                    language=language,
                    confidence=1.0,  # Azure는 confidence 점수 제공 안함
                    words=[],  # 단어 타임스탬프는 더 복잡한 설정 필요
                    segments=[{'text': result.text, 'confidence': 1.0}],
                    engine='azure'
                )
            else:
                raise Exception(f"Azure 인식 실패: {result.reason}")
                
        except Exception as e:
            print(f"❌ Azure STT 전사 실패: {e}")
            return self._transcribe_local_fallback(audio_file)
    
    def _transcribe_naver_clova(self, audio_file: str, language: str = 'ko') -> TranscriptionResult:
        """Naver CLOVA Speech로 전사"""
        try:
            # 오디오 파일 읽기
            with open(audio_file, 'rb') as f:
                data = f.read()
            
            # 헤더 설정
            headers = {
                'X-NCP-APIGW-API-KEY-ID': self.clova_config['client_id'],
                'X-NCP-APIGW-API-KEY': self.clova_config['client_secret'],
                'Content-Type': 'application/octet-stream'
            }
            
            # 파라미터
            params = {
                'lang': language.split('-')[0] if '-' in language else language
            }
            
            # API 호출
            response = requests.post(
                self.clova_config['url'],
                headers=headers,
                params=params,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result.get('text', '')
                
                return TranscriptionResult(
                    text=text,
                    language=language,
                    confidence=1.0,  # CLOVA는 confidence 제공 안함
                    words=[],  # CLOVA는 단어 타임스탬프 제공 안함
                    segments=[{'text': text, 'confidence': 1.0}],
                    engine='naver_clova'
                )
            else:
                raise Exception(f"CLOVA API Error: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Naver CLOVA STT 전사 실패: {e}")
            return self._transcribe_local_fallback(audio_file)
    
    def _transcribe_local_fallback(self, audio_file: str) -> TranscriptionResult:
        """로컬 fallback 전사 (파일명 기반)"""
        filename = Path(audio_file).stem
        
        # 파일명에서 한국어 추출
        korean_text = self._filter_korean_text(filename)
        
        if korean_text:
            print(f"📁 파일명 기반 추정: {korean_text}")
        else:
            korean_text = "텍스트 인식 실패"
            print("⚠️ 텍스트 추출 실패")
        
        return TranscriptionResult(
            text=korean_text,
            language='ko',
            confidence=0.5,  # 낮은 신뢰도
            words=[],
            segments=[{'text': korean_text, 'confidence': 0.5}],
            engine='local_fallback'
        )
    
    def _filter_korean_text(self, text: str) -> str:
        """한국어 텍스트만 필터링"""
        korean_chars = ''.join(c for c in text if self._is_korean(c) or c.isspace() or c in '.,!?')
        return korean_chars.strip()
    
    def _is_korean(self, char: str) -> bool:
        """한국어 문자인지 확인"""
        return 0xAC00 <= ord(char) <= 0xD7A3 if len(char) == 1 else False


class KoreanSyllableAligner:
    """
    한국어 특화 음절 정렬 시스템
    """
    
    def __init__(self):
        self.jamo_dict = self._build_jamo_dictionary()
    
    def _build_jamo_dictionary(self) -> Dict:
        """한국어 자모 사전 구축"""
        # 초성, 중성, 종성 정의
        initial = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 
                  'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
        medial = ['ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ',
                 'ㅙ', 'ㅚ', 'ㅛ', 'ㅜ', 'ㅝ', 'ㅞ', 'ㅟ', 'ㅠ', 'ㅡ', 'ㅢ', 'ㅣ']
        final = ['', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ',
                'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 
                'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
        
        return {
            'initial': initial,
            'medial': medial,
            'final': final
        }
    
    def decompose_syllable(self, syllable: str) -> Tuple[str, str, str]:
        """음절을 자모로 분해"""
        if not syllable or len(syllable) != 1:
            return ('', '', '')
        
        code = ord(syllable) - 0xAC00
        if code < 0:
            return ('', '', '')
        
        initial_idx = code // (21 * 28)
        medial_idx = (code % (21 * 28)) // 28
        final_idx = code % 28
        
        initial = self.jamo_dict['initial'][initial_idx] if initial_idx < len(self.jamo_dict['initial']) else ''
        medial = self.jamo_dict['medial'][medial_idx] if medial_idx < len(self.jamo_dict['medial']) else ''
        final = self.jamo_dict['final'][final_idx] if final_idx < len(self.jamo_dict['final']) else ''
        
        return (initial, medial, final)
    
    def align_syllables_with_timestamps(self, transcription: TranscriptionResult, 
                                      audio_file: str) -> List[SyllableAlignment]:
        """
        전사 결과를 음절 단위로 타임스탬프와 함께 정렬 (음성 시작점 자동 감지)
        """
        print(f"🎯 음절 정렬 시작: {transcription.text}")
        
        # 텍스트를 음절 단위로 분리
        syllables = list(transcription.text.replace(' ', ''))
        korean_syllables = [s for s in syllables if self._is_korean(s)]
        
        print(f"🔤 한국어 음절: {korean_syllables} ({len(korean_syllables)}개)")
        
        # 단어 타임스탬프가 있으면 활용
        if transcription.words:
            return self._align_with_word_timestamps(korean_syllables, transcription.words, audio_file)
        
        # 타임스탬프가 없으면 오디오 길이 기반 균등 분할
        return self._align_with_uniform_distribution(korean_syllables, audio_file)
    
    def _align_with_word_timestamps(self, syllables: List[str], 
                                  words: List[Dict], audio_file: str = None) -> List[SyllableAlignment]:
        """단어 타임스탬프를 활용한 음절 정렬 (실제 음성 시작점 보정)"""
        print(f"🔧 Word-level 타임스탬프 기반 음절 정렬 시작")
        
        # 🎯 실제 음성 시작점 감지 (Voice Activity Detection)
        actual_start = self._detect_voice_start_time(words, audio_file)
        if actual_start > 0:
            print(f"🎤 실제 음성 시작점 감지: {actual_start:.3f}s (무음 구간 제거)")
            # 모든 word 타임스탬프를 실제 시작점만큼 보정
            words = self._adjust_word_timestamps(words, actual_start)
        
        alignments = []
        syllable_idx = 0
        
        for word_idx, word_info in enumerate(words):
            # Word 구조 확인 및 적절한 접근
            if hasattr(word_info, 'word'):
                word = word_info.word.strip()
                start_time = word_info.start
                end_time = word_info.end
            elif isinstance(word_info, dict):
                word = word_info.get('word', '').strip()
                start_time = word_info.get('start', 0.0)
                end_time = word_info.get('end', 0.0)
            else:
                print(f"  ❌ 알 수 없는 word 구조: {type(word_info)}")
                continue
                
            word_syllables = [s for s in word if self._is_korean(s)]
            
            if not word_syllables:
                print(f"  ⏩ 단어 {word_idx+1}: '{word}' - 한국어 음절 없음, 건너뜀")
                continue
            
            # 단어 내 음절들의 시간 간격 계산
            word_duration = end_time - start_time
            syllable_duration = word_duration / len(word_syllables)
            
            print(f"  📍 단어 {word_idx+1}: '{word}' [{start_time:.3f}s ~ {end_time:.3f}s]")
            print(f"    📊 음절: {word_syllables} ({len(word_syllables)}개)")
            print(f"    ⏱️ 단어 지속시간: {word_duration:.3f}s → 음절당 {syllable_duration:.3f}s")
            
            for i, syllable in enumerate(word_syllables):
                if syllable_idx < len(syllables):
                    syl_start_time = start_time + i * syllable_duration
                    syl_end_time = syl_start_time + syllable_duration
                    
                    print(f"      🎯 음절 {syllable_idx+1}: '{syllable}' [{syl_start_time:.3f}s ~ {syl_end_time:.3f}s] (지속: {syl_end_time-syl_start_time:.3f}s)")
                    
                    # 자모 분해로 음성학적 특징 추출
                    initial, medial, final = self.decompose_syllable(syllable)
                    
                    alignments.append(SyllableAlignment(
                        syllable=syllable,
                        start_time=syl_start_time,  # 🔧 음절별 정확한 시작 시간
                        end_time=syl_end_time,      # 🔧 음절별 정확한 종료 시간
                        confidence=0.8,  # word_info에 confidence가 없을 수 있음
                        word_context=word,
                        phonetic_features={
                            'initial': initial,
                            'medial': medial,
                            'final': final
                        }
                    ))
                    
                    syllable_idx += 1
        
        return alignments
    
    def _detect_voice_start_time(self, words: List[Dict], audio_file: str = None) -> float:
        """실제 음성 시작 시간 감지 (오디오 분석 기반)"""
        if not words:
            return 0.0
        
        # 1차: STT word 타임스탬프 기반 감지
        first_word = words[0]
        if hasattr(first_word, 'start'):
            stt_start = first_word.start
        elif isinstance(first_word, dict):
            stt_start = first_word.get('start', 0.0)
        else:
            stt_start = 0.0
        
        # 2차: STT word 길이 분석으로 무음 구간 감지 (더 정확함)
        first_word = words[0]
        if hasattr(first_word, 'end'):
            first_duration = first_word.end - first_word.start
        elif isinstance(first_word, dict):
            first_duration = first_word.get('end', 0) - first_word.get('start', 0)
        else:
            first_duration = 0
            
        # 첫 번째 단어가 1.5초 이상 지속되면 무음 구간 포함으로 간주
        if first_duration > 1.5:
            estimated_silence = first_duration * 0.7  # 70%는 무음으로 추정
            print(f"🎤 STT 첫 단어 과도하게 길음 ({first_duration:.3f}s), 무음 구간 추정: {estimated_silence:.3f}s")
            return estimated_silence
        
        # 기존 로직: 첫 단어가 0.5초 이후 시작
        if stt_start > 0.5:
            print(f"🎤 STT 기반 무음 구간 감지: {stt_start:.3f}s")
            return stt_start
        
        # 3차: 실제 오디오 파일에서 음성 시작점 감지 (보조)
        if audio_file:
            try:
                audio_start = self._detect_audio_voice_start(audio_file)
                if audio_start > 0.1:  # 100ms 이상 차이날 때만 사용
                    print(f"🎤 오디오 분석 기반 음성 시작: {audio_start:.3f}s (STT: {stt_start:.3f}s)")
                    return audio_start
            except Exception as e:
                print(f"⚠️ 오디오 기반 감지 실패: {e}, STT 기준 사용")
        
        return stt_start
    
    def _detect_audio_voice_start(self, audio_file: str, 
                                energy_threshold: float = 0.001,
                                silence_duration: float = 0.05) -> float:
        """오디오 파일에서 실제 음성 시작점 감지"""
        import parselmouth as pm
        
        try:
            # 오디오 로드
            sound = pm.Sound(audio_file)
            
            # 에너지 분석 (RMS)
            window_size = 0.05  # 50ms 윈도우
            hop_size = 0.01     # 10ms 스텝
            
            duration = sound.get_total_duration()
            time_points = []
            energy_values = []
            
            current_time = 0
            while current_time + window_size <= duration:
                # 해당 구간의 에너지 계산
                start_sample = int(current_time * sound.sampling_frequency)
                end_sample = int((current_time + window_size) * sound.sampling_frequency)
                
                if end_sample <= len(sound.values):
                    window_samples = sound.values[start_sample:end_sample]
                    rms_energy = (sum(sample**2 for sample in window_samples) / len(window_samples))**0.5
                    
                    time_points.append(current_time)
                    energy_values.append(rms_energy)
                
                current_time += hop_size
            
            # 음성 시작점 찾기: energy_threshold를 초과하는 첫 지점
            for i, energy in enumerate(energy_values):
                if energy > energy_threshold:
                    voice_start = time_points[i]
                    
                    # 연속적인 음성 확인 (silence_duration만큼 지속되는지)
                    consecutive_voice = 0
                    for j in range(i, min(i + int(silence_duration / hop_size), len(energy_values))):
                        if energy_values[j] > energy_threshold:
                            consecutive_voice += hop_size
                        else:
                            break
                    
                    if consecutive_voice >= silence_duration:
                        return max(0, voice_start - 0.05)  # 50ms 여유 추가
            
            return 0.0  # 음성을 찾지 못한 경우
            
        except Exception as e:
            print(f"❌ 오디오 음성 감지 실패: {e}")
            return 0.0
    
    def _adjust_word_timestamps(self, words: List[Dict], voice_start: float) -> List[Dict]:
        """Word 타임스탬프를 실제 음성 시작점 기준으로 조정"""
        adjusted_words = []
        
        for word in words:
            if hasattr(word, 'start'):
                # Word 객체인 경우
                adjusted_word = type(word)(
                    word=word.word,
                    start=max(0, word.start - voice_start),
                    end=max(0, word.end - voice_start)
                )
                adjusted_words.append(adjusted_word)
            elif isinstance(word, dict):
                # Dict인 경우
                adjusted_word = word.copy()
                adjusted_word['start'] = max(0, word.get('start', 0) - voice_start)
                adjusted_word['end'] = max(0, word.get('end', 0) - voice_start)
                adjusted_words.append(adjusted_word)
        
        return adjusted_words
    
    def _align_with_uniform_distribution(self, syllables: List[str], 
                                       audio_file: str) -> List[SyllableAlignment]:
        """균등 분포 기반 음절 정렬"""
        # 오디오 길이 구하기
        try:
            sound = pm.Sound(audio_file)
            duration = sound.duration
        except:
            duration = 3.0  # 기본값
        
        alignments = []
        syllable_duration = duration / len(syllables) if syllables else 1.0
        
        for i, syllable in enumerate(syllables):
            start_time = i * syllable_duration
            end_time = (i + 1) * syllable_duration
            
            # 자모 분해
            initial, medial, final = self.decompose_syllable(syllable)
            
            alignments.append(SyllableAlignment(
                syllable=syllable,
                start_time=start_time,
                end_time=end_time,
                confidence=0.6,  # 낮은 신뢰도 (타임스탬프 없음)
                word_context="",
                phonetic_features={
                    'initial': initial,
                    'medial': medial,
                    'final': final
                }
            ))
        
        return alignments
    
    def _is_korean(self, char: str) -> bool:
        """한국어 문자인지 확인"""
        return 0xAC00 <= ord(char) <= 0xD7A3 if len(char) == 1 else False


class AdvancedSTTProcessor:
    """
    고급 STT 처리 시스템 (기존 STTProcessor 확장)
    """
    
    def __init__(self, preferred_engine: str = 'whisper', **engine_configs):
        """
        Parameters:
        -----------
        preferred_engine : str
            우선 사용할 STT 엔진
        engine_configs : dict
            각 엔진별 설정 정보
        """
        self.stt = UniversalSTT(preferred_engine, **engine_configs)
        self.syllable_aligner = KoreanSyllableAligner()
        
        # 신뢰도 임계값
        self.confidence_threshold = 0.7
        
        print(f"🎯 고급 STT 시스템 초기화 완료 (엔진: {self.stt.engine})")
    
    def process_audio_with_confidence(self, audio_file: str, 
                                    target_text: str = "") -> Dict:
        """
        신뢰도 평가와 함께 오디오 처리
        """
        print(f"🎤 고급 STT 처리 시작: {Path(audio_file).name}")
        
        # STT 전사
        transcription = self.stt.transcribe(audio_file, language='ko', return_timestamps=True)
        
        # 목표 텍스트가 있으면 일치도 검사
        if target_text:
            similarity = self._calculate_text_similarity(transcription.text, target_text)
            print(f"📊 텍스트 일치도: {similarity:.2%}")
            
            # 일치도가 낮으면 목표 텍스트 사용
            if similarity < 0.7:
                print(f"⚠️ 일치도 낮음, 목표 텍스트 사용: {target_text}")
                transcription.text = target_text
                transcription.confidence = 0.8  # 수동 입력 신뢰도
        
        # 음절 정렬
        syllable_alignments = self.syllable_aligner.align_syllables_with_timestamps(
            transcription, audio_file
        )
        
        # 신뢰도 평가
        overall_confidence = self._evaluate_overall_confidence(transcription, syllable_alignments)
        
        return {
            'transcription': transcription.text,
            'syllables': [
                {
                    'label': sa.syllable,
                    'start': sa.start_time,
                    'end': sa.end_time,
                    'confidence': sa.confidence,
                    'phonetic_features': sa.phonetic_features
                }
                for sa in syllable_alignments
            ],
            'confidence': overall_confidence,
            'engine': transcription.engine,
            'word_timestamps': transcription.words,
            'quality_metrics': {
                'syllable_count': len(syllable_alignments),
                'avg_syllable_confidence': np.mean([sa.confidence for sa in syllable_alignments]),
                'has_word_timestamps': len(transcription.words) > 0
            }
        }
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """한국어 특화 텍스트 유사도 계산 (개선된 구현)"""
        # 한국어 특화 전처리
        clean1 = self._preprocess_korean_text(text1)
        clean2 = self._preprocess_korean_text(text2)
        
        if not clean1 or not clean2:
            return 0.0
        
        # 1. 음절 단위 유사도 (가중치: 0.6)
        syllable_similarity = self._calculate_syllable_similarity(clean1, clean2)
        
        # 2. 자모 단위 유사도 (가중치: 0.3)
        jamo_similarity = self._calculate_jamo_similarity(clean1, clean2)
        
        # 3. 길이 유사도 (가중치: 0.1)
        len1, len2 = len(clean1), len(clean2)
        length_similarity = 1.0 - abs(len1 - len2) / max(len1, len2)
        
        # 가중 평균
        overall_similarity = (
            0.6 * syllable_similarity +
            0.3 * jamo_similarity +
            0.1 * length_similarity
        )
        
        return min(1.0, overall_similarity)
    
    def _preprocess_korean_text(self, text: str) -> str:
        """한국어 텍스트 전처리"""
        import re
        
        # 특수문자, 공백, 구두점 제거
        cleaned = re.sub(r'[^\uAC00-\uD7A3\u1100-\u11FF\u3130-\u318F]', '', text)
        
        # 자음, 모음 단독 제거 (완성형 한글만 유지)
        korean_syllables = re.findall(r'[\uAC00-\uD7A3]', cleaned)
        
        return ''.join(korean_syllables)
    
    def _calculate_syllable_similarity(self, text1: str, text2: str) -> float:
        """음절 단위 유사도 계산"""
        if not text1 or not text2:
            return 0.0
        
        # 동적 프로그래밍으로 최장 공통 부분 시퀀스 계산
        len1, len2 = len(text1), len(text2)
        dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                if text1[i-1] == text2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        
        lcs_length = dp[len1][len2]
        return lcs_length / max(len1, len2)
    
    def _calculate_jamo_similarity(self, text1: str, text2: str) -> float:
        """자모 단위 유사도 계산"""
        try:
            # 각 음절을 자모로 분해
            jamo1 = []
            jamo2 = []
            
            for char in text1:
                if 0xAC00 <= ord(char) <= 0xD7A3:  # 완성형 한글
                    initial, medial, final = self._decompose_hangul(char)
                    jamo1.extend([initial, medial, final] if final else [initial, medial])
            
            for char in text2:
                if 0xAC00 <= ord(char) <= 0xD7A3:
                    initial, medial, final = self._decompose_hangul(char)
                    jamo2.extend([initial, medial, final] if final else [initial, medial])
            
            if not jamo1 or not jamo2:
                return 0.0
            
            # 자모 매칭 계산
            matching = sum(1 for j1, j2 in zip(jamo1, jamo2) if j1 == j2)
            return matching / max(len(jamo1), len(jamo2))
            
        except Exception:
            return 0.0
    
    def _decompose_hangul(self, char: str) -> tuple:
        """한글 음절을 자모로 분해"""
        if len(char) != 1 or not (0xAC00 <= ord(char) <= 0xD7A3):
            return ('', '', '')
        
        # 한글 유니코드 분해
        code = ord(char) - 0xAC00
        
        # 초성, 중성, 종성 인덱스
        initial_idx = code // (21 * 28)
        medial_idx = (code % (21 * 28)) // 28
        final_idx = code % 28
        
        # 자모 테이블
        initials = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
        medials = ['ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ', 'ㅙ', 'ㅚ', 'ㅛ', 'ㅜ', 'ㅝ', 'ㅞ', 'ㅟ', 'ㅠ', 'ㅡ', 'ㅢ', 'ㅣ']
        finals = ['', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
        
        initial = initials[initial_idx]
        medial = medials[medial_idx]
        final = finals[final_idx]
        
        return (initial, medial, final)
    
    def _evaluate_overall_confidence(self, transcription: TranscriptionResult, 
                                   syllables: List[SyllableAlignment]) -> float:
        """전체 신뢰도 평가"""
        factors = []
        
        # STT 엔진별 기본 신뢰도
        engine_confidence = {
            'whisper': 0.85,
            'google': 0.90,
            'azure': 0.88,
            'naver_clova': 0.80,
            'local_fallback': 0.50
        }
        factors.append(engine_confidence.get(transcription.engine, 0.60))
        
        # 전사 신뢰도
        factors.append(transcription.confidence)
        
        # 음절 정렬 신뢰도
        if syllables:
            syllable_confidence = np.mean([s.confidence for s in syllables])
            factors.append(syllable_confidence)
        
        # 타임스탬프 존재 여부
        if transcription.words:
            factors.append(0.9)  # 타임스탬프 있으면 보너스
        else:
            factors.append(0.6)
        
        return np.mean(factors)
    
    def get_engine_status(self) -> Dict:
        """STT 엔진 상태 정보"""
        return {
            'current_engine': self.stt.engine,
            'available_engines': self.stt.available_engines,
            'confidence_threshold': self.confidence_threshold
        }


# 사용 예시
if __name__ == "__main__":
    # 고급 STT 프로세서 초기화
    processor = AdvancedSTTProcessor(
        preferred_engine='whisper',
        model_size='base'
    )
    
    # 테스트 파일 처리
    test_file = "static/reference_files/낭독문장.wav"
    if Path(test_file).exists():
        result = processor.process_audio_with_confidence(
            test_file, 
            target_text="하나도 놓치지 않고 열심히 보고 있습니다"
        )
        print(f"🎯 처리 결과: {result}")