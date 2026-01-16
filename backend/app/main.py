from __future__ import annotations

import asyncio
import json
import os
import urllib.request

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .config import settings
from .db import create_job, get_job, init_db
from .db import connect as db_connect
from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    AnalyzeUrlRequest,
    JobStatusResponse,
    PresignPutRequest,
    PresignPutResponse,
    UploadLocalResponse,
)
from .storage import Storage


def _build_storage() -> Storage:
    return Storage(
        driver=settings.storage_driver,  # type: ignore[arg-type]
        local_upload_dir=settings.local_upload_dir,
        s3_bucket=settings.s3_bucket,
        aws_region=settings.aws_region,
        s3_prefix=settings.s3_prefix,
        s3_public_base_url=settings.s3_public_base_url,
    )


app = FastAPI(title=settings.api_title)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

conn = db_connect(settings.sqlite_path)
init_db(conn)
storage = _build_storage()


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/v1/uploads/presign-put", response_model=PresignPutResponse)
def presign_put(req: PresignPutRequest) -> PresignPutResponse:
    if settings.storage_driver != "s3":
        raise HTTPException(status_code=400, detail="STORAGE_DRIVER must be s3 for presigned uploads")
    p = storage.presign_put(filename=req.filename, content_type=req.content_type)
    return PresignPutResponse(
        key=p.key,
        uploadUrl=p.upload_url,
        publicUrl=p.public_url,
        expiresInSeconds=p.expires_in_seconds,
    )


@app.post("/v1/uploads/local", response_model=UploadLocalResponse)
async def upload_local(file: UploadFile = File(...)) -> UploadLocalResponse:
    # Dev-friendly fallback when not using S3.
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Max file size is 5MB")
    key = storage.local_save_bytes(filename=file.filename or "upload.bin", data=data)
    return UploadLocalResponse(key=key)


@app.post("/v1/uploads/from-url", response_model=UploadLocalResponse)
def upload_from_url(req: AnalyzeUrlRequest) -> UploadLocalResponse:
    url = str(req.url)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if not content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="URL did not return an image")
            data = resp.read(5 * 1024 * 1024 + 1)
            if len(data) > 5 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="Max file size is 5MB")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {e}") from e

    filename = os.path.basename(url) or "url-image"
    if settings.storage_driver == "s3":
        key = storage.s3_put_bytes(filename=filename, content_type=content_type, data=data)
    else:
        key = storage.local_save_bytes(filename=filename, data=data)
    return UploadLocalResponse(key=key)


@app.post("/v1/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    # Enqueue a job (the worker will pick it up).
    if req.source not in ("s3", "local", "url"):
        raise HTTPException(status_code=400, detail="Invalid source")
    job = create_job(conn, image_key=req.key, image_source=req.source)
    return AnalyzeResponse(jobId=job.id, status=job.status)


@app.get("/v1/jobs/{job_id}", response_model=JobStatusResponse)
def job_status(job_id: str) -> JobStatusResponse:
    try:
        job = get_job(conn, job_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Job not found") from e
    return JobStatusResponse(jobId=job.id, status=job.status, error=job.error, result=job.result_json)


@app.get("/v1/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request) -> StreamingResponse:
    """
    Server-Sent Events (SSE): one long-lived connection that streams job status updates
    until the job is done/failed. This avoids client polling loops.
    """

    async def gen():
        # Tell EventSource how long to wait before reconnecting.
        yield "retry: 1000\n\n"

        while True:
            if await request.is_disconnected():
                return

            try:
                job = get_job(conn, job_id)
            except KeyError:
                yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"
                return

            payload = {"jobId": job.id, "status": job.status, "error": job.error, "result": job.result_json}
            yield f"data: {json.dumps(payload)}\n\n"

            if job.status in ("done", "failed"):
                return

            await asyncio.sleep(0.5)

    return StreamingResponse(gen(), media_type="text/event-stream")

