"""
ToneBridge 오디오 자동 정규화 모듈
숨겨진 자동화 기능: 무음 제거, 볼륨 정규화, 샘플레이트 조정, TextGrid 동기화
"""

import os
import librosa
import soundfile as sf
import numpy as np
from pydub import AudioSegment
from pydub.effects import normalize
from pydub.silence import split_on_silence, detect_silence
import textgrid
import tempfile
import shutil
from typing import Tuple, List, Dict, Optional
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioNormalizer:
    """오디오 자동 정규화 클래스"""
    
    def __init__(self, target_sample_rate: int = 16000, target_db: float = -20.0):
        """
        초기화
        Args:
            target_sample_rate: 목표 샘플레이트 (기본 16kHz)
            target_db: 목표 볼륨 레벨 (기본 -20dB)
        """
        self.target_sample_rate = target_sample_rate
        self.target_db = target_db
        
    def remove_silence(self, audio_segment: AudioSegment, 
                      silence_thresh: int = -50, 
                      min_silence_len: int = 500,
                      keep_silence: int = 100) -> Tuple[AudioSegment, float]:
        """
        무음 구간 제거
        Args:
            audio_segment: 입력 오디오
            silence_thresh: 무음 판정 임계값 (dB)
            min_silence_len: 최소 무음 길이 (ms)
            keep_silence: 유지할 무음 길이 (ms)
        Returns:
            (처리된 오디오, 시간 변화 비율)
        """
        original_duration = len(audio_segment)
        
        # 무음 구간에서 분할
        audio_chunks = split_on_silence(
            audio_segment,
            min_silence_len=min_silence_len,
            silence_thresh=silence_thresh,
            keep_silence=keep_silence
        )
        
        if not audio_chunks:
            logger.warning("무음 제거 중 오디오 청크를 찾을 수 없음")
            return audio_segment, 1.0
            
        # 청크들을 다시 합치기
        processed_audio = audio_chunks[0]
        for chunk in audio_chunks[1:]:
            processed_audio += chunk
            
        new_duration = len(processed_audio)
        time_ratio = new_duration / original_duration if original_duration > 0 else 1.0
        
        logger.info(f"무음 제거: {original_duration}ms → {new_duration}ms (비율: {time_ratio:.3f})")
        return processed_audio, time_ratio
        
    def normalize_volume(self, audio_segment: AudioSegment) -> AudioSegment:
        """
        볼륨 정규화
        Args:
            audio_segment: 입력 오디오
        Returns:
            정규화된 오디오
        """
        # 피크 정규화 적용
        normalized = normalize(audio_segment)
        
        # 목표 dB로 조정
        current_db = normalized.dBFS
        target_adjustment = self.target_db - current_db
        
        if abs(target_adjustment) > 0.5:  # 0.5dB 이상 차이날 때만 조정
            normalized = normalized + target_adjustment
            
        logger.info(f"볼륨 정규화: {current_db:.1f}dB → {normalized.dBFS:.1f}dB")
        return normalized
        
    def adjust_sample_rate(self, wav_path: str) -> Tuple[np.ndarray, int]:
        """
        샘플레이트 조정
        Args:
            wav_path: WAV 파일 경로
        Returns:
            (리샘플된 오디오 데이터, 새 샘플레이트)
        """
        # librosa로 로드 (자동 리샘플링)
        audio_data, original_sr = librosa.load(wav_path, sr=None)
        
        if original_sr != self.target_sample_rate:
            # 리샘플링
            resampled_audio = librosa.resample(
                audio_data, 
                orig_sr=original_sr, 
                target_sr=self.target_sample_rate
            )
            logger.info(f"샘플레이트 조정: {original_sr}Hz → {self.target_sample_rate}Hz")
            return resampled_audio, self.target_sample_rate
        else:
            logger.info(f"샘플레이트 유지: {original_sr}Hz")
            return audio_data, original_sr
            
    def process_audio_file(self, wav_path: str, output_path: str) -> Dict[str, float]:
        """
        오디오 파일 전체 처리 (무음 제거 + 볼륨 정규화 + 샘플레이트 조정)
        Args:
            wav_path: 입력 WAV 파일 경로
            output_path: 출력 WAV 파일 경로
        Returns:
            처리 결과 정보 (시간 변화 비율 등)
        """
        try:
            # 1. 오디오 로드
            audio_segment = AudioSegment.from_wav(wav_path)
            original_duration = len(audio_segment) / 1000.0  # 초 단위
            
            # 2. 무음 구간 제거
            processed_audio, time_ratio = self.remove_silence(audio_segment)
            
            # 3. 볼륨 정규화
            processed_audio = self.normalize_volume(processed_audio)
            
            # 4. 임시 파일로 저장
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                processed_audio.export(tmp_file.name, format='wav')
                tmp_path = tmp_file.name
                
            # 5. 샘플레이트 조정
            final_audio, final_sr = self.adjust_sample_rate(tmp_path)
            
            # 6. 최종 저장
            sf.write(output_path, final_audio, final_sr)
            
            # 임시 파일 삭제
            os.unlink(tmp_path)
            
            final_duration = len(final_audio) / final_sr
            
            result = {
                'original_duration': original_duration,
                'final_duration': final_duration,
                'time_ratio': time_ratio,
                'sample_rate': final_sr,
                'volume_normalized': True,
                'silence_removed': True
            }
            
            logger.info(f"오디오 처리 완료: {wav_path} → {output_path}")
            logger.info(f"지속시간: {original_duration:.2f}s → {final_duration:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"오디오 처리 중 오류: {e}")
            raise

class TextGridSynchronizer:
    """TextGrid 자동 동기화 클래스"""
    
    def __init__(self):
        pass
        
    def synchronize_textgrid(self, textgrid_path: str, output_path: str, 
                           time_ratio: float, new_duration: float) -> bool:
        """
        TextGrid 시간 구간을 오디오 변화에 맞게 동기화
        Args:
            textgrid_path: 입력 TextGrid 파일 경로
            output_path: 출력 TextGrid 파일 경로
            time_ratio: 시간 변화 비율 (새 길이 / 원래 길이)
            new_duration: 새로운 오디오 지속시간
        Returns:
            동기화 성공 여부
        """
        try:
            # TextGrid 로드
            tg = textgrid.TextGrid.fromFile(textgrid_path)
            
            # 모든 tier와 interval 조정
            for tier in tg.tiers:
                if hasattr(tier, 'intervals'):  # IntervalTier
                    for interval in tier.intervals:
                        # 시작과 끝 시간을 비율에 맞게 조정
                        interval.minTime *= time_ratio
                        interval.maxTime *= time_ratio
                        
                elif hasattr(tier, 'points'):  # PointTier
                    for point in tier.points:
                        point.time *= time_ratio
                        
            # TextGrid 전체 지속시간 조정
            tg.maxTime = new_duration
            
            # 저장
            tg.write(output_path)
            
            logger.info(f"TextGrid 동기화 완료: {textgrid_path} → {output_path}")
            logger.info(f"시간 비율: {time_ratio:.3f}, 새 지속시간: {new_duration:.2f}s")
            
            return True
            
        except Exception as e:
            logger.error(f"TextGrid 동기화 중 오류: {e}")
            return False

class AutomationProcessor:
    """전체 자동화 처리 클래스"""
    
    def __init__(self, target_sample_rate: int = 16000, target_db: float = -20.0):
        self.audio_normalizer = AudioNormalizer(target_sample_rate, target_db)
        self.textgrid_sync = TextGridSynchronizer()
        
    def process_file_pair(self, wav_path: str, textgrid_path: str, 
                         output_wav: str, output_textgrid: str) -> Dict[str, any]:
        """
        WAV + TextGrid 파일 쌍 자동 처리
        Args:
            wav_path: 입력 WAV 파일
            textgrid_path: 입력 TextGrid 파일 
            output_wav: 출력 WAV 파일
            output_textgrid: 출력 TextGrid 파일
        Returns:
            처리 결과 정보
        """
        try:
            # 1. 오디오 처리
            audio_result = self.audio_normalizer.process_audio_file(wav_path, output_wav)
            
            # 2. TextGrid 동기화
            sync_success = self.textgrid_sync.synchronize_textgrid(
                textgrid_path, 
                output_textgrid,
                audio_result['time_ratio'],
                audio_result['final_duration']
            )
            
            result = {
                'status': 'success',
                'audio_processing': audio_result,
                'textgrid_sync': sync_success,
                'files_processed': {
                    'wav': {'input': wav_path, 'output': output_wav},
                    'textgrid': {'input': textgrid_path, 'output': output_textgrid}
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"파일 쌍 처리 중 오류: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'files_processed': {
                    'wav': {'input': wav_path, 'output': output_wav},
                    'textgrid': {'input': textgrid_path, 'output': output_textgrid}
                }
            }
            
    def process_directory(self, reference_dir: str, backup_dir: str) -> List[Dict[str, any]]:
        """
        디렉토리 내 모든 WAV+TextGrid 파일 쌍 자동 처리
        Args:
            reference_dir: 참조 파일 디렉토리
            backup_dir: 백업 디렉토리
        Returns:
            모든 파일 처리 결과 리스트
        """
        results = []
        
        # WAV 파일 목록 찾기
        wav_files = [f for f in os.listdir(backup_dir) if f.endswith('.wav')]
        
        for wav_file in wav_files:
            base_name = wav_file[:-4]  # .wav 제거
            textgrid_file = base_name + '.TextGrid'
            
            wav_path = os.path.join(backup_dir, wav_file)
            textgrid_path = os.path.join(backup_dir, textgrid_file)
            
            output_wav = os.path.join(reference_dir, wav_file)
            output_textgrid = os.path.join(reference_dir, textgrid_file)
            
            # 쌍이 모두 존재하는지 확인
            if os.path.exists(wav_path) and os.path.exists(textgrid_path):
                logger.info(f"처리 중: {base_name}")
                result = self.process_file_pair(wav_path, textgrid_path, output_wav, output_textgrid)
                result['file_name'] = base_name
                results.append(result)
            else:
                logger.warning(f"파일 쌍 불완전: {base_name}")
                results.append({
                    'status': 'skipped',
                    'file_name': base_name,
                    'reason': 'missing_pair'
                })
                
        return results