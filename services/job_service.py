from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from fastapi import HTTPException


logger = logging.getLogger("media-jobs")
JobRunner = Callable[[Callable[[int, str], None]], Awaitable[dict[str, Any]]]


@dataclass
class ProcessingJob:
    id: str
    owner_id: str
    kind: str
    created_at: float = field(default_factory=time.time)
    status: str = "processing"
    progress: int = 5
    message: str = "Archivo recibido. Preparando el procesamiento..."
    result: dict[str, Any] | None = None
    error: str | None = None


class JobService:
    """Small in-process job registry suitable for a single Render web instance."""

    def __init__(self) -> None:
        self._jobs: dict[str, ProcessingJob] = {}
        self._lock = asyncio.Lock()

    async def create(self, owner_id: str, kind: str, runner: JobRunner) -> ProcessingJob:
        await self._remove_expired()
        job = ProcessingJob(id=uuid.uuid4().hex, owner_id=owner_id, kind=kind)
        async with self._lock:
            self._jobs[job.id] = job
        logger.info("job=%s kind=%s stage=queued", job.id, kind)
        asyncio.create_task(self._run(job, runner))
        return job

    async def get_for_user(self, job_id: str, owner_id: str) -> dict[str, Any]:
        async with self._lock:
            job = self._jobs.get(job_id)
        if not job or job.owner_id != owner_id:
            raise HTTPException(status_code=404, detail="No se encontró el trabajo solicitado.")
        payload: dict[str, Any] = {
            "job_id": job.id,
            "status": job.status,
            "progress": job.progress,
            "message": job.message,
        }
        if job.status == "completed":
            payload["result"] = job.result
        if job.status == "failed":
            payload["error"] = job.error or "El procesamiento no pudo completarse."
        return payload

    async def _run(self, job: ProcessingJob, runner: JobRunner) -> None:
        def update(progress: int, message: str) -> None:
            job.progress = max(job.progress, min(progress, 99))
            job.message = message
            logger.info("job=%s kind=%s progress=%s stage=%s", job.id, job.kind, job.progress, message)

        try:
            update(15, "Preparando el archivo...")
            result = await runner(update)
            job.result = result
            job.progress = 100
            job.message = "Transcripción terminada."
            job.status = "completed"
            logger.info("job=%s kind=%s stage=completed", job.id, job.kind)
        except HTTPException as exc:
            job.error = str(exc.detail)
            job.status = "failed"
            logger.warning("job=%s kind=%s stage=failed detail=%s", job.id, job.kind, job.error)
        except Exception:
            job.error = "Ocurrió un error interno durante el procesamiento."
            job.status = "failed"
            logger.exception("job=%s kind=%s stage=failed", job.id, job.kind)

    async def _remove_expired(self) -> None:
        cutoff = time.time() - 3600
        async with self._lock:
            stale_ids = [job_id for job_id, job in self._jobs.items() if job.created_at < cutoff]
            for job_id in stale_ids:
                self._jobs.pop(job_id, None)


job_service = JobService()
