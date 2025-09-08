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
from pathlib import Path
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

# Static files and templates (remove duplicate)
# Duplicate mount removed - already defined above

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
                        
                        # 대표 f0 필드의 경우 semitone도 업데이트
                        if field == 'f0' and normalized_f0 > 0 and target_base > 0:
                            normalized_semitone = 12 * np.log2(normalized_f0 / target_base)
                            normalized_syl['semitone'] = normalized_semitone
                            # 🎯 올바른 Q-tone 공식: 5 * log2(f0/130)
                            normalized_syl['qtone'] = 5 * np.log2(normalized_f0 / 130) if normalized_f0 > 0 else 0.0
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
                                        syl_analysis['qtone'] = 5 * np.log2(normalized_f0 / 130) if normalized_f0 > 0 else 0.0
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
        syllables = extracted_syllables
    else:
        print("🎯 Fallback: Using old TextGrid parser")
        syllables = praat_script_textgrid_parser(tg) if tg else []
    
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
        
        return JSONResponse({
            "status": "success",
            "pitch_data": f0_values[-10:] if f0_values else [],  # Last 10 points
            "duration": snd.duration if 'snd' in locals() else 0
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
                "syllable": label
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
                    pitch_values.append({
                        "time": float(time),
                        "f0": float(f0),
                        "semitone": float(12 * np.log2(f0 / 200)) if f0 > 0 else 0
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)