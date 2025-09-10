"""
TextGrid 생성기
Praat TextGrid 파일 생성, 파싱, 검증 및 관리
"""

import warnings

warnings.filterwarnings('ignore')

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
import numpy as np
from dataclasses import dataclass
from enum import Enum
import json
from datetime import datetime

# TextGrid 라이브러리
try:
    import textgrid as tg
    TEXTGRID_AVAILABLE = True
except ImportError:
    TEXTGRID_AVAILABLE = False

try:
    import tgt
    TGT_AVAILABLE = True
except ImportError:
    TGT_AVAILABLE = False

# 프로젝트 모듈
from config import settings
from utils import (FileHandler, file_handler, get_logger, log_execution_time,
                   handle_errors, TextGridError)

# ToneBridge Core 모델
from tonebridge_core.models import (TextGridData, TextGridTier,
                                    TextGridInterval, TextGridPoint,
                                    TimeInterval)

logger = get_logger(__name__)

# ========== 열거형 정의 ==========


class TierType(Enum):
    """티어 타입"""
    WORDS = "words"
    PHONES = "phones"
    SYLLABLES = "syllables"
    PITCH = "pitch"
    INTENSITY = "intensity"
    COMMENTS = "comments"
    CUSTOM = "custom"


class AlignmentMethod(Enum):
    """정렬 방법"""
    FORCED = "forced"  # 강제 정렬
    AUTOMATIC = "automatic"  # 자동 정렬
    MANUAL = "manual"  # 수동 정렬
    HYBRID = "hybrid"  # 하이브리드


# ========== TextGrid 빌더 ==========


class TextGridBuilder:
    """TextGrid 구성 빌더"""

    def __init__(self, xmin: float = 0.0, xmax: float = 1.0):
        """
        초기화

        Args:
            xmin: 시작 시간
            xmax: 종료 시간
        """
        self.xmin = xmin
        self.xmax = xmax
        self.tiers = []

    def add_interval_tier(
            self, name: str, intervals: List[Tuple[float, float,
                                                   str]]) -> 'TextGridBuilder':
        """
        인터벌 티어 추가

        Args:
            name: 티어 이름
            intervals: [(시작, 끝, 텍스트), ...]

        Returns:
            self (체이닝용)
        """
        tier = TextGridTier(name=name,
                            tier_type="IntervalTier",
                            xmin=self.xmin,
                            xmax=self.xmax,
                            intervals=[])

        # 인터벌 추가
        for start, end, text in intervals:
            tier.intervals.append(TextGridInterval(start, end, text))

        self.tiers.append(tier)
        return self

    def add_point_tier(self, name: str,
                       points: List[Tuple[float, str]]) -> 'TextGridBuilder':
        """
        포인트 티어 추가

        Args:
            name: 티어 이름
            points: [(시간, 마크), ...]

        Returns:
            self
        """
        tier = TextGridTier(name=name,
                            tier_type="TextTier",
                            xmin=self.xmin,
                            xmax=self.xmax,
                            points=[])

        # 포인트 추가
        for time, mark in points:
            tier.points.append(TextGridPoint(time, mark))

        self.tiers.append(tier)
        return self

    def build(self) -> TextGridData:
        """TextGrid 데이터 생성"""
        return TextGridData(xmin=self.xmin, xmax=self.xmax, tiers=self.tiers)


# ========== TextGrid 파서 ==========


class TextGridParser:
    """TextGrid 파일 파서"""

    @staticmethod
    @handle_errors(context="parse_textgrid")
    def parse(file_path: Union[str, Path]) -> TextGridData:
        """
        TextGrid 파일 파싱

        Args:
            file_path: TextGrid 파일 경로

        Returns:
            TextGrid 데이터
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"TextGrid 파일을 찾을 수 없습니다: {file_path}")

        # textgrid 라이브러리 사용 가능한 경우
        if TEXTGRID_AVAILABLE:
            return TextGridParser._parse_with_textgrid(file_path)
        # tgt 라이브러리 사용 가능한 경우
        elif TGT_AVAILABLE:
            return TextGridParser._parse_with_tgt(file_path)
        # 수동 파싱
        else:
            return TextGridParser._parse_manual(file_path)

    @staticmethod
    def _parse_with_textgrid(file_path: Path) -> TextGridData:
        """textgrid 라이브러리로 파싱"""
        try:
            tg_obj = tg.TextGrid.fromFile(str(file_path))

            tiers = []
            for tier in tg_obj.tiers:
                if isinstance(tier, tg.IntervalTier):
                    intervals = []
                    for interval in tier:
                        intervals.append(
                            TextGridInterval(interval.minTime,
                                             interval.maxTime, interval.mark))

                    tiers.append(
                        TextGridTier(name=tier.name,
                                     tier_type="IntervalTier",
                                     xmin=tier.minTime,
                                     xmax=tier.maxTime,
                                     intervals=intervals))

                elif isinstance(tier, tg.PointTier):
                    points = []
                    for point in tier:
                        points.append(TextGridPoint(point.time, point.mark))

                    tiers.append(
                        TextGridTier(name=tier.name,
                                     tier_type="TextTier",
                                     xmin=tier.minTime,
                                     xmax=tier.maxTime,
                                     points=points))

            return TextGridData(xmin=tg_obj.minTime,
                                xmax=tg_obj.maxTime,
                                tiers=tiers)

        except Exception as e:
            raise TextGridError(f"TextGrid 파싱 실패: {str(e)}")

    @staticmethod
    def _parse_with_tgt(file_path: Path) -> TextGridData:
        """tgt 라이브러리로 파싱"""
        try:
            tg_obj = tgt.read_textgrid(str(file_path))

            tiers = []
            for tier in tg_obj.tiers:
                if isinstance(tier, tgt.IntervalTier):
                    intervals = []
                    for interval in tier:
                        intervals.append(
                            TextGridInterval(interval.start_time,
                                             interval.end_time, interval.text))

                    tiers.append(
                        TextGridTier(name=tier.name,
                                     tier_type="IntervalTier",
                                     xmin=tier.start_time,
                                     xmax=tier.end_time,
                                     intervals=intervals))

                elif isinstance(tier, tgt.PointTier):
                    points = []
                    for point in tier:
                        points.append(TextGridPoint(point.time, point.text))

                    tiers.append(
                        TextGridTier(name=tier.name,
                                     tier_type="TextTier",
                                     xmin=tier.start_time,
                                     xmax=tier.end_time,
                                     points=points))

            return TextGridData(xmin=tg_obj.start_time,
                                xmax=tg_obj.end_time,
                                tiers=tiers)

        except Exception as e:
            raise TextGridError(f"TextGrid 파싱 실패: {str(e)}")

    @staticmethod
    def _parse_manual(file_path: Path) -> TextGridData:
        """수동 파싱"""
        content, encoding = file_handler.read_textgrid(file_path)

        # 정규식 패턴
        xmin_pattern = r'xmin\s*=\s*([\d.]+)'
        xmax_pattern = r'xmax\s*=\s*([\d.]+)'
        size_pattern = r'size\s*=\s*(\d+)'

        # 전체 시간 추출
        xmin_match = re.search(xmin_pattern, content)
        xmax_match = re.search(xmax_pattern, content)

        if not xmin_match or not xmax_match:
            raise TextGridError("TextGrid 시간 정보를 찾을 수 없습니다")

        xmin = float(xmin_match.group(1))
        xmax = float(xmax_match.group(1))

        # 티어 파싱
        tiers = []
        tier_pattern = r'item\s*\[\d+\]:\s*\n(.*?)(?=item\s*\[\d+\]:|$)'
        tier_matches = re.findall(tier_pattern, content, re.DOTALL)

        for tier_content in tier_matches:
            tier = TextGridParser._parse_tier(tier_content, xmin, xmax)
            if tier:
                tiers.append(tier)

        return TextGridData(xmin=xmin, xmax=xmax, tiers=tiers)

    @staticmethod
    def _parse_tier(content: str, xmin: float,
                    xmax: float) -> Optional[TextGridTier]:
        """티어 파싱"""
        # 티어 정보 추출
        class_match = re.search(r'class\s*=\s*"([^"]+)"', content)
        name_match = re.search(r'name\s*=\s*"([^"]*)"', content)

        if not class_match or not name_match:
            return None

        tier_class = class_match.group(1)
        tier_name = name_match.group(1)

        if tier_class == "IntervalTier":
            # 인터벌 티어
            intervals = []
            interval_pattern = r'intervals\s*\[(\d+)\]:\s*\n\s*xmin\s*=\s*([\d.]+)\s*\n\s*xmax\s*=\s*([\d.]+)\s*\n\s*text\s*=\s*"([^"]*)"'

            for match in re.finditer(interval_pattern, content):
                intervals.append(
                    TextGridInterval(float(match.group(2)),
                                     float(match.group(3)), match.group(4)))

            return TextGridTier(name=tier_name,
                                tier_type="IntervalTier",
                                xmin=xmin,
                                xmax=xmax,
                                intervals=intervals)

        elif tier_class == "TextTier":
            # 포인트 티어
            points = []
            point_pattern = r'points\s*\[(\d+)\]:\s*\n\s*time\s*=\s*([\d.]+)\s*\n\s*mark\s*=\s*"([^"]*)"'

            for match in re.finditer(point_pattern, content):
                points.append(
                    TextGridPoint(float(match.group(2)), match.group(3)))

            return TextGridTier(name=tier_name,
                                tier_type="TextTier",
                                xmin=xmin,
                                xmax=xmax,
                                points=points)

        return None


# ========== TextGrid 검증기 ==========


class TextGridValidator:
    """TextGrid 검증기"""

    @staticmethod
    def validate(textgrid: TextGridData) -> Tuple[bool, List[str]]:
        """
        TextGrid 검증

        Args:
            textgrid: TextGrid 데이터

        Returns:
            (유효 여부, 문제점 리스트)
        """
        issues = []

        # 기본 검증
        if textgrid.xmin >= textgrid.xmax:
            issues.append(f"잘못된 시간 범위: {textgrid.xmin} >= {textgrid.xmax}")

        # 티어별 검증
        for tier in textgrid.tiers:
            tier_issues = TextGridValidator._validate_tier(
                tier, textgrid.xmin, textgrid.xmax)
            issues.extend(tier_issues)

        return len(issues) == 0, issues

    @staticmethod
    def _validate_tier(tier: TextGridTier, xmin: float,
                       xmax: float) -> List[str]:
        """티어 검증"""
        issues = []

        # 티어 시간 범위 검증
        if tier.xmin < xmin or tier.xmax > xmax:
            issues.append(f"티어 '{tier.name}' 시간 범위 초과")

        if tier.tier_type == "IntervalTier":
            # 인터벌 티어 검증
            if not tier.intervals:
                issues.append(f"티어 '{tier.name}'에 인터벌이 없음")
            else:
                # 인터벌 연속성 검증
                prev_end = tier.xmin
                for interval in tier.intervals:
                    if interval.xmin < prev_end:
                        issues.append(f"티어 '{tier.name}'에 겹치는 인터벌")
                    elif interval.xmin > prev_end + 0.001:  # 1ms 허용
                        issues.append(f"티어 '{tier.name}'에 빈 구간")
                    prev_end = interval.xmax

                # 마지막 인터벌 검증
                if abs(prev_end - tier.xmax) > 0.001:
                    issues.append(f"티어 '{tier.name}' 끝 시간 불일치")

        elif tier.tier_type == "TextTier":
            # 포인트 티어 검증
            if tier.points:
                # 시간 순서 검증
                prev_time = tier.xmin
                for point in tier.points:
                    if point.time < prev_time:
                        issues.append(f"티어 '{tier.name}'에 순서가 잘못된 포인트")
                    prev_time = point.time

        return issues


# ========== TextGrid 병합기 ==========


class TextGridMerger:
    """TextGrid 병합기"""

    @staticmethod
    def merge(textgrids: List[TextGridData],
              method: str = "sequential") -> TextGridData:
        """
        여러 TextGrid 병합

        Args:
            textgrids: TextGrid 리스트
            method: 병합 방법 ("sequential", "overlay")

        Returns:
            병합된 TextGrid
        """
        if not textgrids:
            raise ValueError("병합할 TextGrid가 없습니다")

        if len(textgrids) == 1:
            return textgrids[0]

        if method == "sequential":
            return TextGridMerger._merge_sequential(textgrids)
        elif method == "overlay":
            return TextGridMerger._merge_overlay(textgrids)
        else:
            raise ValueError(f"지원하지 않는 병합 방법: {method}")

    @staticmethod
    def _merge_sequential(textgrids: List[TextGridData]) -> TextGridData:
        """순차 병합"""
        total_duration = sum(tg.duration for tg in textgrids)
        merged_tiers = {}

        current_offset = 0.0

        for tg in textgrids:
            for tier in tg.tiers:
                if tier.name not in merged_tiers:
                    merged_tiers[tier.name] = {
                        'type': tier.tier_type,
                        'intervals': [],
                        'points': []
                    }

                if tier.tier_type == "IntervalTier":
                    for interval in tier.intervals:
                        merged_tiers[tier.name]['intervals'].append(
                            TextGridInterval(interval.xmin + current_offset,
                                             interval.xmax + current_offset,
                                             interval.text))
                else:
                    for point in tier.points:
                        merged_tiers[tier.name]['points'].append(
                            TextGridPoint(point.time + current_offset,
                                          point.mark))

            current_offset += tg.duration

        # TextGrid 생성
        tiers = []
        for name, data in merged_tiers.items():
            if data['type'] == "IntervalTier":
                tier = TextGridTier(name=name,
                                    tier_type="IntervalTier",
                                    xmin=0.0,
                                    xmax=total_duration,
                                    intervals=data['intervals'])
            else:
                tier = TextGridTier(name=name,
                                    tier_type="TextTier",
                                    xmin=0.0,
                                    xmax=total_duration,
                                    points=data['points'])
            tiers.append(tier)

        return TextGridData(xmin=0.0, xmax=total_duration, tiers=tiers)

    @staticmethod
    def _merge_overlay(textgrids: List[TextGridData]) -> TextGridData:
        """오버레이 병합"""
        # 최대 시간 찾기
        xmin = min(tg.xmin for tg in textgrids)
        xmax = max(tg.xmax for tg in textgrids)

        # 모든 티어 수집
        all_tiers = []
        tier_counter = {}

        for tg in textgrids:
            for tier in tg.tiers:
                # 중복 이름 처리
                original_name = tier.name
                if original_name in tier_counter:
                    tier_counter[original_name] += 1
                    tier.name = f"{original_name}_{tier_counter[original_name]}"
                else:
                    tier_counter[original_name] = 1

                all_tiers.append(tier)

        return TextGridData(xmin=xmin, xmax=xmax, tiers=all_tiers)


# ========== TextGrid 생성기 ==========


class TextGridGenerator:
    """TextGrid 생성기"""

    def __init__(self):
        """초기화"""
        self.file_handler = file_handler
        logger.info("TextGridGenerator 초기화 완료")

    @handle_errors(context="generate_textgrid")
    @log_execution_time
    def generate(
        self,
        duration: float,
        segments: Optional[List[Dict]] = None,
        transcription: Optional[str] = None,
        pitch_data: Optional[List[Tuple[float,
                                        float]]] = None) -> TextGridData:
        """
        TextGrid 생성

        Args:
            duration: 전체 길이
            segments: 세그먼트 리스트
            transcription: 전사 텍스트
            pitch_data: 피치 데이터 [(time, frequency), ...]

        Returns:
            TextGrid 데이터
        """
        builder = TextGridBuilder(0.0, duration)

        # Words 티어
        if segments:
            word_intervals = []
            for seg in segments:
                start = seg.get('start', 0.0)
                end = seg.get('end', 0.0)
                text = seg.get('text', '')
                word_intervals.append((start, end, text))

            if word_intervals:
                builder.add_interval_tier("words", word_intervals)

        # Sentence 티어
        if transcription:
            builder.add_interval_tier("sentence",
                                      [(0.0, duration, transcription)])

        # Pitch 티어
        if pitch_data:
            pitch_points = [(t, f"{f:.1f}") for t, f in pitch_data if f > 0]
            if pitch_points:
                builder.add_point_tier("pitch", pitch_points)

        return builder.build()

    @handle_errors(context="generate_from_stt")
    def generate_from_stt(self, stt_result: Dict[str, Any],
                          duration: float) -> TextGridData:
        """
        STT 결과로부터 TextGrid 생성

        Args:
            stt_result: STT 결과
            duration: 오디오 길이

        Returns:
            TextGrid 데이터
        """
        builder = TextGridBuilder(0.0, duration)

        # 전체 텍스트
        full_text = stt_result.get('text', '')
        if full_text:
            builder.add_interval_tier("utterance",
                                      [(0.0, duration, full_text)])

        # 세그먼트
        if 'segments' in stt_result:
            word_intervals = []
            for seg in stt_result['segments']:
                start = seg.get('start', 0.0)
                end = seg.get('end', 0.0)
                text = seg.get('text', '')
                word_intervals.append((start, end, text))

            if word_intervals:
                builder.add_interval_tier("words", word_intervals)

        # 단어별 신뢰도
        if 'segments' in stt_result:
            confidence_points = []
            for seg in stt_result['segments']:
                time = (seg.get('start', 0.0) + seg.get('end', 0.0)) / 2
                conf = seg.get('confidence', 0.0)
                confidence_points.append((time, f"{conf:.2f}"))

            if confidence_points:
                builder.add_point_tier("confidence", confidence_points)

        return builder.build()

    @handle_errors(context="save_textgrid")
    def save(self,
             textgrid: TextGridData,
             file_path: Union[str, Path],
             encoding: Optional[str] = None) -> bool:
        """
        TextGrid 저장

        Args:
            textgrid: TextGrid 데이터
            file_path: 저장 경로
            encoding: 인코딩

        Returns:
            성공 여부
        """
        file_path = Path(file_path)
        encoding = encoding or settings.TEXTGRID_DEFAULT_ENCODING

        try:
            # TextGrid 포맷 생성
            content = self._format_textgrid(textgrid)

            # 파일 저장
            with open(file_path, 'w', encoding=encoding) as f:
                f.write(content)

            logger.info(f"TextGrid 저장 완료: {file_path}")
            return True

        except Exception as e:
            logger.error(f"TextGrid 저장 실패: {str(e)}")
            return False

    def _format_textgrid(self, textgrid: TextGridData) -> str:
        """TextGrid 포맷 생성"""
        lines = []

        # 헤더
        lines.append('File type = "ooTextFile"')
        lines.append('Object class = "TextGrid"')
        lines.append('')
        lines.append(f'xmin = {textgrid.xmin}')
        lines.append(f'xmax = {textgrid.xmax}')
        lines.append('tiers? <exists>')
        lines.append(f'size = {len(textgrid.tiers)}')
        lines.append('item []:')

        # 티어들
        for i, tier in enumerate(textgrid.tiers, 1):
            lines.append(f'    item [{i}]:')
            lines.append(f'        class = "{tier.tier_type}"')
            lines.append(f'        name = "{tier.name}"')
            lines.append(f'        xmin = {tier.xmin}')
            lines.append(f'        xmax = {tier.xmax}')

            if tier.tier_type == "IntervalTier":
                lines.append(
                    f'        intervals: size = {len(tier.intervals)}')
                for j, interval in enumerate(tier.intervals, 1):
                    lines.append(f'        intervals [{j}]:')
                    lines.append(f'            xmin = {interval.xmin}')
                    lines.append(f'            xmax = {interval.xmax}')
                    lines.append(f'            text = "{interval.text}"')
            else:
                lines.append(f'        points: size = {len(tier.points)}')
                for j, point in enumerate(tier.points, 1):
                    lines.append(f'        points [{j}]:')
                    lines.append(f'            time = {point.time}')
                    lines.append(f'            mark = "{point.mark}"')

        return '\n'.join(lines)

    @handle_errors(context="align_textgrid")
    def align_with_audio(
            self,
            textgrid: TextGridData,
            audio_duration: float,
            method: AlignmentMethod = AlignmentMethod.AUTOMATIC
    ) -> TextGridData:
        """
        TextGrid를 오디오와 정렬

        Args:
            textgrid: TextGrid 데이터
            audio_duration: 오디오 길이
            method: 정렬 방법

        Returns:
            정렬된 TextGrid
        """
        if abs(textgrid.duration - audio_duration) < 0.01:
            # 이미 정렬됨
            return textgrid

        # 시간 비율 계산
        ratio = audio_duration / textgrid.duration if textgrid.duration > 0 else 1.0

        # 새 TextGrid 생성
        aligned_tiers = []

        for tier in textgrid.tiers:
            if tier.tier_type == "IntervalTier":
                aligned_intervals = []
                for interval in tier.intervals:
                    aligned_intervals.append(
                        TextGridInterval(interval.xmin * ratio,
                                         interval.xmax * ratio, interval.text))

                aligned_tiers.append(
                    TextGridTier(name=tier.name,
                                 tier_type="IntervalTier",
                                 xmin=0.0,
                                 xmax=audio_duration,
                                 intervals=aligned_intervals))
            else:
                aligned_points = []
                for point in tier.points:
                    aligned_points.append(
                        TextGridPoint(point.time * ratio, point.mark))

                aligned_tiers.append(
                    TextGridTier(name=tier.name,
                                 tier_type="TextTier",
                                 xmin=0.0,
                                 xmax=audio_duration,
                                 points=aligned_points))

        return TextGridData(xmin=0.0, xmax=audio_duration, tiers=aligned_tiers)


# 메인 실행 코드
if __name__ == "__main__":
    from config import settings

    # 테스트
    generator = TextGridGenerator()

    # 샘플 TextGrid 생성
    textgrid = generator.generate(duration=3.0,
                                  segments=[{
                                      'start': 0.0,
                                      'end': 1.0,
                                      'text': '안녕'
                                  }, {
                                      'start': 1.0,
                                      'end': 2.0,
                                      'text': '하세'
                                  }, {
                                      'start': 2.0,
                                      'end': 3.0,
                                      'text': '요'
                                  }],
                                  transcription="안녕하세요",
                                  pitch_data=[(0.5, 150.0), (1.5, 180.0),
                                              (2.5, 160.0)])

    logger.info(f"TextGrid 생성 완료:")
    logger.info(f"  - 티어 수: {textgrid.tier_count}")
    logger.info(f"  - 길이: {textgrid.duration}초")

    # 검증
    valid, issues = TextGridValidator.validate(textgrid)
    if valid:
        logger.info("TextGrid 검증 통과")
    else:
        logger.warning(f"TextGrid 검증 실패: {issues}")

    # 저장 테스트
    test_path = Path("test_textgrid.TextGrid")
    if generator.save(textgrid, test_path):
        logger.info(f"TextGrid 저장 성공: {test_path}")

        # 다시 읽기
        parsed = TextGridParser.parse(test_path)
        logger.info(f"TextGrid 파싱 성공: {parsed.tier_count}개 티어")

        # 파일 삭제
        test_path.unlink()
        logger.info("테스트 파일 삭제 완료")
