"""
한국어 특화 통합 음절 분절기
기존 분절 알고리즘들을 통합하여 일관된 결과 제공
"""

import sys
from pathlib import Path
from typing import List, Optional

# 기존 모듈 임포트 (하위 호환성)
sys.path.append(str(Path(__file__).parent.parent.parent))

try:
    from audio_analysis import STTBasedSegmenter
    from advanced_stt_processor import KoreanSyllableAligner
    SEGMENTATION_AVAILABLE = True
except ImportError:
    SEGMENTATION_AVAILABLE = False

try:
    import parselmouth as pm
    PARSELMOUTH_AVAILABLE = True
except ImportError:
    PARSELMOUTH_AVAILABLE = False

from ..models import SyllableSegment, TranscriptionResult
from ..stt.universal_stt import UnifiedSTTEngine

class KoreanSyllableSegmenter:
    """
    한국어 특화 통합 음절 분절기
    기존 분절 알고리즘들을 통합하여 모든 차트에서 동일한 품질 제공
    """
    
    def __init__(self, shared_stt_processor=None):
        # 🚀 성능 최적화: 전역 STT 인스턴스 재사용
        if shared_stt_processor:
            self.stt_engine = UnifiedSTTEngine(shared_processor=shared_stt_processor)
        else:
            self.stt_engine = UnifiedSTTEngine()
            
        self.stt_segmenter = None
        self.korean_aligner = None
        self.shared_stt_processor = shared_stt_processor
        
        self._initialize_segmenters()
    
    def _initialize_segmenters(self):
        """기존 분절기들 초기화"""
        try:
            if SEGMENTATION_AVAILABLE:
                # 🚀 성능 최적화: 전역 STT 인스턴스 재사용
                if self.shared_stt_processor:
                    self.stt_segmenter = STTBasedSegmenter(shared_stt_processor=self.shared_stt_processor)
                else:
                    self.stt_segmenter = STTBasedSegmenter()
                    
                
                # KoreanSyllableAligner 초기화
                if self.stt_engine.advanced_stt:
                    self.korean_aligner = self.stt_engine.advanced_stt.syllable_aligner
        except Exception as e:
            print(f"❌ 통합 분절기 초기화 실패: {e}")
    
    def segment(self, audio_file: str, text_hint: str = None) -> List[SyllableSegment]:
        """
        통합 음절 분절 - 모든 차트에서 동일한 품질
        
        Args:
            audio_file: 음성 파일 경로
            text_hint: 텍스트 힌트 (선택사항)
        
        Returns:
            일관된 음절 분절 결과
        """
        print(f"🎯 통합 분절 시작: {Path(audio_file).name}")
        
        # 1. 텍스트 힌트가 있으면 사용, 없으면 STT
        transcription_text = text_hint
        if not transcription_text:
            transcription = self.stt_engine.transcribe_with_timestamps(audio_file)
            transcription_text = transcription.text
        
        if not transcription_text or transcription_text.strip() == "":
            print("⚠️ 텍스트가 없어 기본값 사용")
            transcription_text = "반가워요"  # 안전한 기본값
        
        print(f"📝 분절 대상 텍스트: '{transcription_text}'")
        
        # 2. 고급 분절 시도 (STT 기반)
        segments = self._try_advanced_segmentation(audio_file, transcription_text)
        
        # 3. 결과 검증 - 실패시 에러 발생
        if not segments or len(segments) == 0:
            raise Exception("고급 STT 분절 실패 - 기본 분절은 사용하지 않음")
        
        print(f"✅ 통합 분절 완료: {len(segments)}개 음절")
        return segments
    
    def _try_advanced_segmentation(self, audio_file: str, text: str) -> List[SyllableSegment]:
        """고급 분절 시도 (STT + 한국어 언어학적 보정)"""
        if not self.stt_segmenter:
            return []
        
        try:
            print("🚀 고급 분절 시도: STT + 언어학적 보정")
            
            # STT 기반 분절 시도
            result_segments = self.stt_segmenter.segment_from_audio_file(audio_file, text)
            
            # 결과를 통합 모델로 변환
            segments = []
            for seg in result_segments:
                segments.append(SyllableSegment(
                    label=seg.label,
                    start=seg.start,
                    end=seg.end,
                    duration=seg.duration,
                    confidence=getattr(seg, 'confidence', 0.8)
                ))
            
            # 목표 음절 수와 비교 검증
            target_syllables = list(text.replace(' ', ''))
            if len(segments) == len(target_syllables):
                print(f"✅ 고급 분절 성공: {len(segments)}개 음절")
                return segments
            else:
                print(f"⚠️ 음절 수 불일치 ({len(segments)} != {len(target_syllables)})")
                return []
                
        except Exception as e:
            print(f"❌ 고급 분절 실패: {e}")
            return []
    
    
    def is_available(self) -> bool:
        """분절기 사용 가능 여부 - STT 분절기만 확인"""
        return self.stt_segmenter is not None