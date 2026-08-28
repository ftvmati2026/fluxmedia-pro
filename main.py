from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from services.cleanup_service import TempFileManager
from services.media_service import MediaProcessingService


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("media-app")


app = FastAPI(
    title="Media Transcription API",
    version="1.0.0",
    description="API para extraer audio y transcribir video/audio con FastAPI + FFmpeg + faster-whisper.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

temp_manager = TempFileManager()
media_service = MediaProcessingService(temp_manager=temp_manager)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    temp_manager.cleanup_all_safely()


@app.get("/")
async def root() -> FileResponse:
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend no encontrado.")
    return FileResponse(index_path)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.post("/api/v1/video-to-audio")
async def video_to_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...)) -> FileResponse:
    try:
        output_path, filename = await media_service.video_to_audio(file)
        background_tasks.add_task(temp_manager.safe_delete, Path(output_path))
        return FileResponse(
            path=output_path,
            media_type="audio/mpeg",
            filename=filename,
            headers={"Cache-Control": "no-store"},
            background=background_tasks,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in video_to_audio")
        raise HTTPException(status_code=500, detail=f"Error procesando video a audio: {exc}") from exc


@app.post("/api/v1/audio-to-text")
async def audio_to_text(file: UploadFile = File(...)) -> JSONResponse:
    try:
        result = await media_service.audio_to_text(file)
        return JSONResponse(result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in audio_to_text")
        raise HTTPException(status_code=500, detail=f"Error transcribiendo audio: {exc}") from exc


@app.post("/api/v1/video-to-text")
async def video_to_text(file: UploadFile = File(...)) -> JSONResponse:
    try:
        result = await media_service.video_to_text(file)
        return JSONResponse(result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in video_to_text")
        raise HTTPException(status_code=500, detail=f"Error transcribiendo video: {exc}") from exc


@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
