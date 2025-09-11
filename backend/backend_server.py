"""
ToneBridge 백엔드 서버
FastAPI 기반 REST API 서버
"""

import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import json

# FastAPI
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# 프로젝트 모듈
from config import settings, print_settings
from utils import (get_logger, ErrorHandler, http_exception_handler,
                   validation_exception_handler, general_exception_handler,
                   audit_logger, performance_logger, cleanup_old_logs,
                   log_environment, get_environment)

# Core 모듈
from core import (AudioNormalizer, AudioQualityEnhancer, KoreanAudioOptimizer,
                  VoiceAnalyzer, AdvancedSTTProcessor, MultiEngineSTT,
                  UltimateSTTSystem, QualityValidator)

# ToneBridge Core 모듈
from tonebridge_core import (VoiceProcessor, ProcessingPipeline,
                             PipelineConfig, UniversalSTT, STTConfig,
                             KoreanSegmenter, TextGridGenerator, PitchAnalyzer)

# 데이터베이스 모델
from models import init_db, get_db, AudioFile, ProcessingResult, UserProfile

logger = get_logger(__name__)

# ========== FastAPI 앱 초기화 ==========

app = FastAPI(title="ToneBridge API",
              description="한국어 운율 학습 플랫폼 API",
              version="2.0.0",
              docs_url="/api/docs",
              redoc_url="/api/redoc")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 서빙
app.mount("/static",
          StaticFiles(directory=str(settings.STATIC_DIR)),
          name="static")

# 에러 핸들러 등록
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(422, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# ========== 전역 객체 초기화 ==========

# 처리기 초기화
voice_processor = VoiceProcessor()
universal_stt = UniversalSTT()
quality_validator = QualityValidator()
pitch_analyzer = PitchAnalyzer()
korean_segmenter = KoreanSegmenter()
textgrid_generator = TextGridGenerator()

# ========== Pydantic 모델 ==========


class HealthResponse(BaseModel):
    """헬스 체크 응답"""
    status: str
    timestamp: datetime
    version: str = "2.0.0"
    services: Dict[str, bool]


class ProcessRequest(BaseModel):
    """처리 요청"""
    file_id: str
    processing_options: Dict[str, Any] = Field(default_factory=dict)
    language: str = "ko"
    output_format: str = "json"


class ProcessResponse(BaseModel):
    """처리 응답"""
    success: bool
    task_id: str
    message: str
    data: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None


class TranscribeRequest(BaseModel):
    """전사 요청"""
    file_id: str
    language: str = "ko"
    engine: str = "whisper"
    enable_punctuation: bool = True


class AnalysisRequest(BaseModel):
    """분석 요청"""
    file_id: str
    analyze_pitch: bool = True
    analyze_formants: bool = True
    analyze_spectrum: bool = True


class ComparisonRequest(BaseModel):
    """비교 요청"""
    reference_file_id: str
    target_file_id: str
    analysis_type: str = "all"  # all, pitch, timing, pronunciation


# ========== 유틸리티 함수 ==========


async def save_upload_file(upload_file: UploadFile) -> Path:
    """업로드 파일 저장"""
    # 고유 파일명 생성
    file_extension = Path(upload_file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = settings.UPLOAD_FILES_PATH / unique_filename

    # 파일 저장
    try:
        contents = await upload_file.read()
        with open(file_path, 'wb') as f:
            f.write(contents)

        logger.info(f"파일 저장 완료: {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"파일 저장 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"파일 저장 실패: {str(e)}")


def get_file_path(file_id: str) -> Path:
    """파일 ID로 경로 가져오기"""
    # DB에서 조회 또는 직접 경로 생성
    file_path = settings.UPLOAD_FILES_PATH / file_id

    if not file_path.exists():
        # 확장자 추가 시도
        for ext in ['.wav', '.mp3', '.m4a']:
            test_path = settings.UPLOAD_FILES_PATH / f"{file_id}{ext}"
            if test_path.exists():
                file_path = test_path
                break

    if not file_path.exists():
        raise HTTPException(status_code=404,
                            detail=f"파일을 찾을 수 없습니다: {file_id}")

    return file_path


# ========== 엔드포인트 ==========


@app.get("/", tags=["Root"])
async def root():
    """루트 엔드포인트"""
    return {
        "message": "ToneBridge API v2.0",
        "documentation": "/api/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """헬스 체크"""
    services = {
        "database": True,  # DB 연결 체크
        "stt": universal_stt is not None,
        "processor": voice_processor is not None,
        "storage": settings.UPLOAD_FILES_PATH.exists()
    }

    return HealthResponse(
        status="healthy" if all(services.values()) else "degraded",
        timestamp=datetime.now(),
        services=services)


# ========== 파일 업로드 ==========


@app.post("/api/upload", response_model=ProcessResponse, tags=["Files"])
async def upload_file(file: UploadFile = File(...),
                      background_tasks: BackgroundTasks = BackgroundTasks()):
    """
    오디오 파일 업로드

    - **file**: 업로드할 오디오 파일 (WAV, MP3, M4A 등)
    """
    try:
        # 파일 형식 검증
        if not settings.validate_file_extension(file.filename):
            raise HTTPException(
                status_code=400,
                detail=f"지원하지 않는 파일 형식입니다. 지원 형식: {settings.ALLOWED_EXTENSIONS}"
            )

        # 파일 저장
        file_path = await save_upload_file(file)
        file_id = file_path.stem

        # 감사 로깅
        audit_logger.log_action(action="file_upload",
                                target=str(file_path),
                                details={
                                    "original_name": file.filename,
                                    "file_id": file_id
                                })

        # 백그라운드에서 전처리
        background_tasks.add_task(preprocess_audio, file_path)

        return ProcessResponse(
            success=True,
            task_id=file_id,
            message="파일 업로드 성공",
            data={
                "file_id": file_id,
                "filename": file.filename,
                "path": str(file_path.relative_to(settings.BACKEND_DIR))
            })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"업로드 실패: {str(e)}")
        return ProcessResponse(success=False,
                               task_id="",
                               message="파일 업로드 실패",
                               errors=[str(e)])


# ========== 음성 처리 ==========


@app.post("/api/process", response_model=ProcessResponse, tags=["Processing"])
async def process_audio(request: ProcessRequest,
                        background_tasks: BackgroundTasks):
    """
    오디오 파일 종합 처리

    전처리, 정규화, 품질 향상, 분석, STT 등 모든 처리를 수행합니다.
    """
    try:
        file_path = get_file_path(request.file_id)

        # 파이프라인 설정
        config = PipelineConfig(language=request.language,
                                output_format=request.output_format,
                                **request.processing_options)

        # 백그라운드 처리
        task_id = str(uuid.uuid4())
        background_tasks.add_task(process_audio_pipeline, file_path, config,
                                  task_id)

        return ProcessResponse(success=True,
                               task_id=task_id,
                               message="처리 시작됨",
                               data={"file_id": request.file_id})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"처리 실패: {str(e)}")
        return ProcessResponse(success=False,
                               task_id="",
                               message="처리 실패",
                               errors=[str(e)])


@app.post("/api/transcribe", response_model=ProcessResponse, tags=["STT"])
async def transcribe_audio(request: TranscribeRequest):
    """
    음성 인식 (STT)

    오디오 파일을 텍스트로 변환합니다.
    """
    try:
        file_path = get_file_path(request.file_id)

        # STT 설정
        stt_config = STTConfig(language=request.language,
                               primary_engine=request.engine,
                               enable_punctuation=request.enable_punctuation)

        # STT 실행
        stt = UniversalSTT(stt_config)
        result = stt.transcribe(file_path)

        # 성능 메트릭
        performance_logger.log_metric("stt_processing_time",
                                      result.processing_time,
                                      unit="seconds",
                                      tags={"engine": request.engine})

        return ProcessResponse(success=True,
                               task_id=request.file_id,
                               message="전사 완료",
                               data=result.to_dict())

    except Exception as e:
        logger.error(f"전사 실패: {str(e)}")
        return ProcessResponse(success=False,
                               task_id=request.file_id,
                               message="전사 실패",
                               errors=[str(e)])


# ========== 음성 분석 ==========


@app.post("/api/analyze", response_model=ProcessResponse, tags=["Analysis"])
async def analyze_audio(request: AnalysisRequest):
    """
    음성 분석

    피치, 포먼트, 스펙트럼 등을 분석합니다.
    """
    try:
        file_path = get_file_path(request.file_id)

        result = {}

        # 피치 분석
        if request.analyze_pitch:
            pitch_result = pitch_analyzer.analyze(file_path)
            result['pitch'] = pitch_result.to_dict()

        # 음성 분석
        voice_analyzer = VoiceAnalyzer()
        voice_result = voice_analyzer.analyze_audio(
            file_path,
            extract_pitch=request.analyze_pitch,
            extract_formants=request.analyze_formants,
            segment_syllables=True)
        result['voice'] = voice_result

        return ProcessResponse(success=True,
                               task_id=request.file_id,
                               message="분석 완료",
                               data=result)

    except Exception as e:
        logger.error(f"분석 실패: {str(e)}")
        return ProcessResponse(success=False,
                               task_id=request.file_id,
                               message="분석 실패",
                               errors=[str(e)])


@app.post("/api/compare", response_model=ProcessResponse, tags=["Analysis"])
async def compare_audio(request: ComparisonRequest):
    """
    음성 비교 분석

    두 오디오 파일을 비교 분석합니다.
    """
    try:
        reference_path = get_file_path(request.reference_file_id)
        target_path = get_file_path(request.target_file_id)

        # 비교 분석
        voice_analyzer = VoiceAnalyzer()
        comparison = voice_analyzer.compare_audio_files(
            reference_path, target_path)

        # 품질 검증
        quality_result = quality_validator.pronunciation_validator.evaluate_pronunciation(
            target_path, reference_path)

        return ProcessResponse(
            success=True,
            task_id=f"{request.reference_file_id}_vs_{request.target_file_id}",
            message="비교 완료",
            data={
                "comparison": comparison,
                "pronunciation": quality_result.to_dict()
            })

    except Exception as e:
        logger.error(f"비교 실패: {str(e)}")
        return ProcessResponse(success=False,
                               task_id="",
                               message="비교 실패",
                               errors=[str(e)])


# ========== 품질 검증 ==========


@app.post("/api/validate", response_model=ProcessResponse, tags=["Quality"])
async def validate_quality(file_id: str):
    """
    오디오 품질 검증

    오디오 파일의 품질을 검증합니다.
    """
    try:
        file_path = get_file_path(file_id)

        # 품질 검증
        validation_result = quality_validator.validate_comprehensive(file_path)

        # 보고서 생성
        report = quality_validator.generate_report(validation_result)

        return ProcessResponse(success=True,
                               task_id=file_id,
                               message="검증 완료",
                               data={
                                   "validation": validation_result.to_dict(),
                                   "report": report
                               })

    except Exception as e:
        logger.error(f"검증 실패: {str(e)}")
        return ProcessResponse(success=False,
                               task_id=file_id,
                               message="검증 실패",
                               errors=[str(e)])


# ========== 파일 다운로드 ==========


@app.get("/api/download/{file_id}", tags=["Files"])
async def download_file(file_id: str):
    """
    파일 다운로드

    처리된 파일을 다운로드합니다.
    """
    try:
        file_path = get_file_path(file_id)

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다")

        return FileResponse(path=str(file_path),
                            filename=file_path.name,
                            media_type='application/octet-stream')

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"다운로드 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== TextGrid 생성 ==========


@app.post("/api/textgrid/generate",
          response_model=ProcessResponse,
          tags=["TextGrid"])
async def generate_textgrid(file_id: str):
    """
    TextGrid 생성

    오디오 파일에서 TextGrid를 생성합니다.
    """
    try:
        file_path = get_file_path(file_id)

        # 음성 분석
        voice_analyzer = VoiceAnalyzer()
        analysis = voice_analyzer.analyze_audio(file_path)

        # STT 실행
        stt = UniversalSTT()
        stt_result = stt.transcribe(file_path)

        # TextGrid 생성
        textgrid = textgrid_generator.generate_from_stt(
            stt_result.to_dict(), analysis['file_info']['duration'])

        # 저장
        textgrid_path = file_path.with_suffix('.TextGrid')
        textgrid_generator.save(textgrid, textgrid_path)

        return ProcessResponse(success=True,
                               task_id=file_id,
                               message="TextGrid 생성 완료",
                               data={
                                   "textgrid_path": str(textgrid_path.name),
                                   "tier_count": textgrid.tier_count,
                                   "duration": textgrid.duration
                               })

    except Exception as e:
        logger.error(f"TextGrid 생성 실패: {str(e)}")
        return ProcessResponse(success=False,
                               task_id=file_id,
                               message="TextGrid 생성 실패",
                               errors=[str(e)])


# ========== 참조 파일 ==========


@app.get("/api/reference/list", tags=["Reference"])
async def list_reference_files():
    """
    참조 파일 목록

    사용 가능한 참조 파일 목록을 반환합니다.
    """
    try:
        reference_files = []

        for file_path in settings.REFERENCE_FILES_PATH.glob("*.wav"):
            reference_files.append({
                "id":
                file_path.stem,
                "filename":
                file_path.name,
                "size":
                file_path.stat().st_size,
                "path":
                f"/static/reference_files/{file_path.name}"
            })

        return {
            "success": True,
            "count": len(reference_files),
            "files": reference_files
        }

    except Exception as e:
        logger.error(f"참조 파일 목록 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== 백그라운드 태스크 ==========


async def preprocess_audio(file_path: Path):
    """오디오 전처리 (백그라운드)"""
    try:
        normalizer = AudioNormalizer()
        enhancer = AudioQualityEnhancer()

        # 정규화
        normalized_path = file_path.parent / f"{file_path.stem}_normalized.wav"
        normalizer.process_audio_file(file_path, normalized_path)

        # 품질 향상
        enhanced_path = file_path.parent / f"{file_path.stem}_enhanced.wav"
        enhancer.enhance_audio_quality(normalized_path, enhanced_path)

        logger.info(f"전처리 완료: {file_path}")

    except Exception as e:
        logger.error(f"전처리 실패: {str(e)}")


async def process_audio_pipeline(file_path: Path, config: PipelineConfig,
                                 task_id: str):
    """오디오 처리 파이프라인 (백그라운드)"""
    try:
        # 파이프라인 실행
        result = voice_processor.process(file_path, config)

        # 결과 저장 (DB 또는 파일)
        result_path = settings.TEMP_DIR / f"{task_id}_result.json"
        with open(result_path, 'w', encoding='utf-8') as f:
            f.write(result.to_json())

        logger.info(f"파이프라인 완료: {task_id}")

    except Exception as e:
        logger.error(f"파이프라인 실패: {str(e)}")


# ========== 시작/종료 이벤트 ==========


@app.on_event("startup")
async def startup_event():
    """서버 시작 이벤트"""
    logger.info("=" * 50)
    logger.info("ToneBridge 서버 시작")
    logger.info("=" * 50)

    # 설정 출력
    print_settings()

    # DB 초기화
    init_db()

    # 디렉토리 생성
    settings.UPLOAD_FILES_PATH.mkdir(parents=True, exist_ok=True)
    settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # 오래된 파일 정리
    settings.cleanup_old_files()
    cleanup_old_logs()

    logger.info("서버 초기화 완료")


@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 이벤트"""
    logger.info("ToneBridge 서버 종료")

    # 임시 파일 정리
    for temp_file in settings.TEMP_DIR.glob("*"):
        try:
            temp_file.unlink()
        except:
            pass


# ========== 메인 실행 ==========

if __name__ == "__main__":
    """Pure Nix 환경에서 직접 서버 시작"""
    import uvicorn
    
    # 설정 출력
    print_settings()
    
    # 데이터베이스 초기화
    try:
        init_db()
        logger.info("데이터베이스 초기화 완료")
        
        # 환경 정보 로깅
        environment = get_environment()
        logger.info(f"감지된 환경: {environment}")
        log_environment()
    except Exception as e:
        logger.error(f"데이터베이스 초기화 실패: {e}")
    
    # Pure Nix 환경 설정 로그
    logger.info("Pure Nix 환경에서 ToneBridge 백엔드 서버 시작")
    
    # 서버 시작
    uvicorn.run(
        "backend_server:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )
