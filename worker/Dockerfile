FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/hf_cache

# Needed for HTTPS downloads from model hubs (one-time prefetch).
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# NOTE: this Dockerfile is intended to be built with the REPO ROOT as build context.
COPY worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY worker /app
COPY nutrition_db /app/nutrition_db

# Shared data volume with backend
ENV STORAGE_DRIVER=local \
    LOCAL_UPLOAD_DIR=/data/uploads \
    SQLITE_PATH=/data/app.db \
    NUTRITION_DB_PATH=/app/nutrition_db/nutrition.json \
    DEVICE=auto

CMD ["python", "main.py"]

