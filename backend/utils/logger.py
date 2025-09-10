"""
통합 로깅 시스템
모든 로그를 중앙화하여 관리하고 다양한 출력 옵션 제공
"""

import logging
import logging.handlers
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Union
import traceback
from functools import wraps
import time

from config import settings

# ========== 커스텀 포매터 ==========


class ColoredFormatter(logging.Formatter):
    """컬러 출력을 지원하는 포매터"""

    # ANSI 색상 코드
    COLORS = {
        'DEBUG': '\033[36m',  # Cyan
        'INFO': '\033[32m',  # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',  # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        # 로그 레벨에 따른 색상 적용
        if sys.stdout.isatty() and not sys.platform.startswith('win'):
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"

        return super().format(record)


class JSONFormatter(logging.Formatter):
    """JSON 형식으로 로그를 출력하는 포매터"""

    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # 추가 필드가 있으면 포함
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data

        # 예외 정보가 있으면 포함
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


# ========== 커스텀 핸들러 ==========


class RotatingFileHandlerWithEncoding(logging.handlers.RotatingFileHandler):
    """UTF-8 인코딩을 지원하는 로테이팅 파일 핸들러"""

    def __init__(self,
                 filename,
                 mode='a',
                 maxBytes=0,
                 backupCount=0,
                 encoding='utf-8',
                 delay=False):
        super().__init__(filename, mode, maxBytes, backupCount, encoding,
                         delay)


# ========== 로거 설정 클래스 ==========


class LoggerConfig:
    """로거 설정 관리 클래스"""

    _loggers: Dict[str, logging.Logger] = {}
    _initialized: bool = False

    @classmethod
    def setup(cls, force: bool = False):
        """
        로깅 시스템 설정

        Args:
            force: 강제 재설정 여부
        """
        if cls._initialized and not force:
            return

        # 루트 로거 설정
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

        # 기존 핸들러 제거
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # 콘솔 핸들러 추가
        console_handler = cls._create_console_handler()
        root_logger.addHandler(console_handler)

        # 파일 핸들러 추가 (설정에 따라)
        if settings.ENABLE_FILE_LOGGING:
            file_handler = cls._create_file_handler()
            root_logger.addHandler(file_handler)

        # 서드파티 라이브러리 로그 레벨 조정
        cls._configure_third_party_loggers()

        cls._initialized = True

        # 설정 완료 로그
        logger = logging.getLogger(__name__)
        logger.info("로깅 시스템 초기화 완료")
        logger.debug(f"로그 레벨: {settings.LOG_LEVEL}")
        logger.debug(
            f"로그 파일: {settings.LOG_FILE if settings.ENABLE_FILE_LOGGING else 'Disabled'}"
        )

    @classmethod
    def _create_console_handler(cls) -> logging.StreamHandler:
        """콘솔 핸들러 생성"""
        handler = logging.StreamHandler(sys.stdout)

        # 디버그 모드에서는 컬러 포매터 사용
        if settings.DEBUG:
            formatter = ColoredFormatter(settings.LOG_FORMAT)
        else:
            formatter = logging.Formatter(settings.LOG_FORMAT)

        handler.setFormatter(formatter)
        return handler

    @classmethod
    def _create_file_handler(cls) -> RotatingFileHandlerWithEncoding:
        """파일 핸들러 생성"""
        # 로그 디렉토리 생성
        log_dir = settings.LOG_FILE.parent
        log_dir.mkdir(parents=True, exist_ok=True)

        # 로테이팅 파일 핸들러 (10MB, 5개 백업)
        handler = RotatingFileHandlerWithEncoding(
            filename=str(settings.LOG_FILE),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8')

        # JSON 포매터 사용 (파일에는 구조화된 로그 저장)
        formatter = JSONFormatter(
        ) if not settings.DEBUG else logging.Formatter(settings.LOG_FORMAT)
        handler.setFormatter(formatter)

        return handler

    @classmethod
    def _configure_third_party_loggers(cls):
        """서드파티 라이브러리 로거 설정"""
        # 너무 자세한 로그를 출력하는 라이브러리들의 레벨 조정
        noisy_loggers = [
            'urllib3', 'asyncio', 'multipart', 'uvicorn.access', 'watchfiles',
            'httpx', 'httpcore'
        ]

        for logger_name in noisy_loggers:
            logging.getLogger(logger_name).setLevel(logging.WARNING)

        # 중요한 라이브러리는 INFO 레벨 유지
        important_loggers = ['fastapi', 'uvicorn.error', 'sqlalchemy.engine']

        for logger_name in important_loggers:
            logging.getLogger(logger_name).setLevel(logging.INFO)

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        로거 인스턴스 가져오기

        Args:
            name: 로거 이름

        Returns:
            Logger 인스턴스
        """
        if name not in cls._loggers:
            cls._loggers[name] = logging.getLogger(name)
        return cls._loggers[name]


# ========== 로깅 유틸리티 함수 ==========


def get_logger(name: str = None) -> logging.Logger:
    """
    로거 인스턴스 가져오기

    Args:
        name: 로거 이름 (None이면 호출한 모듈 이름 사용)

    Returns:
        Logger 인스턴스
    """
    if name is None:
        import inspect
        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get('__name__', __name__)
        else:
            name = __name__

    return LoggerConfig.get_logger(name)


def log_execution_time(func=None,
                       *,
                       logger_name: str = None,
                       level: str = 'DEBUG'):
    """
    함수 실행 시간을 로깅하는 데코레이터

    Args:
        func: 데코레이팅할 함수
        logger_name: 로거 이름
        level: 로그 레벨
    """

    def decorator(f):

        @wraps(f)
        def wrapper(*args, **kwargs):
            logger = get_logger(logger_name or f.__module__)
            start_time = time.time()

            try:
                result = f(*args, **kwargs)
                execution_time = time.time() - start_time

                log_func = getattr(logger, level.lower(), logger.debug)
                log_func(f"{f.__name__} 실행 완료 (소요 시간: {execution_time:.3f}초)")

                return result

            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(
                    f"{f.__name__} 실행 실패 (소요 시간: {execution_time:.3f}초): {str(e)}"
                )
                raise

        return wrapper

    if func is None:
        return decorator
    else:
        return decorator(func)


def log_function_call(func=None,
                      *,
                      logger_name: str = None,
                      level: str = 'DEBUG',
                      log_args: bool = True,
                      log_result: bool = False):
    """
    함수 호출을 로깅하는 데코레이터

    Args:
        func: 데코레이팅할 함수
        logger_name: 로거 이름
        level: 로그 레벨
        log_args: 인자 로깅 여부
        log_result: 결과 로깅 여부
    """

    def decorator(f):

        @wraps(f)
        def wrapper(*args, **kwargs):
            logger = get_logger(logger_name or f.__module__)
            log_func = getattr(logger, level.lower(), logger.debug)

            # 함수 호출 로깅
            if log_args:
                log_func(f"{f.__name__} 호출: args={args}, kwargs={kwargs}")
            else:
                log_func(f"{f.__name__} 호출")

            try:
                result = f(*args, **kwargs)

                # 결과 로깅
                if log_result:
                    log_func(f"{f.__name__} 결과: {result}")

                return result

            except Exception as e:
                logger.error(f"{f.__name__} 실행 중 에러: {str(e)}")
                raise

        return wrapper

    if func is None:
        return decorator
    else:
        return decorator(func)


# ========== 구조화된 로깅 ==========


class StructuredLogger:
    """구조화된 로깅을 위한 래퍼 클래스"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def log(self, level: str, message: str, **kwargs):
        """
        구조화된 로그 출력

        Args:
            level: 로그 레벨
            message: 로그 메시지
            **kwargs: 추가 데이터
        """
        log_func = getattr(self.logger, level.lower(), self.logger.info)

        # extra 데이터 준비
        extra = {'extra_data': kwargs} if kwargs else {}

        log_func(message, extra=extra)

    def debug(self, message: str, **kwargs):
        """DEBUG 레벨 로그"""
        self.log('DEBUG', message, **kwargs)

    def info(self, message: str, **kwargs):
        """INFO 레벨 로그"""
        self.log('INFO', message, **kwargs)

    def warning(self, message: str, **kwargs):
        """WARNING 레벨 로그"""
        self.log('WARNING', message, **kwargs)

    def error(self, message: str, **kwargs):
        """ERROR 레벨 로그"""
        self.log('ERROR', message, **kwargs)

    def critical(self, message: str, **kwargs):
        """CRITICAL 레벨 로그"""
        self.log('CRITICAL', message, **kwargs)


# ========== 성능 모니터링 로거 ==========


class PerformanceLogger:
    """성능 모니터링을 위한 로거"""

    def __init__(self, logger_name: str = "performance"):
        self.logger = get_logger(logger_name)
        self.metrics: Dict[str, list] = {}

    def log_metric(self,
                   name: str,
                   value: float,
                   unit: str = "",
                   tags: Optional[Dict[str, Any]] = None):
        """
        성능 메트릭 로깅

        Args:
            name: 메트릭 이름
            value: 메트릭 값
            unit: 단위
            tags: 태그
        """
        # 메트릭 저장
        if name not in self.metrics:
            self.metrics[name] = []

        metric_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'value': value,
            'unit': unit,
            'tags': tags or {}
        }

        self.metrics[name].append(metric_data)

        # 로그 출력
        self.logger.info(f"Metric: {name}={value}{unit}",
                         extra={'extra_data': metric_data})

    def get_metrics_summary(self, name: str) -> Dict[str, Any]:
        """
        메트릭 요약 정보 가져오기

        Args:
            name: 메트릭 이름

        Returns:
            요약 정보
        """
        if name not in self.metrics:
            return {}

        values = [m['value'] for m in self.metrics[name]]

        if not values:
            return {}

        import statistics

        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'mean': statistics.mean(values),
            'median': statistics.median(values),
            'stdev': statistics.stdev(values) if len(values) > 1 else 0
        }


# ========== 감사 로거 ==========


class AuditLogger:
    """감사(Audit) 로깅을 위한 클래스"""

    def __init__(self, logger_name: str = "audit"):
        self.logger = get_logger(logger_name)

    def log_action(self,
                   action: str,
                   user: Optional[str] = None,
                   target: Optional[str] = None,
                   result: str = "success",
                   details: Optional[Dict[str, Any]] = None):
        """
        사용자 액션 로깅

        Args:
            action: 액션 이름
            user: 사용자 식별자
            target: 대상 객체
            result: 결과 (success/failure)
            details: 추가 상세 정보
        """
        audit_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'action': action,
            'user': user or 'anonymous',
            'target': target,
            'result': result,
            'details': details or {}
        }

        self.logger.info(
            f"AUDIT: {action} by {user or 'anonymous'} on {target} - {result}",
            extra={'extra_data': audit_data})


# ========== 전역 로거 인스턴스 ==========

# 로깅 시스템 초기화
LoggerConfig.setup()

# 기본 로거들
logger = get_logger(__name__)
structured_logger = StructuredLogger(logger)
performance_logger = PerformanceLogger()
audit_logger = AuditLogger()

# ========== 유틸리티 함수 ==========


def log_exception(exc: Exception, context: str = None):
    """
    예외 로깅

    Args:
        exc: 예외 객체
        context: 컨텍스트 정보
    """
    logger = get_logger(context or __name__)
    logger.error(f"예외 발생: {type(exc).__name__}: {str(exc)}", exc_info=True)


def log_api_request(method: str,
                    path: str,
                    params: Optional[Dict] = None,
                    body: Optional[Any] = None,
                    user: Optional[str] = None):
    """
    API 요청 로깅

    Args:
        method: HTTP 메서드
        path: 요청 경로
        params: 쿼리 파라미터
        body: 요청 본문
        user: 사용자 식별자
    """
    request_data = {
        'method': method,
        'path': path,
        'params': params or {},
        'user': user or 'anonymous',
        'timestamp': datetime.utcnow().isoformat()
    }

    # 민감한 정보 제거
    if body and isinstance(body, dict):
        safe_body = {
            k: '***' if 'password' in k.lower() or 'token' in k.lower() else v
            for k, v in body.items()
        }
        request_data['body'] = safe_body

    structured_logger.info(f"API Request: {method} {path}", **request_data)


def log_api_response(method: str,
                     path: str,
                     status_code: int,
                     response_time: float,
                     user: Optional[str] = None):
    """
    API 응답 로깅

    Args:
        method: HTTP 메서드
        path: 요청 경로
        status_code: 상태 코드
        response_time: 응답 시간
        user: 사용자 식별자
    """
    response_data = {
        'method': method,
        'path': path,
        'status_code': status_code,
        'response_time_ms': round(response_time * 1000, 2),
        'user': user or 'anonymous',
        'timestamp': datetime.utcnow().isoformat()
    }

    level = 'INFO' if status_code < 400 else 'WARNING' if status_code < 500 else 'ERROR'
    structured_logger.log(
        level,
        f"API Response: {method} {path} - {status_code} ({response_time:.3f}s)",
        **response_data)


# ========== 로그 정리 유틸리티 ==========


def cleanup_old_logs(days: int = 30):
    """
    오래된 로그 파일 정리

    Args:
        days: 보관 일수
    """
    import time
    from datetime import timedelta

    if not settings.LOG_FILE.exists():
        return

    log_dir = settings.LOG_FILE.parent
    cutoff_time = time.time() - (days * 24 * 60 * 60)

    for log_file in log_dir.glob("*.log*"):
        if log_file.stat().st_mtime < cutoff_time:
            try:
                log_file.unlink()
                logger.info(f"오래된 로그 파일 삭제: {log_file}")
            except Exception as e:
                logger.error(f"로그 파일 삭제 실패: {log_file}, 에러: {e}")
