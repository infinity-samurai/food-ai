FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app

# Runtime data (uploads + sqlite) will be mounted at /data
ENV STORAGE_DRIVER=local \
    LOCAL_UPLOAD_DIR=/data/uploads \
    SQLITE_PATH=/data/app.db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

