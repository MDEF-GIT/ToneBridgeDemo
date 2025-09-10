"""
ToneBridge Core 데이터 모델
시스템 전체에서 사용되는 데이터 구조 정의
"""
from typing import Tuple, List, Optional, Dict, Any, Union
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from enum import Enum
import json
import numpy as np

# ========== 열거형 정의 ==========


class ProcessingStatus(Enum):
    """처리 상태"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AudioFormat(Enum):
    """오디오 포맷"""
    WAV = "wav"
    MP3 = "mp3"
    M4A = "m4a"
    FLAC = "flac"
    OGG = "ogg"
    WEBM = "webm"


class Language(Enum):
    """지원 언어"""
    KOREAN = "ko"
    ENGLISH = "en"
    JAPANESE = "ja"
    CHINESE = "zh"


class Gender(Enum):
    """성별"""
    MALE = "male"
    FEMALE = "female"
    CHILD = "child"
    UNKNOWN = "unknown"


# ========== 기본 데이터 클래스 ==========


@dataclass
class TimeInterval:
    """시간 구간"""
    start: float
    end: float

    @property
    def duration(self) -> float:
        """구간 길이"""
        return self.end - self.start

    @property
    def center(self) -> float:
        """구간 중심"""
        return (self.start + self.end) / 2

    def contains(self, time: float) -> bool:
        """시간이 구간에 포함되는지 확인"""
        return self.start <= time <= self.end

    def overlaps(self, other: 'TimeInterval') -> bool:
        """다른 구간과 겹치는지 확인"""
        return not (self.end <= other.start or other.end <= self.start)

    def to_dict(self) -> Dict[str, float]:
        return {
            'start': self.start,
            'end': self.end,
            'duration': self.duration
        }


@dataclass
class AudioMetadata:
    """오디오 메타데이터"""
    file_path: str
    format: AudioFormat
    duration: float
    sample_rate: int
    channels: int
    bit_depth: Optional[int] = None
    file_size: Optional[int] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'file_path': self.file_path,
            'format': self.format.value,
            'duration': self.duration,
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'bit_depth': self.bit_depth,
            'file_size': self.file_size,
            'created_at':
            self.created_at.isoformat() if self.created_at else None
        }


# ========== 오디오 세그먼트 ==========


@dataclass
class AudioSegment:
    """오디오 세그먼트"""
    id: str
    interval: TimeInterval
    text: Optional[str] = None
    confidence: float = 0.0
    speaker_id: Optional[str] = None
    language: Optional[Language] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def start(self) -> float:
        return self.interval.start

    @property
    def end(self) -> float:
        return self.interval.end

    @property
    def duration(self) -> float:
        return self.interval.duration

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'start': self.start,
            'end': self.end,
            'duration': self.duration,
            'text': self.text,
            'confidence': self.confidence,
            'speaker_id': self.speaker_id,
            'language': self.language.value if self.language else None,
            'metadata': self.metadata
        }


# ========== 피치 데이터 ==========


@dataclass
class PitchPoint:
    """피치 포인트"""
    time: float
    frequency: float
    strength: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            'time': self.time,
            'frequency': self.frequency,
            'strength': self.strength
        }


@dataclass
class PitchData:
    """피치 데이터"""
    points: List[PitchPoint]
    time_step: float
    min_pitch: float
    max_pitch: float
    mean_pitch: Optional[float] = None
    std_pitch: Optional[float] = None

    def __post_init__(self):
        """통계 계산"""
        if self.points:
            frequencies = [p.frequency for p in self.points if p.frequency > 0]
            if frequencies:
                self.mean_pitch = float(np.mean(frequencies))
                self.std_pitch = float(np.std(frequencies))

    @property
    def pitch_range(self) -> float:
        """피치 범위"""
        if not self.points:
            return 0.0
        frequencies = [p.frequency for p in self.points if p.frequency > 0]
        if not frequencies:
            return 0.0
        return max(frequencies) - min(frequencies)

    def get_pitch_at_time(self, time: float) -> Optional[float]:
        """특정 시간의 피치 값"""
        for point in self.points:
            if abs(point.time - time) < self.time_step / 2:
                return point.frequency
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'points': [p.to_dict() for p in self.points],
            'time_step': self.time_step,
            'min_pitch': self.min_pitch,
            'max_pitch': self.max_pitch,
            'mean_pitch': self.mean_pitch,
            'std_pitch': self.std_pitch,
            'pitch_range': self.pitch_range
        }


# ========== TextGrid 데이터 ==========


@dataclass
class TextGridInterval:
    """TextGrid 구간"""
    xmin: float
    xmax: float
    text: str

    @property
    def duration(self) -> float:
        return self.xmax - self.xmin

    def to_dict(self) -> Dict[str, Any]:
        return {
            'xmin': self.xmin,
            'xmax': self.xmax,
            'text': self.text,
            'duration': self.duration
        }


@dataclass
class TextGridPoint:
    """TextGrid 포인트"""
    time: float
    mark: str

    def to_dict(self) -> Dict[str, Any]:
        return {'time': self.time, 'mark': self.mark}


@dataclass
class TextGridTier:
    """TextGrid 티어"""
    name: str
    tier_type: str  # "IntervalTier" or "TextTier"
    xmin: float
    xmax: float
    intervals: Optional[List[TextGridInterval]] = None
    points: Optional[List[TextGridPoint]] = None

    def __post_init__(self):
        """티어 타입에 따라 초기화"""
        if self.tier_type == "IntervalTier":
            if self.intervals is None:
                self.intervals = []
            self.points = None
        else:  # TextTier
            if self.points is None:
                self.points = []
            self.intervals = None

    @property
    def size(self) -> int:
        """티어 크기"""
        if self.tier_type == "IntervalTier":
            return len(self.intervals) if self.intervals else 0
        else:
            return len(self.points) if self.points else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name':
            self.name,
            'tier_type':
            self.tier_type,
            'xmin':
            self.xmin,
            'xmax':
            self.xmax,
            'size':
            self.size,
            'intervals':
            [i.to_dict() for i in self.intervals] if self.intervals else None,
            'points':
            [p.to_dict() for p in self.points] if self.points else None
        }


@dataclass
class TextGridData:
    """TextGrid 데이터"""
    xmin: float
    xmax: float
    tiers: List[TextGridTier]
    file_type: str = "ooTextFile"
    object_class: str = "TextGrid"

    @property
    def duration(self) -> float:
        """전체 길이"""
        return self.xmax - self.xmin

    @property
    def tier_count(self) -> int:
        """티어 개수"""
        return len(self.tiers)

    def get_tier(self, name: str) -> Optional[TextGridTier]:
        """이름으로 티어 찾기"""
        for tier in self.tiers:
            if tier.name == name:
                return tier
        return None

    def add_tier(self, tier: TextGridTier):
        """티어 추가"""
        self.tiers.append(tier)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'file_type': self.file_type,
            'object_class': self.object_class,
            'xmin': self.xmin,
            'xmax': self.xmax,
            'duration': self.duration,
            'tier_count': self.tier_count,
            'tiers': [t.to_dict() for t in self.tiers]
        }

    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ========== 분석 결과 ==========


@dataclass
class SpectralFeatures:
    """스펙트럼 특징"""
    spectral_centroid: float
    spectral_bandwidth: float
    spectral_rolloff: float
    zero_crossing_rate: float
    mfcc: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'spectral_centroid': self.spectral_centroid,
            'spectral_bandwidth': self.spectral_bandwidth,
            'spectral_rolloff': self.spectral_rolloff,
            'zero_crossing_rate': self.zero_crossing_rate,
            'mfcc': self.mfcc
        }


@dataclass
class FormantData:
    """포먼트 데이터"""
    time: float
    f1: float
    f2: float
    f3: float
    f4: Optional[float] = None

    def to_dict(self) -> Dict[str, float]:
        result = {
            'time': self.time,
            'f1': self.f1,
            'f2': self.f2,
            'f3': self.f3
        }
        if self.f4 is not None:
            result['f4'] = self.f4
        return result


@dataclass
class AnalysisResult:
    """종합 분석 결과"""
    audio_metadata: AudioMetadata
    segments: List[AudioSegment]
    pitch_data: Optional[PitchData] = None
    formants: Optional[List[FormantData]] = None
    spectral_features: Optional[SpectralFeatures] = None
    textgrid_data: Optional[TextGridData] = None
    transcription: Optional[str] = None
    language: Optional[Language] = None
    gender: Optional[Gender] = None
    processing_time: float = 0.0
    status: ProcessingStatus = ProcessingStatus.PENDING
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'audio_metadata':
            self.audio_metadata.to_dict(),
            'segments': [s.to_dict() for s in self.segments],
            'pitch_data':
            self.pitch_data.to_dict() if self.pitch_data else None,
            'formants':
            [f.to_dict() for f in self.formants] if self.formants else None,
            'spectral_features':
            self.spectral_features.to_dict()
            if self.spectral_features else None,
            'textgrid_data':
            self.textgrid_data.to_dict() if self.textgrid_data else None,
            'transcription':
            self.transcription,
            'language':
            self.language.value if self.language else None,
            'gender':
            self.gender.value if self.gender else None,
            'processing_time':
            self.processing_time,
            'status':
            self.status.value,
            'error_message':
            self.error_message,
            'metadata':
            self.metadata
        }

    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ========== 사용자 프로필 ==========


@dataclass
class SpeakerProfile:
    """화자 프로필"""
    id: str
    name: str
    gender: Gender
    age_group: Optional[str] = None  # child, teen, adult, senior
    native_language: Language = Language.KOREAN
    pitch_range: Tuple[float, float] = (75.0, 600.0)
    average_pitch: Optional[float] = None
    speech_rate: Optional[float] = None  # syllables per second
    voice_characteristics: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'gender': self.gender.value,
            'age_group': self.age_group,
            'native_language': self.native_language.value,
            'pitch_range': list(self.pitch_range),
            'average_pitch': self.average_pitch,
            'speech_rate': self.speech_rate,
            'voice_characteristics': self.voice_characteristics,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


# ========== 학습 세션 ==========


@dataclass
class LearningSession:
    """학습 세션"""
    session_id: str
    user_id: str
    reference_audio: str
    practice_audio: str
    analysis_result: AnalysisResult
    score: float
    feedback: List[str]
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'reference_audio': self.reference_audio,
            'practice_audio': self.practice_audio,
            'analysis_result': self.analysis_result.to_dict(),
            'score': self.score,
            'feedback': self.feedback,
            'created_at': self.created_at.isoformat()
        }


# ========== 설정 모델 ==========


@dataclass
class ProcessingConfig:
    """처리 설정"""
    # 오디오 설정
    target_sample_rate: int = 16000
    normalize_audio: bool = True
    remove_silence: bool = True
    enhance_audio: bool = True

    # 분석 설정
    enable_pitch_analysis: bool = True
    enable_formant_analysis: bool = True
    enable_spectral_analysis: bool = True

    # STT 설정
    enable_stt: bool = True
    stt_engine: str = "whisper"
    stt_language: str = "ko"

    # TextGrid 설정
    generate_textgrid: bool = True
    textgrid_encoding: str = "utf-16"

    # 성능 설정
    use_gpu: bool = False
    max_threads: int = 4
    cache_results: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'audio': {
                'target_sample_rate': self.target_sample_rate,
                'normalize_audio': self.normalize_audio,
                'remove_silence': self.remove_silence,
                'enhance_audio': self.enhance_audio
            },
            'analysis': {
                'enable_pitch_analysis': self.enable_pitch_analysis,
                'enable_formant_analysis': self.enable_formant_analysis,
                'enable_spectral_analysis': self.enable_spectral_analysis
            },
            'stt': {
                'enable_stt': self.enable_stt,
                'stt_engine': self.stt_engine,
                'stt_language': self.stt_language
            },
            'textgrid': {
                'generate_textgrid': self.generate_textgrid,
                'textgrid_encoding': self.textgrid_encoding
            },
            'performance': {
                'use_gpu': self.use_gpu,
                'max_threads': self.max_threads,
                'cache_results': self.cache_results
            }
        }


# ========== 유틸리티 함수 ==========


def create_empty_textgrid(duration: float) -> TextGridData:
    """빈 TextGrid 생성"""
    return TextGridData(xmin=0.0, xmax=duration, tiers=[])


def create_interval_tier(
        name: str, duration: float,
        intervals: List[Tuple[float, float, str]]) -> TextGridTier:
    """인터벌 티어 생성"""
    tier = TextGridTier(name=name,
                        tier_type="IntervalTier",
                        xmin=0.0,
                        xmax=duration,
                        intervals=[])

    for xmin, xmax, text in intervals:
        tier.intervals.append(TextGridInterval(xmin, xmax, text))

    return tier


def create_point_tier(name: str, duration: float,
                      points: List[Tuple[float, str]]) -> TextGridTier:
    """포인트 티어 생성"""
    tier = TextGridTier(name=name,
                        tier_type="TextTier",
                        xmin=0.0,
                        xmax=duration,
                        points=[])

    for time, mark in points:
        tier.points.append(TextGridPoint(time, mark))

    return tier
