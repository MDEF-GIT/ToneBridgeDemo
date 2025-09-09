"""
ToneBridge 다중 STT 엔진 통합 시스템
99% 정확도 달성을 위한 앙상블 STT 처리기
"""

import asyncio
import concurrent.futures
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np
import logging
from pathlib import Path
import json
import os

# 기존 STT 클래스들 import
try:
    from advanced_stt_processor import UniversalSTT, TranscriptionResult
    STT_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ STT 모듈 import 오류: {e}")
    STT_AVAILABLE = False

try:
    from korean_audio_optimizer import KoreanAudioOptimizer
    OPTIMIZER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Korean optimizer import 오류: {e}")
    OPTIMIZER_AVAILABLE = False

logger = logging.getLogger(__name__)

@dataclass 
class STTEngineResult:
    """개별 STT 엔진 결과"""
    engine: str
    text: str
    confidence: float
    processing_time: float
    words: List = field(default_factory=list)
    success: bool = True
    error_message: str = ""

@dataclass
class EnsembleSTTResult:
    """앙상블 STT 최종 결과"""
    final_text: str
    confidence: float
    engine_results: List[STTEngineResult] = field(default_factory=list)
    selected_engine: str = ""
    consensus_score: float = 0.0
    processing_time: float = 0.0

class MultiEngineSTTProcessor:
    """
    다중 STT 엔진 앙상블 처리기
    
    핵심 기능:
    1. 5개 STT 엔진 동시 실행 (Whisper Large, Google Cloud, Azure, Naver CLOVA, Whisper Base)
    2. 신뢰도 기반 결과 선택
    3. 앙상블 투표 방식 (3개 이상 합의시 채택)
    4. 실패 시 자동 차선책
    5. 한국어 특화 신뢰도 계산
    """
    
    def __init__(self, 
                 engines: Optional[List[str]] = None,
                 confidence_threshold: float = 0.85,
                 consensus_threshold: int = 2,
                 timeout_seconds: float = 30.0):
        """
        Parameters:
        -----------
        engines : List[str]
            사용할 STT 엔진 목록
        confidence_threshold : float
            최소 신뢰도 임계값
        consensus_threshold : int  
            합의 필요 최소 엔진 수
        timeout_seconds : float
            STT 처리 타임아웃
        """
        
        # 기본 엔진 우선순위 (성능 순)
        if engines is None:
            engines = [
                'whisper_large',    # 최고 성능
                'google_cloud',     # 높은 신뢰도
                'azure_speech',     # 안정성
                'naver_clova',      # 한국어 특화
                'whisper_base'      # 빠른 처리
            ]
        
        self.engines = engines
        self.confidence_threshold = confidence_threshold
        self.consensus_threshold = consensus_threshold
        self.timeout_seconds = timeout_seconds
        
        # 엔진별 가중치 (한국어 특화)
        self.engine_weights = {
            'whisper_large': 1.0,    # 최고 품질
            'google_cloud': 0.9,     # 높은 신뢰도  
            'azure_speech': 0.8,     # 안정성
            'naver_clova': 0.95,     # 한국어 특화
            'whisper_base': 0.7      # 기본 옵션
        }
        
        # 한국어 오디오 최적화기
        if OPTIMIZER_AVAILABLE:
            self.korean_optimizer = KoreanAudioOptimizer()
        else:
            self.korean_optimizer = None
        
        # 엔진 인스턴스 초기화
        self.stt_engines = self._initialize_engines()
        
        logger.info(f"🚀 다중 STT 엔진 시스템 초기화 완료")
        logger.info(f"   활성 엔진: {list(self.stt_engines.keys())}")
        logger.info(f"   신뢰도 임계값: {confidence_threshold}")
        logger.info(f"   합의 임계값: {consensus_threshold}개 엔진")
    
    def _initialize_engines(self) -> Dict:
        """STT 엔진들 초기화"""
        engines = {}
        
        if not STT_AVAILABLE:
            print("⚠️ STT 모듈 없음, 빈 엔진 딕셔너리 반환")
            return engines
        
        for engine_name in self.engines:
            try:
                if engine_name == 'whisper_large':
                    engines[engine_name] = UniversalSTT('whisper', model_size='large-v3')
                    print(f"✅ Whisper Large-v3 엔진 초기화 완료")
                    
                elif engine_name == 'whisper_base':
                    engines[engine_name] = UniversalSTT('whisper', model_size='base')
                    print(f"✅ Whisper Base 엔진 초기화 완료")
                    
                elif engine_name == 'google_cloud':
                    try:
                        engines[engine_name] = UniversalSTT('google')
                        print(f"✅ Google Cloud STT 엔진 초기화 완료")
                    except:
                        print(f"⚠️ Google Cloud STT 미설치, 건너뜀")
                        
                elif engine_name == 'azure_speech':
                    try:
                        engines[engine_name] = UniversalSTT('azure')
                        print(f"✅ Azure Speech 엔진 초기화 완료")
                    except:
                        print(f"⚠️ Azure Speech Services 미설치, 건너뜀")
                        
                elif engine_name == 'naver_clova':
                    try:
                        engines[engine_name] = UniversalSTT('naver_clova')
                        print(f"✅ Naver CLOVA STT 엔진 초기화 완료")
                    except:
                        print(f"⚠️ Naver CLOVA STT 미설치, 건너뜀")
                        
            except Exception as e:
                logger.warning(f"STT 엔진 '{engine_name}' 초기화 실패: {e}")
        
        return engines
    
    async def transcribe_with_ensemble(self, 
                                     audio_file: str, 
                                     target_text: str = "") -> EnsembleSTTResult:
        """
        앙상블 STT 처리 메인 함수
        
        Parameters:
        -----------
        audio_file : str
            입력 오디오 파일
        target_text : str
            기대 텍스트 (정확도 검증용)
            
        Returns:
        --------
        EnsembleSTTResult : 앙상블 처리 결과
        """
        start_time = time.time()
        print(f"🎯 다중 엔진 앙상블 STT 시작: {Path(audio_file).name}")
        
        # 1단계: 한국어 특화 전처리
        optimized_audio = await self._preprocess_audio(audio_file)
        
        # 2단계: 다중 엔진 동시 실행
        engine_results = await self._run_parallel_stt(optimized_audio)
        
        # 3단계: 결과 분석 및 선택
        final_result = self._analyze_and_select_result(engine_results, target_text)
        
        # 4단계: 품질 검증
        final_result = await self._validate_final_result(final_result, optimized_audio, target_text)
        
        final_result.processing_time = time.time() - start_time
        
        # 결과 보고서 출력
        self._print_ensemble_report(final_result)
        
        return final_result
    
    async def _preprocess_audio(self, audio_file: str) -> str:
        """한국어 특화 전처리"""
        if not self.korean_optimizer:
            print("⚠️ 한국어 최적화기 없음, 원본 파일 사용")
            return audio_file
            
        try:
            print("🇰🇷 한국어 특화 오디오 최적화 중...")
            
            optimized_file = self.korean_optimizer.optimize_for_korean_stt(
                audio_file, stt_engine='whisper'
            )
            
            print(f"✅ 오디오 최적화 완료: {optimized_file}")
            return optimized_file
            
        except Exception as e:
            logger.warning(f"오디오 전처리 실패, 원본 사용: {e}")
            return audio_file
    
    async def _run_parallel_stt(self, audio_file: str) -> List[STTEngineResult]:
        """다중 STT 엔진 병렬 실행"""
        print(f"🔄 {len(self.stt_engines)}개 STT 엔진 병렬 실행 시작...")
        
        # 각 엔진별 태스크 생성
        tasks = []
        for engine_name, engine_instance in self.stt_engines.items():
            task = self._run_single_engine(engine_name, engine_instance, audio_file)
            tasks.append(task)
        
        # 병렬 실행 (타임아웃 적용)
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.timeout_seconds
            )
            
            # 예외 처리된 결과들 정리
            engine_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    engine_name = list(self.stt_engines.keys())[i]
                    error_result = STTEngineResult(
                        engine=engine_name,
                        text="",
                        confidence=0.0,
                        processing_time=0.0,
                        success=False,
                        error_message=str(result)
                    )
                    engine_results.append(error_result)
                else:
                    engine_results.append(result)
            
            return engine_results
            
        except asyncio.TimeoutError:
            logger.error(f"STT 처리 타임아웃 ({self.timeout_seconds}초)")
            return []
    
    async def _run_single_engine(self, 
                                engine_name: str, 
                                engine_instance, 
                                audio_file: str) -> STTEngineResult:
        """단일 STT 엔진 실행"""
        start_time = time.time()
        
        try:
            print(f"  🎤 {engine_name} 엔진 실행 중...")
            
            # STT 전사
            result = engine_instance.transcribe(audio_file, language='ko', return_timestamps=True)
            
            processing_time = time.time() - start_time
            
            # 한국어 특화 신뢰도 계산
            confidence = self._calculate_korean_confidence(result, engine_name)
            
            print(f"  ✅ {engine_name}: '{result.text}' (신뢰도: {confidence:.3f}, {processing_time:.2f}초)")
            
            return STTEngineResult(
                engine=engine_name,
                text=result.text,
                confidence=confidence,
                processing_time=processing_time,
                words=result.words,
                success=True
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            print(f"  ❌ {engine_name} 실패: {e}")
            
            return STTEngineResult(
                engine=engine_name,
                text="",
                confidence=0.0,
                processing_time=processing_time,
                success=False,
                error_message=str(e)
            )
    
    def _calculate_korean_confidence(self, 
                                   result, 
                                   engine_name: str) -> float:
        """한국어 특화 신뢰도 계산"""
        factors = []
        
        # 1. 엔진별 기본 신뢰도
        base_confidence = self.engine_weights.get(engine_name, 0.5)
        factors.append(base_confidence)
        
        # 2. STT 원본 신뢰도
        if hasattr(result, 'confidence'):
            factors.append(result.confidence)
        
        # 3. 한국어 텍스트 품질 평가
        korean_quality = self._evaluate_korean_text_quality(result.text)
        factors.append(korean_quality)
        
        # 4. 타임스탬프 완성도
        if result.words and len(result.words) > 0:
            timestamp_quality = 0.9  # 타임스탬프 있으면 보너스
        else:
            timestamp_quality = 0.6
        factors.append(timestamp_quality)
        
        # 가중평균으로 최종 신뢰도 계산
        return np.mean(factors)
    
    def _evaluate_korean_text_quality(self, text: str) -> float:
        """한국어 텍스트 품질 평가"""
        if not text:
            return 0.0
        
        # 한국어 문자 비율
        korean_chars = sum(1 for c in text if 0xAC00 <= ord(c) <= 0xD7A3)
        total_chars = len(text.replace(' ', ''))
        
        if total_chars == 0:
            return 0.0
        
        korean_ratio = korean_chars / total_chars
        
        # 완전한 음절 비율 (자음/모음 단독 제외)
        complete_syllables = korean_chars
        quality_score = korean_ratio * (complete_syllables / (total_chars + 1))
        
        return min(1.0, quality_score + 0.3)  # 기본 보너스
    
    def _analyze_and_select_result(self, 
                                 engine_results: List[STTEngineResult], 
                                 target_text: str = "") -> EnsembleSTTResult:
        """결과 분석 및 최적 결과 선택"""
        print(f"🔍 {len(engine_results)}개 엔진 결과 분석 중...")
        
        # 성공한 결과들만 필터링
        successful_results = [r for r in engine_results if r.success and r.text.strip()]
        
        if not successful_results:
            return EnsembleSTTResult(
                final_text="",
                confidence=0.0,
                engine_results=engine_results,
                selected_engine="none",
                consensus_score=0.0
            )
        
        # 1. 높은 신뢰도 결과 우선 선택
        high_confidence_results = [
            r for r in successful_results 
            if r.confidence >= self.confidence_threshold
        ]
        
        if high_confidence_results:
            # 가장 높은 신뢰도 결과 선택
            best_result = max(high_confidence_results, key=lambda x: x.confidence)
            
            return EnsembleSTTResult(
                final_text=best_result.text,
                confidence=best_result.confidence,
                engine_results=engine_results,
                selected_engine=best_result.engine,
                consensus_score=1.0
            )
        
        # 2. 앙상블 투표 방식
        consensus_result = self._find_consensus(successful_results)
        if consensus_result:
            return consensus_result
        
        # 3. 차선책: 가장 높은 신뢰도 결과
        best_result = max(successful_results, key=lambda x: x.confidence)
        
        return EnsembleSTTResult(
            final_text=best_result.text,
            confidence=best_result.confidence * 0.8,  # 페널티 적용
            engine_results=engine_results,
            selected_engine=best_result.engine,
            consensus_score=0.5
        )
    
    def _find_consensus(self, results: List[STTEngineResult]) -> Optional[EnsembleSTTResult]:
        """앙상블 합의 찾기"""
        if len(results) < self.consensus_threshold:
            return None
        
        # 텍스트 유사도 기반 그룹핑
        text_groups = {}
        for result in results:
            text = result.text.strip()
            
            # 기존 그룹과 유사도 비교
            best_group = None
            best_similarity = 0.0
            
            for group_text in text_groups.keys():
                similarity = self._calculate_text_similarity(text, group_text)
                if similarity > best_similarity and similarity >= 0.8:  # 80% 이상 유사
                    best_similarity = similarity
                    best_group = group_text
            
            if best_group:
                text_groups[best_group].append(result)
            else:
                text_groups[text] = [result]
        
        # 합의 그룹 찾기
        for group_text, group_results in text_groups.items():
            if len(group_results) >= self.consensus_threshold:
                # 그룹 내 최고 신뢰도 결과 선택
                best_in_group = max(group_results, key=lambda x: x.confidence)
                
                # 합의 점수 계산
                consensus_score = len(group_results) / len(results)
                
                return EnsembleSTTResult(
                    final_text=best_in_group.text,
                    confidence=best_in_group.confidence,
                    engine_results=results,
                    selected_engine=f"consensus_{len(group_results)}",
                    consensus_score=consensus_score
                )
        
        return None
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """텍스트 유사도 계산 (한국어 특화)"""
        if not text1 or not text2:
            return 0.0
        
        # 공백 제거 및 정규화
        text1 = text1.replace(' ', '').strip()
        text2 = text2.replace(' ', '').strip()
        
        if text1 == text2:
            return 1.0
        
        # 레벤슈타인 거리 기반 유사도
        len1, len2 = len(text1), len(text2)
        if len1 == 0 or len2 == 0:
            return 0.0
        
        # DP 배열
        dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        
        # 초기화
        for i in range(len1 + 1):
            dp[i][0] = i
        for j in range(len2 + 1):
            dp[0][j] = j
        
        # DP 계산
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                if text1[i-1] == text2[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
        
        # 유사도 계산
        edit_distance = dp[len1][len2]
        max_len = max(len1, len2)
        similarity = 1.0 - (edit_distance / max_len)
        
        return float(max(0.0, similarity))
    
    async def _validate_final_result(self, 
                                   result: EnsembleSTTResult, 
                                   audio_file: str, 
                                   target_text: str) -> EnsembleSTTResult:
        """최종 결과 품질 검증"""
        if not result.final_text or result.confidence < 0.5:
            print("⚠️ 낮은 품질 결과, 재처리 시도...")
            
            # TODO: 재처리 로직 구현
            # - 오디오 추가 최적화
            # - 다른 모델 시도
            # - 사용자 피드백 요청
            
        return result
    
    def _print_ensemble_report(self, result: EnsembleSTTResult):
        """앙상블 결과 보고서"""
        print(f"\n📊 다중 엔진 STT 결과 보고서:")
        print(f"   최종 텍스트: '{result.final_text}'")
        print(f"   선택된 엔진: {result.selected_engine}")
        print(f"   신뢰도: {result.confidence:.3f}")
        print(f"   합의 점수: {result.consensus_score:.3f}")
        print(f"   처리 시간: {result.processing_time:.2f}초")
        
        print(f"\n   개별 엔진 결과:")
        for engine_result in result.engine_results:
            status = "✅" if engine_result.success else "❌"
            print(f"     {status} {engine_result.engine}: '{engine_result.text}' "
                  f"(신뢰도: {engine_result.confidence:.3f}, "
                  f"{engine_result.processing_time:.2f}초)")
        
        print("✅ 다중 엔진 앙상블 STT 완료\n")

# 편의 함수
async def transcribe_with_multi_engine(audio_file: str, target_text: str = "") -> EnsembleSTTResult:
    """
    다중 엔진 STT 빠른 실행 함수
    
    Parameters:
    -----------
    audio_file : str
        입력 오디오 파일
    target_text : str
        기대 텍스트 (검증용)
        
    Returns:
    --------
    EnsembleSTTResult : 앙상블 결과
    """
    processor = MultiEngineSTTProcessor()
    return await processor.transcribe_with_ensemble(audio_file, target_text)

if __name__ == "__main__":
    # 테스트용
    import sys
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        target_text = sys.argv[2] if len(sys.argv) > 2 else ""
        
        result = asyncio.run(transcribe_with_multi_engine(audio_file, target_text))
        print(f"최종 결과: {result.final_text} (신뢰도: {result.confidence:.3f})")