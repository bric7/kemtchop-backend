# Dockerfile - KemTchop Backend
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dépendances système pour FFmpeg et PostgreSQL
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Requirements
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Code
COPY . .

# Dossier pour uploads temporaires
RUN mkdir -p videos

EXPOSE 8000

# Démarrage
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]