"""
통합 TextGrid 생성기
기존 TextGrid 생성 함수들을 통합하여 일관된 결과 제공
"""

import sys
from pathlib import Path
from typing import List, Optional

# 기존 모듈 임포트 (하위 호환성)
sys.path.append(str(Path(__file__).parent.parent.parent))

from ..models import SyllableSegment

class UnifiedTextGridGenerator:
    """
    단일 TextGrid 생성기 - 모든 용도에 사용
    기존 TextGrid 생성 방식들을 통합
    """
    
    def __init__(self):
        pass
    
    def from_syllables(self, segments: List[SyllableSegment], duration: float = None) -> str:
        """
        음절 데이터에서 TextGrid 생성
        기존 create_textgrid_from_syllables 함수와 호환
        """
        if not segments:
            return self._create_empty_textgrid(duration or 1.0)
        
        # 전체 지속시간 계산
        if duration is None:
            duration = max(seg.end for seg in segments) if segments else 1.0
        
        return self._generate_textgrid_content(segments, duration)
    
    def from_audio(self, audio_file: str, text_hint: str = None) -> str:
        """
        오디오에서 TextGrid 생성 (모든 차트 공통)
        기존 create_textgrid_from_audio 함수와 호환
        """
        from ..segmentation.korean_segmenter import KoreanSyllableSegmenter
        
        segmenter = KoreanSyllableSegmenter()
        segments = segmenter.segment(audio_file, text_hint)
        
        # 오디오 길이 확인
        try:
            import parselmouth as pm
            sound = pm.Sound(audio_file)
            duration = sound.get_total_duration()
        except:
            duration = max(seg.end for seg in segments) if segments else 1.0
        
        return self.from_syllables(segments, duration)
    
    def _generate_textgrid_content(self, segments: List[SyllableSegment], duration: float) -> str:
        """
        TextGrid 포맷 생성 - 기존 포맷과 호환
        """
        content = f'''File type = "ooTextFile"
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
        intervals: size = {len(segments)}
'''
        
        for i, segment in enumerate(segments, 1):
            content += f'''        intervals [{i}]:
            xmin = {segment.start}
            xmax = {segment.end}
            text = "{segment.label}"
'''
        
        return content
    
    def _create_empty_textgrid(self, duration: float) -> str:
        """빈 TextGrid 생성"""
        return f'''File type = "ooTextFile"
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
        intervals: size = 0
'''
    
    def save_to_file(self, segments: List[SyllableSegment], output_path: str, 
                     duration: float = None) -> bool:
        """
        TextGrid 파일로 저장
        기존 save_textgrid 함수와 호환
        """
        try:
            content = self.from_syllables(segments, duration)
            
            with open(output_path, 'w', encoding='utf-16') as f:
                f.write(content)
            
            print(f"✅ TextGrid 저장 완료: {output_path}")
            return True
        except Exception as e:
            print(f"❌ TextGrid 저장 실패: {e}")
            return False