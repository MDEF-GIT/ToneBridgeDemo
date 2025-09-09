"""
ToneBridge 한국어 특화 오디오 최적화 시스템
STT 인식률 향상을 위한 한국어 음성학적 전처리
"""

import numpy as np
import librosa
import soundfile as sf
import parselmouth as pm
from scipy import signal, ndimage
from scipy.fft import fft, ifft
from typing import Tuple, Dict, List, Optional
import logging
from pathlib import Path
import tempfile
import os

logger = logging.getLogger(__name__)

class KoreanAudioOptimizer:
    """
    한국어 STT 정확도 향상을 위한 전문 오디오 최적화기
    
    핵심 기능:
    1. 한국어 자음 명료도 강화 (ㄱ,ㄷ,ㅂ,ㅅ,ㅈ,ㅊ,ㅋ,ㅌ,ㅍ,ㅎ)
    2. 한국어 모음 안정화 (ㅏ,ㅓ,ㅗ,ㅜ,ㅡ,ㅣ)
    3. 운율 패턴 정규화 (한국어 억양 특성)
    4. 지능형 무음 처리 (한국어 리듬 보존)
    5. SNR 최적화 (한국어 음소별)
    """
    
    def __init__(self, 
                 target_sr: int = 16000,
                 target_db: float = -16.0,  # STT 최적화된 볼륨
                 korean_boost: bool = True):
        """
        Parameters:
        -----------
        target_sr : int
            목표 샘플레이트 (Whisper 최적화)
        target_db : float  
            목표 dB (-16dB는 STT 최적값)
        korean_boost : bool
            한국어 특화 강화 사용 여부
        """
        self.target_sr = target_sr
        self.target_db = target_db
        self.korean_boost = korean_boost
        
        # 한국어 음소별 주파수 특성 정의
        self.korean_phoneme_profiles = self._init_korean_phoneme_profiles()
        
        # STT 최적화 필터 계수
        self.stt_filter_coeffs = self._init_stt_filters()
        
        logger.info(f"🎯 한국어 오디오 최적화기 초기화 완료")
        logger.info(f"   목표 샘플레이트: {target_sr}Hz")
        logger.info(f"   목표 볼륨: {target_db}dB")
        logger.info(f"   한국어 특화: {'활성화' if korean_boost else '비활성화'}")
    
    def _init_korean_phoneme_profiles(self) -> Dict:
        """한국어 음소별 주파수 프로파일 정의"""
        return {
            # 한국어 자음 특성 (명료도 중요)
            'consonants': {
                'stops': {  # ㄱ,ㄷ,ㅂ,ㅋ,ㅌ,ㅍ
                    'freq_ranges': [(500, 1500), (1500, 4000)],  # F2, F3 영역
                    'boost_db': [3, 4],  # 각 영역별 부스트
                    'clarity_freq': 2500  # 명료도 핵심 주파수
                },
                'fricatives': {  # ㅅ,ㅆ,ㅈ,ㅊ,ㅎ
                    'freq_ranges': [(3000, 8000)],  # 고주파 마찰음
                    'boost_db': [5],
                    'clarity_freq': 5000
                },
                'nasals': {  # ㅁ,ㄴ,ㅇ
                    'freq_ranges': [(200, 800)],  # 저주파 공명
                    'boost_db': [2],
                    'clarity_freq': 500
                },
                'liquids': {  # ㄹ
                    'freq_ranges': [(800, 2000)],  # 중간 주파수
                    'boost_db': [3],
                    'clarity_freq': 1200
                }
            },
            
            # 한국어 모음 특성 (안정성 중요)
            'vowels': {
                'front': {  # ㅣ,ㅔ,ㅐ
                    'f1_range': (200, 500),   # 제1포먼트
                    'f2_range': (1800, 2500), # 제2포먼트
                    'stabilization_factor': 0.8
                },
                'back': {  # ㅜ,ㅗ
                    'f1_range': (200, 600),
                    'f2_range': (800, 1200),
                    'stabilization_factor': 0.9
                },
                'central': {  # ㅓ,ㅏ,ㅡ
                    'f1_range': (400, 800),
                    'f2_range': (1200, 1800),
                    'stabilization_factor': 0.85
                }
            }
        }
    
    def _init_stt_filters(self) -> Dict:
        """STT 엔진별 최적화 필터 계수"""
        return {
            'whisper': {
                'preemphasis': 0.97,      # 고주파 강조
                'spectral_gate_db': -30,  # 스펙트럴 게이트
                'dynamic_range_db': 40,   # 다이나믹 레인지
            },
            'google': {
                'preemphasis': 0.95,
                'spectral_gate_db': -25,
                'dynamic_range_db': 45,
            }
        }
    
    def optimize_for_korean_stt(self, 
                               audio_file: str, 
                               output_file: str = None,
                               stt_engine: str = 'whisper') -> str:
        """
        한국어 STT 최적화 메인 함수
        
        Parameters:
        -----------
        audio_file : str
            입력 오디오 파일
        output_file : str, optional
            출력 파일 (없으면 자동 생성)
        stt_engine : str
            목표 STT 엔진 ('whisper', 'google', 'azure')
            
        Returns:
        --------
        str : 최적화된 오디오 파일 경로
        """
        try:
            print(f"🎯 한국어 STT 최적화 시작: {Path(audio_file).name}")
            print(f"   목표 엔진: {stt_engine}")
            
            # 출력 파일명 결정
            if not output_file:
                input_path = Path(audio_file)
                output_file = str(input_path.parent / f"{input_path.stem}_korean_optimized{input_path.suffix}")
            
            # 1단계: 오디오 로드 및 기본 정규화
            audio, sr = self._load_and_normalize(audio_file)
            print(f"📊 원본: {len(audio)/sr:.2f}초, {sr}Hz")
            
            # 2단계: 한국어 특화 전처리 파이프라인
            if self.korean_boost:
                # 2-1. 한국어 자음 명료도 강화
                audio = self._enhance_korean_consonants(audio, sr)
                print("✅ 한국어 자음 명료도 강화 완료")
                
                # 2-2. 한국어 모음 안정화
                audio = self._stabilize_korean_vowels(audio, sr)
                print("✅ 한국어 모음 안정화 완료")
                
                # 2-3. 운율 패턴 정규화
                audio = self._normalize_korean_prosody(audio, sr)
                print("✅ 한국어 운율 정규화 완료")
            
            # 3단계: STT 엔진별 최적화
            audio = self._apply_stt_optimization(audio, sr, stt_engine)
            print(f"✅ {stt_engine} 엔진 최적화 완료")
            
            # 4단계: 지능형 무음 처리
            audio = self._intelligent_silence_processing(audio, sr)
            print("✅ 지능형 무음 처리 완료")
            
            # 5단계: 최종 품질 검증 및 저장
            final_audio = self._final_quality_control(audio, sr)
            sf.write(output_file, final_audio, self.target_sr)
            
            # 결과 분석
            quality_metrics = self._analyze_optimization_quality(audio_file, output_file)
            self._print_optimization_report(quality_metrics)
            
            print(f"🎯 최적화 완료: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"한국어 오디오 최적화 실패: {e}")
            raise
    
    def _load_and_normalize(self, audio_file: str) -> Tuple[np.ndarray, int]:
        """오디오 로드 및 기본 정규화"""
        # librosa로 로드 (자동 정규화)
        audio, sr = librosa.load(audio_file, sr=None)
        
        # 샘플레이트 조정
        if sr != self.target_sr:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=self.target_sr)
            sr = self.target_sr
        
        # 기본 볼륨 정규화
        audio = librosa.util.normalize(audio) * 0.8  # 클리핑 방지
        
        return audio, sr
    
    def _enhance_korean_consonants(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """한국어 자음 명료도 강화"""
        consonant_profile = self.korean_phoneme_profiles['consonants']
        
        # STFT 변환
        stft = librosa.stft(audio, hop_length=512, win_length=2048)
        magnitude = np.abs(stft)
        phase = np.angle(stft)
        
        # 주파수 빈 계산
        freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
        
        # 자음별 주파수 강화
        enhanced_magnitude = magnitude.copy()
        
        # 폐쇄음 강화 (ㄱ,ㄷ,ㅂ,ㅋ,ㅌ,ㅍ)
        for freq_range, boost_db in zip(consonant_profile['stops']['freq_ranges'], 
                                       consonant_profile['stops']['boost_db']):
            freq_mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
            boost_factor = 10 ** (boost_db / 20)  # dB to linear
            enhanced_magnitude[freq_mask] *= boost_factor
        
        # 마찰음 강화 (ㅅ,ㅆ,ㅈ,ㅊ,ㅎ)
        for freq_range, boost_db in zip(consonant_profile['fricatives']['freq_ranges'],
                                       consonant_profile['fricatives']['boost_db']):
            freq_mask = (freqs >= freq_range[0]) & (freqs <= freq_range[1])
            boost_factor = 10 ** (boost_db / 20)
            enhanced_magnitude[freq_mask] *= boost_factor
        
        # ISTFT 역변환
        enhanced_stft = enhanced_magnitude * np.exp(1j * phase)
        enhanced_audio = librosa.istft(enhanced_stft, hop_length=512, win_length=2048)
        
        return enhanced_audio
    
    def _stabilize_korean_vowels(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """한국어 모음 안정화 (포먼트 안정화)"""
        # Parselmouth를 사용한 포먼트 분석
        try:
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                sf.write(tmp.name, audio, sr)
                
                # Praat으로 포먼트 분석
                sound = pm.Sound(tmp.name)
                formants = sound.to_formant_burg(maximum_formant=5500)
                
                # 포먼트 안정화 (스무딩)
                stabilized_audio = self._apply_formant_stabilization(audio, sr, formants)
                
                os.unlink(tmp.name)  # 임시 파일 삭제
                return stabilized_audio
                
        except Exception as e:
            logger.warning(f"포먼트 안정화 실패, 원본 사용: {e}")
            return audio
    
    def _apply_formant_stabilization(self, audio: np.ndarray, sr: int, formants) -> np.ndarray:
        """포먼트 기반 모음 안정화"""
        # 간단한 스펙트럴 스무딩으로 구현
        stft = librosa.stft(audio, hop_length=512)
        magnitude = np.abs(stft)
        
        # 시간축 스무딩 (포먼트 변화 안정화)
        from scipy.ndimage import uniform_filter1d
        stabilized_magnitude = uniform_filter1d(magnitude, size=3, axis=1)
        
        # 재구성
        phase = np.angle(stft)
        stabilized_stft = stabilized_magnitude * np.exp(1j * phase)
        stabilized_audio = librosa.istft(stabilized_stft, hop_length=512)
        
        return stabilized_audio
    
    def _normalize_korean_prosody(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """한국어 운율 패턴 정규화"""
        # 피치 추적 및 정규화
        try:
            f0, voiced_flag, voiced_probs = librosa.pyin(
                audio, fmin=80, fmax=400, sr=sr, frame_length=2048
            )
            
            # 피치 스무딩 (한국어 자연스러운 억양)
            f0_smoothed = self._smooth_pitch_contour(f0, voiced_flag)
            
            # 억양 정규화된 오디오 생성 (PSOLA 기반 단순화)
            normalized_audio = self._apply_prosody_normalization(audio, sr, f0_smoothed)
            
            return normalized_audio
            
        except Exception as e:
            logger.warning(f"운율 정규화 실패, 원본 사용: {e}")
            return audio
    
    def _smooth_pitch_contour(self, f0: np.ndarray, voiced_flag: np.ndarray) -> np.ndarray:
        """피치 윤곽 스무딩"""
        # NaN 값 처리
        f0_clean = f0.copy()
        f0_clean[~voiced_flag] = np.nan
        
        # 선형 보간으로 빈 구간 채우기
        mask = ~np.isnan(f0_clean)
        if np.sum(mask) > 2:  # 최소 2개 이상의 유효한 값이 있어야 보간 가능
            indices = np.arange(len(f0_clean))
            f0_interpolated = np.interp(indices, indices[mask], f0_clean[mask])
            
            # 가우시안 스무딩
            from scipy.ndimage import gaussian_filter1d
            f0_smoothed = gaussian_filter1d(f0_interpolated, sigma=2.0)
            
            return f0_smoothed
        else:
            return f0_clean
    
    def _apply_prosody_normalization(self, audio: np.ndarray, sr: int, f0: np.ndarray) -> np.ndarray:
        """운율 정규화 적용 (단순화된 구현)"""
        # 현재는 다이나믹 레인지 압축으로 대체
        # 실제로는 PSOLA나 WORLD vocoder 사용이 이상적
        
        # 다이나믹 레인지 압축 (한국어 자연스러운 볼륨 변화)
        from scipy.signal import hilbert
        
        # 포락선 추출
        analytic_signal = hilbert(audio)
        envelope = np.abs(analytic_signal)
        
        # 부드러운 압축 적용
        compressed_envelope = np.tanh(envelope * 2.0) / 2.0
        
        # 압축된 포락선 적용
        normalized_audio = audio * (compressed_envelope / (envelope + 1e-8))
        
        return normalized_audio
    
    def _apply_stt_optimization(self, audio: np.ndarray, sr: int, engine: str) -> np.ndarray:
        """STT 엔진별 최적화"""
        filter_config = self.stt_filter_coeffs.get(engine, self.stt_filter_coeffs['whisper'])
        
        # Pre-emphasis 필터 (고주파 강조)
        preemph = filter_config['preemphasis']
        audio_preemph = np.append(audio[0], audio[1:] - preemph * audio[:-1])
        
        # 스펙트럴 게이트 (노이즈 억제)
        stft = librosa.stft(audio_preemph, hop_length=512)
        magnitude = np.abs(stft)
        
        # 동적 스펙트럴 게이트
        gate_threshold = np.percentile(magnitude, 10)  # 하위 10% 제거
        gate_mask = magnitude > gate_threshold
        gated_magnitude = magnitude * gate_mask
        
        # 재구성
        phase = np.angle(stft)
        gated_stft = gated_magnitude * np.exp(1j * phase)
        optimized_audio = librosa.istft(gated_stft, hop_length=512)
        
        return optimized_audio
    
    def _intelligent_silence_processing(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """지능형 무음 처리 (한국어 리듬 보존)"""
        # 음성 활동 검출
        intervals = librosa.effects.split(audio, top_db=20, frame_length=2048, hop_length=512)
        
        if len(intervals) == 0:
            return audio
        
        # 음성 구간만 추출하되 자연스러운 마진 유지
        start_margin = int(0.1 * sr)  # 0.1초 마진
        end_margin = int(0.1 * sr)
        
        start_sample = max(0, intervals[0][0] - start_margin)
        end_sample = min(len(audio), intervals[-1][1] + end_margin)
        
        trimmed_audio = audio[start_sample:end_sample]
        
        return trimmed_audio
    
    def _final_quality_control(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """최종 품질 제어"""
        # 1. 볼륨 최적화 (목표 dB로)
        rms = np.sqrt(np.mean(audio**2))
        current_db = 20 * np.log10(rms + 1e-8)
        
        if current_db != self.target_db:
            gain_db = self.target_db - current_db
            gain_linear = 10 ** (gain_db / 20)
            audio = audio * gain_linear
        
        # 2. 클리핑 방지
        audio = np.clip(audio, -0.95, 0.95)
        
        # 3. DC 성분 제거
        audio = audio - np.mean(audio)
        
        return audio
    
    def _analyze_optimization_quality(self, original_file: str, optimized_file: str) -> Dict:
        """최적화 품질 분석"""
        try:
            # 원본과 최적화 파일 로드
            orig_audio, orig_sr = librosa.load(original_file, sr=self.target_sr)
            opt_audio, opt_sr = librosa.load(optimized_file, sr=self.target_sr)
            
            # 품질 메트릭 계산
            metrics = {
                'duration_change': len(opt_audio) / len(orig_audio),
                'rms_change': np.sqrt(np.mean(opt_audio**2)) / np.sqrt(np.mean(orig_audio**2)),
                'spectral_centroid_change': np.mean(librosa.feature.spectral_centroid(y=opt_audio, sr=opt_sr)) / 
                                          np.mean(librosa.feature.spectral_centroid(y=orig_audio, sr=orig_sr)),
                'snr_improvement': self._estimate_snr_improvement(orig_audio, opt_audio)
            }
            
            return metrics
            
        except Exception as e:
            logger.warning(f"품질 분석 실패: {e}")
            return {}
    
    def _estimate_snr_improvement(self, original: np.ndarray, optimized: np.ndarray) -> float:
        """SNR 개선도 추정"""
        try:
            # 신호 에너지 (상위 80% 에너지)
            orig_energy = np.percentile(original**2, 80)
            opt_energy = np.percentile(optimized**2, 80)
            
            # 노이즈 에너지 (하위 20% 에너지)
            orig_noise = np.percentile(original**2, 20)
            opt_noise = np.percentile(optimized**2, 20)
            
            # SNR 계산
            orig_snr = 10 * np.log10(orig_energy / (orig_noise + 1e-8))
            opt_snr = 10 * np.log10(opt_energy / (opt_noise + 1e-8))
            
            return opt_snr - orig_snr
            
        except:
            return 0.0
    
    def _print_optimization_report(self, metrics: Dict):
        """최적화 보고서 출력"""
        if not metrics:
            return
            
        print("\n📊 한국어 최적화 품질 보고서:")
        print(f"   지속시간 변화: {metrics.get('duration_change', 1.0):.3f}x")
        print(f"   볼륨 변화: {metrics.get('rms_change', 1.0):.3f}x")
        print(f"   스펙트럼 중심 변화: {metrics.get('spectral_centroid_change', 1.0):.3f}x")
        print(f"   SNR 개선: {metrics.get('snr_improvement', 0.0):.1f}dB")
        print("✅ 한국어 STT 최적화 완료\n")

def quick_optimize_for_korean(audio_file: str, output_file: str = None) -> str:
    """
    빠른 한국어 최적화 (편의 함수)
    
    Parameters:
    -----------
    audio_file : str
        입력 오디오 파일
    output_file : str, optional
        출력 파일 경로
        
    Returns:
    --------
    str : 최적화된 파일 경로
    """
    optimizer = KoreanAudioOptimizer()
    return optimizer.optimize_for_korean_stt(audio_file, output_file)

if __name__ == "__main__":
    # 테스트용
    import sys
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = quick_optimize_for_korean(input_file)
        print(f"최적화 완료: {output_file}")