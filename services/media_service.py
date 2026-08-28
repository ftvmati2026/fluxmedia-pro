from __future__ import annotations

import asyncio
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile

from faster_whisper import WhisperModel

from services.cleanup_service import TempFileManager


VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(1024 * 1024 * 1024)))  # 1 GB default
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "1"))
ENABLE_DIARIZATION = os.getenv("ENABLE_DIARIZATION", "false").lower() in {"1", "true", "yes", "on"}
HF_TOKEN = os.getenv("HF_TOKEN", "").strip()
DIARIZATION_MODEL = os.getenv("DIARIZATION_MODEL", "pyannote/speaker-diarization-3.1")
OUTPUT_AUDIO_FORMAT = os.getenv("OUTPUT_AUDIO_FORMAT", "mp3").lower()


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str
    speaker: str | None = None


class MediaProcessingService:
    def __init__(self, temp_manager: TempFileManager) -> None:
        self.temp_manager = temp_manager
        self._whisper_model: WhisperModel | None = None
        self._diarization_pipeline: Any | None = None

    async def video_to_audio(self, file: UploadFile) -> tuple[str, str]:
        await self._validate_upload(file, allowed=VIDEO_EXTENSIONS)
        input_path = await self._persist_upload(file, suffix=Path(file.filename or "").suffix)
        output_suffix = ".mp3" if OUTPUT_AUDIO_FORMAT == "mp3" else ".wav"

        try:
            fd, raw_output = tempfile.mkstemp(suffix=output_suffix)
            os.close(fd)
            output_path = Path(raw_output)
            self.temp_manager.track(output_path)
            await asyncio.to_thread(self._extract_audio_ffmpeg, input_path, output_path)
            download_name = f"{Path(file.filename or 'audio').stem}{output_suffix}"
            return str(output_path), download_name
        finally:
            self.temp_manager.safe_delete(input_path)

    async def audio_to_text(self, file: UploadFile) -> dict[str, Any]:
        await self._validate_upload(file, allowed=AUDIO_EXTENSIONS)
        input_path = await self._persist_upload(file, suffix=Path(file.filename or "").suffix)
        try:
            segments, full_text = await asyncio.to_thread(self._transcribe, input_path)
            return {
                "text_full": self._format_transcript(segments, full_text),
                "segments": [segment.__dict__ for segment in segments],
                "language": "es",
                "model": WHISPER_MODEL_SIZE,
            }
        finally:
            self.temp_manager.safe_delete(input_path)

    async def video_to_text(self, file: UploadFile) -> dict[str, Any]:
        await self._validate_upload(file, allowed=VIDEO_EXTENSIONS)
        input_path = await self._persist_upload(file, suffix=Path(file.filename or "").suffix)
        try:
            with self.temp_manager.managed_temp_path(suffix=".mp3") as audio_path:
                await asyncio.to_thread(self._extract_audio_ffmpeg, input_path, audio_path)
                segments, full_text = await asyncio.to_thread(self._transcribe, audio_path)
                return {
                    "text_full": self._format_transcript(segments, full_text),
                    "segments": [segment.__dict__ for segment in segments],
                    "language": "es",
                    "model": WHISPER_MODEL_SIZE,
                }
        finally:
            self.temp_manager.safe_delete(input_path)

    async def _persist_upload(self, file: UploadFile, suffix: str) -> Path:
        fd, raw_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        path = Path(raw_path)
        self.temp_manager.track(path)
        total = 0

        try:
            with path.open("wb") as buffer:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_UPLOAD_SIZE_BYTES:
                        raise HTTPException(status_code=400, detail="El archivo supera el tamaño máximo permitido.")
                    buffer.write(chunk)
        except Exception:
            self.temp_manager.safe_delete(path)
            raise
        finally:
            await file.close()

        return path

    async def _validate_upload(self, file: UploadFile, allowed: set[str]) -> None:
        if not file.filename:
            raise HTTPException(status_code=400, detail="El archivo no tiene nombre.")

        ext = Path(file.filename).suffix.lower()
        if ext not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Formato no válido: {ext}. Formatos permitidos: {', '.join(sorted(allowed))}.",
            )

        content_type = (file.content_type or "").lower()
        if content_type and not self._looks_compatible_content_type(content_type, allowed):
            raise HTTPException(status_code=400, detail=f"Tipo MIME no compatible: {content_type}.")

    def _looks_compatible_content_type(self, content_type: str, allowed: set[str]) -> bool:
        if content_type.startswith("video/"):
            return any(ext in VIDEO_EXTENSIONS for ext in allowed)
        if content_type.startswith("audio/"):
            return any(ext in AUDIO_EXTENSIONS for ext in allowed)
        return True

    def _extract_audio_ffmpeg(self, input_path: Path, output_path: Path) -> None:
        if not shutil_which("ffmpeg"):
            raise HTTPException(status_code=500, detail="FFmpeg no está instalado o no está disponible en PATH.")

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-acodec",
            "libmp3lame" if output_path.suffix.lower() == ".mp3" else "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output_path),
        ]
        self._run_subprocess(cmd)

    def _run_subprocess(self, cmd: list[str]) -> None:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Falló el procesamiento FFmpeg: {proc.stderr.strip() or proc.stdout.strip() or 'error desconocido'}",
            )

    def _get_model(self) -> WhisperModel:
        if self._whisper_model is None:
            self._whisper_model = WhisperModel(
                WHISPER_MODEL_SIZE,
                device=WHISPER_DEVICE,
                compute_type=WHISPER_COMPUTE_TYPE,
            )
        return self._whisper_model

    def _transcribe(self, audio_path: Path) -> tuple[list[TranscriptSegment], str]:
        model = self._get_model()
        segments_iter, _ = model.transcribe(
            str(audio_path),
            language="es",
            task="transcribe",
            beam_size=WHISPER_BEAM_SIZE,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        raw_segments: list[tuple[float, float, str]] = []
        texts: list[str] = []
        for segment in segments_iter:
            text = segment.text.strip()
            if text:
                texts.append(text)
            raw_segments.append((float(segment.start), float(segment.end), text))

        speaker_turns = self._diarize(audio_path) if ENABLE_DIARIZATION else []
        segments = [
            TranscriptSegment(
                start=round(start, 2),
                end=round(end, 2),
                text=text,
                speaker=self._speaker_for_segment(start, end, speaker_turns),
            )
            for start, end, text in raw_segments
        ]
        return segments, " ".join(texts).strip()

    def _get_diarization_pipeline(self) -> Any:
        if self._diarization_pipeline is not None:
            return self._diarization_pipeline
        if not HF_TOKEN:
            raise HTTPException(
                status_code=500,
                detail="La identificación de personas requiere configurar HF_TOKEN y aceptar el modelo de diarización en Hugging Face.",
            )
        try:
            from pyannote.audio import Pipeline
            self._diarization_pipeline = Pipeline.from_pretrained(DIARIZATION_MODEL, token=HF_TOKEN)
            return self._diarization_pipeline
        except ImportError as exc:
            raise HTTPException(status_code=500, detail="Falta instalar pyannote.audio para identificar personas.") from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"No se pudo cargar el modelo de identificación de personas: {exc}") from exc

    def _diarize(self, audio_path: Path) -> list[tuple[float, float, str]]:
        pipeline = self._get_diarization_pipeline()
        diarization = pipeline(str(audio_path))
        raw_turns: list[tuple[float, float, str]] = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            raw_turns.append((float(turn.start), float(turn.end), str(speaker)))

        speaker_numbers: dict[str, str] = {}
        for _, _, raw_speaker in sorted(raw_turns, key=lambda item: item[0]):
            if raw_speaker not in speaker_numbers:
                speaker_numbers[raw_speaker] = f"Persona {len(speaker_numbers) + 1}"
        return [(start, end, speaker_numbers[speaker]) for start, end, speaker in raw_turns]

    def _speaker_for_segment(self, start: float, end: float, turns: list[tuple[float, float, str]]) -> str | None:
        if not turns:
            return None
        best_speaker: str | None = None
        best_overlap = 0.0
        for turn_start, turn_end, speaker in turns:
            overlap = max(0.0, min(end, turn_end) - max(start, turn_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = speaker
        return best_speaker

    def _format_transcript(self, segments: list[TranscriptSegment], fallback_text: str) -> str:
        if not any(segment.speaker for segment in segments):
            return self._format_editorial_text(fallback_text)

        blocks: list[str] = []
        current_speaker: str | None = None
        current_text: list[str] = []
        for segment in segments:
            if not segment.text:
                continue
            if current_speaker is not None and segment.speaker != current_speaker:
                blocks.append(f"{current_speaker}:\n{self._format_editorial_text(' '.join(current_text))}")
                current_text = []
            current_speaker = segment.speaker or current_speaker or "Persona desconocida"
            current_text.append(segment.text)
        if current_text:
            blocks.append(f"{current_speaker}:\n{self._format_editorial_text(' '.join(current_text))}")
        return "\n\n".join(blocks)

    def _format_editorial_text(self, text: str) -> str:
        """Applies conservative editorial cleanup without inventing content."""
        normalized = re.sub(r"\s+", " ", text).strip()
        if not normalized:
            return ""

        normalized = re.sub(r"\s+([,.;:!?])", r"\1", normalized)
        normalized = re.sub(r"([,.;:!?])(?=[A-Za-zÁÉÍÓÚÜÑáéíóúüñ])", r"\1 ", normalized)
        normalized = re.sub(r"([.!?])\s*", r"\1 ", normalized).strip()

        sentences = re.split(r"(?<=[.!?])\s+", normalized)
        cleaned_sentences: list[str] = []
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            sentence = sentence[0].upper() + sentence[1:]
            cleaned_sentences.append(sentence)

        paragraphs: list[str] = []
        for index in range(0, len(cleaned_sentences), 4):
            paragraphs.append(" ".join(cleaned_sentences[index:index + 4]))
        return "\n\n".join(paragraphs)


def shutil_which(command: str) -> str | None:
    from shutil import which

    return which(command)
