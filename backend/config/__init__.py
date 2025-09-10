"""
ToneBridge 설정 모듈
중앙화된 설정 관리 시스템
"""

from .settings import Settings, settings, validate_settings, print_settings

__version__ = "1.0.0"
__all__ = ["Settings", "settings", "validate_settings", "print_settings"]

# 모듈 임포트 시 자동으로 설정 검증
import logging

logger = logging.getLogger(__name__)

# 설정 검증 실행
warnings = validate_settings()
if warnings:
  for warning in warnings:
    logger.warning(warning)

# 설정 정보 로깅 (디버그 모드에서만)
if settings.DEBUG:
  logger.info("ToneBridge 설정 모듈 초기화 완료")
  logger.debug(f"기본 디렉토리: {settings.BASE_DIR}")
  logger.debug(f"참조 파일 경로: {settings.REFERENCE_FILES_PATH}")
  logger.debug(f"업로드 경로: {settings.UPLOAD_FILES_PATH}")
