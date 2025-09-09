"""
ToneBridge 공통 데이터 모델

기존 데이터 구조와 호환되는 통합 모델
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import json

@dataclass
class SyllableSegment:
    """음절 분절 데이터 - 기존 구조와 호환"""
    label: str
    start: float
    end: float
    duration: float = None
    confidence: float = 0.8
    phonetic_features: Dict = None
    
    def __post_init__(self):
        if self.duration is None:
            self.duration = self.end - self.start
        if self.phonetic_features is None:
            self.phonetic_features = {}
    
    def to_dict(self) -> Dict:
        """기존 딕셔너리 형태로 변환 - API 호환성"""
        return {
            'label': self.label,
            'start': self.start,
            'end': self.end,
            'duration': self.duration,
            'confidence': self.confidence
        }

@dataclass
class WordAlignment:
    """단어 정렬 데이터"""
    word: str
    start: float
    end: float
    confidence: float = 0.8

@dataclass
class TranscriptionResult:
    """STT 결과 데이터 - 기존 구조 호환"""
    text: str
    confidence: float
    words: List[WordAlignment]
    segments: List[Dict] = None
    engine: str = 'whisper'
    language: str = 'ko'
    
    def __post_init__(self):
        if self.segments is None:
            self.segments = []

@dataclass
class PitchAnalysis:
    """피치 분석 결과"""
    pitch_points: List[Dict]
    syllable_pitches: List[Dict]
    statistics: Dict
    
@dataclass
class ProcessingResult:
    """통합 처리 결과 - 기존 API 응답과 호환"""
    success: bool
    segments: List[SyllableSegment]
    textgrid_content: str = ""
    textgrid_path: str = ""
    pitch_analysis: PitchAnalysis = None
    transcription: str = ""
    duration: float = 0.0
    file_type: str = ""
    error: str = ""
    
    def to_legacy_dict(self) -> Dict:
        """기존 API 응답 형태로 변환"""
        return {
            'success': self.success,
            'syllables': [seg.to_dict() for seg in self.segments],
            'transcription': self.transcription,
            'duration': self.duration,
            'textgrid_path': self.textgrid_path,
            'error': self.error
        }