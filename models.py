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
    created_at = Column(DateTime, default=datetime.utcnow)

class AnalysisSession(Base):
    __tablename__ = 'analysis_session'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=True)
    session_data = Column(Text)  # JSON data for analysis results
    created_at = Column(DateTime, default=datetime.utcnow)
    session_type = Column(String(50))  # 'reference', 'realtime', etc.

class SurveyResponse(Base):
    __tablename__ = 'survey_response'
    
    id = Column(Integer, primary_key=True)
    response_data = Column(Text)  # JSON data for survey responses
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=True)

class ReferenceFile(Base):
    __tablename__ = 'reference_file'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)  # 파일 제목
    description = Column(Text)  # 파일 설명
    sentence_text = Column(Text)  # 문장 내용
    wav_filename = Column(String(255), nullable=False)  # WAV 파일명
    textgrid_filename = Column(String(255), nullable=False)  # TextGrid 파일명
    file_size = Column(Integer)  # 파일 크기 (bytes)
    duration = Column(Float)  # 오디오 길이 (초)
    syllable_count = Column(Integer)  # 음절 수
    detected_gender = Column(String(10))  # 감지된 성별 (male/female)
    average_f0 = Column(Float)  # 평균 기본 주파수 (Hz)
    created_at = Column(DateTime, default=datetime.utcnow)
    uploaded_by = Column(Integer, ForeignKey('user.id'), nullable=True)
    is_public = Column(Boolean, default=True)  # 공개 여부
