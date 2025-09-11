"""
환경 감지 및 설정 유틸리티
Pure Nix vs Ubuntu 환경을 자동 감지하고 적절한 설정 적용
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class EnvironmentDetector:
    """환경 감지 및 설정 클래스"""
    
    def __init__(self):
        self._environment = None
        self._python_path = None
        self._is_replit = None
        
    @property
    def environment(self) -> str:
        """현재 환경 감지: 'pure_nix', 'ubuntu', 'hybrid'"""
        if self._environment is None:
            self._environment = self._detect_environment()
        return self._environment
    
    @property
    def is_pure_nix(self) -> bool:
        """Pure Nix 환경 여부"""
        return self.environment == 'pure_nix'
    
    @property
    def is_ubuntu(self) -> bool:
        """우분투 환경 여부"""
        return self.environment == 'ubuntu'
    
    @property
    def is_hybrid(self) -> bool:
        """하이브리드 환경 여부"""
        return self.environment == 'hybrid'
    
    @property
    def is_replit(self) -> bool:
        """Replit 환경 여부"""
        if self._is_replit is None:
            self._is_replit = (
                os.getenv('REPL_ID') is not None or
                os.getenv('REPLIT_DB_URL') is not None or
                '/home/runner' in os.getcwd()
            )
        return self._is_replit
    
    def _detect_environment(self) -> str:
        """환경 자동 감지"""
        try:
            # Python 실행 파일 경로 확인
            python_path = sys.executable
            self._python_path = python_path
            
            # Nix Store 경로인지 확인
            is_nix_python = '/nix/store' in python_path
            
            # 시스템 정보 확인
            has_ubuntu_release = Path('/etc/lsb-release').exists()
            has_ubuntu_version = Path('/etc/os-release').exists()
            
            # Poetry/pip 의존성 확인
            has_poetry = self._check_poetry_available()
            has_system_pip = self._check_system_pip()
            
            # 환경 변수 확인
            has_nix_path = os.getenv('NIX_PATH') is not None
            has_nix_profiles = '/nix/var/nix/profiles' in os.getenv('PATH', '')
            
            logger.info(f"환경 감지 정보:")
            logger.info(f"  Python 경로: {python_path}")
            logger.info(f"  Nix Python: {is_nix_python}")
            logger.info(f"  Ubuntu 릴리즈: {has_ubuntu_release}")
            logger.info(f"  Poetry 사용 가능: {has_poetry}")
            logger.info(f"  시스템 pip: {has_system_pip}")
            logger.info(f"  Replit 환경: {self.is_replit}")
            
            # 환경 결정 로직
            if is_nix_python and not has_poetry and self.is_replit:
                return 'pure_nix'
            elif has_ubuntu_release and has_system_pip and not is_nix_python:
                return 'ubuntu'
            else:
                return 'hybrid'
                
        except Exception as e:
            logger.warning(f"환경 감지 실패: {e}")
            return 'hybrid'  # 기본값
    
    def _check_poetry_available(self) -> bool:
        """Poetry 사용 가능 여부 확인"""
        try:
            subprocess.run(['poetry', '--version'], 
                         capture_output=True, check=True, timeout=5)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def _check_system_pip(self) -> bool:
        """시스템 pip 사용 가능 여부 확인"""
        try:
            result = subprocess.run(['which', 'pip'], 
                                  capture_output=True, text=True, timeout=5)
            pip_path = result.stdout.strip()
            return pip_path and '/nix/store' not in pip_path
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def get_library_paths(self) -> Dict[str, str]:
        """환경에 맞는 라이브러리 경로 반환"""
        paths = {}
        
        if self.is_pure_nix:
            # Pure Nix: RPATH에 의존하므로 특별한 라이브러리 경로 불필요
            paths['strategy'] = 'rpath_only'
            paths['clear_ld_library_path'] = True
            
        elif self.is_ubuntu:
            # Ubuntu: 시스템 라이브러리 경로 사용
            paths['strategy'] = 'system_libs'
            paths['ld_library_path'] = [
                '/usr/lib/x86_64-linux-gnu',
                '/usr/local/lib',
                '/lib/x86_64-linux-gnu'
            ]
            
        else:
            # Hybrid: 안전한 혼합 접근
            paths['strategy'] = 'hybrid'
            paths['ld_library_path'] = ['/usr/lib/x86_64-linux-gnu']
            
        return paths
    
    def get_stt_preferences(self) -> Dict[str, bool]:
        """환경에 맞는 STT 엔진 우선순위"""
        if self.is_pure_nix:
            return {
                'prefer_faster_whisper': True,
                'fallback_to_openai_whisper': True,
                'use_system_whisper': False
            }
        else:
            return {
                'prefer_faster_whisper': False,
                'fallback_to_openai_whisper': True,
                'use_system_whisper': True
            }
    
    def get_python_command(self) -> str:
        """환경에 맞는 Python 실행 명령"""
        if self.is_pure_nix:
            return "$(command -v python)"
        else:
            return "python3"
    
    def log_environment_info(self):
        """환경 정보 로깅"""
        logger.info("=" * 50)
        logger.info("ToneBridge 환경 설정")
        logger.info("=" * 50)
        logger.info(f"감지된 환경: {self.environment}")
        logger.info(f"Python 경로: {self._python_path}")
        logger.info(f"Replit 환경: {self.is_replit}")
        
        lib_paths = self.get_library_paths()
        logger.info(f"라이브러리 전략: {lib_paths['strategy']}")
        
        stt_prefs = self.get_stt_preferences()
        logger.info(f"faster-whisper 우선: {stt_prefs['prefer_faster_whisper']}")
        
        logger.info("=" * 50)


# 전역 환경 감지 인스턴스
env_detector = EnvironmentDetector()


def get_environment() -> str:
    """현재 환경 반환"""
    return env_detector.environment


def is_pure_nix() -> bool:
    """Pure Nix 환경 여부"""
    return env_detector.is_pure_nix


def is_ubuntu() -> bool:
    """우분투 환경 여부"""
    return env_detector.is_ubuntu


def get_library_strategy() -> Dict[str, str]:
    """라이브러리 로딩 전략 반환"""
    return env_detector.get_library_paths()


def get_stt_config() -> Dict[str, bool]:
    """STT 설정 반환"""
    return env_detector.get_stt_preferences()


def log_environment():
    """환경 정보 로깅"""
    env_detector.log_environment_info()