from __future__ import annotations

import os

import boto3


class Storage:
    def __init__(
        self,
        *,
        driver: str,
        local_upload_dir: str,
        s3_bucket: str | None,
        aws_region: str | None,
    ) -> None:
        self.driver = driver
        self.local_upload_dir = local_upload_dir
        self.s3_bucket = s3_bucket
        self.aws_region = aws_region
        self._s3 = None
        if self.driver == "s3":
            if not self.s3_bucket:
                raise ValueError("S3_BUCKET is required when STORAGE_DRIVER=s3")
            self._s3 = boto3.client("s3", region_name=self.aws_region)

    def read_bytes(self, *, key: str) -> bytes:
        if key.startswith("local/"):
            path = self._local_path_from_key(key)
            with open(path, "rb") as f:
                return f.read()

        if self.driver == "s3":
            obj = self._s3.get_object(Bucket=self.s3_bucket, Key=key)
            return obj["Body"].read()

        raise ValueError("Unsupported storage/key combination. For local mode, key must start with 'local/'")

    def _local_path_from_key(self, key: str) -> str:
        rel = key.replace("local/", "")
        return os.path.join(self.local_upload_dir, rel)

