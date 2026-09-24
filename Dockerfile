FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .

EXPOSE 10000
# Render supplies PORT at runtime. exec makes Uvicorn the container's main process.
CMD ["sh", "-c", "exec python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000} --timeout-keep-alive 75"]
