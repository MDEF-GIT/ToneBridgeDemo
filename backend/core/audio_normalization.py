"""
오디오 정규화 및 전처리 모듈
무음 제거, 볼륨 정규화, 샘플레이트 조정 등 오디오 전처리 기능
"""

import os
import sys
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
import warnings
warnings.filterwarnings('ignore')

# 오디오 처리 라이브러리
import numpy as np
import librosa
import soundfile as sf
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
try:
    import parselmouth
    PARSELMOUTH_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Parselmouth 라이브러리 로딩 실패: {e}")
    parselmouth = None
    PARSELMOUTH_AVAILABLE = False
# Optional textgrid import (Pure Nix compatibility)
try:
    import textgrid as tg
    HAS_TEXTGRID = True
except ImportError:
    tg = None
    HAS_TEXTGRID = False

# 프로젝트 모듈
from config import settings
from utils import (
    FileHandler,
    file_handler,
    get_logger,
    log_execution_time,
    handle_errors,
    AudioProcessingError
)

logger = get_logger(__name__)


class AudioNormalizer:
    """오디오 정규화 처리 클래스"""

    def __init__(self):
        """초기화"""
        self.sample_rate = settings.TARGET_SAMPLE_RATE
        self.target_db = settings.TARGET_DB
        self.silence_threshold = settings.SILENCE_THRESHOLD
        self.file_handler = file_handler

        logger.info("AudioNormalizer 초기화 완료")

    @handle_errors(context="remove_silence")
    @log_execution_time
    def remove_silence(
        self,
        audio_path: Path,
        output_path: Optional[Path] = None,
        min_silence_len: int = 500,
        silence_thresh: Optional[float] = None,
        keep_silence: int = 100
    ) -> Tuple[Path, float]:
        """
        오디오에서 무음 구간 제거

        Args:
            audio_path: 입력 오디오 파일 경로
            output_path: 출력 파일 경로 (None이면 자동 생성)
            min_silence_len: 무음으로 간주할 최소 길이 (ms)
            silence_thresh: 무음 임계값 (dB)
            keep_silence: 유지할 무음 길이 (ms)

        Returns:
            (output_path, ratio): 출력 파일 경로와 길이 비율
        """
        try:
            # 오디오 로드
            audio = AudioSegment.from_file(str(audio_path))
            original_duration = len(audio)

            # 무음 임계값 설정
            if silence_thresh is None:
                silence_thresh = self.silence_threshold

            # 무음이 아닌 구간 검출
            nonsilent_ranges = detect_nonsilent(
                audio,
                min_silence_len=min_silence_len,
                silence_thresh=silence_thresh,
                seek_step=1
            )

            if not nonsilent_ranges:
                logger.warning(f"전체가 무음으로 감지됨: {audio_path}")
                return audio_path, 1.0

            # 무음 제거된 오디오 생성
            processed_audio = AudioSegment.empty()

            for start_i, end_i in nonsilent_ranges:
                # 앞뒤로 약간의 무음 유지
                start_i = max(0, start_i - keep_silence)
                end_i = min(len(audio), end_i + keep_silence)
                processed_audio += audio[start_i:end_i]

            # 출력 경로 설정
            if output_path is None:
                output_path = audio_path.parent / f"{audio_path.stem}_nosilence.wav"

            # 저장
            processed_audio.export(
                str(output_path),
                format="wav",
                parameters=["-ar", str(self.sample_rate)]
            )

            # 길이 비율 계산
            processed_duration = len(processed_audio)
            ratio = processed_duration / original_duration if original_duration > 0 else 1.0

            logger.info(
                f"무음 제거 완료: {audio_path.name} "
                f"({original_duration}ms -> {processed_duration}ms, 비율: {ratio:.2%})"
            )

            return output_path, ratio

        except Exception as e:
            raise AudioProcessingError(f"무음 제거 실패: {str(e)}")

    @handle_errors(context="normalize_volume")
    @log_execution_time
    def normalize_volume(
        self,
        audio_path: Path,
        output_path: Optional[Path] = None,
        target_dBFS: Optional[float] = None
    ) -> Path:
        """
        오디오 볼륨 정규화

        Args:
            audio_path: 입력 오디오 파일 경로
            output_path: 출력 파일 경로
            target_dBFS: 목표 볼륨 (dBFS)

        Returns:
            출력 파일 경로
        """
        try:
            # 오디오 로드
            audio = AudioSegment.from_file(str(audio_path))

            # 목표 볼륨 설정
            if target_dBFS is None:
                target_dBFS = self.target_db

            # 현재 볼륨 측정
            current_dBFS = audio.dBFS

            # 볼륨 조정
            change_in_dBFS = target_dBFS - current_dBFS
            normalized_audio = audio.apply_gain(change_in_dBFS)

            # 출력 경로 설정
            if output_path is None:
                output_path = audio_path.parent / f"{audio_path.stem}_normalized.wav"

            # 저장
            normalized_audio.export(
                str(output_path),
                format="wav",
                parameters=["-ar", str(self.sample_rate)]
            )

            logger.info(
                f"볼륨 정규화 완료: {audio_path.name} "
                f"({current_dBFS:.1f}dB -> {target_dBFS:.1f}dB)"
            )

            return output_path

        except Exception as e:
            raise AudioProcessingError(f"볼륨 정규화 실패: {str(e)}")

    @handle_errors(context="adjust_sample_rate")
    @log_execution_time
    def adjust_sample_rate(
        self,
        audio_path: Path,
        output_path: Optional[Path] = None,
        target_sr: Optional[int] = None
    ) -> Path:
        """
        샘플레이트 조정

        Args:
            audio_path: 입력 오디오 파일 경로
            output_path: 출력 파일 경로
            target_sr: 목표 샘플레이트

        Returns:
            출력 파일 경로
        """
        try:
            # 목표 샘플레이트 설정
            if target_sr is None:
                target_sr = self.sample_rate

            # 오디오 로드
            audio, sr = librosa.load(str(audio_path), sr=None)

            # 샘플레이트가 이미 목표값인 경우
            if sr == target_sr:
                logger.debug(f"샘플레이트가 이미 {target_sr}Hz입니다")
                return audio_path

            # 리샘플링
            resampled_audio = librosa.resample(
                audio,
                orig_sr=sr,
                target_sr=target_sr
            )

            # 출력 경로 설정
            if output_path is None:
                output_path = audio_path.parent / f"{audio_path.stem}_{target_sr}hz.wav"

            # 저장
            sf.write(str(output_path), resampled_audio, target_sr)

            logger.info(
                f"샘플레이트 조정 완료: {audio_path.name} "
                f"({sr}Hz -> {target_sr}Hz)"
            )

            return output_path

        except Exception as e:
            raise AudioProcessingError(f"샘플레이트 조정 실패: {str(e)}")

    @handle_errors(context="process_audio_file")
    @log_execution_time
    def process_audio_file(
        self,
        audio_path: Path,
        output_path: Optional[Path] = None,
        remove_silence_flag: bool = True,
        normalize_volume_flag: bool = True,
        adjust_sr_flag: bool = True
    ) -> Dict[str, Any]:
        """
        오디오 파일 전체 처리 파이프라인

        Args:
            audio_path: 입력 오디오 파일 경로
            output_path: 최종 출력 파일 경로
            remove_silence_flag: 무음 제거 여부
            normalize_volume_flag: 볼륨 정규화 여부
            adjust_sr_flag: 샘플레이트 조정 여부

        Returns:
            처리 결과 정보
        """
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {audio_path}")

        # 임시 파일 경로들
        temp_files = []
        current_path = audio_path

        try:
            # 처리 정보 수집
            result = {
                'original_path': str(audio_path),
                'steps': []
            }

            # 1. 샘플레이트 조정
            if adjust_sr_flag:
                logger.debug("샘플레이트 조정 중...")
                temp_path = self.file_handler.create_temp_file(suffix=".wav")
                current_path = self.adjust_sample_rate(current_path, temp_path)
                temp_files.append(temp_path)
                result['steps'].append('sample_rate_adjustment')

            # 2. 무음 제거
            silence_ratio = 1.0
            if remove_silence_flag:
                logger.debug("무음 제거 중...")
                temp_path = self.file_handler.create_temp_file(suffix=".wav")
                current_path, silence_ratio = self.remove_silence(current_path, temp_path)
                temp_files.append(temp_path)
                result['steps'].append('silence_removal')
                result['silence_ratio'] = silence_ratio

            # 3. 볼륨 정규화
            if normalize_volume_flag:
                logger.debug("볼륨 정규화 중...")
                temp_path = self.file_handler.create_temp_file(suffix=".wav")
                current_path = self.normalize_volume(current_path, temp_path)
                temp_files.append(temp_path)
                result['steps'].append('volume_normalization')

            # 최종 파일 저장
            if output_path is None:
                output_path = audio_path.parent / f"{audio_path.stem}_processed.wav"
            else:
                output_path = Path(output_path)

            # 최종 파일 복사
            self.file_handler.copy_file(current_path, output_path, overwrite=True)

            result['output_path'] = str(output_path)
            result['success'] = True

            # 오디오 정보 추가
            audio_info = self.file_handler.get_audio_info(output_path)
            result['audio_info'] = audio_info

            logger.info(f"오디오 처리 완료: {audio_path.name} -> {output_path.name}")

            return result

        finally:
            # 임시 파일 정리
            for temp_file in temp_files:
                self.file_handler.safe_delete(temp_file)


class TextGridSynchronizer:
    """TextGrid 시간 동기화 클래스"""

    def __init__(self):
        """초기화"""
        self.file_handler = file_handler
        logger.info("TextGridSynchronizer 초기화 완료")

    @handle_errors(context="synchronize_textgrid")
    @log_execution_time
    def synchronize_textgrid(
        self,
        textgrid_path: Path,
        output_path: Path,
        time_ratio: float,
        new_duration: float
    ) -> bool:
        """
        TextGrid 시간 동기화

        Args:
            textgrid_path: 입력 TextGrid 파일 경로
            output_path: 출력 파일 경로
            time_ratio: 시간 조정 비율
            new_duration: 새로운 전체 길이

        Returns:
            성공 여부
        """
        try:
            # TextGrid 파일 읽기
            tg_obj = tg.TextGrid.fromFile(str(textgrid_path))

            # 전체 시간 조정
            tg_obj.maxTime = new_duration

            # 각 tier 처리
            for tier in tg_obj.tiers:
                if hasattr(tier, 'intervals'):  # IntervalTier
                    for interval in tier.intervals:
                        interval.minTime *= time_ratio
                        interval.maxTime *= time_ratio

                        # 경계 조정
                        if interval.maxTime > new_duration:
                            interval.maxTime = new_duration

                elif hasattr(tier, 'points'):  # PointTier
                    for point in tier.points:
                        point.time *= time_ratio

                        # 경계 체크
                        if point.time > new_duration:
                            tier.points.remove(point)

            # 저장
            tg_obj.write(str(output_path))

            logger.info(
                f"TextGrid 동기화 완료: {textgrid_path.name} "
                f"(비율: {time_ratio:.2%}, 새 길이: {new_duration:.2f}초)"
            )

            return True

        except Exception as e:
            logger.error(f"TextGrid 동기화 실패: {str(e)}")
            return False

    @handle_errors(context="adjust_textgrid_timing")
    def adjust_textgrid_timing(
        self,
        textgrid_path: Path,
        original_duration: float,
        new_duration: float,
        output_path: Optional[Path] = None
    ) -> Optional[Path]:
        """
        TextGrid 타이밍 조정

        Args:
            textgrid_path: TextGrid 파일 경로
            original_duration: 원본 오디오 길이
            new_duration: 새 오디오 길이
            output_path: 출력 경로

        Returns:
            조정된 TextGrid 파일 경로
        """
        if output_path is None:
            output_path = textgrid_path.parent / f"{textgrid_path.stem}_adjusted.TextGrid"

        # 시간 비율 계산
        time_ratio = new_duration / original_duration if original_duration > 0 else 1.0

        # 동기화 실행
        success = self.synchronize_textgrid(
            textgrid_path,
            output_path,
            time_ratio,
            new_duration
        )

        return output_path if success else None


class AutomationProcessor:
    """자동화 처리 클래스"""

    def __init__(self):
        """초기화"""
        self.audio_normalizer = AudioNormalizer()
        self.textgrid_sync = TextGridSynchronizer()
        self.file_handler = file_handler
        logger.info("AutomationProcessor 초기화 완료")

    @handle_errors(context="process_file_pair")
    @log_execution_time
    def process_file_pair(
        self,
        audio_path: Path,
        textgrid_path: Optional[Path] = None,
        output_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        오디오와 TextGrid 파일 쌍 처리

        Args:
            audio_path: 오디오 파일 경로
            textgrid_path: TextGrid 파일 경로
            output_dir: 출력 디렉토리

        Returns:
            처리 결과
        """
        audio_path = Path(audio_path)

        # 출력 디렉토리 설정
        if output_dir is None:
            output_dir = audio_path.parent / "processed"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        result = {
            'audio_path': str(audio_path),
            'textgrid_path': str(textgrid_path) if textgrid_path else None,
            'output_dir': str(output_dir)
        }

        try:
            # 원본 오디오 정보
            original_info = self.file_handler.get_audio_info(audio_path)
            original_duration = original_info['duration']

            # 오디오 처리
            output_audio = output_dir / f"{audio_path.stem}_processed.wav"
            audio_result = self.audio_normalizer.process_audio_file(
                audio_path,
                output_audio
            )
            result['audio_result'] = audio_result

            # 처리된 오디오 정보
            processed_info = self.file_handler.get_audio_info(output_audio)
            new_duration = processed_info['duration']

            # TextGrid 동기화 (있는 경우)
            if textgrid_path and textgrid_path.exists():
                output_textgrid = output_dir / f"{audio_path.stem}_processed.TextGrid"

                adjusted_path = self.textgrid_sync.adjust_textgrid_timing(
                    textgrid_path,
                    original_duration,
                    new_duration,
                    output_textgrid
                )

                result['textgrid_result'] = {
                    'output_path': str(adjusted_path) if adjusted_path else None,
                    'time_ratio': new_duration / original_duration,
                    'success': adjusted_path is not None
                }

            result['success'] = True
            logger.info(f"파일 쌍 처리 완료: {audio_path.name}")

        except Exception as e:
            result['success'] = False
            result['error'] = str(e)
            logger.error(f"파일 쌍 처리 실패: {str(e)}")

        return result

    @handle_errors(context="process_directory")
    @log_execution_time
    def process_directory(
        self,
        input_dir: Path,
        output_dir: Optional[Path] = None,
        pattern: str = "*.wav"
    ) -> List[Dict[str, Any]]:
        """
        디렉토리 일괄 처리

        Args:
            input_dir: 입력 디렉토리
            output_dir: 출력 디렉토리
            pattern: 파일 패턴

        Returns:
            처리 결과 리스트
        """
        input_dir = Path(input_dir)

        if not input_dir.exists():
            raise FileNotFoundError(f"디렉토리를 찾을 수 없습니다: {input_dir}")

        # 출력 디렉토리 설정
        if output_dir is None:
            output_dir = input_dir / "processed"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 처리할 파일 찾기
        audio_files = list(input_dir.glob(pattern))

        if not audio_files:
            logger.warning(f"처리할 파일이 없습니다: {input_dir}/{pattern}")
            return []

        results = []

        for audio_path in audio_files:
            # 대응하는 TextGrid 찾기
            textgrid_path = audio_path.with_suffix('.TextGrid')
            if not textgrid_path.exists():
                textgrid_path = None

            # 처리
            result = self.process_file_pair(
                audio_path,
                textgrid_path,
                output_dir
            )
            results.append(result)

        # 요약
        success_count = sum(1 for r in results if r.get('success', False))
        logger.info(
            f"디렉토리 처리 완료: {success_count}/{len(results)} 파일 성공"
        )

        return results


# 메인 실행 코드
if __name__ == "__main__":
    # 로깅 설정
    from utils import LoggerConfig
    LoggerConfig.setup()

    # 테스트 실행
    processor = AutomationProcessor()

    # 참조 파일 디렉토리 처리
    if settings.REFERENCE_FILES_PATH.exists():
        logger.info("참조 파일 처리 시작...")
        results = processor.process_directory(
            settings.REFERENCE_FILES_PATH,
            settings.REFERENCE_FILES_PATH / "normalized"
        )

        # 결과 출력
        for result in results:
            if result['success']:
                logger.info(f"✓ {Path(result['audio_path']).name}")
            else:
                logger.error(f"✗ {Path(result['audio_path']).name}: {result.get('error', 'Unknown error')}")
    else:
        logger.error(f"참조 파일 디렉토리가 없습니다: {settings.REFERENCE_FILES_PATH}")