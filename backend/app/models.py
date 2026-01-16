from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class PresignPutRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=300)
    content_type: str | None = Field(default=None, max_length=200)


class PresignPutResponse(BaseModel):
    key: str
    uploadUrl: str
    publicUrl: str | None = None
    expiresInSeconds: int


class UploadLocalResponse(BaseModel):
    key: str


class AnalyzeRequest(BaseModel):
    key: str = Field(min_length=1, max_length=1024)
    source: str = Field(default="s3", max_length=20)  # s3 | local | url


class AnalyzeUrlRequest(BaseModel):
    url: HttpUrl


class AnalyzeResponse(BaseModel):
    jobId: str
    status: str


class JobStatusResponse(BaseModel):
    jobId: str
    status: str
    error: str | None = None
    result: dict | None = None

