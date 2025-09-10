"""
ToneBridge 설정 관리 모듈
모든 설정값을 중앙화하여 관리
"""

from pathlib import Path
from typing import List, Tuple, Optional
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()


class Settings:
    """ToneBridge 시스템 전체 설정"""

    # ========== 경로 설정 ==========
    BASE_DIR = Path(__file__).resolve().parent.parent
    BACKEND_DIR = BASE_DIR
    STATIC_DIR = BACKEND_DIR / "static"
    REFERENCE_FILES_PATH = STATIC_DIR / "reference_files"
    UPLOAD_FILES_PATH = STATIC_DIR / "uploads"
    TEMP_DIR = BACKEND_DIR / "temp"
    VIDEOS_PATH = STATIC_DIR / "videos"
    IMAGES_PATH = STATIC_DIR / "images"

    # 디렉토리 생성 (존재하지 않을 경우)
    for dir_path in [UPLOAD_FILES_PATH, TEMP_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # ========== 서버 설정 ==========
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
    MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB

    # ========== 데이터베이스 설정 ==========
    DATABASE_URL = os.getenv("DATABASE_URL",
                             f"sqlite:///{BACKEND_DIR}/tonebridge.db")

    # ========== 음성 분석 설정 ==========
    # Praat 피치 분석 설정
    PITCH_FLOOR = 75.0  # Hz, 최소 피치 (남성 포함)
    PITCH_CEILING = 600.0  # Hz, 최대 피치 (여성 포함)
    PITCH_TIME_STEP = 0.01  # 초, 피치 분석 시간 간격

    # 샘플레이트 설정
    TARGET_SAMPLE_RATE = 16000  # Hz, Whisper 최적 샘플레이트
    HIGH_QUALITY_SAMPLE_RATE = 44100  # Hz, 고품질 오디오

    # 볼륨 정규화 설정
    TARGET_DB = -20.0  # dB, 표준 음량
    TARGET_LUFS = -16.0  # LUFS, 방송 표준
    SILENCE_THRESHOLD = -40.0  # dB, 무음 판단 기준

    # ========== 한국어 특화 설정 ==========
    # 음절 분석 설정
    KOREAN_SYLLABLE_DURATION = 0.3  # 초, 평균 음절 길이
    MIN_SYLLABLE_DURATION = 0.05  # 초, 최소 음절 길이
    MAX_SYLLABLE_DURATION = 0.8  # 초, 최대 음절 길이

    # 성별별 피치 범위
    KOREAN_PITCH_RANGE_MALE = (85, 180)  # Hz
    KOREAN_PITCH_RANGE_FEMALE = (165, 255)  # Hz
    KOREAN_PITCH_RANGE_CHILD = (250, 400)  # Hz

    # 한국어 음성학 설정
    KOREAN_VOWELS = [
        'ㅏ', 'ㅐ', 'ㅑ', 'ㅒ', 'ㅓ', 'ㅔ', 'ㅕ', 'ㅖ', 'ㅗ', 'ㅘ', 'ㅙ', 'ㅚ', 'ㅛ', 'ㅜ',
        'ㅝ', 'ㅞ', 'ㅟ', 'ㅠ', 'ㅡ', 'ㅢ', 'ㅣ'
    ]
    KOREAN_CONSONANTS = [
        'ㄱ', 'ㄲ', 'ㄴ', 'ㄷ', 'ㄸ', 'ㄹ', 'ㅁ', 'ㅂ', 'ㅃ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅉ',
        'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'
    ]

    # ========== STT 설정 ==========
    # Whisper 설정
    WHISPER_MODEL = "large-v3"  # 모델 크기 (tiny, base, small, medium, large, large-v3)
    WHISPER_LANGUAGE = "ko"
    WHISPER_TASK = "transcribe"  # transcribe 또는 translate

    # STT 품질 설정
    STT_CONFIDENCE_THRESHOLD = 0.8  # 신뢰도 임계값
    STT_MAX_RETRIES = 3  # 최대 재시도 횟수
    STT_TIMEOUT = 30  # 초, STT 타임아웃

    # 다중 엔진 설정
    ENABLE_GOOGLE_STT = os.getenv("ENABLE_GOOGLE_STT",
                                  "False").lower() == "true"
    ENABLE_AZURE_STT = os.getenv("ENABLE_AZURE_STT", "False").lower() == "true"
    ENABLE_NAVER_STT = os.getenv("ENABLE_NAVER_STT", "False").lower() == "true"

    # API 키 (환경변수에서 로드)
    GOOGLE_CLOUD_API_KEY = os.getenv("GOOGLE_CLOUD_API_KEY", "")
    AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "")
    AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "koreacentral")
    NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
    NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")

    # ========== TextGrid 설정 ==========
    # 인코딩 우선순위
    TEXTGRID_ENCODINGS = [
        'utf-16', 'utf-16-le', 'utf-16-be', 'utf-8', 'cp949', 'euc-kr'
    ]
    TEXTGRID_DEFAULT_ENCODING = 'utf-16'  # Praat 기본 인코딩

    # TextGrid 생성 설정
    TEXTGRID_TIER_NAMES = {
        'words': 'words',
        'phones': 'phones',
        'syllables': 'syllables',
        'pitch': 'pitch'
    }

    # ========== 음질 향상 설정 ==========
    # 노이즈 제거
    NOISE_REDUCTION_STRENGTH = 0.3  # 0.0 ~ 1.0
    ENABLE_NOISE_GATE = True
    NOISE_GATE_THRESHOLD = -35.0  # dB

    # 음성 향상
    ENABLE_COMPRESSOR = True
    COMPRESSOR_RATIO = 3.0  # 압축 비율
    COMPRESSOR_THRESHOLD = -20.0  # dB

    # EQ 설정
    ENABLE_EQ = True
    EQ_LOW_FREQ = 80  # Hz, 저역 차단 주파수
    EQ_HIGH_FREQ = 12000  # Hz, 고역 차단 주파수

    # ========== 참조 파일 설정 ==========
    # 기본 참조 파일 목록
    DEFAULT_REFERENCE_FILES = [
        "안녕하세요", "반갑습니다", "반가워요", "뭐라고그러셨소", "아주잘보이네요", "낭독문장", "뉴스읽기", "올라가",
        "내려가", "내친구"
    ]

    # ========== 로깅 설정 ==========
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE = BACKEND_DIR / "tonebridge.log"
    ENABLE_FILE_LOGGING = True

    # ========== 캐싱 설정 ==========
    ENABLE_CACHE = True
    CACHE_TTL = 3600  # 초, 캐시 유효 시간
    CACHE_DIR = BACKEND_DIR / ".cache"
    CACHE_DIR.mkdir(exist_ok=True)

    # ========== 성능 설정 ==========
    MAX_WORKERS = os.cpu_count() or 4  # 멀티프로세싱 워커 수
    CHUNK_SIZE = 1024 * 1024  # 1MB, 파일 처리 청크 크기
    MAX_CONCURRENT_REQUESTS = 100  # 최대 동시 요청 수

    # ========== 보안 설정 ==========
    SECRET_KEY = os.getenv("SECRET_KEY",
                           "your-secret-key-here-change-in-production")
    ALLOWED_EXTENSIONS = {'.wav', '.mp3', '.m4a', '.flac', '.ogg', '.webm'}
    MAX_FILE_AGE_DAYS = 7  # 업로드 파일 보관 기간

    @classmethod
    def get_pitch_range(cls, gender: str = "unknown") -> Tuple[float, float]:
        """성별에 따른 피치 범위 반환"""
        gender = gender.lower()
        if gender == "male":
            return cls.KOREAN_PITCH_RANGE_MALE
        elif gender == "female":
            return cls.KOREAN_PITCH_RANGE_FEMALE
        elif gender == "child":
            return cls.KOREAN_PITCH_RANGE_CHILD
        else:
            # 전체 범위 반환
            return (cls.PITCH_FLOOR, cls.PITCH_CEILING)

    @classmethod
    def validate_file_extension(cls, filename: str) -> bool:
        """파일 확장자 검증"""
        return Path(filename).suffix.lower() in cls.ALLOWED_EXTENSIONS

    @classmethod
    def get_temp_path(cls, filename: str) -> Path:
        """임시 파일 경로 생성"""
        import uuid
        unique_name = f"{uuid.uuid4()}_{filename}"
        return cls.TEMP_DIR / unique_name

    @classmethod
    def get_reference_file_path(cls,
                                filename: str,
                                extension: str = ".wav") -> Optional[Path]:
        """참조 파일 경로 가져오기"""
        if not filename.endswith(extension):
            filename = f"{filename}{extension}"
        file_path = cls.REFERENCE_FILES_PATH / filename
        return file_path if file_path.exists() else None

    @classmethod
    def cleanup_old_files(cls):
        """오래된 업로드 파일 정리"""
        import time
        from datetime import datetime, timedelta

        cutoff_time = time.time() - (cls.MAX_FILE_AGE_DAYS * 24 * 3600)

        for file_path in cls.UPLOAD_FILES_PATH.iterdir():
            if file_path.is_file():
                if file_path.stat().st_mtime < cutoff_time:
                    try:
                        file_path.unlink()
                        print(f"Deleted old file: {file_path}")
                    except Exception as e:
                        print(f"Error deleting file {file_path}: {e}")


# 설정 인스턴스 생성
settings = Settings()


# 설정 검증
def validate_settings():
    """설정 검증 및 경고 출력"""
    warnings = []

    # API 키 확인
    if settings.ENABLE_GOOGLE_STT and not settings.GOOGLE_CLOUD_API_KEY:
        warnings.append("Google STT가 활성화되었지만 API 키가 설정되지 않았습니다.")

    if settings.ENABLE_AZURE_STT and not settings.AZURE_SPEECH_KEY:
        warnings.append("Azure STT가 활성화되었지만 API 키가 설정되지 않았습니다.")

    if settings.ENABLE_NAVER_STT and (not settings.NAVER_CLIENT_ID
                                      or not settings.NAVER_CLIENT_SECRET):
        warnings.append("Naver STT가 활성화되었지만 API 키가 설정되지 않았습니다.")

    # 경로 확인
    if not settings.REFERENCE_FILES_PATH.exists():
        warnings.append(
            f"참조 파일 경로가 존재하지 않습니다: {settings.REFERENCE_FILES_PATH}")

    # SECRET_KEY 확인
    if settings.SECRET_KEY == "your-secret-key-here-change-in-production":
        warnings.append("보안 경고: 기본 SECRET_KEY를 사용 중입니다. 프로덕션에서는 변경하세요.")

    return warnings


# 설정 정보 출력
def print_settings():
    """현재 설정 정보 출력"""
    print("=" * 50)
    print("ToneBridge 설정 정보")
    print("=" * 50)
    print(f"기본 디렉토리: {settings.BASE_DIR}")
    print(f"서버: {settings.HOST}:{settings.PORT}")
    print(f"디버그 모드: {settings.DEBUG}")
    print(f"데이터베이스: {settings.DATABASE_URL}")
    print(f"Whisper 모델: {settings.WHISPER_MODEL}")
    print(f"로그 레벨: {settings.LOG_LEVEL}")
    print("=" * 50)

    # 경고 출력
    warnings = validate_settings()
    if warnings:
        print("⚠️  경고:")
        for warning in warnings:
            print(f"  - {warning}")
        print("=" * 50)
