"""
ToneBridge Core 라이브러리
피치 분석, 음절 분절, TextGrid 생성 등 핵심 기능 통합
"""

# 모델
from .models import (AudioSegment, PitchData, TextGridData, AnalysisResult,
                     ProcessingStatus)

# 분석 모듈
from .analysis import (PitchAnalyzer, FormantAnalyzer, SpectralAnalyzer)

# 파이프라인
from .pipeline import (VoiceProcessor, ProcessingPipeline, PipelineConfig)

# 분절 모듈
from .segmentation import (KoreanSegmenter, SyllableSegment,
                           SegmentationResult)

# STT 모듈
from .stt import (UniversalSTT, STTConfig as UniversalSTTConfig, STTResult as
                  UniversalSTTResult)

# TextGrid 모듈
from .textgrid import (TextGridGenerator, TextGridTier, TextGridInterval,
                       TextGridPoint)

__version__ = "1.0.0"
__author__ = "ToneBridge Team"

__all__ = [
    # 모델
    "AudioSegment",
    "PitchData",
    "TextGridData",
    "AnalysisResult",
    "ProcessingStatus",

    # 분석
    "PitchAnalyzer",
    "FormantAnalyzer",
    "SpectralAnalyzer",

    # 파이프라인
    "VoiceProcessor",
    "ProcessingPipeline",
    "PipelineConfig",

    # 분절
    "KoreanSegmenter",
    "SyllableSegment",
    "SegmentationResult",

    # STT
    "UniversalSTT",
    "UniversalSTTConfig",
    "UniversalSTTResult",

    # TextGrid
    "TextGridGenerator",
    "TextGridTier",
    "TextGridInterval",
    "TextGridPoint"
]

# 모듈 초기화 시 로깅
import logging

logger = logging.getLogger(__name__)
logger.debug("ToneBridge Core 라이브러리 초기화 완료")
