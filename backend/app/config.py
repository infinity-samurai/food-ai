from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    api_title: str = "food-ai backend"

    # Storage
    storage_driver: str = os.getenv("STORAGE_DRIVER", "local")  # local | s3
    local_upload_dir: str = os.getenv("LOCAL_UPLOAD_DIR", os.path.abspath("./data/uploads"))

    s3_bucket: str | None = os.getenv("S3_BUCKET") or None
    aws_region: str | None = os.getenv("AWS_REGION") or None
    s3_prefix: str = os.getenv("S3_PREFIX", "uploads/")
    s3_public_base_url: str | None = os.getenv("S3_PUBLIC_BASE_URL") or None

    # DB
    sqlite_path: str = os.getenv("SQLITE_PATH", os.path.abspath("./data/app.db"))


settings = Settings()

