"""
통합 STT 엔진 - 기존 STT 기능들을 통합하여 일관된 인터페이스 제공
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Optional

# 기존 모듈 임포트 (하위 호환성)
sys.path.append(str(Path(__file__).parent.parent.parent))

try:
    from advanced_stt_processor import AdvancedSTTProcessor, UniversalSTT
    ADVANCED_STT_AVAILABLE = True
except ImportError:
    ADVANCED_STT_AVAILABLE = False

from ..models import TranscriptionResult, WordAlignment

class UnifiedSTTEngine:
    """
    통합 STT 엔진 - 모든 차트에서 동일한 STT 사용
    기존 AdvancedSTTProcessor 기능을 통합하여 제공
    """
    
    def __init__(self, preferred_engine: str = 'whisper', shared_processor=None):
        self.preferred_engine = preferred_engine
        self.advanced_stt = None
        self.universal_stt = None
        
        # 🚀 성능 최적화: 전역 STT 인스턴스 재사용
        if shared_processor:
            print("🔄 기존 STT 인스턴스 재사용")
            self.advanced_stt = shared_processor
            self.universal_stt = shared_processor.stt if hasattr(shared_processor, 'stt') else shared_processor
        else:
            # 기존 STT 시스템 초기화
            self._initialize_stt_engines()
    
    def _initialize_stt_engines(self):
        """기존 STT 엔진들 초기화"""
        try:
            if ADVANCED_STT_AVAILABLE:
                print(f"🔧 통합 STT: AdvancedSTTProcessor 초기화 중...")
                self.advanced_stt = AdvancedSTTProcessor(
                    preferred_engine=self.preferred_engine
                )
                self.universal_stt = self.advanced_stt.stt
                print(f"✅ 통합 STT: {self.preferred_engine} 엔진 활성화")
            else:
                print("⚠️ 통합 STT: Advanced STT 비활성화")
        except Exception as e:
            print(f"❌ 통합 STT 초기화 실패: {e}")
            self.advanced_stt = None
            self.universal_stt = None
    
    def transcribe(self, audio_file: str, language: str = 'ko') -> TranscriptionResult:
        """기본 전사 (타임스탬프 없음)"""
        if not self.universal_stt:
            return TranscriptionResult(
                text="",
                confidence=0.0,
                words=[],
                engine='none'
            )
        
        try:
            result = self.universal_stt.transcribe(audio_file, language=language)
            
            # 기존 결과를 통합 모델로 변환
            return TranscriptionResult(
                text=result.text,
                confidence=result.confidence,
                words=[],  # 기본 전사에는 단어 정렬 없음
                engine=result.engine,
                language=language
            )
        except Exception as e:
            print(f"❌ STT 전사 실패: {e}")
            return TranscriptionResult(
                text="",
                confidence=0.0,
                words=[],
                engine=self.preferred_engine
            )
    
    def transcribe_with_timestamps(self, audio_file: str, language: str = 'ko') -> TranscriptionResult:
        """타임스탬프 포함 전사 - 기존 기능 유지"""
        if not self.universal_stt:
            return TranscriptionResult(
                text="",
                confidence=0.0,
                words=[],
                engine='none'
            )
        
        try:
            result = self.universal_stt.transcribe(
                audio_file, 
                language=language,
                return_timestamps=True
            )
            
            # 단어 정렬 데이터 변환
            word_alignments = []
            if hasattr(result, 'words') and result.words:
                for word_info in result.words:
                    if hasattr(word_info, 'word'):
                        word_alignments.append(WordAlignment(
                            word=word_info.word,
                            start=word_info.start,
                            end=word_info.end,
                            confidence=getattr(word_info, 'confidence', 0.8)
                        ))
                    elif isinstance(word_info, dict):
                        word_alignments.append(WordAlignment(
                            word=word_info.get('word', ''),
                            start=word_info.get('start', 0.0),
                            end=word_info.get('end', 0.0),
                            confidence=word_info.get('confidence', 0.8)
                        ))
            
            return TranscriptionResult(
                text=result.text,
                confidence=result.confidence,
                words=word_alignments,
                segments=getattr(result, 'segments', []),
                engine=result.engine,
                language=language
            )
            
        except Exception as e:
            print(f"❌ STT 타임스탬프 전사 실패: {e}")
            return TranscriptionResult(
                text="",
                confidence=0.0,
                words=[],
                engine=self.preferred_engine
            )
    
    def is_available(self) -> bool:
        """STT 엔진 사용 가능 여부"""
        return self.universal_stt is not None
    
    def get_engine_info(self) -> Dict:
        """STT 엔진 정보"""
        return {
            'engine': self.preferred_engine,
            'available': self.is_available(),
            'advanced_stt': self.advanced_stt is not None
        }