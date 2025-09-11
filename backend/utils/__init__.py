"""
ToneBridge 유틸리티 모듈
파일 처리, 에러 처리, 로깅 등 공통 유틸리티 제공
"""

# 파일 처리
from .file_handler import (FileHandler, file_handler, read_textgrid,
                           read_audio, save_audio)

# 에러 처리
from .error_handler import (
    # 에러 클래스
    ToneBridgeError,
    FileNotFoundError,
    InvalidFileFormatError,
    AudioProcessingError,
    STTError,
    TextGridError,
    ValidationError,
    ConfigurationError,
    RateLimitError,
    AuthenticationError,
    AuthorizationError,

    # 핸들러
    ErrorHandler,
    error_handler,
    ErrorRecovery,
    error_recovery,

    # 데코레이터
    handle_errors,

    # FastAPI 핸들러
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler)

# 로깅
from .logger import (
    # 설정
    LoggerConfig,

    # 로거 가져오기
    get_logger,

    # 데코레이터
    log_execution_time,
    log_function_call,

    # 구조화된 로거
    StructuredLogger,
    structured_logger,

    # 특수 로거
    PerformanceLogger,
    performance_logger,
    AuditLogger,
    audit_logger,

    # 유틸리티 함수
    log_exception,
    log_api_request,
    log_api_response,
    cleanup_old_logs)

# 환경 감지
from .environment import (
    env_detector,
    get_environment,
    is_pure_nix,
    is_ubuntu,
    get_library_strategy,
    get_stt_config,
    log_environment
)

__version__ = "1.0.0"

__all__ = [
    # 파일 처리
    "FileHandler",
    "file_handler",
    "read_textgrid",
    "read_audio",
    "save_audio",

    # 에러 처리
    "ToneBridgeError",
    "FileNotFoundError",
    "InvalidFileFormatError",
    "AudioProcessingError",
    "STTError",
    "TextGridError",
    "ValidationError",
    "ConfigurationError",
    "RateLimitError",
    "AuthenticationError",
    "AuthorizationError",
    "ErrorHandler",
    "error_handler",
    "ErrorRecovery",
    "error_recovery",
    "handle_errors",
    "http_exception_handler",
    "validation_exception_handler",
    "general_exception_handler",

    # 로깅
    "LoggerConfig",
    "get_logger",
    "log_execution_time",
    "log_function_call",
    "StructuredLogger",
    "structured_logger",
    "PerformanceLogger",
    "performance_logger",
    "AuditLogger",
    "audit_logger",
    "log_exception",
    "log_api_request",
    "log_api_response",
    "cleanup_old_logs",

    # 환경 감지
    "env_detector",
    "get_environment", 
    "is_pure_nix",
    "is_ubuntu",
    "get_library_strategy",
    "get_stt_config",
    "log_environment"
]

# 모듈 초기화 시 로깅
import logging

logger = logging.getLogger(__name__)
logger.debug("유틸리티 모듈 초기화 완료")
