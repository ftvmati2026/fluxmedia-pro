# FluxMedia Pro

Aplicacion web para extraer audio y transcribir video o audio en espanol con FastAPI, FFmpeg y faster-whisper.

## Funciones

- Video a audio MP3.
- Audio a texto.
- Video a texto.
- Identificacion opcional de interlocutores con pyannote.audio.

## Ejecucion local

```powershell
python -m venv .venv312
.\.venv312\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Abrir `http://127.0.0.1:8000`.

## Diarizacion opcional

Configurar `HF_TOKEN` y `ENABLE_DIARIZATION=true` como variables de entorno antes de iniciar el servidor.

## Requisitos

- Python 3.12 recomendado.
- FFmpeg disponible en PATH.
