from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from flask_login import UserMixin
from datetime import datetime

Base = declarative_base()

class User(UserMixin, Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(256))
    
    # 🎯 학습자 프로필 정보 확장
    learner_name = Column(String(100))  # 학습자 이름
    gender = Column(String(10))  # male/female
    age_group = Column(String(20))  # 10대, 20대, 30대, 등
    korean_level = Column(String(20))  # 초급, 중급, 고급
    learning_goals = Column(Text)  # 학습 목표
    
    # 🎯 학습 통계
    total_sessions = Column(Integer, default=0)  # 총 학습 세션 수
    total_learning_time = Column(Float, default=0.0)  # 총 학습 시간 (분)
    last_activity = Column(DateTime)  # 마지막 활동 시간
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 🎯 관계 설정
    analysis_sessions = relationship("AnalysisSession", back_populates="user")
    survey_responses = relationship("SurveyResponse", back_populates="user")
    uploaded_files = relationship("ReferenceFile", back_populates="uploader")

class AnalysisSession(Base):
    __tablename__ = 'analysis_session'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=True)
    
    # 🎯 세션 기본 정보
    session_type = Column(String(50))  # 'reference', 'realtime', 'upload', etc.
    reference_file_id = Column(Integer, ForeignKey('reference_file.id'), nullable=True)
    learner_gender = Column(String(10))  # 학습 당시 성별 설정
    
    # 🎯 분석 결과 데이터
    session_data = Column(Text)  # JSON data for analysis results
    pitch_data = Column(Text)  # JSON pitch analysis data
    syllable_analysis = Column(Text)  # JSON syllable analysis data
    
    # 🎯 성능 지표
    average_f0 = Column(Float)  # 평균 기본 주파수
    f0_range = Column(Float)  # 기본 주파수 범위
    accuracy_score = Column(Float)  # 정확도 점수 (0-100)
    completion_rate = Column(Float)  # 완료율 (0-100)
    
    # 🎯 시간 정보
    duration_seconds = Column(Float)  # 분석 길이 (초)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 🎯 관계 설정
    user = relationship("User", back_populates="analysis_sessions")
    reference_file = relationship("ReferenceFile")

class SurveyResponse(Base):
    __tablename__ = 'survey_response'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=True)
    
    # 🎯 설문 응답 데이터
    response_data = Column(Text)  # JSON data for survey responses  
    survey_type = Column(String(50))  # 'feedback', 'demographic', 'evaluation'
    completion_status = Column(String(20), default='completed')  # 'started', 'completed', 'abandoned'
    
    # 🎯 메타데이터
    session_id = Column(String(100))  # 설문 세션 ID
    ip_address = Column(String(45))  # 응답자 IP (IPv6 지원)
    user_agent = Column(Text)  # 브라우저 정보
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 🎯 관계 설정
    user = relationship("User", back_populates="survey_responses")

class ReferenceFile(Base):
    __tablename__ = 'reference_file'
    
    id = Column(Integer, primary_key=True)
    uploaded_by = Column(Integer, ForeignKey('user.id'), nullable=True)
    
    # 🎯 파일 메타데이터
    title = Column(String(200), nullable=False)  # 파일 제목
    description = Column(Text)  # 파일 설명
    sentence_text = Column(Text)  # 문장 내용
    wav_filename = Column(String(255), nullable=False)  # WAV 파일명
    textgrid_filename = Column(String(255), nullable=False)  # TextGrid 파일명
    file_size = Column(Integer)  # 파일 크기 (bytes)
    
    # 🎯 음성 분석 결과
    duration = Column(Float)  # 오디오 길이 (초)
    syllable_count = Column(Integer)  # 음절 수
    detected_gender = Column(String(10))  # 감지된 성별 (male/female)
    average_f0 = Column(Float)  # 평균 기본 주파수 (Hz)
    f0_min = Column(Float)  # 최소 기본 주파수 (Hz)
    f0_max = Column(Float)  # 최대 기본 주파수 (Hz)
    
    # 🎯 사용 통계
    download_count = Column(Integer, default=0)  # 다운로드 횟수
    analysis_count = Column(Integer, default=0)  # 분석 사용 횟수
    
    # 🎯 접근 권한
    is_public = Column(Boolean, default=True)  # 공개 여부
    difficulty_level = Column(String(20))  # 난이도 (초급, 중급, 고급)
    tags = Column(String(500))  # 태그 (comma-separated)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 🎯 관계 설정
    uploader = relationship("User", back_populates="uploaded_files")
