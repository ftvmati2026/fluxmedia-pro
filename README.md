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

## Despliegue publico

El repositorio incluye `Dockerfile`, `.dockerignore` y `render.yaml` para desplegar la aplicacion completa en Render. En produccion, configura `HF_TOKEN` y `ENABLE_DIARIZATION=true` si quieres identificar interlocutores.

Para una instancia pequena, se puede configurar `TRANSCRIPTION_PROVIDER=groq` y guardar `GROQ_API_KEY` como secreto del servicio. Asi la aplicacion no carga Whisper en el servidor y los usuarios no necesitan ninguna cuenta.

## Usuarios y planes

La autenticacion persistente usa Supabase. Ejecuta una sola vez el archivo `supabase_schema.sql` desde el SQL Editor del proyecto Supabase.

En Render configura estas variables privadas:

- `SUPABASE_URL`: URL del proyecto Supabase.
- `SUPABASE_ANON_KEY`: clave publica del proyecto.
- `SUPABASE_SERVICE_ROLE_KEY`: clave secreta del servidor. Nunca la publiques en GitHub.
- `MASTER_EMAIL`: tu cuenta Gmail maestra.
- `AUTH_REQUIRED=true`.

Activa Email provider y Google provider en Supabase Auth. En Google Cloud agrega como origen autorizado `https://fluxmedia-pro.onrender.com` y como redirect URI la callback que muestra Supabase en la configuracion del proveedor Google.

Los usuarios Gmail pueden registrarse con Google o con email y contrasena. El panel maestro permite otorgar `premium` por 30 dias o `lifetime` para acceso permanente.
