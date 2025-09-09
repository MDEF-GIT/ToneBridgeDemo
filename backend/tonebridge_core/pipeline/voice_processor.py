"""
통합 음성 처리 파이프라인
모든 차트에서 동일한 처리 흐름과 품질 보장
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Union

# 기존 모듈 임포트 (하위 호환성)
sys.path.append(str(Path(__file__).parent.parent.parent))

from ..models import ProcessingResult, SyllableSegment
from ..stt.universal_stt import UnifiedSTTEngine
from ..segmentation.korean_segmenter import KoreanSyllableSegmenter
from ..textgrid.generator import UnifiedTextGridGenerator
from ..analysis.pitch_analyzer import UnifiedPitchAnalyzer

class UnifiedVoiceProcessor:
    """
    메인 음성 처리 파이프라인 - 모든 차트에서 동일한 처리
    기존 기능을 유지하면서 통합된 처리 제공
    """
    
    def __init__(self, shared_stt_processor=None):
        # 🚀 성능 최적화: 전역 STT 인스턴스 재사용
        if shared_stt_processor:
            self.stt_engine = UnifiedSTTEngine(shared_processor=shared_stt_processor)
        else:
            self.stt_engine = UnifiedSTTEngine()
            
        # 🚀 성능 최적화: 분절기에도 동일한 STT 인스턴스 전달
        if shared_stt_processor:
            self.segmenter = KoreanSyllableSegmenter(shared_stt_processor=shared_stt_processor)
        else:
            self.segmenter = KoreanSyllableSegmenter()
        self.textgrid_generator = UnifiedTextGridGenerator()
        self.pitch_analyzer = UnifiedPitchAnalyzer()
        
        print("✅ 통합 음성 프로세서 초기화 완료")
    
    def process_reference_file(self, file_id: str, audio_file: str = None) -> ProcessingResult:
        """
        참조 파일 처리 - 기존 API와 호환
        """
        print(f"🎯 참조 파일 처리: {file_id}")
        
        try:
            # 오디오 파일 경로 결정
            if not audio_file:
                audio_file = f"static/reference_files/{file_id}.wav"
            
            if not Path(audio_file).exists():
                return ProcessingResult(
                    success=False,
                    segments=[],
                    error=f"참조 파일을 찾을 수 없습니다: {file_id}"
                )
            
            # 기존 TextGrid가 있으면 사용, 없으면 생성
            textgrid_path = f"static/reference_files/{file_id}.TextGrid"
            
            if Path(textgrid_path).exists():
                # 기존 TextGrid 파싱
                segments = self._parse_existing_textgrid(textgrid_path)
                print(f"📋 기존 TextGrid 사용: {len(segments)}개 음절")
            else:
                # 새로 생성
                segments = self.segmenter.segment(audio_file)
                textgrid_content = self.textgrid_generator.from_syllables(segments)
                
                # 저장
                with open(textgrid_path, 'w', encoding='utf-16') as f:
                    f.write(textgrid_content)
                print(f"📋 새 TextGrid 생성: {len(segments)}개 음절")
            
            # 피치 분석
            pitch_analysis = self.pitch_analyzer.analyze(audio_file, segments)
            
            # 지속시간 계산
            try:
                import parselmouth as pm
                sound = pm.Sound(audio_file)
                duration = sound.get_total_duration()
            except:
                duration = max(seg.end for seg in segments) if segments else 1.0
            
            return ProcessingResult(
                success=True,
                segments=segments,
                textgrid_path=textgrid_path,
                pitch_analysis=pitch_analysis,
                duration=duration,
                file_type='reference'
            )
            
        except Exception as e:
            print(f"❌ 참조 파일 처리 실패: {e}")
            return ProcessingResult(
                success=False,
                segments=[],
                error=str(e)
            )
    
    def process_uploaded_file(self, audio_file: str, text_hint: str = "") -> ProcessingResult:
        """
        업로드 파일 처리 - 기존 API와 호환
        """
        print(f"🎯 업로드 파일 처리: {Path(audio_file).name}")
        
        try:
            # 텍스트 힌트 처리
            if not text_hint:
                # 파일명에서 추출 시도
                filename = Path(audio_file).stem
                parts = filename.split('_')
                if len(parts) >= 4:
                    text_hint = parts[3]  # 반가워요 등
                else:
                    text_hint = "반가워요"  # 기본값
            
            print(f"📝 텍스트 힌트: {text_hint}")
            
            # 통합 분절 처리
            segments = self.segmenter.segment(audio_file, text_hint)
            
            # TextGrid 생성
            textgrid_path = str(Path(audio_file).with_suffix('.TextGrid'))
            textgrid_content = self.textgrid_generator.from_syllables(segments)
            
            # TextGrid 저장
            with open(textgrid_path, 'w', encoding='utf-16') as f:
                f.write(textgrid_content)
            
            # 피치 분석
            pitch_analysis = self.pitch_analyzer.analyze(audio_file, segments)
            
            # 지속시간 계산
            try:
                import parselmouth as pm
                sound = pm.Sound(audio_file)
                duration = sound.get_total_duration()
            except:
                duration = max(seg.end for seg in segments) if segments else 1.0
            
            print(f"✅ 업로드 파일 처리 완료: {len(segments)}개 음절")
            
            return ProcessingResult(
                success=True,
                segments=segments,
                textgrid_content=textgrid_content,
                textgrid_path=textgrid_path,
                pitch_analysis=pitch_analysis,
                transcription=text_hint,
                duration=duration,
                file_type='uploaded'
            )
            
        except Exception as e:
            print(f"❌ 업로드 파일 처리 실패: {e}")
            return ProcessingResult(
                success=False,
                segments=[],
                error=str(e)
            )
    
    def process_realtime_audio(self, audio_data: bytes, text_hint: str = "") -> ProcessingResult:
        """
        실시간 오디오 처리 - 기존 API와 호환
        """
        print("🎯 실시간 오디오 처리")
        
        try:
            # 임시 파일 생성
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_file.write(audio_data)
                temp_path = tmp_file.name
            
            # 업로드 파일과 동일한 처리
            result = self.process_uploaded_file(temp_path, text_hint)
            result.file_type = 'realtime'
            
            # 임시 파일 정리
            try:
                os.unlink(temp_path)
            except:
                pass
            
            return result
            
        except Exception as e:
            print(f"❌ 실시간 오디오 처리 실패: {e}")
            return ProcessingResult(
                success=False,
                segments=[],
                error=str(e)
            )
    
    def _parse_existing_textgrid(self, textgrid_path: str) -> List[SyllableSegment]:
        """기존 TextGrid 파일 파싱"""
        try:
            # 기존 TextGrid 파싱 로직 (간단한 정규식 기반)
            with open(textgrid_path, 'r', encoding='utf-16') as f:
                content = f.read()
            
            import re
            # 기존 패턴과 동일한 방식으로 파싱
            pattern = r'intervals \[\d+\]:\s*xmin = ([\d.]+)\s*xmax = ([\d.]+)\s*text = "([^"]*)"'
            matches = re.findall(pattern, content)
            
            segments = []
            for start_str, end_str, label in matches:
                if label.strip():  # 빈 라벨 제외
                    segments.append(SyllableSegment(
                        label=label.strip(),
                        start=float(start_str),
                        end=float(end_str),
                        confidence=1.0  # 기존 TextGrid는 높은 신뢰도
                    ))
            
            return segments
            
        except Exception as e:
            print(f"❌ TextGrid 파싱 실패: {e}")
            return []
    
    def get_status(self) -> Dict:
        """프로세서 상태 정보"""
        return {
            'stt_available': self.stt_engine.is_available(),
            'segmenter_available': self.segmenter.is_available(),
            'processor_ready': True
        }