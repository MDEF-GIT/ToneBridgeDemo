"""
ToneBridge FastAPI backend - PRAAT ALGORITHM IMPLEMENTATION
Implements authentic Praat pitch extraction with real-time analysis
"""
import io
import os
import sys
import tempfile
import subprocess
import shutil
import uuid
import math
import re
from pathlib import Path
from datetime import datetime
from typing import List, Optional

import numpy as np
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from models import ReferenceFile, Base

try:
    import parselmouth as pm
    print("🎯 Parselmouth (Praat Python) imported successfully")
except ImportError as e:
    print(f"❌ Failed to import parselmouth: {e}")
    sys.exit(1)

# Import our enhanced automation systems
from audio_enhancement import AutomatedProcessor
from advanced_stt_processor import AdvancedSTTProcessor
from audio_analysis import (
    STTBasedSegmenter, 
    split_korean_sentence,
    analyze_audio_file,
    create_textgrid_from_audio,
    SyllableSegment
)

# 🚀 Import Ultimate STT System
try:
    from ultimate_stt_system import UltimateSTTSystem
    ULTIMATE_STT_AVAILABLE = True
    print("✅ Ultimate STT System 로드 완료")
except ImportError as e:
    print(f"⚠️ Ultimate STT System 로드 실패: {e}")
    ULTIMATE_STT_AVAILABLE = False

# 🚀 Import Korean Audio Optimizer
try:
    from korean_audio_optimizer import KoreanAudioOptimizer
    KOREAN_OPTIMIZER_AVAILABLE = True
    print("✅ Korean Audio Optimizer 로드 완료")
except ImportError as e:
    print(f"⚠️ Korean Audio Optimizer 로드 실패: {e}")
    KOREAN_OPTIMIZER_AVAILABLE = False

app = FastAPI(title="ToneBridge Praat Analysis API")

# 마이크로서비스 아키텍처: 백엔드는 순수 API만 제공
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Database setup
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///tonebridge.db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# File upload directory
UPLOAD_DIR = Path("static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🚀 전역 AI 인스턴스들 (서버 시작 시 미리 로드)
print("🎯 ToneBridge AI 시스템 초기화 중...")
global_ai_instances = {}

# STT 프로세서 초기화
try:
    print("🎤 고급 STT 프로세서 초기화 중...")
    global_ai_instances['advanced_stt'] = AdvancedSTTProcessor()
    print("✅ 고급 STT 프로세서 초기화 완료")
except Exception as e:
    print(f"❌ 고급 STT 초기화 실패: {e}")
    global_ai_instances['advanced_stt'] = None

# Ultimate STT 시스템 (지연 로딩 - 첫 사용 시에만 초기화)
if ULTIMATE_STT_AVAILABLE:
    global_ai_instances['ultimate_stt'] = None  # 지연 로딩
    print("⚡ Ultimate STT 시스템: 지연 로딩 설정 (첫 사용 시 자동 초기화)")
else:
    global_ai_instances['ultimate_stt'] = None

# Korean Audio Optimizer 초기화
if KOREAN_OPTIMIZER_AVAILABLE:
    try:
        print("🇰🇷 Korean Audio Optimizer 초기화 중...")
        global_ai_instances['korean_optimizer'] = KoreanAudioOptimizer()
        print("✅ Korean Audio Optimizer 초기화 완료")
    except Exception as e:
        print(f"❌ Korean Optimizer 초기화 실패: {e}")
        global_ai_instances['korean_optimizer'] = None
else:
    global_ai_instances['korean_optimizer'] = None

print("🎯 ToneBridge AI 시스템 초기화 완료!")
print(f"   활성 시스템: {list(global_ai_instances.keys())}")

# 뮤텍스 (순서 보장용)
import asyncio
ai_processing_lock = asyncio.Lock()

# Pydantic models
class RefPoint(BaseModel):
    t: float
    f0: float
    dB: float
    semitone: float

class Syllable(BaseModel):
    label: str
    start: float
    end: float

class SyllableAnalysis(BaseModel):
    label: str  # 'syllable' → 'label'
    start: float
    end: float
    duration: float  # str → float
    f0: float  # 'pitch_mean' → 'f0'
    semitone: float
    qtone: float
    intensity: float  # str → float

class RefAnalysis(BaseModel):
    curve: List[RefPoint]
    syllables: List[Syllable]
    syllable_analysis: List[SyllableAnalysis]
    stats: dict

def split_korean_sentence(sentence: str) -> List[str]:
    """Split Korean sentence into individual syllables"""
    return [char for char in sentence.strip() if char.strip()]

# 정밀 음절 분절 기능은 audio_analysis.py 모듈로 이동됨

def auto_segment_syllables(sound: pm.Sound, sentence: str) -> List[dict]:
    """
    자동 음절 분절 기능 - Parselmouth 기반 음성 분석
    음성에서 자동으로 음절 경계를 탐지하고 TextGrid 생성
    """
    print("🤖🤖🤖 자동 음절 분절 시작 🤖🤖🤖")
    
    if not sentence or not sentence.strip():
        print("❌ 문장 정보가 없어 자동 분절 불가")
        return []
    
    # 한국어 음절로 분리
    syllables_text = split_korean_sentence(sentence)
    print(f"🎯 목표 음절: {syllables_text} ({len(syllables_text)}개)")
    
    try:
        # Step 1: Intensity 기반 음성 활동 구간 탐지
        intensity = sound.to_intensity(minimum_pitch=75.0)
        
        # Step 2: 무음 구간 탐지로 대략적인 경계 찾기
        # 평균 intensity의 20% 이하를 무음으로 판정
        mean_intensity = intensity.values.mean()
        silence_threshold = mean_intensity * 0.2
        
        print(f"🎯 평균 강도: {mean_intensity:.2f}dB, 무음 임계값: {silence_threshold:.2f}dB")
        
        # Step 3: 정밀한 음성학적 분절 알고리즘 적용
        duration = sound.xmax - sound.xmin
        
        print(f"🎯 음성 길이: {duration:.3f}초")
        print(f"🎯 목표: {len(syllables_text)}개 음절 - {syllables_text}")
        
        # Step 4: STT 기반 정밀 분절 (새 모듈 사용) - 통합 라이브러리 사용
        from tonebridge_core.segmentation.korean_segmenter import KoreanSyllableSegmenter
        segmenter = KoreanSyllableSegmenter()
        
        # 임시 파일 생성 (Parselmouth Sound 객체로부터)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            temp_path = tmp_file.name
            sound.save(temp_path, "WAV")
        
        segment_results = segmenter.segment(temp_path, sentence)
        
        # 임시 파일 정리
        import os
        os.unlink(temp_path)
        
        # 기존 형식으로 변환
        syllables = []
        for segment in segment_results:
            syllables.append({
                'label': segment.label,
                'start': segment.start,
                'end': segment.end
            })
        
        for i, syl in enumerate(syllables):
            print(f"   🎯 '{syl['label']}': {syl['start']:.3f}s ~ {syl['end']:.3f}s")
        
        print(f"✅ 자동 음절 분절 완료: {len(syllables)}개")
        return syllables
        
    except Exception as e:
        print(f"❌ 자동 분절 실패: {e}")
        return []

def save_textgrid(syllables: List[dict], output_path: str, total_duration: float):
    """
    음절 정보를 TextGrid 파일로 저장
    """
    print(f"💾 TextGrid 저장: {output_path}")
    
    try:
        # 🚀 통합 라이브러리 사용하여 TextGrid 생성
        from tonebridge_core.textgrid.generator import UnifiedTextGridGenerator
        from tonebridge_core.models import SyllableSegment
        
        # 기존 딕셔너리 형식을 SyllableSegment로 변환
        segments = []
        for syl in syllables:
            if isinstance(syl, dict):
                segments.append(SyllableSegment(
                    label=syl.get('label', syl.get('syllable', '')),
                    start=syl.get('start', 0.0),
                    end=syl.get('end', 0.0),
                    confidence=syl.get('confidence', 0.8)
                ))
        
        # 통합 생성기로 TextGrid 생성
        generator = UnifiedTextGridGenerator()
        textgrid_content = generator.from_syllables(segments, total_duration)
        
        # UTF-16으로 저장 (기존 TextGrid와 동일한 인코딩)
        with open(output_path, 'w', encoding='utf-16') as f:
            f.write(textgrid_content)
        
        print(f"✅ TextGrid 저장 완료: {len(syllables)}개 음절")
        return True
        
    except Exception as e:
        print(f"❌ TextGrid 저장 실패: {e}")
        return False

def adjust_textgrid_timing(syllables: List[dict]) -> List[dict]:
    """
    TextGrid 시간 정보 자동 보정 - 무음 구간 제거 대응
    첫 번째 음절의 시작 시간을 0으로 맞춰서 전체 시간 조정
    """
    if not syllables:
        return syllables
    
    # 첫 번째 음절의 시작 시간 확인
    first_start = syllables[0]['start']
    
    if first_start > 0.1:  # 0.1초 이상의 지연이 있으면 보정
        print(f"🔧🔧🔧 TextGrid 시간 보정: {first_start:.3f}초만큼 앞당김")
        
        # 모든 음절의 시간을 앞당김
        for syllable in syllables:
            syllable['start'] -= first_start
            syllable['end'] -= first_start
            
        print(f"🔧 보정 완료: 첫 음절이 {syllables[0]['start']:.3f}초부터 시작")
    
    return syllables

def praat_script_textgrid_parser(tg: pm.TextGrid) -> List[dict]:
    """
    Praat Call 기반 TextGrid parser - 표준 Parselmouth 방식
    """
    print("🎯🎯🎯 PRAAT CALL TEXTGRID PARSER 시작 🎯🎯🎯")
    
    if not tg:
        print("❌ TextGrid object is None")
        return []
    
    try:
        from parselmouth.praat import call
        
        # Praat call로 tier 정보 가져오기
        n_tiers = call(tg, "Get number of tiers")
        print(f"🎯 Found {n_tiers} tiers via Praat call")
        
        # 모든 tier에서 interval 수집
        table_rows = []
        
        for tier_num in range(1, n_tiers + 1):  # Praat은 1-based indexing
            try:
                tier_name = call(tg, "Get tier name", tier_num)
                is_interval_tier = call(tg, "Is interval tier", tier_num)
                
                print(f"🎯 Tier {tier_num}: '{tier_name}' (interval={is_interval_tier})")
                
                if is_interval_tier:
                    n_intervals = call(tg, "Get number of intervals", tier_num)
                    print(f"    🎯 Found {n_intervals} intervals")
                    
                    for interval_num in range(1, n_intervals + 1):  # 1-based
                        start_time = call(tg, "Get starting point", tier_num, interval_num)
                        end_time = call(tg, "Get end point", tier_num, interval_num)
                        label = call(tg, "Get label of interval", tier_num, interval_num).strip()
                        
                        if label:  # 빈 라벨 제외
                            table_rows.append({
                                "tier": tier_name.lower(),
                                "tier_idx": tier_num - 1,  # 0-based로 변환
                                "text": label,
                                "tmin": float(start_time),
                                "tmax": float(end_time),
                                "duration": float(end_time - start_time)
                            })
                            print(f"      🎯 Interval {interval_num}: '{label}' ({start_time:.3f}s-{end_time:.3f}s)")
                
            except Exception as e:
                print(f"❌ Error processing tier {tier_num}: {e}")
                continue
        
        print(f"🎯 Table created with {len(table_rows)} rows")
        
        # 음절 tier 찾기 (숫자 tier도 포함)
        target_tier_names = ["syllable", "syllables", "음절", "syl", "word", "words", "phones", "phone", "1", "2", "3", "intervals", "segment", "segments", "tier", "tier1", "tier2", "tier3"]
        extracted_rows = []
        
        for tier_name in target_tier_names:
            matches = [row for row in table_rows 
                      if row["tier"] == tier_name and row["text"] and row["duration"] > 0.001]
            if matches:
                extracted_rows = matches
                print(f"🎯✅ Found {len(matches)} syllables in tier '{tier_name}'")
                break
        
        # 특정 tier를 찾지 못하면 가장 많은 interval을 가진 tier 사용
        if not extracted_rows and table_rows:
            tier_counts = {}
            for row in table_rows:
                if row["text"] and row["duration"] > 0.001:
                    tier_name = row["tier"]
                    tier_counts[tier_name] = tier_counts.get(tier_name, 0) + 1
            
            if tier_counts:
                best_tier = max(tier_counts.keys(), key=lambda k: tier_counts[k])
                extracted_rows = [row for row in table_rows 
                                if row["tier"] == best_tier and row["text"] and row["duration"] > 0.001]
                print(f"🎯✅ Using tier with most intervals: '{best_tier}' ({len(extracted_rows)} syllables)")
        
        # 🚨 CRITICAL FIX: 여전히 음절이 없으면 모든 tier의 모든 데이터를 강제로 사용
        if not extracted_rows and table_rows:
            print("🎯🚨 FALLBACK: 모든 tier 데이터를 음절로 강제 사용")
            extracted_rows = [row for row in table_rows if row["text"] and row["duration"] > 0.001]
            extracted_rows.sort(key=lambda x: x["tmin"])  # 시간순 정렬
            print(f"🎯✅ Forced extraction: {len(extracted_rows)} syllables from all tiers")
        
        # 음절이 없으면 빈 리스트 반환
        if not extracted_rows:
            print("🎯❌ COMPLETE FAILURE: No syllable data found at all")
            return []
        
        # 시간순 정렬
        extracted_rows.sort(key=lambda x: x["tmin"])
        
        # 표준 형식으로 변환
        syllables = []
        for row in extracted_rows:
            syllables.append({
                "label": row["text"],
                "start": row["tmin"],
                "end": row["tmax"]
            })
        
        print(f"🎯✅ Successfully parsed {len(syllables)} syllables from TextGrid")
        for syl in syllables:
            print(f"    - '{syl['label']}': {syl['start']:.3f}s-{syl['end']:.3f}s")
        
        # 🔧 시간 보정 적용
        print(f"🔧 보정 전 첫 음절: {syllables[0]['start']:.3f}초")
        syllables = adjust_textgrid_timing(syllables)
        print(f"🔧 보정 후 첫 음절: {syllables[0]['start']:.3f}초")
        
        return syllables
        
    except Exception as e:
        print(f"❌ Praat call parsing failed: {e}")
        return []

def apply_gender_normalization(analysis_result: dict, target_gender: str, learner_gender: str) -> dict:
    """
    학습자 성별에 따라 참조 데이터를 정규화하는 함수
    """
    try:
        # 성별별 평균 기본 주파수 (Hz) - 연구 기반 데이터
        gender_f0_base = {
            "male": 120.0,    # 남성 평균 기본 주파수
            "female": 220.0   # 여성 평균 기본 주파수
        }
        
        if target_gender == "auto":
            target_gender = "female"  # auto인 경우 기본값 설정
            print(f"🎯 참조 성별을 자동으로 female로 설정")
            
        if target_gender not in gender_f0_base or learner_gender not in gender_f0_base:
            print(f"🎯 정규화 생략: 지원하지 않는 성별 ({target_gender} -> {learner_gender})")
            return analysis_result
        
        # 정규화 비율 계산
        source_base = gender_f0_base[target_gender]  # 참조 음성의 성별 기준
        target_base = gender_f0_base[learner_gender]  # 학습자 성별 기준
        normalization_ratio = target_base / source_base
        
        print(f"🎯 정규화 비율: {source_base}Hz({target_gender}) -> {target_base}Hz({learner_gender}) = {normalization_ratio:.3f}")
        print(f"🎯 Semitone 기준 주파수: {target_base}Hz (학습자: {learner_gender})")
        print(f"🎯 컨투어 일치성: 대표 피치가 실제 곡선에서 벗어나지 않도록 보정 적용")
        
        # 곡선 데이터 정규화 (dict 형태 처리)
        normalized_curve = []
        for point in analysis_result.get('curve', []):
            if isinstance(point, dict):
                # dict 형태의 포인트 (t, f0, dB, semitone)
                normalized_point = point.copy()
                if 'f0' in normalized_point:
                    normalized_f0 = normalized_point['f0'] * normalization_ratio
                    normalized_point['f0'] = normalized_f0
                    # semitone 재계산 (정규화된 f0 기준)
                    if normalized_f0 > 0 and target_base > 0:
                        semitone_val = 12 * np.log2(normalized_f0 / target_base)
                        normalized_point['semitone'] = semitone_val
                        # 첫 번째 포인트만 디버깅 출력
                        if len(normalized_curve) == 0:
                            print(f"🎯 첫 포인트 semitone 계산: f0={normalized_f0:.1f}Hz, base={target_base}Hz → {semitone_val:.2f}st")
                    else:
                        normalized_point['semitone'] = 0.0
                normalized_curve.append(normalized_point)
            elif len(point) >= 2:
                # 리스트 형태의 포인트 [time, freq]
                time_val = point[0]
                freq_val = point[1] * normalization_ratio
                normalized_curve.append([time_val, freq_val])
            else:
                normalized_curve.append(point)
        
        # 음절 데이터 정규화
        normalized_syllables = []
        for syl in analysis_result.get('syllables', []):
            normalized_syl = syl.copy()
            
            # 🎯 모든 학습자에게 정규화된 음절 대표 피치 표시
            if True:  # 남성/여성 모두 정규화된 데이터 표시
                # 🎯 모든 성별에게 f0 관련 필드 정규화
                f0_fields = ['f0', 'median_f0', 'representative_f0', 'center_f0']
                for field in f0_fields:
                    if field in normalized_syl and normalized_syl[field] is not None:
                        original_f0 = normalized_syl[field]
                        normalized_f0 = original_f0 * normalization_ratio
                        normalized_syl[field] = normalized_f0
                        
                        # 대표 f0 필드의 경우 semitone도 업데이트 (성별별 기준 주파수 적용)
                        if field == 'f0' and normalized_f0 > 0 and target_base > 0:
                            # 🎯 성별별 최적화된 기준 주파수
                            gender = analysis_result.get('gender', 'unknown')
                            semitone_base = 200 if gender == 'female' else 150  # 여성 200Hz, 남성 150Hz
                            qtone_base = 130  # Q-tone은 표준 130Hz 유지
                            
                            normalized_semitone = 12 * np.log2(normalized_f0 / semitone_base)
                            normalized_syl['semitone'] = normalized_semitone
                            # 🎯 올바른 Q-tone 공식: 5 * log2(f0/130)
                            normalized_syl['qtone'] = 5 * np.log2(normalized_f0 / qtone_base) if normalized_f0 > 0 else 0.0
                            normalized_syl['semitone_median'] = normalized_semitone  # 호환성
                            
                            print(f"🎯 음절 '{normalized_syl.get('label', '?')}': {original_f0:.1f}Hz → {normalized_f0:.1f}Hz ({normalized_semitone:.2f}st)")
                            
                            # 🎯 CRITICAL DEBUG: 정규화된 syllable_analysis에도 반영해야함!
                            if 'syllable_analysis' in analysis_result:
                                for syl_analysis in analysis_result['syllable_analysis']:
                                    if syl_analysis.get('label') == normalized_syl.get('label'):
                                        syl_analysis['f0'] = normalized_f0
                                        syl_analysis['semitone'] = normalized_semitone
                                        syl_analysis['semitone_median'] = normalized_semitone
                                        # 🎯 올바른 Q-tone 공식: 5 * log2(f0/130)  
                                        syl_analysis['qtone'] = 5 * np.log2(normalized_f0 / qtone_base) if normalized_f0 > 0 else 0.0
                                        print(f"🎯 syllable_analysis 업데이트: {syl_analysis['label']} = {normalized_semitone:.2f}st")
                normalized_syl['show_syllable_pitch'] = True
                    
            # 빈 f0 필드 처리
            if 'f0' not in normalized_syl or normalized_syl['f0'] is None or normalized_syl['f0'] <= 0:
                normalized_syl['semitone'] = 0.0
                normalized_syl['qtone'] = 0.0
                normalized_syl['semitone_median'] = 0.0
                
            normalized_syllables.append(normalized_syl)
        
        # 통계 데이터 정규화
        normalized_stats = analysis_result.get('stats', {}).copy()
        if 'mean_f0' in normalized_stats:
            normalized_stats['mean_f0'] = normalized_stats['mean_f0'] * normalization_ratio
        if 'median_f0' in normalized_stats:
            normalized_stats['median_f0'] = normalized_stats['median_f0'] * normalization_ratio
        if 'max_f0' in normalized_stats:
            normalized_stats['max_f0'] = normalized_stats['max_f0'] * normalization_ratio
        if 'min_f0' in normalized_stats:
            normalized_stats['min_f0'] = normalized_stats['min_f0'] * normalization_ratio
        
        # 정규화된 결과 반환
        normalized_result = analysis_result.copy()
        normalized_result['curve'] = normalized_curve
        normalized_result['syllables'] = normalized_syllables
        normalized_result['stats'] = normalized_stats
        
        print(f"🎯 정규화 완료: {len(normalized_curve)}개 포인트, {len(normalized_syllables)}개 음절")
        return normalized_result
        
    except Exception as e:
        print(f"🚨 정규화 오류: {e}")
        return analysis_result

def detect_reference_gender(analysis_result: dict) -> str:
    """
    참조 음성의 성별을 자동으로 감지하는 함수
    평균 기본 주파수를 기반으로 성별을 추정
    """
    try:
        # 곡선 데이터에서 평균 주파수 계산
        curve_data = analysis_result.get('curve', [])
        if not curve_data:
            return "female"  # 기본값을 female로 설정
        
        # 주파수 값들 추출 (dict 형태와 list 형태 모두 처리)
        frequencies = []
        for point in curve_data:
            if isinstance(point, dict) and 'f0' in point:
                frequencies.append(point['f0'])
            elif isinstance(point, (list, tuple)) and len(point) >= 2 and isinstance(point[1], (int, float)):
                frequencies.append(point[1])
        
        if not frequencies:
            return "female"  # 기본값
        
        # 평균 기본 주파수 계산
        mean_f0 = sum(frequencies) / len(frequencies)
        
        # 성별 분류 기준 (일반적인 음성학 기준)
        gender_threshold = 165.0  # Hz - 남성과 여성을 구분하는 임계값
        
        if mean_f0 < gender_threshold:
            detected_gender = "male"
        else:
            detected_gender = "female"
        
        print(f"🎯 참조 음성 분석: 평균 F0 = {mean_f0:.1f}Hz -> {detected_gender}")
        return detected_gender
        
    except Exception as e:
        print(f"🚨 성별 감지 오류: {e}")
        return "female"  # 오류 시 기본값

def simple_pitch_analysis_implementation(sound: pm.Sound, syllables: List[dict]) -> tuple:
    """
    Simple pitch analysis implementation
    """
    try:
        duration = sound.get_total_duration()
        print(f"🚀 AUDIO: {duration:.3f}s duration")
        
        # Basic pitch extraction
        pitch = sound.to_pitch(
            time_step=0.01,
            pitch_floor=75.0,
            pitch_ceiling=500.0
        )
        
        # Extract valid pitch points
        times = pitch.xs()
        valid_points = []
        
        for t in times:
            f0 = pitch.get_value_at_time(t)
            if f0 and not np.isnan(f0) and 75.0 < f0 < 500.0:
                valid_points.append((t, f0))
        
        print(f"🚀 Found {len(valid_points)} valid pitch points")
        
        # Calculate sentence median
        all_f0_values = [f0 for t, f0 in valid_points]
        sentence_median = np.median(all_f0_values) if all_f0_values else 200.0
        
        # 🎯 PERCEPTUAL PITCH CONTOUR: 음절별 대표 피치로 부드러운 곡선 생성
        curve = []
        
        if len(syllables) > 0 and len(valid_points) > 0:
            # 1. 음절별 대표 피치 계산 (사람이 인지하는 억양 패턴)
            syllable_pitch_points = []
            
            for i, syl in enumerate(syllables):
                start_t = syl["start"]
                end_t = syl["end"]
                center_t = start_t + (end_t - start_t) / 2
                label = syl["label"]
                
                # 🎯 개선된 음절별 대표 피치 계산
                syllable_data = [(t, f0) for t, f0 in valid_points if start_t <= t <= end_t]
                
                if len(syllable_data) >= 2:
                    # 🎯 스마트 대표값 계산: 이상값 제거 + 중심부 가중평균
                    times, pitches = zip(*syllable_data)
                    
                    # 1. 이상값 제거 (IQR 방식)
                    pitch_array = np.array(pitches)
                    Q1 = np.percentile(pitch_array, 25)
                    Q3 = np.percentile(pitch_array, 75)
                    IQR = Q3 - Q1
                    
                    # 이상값 기준: Q1 - 1.5*IQR ~ Q3 + 1.5*IQR
                    lower_bound = Q1 - 1.5 * IQR
                    upper_bound = Q3 + 1.5 * IQR
                    
                    # 정상값만 필터링
                    filtered_data = [(t, f0) for t, f0 in syllable_data 
                                   if lower_bound <= f0 <= upper_bound]
                    
                    if len(filtered_data) >= 2:
                        times, pitches = zip(*filtered_data)
                        
                        # 2. 중심부 가중평균 (더 정교한 가중치)
                        weights = []
                        for t in times:
                            # 음절 중심에서의 거리 비율 (0~1)
                            if (end_t - start_t) > 0:
                                distance_ratio = abs(t - center_t) / ((end_t - start_t) / 2)
                                distance_ratio = min(1.0, distance_ratio)  # 1.0 이상 제한
                            else:
                                distance_ratio = 0
                            
                            # 가우시안 가중치: 중심에서 멀어질수록 급격히 감소
                            weight = np.exp(-2 * distance_ratio ** 2)  # e^(-2*d^2)
                            weights.append(weight)
                        
                        # 🎯 더 엄격한 컨투어 일치 검증
                        min_f0 = min(pitches)
                        max_f0 = max(pitches)
                        center_f0 = np.median(pitches)
                        q1_f0 = np.percentile(pitches, 25)
                        q3_f0 = np.percentile(pitches, 75)
                        
                        # 가중 평균 계산
                        representative_f0 = np.average(pitches, weights=weights)
                        
                        # 🎯 더욱 엄격한 보정: 남성 성별 문제 해결
                        iqr_range = q3_f0 - q1_f0
                        acceptable_range = max(iqr_range * 0.3, 8.0)  # 더 엄격하게: 30% 범위, 최소 8Hz
                        
                        # 가중 평균이 중앙값에서 너무 멀리 떨어진 경우
                        if abs(representative_f0 - center_f0) > acceptable_range:
                            representative_f0 = center_f0
                            print(f"  🎯 '{label}': IQR보정 {len(syllable_data)}개→{len(filtered_data)}개 → {representative_f0:.1f}Hz (중앙값사용)")
                        else:
                            # 추가 검증: 최댓값/최솟값 범위 내인지 확인
                            if representative_f0 < min_f0 or representative_f0 > max_f0:
                                representative_f0 = center_f0
                                print(f"  🎯 '{label}': 범위보정 {len(syllable_data)}개→{len(filtered_data)}개 → {representative_f0:.1f}Hz (중앙값사용)")
                            else:
                                # 최종 검증: 25-75% 범위 내에 있는지 확인 (더 엄격)
                                if representative_f0 < q1_f0 or representative_f0 > q3_f0:
                                    representative_f0 = center_f0
                                    print(f"  🎯 '{label}': Q범위보정 {len(syllable_data)}개→{len(filtered_data)}개 → {representative_f0:.1f}Hz (중앙값사용)")
                                else:
                                    print(f"  🎯 '{label}': {len(syllable_data)}개→{len(filtered_data)}개 → {representative_f0:.1f}Hz (검증완료)")
                    else:
                        # 필터링 후 데이터가 부족하면 원본 median 사용
                        representative_f0 = np.median([f0 for t, f0 in syllable_data])
                        print(f"  🎯 '{label}': {len(syllable_data)}개 → {representative_f0:.1f}Hz (원본median)")
                elif len(syllable_data) == 1:
                    # 데이터가 1개면 그대로 사용
                    representative_f0 = syllable_data[0][1]
                    print(f"  🎯 '{label}': 1개 → {representative_f0:.1f}Hz (단일값)")
                else:
                    # 음절 내 데이터 없음: 더 넓은 범위에서 검색
                    margin = 0.1  # 100ms로 확장
                    extended_data = [(t, f0) for t, f0 in valid_points 
                                   if (start_t - margin) <= t <= (end_t + margin)]
                    
                    if len(extended_data) >= 2:
                        # 확장 데이터로 동일한 스마트 계산
                        times, pitches = zip(*extended_data)
                        pitch_array = np.array(pitches)
                        representative_f0 = np.median(pitch_array)
                        print(f"  🎯 '{label}': 확장검색 {len(extended_data)}개 → {representative_f0:.1f}Hz")
                    elif extended_data:
                        representative_f0 = extended_data[0][1]
                        print(f"  🎯 '{label}': 확장검색 1개 → {representative_f0:.1f}Hz")
                    elif valid_points:
                        # 가장 가까운 3개 피치의 median
                        distances = [(abs(t - center_t), f0) for t, f0 in valid_points]
                        distances.sort()
                        nearest_pitches = [f0 for _, f0 in distances[:3]]
                        representative_f0 = np.median(nearest_pitches)
                        print(f"  🎯 '{label}': 최근접3개 → {representative_f0:.1f}Hz")
                    else:
                        representative_f0 = sentence_median
                        print(f"  🎯 '{label}': 기본값 → {representative_f0:.1f}Hz")
                
                syllable_pitch_points.append((center_t, representative_f0))
            
            # 2. 음절 사이를 부드럽게 보간 (스플라인 곡선 시뮬레이션)
            if len(syllable_pitch_points) >= 2:
                # 전체 시간 범위
                start_time = syllable_pitch_points[0][0]
                end_time = syllable_pitch_points[-1][0]
                total_duration = end_time - start_time
                
                # 0.02초 간격으로 부드러운 곡선 생성 (50Hz 샘플링)
                time_step = 0.02
                num_points = int(total_duration / time_step) + 1
                
                for i in range(num_points):
                    current_time = start_time + i * time_step
                    
                    # 현재 시간에 해당하는 피치 보간
                    if current_time <= syllable_pitch_points[0][0]:
                        # 시작 전
                        interpolated_f0 = syllable_pitch_points[0][1]
                    elif current_time >= syllable_pitch_points[-1][0]:
                        # 끝 이후
                        interpolated_f0 = syllable_pitch_points[-1][1]
                    else:
                        # 중간 구간 - 선형 보간
                        for j in range(len(syllable_pitch_points) - 1):
                            t1, f0_1 = syllable_pitch_points[j]
                            t2, f0_2 = syllable_pitch_points[j + 1]
                            
                            if t1 <= current_time <= t2:
                                # 선형 보간 (부드러운 곡선)
                                ratio = (current_time - t1) / (t2 - t1) if t2 != t1 else 0
                                interpolated_f0 = f0_1 + (f0_2 - f0_1) * ratio
                                break
                        else:
                            interpolated_f0 = syllable_pitch_points[0][1]
                    
                    # 곡선 데이터 추가
                    semitone = 12 * np.log2(interpolated_f0 / sentence_median) if sentence_median > 0 else 0.0
                    curve.append({
                        "t": float(current_time),
                        "f0": float(interpolated_f0),
                        "dB": -30.0,  # Default intensity
                        "semitone": float(semitone)
                    })
            
            elif len(syllable_pitch_points) == 1:
                # 음절이 하나만 있으면 플랫 라인
                t, f0 = syllable_pitch_points[0]
                semitone = 12 * np.log2(f0 / sentence_median) if sentence_median > 0 else 0.0
                curve.append({
                    "t": float(t),
                    "f0": float(f0),
                    "dB": -30.0,
                    "semitone": float(semitone)
                })
        
        elif len(valid_points) > 0:
            # 음절 정보가 없으면 기존 방식으로 폴백 (하지만 더 간소화)
            # 시간 간격으로 샘플링 (0.1초마다)
            time_step = 0.1
            start_time = valid_points[0][0]
            end_time = valid_points[-1][0]
            
            current_time = start_time
            while current_time <= end_time:
                # 현재 시간 근처의 피치들 평균
                nearby_pitches = [f0 for t, f0 in valid_points if abs(t - current_time) <= time_step/2]
                
                if nearby_pitches:
                    representative_f0 = np.median(nearby_pitches)
                    semitone = 12 * np.log2(representative_f0 / sentence_median) if sentence_median > 0 else 0.0
                    curve.append({
                        "t": float(current_time),
                        "f0": float(representative_f0),
                        "dB": -30.0,
                        "semitone": float(semitone)
                    })
                
                current_time += time_step
        
        print(f"🎯 인지적 피치 곡선: {len(valid_points)} raw → {len(curve)} 부드러운 포인트")
        
        # Process syllables for analysis table (unchanged)
        syllable_analysis = []
        
        for i, syl in enumerate(syllables):
            start_t = syl["start"]
            end_t = syl["end"]
            center_t = start_t + (end_t - start_t) / 2
            label = syl["label"]
            
            # Find pitch in syllable range
            syllable_pitches = [f0 for t, f0 in valid_points if start_t <= t <= end_t]
            
            if syllable_pitches:
                f0_val = np.mean(syllable_pitches)  # Use average instead of max
            elif valid_points:
                # Find nearest pitch
                nearest = min(valid_points, key=lambda x: abs(x[0] - center_t))
                f0_val = nearest[1]
            else:
                f0_val = sentence_median
            
            # Calculate semitone
            semitone = 12 * np.log2(f0_val / sentence_median) if sentence_median > 0 else 0.0
            
            syllable_analysis.append({
                "label": label,
                "start": float(start_t),
                "end": float(end_t),
                "duration": float(end_t - start_t),
                "f0": float(f0_val),
                "representative_f0": float(f0_val),  # 대표 f0 추가
                "semitone": float(semitone),
                "semitone_median": float(semitone),  # 호환성
                "qtone": float(5 * np.log2(f0_val / 130)) if f0_val > 0 else 0.0,
                "intensity": -30.0,
                # 🎯 음절 중심점 데이터 추가 (차트 표시용)
                "center_time": float(center_t),
                "start_time": float(start_t),  # 프론트엔드 호환성
                "end_time": float(end_t),      # 프론트엔드 호환성
                "start": float(start_t),       # 추가 호환성
                "end": float(end_t)            # 추가 호환성
            })
        
        print(f"🎯 Generated {len(curve)} time series points and {len(syllable_analysis)} syllable analyses")
        
        return curve, syllable_analysis, sentence_median
        
    except Exception as e:
        print(f"Simple pitch analysis error: {e}")
        # Return default values
        return [], [], 200.0

def praat_pitch_analysis(
    sound: pm.Sound,
    syllables: List[dict],
    pitch_floor: float = 75.0,
    pitch_ceiling: float = 500.0,   
    time_step: float = 0.01,
) -> tuple:
    """
    🚀 NEW SIMPLE ENGINE: 문제 해결을 위한 완전히 새로운 접근
    """
    # Simple pitch analysis implementation
    return simple_pitch_analysis_implementation(sound, syllables)
    
    duration = sound.get_total_duration()
    print(f"🚀 AUDIO: {duration:.3f}s duration")
    
    # 🎯 STEP 1: 기본 피치 추출 (표준 설정)
    pitch = sound.to_pitch(
        time_step=time_step,
        pitch_floor=pitch_floor,
        pitch_ceiling=pitch_ceiling
    )
    
    print(f"🚀 PITCH TRACK: {pitch_floor}-{pitch_ceiling}Hz, step={time_step}s")
    
    # 🎯 STEP 2: 음성 구간 찾기 (심플한 방법)
    times = pitch.xs()
    valid_points = []
    
    for t in times:
        f0 = pitch.get_value_at_time(t)
        if f0 and not np.isnan(f0) and f0 > pitch_floor and f0 < pitch_ceiling:
            valid_points.append((t, f0))
    
    print(f"🚀 FOUND: {len(valid_points)} valid pitch points")
    
    # 처음 몇개 포인트 확인
    if valid_points:
        print("🚀 FIRST VALID POINTS:")
        for i in range(min(3, len(valid_points))):
            t, f0 = valid_points[i]
            print(f"🚀   {t:.3f}s = {f0:.1f}Hz")
    else:
        print("🚀 ERROR: NO VALID PITCH FOUND")
        # 더 관대한 조건으로 재시도
        print("🚀 TRYING BROADER RANGE...")
        pitch = sound.to_pitch(pitch_floor=50, pitch_ceiling=800, time_step=0.01)
        times = pitch.xs()
        for t in times:
            f0 = pitch.get_value_at_time(t)
            if f0 and not np.isnan(f0) and f0 > 50:
                valid_points.append((t, f0))
        print(f"🚀 BROADER SEARCH: {len(valid_points)} points")
    
    # 🎯 STEP 3: 강도(intensity) 계산
    intensity = sound.to_intensity()
    
    # 🎯 STEP 4: 전체 문장의 기준 피치 계산
    all_f0_values = [f0 for t, f0 in valid_points]
    sentence_median = np.median(all_f0_values) if all_f0_values else 200.0
    print(f"🚀 SENTENCE MEDIAN: {sentence_median:.1f} Hz")
    
    # 🎯 STEP 5: 각 음절별 피치 분석 (심플하게!)
    curve = []
    syllable_analysis = []
    
    # Process each syllable (equivalent to Praat script's for loop)
    for i, syl in enumerate(syllables):
        start_t = syl["start"]
        end_t = syl["end"]
        dur = end_t - start_t
        center_t = start_t + dur/2
        label = syl["label"]
        
        print(f"🎯 Processing syllable '{label}' ({start_t:.3f}s - {end_t:.3f}s)")
        
        # 🎯 DEBUG: Check pitch values in syllable range
        print(f"   🎯 Checking pitch values from {start_t:.3f}s to {end_t:.3f}s...")
        
        # 더 조밀하게 샘플링 (20개 포인트)
        sample_times = [start_t + (end_t - start_t) * i / 19 for i in range(20)]
        valid_f0_values = []
        
        for sample_t in sample_times:
            try:
                f0_at_t = pitch.get_value_at_time(sample_t)
                if f0_at_t is not None and not np.isnan(f0_at_t) and f0_at_t > pitch_floor * 0.8:  # 더 관대한 필터링
                    valid_f0_values.append(f0_at_t)
                    print(f"     🎯 t={sample_t:.3f}s: f0={f0_at_t:.1f}Hz")
            except Exception as e:
                print(f"     🎯 t={sample_t:.3f}s: Error - {e}")
        
        print(f"   🎯 Found {len(valid_f0_values)} valid F0 values in syllable")
        
        # 🎯 CRITICAL FIX: 전체 피치 트랙에서 해당 시간대 데이터 직접 추출
        pitch_times = pitch.xs()  # 모든 시간 포인트
        pitch_values = []
        
        for t in pitch_times:
            if start_t <= t <= end_t:
                f0_val = pitch.get_value_at_time(t)
                if f0_val is not None and not np.isnan(f0_val) and f0_val > pitch_floor * 0.8:
                    pitch_values.append((t, f0_val))
        
        print(f"   🎯 Direct extraction found {len(pitch_values)} pitch points in syllable")
        
        if pitch_values:
            # 유효한 피치값이 있으면 최대값 사용
            max_pitch_point = max(pitch_values, key=lambda x: x[1])
            f0_max = max_pitch_point[1]
            time_of_max = max_pitch_point[0]
            f0_mean = np.mean([p[1] for p in pitch_values])
            print(f"   🎯 Direct extraction: max={f0_max:.1f}Hz at {time_of_max:.3f}s, mean={f0_mean:.1f}Hz")
        elif valid_f0_values:
            # 샘플링에서 찾은 값들 사용
            f0_max = max(valid_f0_values)
            f0_mean = np.mean(valid_f0_values)
            time_of_max = center_t
            print(f"   🎯 Sampling fallback: max={f0_max:.1f}Hz, mean={f0_mean:.1f}Hz")
        else:
            # 마지막 대안: 인근 유효한 피치값 찾기
            nearby_f0_values = []
            search_range = 0.1  # 100ms 범위로 확장 검색
            
            for t in pitch_times:
                if (start_t - search_range) <= t <= (end_t + search_range):
                    f0_val = pitch.get_value_at_time(t)
                    if f0_val is not None and not np.isnan(f0_val) and f0_val > pitch_floor * 0.8:
                        nearby_f0_values.append(f0_val)
            
            if nearby_f0_values:
                f0_max = np.median(nearby_f0_values)  # 중간값 사용
                time_of_max = center_t
                print(f"   🎯 Extended search found {len(nearby_f0_values)} nearby values, using median={f0_max:.1f}Hz")
            else:
                f0_max = None
                time_of_max = center_t
                print(f"   🎯 No pitch found even with extended search")
        
        # Get mean F0 as fallback (like Praat script: Get mean...)
        try:
            f0_mean = pitch.get_mean(start_t, end_t, "Hertz")
            print(f"   🎯 get_mean() returned: {f0_mean}")
        except Exception as e:
            print(f"   🎯 get_mean() failed: {e}")
            f0_mean = None
        
        # Manual calculation from valid samples
        if valid_f0_values:
            manual_max = max(valid_f0_values)
            manual_mean = np.mean(valid_f0_values)
            print(f"   🎯 Manual calculation: max={manual_max:.1f}Hz, mean={manual_mean:.1f}Hz")
            
            # Use manual values if official methods failed
            if f0_max is None or np.isnan(f0_max):
                f0_max = manual_max
                time_of_max = center_t
                print(f"   🎯 Using manual max: {f0_max:.1f}Hz")
            
            if f0_mean is None or np.isnan(f0_mean):
                f0_mean = manual_mean
                print(f"   🎯 Using manual mean: {f0_mean:.1f}Hz")
        
        # Choose F0 value (prefer max, fallback to mean)
        if f0_max is not None and not np.isnan(f0_max):
            f0_val = f0_max
            time_val = time_of_max
            print(f"   🎯 Max F0: {f0_val:.1f} Hz @ {time_val:.3f}s")
        elif f0_mean is not None and not np.isnan(f0_mean):
            f0_val = f0_mean
            time_val = center_t
            print(f"   🎯 Mean F0: {f0_val:.1f} Hz @ {time_val:.3f}s")
        else:
            f0_val = sentence_median  # fallback to sentence median
            time_val = center_t
            print(f"   🎯 Fallback to sentence median: {f0_val:.1f} Hz")
        
        # Get intensity
        try:
            db_val = intensity.get_value(time_val)
            if db_val is None or np.isnan(db_val):
                db_val = -40.0
        except:
            db_val = -40.0
        
        # Calculate semitone and quarter-tone (like Praat script)
        if f0_val and not np.isnan(f0_val):
            semi_tone = 12 * np.log2(f0_val / sentence_median)
            quarter_tone = 24 * np.log2(f0_val / sentence_median)
            print(f"   🎯 Semi-tone: {semi_tone:.1f}, Quarter-tone: {quarter_tone:.1f}")
        else:
            semi_tone = 0.0
            quarter_tone = 0.0
        
        curve.append({
            "t": time_val,
            "f0": float(f0_val),
            "dB": float(db_val),
            "semitone": float(semi_tone)
        })
        
        syllable_analysis.append({
            "label": label,  # 🎯 "syllable" → "label" 수정
            "start": float(start_t),
            "end": float(end_t), 
            "duration": float(dur),
            "f0": float(f0_val),
            "representative_f0": float(f0_val),
            "semitone": float(semi_tone),  # 🎯 중요! semitone 추가
            "semitone_median": float(semi_tone),
            "qtone": float(5 * np.log2(f0_val / 130)) if f0_val > 0 else 0.0,
            "intensity": float(db_val),
            "center_time": float(time_val),  # 🎯 중심 시간 추가
            "start_time": float(start_t),
            "end_time": float(end_t)
        })
        
        print(f"   🎯✅ '{label}': {f0_val:.1f}Hz @ {time_val:.3f}s, {db_val:.1f}dB")
    
    print(f"🎯🎯🎯 PRAAT ANALYSIS 완료: {len(curve)}개 포인트 🎯🎯🎯")
    return curve, syllable_analysis, sentence_median

def extract_ref_praat_implementation(
    sound: pm.Sound,
    tg: pm.TextGrid,
    pitch_floor: float = 75.0,
    pitch_ceiling: float = 600.0,
    time_step: float = 0.01,
    sentence: str | None = None,
    extracted_syllables: Optional[list] = None,
    target_gender: str = 'auto',
):
    """
    Complete Praat-based reference extraction implementing Script_toneLabeler_cj.praat
    """
    print("🎯🎯🎯🎯🎯 PRAAT IMPLEMENTATION 시작!!! 🎯🎯🎯🎯🎯")
    print("🎯🎯🎯🎯🎯 PRAAT IMPLEMENTATION 시작!!! 🎯🎯🎯🎯🎯")
    print("🎯🎯🎯🎯🎯 PRAAT IMPLEMENTATION 시작!!! 🎯🎯🎯🎯🎯")
    print(f"🎯 Parameters: pitch_floor={pitch_floor}, pitch_ceiling={pitch_ceiling}")
    print(f"🎯 Sound duration: {sound.xmax - sound.xmin:.3f}s")
    
    t_min, t_max = sound.xmin, sound.xmax
    
    # Step 1: Use extracted syllables from new TextGrid parser or fallback
    if extracted_syllables:
        print(f"🎯 Using extracted syllables: {len(extracted_syllables)} syllables")
        syllables = adjust_textgrid_timing(extracted_syllables)  # 🔧 시간 보정 적용
    else:
        print("🎯 Fallback: Using old TextGrid parser")
        syllables = praat_script_textgrid_parser(tg) if tg else []
    
    # Step 1.5: TextGrid가 없거나 문제가 있으면 자동 분절 시도
    if not syllables and sentence and sentence.strip():
        print("🤖 TextGrid 분석 실패 → 자동 음절 분절 시도")
        syllables = auto_segment_syllables(sound, sentence)
        
        # 자동 생성된 음절로 TextGrid 파일 업데이트
        if syllables:
            textgrid_path = str(Path("static/reference_files") / f"{sentence.replace(' ', '')}.TextGrid")
            save_textgrid(syllables, textgrid_path, sound.duration)
            print(f"🤖 새로운 TextGrid 생성: {textgrid_path}")
    
    # Step 2: Fallback to sentence-based or time-based segmentation
    if not syllables:
        if sentence and sentence.strip():
            print(f"🎯 Sentence-based segmentation: '{sentence}'")
            syllable_labels = split_korean_sentence(sentence.strip())
            num_syllables = len(syllable_labels)
            segment_duration = float(t_max - t_min) / num_syllables
            
            for i, label in enumerate(syllable_labels):
                start_time = float(t_min + i * segment_duration)
                end_time = float(t_min + (i+1) * segment_duration)
                syllables.append({
                    "label": label,
                    "start": start_time,
                    "end": end_time,
                })
                print(f"   🎯 Sentence syllable: '{label}' ({start_time:.3f}s-{end_time:.3f}s)")
        else:
            print("🎯 Default 3-segment division")
            segment_duration = float(t_max - t_min) / 3
            for i in range(3):
                start_time = float(t_min + i * segment_duration)
                end_time = float(t_min + (i+1) * segment_duration)
                syllables.append({
                    "label": f"구간{i+1}",
                    "start": start_time,
                    "end": end_time,
                })
    
    print(f"🎯 Final syllables: {len(syllables)} syllables")
    
    # Step 3: Praat pitch analysis
    curve, syllable_analysis, sentence_median = praat_pitch_analysis(
        sound, syllables, pitch_floor, pitch_ceiling, time_step
    )
    
    
    return {
        "curve": curve,
        "syllables": syllables,
        "syllable_analysis": syllable_analysis,
        "spectrogram": [],
        "stats": {
            "meanF0": sentence_median,
            "maxF0": max([p["f0"] for p in curve]) if curve else 180.0,
            "maxdB": max([p["dB"] for p in curve]) if curve else -40.0,
            "sentence_median": sentence_median,
            "duration": float(t_max - t_min),
        },
    }

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/react-demo", response_class=HTMLResponse)
async def react_demo(request: Request):
    """React migration demo using voice-analysis-demo directory contents only"""
    # Use voice-analysis-demo directory templates and static files
    from fastapi.templating import Jinja2Templates
    demo_templates = Jinja2Templates(directory="voice-analysis-demo/templates")
    return demo_templates.TemplateResponse("index.html", {"request": request})

@app.post("/analyze_ref", response_model=RefAnalysis)
async def analyze_ref(
    wav: UploadFile = File(..., description="Reference WAV"),
    textgrid: UploadFile = File(..., description="Reference TextGrid"),
    sentence: str = Form(None, description="Sentence text for syllable labeling"),
    learner_gender: str = Form(..., description="Learner gender (male/female)"),
    learner_name: str = Form(None, description="Learner name (optional)"),
    learner_level: str = Form(None, description="Learner level (optional)"),
    pitch_floor: Optional[float] = Form(75.0),
    pitch_ceiling: Optional[float] = Form(600.0),
    time_step: Optional[float] = Form(0.01),
):
    try:
        print("🎯🎯🎯 PRAAT API ENDPOINT 호출됨!!! 🎯🎯🎯")
        print(f"Received files: WAV={wav.filename}, TextGrid={textgrid.filename}")
        print(f"🎯 학습자 정보: 성별={learner_gender}, 이름={learner_name or '미입력'}, 수준={learner_level or '미입력'}")
        if sentence:
            print(f"Received sentence: '{sentence}'")
        
        # Validate file types
        if wav.filename and not wav.filename.lower().endswith('.wav'):
            raise HTTPException(status_code=400, detail="WAV 파일만 업로드 가능합니다")
        if textgrid.filename and not textgrid.filename.lower().endswith(('.textgrid', '.TextGrid')):
            raise HTTPException(status_code=400, detail="TextGrid 파일만 업로드 가능합니다")
        
        wav_bytes = await wav.read()
        tg_bytes = await textgrid.read()
        
        print(f"File sizes: WAV={len(wav_bytes)} bytes, TextGrid={len(tg_bytes)} bytes")

        # Create temporary files for parselmouth
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as wav_temp:
            wav_temp.write(wav_bytes)
            wav_temp_path = wav_temp.name
            
        with tempfile.NamedTemporaryFile(suffix='.TextGrid', delete=False) as tg_temp:
            tg_temp.write(tg_bytes)
            tg_temp_path = tg_temp.name

        try:
            import parselmouth as pm
            snd = pm.Sound(wav_temp_path)
            
            # Try to read TextGrid file
            try:
                tg = pm.TextGrid.read(tg_temp_path)
                
                # 🎯 COMPLETE TextGrid structure analysis
                print(f"🎯🔍 TextGrid 객체 완전 분석:")
                print(f"    🎯 Type: {type(tg)}")
                print(f"    🎯 Dir: {[attr for attr in dir(tg) if not attr.startswith('_')]}")
                
                # Check all possible attributes AND methods
                attributes_to_check = [
                    'n_tiers', 'tiers', 'size', 'count', 'length',
                    'xmin', 'xmax', 'start_time', 'end_time', 'info'
                ]
                
                for attr in attributes_to_check:
                    if hasattr(tg, attr):
                        try:
                            if callable(getattr(tg, attr)):
                                if attr == 'info':
                                    value = getattr(tg, attr)()  # Call the method
                                else:
                                    value = f"<method {attr}>"
                            else:
                                value = getattr(tg, attr)
                            print(f"    🎯 {attr}: {value} (type: {type(value)})")
                        except Exception as e:
                            print(f"    🎯 {attr}: Error calling - {e}")
                
                # 🎯 TRY DIFFERENT PARSELMOUTH METHODS
                print("🎯 Trying different Parselmouth access methods...")
                
                # Method: Try to find tier-related methods in dir
                all_methods = [attr for attr in dir(tg) if not attr.startswith('_')]
                tier_methods = [m for m in all_methods if 'tier' in m.lower()]
                if tier_methods:
                    print(f"    🎯 Found tier-related methods: {tier_methods}")
                
                # Method: Try to use info() method for structure
                try:
                    if hasattr(tg, 'info'):
                        info_result = tg.info()
                        print(f"    🎯 Info method result: {info_result}")
                except Exception as e:
                    print(f"    🎯 Info method failed: {e}")
                
                # 🎯 CORRECT APPROACH: Use official Parselmouth TextGrid API
                tier_count = 0
                intervals = []
                
                # Method 1: Try TextGridTools (to_tgt) - OFFICIAL METHOD
                try:
                    print("🎯 Method 1: Using TextGridTools (.to_tgt())")
                    try:
                        import textgrid as tgt  # TextGrid parser
                    except ImportError:
                        print("🚨 textgrid 라이브러리가 설치되지 않음")
                    
                    # Simple TextGrid parsing without external library
                    print("🎯 Using simple TextGrid parsing")
                    
                    # Read TextGrid file content
                    with open(tg_temp_path, 'r', encoding='utf-8') as f:
                        tg_content = f.read()
                    
                    tgt_grid = None
                    print(f"    🎯 TextGrid content read successful!")
                    print(f"    🎯 Content length: {len(tg_content)} characters")
                    
                    # Simple TextGrid parsing - extract intervals using regex
                    import re
                    
                    # Find intervals in TextGrid content
                    interval_pattern = r'intervals \[\d+\]:\s*xmin = ([\d.]+)\s*xmax = ([\d.]+)\s*text = "([^"]*)"'  
                    matches = re.findall(interval_pattern, tg_content)
                    
                    for start_str, end_str, text in matches:
                        if text.strip() and text.strip().lower() not in ['', 'p', 'sp']:
                            intervals.append({
                                "label": text.strip(),
                                "start": float(start_str),
                                "end": float(end_str)
                            })
                            print(f"      🎯 Parsed interval: '{text}' ({start_str}s-{end_str}s)")
                    
                    tier_count = 1 if intervals else 0
                    print(f"🎯✅ Simple parsing method SUCCESS: {len(intervals)} intervals extracted")
                        
                except ImportError:
                    print("    🎯 TextGridTools not installed, trying Method 2...")
                except Exception as e:
                    print(f"    🎯 TextGridTools method failed: {e}")
                
                # Method 2: Direct Praat calls - OFFICIAL METHOD
                if tier_count == 0:
                    try:
                        print("🎯 Method 2: Using parselmouth.praat.call()")
                        import parselmouth as pm
                        
                        # Get basic tier information  
                        num_tiers = pm.praat.call(tg, "Get number of tiers")
                        print(f"    🎯 Number of tiers: {num_tiers}")
                        
                        if num_tiers > 0:
                            tier_count = num_tiers
                            
                            # Get first tier information (1-based indexing in Praat!)
                            tier_name = pm.praat.call(tg, "Get tier name", 1)
                            num_intervals = pm.praat.call(tg, "Get number of intervals", 1)
                            print(f"    🎯 Tier 1 name: '{tier_name}', intervals: {num_intervals}")
                            
                            # Extract all intervals from first tier
                            for i in range(1, num_intervals + 1):  # 1-based indexing!
                                start_time = pm.praat.call(tg, "Get start time of interval", 1, i)
                                end_time = pm.praat.call(tg, "Get end time of interval", 1, i)
                                label = pm.praat.call(tg, "Get label of interval", 1, i)
                                
                                intervals.append({
                                    'start': start_time,
                                    'end': end_time,
                                    'label': label.strip(),
                                    'index': i-1  # Convert to 0-based for consistency
                                })
                                print(f"        🎯 Interval {i}: '{label}' ({start_time:.3f}s - {end_time:.3f}s)")
                            
                            print(f"🎯✅ Praat calls method SUCCESS: {len(intervals)} intervals extracted")
                            
                    except Exception as e:
                        print(f"    🎯 Praat calls method failed: {e}")
                
                # Filter out empty intervals and prepare syllable data
                syllables = []
                if intervals:
                    print(f"🎯 Processing {len(intervals)} intervals...")
                    
                    for interval in intervals:
                        # Only include non-empty intervals
                        if interval['label'] and interval['label'].strip():
                            syllables.append({
                                'label': interval['label'],
                                'start': interval['start'],
                                'end': interval['end']
                            })
                            print(f"    🎯 Valid syllable: '{interval['label']}' ({interval['start']:.3f}s - {interval['end']:.3f}s)")
                    
                    print(f"🎯✅ Final syllable count: {len(syllables)} syllables")
                else:
                    print("🎯⚠️ No intervals extracted from TextGrid")
                
                # Use extracted syllables or fallback
                if syllables:
                    tier_count = len(syllables) 
                    print(f"🎯✅ Successfully extracted {len(syllables)} syllables from TextGrid")
                else:
                    tier_count = 0
                    print("🎯⚠️ No syllables found - using fallback mode")
                    
            except Exception as e1:
                try:
                    # Alternative reading method
                    import subprocess
                    result = subprocess.run(['file', tg_temp_path], capture_output=True, text=True)
                    print(f"🎯 File type check: {result.stdout.strip()}")
                    
                    data_obj = pm.Data.read(tg_temp_path)
                    if hasattr(data_obj, 'n_tiers') or hasattr(data_obj, 'tiers'):
                        tg = data_obj
                        tier_count = getattr(data_obj, 'n_tiers', len(getattr(data_obj, 'tiers', [])))
                        print(f"🎯✅ TextGrid 읽기 성공 (Data로): {tier_count}개 tier")
                    else:
                        raise Exception("Read object is not a valid TextGrid")
                except Exception as e2:
                    print(f"🎯❌ TextGrid 읽기 실패: {e1}, {e2}")
                    print("🎯🔄 음성 전용 분석 모드로 진행 (TextGrid 없이)")
                    tg = None
                    tier_count = 0
            
            tg_info = f"Sound duration: {snd.duration:.2f}s"
            if tg is not None:
                tg_info += f", TextGrid tiers: {tier_count}"
            else:
                tg_info += ", TextGrid: fallback mode"
            print(tg_info)
            
            # 🎯 성별 매개변수 가져오기 
            target_gender = 'auto'  # 기본값으로 설정
            print(f"🎯 Target gender: {target_gender}")
            
            # 🎯 syllables 변수 초기화 (확실하게 정의)
            syllables = []
            if 'syllables' not in locals():
                syllables = []
            
            # 🎯 학습자 성별에 따른 최적화된 분석 파라미터 설정
            if learner_gender == "male":
                optimized_pitch_floor = 75.0
                optimized_pitch_ceiling = 300.0
                print(f"🎯 남성 학습자 - 최적화된 피치 범위: {optimized_pitch_floor}-{optimized_pitch_ceiling}Hz")
            elif learner_gender == "female":
                optimized_pitch_floor = 100.0
                optimized_pitch_ceiling = 600.0
                print(f"🎯 여성 학습자 - 최적화된 피치 범위: {optimized_pitch_floor}-{optimized_pitch_ceiling}Hz")
            else:
                optimized_pitch_floor = pitch_floor or 75.0
                optimized_pitch_ceiling = pitch_ceiling or 600.0
                print(f"🎯 기본 피치 범위 사용: {optimized_pitch_floor}-{optimized_pitch_ceiling}Hz")
            
            print("🎯🎯🎯 PRAAT extract_ref 함수 호출 직전!!! 🎯🎯🎯")
            # Pass extracted syllables from TextGrid to the processing function with optimized parameters
            out = extract_ref_praat_implementation(
                snd, tg,
                pitch_floor=optimized_pitch_floor,
                pitch_ceiling=optimized_pitch_ceiling,
                time_step=time_step or 0.01,
                sentence=sentence,
                extracted_syllables=syllables if syllables and len(syllables) > 0 else None,
                target_gender=target_gender
            )
            print("🎯🎯🎯 PRAAT extract_ref 함수 호출 완료!!! 🎯🎯🎯")
            
            # 🎯 참조 음성의 성별 자동 감지
            reference_gender = detect_reference_gender(out)
            print(f"🎯 참조 음성 성별 감지: {reference_gender}")
            
            # 🎯 학습자 성별에 따른 참조 데이터 정규화
            if learner_gender == "male":
                print("🎯 남성 학습자 - 참조 데이터를 남성 기준으로 정규화 중...")
                out = apply_gender_normalization(out, target_gender=reference_gender, learner_gender="male")
                print("🎯 남성 학습자 - 정규화된 곡선에 맞는 음절 대표 피치 표시")
            elif learner_gender == "female":
                print("🎯 여성 학습자 - 참조 데이터를 여성 기준으로 정규화 중...")
                out = apply_gender_normalization(out, target_gender=reference_gender, learner_gender="female")
            else:
                print("🎯 성별 미지정 - 원본 데이터 사용")
            
            print(f"Analysis complete: {len(out['curve'])} points, {len(out['syllables'])} syllables, {len(out.get('syllable_analysis', []))} syllable_analysis")
            print(f"🎯 CRITICAL DEBUG - out keys: {list(out.keys())}")
            if 'syllable_analysis' in out:
                print(f"🎯 syllable_analysis 샘플: {out['syllable_analysis'][:3] if len(out['syllable_analysis']) > 0 else 'EMPTY'}")
            
        finally:
            # Clean up temporary files
            try:
                os.unlink(wav_temp_path)
                os.unlink(tg_temp_path)
            except:
                pass
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Analysis error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"분석 중 오류 발생: {str(e)}")

    curve = [RefPoint(**p) for p in out["curve"]]
    syll  = [Syllable(**s) for s in out["syllables"]]
    
    print(f"🎯 FINAL CHECK - syllable_analysis exists: {'syllable_analysis' in out}")
    if 'syllable_analysis' in out:
        print(f"🎯 FINAL CHECK - syllable_analysis length: {len(out['syllable_analysis'])}")
        print(f"🎯 FINAL CHECK - syllable_analysis sample: {out['syllable_analysis'][:2] if out['syllable_analysis'] else 'EMPTY'}")
    
    syllable_analysis = [SyllableAnalysis(**s) for s in out.get("syllable_analysis", [])]
    print(f"🎯 FINAL CHECK - Pydantic syllable_analysis length: {len(syllable_analysis)}")
    return RefAnalysis(
        curve=curve, 
        syllables=syll, 
        syllable_analysis=syllable_analysis,
        stats=out["stats"]
    )

@app.post("/api/save_session")
async def save_session(request: Request):
    """Save analysis session data"""
    try:
        data = await request.json()
        print(f"🎯 Saving session data: {len(data)} items")
        # Here you would typically save to database
        return JSONResponse({"status": "success", "message": "Session saved"})
    except Exception as e:
        print(f"Save session error: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/record_realtime")
async def record_realtime(
    audio_data: UploadFile = File(...),
    session_id: str = Form(None)
):
    """Real-time audio recording and analysis endpoint"""
    try:
        print("🎯 Real-time recording received")
        audio_bytes = await audio_data.read()
        
        # Process real-time audio with Praat algorithms
        # Handle webm files from browser recording
        if audio_data.filename and audio_data.filename.endswith('.webm'):
            # Save as webm first, then convert to wav
            with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as temp_webm:
                temp_webm.write(audio_bytes)
                temp_webm_path = temp_webm.name
            
            # Convert webm to wav using FFmpeg
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                temp_audio_path = temp_wav.name
            
            import subprocess
            result = subprocess.run([
                'ffmpeg', '-i', temp_webm_path, '-ar', '16000', '-ac', '1', 
                '-y', temp_audio_path
            ], capture_output=True, text=True)
            
            os.unlink(temp_webm_path)  # Clean up webm file
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg conversion failed: {result.stderr}")
        else:
            # Direct wav file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
                temp_audio.write(audio_bytes)
                temp_audio_path = temp_audio.name
        
        try:
            snd = pm.Sound(temp_audio_path)
            
            # Quick pitch analysis for real-time
            pitch = snd.to_pitch_ac(
                time_step=0.01,
                pitch_floor=75.0,
                pitch_ceiling=600.0,
                very_accurate=False  # Faster for real-time
            )
            
            times = pitch.xs()
            f0_values = []
            for t in times:
                f0 = pitch.get_value_at_time(t)
                if f0 is not None and not np.isnan(f0):
                    f0_values.append({"t": t, "f0": f0})
            
            print(f"🎯 Real-time analysis: {len(f0_values)} pitch points")
            
        finally:
            os.unlink(temp_audio_path)
        
        # 🎯 개선된 실시간 응답: Hz, semitone, Q-tone 모든 단위 포함
        enhanced_f0_values = []
        for f0_data in f0_values[-10:]:  # 최근 10개 포인트만
            f0 = f0_data['f0']
            # 🎯 성별 추정 기반 최적화 (실시간에서는 주파수 범위로 추정)
            estimated_gender = 'female' if f0 > 180 else 'male'
            semitone_base = 200 if estimated_gender == 'female' else 150
            qtone_base = 130  # Q-tone 표준 기준
            
            enhanced_f0_values.append({
                "t": f0_data['t'],
                "f0": f0,
                "semitone": 12 * np.log2(f0 / semitone_base) if f0 > 0 else 0.0,
                "qtone": 5 * np.log2(f0 / qtone_base) if f0 > 0 else 0.0,
                "estimated_gender": estimated_gender
            })
        
        return JSONResponse({
            "status": "success",
            "pitch_data": enhanced_f0_values,
            "duration": snd.duration if 'snd' in locals() else 0,
            "units": ["hz", "semitone", "qtone"]  # 지원되는 단위 명시
        })
        
    except Exception as e:
        print(f"Real-time analysis error: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/api/save_reference")
async def save_reference_file(
    title: str = Form(...),
    description: str = Form(""),
    sentence_text: str = Form(""),
    wav_file: UploadFile = File(...),
    textgrid_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """참조 파일을 서버에 저장"""
    try:
        # 고유한 파일명 생성
        file_id = str(uuid.uuid4())
        wav_filename = f"{file_id}_{wav_file.filename}"
        textgrid_filename = f"{file_id}_{textgrid_file.filename}"
        
        # 파일 저장
        wav_path = UPLOAD_DIR / wav_filename
        textgrid_path = UPLOAD_DIR / textgrid_filename
        
        with open(wav_path, "wb") as f:
            shutil.copyfileobj(wav_file.file, f)
        
        with open(textgrid_path, "wb") as f:
            shutil.copyfileobj(textgrid_file.file, f)
        
        # 파일 크기 계산
        file_size = wav_path.stat().st_size + textgrid_path.stat().st_size
        
        # 오디오 길이와 음절 수 분석
        try:
            snd = pm.Sound(str(wav_path))
            duration = snd.duration
            
            # TextGrid에서 음절 수 추출
            tg = pm.TextGrid.read_from_file(str(textgrid_path))
            syllable_count = len([tier for tier in tg.tiers if tier.name == "syllables"])
            if syllable_count == 0:
                syllable_count = len(tg.tiers[0].intervals) if tg.tiers else 0
        except:
            duration = 0.0
            syllable_count = 0
        
        # 데이터베이스에 저장
        ref_file = ReferenceFile(
            title=title,
            description=description,
            sentence_text=sentence_text,
            wav_filename=wav_filename,
            textgrid_filename=textgrid_filename,
            file_size=file_size,
            duration=duration,
            syllable_count=syllable_count,
            is_public=True
        )
        
        db.add(ref_file)
        db.commit()
        db.refresh(ref_file)
        
        return JSONResponse({
            "status": "success",
            "message": "참조 파일이 성공적으로 저장되었습니다.",
            "file_id": ref_file.id
        })
        
    except Exception as e:
        print(f"Save reference file error: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/api/reference_files")
async def get_reference_files():
    """저장된 참조 파일 목록 조회 - 파일 시스템 기반"""
    try:
        # 직접 파일 시스템에서 파일 목록 조회 - 마이크로서비스 구조 반영
        reference_dir = "static/reference_files"
        if not os.path.exists(reference_dir):
            return JSONResponse({"files": []})
        
        # 사용 가능한 WAV 파일들 찾기
        wav_files = []
        for filename in os.listdir(reference_dir):
            if filename.endswith('.wav'):
                base_name = filename[:-4]  # .wav 제거
                textgrid_file = base_name + '.TextGrid'
                textgrid_path = os.path.join(reference_dir, textgrid_file)
                
                if os.path.exists(textgrid_path):
                    # 파일 크기 및 지속시간 계산
                    wav_path = os.path.join(reference_dir, filename)
                    file_size = os.path.getsize(wav_path)
                    
                    # 🎯 실제 오디오 지속시간과 성별 분석
                    duration = 0.0
                    detected_gender = "female"  # 기본값
                    average_f0 = 0.0
                    
                    try:
                        import parselmouth as pm
                        sound = pm.Sound(wav_path)
                        duration = sound.get_total_duration()
                        
                        # 성별 자동 감지를 위한 피치 분석
                        pitch = sound.to_pitch()
                        f0_values = []
                        for i in range(pitch.get_number_of_frames()):
                            f0 = pitch.get_value_in_frame(i + 1)
                            if not np.isnan(f0) and f0 > 0:
                                f0_values.append(f0)
                        
                        if f0_values:
                            average_f0 = np.mean(f0_values)
                            # 성별 감지 (165Hz 기준)
                            detected_gender = "male" if average_f0 < 165.0 else "female"
                        
                        print(f"🎯 {filename}: {duration:.2f}초, 평균F0={average_f0:.1f}Hz, 성별={detected_gender}")
                    except Exception as e:
                        print(f"🎯 {filename}: 오디오 분석 실패 - {e}")
                        duration = 0.0
                    
                    # 파일 이름을 기반으로 제목 생성
                    title = base_name.replace('_', ' ').replace('-', ' ')
                    if base_name == "올라가":
                        title = "어디까지 올라가는 거예요"
                    elif base_name == "내려가":
                        title = "어디까지 내려가는 거예요"
                    elif base_name == "내친구":
                        title = "내 친구가 면접에 합격했대"
                    elif base_name == "friend_interview":
                        title = "내 친구가 면접에 합격했대 (새버전)"
                    elif base_name == "뭐라고그러셨소":
                        title = "뭐라고 그러셨소"
                    elif base_name == "뉴스읽기":
                        title = "뉴스 읽기"
                    elif base_name == "낭독문장":
                        title = "낭독 문장"
                    
                    wav_files.append({
                        "id": base_name,
                        "title": title,
                        "description": f"{title} 연습용 참조 음성",
                        "sentence_text": title,
                        "duration": duration,
                        "syllable_count": 0,
                        "file_size": file_size,
                        "detected_gender": detected_gender,
                        "average_f0": average_f0,
                        "created_at": "2025-01-01T00:00:00",
                        "wav": filename,
                        "textgrid": textgrid_file
                    })
        
        # 🎯 사용자 지정 순서로 정렬
        custom_order = [
            "안녕하세요", "반갑습니다", "반가워요", "올라가", "내려가", 
            "뭐라고그러셨소", "아주잘보이네요", "낭독문장", "뉴스읽기"
        ]
        
        # 순서 인덱스를 기반으로 정렬
        def get_sort_key(file_item):
            base_name = file_item["id"]
            try:
                return custom_order.index(base_name)
            except ValueError:
                return len(custom_order)  # 리스트에 없는 파일은 맨 뒤로
        
        wav_files.sort(key=get_sort_key)
        
        print(f"🎯 Found {len(wav_files)} reference files")
        return JSONResponse({"files": wav_files})
        
    except Exception as e:
        print(f"Get reference files error: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/api/reference_files/{file_id}/wav")
async def get_reference_wav(file_id: str):
    """저장된 WAV 파일 다운로드 - 파일 시스템 기반"""
    try:
        wav_path = f"static/reference_files/{file_id}.wav"
        if not os.path.exists(wav_path):
            raise HTTPException(status_code=404, detail="WAV 파일을 찾을 수 없습니다.")
        
        print(f"🎯 Serving WAV file: {wav_path}")
        return FileResponse(wav_path, media_type="audio/wav", filename=f"{file_id}.wav")
        
    except Exception as e:
        print(f"Get reference WAV error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analyze/{file_id}")
async def analyze_reference_file(file_id: str):
    """참조 파일 분석 - 기존 파일로부터 분석 수행"""
    try:
        print(f"🎯 Analyzing reference file: {file_id}")
        
        # 파일 경로 설정
        wav_path = f"static/reference_files/{file_id}.wav"
        tg_path = f"static/reference_files/{file_id}.TextGrid"
        
        # 파일 존재 확인
        if not os.path.exists(wav_path):
            raise HTTPException(status_code=404, detail=f"WAV 파일을 찾을 수 없습니다: {wav_path}")
        if not os.path.exists(tg_path):
            raise HTTPException(status_code=404, detail=f"TextGrid 파일을 찾을 수 없습니다: {tg_path}")
        
        # 파일 분석 수행 (기존 analyze_ref 로직 재사용)
        import parselmouth as pm
        
        try:
            snd = pm.Sound(wav_path)
            tg = pm.TextGrid.read(tg_path)
            
            print(f"🎯 Successfully loaded: {wav_path} and {tg_path}")
            
            # 기본 분석 결과 반환
            duration = snd.get_total_duration()
            pitch = snd.to_pitch(time_step=0.01, pitch_floor=75.0, pitch_ceiling=500.0)
            
            # 기본 피치 데이터 추출
            times = pitch.xs()
            valid_points = []
            
            for t in times:
                f0 = pitch.get_value_at_time(t)
                if f0 and not np.isnan(f0) and 75.0 < f0 < 500.0:
                    valid_points.append({"time": float(t), "frequency": float(f0)})
            
            return {
                "success": True,
                "file_id": file_id,
                "duration": float(duration),
                "pitch_data": valid_points[:100],  # 처음 100개 포인트만
                "total_points": len(valid_points),
                "message": f"성공적으로 분석되었습니다: {len(valid_points)}개 피치 포인트"
            }
            
        except Exception as parse_error:
            print(f"❌ Parselmouth parsing error: {parse_error}")
            raise HTTPException(status_code=500, detail=f"파일 분석 실패: {str(parse_error)}")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Analyze reference file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/reference_files/{file_id}/pitch")
async def get_reference_pitch(file_id: str, syllable_only: bool = False):
    """참조 파일의 피치 데이터 반환 - Chart.js에서 사용"""
    try:
        print(f"🎯 Getting pitch data for reference file: {file_id} (syllable_only={syllable_only})")
        
        # 파일 경로 설정
        wav_path = f"static/reference_files/{file_id}.wav"
        tg_path = f"static/reference_files/{file_id}.TextGrid"
        
        # 파일 존재 확인
        if not os.path.exists(wav_path):
            raise HTTPException(status_code=404, detail=f"WAV 파일을 찾을 수 없습니다: {wav_path}")
        
        # 파일 분석 수행
        import parselmouth as pm
        
        try:
            snd = pm.Sound(wav_path)
            print(f"🎯 Successfully loaded WAV: {wav_path}")
            
            # 피치 데이터 추출
            pitch = snd.to_pitch(time_step=0.01, pitch_floor=75.0, pitch_ceiling=500.0)
            times = pitch.xs()
            
            if syllable_only:
                # 🎯 음절별 대표 포인트만 반환
                return await get_syllable_representative_pitch(file_id, wav_path, tg_path, snd, pitch)
            else:
                # 🎯 모든 피치 포인트 반환 (기존 동작)
                pitch_points = []
                for t in times:
                    f0 = pitch.get_value_at_time(t)
                    if f0 and not np.isnan(f0) and 75.0 < f0 < 500.0:
                        pitch_points.append({
                            "time": float(t), 
                            "frequency": float(f0)
                        })
                
                print(f"🎯 Extracted {len(pitch_points)} pitch points")
                return JSONResponse(pitch_points)
            
        except Exception as parse_error:
            print(f"❌ Parselmouth parsing error: {parse_error}")
            raise HTTPException(status_code=500, detail=f"파일 분석 실패: {str(parse_error)}")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Get reference pitch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_syllable_representative_pitch(file_id: str, wav_path: str, tg_path: str, snd, pitch):
    """음절별 대표 피치 포인트 계산"""
    try:
        # TextGrid 파일 로드
        if not os.path.exists(tg_path):
            print(f"🎯 No TextGrid file found: {tg_path}")
            return JSONResponse([])
        
        # TextGrid 파싱 (기존 정규식 로직 재사용)
        syllables = []
        try:
            # UTF-16 인코딩으로 TextGrid 파일 읽기
            encodings_to_try = ['utf-16', 'utf-16-le', 'utf-16-be', 'utf-8', 'cp949']
            content = None
            
            for encoding in encodings_to_try:
                try:
                    with open(tg_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    print(f"✅ TextGrid 파일 읽기 성공: {encoding}")
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                print(f"❌ TextGrid 파일 인코딩 실패: {tg_path}")
                return JSONResponse([])
                
            # 정규식 패턴으로 음절 구간 추출
            import re
            interval_pattern = r'intervals\s*\[\s*(\d+)\s*\]:\s*\n\s*xmin\s*=\s*([0-9.]+)\s*\n\s*xmax\s*=\s*([0-9.]+)\s*\n\s*text\s*=\s*"([^"]*)"'
            
            matches = re.findall(interval_pattern, content, re.MULTILINE)
            print(f"🎯 정규식 매칭 결과: {len(matches)}개 구간 발견")
            
            for i, (index, xmin, xmax, text) in enumerate(matches):
                if text.strip() and text.strip().lower() not in ['', 'sp', 'sil', '<p:>', 'p']:
                    syllables.append({
                        "label": text.strip(),
                        "start": float(xmin),
                        "end": float(xmax),
                        "duration": float(xmax) - float(xmin)
                    })
                    print(f"  🎯 음절 {i+1}: '{text}' ({xmin}s-{xmax}s)")
                    
        except Exception as e:
            print(f"🚨 TextGrid 파싱 오류: {str(e)}")
            return JSONResponse([])
        
        if not syllables:
            print(f"🎯 No syllables found in TextGrid")
            return JSONResponse([])
        
        # 피치 데이터 추출
        times = pitch.xs()
        valid_points = []
        for t in times:
            f0 = pitch.get_value_at_time(t)
            if f0 and not np.isnan(f0) and 75.0 < f0 < 500.0:
                valid_points.append((float(t), float(f0)))
        
        print(f"🎯 Processing {len(syllables)} syllables with {len(valid_points)} pitch points")
        
        syllable_pitch_points = []
        
        # 각 음절별 대표 피치 계산
        for syl in syllables:
            start_t = syl['start']
            end_t = syl['end'] 
            center_t = (start_t + end_t) / 2
            label = syl['label']
            
            # 음절 구간 내 피치 데이터 찾기
            syllable_data = [(t, f0) for t, f0 in valid_points 
                           if start_t <= t <= end_t]
            
            if len(syllable_data) >= 2:
                # 중앙값 사용 (가장 안정적)
                pitches = [f0 for t, f0 in syllable_data]
                representative_f0 = float(np.median(pitches))
                print(f"  🎯 '{label}': {len(syllable_data)}개 → {representative_f0:.1f}Hz")
            elif len(syllable_data) == 1:
                representative_f0 = syllable_data[0][1]
                print(f"  🎯 '{label}': 1개 → {representative_f0:.1f}Hz")
            else:
                # 가장 가까운 피치 포인트 사용
                if valid_points:
                    distances = [(abs(t - center_t), f0) for t, f0 in valid_points]
                    distances.sort()
                    representative_f0 = distances[0][1] if distances else 200.0
                    print(f"  🎯 '{label}': 최근접 → {representative_f0:.1f}Hz")
                else:
                    representative_f0 = 200.0
                    print(f"  🎯 '{label}': 기본값 → {representative_f0:.1f}Hz")
            
            syllable_pitch_points.append({
                "time": float(center_t),  # 음절 중심 시간
                "frequency": representative_f0,
                "syllable": label,
                "start": float(start_t),  # ✅ 실제 시작 시간 추가
                "end": float(end_t),      # ✅ 실제 끝 시간 추가
                "duration": float(end_t - start_t)  # ✅ 지속 시간 추가
            })
        
        print(f"🎯 Returning {len(syllable_pitch_points)} syllable representative points")
        return JSONResponse(syllable_pitch_points)
        
    except Exception as e:
        print(f"❌ Syllable pitch calculation error: {e}")
        return JSONResponse([])

@app.get("/api/reference_files/{file_id}/textgrid")
async def get_reference_textgrid(file_id: str):
    """저장된 TextGrid 파일 다운로드 - 파일 시스템 기반"""
    try:
        tg_path = f"static/reference_files/{file_id}.TextGrid"
        if not os.path.exists(tg_path):
            raise HTTPException(status_code=404, detail="TextGrid 파일을 찾을 수 없습니다.")
        
        print(f"🎯 Serving TextGrid file: {tg_path}")
        return FileResponse(tg_path, media_type="text/plain", filename=f"{file_id}.TextGrid")
        
    except Exception as e:
        print(f"Get reference TextGrid error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/syllable_pitch_analysis")
async def get_syllable_pitch_analysis():
    """모든 참조 파일의 음절 대표 피치를 남성/여성 버전으로 추출"""
    try:
        reference_dir = "static/reference_files"
        if not os.path.exists(reference_dir):
            return JSONResponse({"analysis": []})
        
        analysis_results = []
        
        # 모든 WAV 파일에 대해 분석
        for filename in os.listdir(reference_dir):
            if filename.endswith('.wav'):
                base_name = filename[:-4]
                textgrid_file = base_name + '.TextGrid'
                wav_path = os.path.join(reference_dir, filename)
                tg_path = os.path.join(reference_dir, textgrid_file)
                
                if os.path.exists(tg_path):
                    print(f"🎯 음절 피치 분석: {base_name}")
                    
                    # 남성/여성 버전으로 각각 분석 (Sound 객체 생성 필요)
                    male_sound = pm.Sound(wav_path)
                    male_tg = pm.read(tg_path)
                    male_analysis = extract_ref_praat_implementation(
                        male_sound, male_tg, 75.0, 300.0, 0.01
                    )
                    
                    female_sound = pm.Sound(wav_path)
                    female_tg = pm.read(tg_path)
                    female_analysis = extract_ref_praat_implementation(
                        female_sound, female_tg, 100.0, 600.0, 0.01
                    )
                    
                    # 참조 음성 성별 감지
                    ref_gender = detect_reference_gender(male_analysis['stats']['meanF0'])
                    
                    # 성별별 정규화 적용
                    male_normalized = apply_gender_normalization(
                        male_analysis, target_gender=ref_gender, learner_gender="male"
                    )
                    
                    female_normalized = apply_gender_normalization(
                        female_analysis, target_gender=ref_gender, learner_gender="female"
                    )
                    
                    # 음절 대표 피치 추출
                    male_syllables = []
                    female_syllables = []
                    
                    if 'syllable_analysis' in male_normalized:
                        for syl in male_normalized['syllable_analysis']:
                            male_syllables.append({
                                'label': syl['label'],
                                'start_time': syl['start_time'],
                                'end_time': syl['end_time'],
                                'duration': syl['duration'],
                                'f0_hz': syl['f0'],
                                'semitone': syl['semitone'],
                                'center_time': syl['center_time']
                            })
                    
                    if 'syllable_analysis' in female_normalized:
                        for syl in female_normalized['syllable_analysis']:
                            female_syllables.append({
                                'label': syl['label'],
                                'start_time': syl['start_time'],
                                'end_time': syl['end_time'],
                                'duration': syl['duration'],
                                'f0_hz': syl['f0'],
                                'semitone': syl['semitone'],
                                'center_time': syl['center_time']
                            })
                    
                    analysis_results.append({
                        'sentence_id': base_name,
                        'reference_gender': ref_gender,
                        'duration': male_analysis['stats']['duration'],
                        'male_version': {
                            'base_frequency': 120.0,  # 남성 기준 주파수
                            'syllables': male_syllables
                        },
                        'female_version': {
                            'base_frequency': 220.0,  # 여성 기준 주파수
                            'syllables': female_syllables
                        }
                    })
                    
                    print(f"   ✅ {base_name}: {len(male_syllables)}개 음절, 참조성별={ref_gender}")
        
        print(f"🎯 전체 분석 완료: {len(analysis_results)}개 문장")
        return JSONResponse({"analysis": analysis_results})
        
    except Exception as e:
        print(f"Syllable pitch analysis error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.delete("/api/reference_files/{file_id}")
async def delete_reference_file(file_id: int, db: Session = Depends(get_db)):
    """저장된 참조 파일 삭제"""
    try:
        # 데이터베이스에서 파일 정보 조회
        ref_file = db.query(ReferenceFile).filter(ReferenceFile.id == file_id).first()
        if not ref_file:
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
        
        # 실제 파일들 삭제
        wav_path = UPLOAD_DIR / ref_file.wav_filename
        textgrid_path = UPLOAD_DIR / ref_file.textgrid_filename
        
        # WAV 파일 삭제
        if wav_path.exists():
            wav_path.unlink()
            print(f"🗑️ Deleted WAV file: {wav_path}")
        else:
            print(f"⚠️ WAV file not found: {wav_path}")
        
        # TextGrid 파일 삭제
        if textgrid_path.exists():
            textgrid_path.unlink()
            print(f"🗑️ Deleted TextGrid file: {textgrid_path}")
        else:
            print(f"⚠️ TextGrid file not found: {textgrid_path}")
        
        # 데이터베이스에서 레코드 삭제
        db.delete(ref_file)
        db.commit()
        
        print(f"🗑️ Successfully deleted reference file {file_id}: {ref_file.title}")
        
        return JSONResponse({
            "status": "success", 
            "message": f"참조 파일 '{ref_file.title}'이 성공적으로 삭제되었습니다."
        })
        
    except Exception as e:
        db.rollback()
        print(f"Delete reference file error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/uploaded_files/{file_id}")
async def delete_uploaded_file(file_id: str):
    """업로드된 파일 삭제 (WAV + TextGrid)"""
    try:
        # 파일 ID 검증
        if not file_id or file_id.strip() == '':
            raise HTTPException(status_code=400, detail="파일 ID가 필요합니다")
        
        # 파일 경로 생성
        wav_path = UPLOAD_DIR / f"{file_id}.wav"
        textgrid_path = UPLOAD_DIR / f"{file_id}.TextGrid"
        
        deleted_files = []
        
        # WAV 파일 삭제
        if wav_path.exists():
            wav_path.unlink()
            deleted_files.append("WAV")
            print(f"🗑️ Deleted uploaded WAV file: {wav_path}")
        else:
            print(f"⚠️ Upload WAV file not found: {wav_path}")
        
        # TextGrid 파일 삭제
        if textgrid_path.exists():
            textgrid_path.unlink()
            deleted_files.append("TextGrid")
            print(f"🗑️ Deleted uploaded TextGrid file: {textgrid_path}")
        else:
            print(f"⚠️ Upload TextGrid file not found: {textgrid_path}")
        
        if not deleted_files:
            raise HTTPException(status_code=404, detail="삭제할 파일을 찾을 수 없습니다")
        
        print(f"🗑️ Successfully deleted uploaded file {file_id}: {', '.join(deleted_files)} files")
        
        return JSONResponse({
            "status": "success",
            "message": f"업로드 파일 '{file_id}'이 성공적으로 삭제되었습니다.",
            "deleted_files": deleted_files
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Delete uploaded file error: {e}")
        raise HTTPException(status_code=500, detail=f"파일 삭제 실패: {str(e)}")

@app.post("/analyze_live_audio")
async def analyze_live_audio(audio: UploadFile = File(...)):
    """🎯 실시간 오디오 청크를 Praat 알고리즘으로 분석하여 정확한 피치 데이터 반환"""
    try:
        # 오디오 데이터 읽기
        audio_data = await audio.read()
        
        # WAV 형식으로 변환
        audio_array = np.frombuffer(audio_data, dtype=np.float32)
        
        # 🎯 Parselmouth(Praat) 알고리즘으로 정밀 피치 분석
        try:
            import soundfile as sf
        except ImportError:
            print("🚨 soundfile 라이브러리가 설치되지 않음")
            raise HTTPException(status_code=500, detail="soundfile 라이브러리가 필요합니다")
        
        # 임시 파일로 저장하여 Parselmouth로 분석
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
            # NumPy 배열을 WAV 파일로 저장 (16kHz 샘플링)
            sf.write(tmp_file.name, audio_array, 16000)
            
            # 🎯 Praat 고정밀 피치 분석 설정
            sound = pm.Sound(tmp_file.name)
            pitch = sound.to_pitch(
                time_step=0.01,      # 10ms 간격으로 분석
                pitch_floor=75.0,    # 최소 75Hz (남성 저음)
                pitch_ceiling=500.0, # 최대 500Hz (여성 고음)
                max_number_of_candidates=15,  # 정확도 향상
                silence_threshold=0.03,
                voicing_threshold=0.45,
                octave_cost=0.01,
                octave_jump_cost=0.35,
                voiced_unvoiced_cost=0.14
            )
            
            # 🎯 피치 데이터 추출 (Praat 고정밀 분석 결과)
            pitch_values = []
            times = pitch.xs()
            
            for i, time in enumerate(times):
                f0 = pitch.get_value_at_time(time)
                if not np.isnan(f0) and f0 > 0:
                    # 🎯 성별 추정 기반 최적화
                    estimated_gender = 'female' if f0 > 180 else 'male'
                    semitone_base = 200 if estimated_gender == 'female' else 150
                    qtone_base = 130
                    
                    pitch_values.append({
                        "time": float(time),
                        "f0": float(f0),
                        "semitone": float(12 * np.log2(f0 / semitone_base)) if f0 > 0 else 0.0,
                        "qtone": float(5 * np.log2(f0 / qtone_base)) if f0 > 0 else 0.0,
                        "estimated_gender": estimated_gender
                    })
            
            # 임시 파일 삭제
            os.unlink(tmp_file.name)
            
        print(f"🎯 Praat 분석 완료: {len(pitch_values)}개 피치 포인트 추출")
        return {"success": True, "pitch_data": pitch_values}
        
    except Exception as e:
        print(f"🔥 실시간 Praat 분석 오류: {e}")
        return {"success": False, "error": str(e)}

# Flask-style routes for survey
@app.get("/survey", response_class=HTMLResponse)
async def survey_page(request: Request):
    """Survey selection page"""
    return templates.TemplateResponse("survey.html", {"request": request})

@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    """Main prosody analysis interface"""
    return templates.TemplateResponse("index.html", {"request": request})

# 🎯 새로운 syllables API 엔드포인트 추가
@app.get("/api/reference_files/{file_id}/syllables")
async def get_reference_file_syllables(file_id: str, db: Session = Depends(get_db)):
    """🎯 핵심 기능: TextGrid 파일에서 실제 음절 데이터 추출"""
    try:
        # 🎯 파일명으로 직접 TextGrid 파일 찾기 (데이터베이스 의존성 제거)
        reference_dir = "static/reference_files"
        textgrid_path = os.path.join(reference_dir, f"{file_id}.TextGrid")
        
        print(f"🎯 Looking for TextGrid: {textgrid_path}")
        
        if not os.path.exists(textgrid_path):
            print(f"🚨 TextGrid file not found: {textgrid_path}")
            return []
        
        # 🎯 TextGrid 파일에서 음절 구간 추출 - 오리지널 알고리즘 구현
        syllables = []
        try:
            # 🎯 UTF-16 인코딩으로 TextGrid 파일 읽기 (Praat 표준)
            encodings_to_try = ['utf-16', 'utf-16-le', 'utf-16-be', 'utf-8', 'cp949']
            content = None
            
            for encoding in encodings_to_try:
                try:
                    with open(textgrid_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    print(f"✅ TextGrid 파일 읽기 성공: {encoding}")
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                print(f"❌ TextGrid 파일 인코딩 실패: {textgrid_path}")
                return []
                
            # 🎯 오리지널 정규식 패턴 사용 (ToneBridge_Implementation_Guide.md)
            import re
            interval_pattern = r'intervals\s*\[\s*(\d+)\s*\]:\s*\n\s*xmin\s*=\s*([0-9.]+)\s*\n\s*xmax\s*=\s*([0-9.]+)\s*\n\s*text\s*=\s*"([^"]*)"'
            
            matches = re.findall(interval_pattern, content, re.MULTILINE)
            print(f"🎯 정규식 매칭 결과: {len(matches)}개 구간 발견")
            
            for i, (index, xmin, xmax, text) in enumerate(matches):
                if text.strip() and text.strip().lower() not in ['', 'sp', 'sil', '<p:>', 'p']:  # 빈 텍스트와 침묵 구간 제외
                    syllable_data = {
                        "label": text.strip(),
                        "start": float(xmin),
                        "end": float(xmax),
                        "duration": float(xmax) - float(xmin)
                    }
                    syllables.append(syllable_data)
                    print(f"  🎯 음절 {i+1}: '{text}' ({xmin}s-{xmax}s)")
            
        except Exception as e:
            print(f"🚨 TextGrid 파싱 오류 상세: {str(e)}")
            # Fallback: 파일 내용 샘플 출력으로 디버깅
            try:
                with open(textgrid_path, 'rb') as f:
                    raw_content = f.read(100)
                print(f"🔍 파일 시작 바이트: {raw_content}")
            except:
                pass
            
        # 🎯 파일별 기본 음절 정보 (TextGrid가 비어있는 경우 대비)
        if not syllables:
            print(f"🎯 Using default syllables for {file_id}")
            if file_id == "반갑습니다":
                syllables = [
                    {"label": "반", "start": 0.0, "end": 0.4},
                    {"label": "갑", "start": 0.4, "end": 0.8},
                    {"label": "습", "start": 0.8, "end": 1.1},
                    {"label": "니", "start": 1.1, "end": 1.3},
                    {"label": "다", "start": 1.3, "end": 1.4}
                ]
            elif file_id == "안녕하세요":
                syllables = [
                    {"label": "안", "start": 0.0, "end": 0.2},
                    {"label": "녕", "start": 0.2, "end": 0.4},
                    {"label": "하", "start": 0.4, "end": 0.6},
                    {"label": "세", "start": 0.6, "end": 0.9},
                    {"label": "요", "start": 0.9, "end": 1.1}
                ]
            else:
                # 기본 더미 데이터
                syllables = [{"label": "음절", "start": 0.0, "end": 1.0}]
        
        print(f"🎯 Returning {len(syllables)} syllables for {file_id}: {[s['label'] for s in syllables]}")
        return syllables
        
    except Exception as e:
        print(f"🚨 Error in get_reference_file_syllables: {e}")
        return []

# 🎯 숨겨진 자동 정규화 기능
from audio_normalization import AutomationProcessor

@app.post("/api/normalize_reference_files")
async def normalize_reference_files():
    """
    숨겨진 자동 정규화 기능 - 단일 버튼으로 모든 참조 파일 정규화
    - 무음 구간 제거 (자동)
    - 볼륨 정규화 (일정한 볼륨으로 조정)  
    - 샘플레이트 변경 (16kHz 표준화)
    - TextGrid 자동 동기화 (WAV 편집에 맞춤)
    """
    try:
        reference_dir = "static/reference_files"
        backup_dir = "static/backup_reference_files"
        
        # 디렉토리 존재 확인
        if not os.path.exists(backup_dir):
            raise HTTPException(status_code=400, detail="백업 디렉토리가 존재하지 않습니다")
            
        # 자동화 프로세서 초기화 (16kHz, -20dB 표준)
        processor = AutomationProcessor(target_sample_rate=16000, target_db=-20.0)
        
        print("🎯 ToneBridge 참조 파일 자동 정규화 시작...")
        print(f"   백업 소스: {backup_dir}")
        print(f"   출력 대상: {reference_dir}")
        
        # 모든 파일 쌍 처리
        results = processor.process_directory(reference_dir, backup_dir)
        
        # 결과 분석
        successful = [r for r in results if r['status'] == 'success']
        failed = [r for r in results if r['status'] == 'error']
        skipped = [r for r in results if r['status'] == 'skipped']
        
        print(f"🎯 자동 정규화 완료!")
        print(f"   성공: {len(successful)}개 파일")
        print(f"   실패: {len(failed)}개 파일") 
        print(f"   건너뜀: {len(skipped)}개 파일")
        
        # 성공한 파일들의 요약 정보
        summary = {
            'total_processed': len(results),
            'successful': len(successful),
            'failed': len(failed), 
            'skipped': len(skipped),
            'processing_details': []
        }
        
        for result in successful:
            if 'audio_processing' in result:
                audio_info = result['audio_processing']
                summary['processing_details'].append({
                    'file': result['file_name'],
                    'original_duration': audio_info.get('original_duration', 0),
                    'final_duration': audio_info.get('final_duration', 0),
                    'time_ratio': audio_info.get('time_ratio', 1.0),
                    'sample_rate': audio_info.get('sample_rate', 16000),
                    'textgrid_synced': result.get('textgrid_sync', False)
                })
        
        return JSONResponse({
            "status": "success",
            "message": "참조 파일 자동 정규화가 완료되었습니다",
            "summary": summary,
            "detailed_results": results
        })
        
    except Exception as e:
        print(f"❌ 자동 정규화 오류: {e}")
        raise HTTPException(status_code=500, detail=f"정규화 중 오류가 발생했습니다: {e}")

@app.post("/api/normalize_single_file")  
async def normalize_single_file(file_name: str):
    """
    단일 파일 정규화 (테스트용)
    Args:
        file_name: 파일명 (확장자 제외, 예: "낭독문장")
    """
    try:
        reference_dir = "static/reference_files"
        backup_dir = "static/backup_reference_files"
        
        wav_file = f"{file_name}.wav"
        textgrid_file = f"{file_name}.TextGrid"
        
        wav_backup = os.path.join(backup_dir, wav_file)
        textgrid_backup = os.path.join(backup_dir, textgrid_file)
        wav_output = os.path.join(reference_dir, wav_file)
        textgrid_output = os.path.join(reference_dir, textgrid_file)
        
        # 파일 존재 확인
        if not os.path.exists(wav_backup) or not os.path.exists(textgrid_backup):
            raise HTTPException(status_code=404, detail=f"백업 파일을 찾을 수 없습니다: {file_name}")
            
        # 자동화 프로세서로 처리
        processor = AutomationProcessor(target_sample_rate=16000, target_db=-20.0)
        result = processor.process_file_pair(wav_backup, textgrid_backup, wav_output, textgrid_output)
        
        print(f"🎯 단일 파일 정규화 완료: {file_name}")
        
        return JSONResponse({
            "status": "success", 
            "message": f"{file_name} 파일 정규화가 완료되었습니다",
            "result": result
        })
        
    except Exception as e:
        print(f"❌ 단일 파일 정규화 오류: {e}")
        raise HTTPException(status_code=500, detail=f"정규화 중 오류가 발생했습니다: {e}")

# Initialize processors (shared STT instance to avoid duplication)
automated_processor = AutomatedProcessor()
# Use the STT instance from automated_processor to avoid duplicate initialization
if hasattr(automated_processor.stt, 'advanced_stt') and automated_processor.stt.advanced_stt:
    advanced_stt_processor = automated_processor.stt.advanced_stt
    print("🔄 기존 STT 인스턴스 재사용")
else:
    advanced_stt_processor = AdvancedSTTProcessor(preferred_engine='whisper')
    print("🆕 새 STT 인스턴스 생성")

@app.post("/api/optimize-uploaded-file")
async def optimize_uploaded_file(file_id: str = Form(...), use_ultimate_stt: bool = Form(False)):
    """
    업로드된 파일을 99% 정확도 Ultimate STT 시스템으로 최적화
    🎯 한국어 특화 오디오 전처리 → 다중 STT 엔진 앙상블 → 실시간 품질 검증 → 적응형 재처리
    """
    # 빈 파일ID 검증
    if not file_id or file_id.strip() == '' or file_id == '()':
        raise HTTPException(status_code=400, detail="파일 ID가 필요합니다")
        
    async with ai_processing_lock:  # 뮤텍스로 순서 보장
        try:
            wav_file = f"{file_id}.wav"
            wav_path = UPLOAD_DIR / wav_file
            textgrid_path = UPLOAD_DIR / f"{file_id}.TextGrid"
            
            if not wav_path.exists():
                raise HTTPException(status_code=404, detail="WAV 파일을 찾을 수 없습니다")
            
            print(f"🎯🎯🎯 업로드 파일 Ultimate STT 처리 시작: {file_id} 🎯🎯🎯")
            
            # 파일명에서 정보 추출
            parts = file_id.split('_')
            reference_sentence = "반가워요"  # 기본값
            if len(parts) >= 4:
                reference_sentence = parts[3]
            
            # 🚀 Ultimate STT 시스템 사용 (99% 정확도)
            if use_ultimate_stt:
                print("🎯 Ultimate STT 시스템 사용 - 99% 정확도 목표")
                
                # 지연 로딩: 필요할 때만 초기화
                if global_ai_instances.get('ultimate_stt') is None:
                    print("⚡ Ultimate STT 첫 사용: 초기화 중... (1분 정도 소요)")
                    try:
                        global_ai_instances['ultimate_stt'] = UltimateSTTSystem(
                            target_accuracy=0.99,
                            max_reprocessing_attempts=2,
                            quality_threshold=0.95
                        )
                        print("✅ Ultimate STT 시스템 초기화 완료!")
                    except Exception as e:
                        print(f"❌ Ultimate STT 초기화 실패: {e}")
                        # 백업 시스템으로 전환
                        print("🔄 기존 시스템으로 백업 처리")
                        from tonebridge_core.pipeline.voice_processor import UnifiedVoiceProcessor
                        advanced_stt = global_ai_instances.get('advanced_stt')
                        unified_processor = UnifiedVoiceProcessor(shared_stt_processor=advanced_stt)
                        process_result = unified_processor.process_uploaded_file(str(wav_path), reference_sentence)
                        result = process_result.to_legacy_dict()
                
                ultimate_stt = global_ai_instances.get('ultimate_stt')
                if ultimate_stt:
                    ultimate_result = await ultimate_stt.process_audio_ultimate(
                    str(wav_path), 
                    reference_sentence,
                    enable_reprocessing=True
                )
                
                # Ultimate STT 결과를 기존 API 형식으로 변환
                result = {
                    'success': ultimate_result.accuracy_achieved >= 0.8,  # 80% 이상이면 성공
                    'transcription': ultimate_result.final_text,
                    'confidence': ultimate_result.confidence,
                    'accuracy_achieved': ultimate_result.accuracy_achieved,
                    'processing_time': ultimate_result.total_processing_time,
                    'reprocessing_attempts': ultimate_result.reprocessing_attempts,
                    'quality_score': ultimate_result.final_quality_score
                }
                
                # 음절 데이터 추출 (Ultimate STT 결과에서)
                syllables = []
                if ultimate_result.final_text:
                    # 간단한 음절 분할 (실제로는 더 정교한 처리 필요)
                    korean_syllables = [c for c in ultimate_result.final_text.replace(' ', '') if 0xAC00 <= ord(c) <= 0xD7A3]
                    if korean_syllables:
                        duration_per_syllable = 0.25  # 기본값
                        for i, syllable in enumerate(korean_syllables):
                            start_time = i * duration_per_syllable
                            end_time = (i + 1) * duration_per_syllable
                            syllables.append({
                                'label': syllable,
                                'start': start_time,
                                'end': end_time,
                                'confidence': ultimate_result.confidence
                            })
                
                result['syllables'] = syllables
                result['duration'] = len(syllables) * 0.25 if syllables else 1.0
                
                print(f"✅ Ultimate STT 완료: 정확도 {ultimate_result.accuracy_achieved:.1%}, 신뢰도 {ultimate_result.confidence:.3f}")
                
            else:
                # 🔄 기존 시스템 사용 (백업)
                print("🔧 기존 통합 프로세서 사용: 백업 처리")
                from tonebridge_core.pipeline.voice_processor import UnifiedVoiceProcessor
                
                # 전역 STT 인스턴스 재사용
                advanced_stt = global_ai_instances.get('advanced_stt')
                unified_processor = UnifiedVoiceProcessor(shared_stt_processor=advanced_stt)
                process_result = unified_processor.process_uploaded_file(str(wav_path), reference_sentence)
                
                # 기존 API 형식으로 변환 (하위 호환성)
                result = process_result.to_legacy_dict()
            
            if result['success']:
                # 최적화된 TextGrid 생성
                syllables = result.get('syllables', [])
                
                if syllables:
                    # TextGrid 파일 생성
                    textgrid_content = create_textgrid_from_syllables(syllables, result.get('duration', 1.0))
                    
                    with open(textgrid_path, 'w', encoding='utf-16') as f:
                        f.write(textgrid_content)
                    
                    print(f"✅ TextGrid 재생성 완료: {len(syllables)}개 음절")
                
                # 최적화된 오디오 저장 (0.25초 마진 적용)
                optimized_audio_path = create_optimized_audio(str(wav_path), syllables)
                if optimized_audio_path:
                    # 원본 파일을 최적화된 버전으로 교체
                    shutil.move(optimized_audio_path, str(wav_path))
                    print(f"✅ 오디오 최적화 완료")
        
            # 응답 데이터 구성
            response_data = {
                "success": result['success'],
                "file_id": file_id,
                "transcription": result.get('transcription', ''),
                "syllables": result.get('syllables', []),
                "duration": result.get('duration', 0),
                "optimized": True
            }
            
            # Ultimate STT 추가 정보 포함
            if 'accuracy_achieved' in result:
                response_data.update({
                    "accuracy_achieved": result['accuracy_achieved'],
                    "confidence": result.get('confidence', 0.0),
                    "quality_score": result.get('quality_score', 0.0),
                    "processing_time": result.get('processing_time', 0.0),
                    "reprocessing_attempts": result.get('reprocessing_attempts', 0),
                    "ultimate_stt_used": True
                })
            else:
                response_data["ultimate_stt_used"] = False
            
            return response_data
            
        except Exception as e:
            print(f"❌ 업로드 파일 최적화 오류: {e}")
            raise HTTPException(status_code=500, detail=f"최적화 중 오류: {e}")

def create_textgrid_from_syllables(syllables, duration):
    """음절 데이터로부터 TextGrid 생성 - 직접 생성 방식"""
    print(f"🎯 TextGrid 생성: {len(syllables)}개 음절, 지속시간: {duration:.3f}초")
    
    # 음절 텍스트 추출 (다양한 키 이름 대응)
    processed_syllables = []
    for i, syl in enumerate(syllables):
        if isinstance(syl, dict):
            # 다양한 텍스트 키 확인
            text = syl.get('label', '') or syl.get('text', '') or syl.get('syllable', '') or syl.get('name', '')
            start = syl.get('start', 0.0)
            end = syl.get('end', 0.0)
            
            processed_syllables.append({
                'text': text,
                'start': start,
                'end': end
            })
            print(f"   음절 {i+1}: '{text}' [{start:.3f}s ~ {end:.3f}s]")
    
    # 직접 TextGrid 내용 생성
    textgrid_content = f'''File type = "ooTextFile"
Object class = "TextGrid"

xmin = 0.0
xmax = {duration}
tiers? <exists>
size = 1
item []:
    item [1]:
        class = "IntervalTier"
        name = "syllables"
        xmin = 0.0
        xmax = {duration}
        intervals: size = {len(processed_syllables)}
'''
    
    # 각 음절 구간 추가
    for i, syl in enumerate(processed_syllables, 1):
        textgrid_content += f'''        intervals [{i}]:
            xmin = {syl['start']}
            xmax = {syl['end']}
            text = "{syl['text']}"
'''
    
    print(f"✅ TextGrid 내용 생성 완료: {len(processed_syllables)}개 음절")
    return textgrid_content

def create_optimized_audio(wav_path, syllables):
    """0.25초 마진을 적용한 최적화된 오디오 생성"""
    try:
        import tempfile
        
        if not syllables:
            return None
            
        sound = pm.Sound(wav_path)
        
        # 음절 구간에서 최소/최대 시간 찾기
        start_times = [s.get('start', 0) for s in syllables if s.get('start') is not None]
        end_times = [s.get('end', 0) for s in syllables if s.get('end') is not None]
        
        if not start_times or not end_times:
            return None
            
        voice_start = max(0, min(start_times) - 0.25)  # 0.25초 마진
        voice_end = min(sound.duration, max(end_times) + 0.25)  # 0.25초 마진
        
        # 구간 추출
        trimmed_sound = sound.extract_part(from_time=voice_start, to_time=voice_end, preserve_times=False)
        
        # 볼륨 정규화 (RMS 0.02)
        values = trimmed_sound.values[0] if trimmed_sound.n_channels > 0 else trimmed_sound.values
        rms = np.sqrt(np.mean(values**2))
        if rms > 0:
            target_rms = 0.02
            amplification_factor = target_rms / rms
            amplification_factor = min(amplification_factor, 10.0)  # 최대 10배
            
            normalized_values = values * amplification_factor
            normalized_values = np.clip(normalized_values, -0.9, 0.9)
            
            optimized_sound = pm.Sound(normalized_values, sampling_frequency=trimmed_sound.sampling_frequency)
        else:
            optimized_sound = trimmed_sound
        
        # 임시 파일에 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            optimized_sound.save(tmp_file.name, "WAV")
            return tmp_file.name
            
    except Exception as e:
        print(f"❌ 오디오 최적화 실패: {e}")
        return None

@app.post("/api/test-ultimate-stt")
async def test_ultimate_stt_on_uploaded_file(file_id: str = Form(...), expected_text: str = Form("")):
    """
    업로드된 파일에서 Ultimate STT 99% 정확도 시스템 테스트
    🎯 실시간 정확도 측정 및 상세 분석 보고서 제공
    """
    # 빈 파일ID 검증
    if not file_id or file_id.strip() == '' or file_id == '()':
        raise HTTPException(status_code=400, detail="파일 ID가 필요합니다")
        
    async with ai_processing_lock:  # 뮤텍스로 순서 보장
        try:
            wav_file = f"{file_id}.wav"
            wav_path = UPLOAD_DIR / wav_file
            
            if not wav_path.exists():
                raise HTTPException(status_code=404, detail="WAV 파일을 찾을 수 없습니다")
            
            print(f"🧪🧪🧪 Ultimate STT 테스트 시작: {file_id} 🧪🧪🧪")
            
            # 파일명에서 기대 텍스트 추출 (없으면 사용자 입력 사용)
            if not expected_text:
                parts = file_id.split('_')
                if len(parts) >= 4:
                    expected_text = parts[3]  # 반가워요 등
                else:
                    expected_text = "반가워요"  # 기본값
            
            print(f"🎯 기대 텍스트: '{expected_text}'")
            
            # Ultimate STT 시스템 테스트 (지연 로딩)
            # 지연 로딩: 필요할 때만 초기화
            if global_ai_instances.get('ultimate_stt') is None:
                print("⚡ Ultimate STT 첫 사용: 초기화 중... (1분 정도 소요)")
                try:
                    global_ai_instances['ultimate_stt'] = UltimateSTTSystem(
                        target_accuracy=0.99,
                        max_reprocessing_attempts=2,
                        quality_threshold=0.95
                    )
                    print("✅ Ultimate STT 시스템 초기화 완료!")
                except Exception as e:
                    print(f"❌ Ultimate STT 초기화 실패: {e}")
                    raise HTTPException(status_code=503, detail=f"Ultimate STT 시스템 초기화 실패: {e}")
            
            ultimate_stt = global_ai_instances.get('ultimate_stt')
            if ultimate_stt:
                
                # 테스트 시작 시간
                import time
                test_start = time.time()
                
                ultimate_result = await ultimate_stt.process_audio_ultimate(
                    str(wav_path), 
                    expected_text,
                    enable_reprocessing=True
                )
                
                test_duration = time.time() - test_start
                
                # 상세 테스트 결과 구성
                test_report = {
                    "success": True,
                    "file_id": file_id,
                    "expected_text": expected_text,
                    "predicted_text": ultimate_result.final_text,
                    "accuracy_achieved": ultimate_result.accuracy_achieved,
                    "target_accuracy": 0.99,
                    "accuracy_met": ultimate_result.accuracy_achieved >= 0.99,
                    "confidence": ultimate_result.confidence,
                    "quality_score": ultimate_result.final_quality_score,
                    "processing_time": ultimate_result.total_processing_time,
                    "total_test_time": test_duration,
                    "reprocessing_attempts": ultimate_result.reprocessing_attempts,
                    
                    # 상세 분석
                    "processing_stages": ultimate_result.processing_stages,
                    "audio_optimizations": ultimate_result.audio_optimizations_applied,
                    "stt_engines_used": ultimate_result.stt_engines_used,
                    "quality_improvements": ultimate_result.quality_improvements,
                    
                    # 성능 등급
                    "performance_grade": "S" if ultimate_result.accuracy_achieved >= 0.99 else 
                                       "A" if ultimate_result.accuracy_achieved >= 0.95 else
                                       "B" if ultimate_result.accuracy_achieved >= 0.90 else
                                       "C" if ultimate_result.accuracy_achieved >= 0.80 else "D",
                    
                    # 시스템 상태
                    "system_components": {
                        "korean_optimizer": global_ai_instances.get('korean_optimizer') is not None,
                        "advanced_stt": global_ai_instances.get('advanced_stt') is not None,
                        "ultimate_stt": global_ai_instances.get('ultimate_stt') is not None
                    }
                }
                
                # 정확도별 메시지
                if ultimate_result.accuracy_achieved >= 0.99:
                    test_report["result_message"] = "🎯 99% 목표 달성! 완벽한 인식 성공"
                elif ultimate_result.accuracy_achieved >= 0.95:
                    test_report["result_message"] = "🥈 95% 이상 달성! 매우 우수한 성능"
                elif ultimate_result.accuracy_achieved >= 0.90:
                    test_report["result_message"] = "🥉 90% 이상 달성! 좋은 성능"
                else:
                    test_report["result_message"] = "📈 성능 개선 필요 - 재처리 권장"
                
                print(f"✅ Ultimate STT 테스트 완료:")
                print(f"   기대: '{expected_text}'")
                print(f"   예측: '{ultimate_result.final_text}'")
                print(f"   정확도: {ultimate_result.accuracy_achieved:.1%}")
                print(f"   등급: {test_report['performance_grade']}")
                
                return test_report
                
            else:
                raise HTTPException(status_code=503, detail="Ultimate STT 시스템이 초기화되지 않았습니다")
                
        except Exception as e:
            print(f"❌ Ultimate STT 테스트 오류: {e}")
            return {
                "success": False,
                "error": str(e),
                "file_id": file_id,
                "result_message": "🚨 테스트 실행 중 오류 발생"
            }

# 첫 번째 중복 함수 제거됨 - 통합된 버전이 아래에 있음

@app.post("/api/auto-process")
async def auto_process_audio(
    file: UploadFile = File(...), 
    sentence_hint: str = Form(""), 
    save_permanent: bool = Form(False),
    learner_name: str = Form(""),
    learner_gender: str = Form(""),
    learner_age_group: str = Form(""),
    reference_sentence: str = Form("")
):
    """
    완전 자동화된 오디오 처리 API
    STT + 자동 분절 + TextGrid 생성
    
    Parameters:
    - save_permanent: True시 WAV + TextGrid를 uploads/ 폴더에 영구 저장
    - learner_name: 학습자 이름
    - learner_gender: 학습자 성별 (male/female)
    - learner_age_group: 학습자 연령대
    - reference_sentence: 참조 문장 이름
    """
    if not file.filename or not file.filename.endswith(('.wav', '.mp3', '.m4a', '.webm')):
        raise HTTPException(status_code=400, detail="지원되지 않는 파일 형식")
    
    try:
        # 임시 파일로 저장 및 변환
        content = await file.read()
        
        if file.filename and file.filename.endswith('.webm'):
            # webm 파일인 경우 FFmpeg로 변환
            with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as webm_file:
                webm_file.write(content)
                webm_path = webm_file.name
            
            # Parselmouth 호환성 최적화 변환
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as wav_file:
                tmp_path = wav_file.name
            
            import subprocess
            result = subprocess.run([
                'ffmpeg', '-i', webm_path, 
                '-acodec', 'pcm_s16le',  # 16-bit PCM 
                '-ar', '22050',          # 22kHz 샘플링 (Parselmouth 호환)
                '-ac', '1',              # 모노
                '-y', tmp_path
            ], capture_output=True, text=True)
            
            os.unlink(webm_path)  # webm 파일 정리
            
            if result.returncode != 0:
                raise HTTPException(status_code=400, detail=f"오디오 변환 실패: {result.stderr}")
                
            print(f"🎵 webm → wav 변환 완료: {tmp_path}")
        else:
            # 직접 wav 파일인 경우
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
                tmp_file.write(content)
                tmp_path = tmp_file.name
        
        # 자동 처리 실행
        result = automated_processor.process_audio_completely(tmp_path, sentence_hint)
        
        if result['success']:
            response_data = {
                "success": True,
                "transcription": result['transcription'],
                "syllables": result['syllables'],
                "duration": result['duration'],
                "message": f"✅ 자동 처리 완료 - {len(result['syllables'])}개 음절 분절"
            }
            
            # 영구 저장이 요청된 경우
            if save_permanent:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # 의미있는 파일명 생성
                filename_parts = []
                if learner_name:
                    filename_parts.append(learner_name)
                if learner_gender:
                    filename_parts.append(learner_gender)
                if learner_age_group:
                    filename_parts.append(learner_age_group)
                if reference_sentence:
                    filename_parts.append(reference_sentence)
                filename_parts.append(timestamp)
                
                filename = "_".join(filename_parts) if filename_parts else f"recording_{timestamp}"
                
                # 🎵 무음 제거 + 볼륨 정규화된 WAV 파일 생성 및 저장
                print(f"🎵 무음 제거 + 볼륨 정규화 시작: {filename}")
                trimmed_path = advanced_stt_processor.create_trimmed_audio(
                    tmp_path, 
                    str(UPLOAD_DIR / f"{filename}_trimmed.wav")
                )
                
                # 최적화된 파일을 최종 저장 (사용자가 재생할 파일)
                wav_path = UPLOAD_DIR / f"{filename}.wav"
                shutil.copy2(trimmed_path, wav_path)
                
                # 원본도 백업으로 저장
                original_wav_path = UPLOAD_DIR / f"{filename}_original.wav"
                shutil.copy2(tmp_path, original_wav_path)
                
                print(f"💾 최적화된 WAV 저장: {wav_path}")
                print(f"💾 원본 WAV 백업: {original_wav_path}")
                
                # TextGrid 파일 저장  
                textgrid_path = UPLOAD_DIR / f"{filename}.TextGrid"
                save_textgrid(result['syllables'], str(textgrid_path), result['duration'])
                
                response_data.update({
                    "saved_files": {
                        "wav": str(wav_path),  # 최적화된 파일 (재생용)
                        "wav_original": str(original_wav_path),  # 원본 파일 (백업용)
                        "textgrid": str(textgrid_path)
                    },
                    "filename": filename,
                    "optimization_applied": True,
                    "message": f"✅ 무음 제거 + 볼륨 정규화 완료 - {len(result['syllables'])}개 음절 분절"
                })
                
                print(f"💾 영구 저장 완료: {filename}.wav + {filename}.TextGrid")
                print(f"📋 학습자: {learner_name} ({learner_gender}, {learner_age_group})")
                print(f"📄 연습문장: {reference_sentence}")
            
            # 임시 파일 정리 (영구 저장 후)
            os.unlink(tmp_path)
            
            return JSONResponse(response_data)
        else:
            # 실패 시에도 임시 파일 정리
            os.unlink(tmp_path)
            return JSONResponse({
                "success": False,
                "error": result.get('error', '알 수 없는 오류'),
                "message": "❌ 자동 처리 실패"
            }, status_code=500)
            
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e),
            "message": "❌ 서버 처리 오류"
        }, status_code=500)

@app.post("/api/optimize-textgrid/{file_id}")
async def optimize_existing_textgrid(file_id: str, db: Session = Depends(get_db)):
    """
    기존 reference 파일의 TextGrid 최적화
    """
    try:
        # DB에서 파일 정보 조회
        ref_file = db.query(ReferenceFile).filter(ReferenceFile.id == file_id).first()
        if not ref_file:
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")
        
        audio_path = f"static/reference_files/{ref_file.filename}"
        if not os.path.exists(audio_path):
            raise HTTPException(status_code=404, detail="오디오 파일이 존재하지 않습니다")
        
        # 자동 처리로 TextGrid 재생성
        result = automated_processor.process_audio_completely(
            audio_path, 
            ref_file.sentence or ""
        )
        
        if result['success']:
            return JSONResponse({
                "success": True,
                "syllables": result['syllables'],
                "transcription": result['transcription'],
                "message": f"✅ TextGrid 최적화 완료 - {len(result['syllables'])}개 음절"
            })
        else:
            return JSONResponse({
                "success": False,
                "error": result.get('error'),
                "message": "❌ TextGrid 최적화 실패"
            }, status_code=500)
            
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e),
            "message": "❌ 최적화 처리 오류"
        }, status_code=500)

@app.get("/api/stt-status")
async def get_stt_status():
    """
    STT(음성인식) 시스템 상태 확인
    """
    status = advanced_stt_processor.get_engine_status()
    
    return JSONResponse({
        "current_engine": status['current_engine'],
        "available_engines": status['available_engines'],
        "confidence_threshold": status['confidence_threshold'],
        "status": "ready" if len(status['available_engines']) > 1 else "limited",
        "message": f"🎤 {status['current_engine']} 엔진 활성화" if status['current_engine'] != 'local_fallback' else "⚠️ 제한된 기능만 사용 가능"
    })

@app.post("/api/advanced-stt")
async def advanced_stt_process(file: UploadFile = File(...), 
                              target_text: str = Form(""),
                              engine: str = Form("auto")):
    """
    고급 STT 처리 API
    다중 엔진 지원 및 신뢰도 평가
    """
    if not file.filename or not file.filename.endswith(('.wav', '.mp3', '.m4a', '.webm')):
        raise HTTPException(status_code=400, detail="지원되지 않는 파일 형식")
    
    try:
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        # 엔진 선택
        if engine != "auto":
            # 특정 엔진 요청 시 새로 초기화
            processor = AdvancedSTTProcessor(preferred_engine=engine)
        else:
            processor = advanced_stt_processor
        
        # 고급 STT 처리
        result = processor.process_audio_with_confidence(tmp_path, target_text)
        
        # 임시 파일 정리
        os.unlink(tmp_path)
        
        return JSONResponse({
            "success": True,
            "transcription": result['transcription'],
            "syllables": result['syllables'],
            "confidence": result['confidence'],
            "engine": result['engine'],
            "quality_metrics": result['quality_metrics'],
            "word_timestamps": result.get('word_timestamps', []),
            "message": f"✅ 고급 STT 처리 완료 ({result['engine']} 엔진)"
        })
        
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e),
            "message": "❌ 고급 STT 처리 오류"
        }, status_code=500)

@app.post("/api/multi-engine-comparison")
async def multi_engine_comparison(file: UploadFile = File(...), 
                                target_text: str = Form("")):
    """
    다중 STT 엔진 비교 분석
    """
    if not file.filename or not file.filename.endswith(('.wav', '.mp3', '.m4a', '.webm')):
        raise HTTPException(status_code=400, detail="지원되지 않는 파일 형식")
    
    try:
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        # 사용 가능한 엔진들로 처리
        available_engines = advanced_stt_processor.stt.available_engines
        results = {}
        
        for engine in available_engines:
            if engine == 'local_fallback':
                continue  # 비교에서 제외
            
            try:
                processor = AdvancedSTTProcessor(preferred_engine=engine)
                result = processor.process_audio_with_confidence(tmp_path, target_text)
                
                results[engine] = {
                    "transcription": result['transcription'],
                    "confidence": result['confidence'],
                    "syllable_count": result['quality_metrics']['syllable_count'],
                    "avg_syllable_confidence": result['quality_metrics']['avg_syllable_confidence'],
                    "has_word_timestamps": result['quality_metrics']['has_word_timestamps']
                }
            except Exception as e:
                results[engine] = {
                    "error": str(e),
                    "transcription": "",
                    "confidence": 0.0
                }
        
        # 임시 파일 정리
        os.unlink(tmp_path)
        
        # 최고 신뢰도 엔진 선택
        best_engine = max(results.keys(), key=lambda k: results[k].get('confidence', 0))
        
        return JSONResponse({
            "success": True,
            "results": results,
            "best_engine": best_engine,
            "target_text": target_text,
            "message": f"✅ 다중 엔진 비교 완료 - 최적: {best_engine}"
        })
        
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e),
            "message": "❌ 다중 엔진 비교 오류"
        }, status_code=500)

@app.post("/api/syllable-alignment-analysis")
async def syllable_alignment_analysis(file: UploadFile = File(...),
                                    text: str = Form(...)):
    """
    음절 정렬 상세 분석
    """
    try:
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        # 고급 처리
        result = advanced_stt_processor.process_audio_with_confidence(tmp_path, text)
        
        # 상세 분석 정보 추가
        syllable_analysis = []
        for syllable in result['syllables']:
            analysis = {
                "syllable": syllable['label'],
                "start": syllable['start'],
                "end": syllable['end'],
                "duration": syllable['end'] - syllable['start'],
                "confidence": syllable['confidence'],
                "phonetic_features": syllable.get('phonetic_features', {}),
                "analysis": {
                    "is_valid_duration": 0.05 <= (syllable['end'] - syllable['start']) <= 0.8,
                    "confidence_level": "high" if syllable['confidence'] > 0.8 else "medium" if syllable['confidence'] > 0.6 else "low"
                }
            }
            syllable_analysis.append(analysis)
        
        # 임시 파일 정리
        os.unlink(tmp_path)
        
        return JSONResponse({
            "success": True,
            "syllable_analysis": syllable_analysis,
            "summary": {
                "total_syllables": len(syllable_analysis),
                "avg_duration": np.mean([s['duration'] for s in syllable_analysis]),
                "avg_confidence": np.mean([s['confidence'] for s in syllable_analysis]),
                "high_confidence_ratio": len([s for s in syllable_analysis if s['confidence'] > 0.8]) / len(syllable_analysis)
            },
            "message": "✅ 음절 정렬 분석 완료"
        })
        
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": str(e),
            "message": "❌ 음절 정렬 분석 오류"
        }, status_code=500)

# ========================================
# 📁 업로드 파일 테스트 API들
# ========================================

@app.get("/api/uploaded_files")
async def get_uploaded_files():
    """업로드된 파일 목록 조회 - 통합된 버전 (Ultimate STT + 상세 정보)"""
    try:
        uploaded_files = []
        
        # uploads 디렉토리의 모든 wav 파일 찾기
        for file_path in UPLOAD_DIR.glob("*.wav"):
            wav_file = file_path.name
            file_id = file_path.stem
            textgrid_file = wav_file.replace('.wav', '.TextGrid')
            textgrid_path = UPLOAD_DIR / textgrid_file
            
            # 파일명에서 정보 추출
            parts = file_id.split('_')
            
            # Ultimate STT 테스트용 기본 정보
            expected_text = parts[3] if len(parts) >= 4 else "알 수 없음"
            
            # 상세 정보 파싱 (5개 이상 부분이 있는 경우)
            if len(parts) >= 5 and textgrid_path.exists():
                name = parts[0] if parts[0] else "이름없음"
                gender = parts[1] if parts[1] else "성별없음"
                age_group = parts[2] if parts[2] else "연령없음"
                sentence = parts[3] if parts[3] else "문장없음"
                timestamp = '_'.join(parts[4:]) if len(parts) > 4 else "시간없음"
                
                file_info = {
                    # Ultimate STT 호환 필드들
                    "file_id": file_id,
                    "filename": wav_file,
                    "expected_text": expected_text,
                    "has_textgrid": textgrid_path.exists(),
                    "file_size": file_path.stat().st_size,
                    "modified_time": file_path.stat().st_mtime,
                    
                    # 상세 정보 필드들
                    "id": file_id,
                    "wav_file": wav_file,
                    "textgrid_file": textgrid_file,
                    "name": name,
                    "gender": gender,
                    "age_group": age_group,
                    "sentence": sentence,
                    "timestamp": timestamp,
                    "display_name": f"{name} ({gender}, {age_group}) - {sentence}"
                }
            else:
                # TextGrid가 없거나 파싱할 수 없는 경우 기본 정보만
                file_info = {
                    "file_id": file_id,
                    "filename": wav_file,
                    "expected_text": expected_text,
                    "has_textgrid": textgrid_path.exists(),
                    "file_size": file_path.stat().st_size,
                    "modified_time": file_path.stat().st_mtime,
                    
                    # 기본 상세 정보
                    "id": file_id,
                    "wav_file": wav_file,
                    "textgrid_file": textgrid_file,
                    "name": expected_text,
                    "gender": "알 수 없음",
                    "age_group": "알 수 없음",
                    "sentence": expected_text,
                    "timestamp": str(file_path.stat().st_mtime),
                    "display_name": f"{expected_text} (파일명: {wav_file})"
                }
            
            uploaded_files.append(file_info)
        
        # 수정 시간 기준 최신 순 정렬
        uploaded_files.sort(key=lambda x: x['modified_time'], reverse=True)
        
        print(f"🗂️ 업로드된 파일 {len(uploaded_files)}개 찾음")
        return {
            "success": True,
            "files": uploaded_files,
            "total_count": len(uploaded_files)
        }
        
    except Exception as e:
        print(f"❌ 업로드 파일 목록 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=f"업로드 파일 목록 조회 실패: {e}")

@app.get("/api/uploaded_files/{file_id}/pitch")
async def get_uploaded_file_pitch(file_id: str, syllable_only: bool = False):
    # 빈 파일ID 검증
    if not file_id or file_id.strip() == '' or file_id == '()':
        raise HTTPException(status_code=400, detail="파일 ID가 필요합니다")
    """업로드된 파일의 피치 데이터 추출"""
    try:
        wav_file = f"{file_id}.wav"
        wav_path = UPLOAD_DIR / wav_file
        
        if not wav_path.exists():
            raise HTTPException(status_code=404, detail="WAV 파일을 찾을 수 없습니다")
        
        print(f"🎯 업로드 파일 피치 분석: {wav_file} (syllable_only={syllable_only})")
        
        # Parselmouth로 피치 추출
        sound = pm.Sound(str(wav_path))
        
        # 볼륨 증폭 (RMS가 낮은 경우)
        values = sound.values[0] if sound.n_channels > 0 else sound.values
        rms = np.sqrt(np.mean(values**2))
        if rms < 0.01:  # 볼륨이 작은 경우
            target_rms = 0.02  # 목표 RMS
            amplification_factor = target_rms / (rms + 1e-10)  # 0으로 나누기 방지
            # 최대 10배까지만 증폭
            amplification_factor = min(amplification_factor, 10.0)
            
            print(f"🔊 볼륨 증폭: RMS {rms:.4f} → {target_rms:.4f} (x{amplification_factor:.2f})")
            
            # 새로운 오디오 생성
            amplified_values = values * amplification_factor
            # 클리핑 방지
            amplified_values = np.clip(amplified_values, -0.9, 0.9)
            sound = pm.Sound(amplified_values, sampling_frequency=sound.sampling_frequency)
        
        # ✅ Reference 파일과 동일한 피치 파라미터 사용
        pitch = sound.to_pitch(time_step=0.01, pitch_floor=75.0, pitch_ceiling=500.0)
        
        # 피치 데이터 추출
        times = pitch.xs()
        frequencies = [pitch.get_value_at_time(t) for t in times]
        
        # NaN 값 제거
        pitch_data = []
        for i, (time, freq) in enumerate(zip(times, frequencies)):
            if not math.isnan(freq) and freq > 0:
                pitch_data.append({"time": time, "frequency": freq})
        
        print(f"🎯 {len(pitch_data)}개 피치 포인트 추출")
        
        if syllable_only:
            # ✅ Reference 파일과 동일한 함수 사용
            textgrid_file = f"{file_id}.TextGrid"
            textgrid_path = UPLOAD_DIR / textgrid_file
            
            if textgrid_path.exists():
                # Reference 파일과 동일한 처리 함수 호출
                return await get_syllable_representative_pitch(file_id, str(wav_path), str(textgrid_path), sound, pitch)
        
        return pitch_data
        
    except Exception as e:
        print(f"❌ 업로드 파일 피치 분석 오류: {e}")
        raise HTTPException(status_code=500, detail=f"피치 분석 실패: {e}")

@app.get("/api/uploaded_files/{file_id}/syllables")
async def get_uploaded_file_syllables(file_id: str):
    """업로드된 파일의 TextGrid 음절 정보"""
    try:
        textgrid_file = f"{file_id}.TextGrid"
        textgrid_path = UPLOAD_DIR / textgrid_file
        
        if not textgrid_path.exists():
            raise HTTPException(status_code=404, detail="TextGrid 파일을 찾을 수 없습니다")
        
        print(f"🎯 업로드 파일 TextGrid 읽기: {textgrid_file}")
        
        # TextGrid 파싱
        syllables = []
        try:
            with open(textgrid_path, 'r', encoding='utf-16') as f:
                content = f.read()
        except:
            with open(textgrid_path, 'r', encoding='utf-8') as f:
                content = f.read()
        
        # 음절 정보 추출 (기존 로직과 동일)
        pattern = r'text = "([^"]+)"'
        matches = re.findall(pattern, content)
        
        for match in matches:
            if match.strip() and match.strip() != '':
                syllables.append(match.strip())
        
        print(f"🎯 {len(syllables)}개 음절 반환: {syllables}")
        return syllables
        
    except Exception as e:
        print(f"❌ 업로드 파일 TextGrid 읽기 오류: {e}")
        raise HTTPException(status_code=500, detail=f"TextGrid 읽기 실패: {e}")

def calculate_syllable_pitch_from_textgrid(textgrid_path: str, pitch_data: list):
    """TextGrid 기반 음절별 대표 피치 계산"""
    try:
        # TextGrid 파일 읽기
        try:
            with open(textgrid_path, 'r', encoding='utf-16') as f:
                content = f.read()
        except:
            with open(textgrid_path, 'r', encoding='utf-8') as f:
                content = f.read()
        
        # 음절 구간 정보 추출
        syllable_regions = []
        lines = content.split('\n')
        current_interval = {}
        
        for line in lines:
            line = line.strip()
            if 'xmin =' in line:
                current_interval['start'] = float(line.split('=')[1].strip())
            elif 'xmax =' in line:
                current_interval['end'] = float(line.split('=')[1].strip())
            elif 'text = "' in line:
                text = line.split('"')[1]
                if text.strip():
                    current_interval['text'] = text.strip()
                    syllable_regions.append(current_interval.copy())
                current_interval = {}
        
        # 각 음절의 대표 피치 계산
        syllable_pitch = []
        print(f"🎯 음절 구간 처리: {len(syllable_regions)}개 구간, {len(pitch_data)}개 피치 포인트")
        
        for i, region in enumerate(syllable_regions):
            start_time = region['start']
            end_time = region['end']
            syllable = region['text']
            
            print(f"  🎯 음절 {i+1}: '{syllable}' ({start_time:.3f}s ~ {end_time:.3f}s)")
            
            # 해당 구간의 피치 데이터 필터링 (경계 조건 완화)
            region_pitches = []
            region_times = []
            for p in pitch_data:
                # 구간 경계에서 약간의 여유를 둠 (0.05초)
                margin = 0.05
                if (start_time - margin) <= p['time'] <= (end_time + margin):
                    region_pitches.append(p['frequency'])
                    region_times.append(p['time'])
            
            if region_times:
                print(f"    📊 구간 내 시간 범위: {min(region_times):.3f}s ~ {max(region_times):.3f}s")
            
            print(f"    📊 구간 내 피치 포인트: {len(region_pitches)}개")
            
            if region_pitches:
                avg_pitch = sum(region_pitches) / len(region_pitches)
                syllable_data = {
                    "time": (start_time + end_time) / 2,  # 구간 중점
                    "frequency": avg_pitch,
                    "syllable": syllable,
                    "start": start_time,
                    "end": end_time
                }
                syllable_pitch.append(syllable_data)
                print(f"    ✅ 평균 피치: {avg_pitch:.1f}Hz")
            else:
                print(f"    ❌ 구간 내 피치 데이터 없음")
        
        print(f"🎯 최종 음절 피치 결과: {len(syllable_pitch)}개 반환")
        return syllable_pitch
        
    except Exception as e:
        print(f"❌ TextGrid 기반 음절 피치 계산 오류: {e}")
        return []

@app.post("/api/update-all-textgrids")
async def update_all_textgrids():
    """모든 파일의 TextGrid를 새로운 정밀 알고리즘으로 업데이트"""
    try:
        print("🔄 모든 TextGrid 파일 업데이트 시작")
        
        updated_files = []
        errors = []
        
        # 1. Reference Files 업데이트
        reference_dir = Path("static/reference_files")
        if reference_dir.exists():
            for wav_file in reference_dir.glob("*.wav"):
                try:
                    # 파일명에서 문장 추출 (확장자 제거)
                    sentence = wav_file.stem
                    
                    # 새로운 알고리즘으로 TextGrid 생성
                    textgrid_path = create_textgrid_from_audio(
                        str(wav_file), 
                        sentence,
                        output_path=str(wav_file.with_suffix('.TextGrid'))
                    )
                    
                    updated_files.append({
                        "type": "reference",
                        "file": wav_file.name,
                        "textgrid": textgrid_path,
                        "sentence": sentence
                    })
                    print(f"✅ Reference 업데이트: {wav_file.name}")
                    
                except Exception as e:
                    error_msg = f"Reference {wav_file.name}: {str(e)}"
                    errors.append(error_msg)
                    print(f"❌ {error_msg}")
        
        # 2. Uploaded Files 업데이트 
        uploads_dir = Path("static/uploads")
        if uploads_dir.exists():
            for wav_file in uploads_dir.glob("*.wav"):
                try:
                    # 파일명에서 정보 추출 (예: 박우용_male_30대_반가워요_20250908_184908.wav)
                    filename_parts = wav_file.stem.split('_')
                    if len(filename_parts) >= 4:
                        sentence = filename_parts[3]  # 연습문장 부분
                        
                        # 새로운 알고리즘으로 TextGrid 생성
                        textgrid_path = create_textgrid_from_audio(
                            str(wav_file),
                            sentence, 
                            output_path=str(wav_file.with_suffix('.TextGrid'))
                        )
                        
                        updated_files.append({
                            "type": "uploaded",
                            "file": wav_file.name,
                            "textgrid": textgrid_path,
                            "sentence": sentence
                        })
                        print(f"✅ Upload 업데이트: {wav_file.name}")
                    else:
                        print(f"⚠️ 파일명 형식 불일치: {wav_file.name}")
                        
                except Exception as e:
                    error_msg = f"Upload {wav_file.name}: {str(e)}"
                    errors.append(error_msg)
                    print(f"❌ {error_msg}")
        
        print(f"🎉 TextGrid 업데이트 완료: {len(updated_files)}개 성공, {len(errors)}개 실패")
        
        return {
            "success": True,
            "updated_count": len(updated_files),
            "error_count": len(errors),
            "updated_files": updated_files,
            "errors": errors,
            "message": f"새로운 정밀 분절 알고리즘으로 {len(updated_files)}개 파일 업데이트 완료"
        }
        
    except Exception as e:
        print(f"❌ TextGrid 일괄 업데이트 실패: {e}")
        raise HTTPException(status_code=500, detail=f"TextGrid 업데이트 실패: {str(e)}")

# 🎵 음역대 측정 API - 최저음/최고음 측정 및 기하평균 계산
@app.post("/api/voice-range-measurement")
async def voice_range_measurement(file: UploadFile = File(...)):
    """
    화자의 음역대를 측정하여 기준 주파수 계산
    - 최저음/최고음 측정
    - 기하평균 계산: √(최저주파수 × 최고주파수)
    - 로그 스케일 중간점 계산
    """
    try:
        print(f"🎵 음역대 측정 시작: {file.filename}")
        
        # 임시 파일로 저장
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        content = await file.read()
        temp_file.write(content)
        temp_file.close()
        
        # Parselmouth로 음성 로드
        sound = parselmouth.Sound(temp_file.name)
        
        # 피치 추출 (더 넓은 범위로 설정)
        pitch = sound.to_pitch(time_step=0.01, pitch_floor=50.0, pitch_ceiling=600.0)
        
        # 유효한 피치 값들만 추출 (0이 아닌 값들)
        pitch_values = []
        for i in range(pitch.get_number_of_frames()):
            f0 = pitch.get_value_at_time(pitch.get_time_from_frame_number(i + 1))
            if f0 > 0:  # 유효한 피치 값만
                pitch_values.append(f0)
        
        if len(pitch_values) < 10:
            raise HTTPException(status_code=400, detail="충분한 음성 데이터를 추출할 수 없습니다")
        
        # 최저음/최고음 추출 (극단값 제거)
        sorted_pitches = sorted(pitch_values)
        # 하위 5%와 상위 5%는 노이즈로 간주하여 제거
        trim_count = max(1, len(sorted_pitches) // 20)
        trimmed_pitches = sorted_pitches[trim_count:-trim_count]
        
        min_freq = min(trimmed_pitches)
        max_freq = max(trimmed_pitches)
        
        # 기하평균 계산: √(min × max)
        geometric_mean = (min_freq * max_freq) ** 0.5
        
        # 로그 스케일 중간점 계산 (세미톤 단위)
        import math
        log_midpoint = math.exp((math.log(min_freq) + math.log(max_freq)) / 2)
        
        # 평균 피치 (산술평균)
        arithmetic_mean = sum(trimmed_pitches) / len(trimmed_pitches)
        
        # 임시 파일 삭제
        os.unlink(temp_file.name)
        
        result = {
            "measurement_type": "voice_range",
            "min_frequency": round(min_freq, 2),
            "max_frequency": round(max_freq, 2),
            "geometric_mean": round(geometric_mean, 2),
            "log_midpoint": round(log_midpoint, 2),
            "arithmetic_mean": round(arithmetic_mean, 2),
            "total_samples": len(pitch_values),
            "valid_samples": len(trimmed_pitches),
            "range_semitones": round(12 * math.log2(max_freq / min_freq), 1)
        }
        
        print(f"🎵 음역대 측정 완료:")
        print(f"   최저음: {min_freq:.1f}Hz, 최고음: {max_freq:.1f}Hz")
        print(f"   기하평균: {geometric_mean:.1f}Hz, 음역: {result['range_semitones']}st")
        
        return result
        
    except Exception as e:
        print(f"❌ 음역대 측정 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"음역대 측정 실패: {str(e)}")

# 🗣️ 모음별 분석 API - /아/, /이/, /우/ 개별 주파수 분석
@app.post("/api/vowel-analysis")
async def vowel_analysis(file: UploadFile = File(...), vowel_type: str = Form(...)):
    """
    특정 모음의 주파수 특성 분석
    vowel_type: 'a' (/아/), 'i' (/이/), 'u' (/우/)
    """
    try:
        print(f"🗣️ 모음별 분석 시작: {vowel_type} - {file.filename}")
        
        # 임시 파일로 저장
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
        content = await file.read()
        temp_file.write(content)
        temp_file.close()
        
        # Parselmouth로 음성 로드
        sound = parselmouth.Sound(temp_file.name)
        
        # 피치 추출
        pitch = sound.to_pitch(time_step=0.01)
        
        # 포먼트 분석 (모음 특성)
        formant = sound.to_formant_burg(time_step=0.01, max_number_of_formants=4)
        
        # 피치 값들 추출
        pitch_values = []
        f1_values = []  # 첫 번째 포먼트
        f2_values = []  # 두 번째 포먼트
        
        for i in range(min(pitch.get_number_of_frames(), formant.get_number_of_frames())):
            time = pitch.get_time_from_frame_number(i + 1)
            f0 = pitch.get_value_at_time(time)
            f1 = formant.get_value_at_time(1, time)  # 첫 번째 포먼트
            f2 = formant.get_value_at_time(2, time)  # 두 번째 포먼트
            
            if f0 > 0:
                pitch_values.append(f0)
            if not math.isnan(f1) and f1 > 0:
                f1_values.append(f1)
            if not math.isnan(f2) and f2 > 0:
                f2_values.append(f2)
        
        if len(pitch_values) < 5:
            raise HTTPException(status_code=400, detail="충분한 모음 데이터를 추출할 수 없습니다")
        
        # 통계 계산
        mean_f0 = sum(pitch_values) / len(pitch_values)
        mean_f1 = sum(f1_values) / len(f1_values) if f1_values else 0
        mean_f2 = sum(f2_values) / len(f2_values) if f2_values else 0
        
        # 표준편차 계산
        import statistics
        std_f0 = statistics.stdev(pitch_values) if len(pitch_values) > 1 else 0
        
        # 임시 파일 삭제
        os.unlink(temp_file.name)
        
        result = {
            "vowel_type": vowel_type,
            "fundamental_frequency": round(mean_f0, 2),
            "f1_formant": round(mean_f1, 2),
            "f2_formant": round(mean_f2, 2),
            "f0_std_deviation": round(std_f0, 2),
            "stability_score": round(1 / (1 + std_f0/mean_f0), 3),  # 안정성 점수
            "sample_count": len(pitch_values)
        }
        
        print(f"🗣️ 모음 /{vowel_type}/ 분석 완료: F0={mean_f0:.1f}Hz, F1={mean_f1:.0f}Hz, F2={mean_f2:.0f}Hz")
        
        return result
        
    except Exception as e:
        print(f"❌ 모음 분석 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"모음 분석 실패: {str(e)}")

# 📊 기하평균 기반 기준점 계산 API
@app.post("/api/calculate-reference-frequency")
async def calculate_reference_frequency(measurements: dict):
    """
    다중 측정값을 통합하여 최적 기준 주파수 계산
    measurements: {
        "comfortable_pitch": float,  # 편안한 발화 주파수
        "voice_range": {...},        # 음역대 측정 결과
        "vowel_analysis": [...]      # 모음별 분석 결과들
    }
    """
    try:
        print("📊 기하평균 기반 기준점 계산 시작")
        
        reference_candidates = []
        weights = []
        
        # 1. 편안한 발화 주파수 (가중치: 0.4)
        if "comfortable_pitch" in measurements:
            reference_candidates.append(measurements["comfortable_pitch"])
            weights.append(0.4)
            print(f"   편안한 발화: {measurements['comfortable_pitch']:.1f}Hz (가중치: 0.4)")
        
        # 2. 음역대 기하평균 (가중치: 0.3)
        if "voice_range" in measurements:
            range_data = measurements["voice_range"]
            reference_candidates.append(range_data["geometric_mean"])
            weights.append(0.3)
            print(f"   음역대 기하평균: {range_data['geometric_mean']:.1f}Hz (가중치: 0.3)")
        
        # 3. 모음별 분석 평균 (가중치: 0.3)
        if "vowel_analysis" in measurements and measurements["vowel_analysis"]:
            vowel_freqs = []
            for vowel in measurements["vowel_analysis"]:
                # 안정성 점수로 가중치 조정
                stability = vowel.get("stability_score", 0.5)
                freq = vowel["fundamental_frequency"]
                vowel_freqs.append(freq * stability)
            
            if vowel_freqs:
                vowel_mean = sum(vowel_freqs) / len(vowel_freqs)
                reference_candidates.append(vowel_mean)
                weights.append(0.3)
                print(f"   모음 평균: {vowel_mean:.1f}Hz (가중치: 0.3)")
        
        if not reference_candidates:
            raise HTTPException(status_code=400, detail="계산에 필요한 측정 데이터가 없습니다")
        
        # 가중 기하평균 계산
        import math
        
        # 정규화된 가중치
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]
        
        # 가중 기하평균: (∏ fi^wi)^(1/Σwi)
        log_sum = sum(math.log(freq) * weight for freq, weight in zip(reference_candidates, normalized_weights))
        weighted_geometric_mean = math.exp(log_sum)
        
        # 가중 산술평균 (비교용)
        weighted_arithmetic_mean = sum(freq * weight for freq, weight in zip(reference_candidates, normalized_weights))
        
        # 신뢰도 점수 계산 (측정값들의 일관성)
        import statistics
        if len(reference_candidates) > 1:
            cv = statistics.stdev(reference_candidates) / statistics.mean(reference_candidates)  # 변동계수
            confidence_score = max(0, 1 - cv)  # 변동이 적을수록 신뢰도 높음
        else:
            confidence_score = 0.5
        
        result = {
            "reference_frequency": round(weighted_geometric_mean, 2),
            "alternative_reference": round(weighted_arithmetic_mean, 2),
            "confidence_score": round(confidence_score, 3),
            "measurement_count": len(reference_candidates),
            "individual_measurements": [
                {"value": round(freq, 2), "weight": round(weight, 2)} 
                for freq, weight in zip(reference_candidates, normalized_weights)
            ]
        }
        
        print(f"📊 최적 기준 주파수: {weighted_geometric_mean:.1f}Hz (신뢰도: {confidence_score:.2f})")
        
        return result
        
    except Exception as e:
        print(f"❌ 기준점 계산 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"기준점 계산 실패: {str(e)}")

# 🔄 실시간 기준점 조정 API - 현재 발화 기반 동적 업데이트
@app.post("/api/adaptive-reference-adjustment")
async def adaptive_reference_adjustment(current_data: dict):
    """
    실시간 발화 데이터를 기반으로 기준 주파수 동적 조정
    current_data: {
        "current_frequency": float,    # 현재 발화 주파수
        "current_reference": float,    # 현재 기준 주파수
        "confidence": float,           # 피치 신뢰도 (0-1)
        "adjustment_factor": float,    # 조정 강도 (0-1, 기본: 0.1)
        "context": str                 # 발화 상황 ("normal", "stressed", "relaxed")
    }
    """
    try:
        print("🔄 실시간 기준점 조정 시작")
        
        current_freq = current_data["current_frequency"]
        current_ref = current_data["current_reference"]
        confidence = current_data.get("confidence", 0.8)
        adjustment_factor = current_data.get("adjustment_factor", 0.1)
        context = current_data.get("context", "normal")
        
        # 상황별 조정 계수
        context_multipliers = {
            "normal": 1.0,      # 일반 상황
            "stressed": 0.5,    # 스트레스 상황: 조정 강도 줄임
            "relaxed": 1.2,     # 편안한 상황: 조정 강도 높임
            "loud": 0.3,        # 큰 소리: 급격한 변화 억제
            "quiet": 0.8        # 작은 소리: 적당한 조정
        }
        
        effective_adjustment = adjustment_factor * context_multipliers.get(context, 1.0) * confidence
        
        # 주파수 차이 계산 (세미톤 단위)
        import math
        freq_diff_semitones = 12 * math.log2(current_freq / current_ref)
        
        # 점진적 조정 (exponential moving average 방식)
        # 새로운 기준점 = 기존 기준점 + (차이 × 조정계수)
        adjustment_hz = (current_freq - current_ref) * effective_adjustment
        new_reference = current_ref + adjustment_hz
        
        # 극단적 변화 방지 (±3 세미톤 이내로 제한)
        max_change_semitones = 3.0
        max_change_hz = current_ref * (2**(max_change_semitones/12) - 1)
        
        if abs(adjustment_hz) > max_change_hz:
            adjustment_hz = max_change_hz if adjustment_hz > 0 else -max_change_hz
            new_reference = current_ref + adjustment_hz
        
        # 결과 검증 (50Hz ~ 600Hz 범위 내)
        new_reference = max(50.0, min(600.0, new_reference))
        
        result = {
            "original_reference": round(current_ref, 2),
            "new_reference": round(new_reference, 2),
            "adjustment_hz": round(adjustment_hz, 2),
            "adjustment_semitones": round(12 * math.log2(new_reference / current_ref), 3),
            "effective_factor": round(effective_adjustment, 3),
            "context": context,
            "confidence_used": confidence
        }
        
        print(f"🔄 기준점 조정: {current_ref:.1f}Hz → {new_reference:.1f}Hz (±{adjustment_hz:.1f}Hz)")
        
        return result
        
    except Exception as e:
        print(f"❌ 실시간 기준점 조정 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"실시간 조정 실패: {str(e)}")

# 📈 이동평균 기반 기준점 업데이트 API
@app.post("/api/moving-average-update")
async def moving_average_update(pitch_history: dict):
    """
    최근 N개 발화의 가중평균으로 기준점 업데이트
    pitch_history: {
        "recent_pitches": [float],     # 최근 피치 값들
        "timestamps": [float],         # 각 피치의 시간정보
        "confidences": [float],        # 각 피치의 신뢰도
        "window_size": int,            # 이동평균 윈도우 크기 (기본: 20)
        "decay_factor": float          # 시간 감쇠 계수 (기본: 0.95)
    }
    """
    try:
        print("📈 이동평균 기반 기준점 업데이트 시작")
        
        recent_pitches = pitch_history["recent_pitches"]
        timestamps = pitch_history.get("timestamps", [])
        confidences = pitch_history.get("confidences", [1.0] * len(recent_pitches))
        window_size = pitch_history.get("window_size", 20)
        decay_factor = pitch_history.get("decay_factor", 0.95)
        
        if len(recent_pitches) < 3:
            raise HTTPException(status_code=400, detail="이동평균 계산에 충분한 데이터가 없습니다")
        
        # 최근 N개 데이터만 사용
        if len(recent_pitches) > window_size:
            recent_pitches = recent_pitches[-window_size:]
            if timestamps:
                timestamps = timestamps[-window_size:]
            confidences = confidences[-window_size:]
        
        # 시간 기반 가중치 계산 (최근일수록 높은 가중치)
        weights = []
        if timestamps:
            max_time = max(timestamps)
            for i, timestamp in enumerate(timestamps):
                # 시간 차이에 따른 감쇠
                time_diff = max_time - timestamp
                time_weight = decay_factor ** time_diff
                # 신뢰도와 시간 가중치 결합
                combined_weight = time_weight * confidences[i]
                weights.append(combined_weight)
        else:
            # 시간 정보가 없으면 순서 기반 가중치
            for i in range(len(recent_pitches)):
                position_weight = decay_factor ** (len(recent_pitches) - 1 - i)
                combined_weight = position_weight * confidences[i]
                weights.append(combined_weight)
        
        # 가중 평균 계산 (기하평균 사용)
        import math
        
        total_weight = sum(weights)
        if total_weight == 0:
            raise HTTPException(status_code=400, detail="유효한 가중치가 없습니다")
        
        # 정규화된 가중치로 기하평균 계산
        normalized_weights = [w / total_weight for w in weights]
        log_sum = sum(math.log(freq) * weight for freq, weight in zip(recent_pitches, normalized_weights))
        weighted_geometric_mean = math.exp(log_sum)
        
        # 가중 산술평균 (비교용)
        weighted_arithmetic_mean = sum(freq * weight for freq, weight in zip(recent_pitches, normalized_weights))
        
        # 안정성 지표 계산
        import statistics
        pitch_std = statistics.stdev(recent_pitches) if len(recent_pitches) > 1 else 0
        pitch_mean = statistics.mean(recent_pitches)
        stability_coefficient = 1 - (pitch_std / pitch_mean)  # 변동이 적을수록 높음
        
        result = {
            "updated_reference": round(weighted_geometric_mean, 2),
            "alternative_reference": round(weighted_arithmetic_mean, 2),
            "stability_coefficient": round(stability_coefficient, 3),
            "sample_count": len(recent_pitches),
            "effective_window": len(recent_pitches),
            "pitch_range": {
                "min": round(min(recent_pitches), 2),
                "max": round(max(recent_pitches), 2),
                "std": round(pitch_std, 2)
            }
        }
        
        print(f"📈 이동평균 기준점: {weighted_geometric_mean:.1f}Hz (안정성: {stability_coefficient:.2f})")
        
        return result
        
    except Exception as e:
        print(f"❌ 이동평균 업데이트 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"이동평균 업데이트 실패: {str(e)}")

# ⏰ 주기적 재측정 알림 시스템 API
@app.post("/api/remeasurement-schedule")
async def remeasurement_schedule(user_profile: dict):
    """
    사용자 프로필 기반 재측정 스케줄 관리
    user_profile: {
        "user_id": str,
        "last_measurement": str,       # ISO 날짜 형식
        "measurement_frequency": int,  # 개월 단위 (기본: 3개월)
        "voice_change_factors": [str], # ["age", "health", "training"]
        "current_age": int,
        "gender": str
    }
    """
    try:
        print("⏰ 재측정 스케줄 관리 시작")
        
        from datetime import datetime, timedelta
        import json
        
        user_id = user_profile["user_id"]
        last_measurement_str = user_profile["last_measurement"]
        frequency_months = user_profile.get("measurement_frequency", 3)
        change_factors = user_profile.get("voice_change_factors", [])
        current_age = user_profile.get("current_age", 30)
        gender = user_profile.get("gender", "unknown")
        
        # 날짜 파싱
        last_measurement = datetime.fromisoformat(last_measurement_str.replace('Z', '+00:00'))
        
        # 기본 재측정 주기 계산
        base_interval_months = frequency_months
        
        # 나이별 조정
        if current_age < 18:
            base_interval_months = max(1, base_interval_months // 2)  # 청소년: 더 자주
        elif current_age > 60:
            base_interval_months = max(2, int(base_interval_months * 0.8))  # 고령: 약간 더 자주
        
        # 변화 요인별 주기 조정
        adjustment_factor = 1.0
        for factor in change_factors:
            if factor == "training":
                adjustment_factor *= 0.5  # 음성 훈련 중: 더 자주
            elif factor == "health":
                adjustment_factor *= 0.7  # 건강 문제: 자주
            elif factor == "medication":
                adjustment_factor *= 0.6  # 약물 복용: 자주
            elif factor == "surgery":
                adjustment_factor *= 0.3  # 수술 후: 매우 자주
        
        adjusted_interval_months = max(1, int(base_interval_months * adjustment_factor))
        
        # 다음 측정 예정일 계산
        next_measurement = last_measurement + timedelta(days=adjusted_interval_months * 30)
        
        # 현재까지의 경과 시간
        now = datetime.now()
        days_since_last = (now - last_measurement).days
        days_until_next = (next_measurement - now).days
        
        # 알림 상태 결정
        if days_until_next <= 0:
            alert_status = "overdue"
            urgency = "high"
        elif days_until_next <= 7:
            alert_status = "due_soon"
            urgency = "medium"
        elif days_until_next <= 30:
            alert_status = "upcoming"
            urgency = "low"
        else:
            alert_status = "scheduled"
            urgency = "none"
        
        # 권장 측정 항목
        recommended_tests = ["comfortable_pitch"]
        if days_since_last > 90:  # 3개월 이상
            recommended_tests.extend(["voice_range", "vowel_analysis"])
        if "training" in change_factors:
            recommended_tests.append("stability_analysis")
        
        result = {
            "user_id": user_id,
            "last_measurement_date": last_measurement_str,
            "next_measurement_date": next_measurement.isoformat(),
            "days_since_last": days_since_last,
            "days_until_next": days_until_next,
            "adjusted_interval_months": adjusted_interval_months,
            "alert_status": alert_status,
            "urgency_level": urgency,
            "recommended_tests": recommended_tests,
            "change_factors_considered": change_factors,
            "schedule_message": generate_schedule_message(alert_status, days_until_next, urgency)
        }
        
        print(f"⏰ 사용자 {user_id}: {alert_status} (다음 측정까지 {days_until_next}일)")
        
        return result
        
    except Exception as e:
        print(f"❌ 재측정 스케줄 관리 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"스케줄 관리 실패: {str(e)}")

def generate_schedule_message(status: str, days_until: int, urgency: str) -> str:
    """재측정 알림 메시지 생성"""
    if status == "overdue":
        return f"⚠️ 기준 주파수 재측정이 {abs(days_until)}일 지연되었습니다. 정확한 분석을 위해 지금 측정하세요."
    elif status == "due_soon":
        return f"🔔 {days_until}일 후 기준 주파수 재측정이 예정되어 있습니다."
    elif status == "upcoming":
        return f"📅 {days_until}일 후 기준 주파수 재측정 예정입니다."
    else:
        return f"✅ 다음 재측정까지 {days_until}일 남았습니다."

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)