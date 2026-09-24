from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from services.cleanup_service import TempFileManager
from services.auth_service import auth_service, get_current_user
from services.job_service import job_service
from services.media_service import MediaProcessingService


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("media-app")
APP_VERSION = os.getenv("APP_VERSION", "async-jobs-v3")


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


@app.get("/app")
async def app_dashboard() -> FileResponse:
    app_path = FRONTEND_DIR / "app.html"
    if not app_path.exists():
        raise HTTPException(status_code=404, detail="Frontend no encontrado.")
    return FileResponse(app_path)


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "version": APP_VERSION,
            "transcription_provider": os.getenv("TRANSCRIPTION_PROVIDER", "local"),
        }
    )


@app.get("/api/v1/auth/config")
async def auth_config() -> JSONResponse:
    return JSONResponse(
        {
            "enabled": auth_service.configured,
            "supabase_url": auth_service.url,
            "supabase_anon_key": auth_service.anon_key,
        }
    )


@app.get("/api/v1/account")
async def account(user=Depends(get_current_user)) -> JSONResponse:
    return JSONResponse(await auth_service.account(user))


@app.post("/api/v1/account/consume/{service}")
async def consume_free_use(service: str, user=Depends(get_current_user)) -> JSONResponse:
    return JSONResponse(await auth_service.consume_or_reject(user, service))


@app.get("/api/v1/admin/users")
async def admin_users(user=Depends(get_current_user)) -> JSONResponse:
    return JSONResponse(await auth_service.admin_users(user))


@app.get("/api/v1/jobs/{job_id}")
async def job_status(job_id: str, user=Depends(get_current_user)) -> JSONResponse:
    return JSONResponse(await job_service.get_for_user(job_id, user["id"]))


@app.patch("/api/v1/admin/users/{user_id}/plan")
async def admin_set_plan(user_id: str, payload: dict[str, str], user=Depends(get_current_user)) -> JSONResponse:
    return JSONResponse(await auth_service.admin_set_plan(user, user_id, payload.get("plan", "")))


@app.post("/api/v1/video-to-audio")
async def video_to_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...), user=Depends(get_current_user)) -> FileResponse:
    try:
        output_path, filename = await media_service.video_to_audio(file)
        try:
            await auth_service.consume_or_reject(user, "video_to_audio")
        except Exception:
            temp_manager.safe_delete(Path(output_path))
            raise
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


@app.post("/api/v1/audio-to-text", status_code=202)
async def audio_to_text(file: UploadFile = File(...), user=Depends(get_current_user)) -> JSONResponse:
    logger.info("stage=audio_request_received user=%s filename=%s", user["id"], file.filename)
    input_path = await media_service.prepare_audio_upload(file)
    logger.info("stage=audio_upload_persisted user=%s file=%s", user["id"], input_path.name)

    async def runner(update):
        try:
            update(30, "Normalizando el audio con FFmpeg...")
            update(45, "Enviando el audio al motor de transcripción...")
            result = await media_service.audio_path_to_text(input_path)
            update(90, "Preparando el texto final...")
            await auth_service.consume_or_reject(user, "audio_to_text")
            return result
        finally:
            temp_manager.safe_delete(input_path)

    job = await job_service.create(user["id"], "audio_to_text", runner)
    logger.info("stage=audio_job_accepted user=%s job=%s", user["id"], job.id)
    return JSONResponse({"job_id": job.id, "status": job.status, "progress": job.progress}, status_code=202)


@app.post("/api/v1/video-to-text", status_code=202)
async def video_to_text(file: UploadFile = File(...), user=Depends(get_current_user)) -> JSONResponse:
    try:
        await media_service._validate_upload(file, allowed={".mp4", ".mov", ".avi", ".mkv"})
        input_path = await media_service._persist_upload(file, suffix=Path(file.filename or "").suffix)
    except Exception:
        raise

    async def runner(update):
        try:
            update(25, "Extrayendo el audio del video...")
            with media_service.temp_manager.managed_temp_path(suffix=".mp3") as audio_path:
                await asyncio.to_thread(media_service._extract_audio_ffmpeg, input_path, audio_path)
                update(50, "Enviando el audio al motor de transcripción...")
                result = await media_service.audio_path_to_text(audio_path)
            update(90, "Preparando el texto final...")
            await auth_service.consume_or_reject(user, "video_to_text")
            return result
        finally:
            temp_manager.safe_delete(input_path)

    job = await job_service.create(user["id"], "video_to_text", runner)
    return JSONResponse({"job_id": job.id, "status": job.status, "progress": job.progress}, status_code=202)


@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
