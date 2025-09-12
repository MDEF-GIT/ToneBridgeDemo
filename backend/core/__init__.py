"""
ToneBridge 핵심 처리 모듈
오디오 정규화, 분석, 향상, 한국어 최적화 등 핵심 기능 제공
"""

# 오디오 정규화
from .audio_normalization import (AudioNormalizer, TextGridSynchronizer,
                                  AutomationProcessor)

# 음성 분석
from .audio_analysis import (PitchAnalyzer, FormantAnalyzer, SyllableSegmenter,
                             VoiceAnalyzer, PitchPoint, FormantPoint, Syllable,
                             Gender, RhythmAnalyzer, PronunciationScorer,
                             VADProcessor, IntensityAnalyzer, SpectralAnalyzer)

# 음질 향상
from .audio_enhancement import (NoiseReducer, AudioEnhancer, EQProcessor,
                                CompressorProcessor, AudioQualityEnhancer)

# 한국어 음성 최적화
from .korean_audio_optimizer import (KoreanTextProcessor, KoreanSpeechAnalyzer,
                                     KoreanAudioOptimizer,
                                     KoreanProsodyGenerator, KoreanPhonemes,
                                     KoreanSyllable, TonePattern)

# STT 처리 모듈들
from .advanced_stt_processor import AdvancedSTTProcessor, DualGPUProcessor
from .multi_engine_stt import MultiEngineSTT
from .ultimate_stt_system import UltimateSTTSystem

# 품질 검증
from .quality_validator import QualityValidator

# GPU Manager
from .gpu_manager import gpu_manager


__version__ = "1.0.0"

__all__ = [
    # 오디오 정규화
    "AudioNormalizer",
    "TextGridSynchronizer",
    "AutomationProcessor",

    # 음성 분석
    "PitchAnalyzer",
    "FormantAnalyzer",
    "SyllableSegmenter",
    "VoiceAnalyzer",
    "PitchPoint",
    "FormantPoint",
    "Syllable",
    "Gender",
    "RhythmAnalyzer",
    "PronunciationScorer",
    "VADProcessor",
    "IntensityAnalyzer",
    "SpectralAnalyzer",

    # 음질 향상
    "NoiseReducer",
    "AudioEnhancer",
    "EQProcessor",
    "CompressorProcessor",
    "AudioQualityEnhancer",

    # 한국어 음성 최적화
    "KoreanTextProcessor",
    "KoreanSpeechAnalyzer",
    "KoreanAudioOptimizer",
    "KoreanProsodyGenerator",
    "KoreanPhonemes",
    "KoreanSyllable",
    "TonePattern",

    # STT 처리 모듈들
    "AdvancedSTTProcessor",
    "gpu_manager",  # 추가
    "DualGPUProcessor",  # 추가
    "MultiEngineSTT",
    "UltimateSTTSystem",

    # 품질 검증
    "QualityValidator"
]

# 모듈 초기화 시 로깅
import logging

logger = logging.getLogger(__name__)
logger.debug("Core 모듈 초기화 완료")
