from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Literal

import boto3


StorageDriver = Literal["local", "s3"]


@dataclass(frozen=True)
class PresignPutResponse:
    key: str
    upload_url: str
    public_url: str | None
    expires_in_seconds: int


class Storage:
    def __init__(
        self,
        *,
        driver: StorageDriver,
        local_upload_dir: str,
        s3_bucket: str | None,
        aws_region: str | None,
        s3_prefix: str,
        s3_public_base_url: str | None,
    ) -> None:
        self.driver = driver
        self.local_upload_dir = local_upload_dir
        self.s3_bucket = s3_bucket
        self.aws_region = aws_region
        self.s3_prefix = s3_prefix if s3_prefix.endswith("/") else f"{s3_prefix}/"
        self.s3_public_base_url = s3_public_base_url.rstrip("/") + "/" if s3_public_base_url else None

        self._s3 = None
        if self.driver == "s3":
            if not self.s3_bucket:
                raise ValueError("S3_BUCKET is required when STORAGE_DRIVER=s3")
            self._s3 = boto3.client("s3", region_name=self.aws_region)

    def presign_put(self, *, filename: str, content_type: str | None, expires_in_seconds: int = 300) -> PresignPutResponse:
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[1].lower()
        key = f"{self.s3_prefix}{uuid.uuid4().hex}{ext}"

        if self.driver != "s3":
            raise RuntimeError("presign_put is only available for STORAGE_DRIVER=s3")

        params = {"Bucket": self.s3_bucket, "Key": key}
        if content_type:
            params["ContentType"] = content_type

        upload_url = self._s3.generate_presigned_url(
            ClientMethod="put_object",
            Params=params,
            ExpiresIn=expires_in_seconds,
        )

        public_url = f"{self.s3_public_base_url}{key}" if self.s3_public_base_url else None
        return PresignPutResponse(key=key, upload_url=upload_url, public_url=public_url, expires_in_seconds=expires_in_seconds)

    def local_save_bytes(self, *, filename: str, data: bytes) -> str:
        os.makedirs(self.local_upload_dir, exist_ok=True)
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[1].lower()
        key = f"local/{uuid.uuid4().hex}{ext}"
        abs_path = os.path.join(self.local_upload_dir, key.replace("local/", ""))
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "wb") as f:
            f.write(data)
        return key

    def s3_put_bytes(self, *, filename: str, content_type: str | None, data: bytes) -> str:
        if self.driver != "s3":
            raise RuntimeError("s3_put_bytes requires STORAGE_DRIVER=s3")
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[1].lower()
        key = f"{self.s3_prefix}{uuid.uuid4().hex}{ext}"
        extra = {}
        if content_type:
            extra["ContentType"] = content_type
        self._s3.put_object(Bucket=self.s3_bucket, Key=key, Body=data, **extra)
        return key

    def local_resolve_key_to_path(self, key: str) -> str:
        if not key.startswith("local/"):
            raise ValueError("Not a local key")
        rel = key.replace("local/", "")
        return os.path.join(self.local_upload_dir, rel)

