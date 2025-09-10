"""
데이터베이스 모델
SQLAlchemy ORM 모델 정의
"""

from datetime import datetime
from typing import Optional, Dict, Any
import json
import enum
from pathlib import Path

from sqlalchemy import (create_engine, Column, Integer, String, Float,
                        DateTime, Boolean, Text, JSON, ForeignKey, Enum, Index)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.sql import func

from config import settings
from utils import get_logger

logger = get_logger(__name__)

# ========== 데이터베이스 설정 ==========

Base = declarative_base()
engine = create_engine(settings.DATABASE_URL,
                       echo=settings.DEBUG,
                       pool_pre_ping=True,
                       pool_size=5,
                       max_overflow=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ========== 열거형 정의 ==========


class FileStatus(enum.Enum):
    """파일 상태"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DELETED = "deleted"


class ProcessingType(enum.Enum):
    """처리 타입"""
    NORMALIZATION = "normalization"
    ENHANCEMENT = "enhancement"
    ANALYSIS = "analysis"
    TRANSCRIPTION = "transcription"
    SEGMENTATION = "segmentation"
    QUALITY_CHECK = "quality_check"
    FULL_PIPELINE = "full_pipeline"


class UserRole(enum.Enum):
    """사용자 역할"""
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"
    GUEST = "guest"


# ========== 모델 정의 ==========


class TimestampMixin:
    """타임스탬프 믹스인"""
    created_at = Column(DateTime(timezone=True),
                        server_default=func.now(),
                        nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AudioFile(Base, TimestampMixin):
    """오디오 파일 모델"""
    __tablename__ = "audio_files"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(String(100), unique=True, index=True, nullable=False)
    original_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)  # bytes
    duration = Column(Float)  # seconds
    sample_rate = Column(Integer)
    channels = Column(Integer)
    format = Column(String(20))
    status = Column(Enum(FileStatus), default=FileStatus.UPLOADED)

    # 관계
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("UserProfile", back_populates="audio_files")
    processing_results = relationship("ProcessingResult",
                                      back_populates="audio_file",
                                      cascade="all, delete-orphan")

    # 메타데이터
    file_metadata = Column(JSON, default={})

    # 인덱스
    __table_args__ = (
        Index('idx_audio_files_user_status', 'user_id', 'status'),
        Index('idx_audio_files_created', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            'id': self.id,
            'file_id': self.file_id,
            'original_name': self.original_name,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'duration': self.duration,
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'format': self.format,
            'status': self.status.value if self.status else None,
            'user_id': self.user_id,
            'metadata': self.file_metadata,
            'created_at':
            self.created_at.isoformat() if self.created_at else None,
            'updated_at':
            self.updated_at.isoformat() if self.updated_at else None
        }


class ProcessingResult(Base, TimestampMixin):
    """처리 결과 모델"""
    __tablename__ = "processing_results"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(100), unique=True, index=True, nullable=False)
    processing_type = Column(Enum(ProcessingType), nullable=False)

    # 관계
    audio_file_id = Column(Integer,
                           ForeignKey("audio_files.id"),
                           nullable=False)
    audio_file = relationship("AudioFile", back_populates="processing_results")

    # 결과
    success = Column(Boolean, default=False)
    processing_time = Column(Float)  # seconds

    # STT 결과
    transcription = Column(Text)
    transcription_confidence = Column(Float)
    language = Column(String(10))

    # 분석 결과
    pitch_mean = Column(Float)
    pitch_std = Column(Float)
    pitch_range = Column(Float)
    formants = Column(JSON)  # F1, F2, F3, F4

    # 품질 메트릭
    audio_quality_score = Column(Float)
    pronunciation_score = Column(Float)

    # 전체 결과 JSON
    result_data = Column(JSON, default={})
    error_message = Column(Text)

    # 인덱스
    __table_args__ = (
        Index('idx_processing_results_audio', 'audio_file_id'),
        Index('idx_processing_results_type_success', 'processing_type',
              'success'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            'id':
            self.id,
            'task_id':
            self.task_id,
            'processing_type':
            self.processing_type.value if self.processing_type else None,
            'audio_file_id':
            self.audio_file_id,
            'success':
            self.success,
            'processing_time':
            self.processing_time,
            'transcription':
            self.transcription,
            'transcription_confidence':
            self.transcription_confidence,
            'language':
            self.language,
            'pitch_mean':
            self.pitch_mean,
            'pitch_std':
            self.pitch_std,
            'pitch_range':
            self.pitch_range,
            'formants':
            self.formants,
            'audio_quality_score':
            self.audio_quality_score,
            'pronunciation_score':
            self.pronunciation_score,
            'result_data':
            self.result_data,
            'error_message':
            self.error_message,
            'created_at':
            self.created_at.isoformat() if self.created_at else None
        }


class UserProfile(Base, TimestampMixin):
    """사용자 프로필 모델"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True)
    name = Column(String(100))
    role = Column(Enum(UserRole), default=UserRole.STUDENT)

    # 프로필 정보
    age_group = Column(String(20))  # child, teen, adult, senior
    gender = Column(String(10))  # male, female, other
    native_language = Column(String(10), default="ko")

    # 음성 특성
    avg_pitch = Column(Float)
    pitch_range_min = Column(Float)
    pitch_range_max = Column(Float)
    speech_rate = Column(Float)  # syllables per second

    # 학습 통계
    total_sessions = Column(Integer, default=0)
    total_practice_time = Column(Float, default=0.0)  # seconds
    last_session_date = Column(DateTime(timezone=True))

    # 설정
    preferences = Column(JSON, default={})

    # 관계
    audio_files = relationship("AudioFile",
                               back_populates="user",
                               cascade="all, delete-orphan")
    learning_sessions = relationship("LearningSession",
                                     back_populates="user",
                                     cascade="all, delete-orphan")

    # 인덱스
    __table_args__ = (
        Index('idx_users_role', 'role'),
        Index('idx_users_last_session', 'last_session_date'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            'id':
            self.id,
            'user_id':
            self.user_id,
            'email':
            self.email,
            'name':
            self.name,
            'role':
            self.role.value if self.role else None,
            'age_group':
            self.age_group,
            'gender':
            self.gender,
            'native_language':
            self.native_language,
            'avg_pitch':
            self.avg_pitch,
            'pitch_range': [self.pitch_range_min, self.pitch_range_max],
            'speech_rate':
            self.speech_rate,
            'total_sessions':
            self.total_sessions,
            'total_practice_time':
            self.total_practice_time,
            'last_session_date':
            self.last_session_date.isoformat()
            if self.last_session_date else None,
            'preferences':
            self.preferences,
            'created_at':
            self.created_at.isoformat() if self.created_at else None
        }


class LearningSession(Base, TimestampMixin):
    """학습 세션 모델"""
    __tablename__ = "learning_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)

    # 관계
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("UserProfile", back_populates="learning_sessions")

    reference_file_id = Column(Integer, ForeignKey("audio_files.id"))
    practice_file_id = Column(Integer, ForeignKey("audio_files.id"))

    # 세션 정보
    session_type = Column(String(50))  # practice, assessment, free_talk
    duration = Column(Float)  # seconds

    # 평가 결과
    overall_score = Column(Float)
    pitch_accuracy = Column(Float)
    timing_accuracy = Column(Float)
    pronunciation_score = Column(Float)
    fluency_score = Column(Float)

    # 상세 결과
    results = Column(JSON, default={})
    feedback = Column(JSON, default=[])

    # 완료 여부
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True))

    # 인덱스
    __table_args__ = (
        Index('idx_sessions_user_completed', 'user_id', 'is_completed'),
        Index('idx_sessions_created', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            'id':
            self.id,
            'session_id':
            self.session_id,
            'user_id':
            self.user_id,
            'reference_file_id':
            self.reference_file_id,
            'practice_file_id':
            self.practice_file_id,
            'session_type':
            self.session_type,
            'duration':
            self.duration,
            'overall_score':
            self.overall_score,
            'pitch_accuracy':
            self.pitch_accuracy,
            'timing_accuracy':
            self.timing_accuracy,
            'pronunciation_score':
            self.pronunciation_score,
            'fluency_score':
            self.fluency_score,
            'results':
            self.results,
            'feedback':
            self.feedback,
            'is_completed':
            self.is_completed,
            'completed_at':
            self.completed_at.isoformat() if self.completed_at else None,
            'created_at':
            self.created_at.isoformat() if self.created_at else None
        }


class SystemLog(Base):
    """시스템 로그 모델"""
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True),
                       server_default=func.now(),
                       index=True)
    level = Column(String(20))  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    logger_name = Column(String(100))
    message = Column(Text)

    # 추가 정보
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(100))
    request_id = Column(String(100))

    # 상세 데이터
    extra_data = Column(JSON, default={})
    traceback = Column(Text)

    # 인덱스
    __table_args__ = (
        Index('idx_logs_timestamp_level', 'timestamp', 'level'),
        Index('idx_logs_user', 'user_id'),
        Index('idx_logs_session', 'session_id'),
    )


# ========== 데이터베이스 유틸리티 ==========


def init_db():
    """데이터베이스 초기화"""
    try:
        # 테이블 생성
        Base.metadata.create_all(bind=engine)
        logger.info("데이터베이스 테이블 생성 완료")

        # 초기 데이터 삽입 (필요시)
        db = SessionLocal()
        try:
            # 기본 사용자 생성 (없으면)
            guest_user = db.query(UserProfile).filter_by(
                user_id="guest").first()
            if not guest_user:
                guest_user = UserProfile(user_id="guest",
                                         name="Guest User",
                                         role=UserRole.GUEST)
                db.add(guest_user)
                db.commit()
                logger.info("게스트 사용자 생성 완료")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"데이터베이스 초기화 실패: {str(e)}")
        raise


def get_db() -> Session:
    """데이터베이스 세션 생성"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_or_create_user(db: Session, user_id: str, **kwargs) -> UserProfile:
    """사용자 가져오기 또는 생성"""
    user = db.query(UserProfile).filter_by(user_id=user_id).first()

    if not user:
        user = UserProfile(user_id=user_id, **kwargs)
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"새 사용자 생성: {user_id}")

    return user


def save_audio_file(db: Session,
                    file_id: str,
                    original_name: str,
                    file_path: str,
                    user_id: Optional[int] = None,
                    **metadata) -> AudioFile:
    """오디오 파일 정보 저장"""
    audio_file = AudioFile(file_id=file_id,
                           original_name=original_name,
                           file_path=file_path,
                           user_id=user_id,
                           file_file_metadata=metadata)

    # 파일 정보 추출
    if Path(file_path).exists():
        import librosa
        try:
            y, sr = librosa.load(file_path, sr=None, duration=1)
            audio_file.sample_rate = sr

            # 전체 길이는 따로 계산
            info = librosa.get_duration(filename=file_path)
            audio_file.duration = info

            # 파일 크기
            audio_file.file_size = Path(file_path).stat().st_size

            # 포맷
            audio_file.format = Path(file_path).suffix[1:]

        except Exception as e:
            logger.warning(f"오디오 정보 추출 실패: {e}")

    db.add(audio_file)
    db.commit()
    db.refresh(audio_file)

    logger.info(f"오디오 파일 저장: {file_id}")
    return audio_file


def save_processing_result(db: Session,
                           task_id: str,
                           audio_file_id: int,
                           processing_type: ProcessingType,
                           result_data: Dict[str, Any],
                           success: bool = True,
                           processing_time: float = 0.0) -> ProcessingResult:
    """처리 결과 저장"""
    result = ProcessingResult(task_id=task_id,
                              audio_file_id=audio_file_id,
                              processing_type=processing_type,
                              success=success,
                              processing_time=processing_time,
                              result_data=result_data)

    # 주요 필드 추출
    if processing_type == ProcessingType.TRANSCRIPTION:
        result.transcription = result_data.get('text', '')
        result.transcription_confidence = result_data.get('confidence', 0.0)
        result.language = result_data.get('language', 'ko')

    elif processing_type == ProcessingType.ANALYSIS:
        if 'pitch' in result_data:
            pitch = result_data['pitch']
            result.pitch_mean = pitch.get('statistics', {}).get('mean', 0.0)
            result.pitch_std = pitch.get('statistics', {}).get('std', 0.0)
            result.pitch_range = pitch.get('statistics', {}).get('range', 0.0)

    db.add(result)
    db.commit()
    db.refresh(result)

    logger.info(f"처리 결과 저장: {task_id}")
    return result


def cleanup_old_files(db: Session, days: int = 7):
    """오래된 파일 정리"""
    from datetime import timedelta

    cutoff_date = datetime.now() - timedelta(days=days)

    # 오래된 파일 조회
    old_files = db.query(AudioFile).filter(
        AudioFile.created_at < cutoff_date, AudioFile.status
        != FileStatus.DELETED).all()

    for file in old_files:
        # 파일 삭제
        file_path = Path(file.file_path)
        if file_path.exists():
            try:
                file_path.unlink()
                logger.info(f"파일 삭제: {file_path}")
            except Exception as e:
                logger.error(f"파일 삭제 실패: {e}")

        # DB 상태 업데이트
        file.status = FileStatus.DELETED

    db.commit()
    logger.info(f"{len(old_files)}개 오래된 파일 정리 완료")


# ========== 통계 쿼리 ==========


def get_user_statistics(db: Session, user_id: int) -> Dict[str, Any]:
    """사용자 통계 조회"""
    user = db.query(UserProfile).filter_by(id=user_id).first()

    if not user:
        return {}

    # 세션 통계
    sessions = db.query(LearningSession).filter_by(user_id=user_id).all()
    completed_sessions = [s for s in sessions if s.is_completed]

    # 평균 점수 계산
    if completed_sessions:
        avg_score = sum(s.overall_score or 0
                        for s in completed_sessions) / len(completed_sessions)
        avg_pitch = sum(s.pitch_accuracy or 0
                        for s in completed_sessions) / len(completed_sessions)
        avg_pronunciation = sum(
            s.pronunciation_score or 0
            for s in completed_sessions) / len(completed_sessions)
    else:
        avg_score = avg_pitch = avg_pronunciation = 0.0

    return {
        'user_id':
        user.user_id,
        'name':
        user.name,
        'total_sessions':
        len(sessions),
        'completed_sessions':
        len(completed_sessions),
        'total_practice_time':
        user.total_practice_time,
        'average_score':
        avg_score,
        'average_pitch_accuracy':
        avg_pitch,
        'average_pronunciation':
        avg_pronunciation,
        'last_session':
        user.last_session_date.isoformat() if user.last_session_date else None
    }


if __name__ == "__main__":
    # 데이터베이스 초기화
    init_db()
    logger.info("데이터베이스 초기화 완료")
