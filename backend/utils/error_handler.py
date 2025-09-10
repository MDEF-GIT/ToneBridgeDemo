"""
통합 에러 처리 시스템
모든 예외 처리를 표준화하고 일관된 에러 응답 제공
"""

import sys
import traceback
import logging
from typing import Optional, Dict, Any, Union
from datetime import datetime
from pathlib import Path
import json

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

from config import settings

logger = logging.getLogger(__name__)


class ToneBridgeError(Exception):
    """ToneBridge 기본 에러 클래스"""

    def __init__(self,
                 message: str,
                 error_code: str = "UNKNOWN_ERROR",
                 status_code: int = 500,
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """에러를 딕셔너리로 변환"""
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details,
                "timestamp": self.timestamp,
                "status_code": self.status_code
            }
        }

    def to_json(self) -> str:
        """에러를 JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# ========== 커스텀 에러 클래스 ==========


class FileNotFoundError(ToneBridgeError):
    """파일을 찾을 수 없을 때"""

    def __init__(self,
                 file_path: Union[str, Path],
                 details: Optional[Dict] = None):
        super().__init__(message=f"파일을 찾을 수 없습니다: {file_path}",
                         error_code="FILE_NOT_FOUND",
                         status_code=404,
                         details=details)


class InvalidFileFormatError(ToneBridgeError):
    """잘못된 파일 형식"""

    def __init__(self,
                 file_path: Union[str, Path],
                 expected_format: str,
                 details: Optional[Dict] = None):
        super().__init__(message=f"잘못된 파일 형식입니다. 예상: {expected_format}",
                         error_code="INVALID_FILE_FORMAT",
                         status_code=400,
                         details={
                             "file": str(file_path),
                             "expected_format": expected_format,
                             **(details or {})
                         })


class AudioProcessingError(ToneBridgeError):
    """오디오 처리 에러"""

    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message=f"오디오 처리 중 오류 발생: {message}",
                         error_code="AUDIO_PROCESSING_ERROR",
                         status_code=500,
                         details=details)


class STTError(ToneBridgeError):
    """STT 처리 에러"""

    def __init__(self,
                 engine: str,
                 message: str,
                 details: Optional[Dict] = None):
        super().__init__(message=f"STT 처리 실패 ({engine}): {message}",
                         error_code="STT_ERROR",
                         status_code=500,
                         details={
                             "engine": engine,
                             **(details or {})
                         })


class TextGridError(ToneBridgeError):
    """TextGrid 처리 에러"""

    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message=f"TextGrid 처리 오류: {message}",
                         error_code="TEXTGRID_ERROR",
                         status_code=500,
                         details=details)


class ValidationError(ToneBridgeError):
    """데이터 검증 에러"""

    def __init__(self,
                 field: str,
                 message: str,
                 details: Optional[Dict] = None):
        super().__init__(message=f"검증 실패 ({field}): {message}",
                         error_code="VALIDATION_ERROR",
                         status_code=422,
                         details={
                             "field": field,
                             **(details or {})
                         })


class ConfigurationError(ToneBridgeError):
    """설정 에러"""

    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message=f"설정 오류: {message}",
                         error_code="CONFIGURATION_ERROR",
                         status_code=500,
                         details=details)


class RateLimitError(ToneBridgeError):
    """요청 제한 에러"""

    def __init__(self,
                 message: str = "너무 많은 요청입니다",
                 details: Optional[Dict] = None):
        super().__init__(message=message,
                         error_code="RATE_LIMIT_EXCEEDED",
                         status_code=429,
                         details=details)


class AuthenticationError(ToneBridgeError):
    """인증 에러"""

    def __init__(self,
                 message: str = "인증이 필요합니다",
                 details: Optional[Dict] = None):
        super().__init__(message=message,
                         error_code="AUTHENTICATION_REQUIRED",
                         status_code=401,
                         details=details)


class AuthorizationError(ToneBridgeError):
    """권한 에러"""

    def __init__(self,
                 message: str = "권한이 없습니다",
                 details: Optional[Dict] = None):
        super().__init__(message=message,
                         error_code="AUTHORIZATION_FAILED",
                         status_code=403,
                         details=details)


# ========== 에러 핸들러 클래스 ==========


class ErrorHandler:
    """통합 에러 처리 클래스"""

    @staticmethod
    def handle_exception(exception: Exception,
                         context: Optional[str] = None,
                         log_traceback: bool = True) -> Dict[str, Any]:
        """
        예외 처리 및 로깅

        Args:
            exception: 처리할 예외
            context: 에러 발생 컨텍스트
            log_traceback: 트레이스백 로깅 여부

        Returns:
            에러 응답 딕셔너리
        """
        # ToneBridge 커스텀 에러인 경우
        if isinstance(exception, ToneBridgeError):
            logger.error(
                f"[{context or 'Unknown'}] {exception.error_code}: {exception.message}"
            )
            if exception.details:
                logger.error(f"Details: {exception.details}")
            return exception.to_dict()

        # FastAPI HTTPException인 경우
        elif isinstance(exception, HTTPException):
            error_dict = {
                "error": {
                    "code": "HTTP_ERROR",
                    "message": exception.detail,
                    "status_code": exception.status_code,
                    "timestamp": datetime.now().isoformat()
                }
            }
            logger.error(
                f"[{context or 'Unknown'}] HTTP {exception.status_code}: {exception.detail}"
            )
            return error_dict

        # 일반 Python 예외인 경우
        else:
            error_message = str(exception)
            error_type = type(exception).__name__

            error_dict = {
                "error": {
                    "code": "INTERNAL_ERROR",
                    "type": error_type,
                    "message": error_message,
                    "status_code": 500,
                    "timestamp": datetime.now().isoformat()
                }
            }

            # 디버그 모드에서는 트레이스백 포함
            if settings.DEBUG and log_traceback:
                error_dict["error"]["traceback"] = traceback.format_exc()

            logger.error(
                f"[{context or 'Unknown'}] {error_type}: {error_message}")
            if log_traceback:
                logger.error(f"Traceback:\n{traceback.format_exc()}")

            return error_dict

    @staticmethod
    def handle_api_error(exception: Exception,
                         context: Optional[str] = None) -> JSONResponse:
        """
        API 에러 처리 (FastAPI용)

        Args:
            exception: 처리할 예외
            context: 에러 발생 컨텍스트

        Returns:
            JSONResponse 객체
        """
        error_dict = ErrorHandler.handle_exception(exception, context)
        status_code = error_dict["error"].get("status_code", 500)

        return JSONResponse(status_code=status_code, content=error_dict)

    @staticmethod
    def log_error(message: str,
                  error: Optional[Exception] = None,
                  level: str = "error",
                  context: Optional[str] = None,
                  extra_data: Optional[Dict[str, Any]] = None):
        """
        에러 로깅

        Args:
            message: 로그 메시지
            error: 예외 객체
            level: 로그 레벨
            context: 컨텍스트
            extra_data: 추가 데이터
        """
        log_message = f"[{context or 'Unknown'}] {message}"

        if extra_data:
            log_message += f" | Data: {json.dumps(extra_data, ensure_ascii=False)}"

        if error:
            log_message += f" | Error: {str(error)}"

        # 로그 레벨에 따라 로깅
        log_func = getattr(logger, level.lower(), logger.error)
        log_func(log_message)

        # 디버그 모드에서는 트레이스백도 로깅
        if settings.DEBUG and error:
            logger.debug(f"Traceback:\n{traceback.format_exc()}")

    @staticmethod
    def create_error_response(
            message: str,
            error_code: str = "ERROR",
            status_code: int = 500,
            details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        에러 응답 생성

        Args:
            message: 에러 메시지
            error_code: 에러 코드
            status_code: HTTP 상태 코드
            details: 추가 상세 정보

        Returns:
            에러 응답 딕셔너리
        """
        return {
            "error": {
                "code": error_code,
                "message": message,
                "status_code": status_code,
                "details": details or {},
                "timestamp": datetime.now().isoformat()
            }
        }

    @staticmethod
    def wrap_safe_execution(func,
                            context: str,
                            default_return=None,
                            raise_on_error: bool = False):
        """
        함수 실행을 안전하게 래핑

        Args:
            func: 실행할 함수
            context: 실행 컨텍스트
            default_return: 에러 시 기본 반환값
            raise_on_error: 에러 시 예외 발생 여부

        Returns:
            함수 실행 결과 또는 기본값
        """
        try:
            return func()
        except Exception as e:
            ErrorHandler.log_error(
                f"함수 실행 실패: {func.__name__ if hasattr(func, '__name__') else 'unknown'}",
                error=e,
                context=context)

            if raise_on_error:
                raise

            return default_return


# ========== 데코레이터 ==========


def handle_errors(context: Optional[str] = None,
                  default_return=None,
                  raise_on_error: bool = True,
                  log_args: bool = False):
    """
    에러 처리 데코레이터

    Args:
        context: 실행 컨텍스트
        default_return: 에러 시 기본 반환값
        raise_on_error: 에러 시 예외 발생 여부
        log_args: 함수 인자 로깅 여부
    """

    def decorator(func):

        def wrapper(*args, **kwargs):
            func_context = context or func.__name__

            try:
                if log_args and settings.DEBUG:
                    logger.debug(
                        f"[{func_context}] Called with args={args}, kwargs={kwargs}"
                    )

                result = func(*args, **kwargs)

                if settings.DEBUG:
                    logger.debug(f"[{func_context}] Completed successfully")

                return result

            except Exception as e:
                ErrorHandler.log_error(f"함수 실행 실패",
                                       error=e,
                                       context=func_context)

                if raise_on_error:
                    raise

                return default_return

        return wrapper

    return decorator


# ========== 에러 복구 유틸리티 ==========


class ErrorRecovery:
    """에러 복구 유틸리티"""

    @staticmethod
    def retry_on_error(func,
                       max_retries: int = 3,
                       delay: float = 1.0,
                       backoff: float = 2.0,
                       exceptions: tuple = (Exception, )):
        """
        에러 시 재시도

        Args:
            func: 실행할 함수
            max_retries: 최대 재시도 횟수
            delay: 재시도 간 대기 시간
            backoff: 대기 시간 증가율
            exceptions: 재시도할 예외 타입들

        Returns:
            함수 실행 결과
        """
        import time

        last_exception = None
        current_delay = delay

        for attempt in range(max_retries + 1):
            try:
                return func()
            except exceptions as e:
                last_exception = e

                if attempt < max_retries:
                    logger.warning(
                        f"재시도 {attempt + 1}/{max_retries}: {str(e)}")
                    time.sleep(current_delay)
                    current_delay *= backoff
                else:
                    logger.error(f"최대 재시도 횟수 초과 ({max_retries}회): {str(e)}")

        if last_exception:
            raise last_exception

    @staticmethod
    def fallback_on_error(primary_func,
                          fallback_func,
                          exceptions: tuple = (Exception, )):
        """
        에러 시 대체 함수 실행

        Args:
            primary_func: 주 함수
            fallback_func: 대체 함수
            exceptions: 대체할 예외 타입들

        Returns:
            함수 실행 결과
        """
        try:
            return primary_func()
        except exceptions as e:
            logger.warning(f"주 함수 실패, 대체 함수 실행: {str(e)}")
            return fallback_func()


# ========== 전역 에러 핸들러 설정 ==========


def setup_global_error_handler():
    """전역 에러 핸들러 설정"""

    def global_exception_handler(exc_type, exc_value, exc_traceback):
        """전역 예외 처리"""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger.critical("처리되지 않은 예외 발생",
                        exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = global_exception_handler


# 모듈 임포트 시 전역 핸들러 설정
if settings.DEBUG:
    setup_global_error_handler()

# ========== FastAPI 에러 핸들러 ==========


async def http_exception_handler(request, exc: HTTPException):
    """FastAPI HTTP 예외 처리"""
    return ErrorHandler.handle_api_error(exc, context="HTTP")


async def validation_exception_handler(request, exc):
    """FastAPI 검증 예외 처리"""
    from fastapi.exceptions import RequestValidationError

    if isinstance(exc, RequestValidationError):
        errors = exc.errors()
        return JSONResponse(status_code=422,
                            content={
                                "error": {
                                    "code": "VALIDATION_ERROR",
                                    "message": "요청 데이터 검증 실패",
                                    "details": errors,
                                    "timestamp": datetime.now().isoformat()
                                }
                            })

    return ErrorHandler.handle_api_error(exc, context="Validation")


async def general_exception_handler(request, exc: Exception):
    """일반 예외 처리"""
    return ErrorHandler.handle_api_error(exc, context="General")


# 싱글톤 인스턴스
error_handler = ErrorHandler()
error_recovery = ErrorRecovery()
