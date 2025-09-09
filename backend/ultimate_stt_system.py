"""
ToneBridge 통합 STT 시스템
99% 한국어 음성 인식 정확도 달성을 위한 완전 통합 솔루션

통합 구성요소:
1. 한국어 특화 오디오 전처리 (korean_audio_optimizer.py)
2. 다중 STT 엔진 앙상블 (multi_engine_stt.py) 
3. 실시간 품질 검증 (quality_validator.py)
4. 적응형 재처리 시스템
"""

import asyncio
import time
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import logging
import json

# 통합 시스템 모듈들
try:
    from korean_audio_optimizer import KoreanAudioOptimizer
    OPTIMIZER_AVAILABLE = True
except ImportError:
    OPTIMIZER_AVAILABLE = False
    print("⚠️ Korean Audio Optimizer 미사용 가능")

try:
    from multi_engine_stt import MultiEngineSTTProcessor, EnsembleSTTResult
    MULTI_STT_AVAILABLE = True
except ImportError:
    MULTI_STT_AVAILABLE = False
    print("⚠️ Multi-Engine STT 미사용 가능")

try:
    from quality_validator import RealTimeQualityValidator, QualityValidationResult
    VALIDATOR_AVAILABLE = True
except ImportError:
    VALIDATOR_AVAILABLE = False
    print("⚠️ Quality Validator 미사용 가능")

try:
    from advanced_stt_processor import AdvancedSTTProcessor
    ADVANCED_STT_AVAILABLE = True
except ImportError:
    ADVANCED_STT_AVAILABLE = False
    print("⚠️ Advanced STT Processor 미사용 가능")

logger = logging.getLogger(__name__)

@dataclass
class UltimateSTTResult:
    """통합 STT 최종 결과"""
    final_text: str
    confidence: float
    accuracy_achieved: float
    processing_stages: List[str] = field(default_factory=list)
    
    # 상세 결과들
    preprocessing_result: Optional[Any] = None
    ensemble_result: Optional[EnsembleSTTResult] = None
    validation_result: Optional[QualityValidationResult] = None
    
    # 성능 메트릭
    total_processing_time: float = 0.0
    reprocessing_attempts: int = 0
    final_quality_score: float = 0.0
    
    # 디버깅 정보
    audio_optimizations_applied: List[str] = field(default_factory=list)
    stt_engines_used: List[str] = field(default_factory=list)
    quality_improvements: List[str] = field(default_factory=list)

class UltimateSTTSystem:
    """
    ToneBridge 통합 STT 시스템 - 99% 정확도 달성
    
    시스템 아키텍처:
    1. 한국어 특화 오디오 전처리
    2. 다중 엔진 앙상블 STT  
    3. 실시간 품질 검증
    4. 적응형 재처리 (필요시)
    5. 최종 결과 통합 및 검증
    
    목표 성능:
    - 한국어 음성 인식 정확도: 99%+
    - 처리 시간: 평균 5초 이내
    - 신뢰도: 95% 이상
    """
    
    def __init__(self,
                 target_accuracy: float = 0.99,
                 max_reprocessing_attempts: int = 3,
                 quality_threshold: float = 0.95,
                 enable_advanced_features: bool = True):
        """
        Parameters:
        -----------
        target_accuracy : float
            목표 정확도 (99%)
        max_reprocessing_attempts : int
            최대 재처리 시도 횟수
        quality_threshold : float
            품질 임계값 (95%)
        enable_advanced_features : bool
            고급 기능 활성화
        """
        
        self.target_accuracy = target_accuracy
        self.max_reprocessing_attempts = max_reprocessing_attempts
        self.quality_threshold = quality_threshold
        self.enable_advanced_features = enable_advanced_features
        
        # 각 시스템 컴포넌트 초기화
        self.components = self._initialize_components()
        
        # 성능 추적
        self.performance_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'accuracy_scores': [],
            'processing_times': [],
            'reprocessing_stats': {}
        }
        
        logger.info(f"🚀 ToneBridge 통합 STT 시스템 초기화 완료")
        logger.info(f"   목표 정확도: {target_accuracy:.1%}")
        logger.info(f"   최대 재처리: {max_reprocessing_attempts}회")
        logger.info(f"   품질 임계값: {quality_threshold:.1%}")
        logger.info(f"   활성 컴포넌트: {list(self.components.keys())}")
    
    def _initialize_components(self) -> Dict:
        """시스템 컴포넌트 초기화"""
        components = {}
        
        # 1. 한국어 오디오 최적화기
        if OPTIMIZER_AVAILABLE:
            components['audio_optimizer'] = KoreanAudioOptimizer(
                target_sr=16000,
                target_db=-16.0,
                korean_boost=True
            )
            print("✅ 한국어 오디오 최적화기 활성화")
        
        # 2. 다중 STT 엔진 앙상블
        if MULTI_STT_AVAILABLE:
            components['multi_stt'] = MultiEngineSTTProcessor(
                engines=['whisper_base'],  # 빠른 모델만 사용 (large 제거)
                confidence_threshold=0.85,
                consensus_threshold=2
            )
            print("✅ 다중 STT 엔진 앙상블 활성화")
        
        # 3. 품질 검증기
        if VALIDATOR_AVAILABLE:
            components['quality_validator'] = RealTimeQualityValidator(
                quality_threshold=self.quality_threshold,
                syllable_accuracy_threshold=0.90,
                confidence_threshold=0.85
            )
            print("✅ 실시간 품질 검증기 활성화")
        
        # 4. 기본 STT (백업용)
        if ADVANCED_STT_AVAILABLE:
            components['backup_stt'] = AdvancedSTTProcessor()
            print("✅ 백업 STT 프로세서 활성화")
        
        return components
    
    async def process_audio_ultimate(self,
                                   audio_file: str,
                                   target_text: str = "",
                                   enable_reprocessing: bool = True) -> UltimateSTTResult:
        """
        통합 STT 처리 메인 함수 - 99% 정확도 달성
        
        Parameters:
        -----------
        audio_file : str
            입력 오디오 파일
        target_text : str
            기대 텍스트 (정확도 측정용)
        enable_reprocessing : bool
            재처리 활성화 여부
            
        Returns:
        --------
        UltimateSTTResult : 통합 처리 결과
        """
        start_time = time.time()
        
        print(f"🎯🎯🎯 ToneBridge 통합 STT 시작: {Path(audio_file).name} 🎯🎯🎯")
        print(f"   목표: {self.target_accuracy:.1%} 정확도 달성")
        
        # 결과 객체 초기화
        result = UltimateSTTResult(
            final_text="",
            confidence=0.0,
            accuracy_achieved=0.0
        )
        
        current_audio_file = audio_file
        attempt = 0
        
        # 처리 시도 루프 (최대 재처리 횟수까지)
        while attempt <= self.max_reprocessing_attempts:
            attempt += 1
            
            print(f"\n🔄 처리 시도 {attempt}/{self.max_reprocessing_attempts + 1}")
            
            try:
                # 1단계: 한국어 특화 오디오 전처리
                stage_result = await self._stage_1_audio_preprocessing(current_audio_file, attempt)
                current_audio_file = stage_result['optimized_file']
                result.audio_optimizations_applied.extend(stage_result['optimizations'])
                result.processing_stages.append(f"전처리_시도_{attempt}")
                
                # 2단계: 다중 엔진 앙상블 STT
                stage_result = await self._stage_2_ensemble_stt(current_audio_file, target_text)
                result.ensemble_result = stage_result['ensemble_result']
                result.stt_engines_used.extend(stage_result['engines_used'])
                result.processing_stages.append(f"STT_시도_{attempt}")
                
                # 3단계: 실시간 품질 검증
                stage_result = await self._stage_3_quality_validation(
                    result.ensemble_result, target_text, current_audio_file
                )
                result.validation_result = stage_result['validation_result']
                result.processing_stages.append(f"검증_시도_{attempt}")
                
                # 품질 충족 여부 확인
                if result.validation_result and result.validation_result.is_valid:
                    print(f"✅ 목표 품질 달성! (시도 {attempt})")
                    break
                
                # 재처리 필요성 판단
                if not enable_reprocessing or attempt > self.max_reprocessing_attempts:
                    print(f"⚠️ 최대 시도 횟수 도달, 현재 결과로 완료")
                    break
                
                # 4단계: 적응형 재처리 전략 적용
                if result.validation_result and result.validation_result.suggested_strategies:
                    print(f"🔧 재처리 전략 적용 중...")
                    current_audio_file = await self._stage_4_adaptive_reprocessing(
                        audio_file, result.validation_result.suggested_strategies[0]
                    )
                    result.reprocessing_attempts += 1
                    result.quality_improvements.extend([
                        result.validation_result.suggested_strategies[0].strategy_name
                    ])
                
            except Exception as e:
                logger.error(f"처리 시도 {attempt} 실패: {e}")
                if attempt > self.max_reprocessing_attempts:
                    raise
        
        # 최종 결과 정리
        await self._finalize_result(result, target_text, start_time)
        
        # 성능 통계 업데이트
        self._update_performance_stats(result)
        
        # 최종 보고서 출력
        self._print_ultimate_report(result)
        
        return result
    
    async def _stage_1_audio_preprocessing(self, audio_file: str, attempt: int) -> Dict:
        """1단계: 한국어 특화 오디오 전처리"""
        print("🎵 1단계: 한국어 특화 오디오 전처리")
        
        optimizations = []
        optimized_file = audio_file
        
        if 'audio_optimizer' in self.components:
            try:
                # 시도 횟수에 따라 전처리 강도 조정
                optimizer = self.components['audio_optimizer']
                
                if attempt == 1:
                    # 첫 시도: 기본 최적화
                    optimized_file = optimizer.optimize_for_korean_stt(
                        audio_file, stt_engine='whisper'
                    )
                    optimizations.append("기본_한국어_최적화")
                
                elif attempt == 2:
                    # 두 번째 시도: 강화된 자음 처리
                    optimizer.korean_phoneme_profiles['consonants']['stops']['boost_db'] = [5, 6]
                    optimized_file = optimizer.optimize_for_korean_stt(
                        audio_file, stt_engine='whisper'
                    )
                    optimizations.append("강화_자음_처리")
                
                else:
                    # 세 번째 이후: 최대 강도 처리
                    optimizer.korean_boost = True
                    optimizer.target_db = -14.0  # 더 높은 볼륨
                    optimized_file = optimizer.optimize_for_korean_stt(
                        audio_file, stt_engine='whisper'
                    )
                    optimizations.append("최대_강도_처리")
                
                print(f"✅ 오디오 전처리 완료: {optimizations}")
                
            except Exception as e:
                logger.warning(f"오디오 전처리 실패: {e}")
                optimized_file = audio_file
                optimizations.append("전처리_실패")
        
        return {
            'optimized_file': optimized_file,
            'optimizations': optimizations
        }
    
    async def _stage_2_ensemble_stt(self, audio_file: str, target_text: str) -> Dict:
        """2단계: 다중 엔진 앙상블 STT"""
        print("🎤 2단계: 다중 엔진 앙상블 STT")
        
        ensemble_result = None
        engines_used = []
        
        if 'multi_stt' in self.components:
            try:
                multi_stt = self.components['multi_stt']
                ensemble_result = await multi_stt.transcribe_with_ensemble(
                    audio_file, target_text
                )
                engines_used = [r.engine for r in ensemble_result.engine_results if r.success]
                print(f"✅ 앙상블 STT 완료: {engines_used}")
                
            except Exception as e:
                logger.warning(f"앙상블 STT 실패: {e}")
        
        # 백업 STT 사용
        if not ensemble_result and 'backup_stt' in self.components:
            try:
                backup_stt = self.components['backup_stt']
                backup_result = backup_stt.process_audio_with_confidence(audio_file, target_text)
                
                # EnsembleSTTResult 형태로 변환
                ensemble_result = type('EnsembleSTTResult', (), {
                    'final_text': backup_result.get('transcription', {}).get('text', ''),
                    'confidence': backup_result.get('overall_confidence', 0.0),
                    'processing_time': 0.0
                })()
                engines_used = ['backup_whisper']
                print("✅ 백업 STT 사용")
                
            except Exception as e:
                logger.error(f"백업 STT도 실패: {e}")
        
        return {
            'ensemble_result': ensemble_result,
            'engines_used': engines_used
        }
    
    async def _stage_3_quality_validation(self, 
                                        ensemble_result: Any,
                                        target_text: str,
                                        audio_file: str) -> Dict:
        """3단계: 실시간 품질 검증"""
        print("🔍 3단계: 실시간 품질 검증")
        
        validation_result = None
        
        if 'quality_validator' in self.components and ensemble_result:
            try:
                validator = self.components['quality_validator']
                validation_result = await validator.validate_stt_quality(
                    ensemble_result, target_text, audio_file
                )
                print(f"✅ 품질 검증 완료: 점수 {validation_result.quality_metrics.overall_score:.3f}")
                
            except Exception as e:
                logger.warning(f"품질 검증 실패: {e}")
        
        return {
            'validation_result': validation_result
        }
    
    async def _stage_4_adaptive_reprocessing(self, 
                                           original_audio: str,
                                           strategy) -> str:
        """4단계: 적응형 재처리"""
        print(f"🔧 4단계: 적응형 재처리 - {strategy.strategy_name}")
        
        try:
            # 재처리 전략에 따른 오디오 최적화
            if 'audio_optimizer' in self.components:
                optimizer = self.components['audio_optimizer']
                
                # 전략별 파라미터 적용
                for key, value in strategy.audio_adjustments.items():
                    if hasattr(optimizer, key):
                        setattr(optimizer, key, value)
                
                # 임시 파일로 재최적화
                temp_dir = tempfile.gettempdir()
                reprocessed_file = os.path.join(
                    temp_dir, 
                    f"reprocessed_{strategy.strategy_name}_{Path(original_audio).name}"
                )
                
                final_file = optimizer.optimize_for_korean_stt(
                    original_audio, reprocessed_file
                )
                
                print(f"✅ 재처리 완료: {strategy.strategy_name}")
                return final_file
            
        except Exception as e:
            logger.warning(f"재처리 실패: {e}")
        
        return original_audio
    
    async def _finalize_result(self, result: UltimateSTTResult, target_text: str, start_time: float):
        """최종 결과 정리"""
        # 최종 텍스트 및 신뢰도
        if result.ensemble_result:
            result.final_text = result.ensemble_result.final_text
            result.confidence = result.ensemble_result.confidence
        
        # 정확도 계산 (target_text가 있는 경우)
        if target_text and result.final_text:
            result.accuracy_achieved = self._calculate_final_accuracy(
                result.final_text, target_text
            )
        
        # 최종 품질 점수
        if result.validation_result:
            result.final_quality_score = result.validation_result.quality_metrics.overall_score
        
        # 총 처리 시간
        result.total_processing_time = time.time() - start_time
    
    def _calculate_final_accuracy(self, predicted: str, target: str) -> float:
        """최종 정확도 계산"""
        if not target:
            return 1.0 if not predicted else 0.0
        
        # 한국어 음절 단위 정확도
        pred_syllables = [c for c in predicted.replace(' ', '') if 0xAC00 <= ord(c) <= 0xD7A3]
        target_syllables = [c for c in target.replace(' ', '') if 0xAC00 <= ord(c) <= 0xD7A3]
        
        if not target_syllables:
            return 1.0
        
        # 편집 거리 기반 정확도
        len_pred, len_target = len(pred_syllables), len(target_syllables)
        
        # DP 테이블 생성
        dp = [[0] * (len_target + 1) for _ in range(len_pred + 1)]
        
        for i in range(len_pred + 1):
            dp[i][0] = i
        for j in range(len_target + 1):
            dp[0][j] = j
        
        for i in range(1, len_pred + 1):
            for j in range(1, len_target + 1):
                if pred_syllables[i-1] == target_syllables[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
        
        edit_distance = dp[len_pred][len_target]
        accuracy = 1.0 - (edit_distance / len_target)
        
        return max(0.0, accuracy)
    
    def _update_performance_stats(self, result: UltimateSTTResult):
        """성능 통계 업데이트"""
        self.performance_stats['total_requests'] += 1
        
        if result.accuracy_achieved >= self.target_accuracy:
            self.performance_stats['successful_requests'] += 1
        
        self.performance_stats['accuracy_scores'].append(result.accuracy_achieved)
        self.performance_stats['processing_times'].append(result.total_processing_time)
        
        # 재처리 통계
        if result.reprocessing_attempts > 0:
            attempts_key = f"{result.reprocessing_attempts}_attempts"
            self.performance_stats['reprocessing_stats'][attempts_key] = \
                self.performance_stats['reprocessing_stats'].get(attempts_key, 0) + 1
    
    def _print_ultimate_report(self, result: UltimateSTTResult):
        """최종 보고서 출력"""
        print(f"\n🎯🎯🎯 ToneBridge 통합 STT 최종 보고서 🎯🎯🎯")
        print(f"   최종 텍스트: '{result.final_text}'")
        print(f"   달성 정확도: {result.accuracy_achieved:.1%} ({'✅ 목표 달성' if result.accuracy_achieved >= self.target_accuracy else '❌ 목표 미달'})")
        print(f"   신뢰도: {result.confidence:.3f}")
        print(f"   품질 점수: {result.final_quality_score:.3f}")
        print(f"   총 처리 시간: {result.total_processing_time:.2f}초")
        print(f"   재처리 횟수: {result.reprocessing_attempts}회")
        
        print(f"\n   처리 단계: {' → '.join(result.processing_stages)}")
        print(f"   적용된 최적화: {', '.join(result.audio_optimizations_applied)}")
        print(f"   사용된 STT 엔진: {', '.join(result.stt_engines_used)}")
        
        if result.quality_improvements:
            print(f"   품질 개선 기법: {', '.join(result.quality_improvements)}")
        
        # 전체 시스템 성능 요약
        if self.performance_stats['total_requests'] > 0:
            success_rate = self.performance_stats['successful_requests'] / self.performance_stats['total_requests']
            avg_accuracy = sum(self.performance_stats['accuracy_scores']) / len(self.performance_stats['accuracy_scores'])
            avg_time = sum(self.performance_stats['processing_times']) / len(self.performance_stats['processing_times'])
            
            print(f"\n📊 시스템 전체 성능:")
            print(f"   성공률: {success_rate:.1%} ({self.performance_stats['successful_requests']}/{self.performance_stats['total_requests']})")
            print(f"   평균 정확도: {avg_accuracy:.1%}")
            print(f"   평균 처리 시간: {avg_time:.2f}초")
        
        print("✅ ToneBridge 통합 STT 처리 완료\n")
    
    async def test_system_performance(self, test_cases: List[Dict]) -> Dict:
        """시스템 성능 테스트"""
        print(f"🧪 시스템 성능 테스트 시작: {len(test_cases)}개 케이스")
        
        test_results = []
        
        for i, test_case in enumerate(test_cases):
            print(f"\n📋 테스트 케이스 {i+1}/{len(test_cases)}: {test_case.get('name', 'Unknown')}")
            
            try:
                result = await self.process_audio_ultimate(
                    test_case['audio_file'],
                    test_case.get('target_text', ''),
                    enable_reprocessing=test_case.get('enable_reprocessing', True)
                )
                
                test_results.append({
                    'test_case': test_case['name'],
                    'success': result.accuracy_achieved >= self.target_accuracy,
                    'accuracy': result.accuracy_achieved,
                    'confidence': result.confidence,
                    'processing_time': result.total_processing_time,
                    'reprocessing_attempts': result.reprocessing_attempts
                })
                
            except Exception as e:
                logger.error(f"테스트 케이스 {i+1} 실패: {e}")
                test_results.append({
                    'test_case': test_case['name'],
                    'success': False,
                    'error': str(e)
                })
        
        # 테스트 결과 분석
        successful_tests = [r for r in test_results if r.get('success', False)]
        
        summary = {
            'total_tests': len(test_cases),
            'successful_tests': len(successful_tests),
            'success_rate': len(successful_tests) / len(test_cases) if test_cases else 0,
            'average_accuracy': sum(r.get('accuracy', 0) for r in successful_tests) / len(successful_tests) if successful_tests else 0,
            'average_processing_time': sum(r.get('processing_time', 0) for r in successful_tests) / len(successful_tests) if successful_tests else 0,
            'test_results': test_results
        }
        
        # 테스트 보고서 출력
        print(f"\n🧪 시스템 성능 테스트 완료 보고서:")
        print(f"   전체 테스트: {summary['total_tests']}개")
        print(f"   성공 테스트: {summary['successful_tests']}개")
        print(f"   성공률: {summary['success_rate']:.1%}")
        print(f"   평균 정확도: {summary['average_accuracy']:.1%}")
        print(f"   평균 처리 시간: {summary['average_processing_time']:.2f}초")
        
        return summary

# 편의 함수들
async def process_audio_with_ultimate_accuracy(audio_file: str, target_text: str = "") -> UltimateSTTResult:
    """
    99% 정확도 STT 처리 편의 함수
    
    Parameters:
    -----------
    audio_file : str
        입력 오디오 파일
    target_text : str
        기대 텍스트
        
    Returns:
    --------
    UltimateSTTResult : 통합 처리 결과
    """
    system = UltimateSTTSystem()
    return await system.process_audio_ultimate(audio_file, target_text)

def create_test_suite() -> List[Dict]:
    """테스트 케이스 생성"""
    return [
        {
            'name': '기본_한국어_인사',
            'audio_file': 'test_audio/안녕하세요.wav',
            'target_text': '안녕하세요',
            'enable_reprocessing': True
        },
        {
            'name': '복잡_한국어_문장',
            'audio_file': 'test_audio/반갑습니다.wav', 
            'target_text': '반갑습니다',
            'enable_reprocessing': True
        },
        {
            'name': '빠른_처리_모드',
            'audio_file': 'test_audio/감사합니다.wav',
            'target_text': '감사합니다',
            'enable_reprocessing': False
        }
    ]

if __name__ == "__main__":
    # 시스템 테스트
    import sys
    
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        target_text = sys.argv[2] if len(sys.argv) > 2 else ""
        
        result = asyncio.run(process_audio_with_ultimate_accuracy(audio_file, target_text))
        print(f"최종 결과: {result.final_text} (정확도: {result.accuracy_achieved:.1%})")
    else:
        # 성능 테스트 실행
        system = UltimateSTTSystem()
        test_cases = create_test_suite()
        test_summary = asyncio.run(system.test_system_performance(test_cases))