"""
파일 처리 통합 유틸리티
TextGrid, 오디오 파일 등 모든 파일 I/O 처리를 담당
중복 코드 제거 및 에러 처리 통일
"""

import os
import json
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union, Any
import re
import logging
import hashlib
from datetime import datetime

# 오디오 관련
import soundfile as sf
import librosa
import numpy as np
from pydub import AudioSegment

# TextGrid 관련
try:
    import tgt
except ImportError:
    tgt = None

try:
    import textgrid
except ImportError:
    textgrid = None

from config import settings

logger = logging.getLogger(__name__)


class FileHandler:
    """파일 처리 통합 클래스"""

    # ========== TextGrid 파일 처리 ==========

    @staticmethod
    def read_textgrid(file_path: Union[str, Path]) -> Tuple[str, str]:
        """
        TextGrid 파일 읽기 (다양한 인코딩 지원)

        Args:
            file_path: TextGrid 파일 경로

        Returns:
            (content, encoding): 파일 내용과 사용된 인코딩

        Raises:
            FileNotFoundError: 파일이 존재하지 않을 때
            UnicodeDecodeError: 모든 인코딩으로 읽기 실패했을 때
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"TextGrid 파일을 찾을 수 없습니다: {file_path}")

        # 인코딩 시도 순서 (설정에서 가져옴)
        encodings = settings.TEXTGRID_ENCODINGS

        last_error = None
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                logger.debug(
                    f"TextGrid 파일 읽기 성공: {file_path} (인코딩: {encoding})")
                return content, encoding
            except UnicodeDecodeError as e:
                last_error = e
                continue
            except Exception as e:
                logger.warning(f"TextGrid 읽기 중 예외 발생 ({encoding}): {e}")
                last_error = e
                continue

        # 모든 인코딩 실패
        error_msg = f"TextGrid 파일을 읽을 수 없습니다. 시도한 인코딩: {encodings}"
        logger.error(error_msg)
        raise UnicodeDecodeError('multiple', b'', 0, 1,
                                 f"{error_msg}. 마지막 에러: {last_error}")

    @staticmethod
    def parse_textgrid_intervals(content: str) -> List[Dict[str, Any]]:
        """
        TextGrid 내용에서 interval 정보 파싱

        Args:
            content: TextGrid 파일 내용

        Returns:
            intervals 리스트 [{xmin, xmax, text}, ...]
        """
        intervals = []

        # 정규식 패턴들
        interval_pattern = r'intervals\s*\[(\d+)\]'
        xmin_pattern = r'xmin\s*=\s*([\d.]+)'
        xmax_pattern = r'xmax\s*=\s*([\d.]+)'
        text_pattern = r'text\s*=\s*"([^"]*)"'

        # 전체 내용을 interval 단위로 분리
        interval_blocks = re.split(interval_pattern, content)

        for i in range(1, len(interval_blocks), 2):
            block = interval_blocks[i +
                                    1] if i + 1 < len(interval_blocks) else ""

            xmin_match = re.search(xmin_pattern, block)
            xmax_match = re.search(xmax_pattern, block)
            text_match = re.search(text_pattern, block)

            if xmin_match and xmax_match:
                interval = {
                    'xmin': float(xmin_match.group(1)),
                    'xmax': float(xmax_match.group(1)),
                    'text': text_match.group(1) if text_match else ""
                }
                intervals.append(interval)

        return intervals

    @staticmethod
    def save_textgrid(file_path: Union[str, Path],
                      tiers: List[Dict[str, Any]],
                      xmin: float = 0.0,
                      xmax: float = None,
                      encoding: str = None) -> bool:
        """
        TextGrid 파일 저장

        Args:
            file_path: 저장할 파일 경로
            tiers: tier 정보 리스트
            xmin: 시작 시간
            xmax: 종료 시간
            encoding: 인코딩 (기본값: settings에서 가져옴)

        Returns:
            성공 여부
        """
        file_path = Path(file_path)
        encoding = encoding or settings.TEXTGRID_DEFAULT_ENCODING

        try:
            # textgrid 라이브러리 사용 가능한 경우
            if textgrid:
                tg = textgrid.TextGrid(minTime=xmin, maxTime=xmax)

                for tier_info in tiers:
                    tier_name = tier_info.get('name', 'tier')
                    tier_type = tier_info.get('type', 'interval')

                    if tier_type == 'interval':
                        tier = textgrid.IntervalTier(name=tier_name,
                                                     minTime=xmin,
                                                     maxTime=xmax)
                        for interval in tier_info.get('intervals', []):
                            tier.add(interval['xmin'], interval['xmax'],
                                     interval.get('text', ''))
                    else:  # point tier
                        tier = textgrid.PointTier(name=tier_name,
                                                  minTime=xmin,
                                                  maxTime=xmax)
                        for point in tier_info.get('points', []):
                            tier.add(point['time'], point.get('mark', ''))

                    tg.append(tier)

                # 저장
                tg.write(str(file_path))
                logger.info(f"TextGrid 저장 완료: {file_path}")
                return True

            else:
                # textgrid 라이브러리가 없는 경우 수동 생성
                return FileHandler._save_textgrid_manual(
                    file_path, tiers, xmin, xmax, encoding)

        except Exception as e:
            logger.error(f"TextGrid 저장 실패: {e}")
            return False

    @staticmethod
    def _save_textgrid_manual(file_path: Path, tiers: List[Dict], xmin: float,
                              xmax: float, encoding: str) -> bool:
        """TextGrid 수동 생성 (라이브러리 없이)"""
        try:
            content = 'File type = "ooTextFile"\n'
            content += 'Object class = "TextGrid"\n\n'
            content += f'xmin = {xmin}\n'
            content += f'xmax = {xmax}\n'
            content += f'tiers? <exists>\n'
            content += f'size = {len(tiers)}\n'
            content += 'item []:\n'

            for i, tier in enumerate(tiers, 1):
                content += f'    item [{i}]:\n'
                content += f'        class = "IntervalTier"\n'
                content += f'        name = "{tier.get("name", "tier")}"\n'
                content += f'        xmin = {xmin}\n'
                content += f'        xmax = {xmax}\n'
                intervals = tier.get('intervals', [])
                content += f'        intervals: size = {len(intervals)}\n'

                for j, interval in enumerate(intervals, 1):
                    content += f'        intervals [{j}]:\n'
                    content += f'            xmin = {interval["xmin"]}\n'
                    content += f'            xmax = {interval["xmax"]}\n'
                    content += f'            text = "{interval.get("text", "")}"\n'

            with open(file_path, 'w', encoding=encoding) as f:
                f.write(content)

            return True

        except Exception as e:
            logger.error(f"TextGrid 수동 생성 실패: {e}")
            return False

    # ========== 오디오 파일 처리 ==========

    @staticmethod
    def read_audio(file_path: Union[str, Path],
                   target_sr: Optional[int] = None,
                   mono: bool = True) -> Tuple[np.ndarray, int]:
        """
        오디오 파일 읽기 (다양한 포맷 지원)

        Args:
            file_path: 오디오 파일 경로
            target_sr: 목표 샘플레이트 (None이면 원본 유지)
            mono: 모노로 변환 여부

        Returns:
            (audio_data, sample_rate): 오디오 데이터와 샘플레이트
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {file_path}")

        try:
            # librosa로 읽기 시도
            audio, sr = librosa.load(str(file_path), sr=target_sr, mono=mono)
            logger.debug(f"오디오 파일 읽기 성공 (librosa): {file_path}")
            return audio, sr

        except Exception as e:
            logger.warning(f"librosa 읽기 실패, soundfile 시도: {e}")

            try:
                # soundfile로 읽기 시도
                audio, sr = sf.read(str(file_path))

                # 필요시 리샘플링
                if target_sr and sr != target_sr:
                    audio = librosa.resample(audio,
                                             orig_sr=sr,
                                             target_sr=target_sr)
                    sr = target_sr

                # 필요시 모노 변환
                if mono and len(audio.shape) > 1:
                    audio = np.mean(audio, axis=1)

                logger.debug(f"오디오 파일 읽기 성공 (soundfile): {file_path}")
                return audio, sr

            except Exception as e2:
                logger.error(f"오디오 파일 읽기 실패: {e2}")
                raise

    @staticmethod
    def save_audio(file_path: Union[str, Path],
                   audio_data: np.ndarray,
                   sample_rate: int,
                   normalize: bool = True) -> bool:
        """
        오디오 파일 저장

        Args:
            file_path: 저장할 파일 경로
            audio_data: 오디오 데이터
            sample_rate: 샘플레이트
            normalize: 정규화 여부

        Returns:
            성공 여부
        """
        file_path = Path(file_path)

        try:
            # 정규화
            if normalize and np.max(np.abs(audio_data)) > 0:
                audio_data = audio_data / np.max(np.abs(audio_data))

            # 저장
            sf.write(str(file_path), audio_data, sample_rate)
            logger.info(f"오디오 파일 저장 완료: {file_path}")
            return True

        except Exception as e:
            logger.error(f"오디오 파일 저장 실패: {e}")
            return False

    @staticmethod
    def get_audio_info(file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        오디오 파일 정보 추출

        Args:
            file_path: 오디오 파일 경로

        Returns:
            오디오 정보 딕셔너리
        """
        file_path = Path(file_path)

        try:
            info = sf.info(str(file_path))

            return {
                'duration': info.duration,
                'sample_rate': info.samplerate,
                'channels': info.channels,
                'format': info.format,
                'subtype': info.subtype,
                'frames': info.frames,
                'file_size': file_path.stat().st_size,
                'file_name': file_path.name
            }

        except Exception as e:
            logger.error(f"오디오 정보 추출 실패: {e}")
            return {}

    # ========== 일반 파일 처리 ==========

    @staticmethod
    def ensure_directory(directory: Union[str, Path]) -> Path:
        """
        디렉토리 존재 확인 및 생성

        Args:
            directory: 디렉토리 경로

        Returns:
            생성된 디렉토리 경로
        """
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @staticmethod
    def safe_delete(file_path: Union[str, Path]) -> bool:
        """
        안전한 파일 삭제

        Args:
            file_path: 삭제할 파일 경로

        Returns:
            삭제 성공 여부
        """
        file_path = Path(file_path)

        try:
            if file_path.exists():
                if file_path.is_file():
                    file_path.unlink()
                elif file_path.is_dir():
                    shutil.rmtree(str(file_path))
                logger.debug(f"파일 삭제 완료: {file_path}")
                return True
            return False

        except Exception as e:
            logger.error(f"파일 삭제 실패: {e}")
            return False

    @staticmethod
    def copy_file(source: Union[str, Path],
                  destination: Union[str, Path],
                  overwrite: bool = False) -> bool:
        """
        파일 복사

        Args:
            source: 원본 파일 경로
            destination: 대상 파일 경로
            overwrite: 덮어쓰기 허용 여부

        Returns:
            복사 성공 여부
        """
        source = Path(source)
        destination = Path(destination)

        if not source.exists():
            logger.error(f"원본 파일이 존재하지 않음: {source}")
            return False

        if destination.exists() and not overwrite:
            logger.warning(f"대상 파일이 이미 존재함: {destination}")
            return False

        try:
            # 대상 디렉토리 생성
            destination.parent.mkdir(parents=True, exist_ok=True)

            # 파일 복사
            shutil.copy2(str(source), str(destination))
            logger.debug(f"파일 복사 완료: {source} -> {destination}")
            return True

        except Exception as e:
            logger.error(f"파일 복사 실패: {e}")
            return False

    @staticmethod
    def get_file_hash(file_path: Union[str, Path],
                      algorithm: str = 'md5') -> str:
        """
        파일 해시값 계산

        Args:
            file_path: 파일 경로
            algorithm: 해시 알고리즘 ('md5', 'sha1', 'sha256')

        Returns:
            해시값 문자열
        """
        file_path = Path(file_path)

        if not file_path.exists():
            return ""

        hash_algo = {
            'md5': hashlib.md5,
            'sha1': hashlib.sha1,
            'sha256': hashlib.sha256
        }.get(algorithm, hashlib.md5)()

        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    hash_algo.update(chunk)
            return hash_algo.hexdigest()

        except Exception as e:
            logger.error(f"해시 계산 실패: {e}")
            return ""

    @staticmethod
    def create_temp_file(suffix: str = None,
                         prefix: str = "tonebridge_",
                         directory: Union[str, Path] = None) -> Path:
        """
        임시 파일 생성

        Args:
            suffix: 파일 확장자
            prefix: 파일 이름 접두사
            directory: 임시 파일 생성 디렉토리

        Returns:
            임시 파일 경로
        """
        directory = directory or settings.TEMP_DIR
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        temp_file = tempfile.NamedTemporaryFile(suffix=suffix,
                                                prefix=prefix,
                                                dir=str(directory),
                                                delete=False)
        temp_path = Path(temp_file.name)
        temp_file.close()

        return temp_path

    # ========== JSON 파일 처리 ==========

    @staticmethod
    def read_json(file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        JSON 파일 읽기

        Args:
            file_path: JSON 파일 경로

        Returns:
            파싱된 JSON 데이터
        """
        file_path = Path(file_path)

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"JSON 파일 읽기 실패: {e}")
            return {}

    @staticmethod
    def save_json(file_path: Union[str, Path],
                  data: Dict[str, Any],
                  indent: int = 2) -> bool:
        """
        JSON 파일 저장

        Args:
            file_path: 저장할 파일 경로
            data: 저장할 데이터
            indent: 들여쓰기 크기

        Returns:
            저장 성공 여부
        """
        file_path = Path(file_path)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"JSON 파일 저장 실패: {e}")
            return False

    # ========== 파일 검증 ==========

    @staticmethod
    def validate_audio_file(file_path: Union[str, Path]) -> Tuple[bool, str]:
        """
        오디오 파일 검증

        Args:
            file_path: 오디오 파일 경로

        Returns:
            (valid, message): 검증 결과와 메시지
        """
        file_path = Path(file_path)

        # 파일 존재 확인
        if not file_path.exists():
            return False, "파일이 존재하지 않습니다"

        # 확장자 확인
        if not settings.validate_file_extension(str(file_path)):
            return False, f"지원하지 않는 파일 형식입니다. 지원 형식: {settings.ALLOWED_EXTENSIONS}"

        # 파일 크기 확인
        file_size = file_path.stat().st_size
        if file_size > settings.MAX_UPLOAD_SIZE:
            return False, f"파일 크기가 너무 큽니다. 최대: {settings.MAX_UPLOAD_SIZE / 1024 / 1024:.0f}MB"

        # 오디오 파일로 읽기 가능한지 확인
        try:
            info = FileHandler.get_audio_info(file_path)
            if not info or info.get('duration', 0) <= 0:
                return False, "유효하지 않은 오디오 파일입니다"
        except Exception as e:
            return False, f"오디오 파일 검증 실패: {str(e)}"

        return True, "검증 통과"

    @staticmethod
    def validate_textgrid_file(
            file_path: Union[str, Path]) -> Tuple[bool, str]:
        """
        TextGrid 파일 검증

        Args:
            file_path: TextGrid 파일 경로

        Returns:
            (valid, message): 검증 결과와 메시지
        """
        file_path = Path(file_path)

        # 파일 존재 확인
        if not file_path.exists():
            return False, "파일이 존재하지 않습니다"

        # 확장자 확인
        if not file_path.suffix.lower() in ['.textgrid', '.txt']:
            return False, "TextGrid 파일이 아닙니다"

        # 파일 읽기 가능한지 확인
        try:
            content, encoding = FileHandler.read_textgrid(file_path)
            if not content or 'File type = "ooTextFile"' not in content:
                return False, "유효하지 않은 TextGrid 파일입니다"
        except Exception as e:
            return False, f"TextGrid 파일 검증 실패: {str(e)}"

        return True, "검증 통과"


# 싱글톤 인스턴스
file_handler = FileHandler()


# 유틸리티 함수들 (하위 호환성을 위해)
def read_textgrid(file_path: Union[str, Path]) -> Tuple[str, str]:
    """TextGrid 파일 읽기 (하위 호환성)"""
    return file_handler.read_textgrid(file_path)


def read_audio(file_path: Union[str, Path],
               sr: Optional[int] = None) -> Tuple[np.ndarray, int]:
    """오디오 파일 읽기 (하위 호환성)"""
    return file_handler.read_audio(file_path, target_sr=sr)


def save_audio(file_path: Union[str, Path], audio: np.ndarray,
               sr: int) -> bool:
    """오디오 파일 저장 (하위 호환성)"""
    return file_handler.save_audio(file_path, audio, sr)
