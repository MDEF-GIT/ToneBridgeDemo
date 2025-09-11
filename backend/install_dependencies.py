#!/usr/bin/env python3
"""
ToneBridge 의존성 설치 스크립트
Ubuntu, Pure Nix 환경 완전 호환
"""

import os
import sys
import subprocess
import platform
import importlib.util
from pathlib import Path


class ToneBridgeInstaller:
    def __init__(self):
        self.env_type = self.detect_environment()
        self.success_packages = []
        self.failed_packages = []

    def detect_environment(self):
        """환경 자동 감지"""
        if os.environ.get('NIX_PATH') or os.path.exists('/nix'):
            return 'nix'
        elif platform.system() == 'Linux':
            try:
                with open('/etc/os-release') as f:
                    content = f.read()
                    if 'ubuntu' in content.lower() or 'debian' in content.lower():
                        return 'ubuntu'
            except:
                pass
        return 'generic'

    def run_command(self, cmd, check=True, capture=True):
        """명령어 실행"""
        try:
            if capture:
                result = subprocess.run(cmd, shell=True, check=check, 
                                      capture_output=True, text=True)
                return result.stdout.strip()
            else:
                result = subprocess.run(cmd, shell=True, check=check)
                return result.returncode == 0
        except subprocess.CalledProcessError as e:
            if capture:
                return None
            return False

    def install_system_dependencies(self):
        """시스템 의존성 설치"""
        print(f"🔧 {self.env_type} 환경에서 시스템 의존성 설치 중...")
        
        if self.env_type == 'ubuntu':
            ubuntu_packages = [
                'python3-dev', 'python3-pip', 'python3-venv',
                'build-essential', 'pkg-config', 'libffi-dev', 'libssl-dev',
                'libasound2-dev', 'libportaudio2', 'portaudio19-dev',
                'libsndfile1-dev', 'libsamplerate0-dev', 'libfftw3-dev',
                'libblas-dev', 'liblapack-dev', 'gfortran',
                'openjdk-17-jdk', 'curl', 'wget', 'git'
            ]
            
            # 패키지 업데이트
            print("패키지 목록 업데이트 중...")
            if not self.run_command("sudo apt update", capture=False):
                print("❌ apt update 실패")
                return False
            
            # 패키지 설치
            packages_str = ' '.join(ubuntu_packages)
            print(f"Ubuntu 패키지 설치 중: {len(ubuntu_packages)}개")
            cmd = f"sudo apt install -y {packages_str}"
            if not self.run_command(cmd, capture=False):
                print("❌ 일부 Ubuntu 패키지 설치 실패")
                return False
            
            # Java 환경 설정
            java_home = "/usr/lib/jvm/java-17-openjdk-amd64"
            if os.path.exists(java_home):
                os.environ['JAVA_HOME'] = java_home
                print(f"✅ JAVA_HOME 설정: {java_home}")
        
        elif self.env_type == 'nix':
            print("✅ Nix 환경에서는 시스템 패키지가 자동 관리됩니다.")
        
        else:
            print("⚠️  일반 Linux 환경입니다. 수동 의존성 설치가 필요할 수 있습니다.")
        
        return True

    def install_package(self, package):
        """개별 패키지 설치"""
        try:
            print(f"  설치 중: {package}")
            result = subprocess.run([
                sys.executable, '-m', 'pip', 'install', package
            ], capture_output=True, text=True, check=True)
            
            self.success_packages.append(package)
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"  ❌ {package} 설치 실패: {e.stderr.strip()}")
            self.failed_packages.append(package)
            return False

    def install_requirements(self):
        """requirements.txt 패키지 설치"""
        print("📦 ToneBridge 필수 패키지 설치 중...")
        
        # pip 업그레이드
        print("pip 업그레이드 중...")
        self.run_command(f"{sys.executable} -m pip install --upgrade pip setuptools wheel")
        
        # requirements.txt 읽기
        req_file = Path(__file__).parent / "requirements.txt"
        if not req_file.exists():
            print("❌ requirements.txt 파일을 찾을 수 없습니다.")
            return False
        
        packages = []
        with open(req_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    packages.append(line)
        
        print(f"설치할 패키지 수: {len(packages)}개")
        
        # 패키지별 설치
        for package in packages:
            self.install_package(package)
        
        return True

    def install_optional_packages(self):
        """선택적 패키지 설치"""
        print("🔧 선택적 패키지 설치 중...")
        
        opt_file = Path(__file__).parent / "requirements-optional.txt"
        if not opt_file.exists():
            print("⚠️  requirements-optional.txt가 없습니다. 건너뜁니다.")
            return True
        
        packages = []
        with open(opt_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    packages.append(line)
        
        print(f"선택적 패키지 수: {len(packages)}개")
        
        for package in packages:
            # 선택적 패키지는 실패해도 계속 진행
            try:
                self.install_package(package)
            except:
                print(f"  ⚠️  {package} 선택적 설치 실패 (계속 진행)")
        
        return True

    def verify_installation(self):
        """설치 검증"""
        print("🧪 설치 검증 중...")
        
        core_modules = [
            ('parselmouth', 'Praat 음성 분석'),
            ('faster_whisper', 'STT 엔진'),
            ('librosa', '오디오 처리'),
            ('soundfile', '오디오 I/O'),
            ('jamo', '한글 처리'),
            ('konlpy', '한국어 분석'),
            ('fastapi', '웹 프레임워크'),
            ('uvicorn', '웹 서버'),
            ('numpy', '수치 계산'),
            ('scipy', '과학 계산')
        ]
        
        success_count = 0
        print("\n=== 핵심 모듈 확인 ===")
        
        for module, desc in core_modules:
            try:
                importlib.import_module(module)
                print(f"✅ {desc} ({module})")
                success_count += 1
            except ImportError:
                print(f"❌ {desc} ({module})")
        
        success_rate = (success_count / len(core_modules)) * 100
        print(f"\n📊 설치 성공률: {success_count}/{len(core_modules)} ({success_rate:.1f}%)")
        
        if success_count >= 8:
            print("🎉 ToneBridge 설치 완료! 모든 핵심 기능을 사용할 수 있습니다.")
            return True
        elif success_count >= 6:
            print("✅ ToneBridge 기본 설치 완료! 일부 고급 기능은 제한될 수 있습니다.")
            return True
        else:
            print("❌ ToneBridge 설치에 문제가 있습니다. 로그를 확인하세요.")
            return False

    def show_summary(self):
        """설치 요약"""
        print("\n" + "="*50)
        print("ToneBridge 설치 요약")
        print("="*50)
        print(f"환경: {self.env_type}")
        print(f"성공 패키지: {len(self.success_packages)}개")
        print(f"실패 패키지: {len(self.failed_packages)}개")
        
        if self.failed_packages:
            print("\n실패한 패키지들:")
            for pkg in self.failed_packages:
                print(f"  - {pkg}")
        
        print(f"\n🚀 ToneBridge 백엔드 시작 방법:")
        print(f"  cd backend")
        print(f"  python backend_server.py")

    def run(self):
        """전체 설치 프로세스 실행"""
        print("🚀 ToneBridge 자동 설치 시작")
        print("="*50)
        print(f"감지된 환경: {self.env_type}")
        print(f"Python 버전: {sys.version}")
        
        try:
            # 1. 시스템 의존성 설치
            if not self.install_system_dependencies():
                print("❌ 시스템 의존성 설치 실패")
                return False
            
            # 2. 필수 패키지 설치
            if not self.install_requirements():
                print("❌ 필수 패키지 설치 실패")
                return False
            
            # 3. 선택적 패키지 설치
            self.install_optional_packages()
            
            # 4. 설치 검증
            success = self.verify_installation()
            
            # 5. 요약 출력
            self.show_summary()
            
            return success
            
        except KeyboardInterrupt:
            print("\n⚠️  설치가 중단되었습니다.")
            return False
        except Exception as e:
            print(f"❌ 설치 중 오류 발생: {e}")
            return False


if __name__ == "__main__":
    installer = ToneBridgeInstaller()
    success = installer.run()
    sys.exit(0 if success else 1)