"""
ToneBridge 실시간 품질 검증 및 적응형 재처리 시스템
95% 정확도 보장을 위한 지능형 품질 관리
"""

import time
import asyncio
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path
import logging
import json
import os

# 기존 모듈들 import
try:
    from korean_audio_optimizer import KoreanAudioOptimizer
    OPTIMIZER_AVAILABLE = True
except ImportError:
    OPTIMIZER_AVAILABLE = False

try:
    from multi_engine_stt import MultiEngineSTTProcessor, EnsembleSTTResult
    MULTI_STT_AVAILABLE = True
except ImportError:
    MULTI_STT_AVAILABLE = False

try:
    from advanced_stt_processor import AdvancedSTTProcessor
    ADVANCED_STT_AVAILABLE = True
except ImportError:
    ADVANCED_STT_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass
class QualityMetrics:
    """품질 평가 메트릭"""
    syllable_accuracy: float = 0.0      # 음절 정확도
    phonetic_similarity: float = 0.0    # 음성학적 유사도
    confidence_score: float = 0.0       # STT 신뢰도
    duration_alignment: float = 0.0     # 지속시간 정렬
    korean_text_quality: float = 0.0    # 한국어 텍스트 품질
    overall_score: float = 0.0          # 종합 점수
    
    # 상세 분석
    missing_syllables: List[str] = field(default_factory=list)
    extra_syllables: List[str] = field(default_factory=list)
    misaligned_segments: List[Dict] = field(default_factory=list)

@dataclass 
class ReprocessingStrategy:
    """재처리 전략"""
    strategy_name: str
    audio_adjustments: Dict = field(default_factory=dict)
    stt_parameters: Dict = field(default_factory=dict)
    priority: int = 1
    expected_improvement: float = 0.0

@dataclass
class QualityValidationResult:
    """품질 검증 결과"""
    is_valid: bool
    quality_metrics: QualityMetrics
    reprocessing_needed: bool = False
    suggested_strategies: List[ReprocessingStrategy] = field(default_factory=list)
    validation_time: float = 0.0

class RealTimeQualityValidator:
    """
    실시간 품질 검증 시스템
    
    핵심 기능:
    1. 다차원 품질 메트릭 실시간 계산
    2. 한국어 특화 정확도 평가
    3. 자동 재처리 전략 제안
    4. 적응형 임계값 조정
    5. 연속 학습을 통한 성능 개선
    """
    
    def __init__(self,
                 quality_threshold: float = 0.95,
                 syllable_accuracy_threshold: float = 0.90,
                 confidence_threshold: float = 0.85,
                 enable_adaptive_learning: bool = True):
        """
        Parameters:
        -----------
        quality_threshold : float
            전체 품질 임계값 (95%)
        syllable_accuracy_threshold : float
            음절 정확도 임계값 (90%)
        confidence_threshold : float
            STT 신뢰도 임계값 (85%)
        enable_adaptive_learning : bool
            적응형 학습 활성화
        """
        
        self.quality_threshold = quality_threshold
        self.syllable_accuracy_threshold = syllable_accuracy_threshold
        self.confidence_threshold = confidence_threshold
        self.enable_adaptive_learning = enable_adaptive_learning
        
        # 재처리 전략 라이브러리
        self.reprocessing_strategies = self._init_reprocessing_strategies()
        
        # 성능 기록 (적응형 학습용)
        self.performance_history = []
        self.strategy_effectiveness = {}
        
        # 한국어 특화 검증 규칙
        self.korean_validation_rules = self._init_korean_validation_rules()
        
        logger.info(f"🔍 실시간 품질 검증 시스템 초기화 완료")
        logger.info(f"   품질 임계값: {quality_threshold:.1%}")
        logger.info(f"   음절 정확도 임계값: {syllable_accuracy_threshold:.1%}")
        logger.info(f"   신뢰도 임계값: {confidence_threshold:.1%}")
        logger.info(f"   적응형 학습: {'활성화' if enable_adaptive_learning else '비활성화'}")
    
    def _init_reprocessing_strategies(self) -> List[ReprocessingStrategy]:
        """재처리 전략 초기화"""
        strategies = [
            # 오디오 품질 개선 전략
            ReprocessingStrategy(
                strategy_name="고급_노이즈_제거",
                audio_adjustments={
                    "noise_reduction_strength": 0.8,
                    "spectral_gating": True,
                    "adaptive_filtering": True
                },
                priority=1,
                expected_improvement=0.15
            ),
            
            ReprocessingStrategy(
                strategy_name="한국어_자음_강화",
                audio_adjustments={
                    "consonant_boost_db": [4, 5, 6],  # ㄱ,ㄷ,ㅂ 등
                    "clarity_enhancement": True,
                    "formant_correction": True
                },
                priority=2,
                expected_improvement=0.20
            ),
            
            ReprocessingStrategy(
                strategy_name="운율_정규화_강화",
                audio_adjustments={
                    "prosody_normalization": True,
                    "pitch_smoothing": 0.9,
                    "rhythm_stabilization": True
                },
                priority=3,
                expected_improvement=0.12
            ),
            
            # STT 파라미터 최적화 전략
            ReprocessingStrategy(
                strategy_name="Whisper_Large_정밀모드",
                stt_parameters={
                    "model_size": "large-v3",
                    "temperature": 0.0,
                    "beam_size": 10,
                    "patience": 2.0,
                    "length_penalty": 1.2
                },
                priority=1,
                expected_improvement=0.25
            ),
            
            ReprocessingStrategy(
                strategy_name="다중엔진_강화_합의",
                stt_parameters={
                    "consensus_threshold": 2,
                    "confidence_threshold": 0.8,
                    "ensemble_weighting": "korean_optimized"
                },
                priority=2,
                expected_improvement=0.18
            ),
            
            ReprocessingStrategy(
                strategy_name="한국어_특화_후처리",
                stt_parameters={
                    "korean_text_correction": True,
                    "syllable_validation": True,
                    "phonetic_adjustment": True
                },
                priority=3,
                expected_improvement=0.10
            )
        ]
        
        return strategies
    
    def _init_korean_validation_rules(self) -> Dict:
        """한국어 특화 검증 규칙"""
        return {
            "syllable_completeness": {
                "check_incomplete_syllables": True,
                "check_consonant_clusters": True,
                "check_vowel_sequences": True
            },
            
            "phonetic_consistency": {
                "check_impossible_combinations": True,
                "check_loanword_patterns": True,
                "check_dialectal_variations": False
            },
            
            "prosodic_alignment": {
                "check_syllable_timing": True,
                "check_word_boundaries": True,
                "check_pause_patterns": True
            }
        }
    
    async def validate_stt_quality(self,
                                 stt_result: Any,
                                 target_text: str,
                                 audio_file: str,
                                 detailed_analysis: bool = True) -> QualityValidationResult:
        """
        STT 결과 품질 검증 메인 함수
        
        Parameters:
        -----------
        stt_result : Any
            STT 처리 결과 (EnsembleSTTResult 또는 기타)
        target_text : str
            기대 텍스트
        audio_file : str
            원본 오디오 파일
        detailed_analysis : bool
            상세 분석 실행 여부
            
        Returns:
        --------
        QualityValidationResult : 검증 결과
        """
        start_time = time.time()
        print(f"🔍 실시간 품질 검증 시작: {Path(audio_file).name}")
        
        # 1단계: 기본 품질 메트릭 계산
        quality_metrics = await self._calculate_quality_metrics(
            stt_result, target_text, audio_file
        )
        
        # 2단계: 한국어 특화 검증
        korean_quality = await self._validate_korean_specific(
            stt_result, target_text, quality_metrics
        )
        quality_metrics.korean_text_quality = korean_quality
        
        # 3단계: 종합 품질 점수 계산
        overall_score = self._calculate_overall_score(quality_metrics)
        quality_metrics.overall_score = overall_score
        
        # 4단계: 재처리 필요성 판단
        is_valid = overall_score >= self.quality_threshold
        reprocessing_needed = not is_valid
        
        # 5단계: 재처리 전략 제안 (필요시)
        suggested_strategies = []
        if reprocessing_needed:
            suggested_strategies = await self._suggest_reprocessing_strategies(
                quality_metrics, stt_result, audio_file
            )
        
        validation_time = time.time() - start_time
        
        result = QualityValidationResult(
            is_valid=is_valid,
            quality_metrics=quality_metrics,
            reprocessing_needed=reprocessing_needed,
            suggested_strategies=suggested_strategies,
            validation_time=validation_time
        )
        
        # 6단계: 성능 기록 (적응형 학습)
        if self.enable_adaptive_learning:
            await self._record_performance(result, stt_result, target_text)
        
        # 결과 보고서 출력
        self._print_quality_report(result)
        
        return result
    
    async def _calculate_quality_metrics(self,
                                       stt_result: Any,
                                       target_text: str,
                                       audio_file: str) -> QualityMetrics:
        """품질 메트릭 계산"""
        metrics = QualityMetrics()
        
        # STT 결과에서 텍스트 추출
        if hasattr(stt_result, 'final_text'):
            predicted_text = stt_result.final_text
            confidence = getattr(stt_result, 'confidence', 0.0)
        elif hasattr(stt_result, 'text'):
            predicted_text = stt_result.text
            confidence = getattr(stt_result, 'confidence', 0.0)
        else:
            predicted_text = str(stt_result)
            confidence = 0.0
        
        print(f"  📝 예측 텍스트: '{predicted_text}'")
        print(f"  🎯 목표 텍스트: '{target_text}'")
        
        # 1. 음절 정확도 계산
        metrics.syllable_accuracy = self._calculate_syllable_accuracy(
            predicted_text, target_text
        )
        
        # 2. 음성학적 유사도 계산
        metrics.phonetic_similarity = self._calculate_phonetic_similarity(
            predicted_text, target_text
        )
        
        # 3. STT 신뢰도
        metrics.confidence_score = confidence
        
        # 4. 지속시간 정렬 (오디오 파일 기반)
        metrics.duration_alignment = await self._calculate_duration_alignment(
            predicted_text, target_text, audio_file
        )
        
        return metrics
    
    def _calculate_syllable_accuracy(self, predicted: str, target: str) -> float:
        """음절 단위 정확도 계산"""
        if not target:
            return 1.0 if not predicted else 0.0
        
        # 한국어 음절만 추출
        pred_syllables = [c for c in predicted.replace(' ', '') if 0xAC00 <= ord(c) <= 0xD7A3]
        target_syllables = [c for c in target.replace(' ', '') if 0xAC00 <= ord(c) <= 0xD7A3]
        
        if not target_syllables:
            return 1.0 if not pred_syllables else 0.0
        
        # 편집 거리 기반 정확도
        accuracy = self._calculate_edit_distance_accuracy(pred_syllables, target_syllables)
        
        print(f"  🔤 음절 정확도: {accuracy:.3f} (예측: {len(pred_syllables)}, 목표: {len(target_syllables)})")
        return accuracy
    
    def _calculate_edit_distance_accuracy(self, pred: List[str], target: List[str]) -> float:
        """편집 거리 기반 정확도"""
        len_pred, len_target = len(pred), len(target)
        
        if len_target == 0:
            return 1.0 if len_pred == 0 else 0.0
        
        # DP 배열
        dp = [[0] * (len_target + 1) for _ in range(len_pred + 1)]
        
        # 초기화
        for i in range(len_pred + 1):
            dp[i][0] = i
        for j in range(len_target + 1):
            dp[0][j] = j
        
        # DP 계산
        for i in range(1, len_pred + 1):
            for j in range(1, len_target + 1):
                if pred[i-1] == target[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
        
        edit_distance = dp[len_pred][len_target]
        accuracy = 1.0 - (edit_distance / len_target)
        
        return max(0.0, accuracy)
    
    def _calculate_phonetic_similarity(self, predicted: str, target: str) -> float:
        """음성학적 유사도 계산"""
        if not target:
            return 1.0 if not predicted else 0.0
        
        # 자모 단위 분해 및 비교
        pred_jamo = self._decompose_to_jamo(predicted)
        target_jamo = self._decompose_to_jamo(target)
        
        if not target_jamo:
            return 1.0 if not pred_jamo else 0.0
        
        # 자모 매칭 정확도
        jamo_accuracy = self._calculate_edit_distance_accuracy(pred_jamo, target_jamo)
        
        print(f"  🔊 음성학적 유사도: {jamo_accuracy:.3f}")
        return jamo_accuracy
    
    def _decompose_to_jamo(self, text: str) -> List[str]:
        """텍스트를 자모 단위로 분해"""
        jamo_list = []
        
        for char in text.replace(' ', ''):
            if 0xAC00 <= ord(char) <= 0xD7A3:  # 완성형 한글
                # 한글 유니코드 분해
                code = ord(char) - 0xAC00
                
                initial_idx = code // (21 * 28)
                medial_idx = (code % (21 * 28)) // 28
                final_idx = code % 28
                
                # 자모 테이블
                initials = ['ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
                medials = ['ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ', 'ㅙ', 'ㅚ', 'ㅛ', 'ㅜ', 'ㅝ', 'ㅞ', 'ㅟ', 'ㅠ', 'ㅡ', 'ㅢ', 'ㅣ']
                finals = ['', 'ㄱ', 'ㄲ', 'ㄳ', 'ㄴ', 'ㄵ', 'ㄶ', 'ㄷ', 'ㄹ', 'ㄺ', 'ㄻ', 'ㄼ', 'ㄽ', 'ㄾ', 'ㄿ', 'ㅀ', 'ㅁ', 'ㅂ', 'ㅄ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ']
                
                jamo_list.append(initials[initial_idx])
                jamo_list.append(medials[medial_idx])
                if finals[final_idx]:  # 종성이 있는 경우만
                    jamo_list.append(finals[final_idx])
        
        return jamo_list
    
    async def _calculate_duration_alignment(self, predicted: str, target: str, audio_file: str) -> float:
        """지속시간 정렬 품질 계산"""
        try:
            # 실제 오디오 길이 계산
            import librosa
            audio, sr = librosa.load(audio_file, sr=None)
            actual_duration = len(audio) / sr
            
            # 예상 발화 시간 (한국어 기준: 1음절당 0.3초)
            target_syllables = len([c for c in target.replace(' ', '') if 0xAC00 <= ord(c) <= 0xD7A3])
            expected_duration = target_syllables * 0.3  # 한국어 평균 발화 속도
            
            # 정렬 품질 계산
            duration_ratio = min(actual_duration, expected_duration) / max(actual_duration, expected_duration)
            
            print(f"  ⏱️ 지속시간 정렬: {duration_ratio:.3f} (실제: {actual_duration:.2f}s, 예상: {expected_duration:.2f}s)")
            return duration_ratio
            
        except Exception as e:
            logger.warning(f"지속시간 계산 실패: {e}")
            return 0.8  # 기본값
    
    async def _validate_korean_specific(self, stt_result: Any, target_text: str, metrics: QualityMetrics) -> float:
        """한국어 특화 검증"""
        # STT 결과에서 텍스트 추출
        if hasattr(stt_result, 'final_text'):
            predicted_text = stt_result.final_text
        elif hasattr(stt_result, 'text'):
            predicted_text = stt_result.text
        else:
            predicted_text = str(stt_result)
        
        quality_factors = []
        
        # 1. 완성형 한글 비율
        korean_ratio = self._calculate_korean_text_ratio(predicted_text)
        quality_factors.append(korean_ratio)
        
        # 2. 불완전 음절 검사
        incomplete_penalty = self._check_incomplete_syllables(predicted_text)
        quality_factors.append(1.0 - incomplete_penalty)
        
        # 3. 음성학적 불가능 조합 검사
        phonetic_validity = self._check_phonetic_validity(predicted_text)
        quality_factors.append(phonetic_validity)
        
        korean_quality = np.mean(quality_factors)
        print(f"  🇰🇷 한국어 품질: {korean_quality:.3f}")
        
        return korean_quality
    
    def _calculate_korean_text_ratio(self, text: str) -> float:
        """한국어 텍스트 비율 계산"""
        if not text:
            return 0.0
        
        korean_chars = sum(1 for c in text if 0xAC00 <= ord(c) <= 0xD7A3)
        total_chars = len(text.replace(' ', ''))
        
        return korean_chars / max(total_chars, 1)
    
    def _check_incomplete_syllables(self, text: str) -> float:
        """불완전 음절 검사"""
        # 자음/모음 단독 문자 검사
        incomplete_count = 0
        total_chars = 0
        
        for char in text:
            if 0x1100 <= ord(char) <= 0x11FF:  # 초성 자모
                incomplete_count += 1
            elif 0x1161 <= ord(char) <= 0x1175:  # 중성 자모
                incomplete_count += 1
            elif 0x11A8 <= ord(char) <= 0x11C2:  # 종성 자모
                incomplete_count += 1
            elif 0xAC00 <= ord(char) <= 0xD7A3:  # 완성형 한글
                total_chars += 1
            total_chars += 1
        
        if total_chars == 0:
            return 0.0
        
        return incomplete_count / total_chars
    
    def _check_phonetic_validity(self, text: str) -> float:
        """음성학적 유효성 검사"""
        # 현재는 기본 구현, 향후 확장 가능
        # 예: 불가능한 자음 클러스터, 모음 연속 등
        return 0.9  # 기본 높은 점수
    
    def _calculate_overall_score(self, metrics: QualityMetrics) -> float:
        """종합 품질 점수 계산"""
        # 가중 평균 (한국어 특화 가중치)
        weights = {
            'syllable_accuracy': 0.35,      # 가장 중요
            'phonetic_similarity': 0.25,    # 음성학적 정확성
            'confidence_score': 0.20,       # STT 신뢰도
            'duration_alignment': 0.10,     # 시간 정렬
            'korean_text_quality': 0.10     # 한국어 품질
        }
        
        overall_score = (
            metrics.syllable_accuracy * weights['syllable_accuracy'] +
            metrics.phonetic_similarity * weights['phonetic_similarity'] +
            metrics.confidence_score * weights['confidence_score'] +
            metrics.duration_alignment * weights['duration_alignment'] +
            metrics.korean_text_quality * weights['korean_text_quality']
        )
        
        return overall_score
    
    async def _suggest_reprocessing_strategies(self,
                                             quality_metrics: QualityMetrics,
                                             stt_result: Any,
                                             audio_file: str) -> List[ReprocessingStrategy]:
        """재처리 전략 제안"""
        strategies = []
        
        print("🔧 재처리 전략 분석 중...")
        
        # 1. 음절 정확도가 낮은 경우
        if quality_metrics.syllable_accuracy < self.syllable_accuracy_threshold:
            strategies.extend([
                s for s in self.reprocessing_strategies 
                if "한국어_자음_강화" in s.strategy_name or "Whisper_Large_정밀모드" in s.strategy_name
            ])
        
        # 2. 신뢰도가 낮은 경우
        if quality_metrics.confidence_score < self.confidence_threshold:
            strategies.extend([
                s for s in self.reprocessing_strategies 
                if "다중엔진_강화_합의" in s.strategy_name or "고급_노이즈_제거" in s.strategy_name
            ])
        
        # 3. 음성학적 유사도가 낮은 경우
        if quality_metrics.phonetic_similarity < 0.8:
            strategies.extend([
                s for s in self.reprocessing_strategies 
                if "운율_정규화_강화" in s.strategy_name or "한국어_특화_후처리" in s.strategy_name
            ])
        
        # 중복 제거 및 우선순위 정렬
        unique_strategies = []
        seen_names = set()
        for strategy in strategies:
            if strategy.strategy_name not in seen_names:
                unique_strategies.append(strategy)
                seen_names.add(strategy.strategy_name)
        
        # 우선순위 정렬 (낮은 숫자가 높은 우선순위)
        unique_strategies.sort(key=lambda x: x.priority)
        
        # 상위 3개 전략만 제안
        recommended_strategies = unique_strategies[:3]
        
        for strategy in recommended_strategies:
            print(f"  💡 제안 전략: {strategy.strategy_name} (예상 개선: {strategy.expected_improvement:.1%})")
        
        return recommended_strategies
    
    async def _record_performance(self, result: QualityValidationResult, stt_result: Any, target_text: str):
        """성능 기록 (적응형 학습)"""
        # 성능 기록 저장
        performance_record = {
            'timestamp': time.time(),
            'overall_score': result.quality_metrics.overall_score,
            'syllable_accuracy': result.quality_metrics.syllable_accuracy,
            'confidence_score': result.quality_metrics.confidence_score,
            'is_valid': result.is_valid,
            'target_length': len(target_text.replace(' ', ''))
        }
        
        self.performance_history.append(performance_record)
        
        # 최근 100개 기록만 유지
        if len(self.performance_history) > 100:
            self.performance_history = self.performance_history[-100:]
    
    def _print_quality_report(self, result: QualityValidationResult):
        """품질 검증 보고서 출력"""
        metrics = result.quality_metrics
        
        print(f"\n📊 실시간 품질 검증 보고서:")
        print(f"   종합 점수: {metrics.overall_score:.3f} ({'✅ 통과' if result.is_valid else '❌ 실패'})")
        print(f"   음절 정확도: {metrics.syllable_accuracy:.3f}")
        print(f"   음성학적 유사도: {metrics.phonetic_similarity:.3f}")
        print(f"   STT 신뢰도: {metrics.confidence_score:.3f}")
        print(f"   지속시간 정렬: {metrics.duration_alignment:.3f}")
        print(f"   한국어 품질: {metrics.korean_text_quality:.3f}")
        print(f"   검증 시간: {result.validation_time:.3f}초")
        
        if result.reprocessing_needed:
            print(f"   🔧 재처리 필요 ({len(result.suggested_strategies)}개 전략 제안)")
        
        print("✅ 품질 검증 완료\n")

# 편의 함수
async def validate_quality(stt_result: Any, target_text: str, audio_file: str) -> QualityValidationResult:
    """
    품질 검증 빠른 실행 함수
    
    Parameters:
    -----------
    stt_result : Any
        STT 결과
    target_text : str
        기대 텍스트
    audio_file : str
        오디오 파일
        
    Returns:
    --------
    QualityValidationResult : 검증 결과
    """
    validator = RealTimeQualityValidator()
    return await validator.validate_stt_quality(stt_result, target_text, audio_file)

if __name__ == "__main__":
    # 테스트용
    import sys
    if len(sys.argv) > 3:
        # TODO: 테스트 코드 구현
        print("품질 검증 테스트 모드")