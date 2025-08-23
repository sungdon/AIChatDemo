# melotts_fastapi_server.py
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
import asyncio
import tempfile
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
import logging
from contextlib import asynccontextmanager

# MeloTTS import
from melo.api import TTS


# Pydantic 모델 정의
class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="변환할 텍스트")
    speed: float = Field(default=1.0, ge=0.1, le=3.0, description="음성 속도 (0.1-3.0)")


class ChatTTSRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000, description="Ollama 프롬프트")
    model: str = Field(default="llama-3-Korean-Bllossom", description="Ollama 모델명")
    speed: float = Field(default=1.0, ge=0.1, le=3.0, description="음성 속도")


class TTSResponse(BaseModel):
    text_response: Optional[str] = None
    audio_url: Optional[str] = None
    success: bool
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    model_loaded: bool


# 글로벌 변수
model = None
speaker_ids = None
temp_files: Dict[str, str] = {}

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 애플리케이션 생명주기 관리
@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작 및 종료 시 실행될 코드"""
    # 시작 시 실행
    global model, speaker_ids
    try:
        logger.info("MeloTTS 한국어 모델 로딩 중...")
        model = TTS(language='KR', device='cpu')
        speaker_ids = model.hps.data.spk2id
        logger.info("MeloTTS 모델 로딩 완료!")
    except Exception as e:
        logger.error(f"모델 로딩 실패: {e}")
        model = None
        speaker_ids = None

    yield

    # 종료 시 정리 작업
    logger.info("임시 파일 정리 중...")
    for file_path in temp_files.values():
        if os.path.exists(file_path):
            os.remove(file_path)
    temp_files.clear()


# FastAPI 앱 생성
app = FastAPI(
    title="MeloTTS 한국어 서버",
    description="Ollama와 통합된 한국어 TTS API 서버",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class OllamaTTSService:
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.client = None

    async def get_http_client(self) -> httpx.AsyncClient:
        """HTTP 클라이언트 싱글턴"""
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=30.0)
        return self.client

    async def close_client(self):
        """HTTP 클라이언트 종료"""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def get_ollama_response(self, prompt: str, model_name: str = "llama-3-Korean-Bllossom") -> str:
        """Ollama에서 비동기 텍스트 응답 생성"""
        try:
            client = await self.get_http_client()
            url = f"{self.ollama_url}/api/generate"
            data = {
                "model": model_name,
                "prompt": prompt,
                "stream": False
            }

            response = await client.post(url, json=data)

            if response.status_code == 200:
                result = response.json()
                return result.get('response', '')
            else:
                logger.error(f"Ollama 요청 실패: {response.status_code}")
                return f"Ollama 오류: {response.status_code}"

        except httpx.TimeoutException:
            logger.error("Ollama 서버 타임아웃")
            return "요청 시간 초과: Ollama 서버 응답이 느립니다."
        except httpx.ConnectError:
            logger.error("Ollama 서버 연결 실패")
            return "연결 오류: Ollama 서버에 연결할 수 없습니다."
        except Exception as e:
            logger.error(f"예상치 못한 오류: {e}")
            return f"시스템 오류: {str(e)}"

    async def generate_korean_tts(self, text: str, speed: float = 1.0) -> Optional[str]:
        """한국어 텍스트를 음성으로 변환 (비동기)"""
        if model is None or speaker_ids is None:
            logger.error("TTS 모델이 로드되지 않았습니다")
            return None

        try:
            # 임시 파일 생성
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            output_path = temp_file.name
            temp_file.close()

            # CPU 집약적 작업을 별도 스레드에서 실행
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: model.tts_to_file(
                    text=text,
                    speaker_id=speaker_ids['KR'],
                    output_path=output_path,
                    speed=speed
                )
            )

            # 생성된 파일 경로를 전역 딕셔너리에 저장
            file_id = os.path.basename(output_path)
            temp_files[file_id] = output_path

            logger.info(f"TTS 음성 생성 완료: {output_path}")
            return file_id

        except Exception as e:
            logger.error(f"TTS 생성 오류: {e}")
            return None


# 서비스 인스턴스 생성
tts_service = OllamaTTSService()


# 의존성 함수
async def get_tts_service() -> OllamaTTSService:
    return tts_service


def check_model_loaded():
    """모델 로드 여부 확인"""
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="TTS 모델이 로드되지 않았습니다. 서버를 재시작해주세요."
        )


# API 엔드포인트
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """서버 상태 확인"""
    return HealthResponse(
        status="healthy",
        service="MeloTTS Korean Server",
        model_loaded=model is not None
    )


@app.post("/chat_tts", response_model=TTSResponse)
async def chat_with_tts(
        request: ChatTTSRequest,
        service: OllamaTTSService = Depends(get_tts_service),
        background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Ollama 채팅 + TTS 음성 생성"""
    check_model_loaded()

    try:
        logger.info(f"채팅 TTS 요청: {request.prompt[:50]}...")

        # Ollama에서 응답 생성
        response_text = await service.get_ollama_response(request.prompt, request.model)

        # 응답이 오류 메시지인지 확인
        if response_text.startswith(("Ollama 오류:", "연결 오류:", "요청 시간 초과:", "시스템 오류:")):
            return TTSResponse(
                text_response=response_text,
                success=False,
                error=response_text
            )

        # 응답을 한국어 TTS로 변환
        file_id = await service.generate_korean_tts(response_text, request.speed)

        if file_id:
            # 백그라운드 태스크로 파일 정리 스케줄링 (10분 후)
            background_tasks.add_task(cleanup_temp_file, file_id, delay=600)

            return TTSResponse(
                text_response=response_text,
                audio_url=f"/get_audio?file={file_id}",
                success=True
            )
        else:
            return TTSResponse(
                text_response=response_text,
                success=False,
                error="음성 생성에 실패했습니다."
            )

    except Exception as e:
        logger.error(f"채팅 TTS 오류: {e}")
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")


@app.post("/tts", response_model=TTSResponse)
async def text_to_speech(
        request: TTSRequest,
        service: OllamaTTSService = Depends(get_tts_service),
        background_tasks: BackgroundTasks = BackgroundTasks()
):
    """텍스트만 TTS로 변환"""
    check_model_loaded()

    try:
        logger.info(f"TTS 요청: {request.text[:50]}...")

        file_id = await service.generate_korean_tts(request.text, request.speed)

        if file_id:
            # 백그라운드 태스크로 파일 정리 스케줄링 (10분 후)
            background_tasks.add_task(cleanup_temp_file, file_id, delay=600)

            return TTSResponse(
                audio_url=f"/get_audio?file={file_id}",
                success=True
            )
        else:
            raise HTTPException(status_code=500, detail="음성 생성에 실패했습니다.")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS 오류: {e}")
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")


@app.get("/get_audio")
async def get_audio_file(file: str):
    """생성된 음성 파일 다운로드"""
    try:
        if not file or file not in temp_files:
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

        file_path = temp_files[file]

        if not os.path.exists(file_path):
            # 파일이 삭제된 경우 딕셔너리에서도 제거
            temp_files.pop(file, None)
            raise HTTPException(status_code=404, detail="파일이 더 이상 존재하지 않습니다.")

        return FileResponse(
            path=file_path,
            media_type="audio/wav",
            filename="tts_audio.wav",
            headers={
                "Content-Disposition": "attachment; filename=tts_audio.wav",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"파일 전송 오류: {e}")
        raise HTTPException(status_code=500, detail=f"파일 전송 중 오류가 발생했습니다: {str(e)}")


# 백그라운드 태스크 함수
async def cleanup_temp_file(file_id: str, delay: int = 0):
    """임시 파일 정리 (지연 시간 후)"""
    if delay > 0:
        await asyncio.sleep(delay)

    if file_id in temp_files:
        file_path = temp_files.pop(file_id)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"임시 파일 삭제됨: {file_path}")
            except Exception as e:
                logger.error(f"파일 삭제 실패: {file_path}, 오류: {e}")


# 서버 종료 시 정리
@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 실행"""
    logger.info("서버 종료 중...")
    await tts_service.close_client()


# 메인 실행
if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("🎤 MeloTTS 한국어 FastAPI 서버")
    print("=" * 60)
    print("📋 사전 준비사항:")
    print("1. Ollama 서버가 http://localhost:11434 에서 실행 중인지 확인")
    print("2. MeloTTS 라이브러리가 설치되어 있는지 확인")
    print("📚 API 문서: http://localhost:5000/docs")
    print("🔧 ReDoc 문서: http://localhost:5000/redoc")
    print("=" * 60)

    uvicorn.run(
        "melotts_fastapi_server:app",
        host="0.0.0.0",
        port=5000,
        reload=True,
        log_level="info"
    )
