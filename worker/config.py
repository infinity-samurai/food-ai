from __future__ import annotations

import os
from dataclasses import dataclass


def _default_sqlite_path() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, "..", "backend", "data", "app.db"))


def _default_local_upload_dir() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, "..", "backend", "data", "uploads"))


def _default_nutrition_db_path() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, "..", "nutrition_db", "nutrition.json"))


@dataclass(frozen=True)
class Settings:
    sqlite_path: str = os.getenv("SQLITE_PATH", _default_sqlite_path())
    nutrition_db_path: str = os.getenv("NUTRITION_DB_PATH", _default_nutrition_db_path())

    # Storage
    storage_driver: str = os.getenv("STORAGE_DRIVER", "local")  # local | s3
    local_upload_dir: str = os.getenv("LOCAL_UPLOAD_DIR", _default_local_upload_dir())
    s3_bucket: str | None = os.getenv("S3_BUCKET") or None
    aws_region: str | None = os.getenv("AWS_REGION") or None

    # Models
    clip_model: str = os.getenv("CLIP_MODEL", "openai/clip-vit-base-patch32")
    vlm_model: str = os.getenv("VLM_MODEL", "vikhyatk/moondream2")
    device: str = os.getenv("DEVICE", "auto")  # auto | cpu | cuda
    food_threshold: float = float(os.getenv("FOOD_THRESHOLD", "0.6"))

    poll_interval_seconds: float = float(os.getenv("POLL_INTERVAL_SECONDS", "0.5"))

    use_vlm: bool = os.getenv("USE_VLM", "1").strip().lower() not in ("0", "false", "no", "off")
    vlm_load_timeout_seconds: float = float(os.getenv("VLM_LOAD_TIMEOUT_SECONDS", "300"))
    # On CPU, 300s feels like a hang. Default to 60s and rely on CLIP fallback if needed.
    vlm_infer_timeout_seconds: float = float(os.getenv("VLM_INFER_TIMEOUT_SECONDS", "60"))

    # Speed/quality tradeoff: downscale images before CLIP/VLM.
    image_max_side: int = int(os.getenv("IMAGE_MAX_SIDE", "384"))

    # Fast mode: target <10s on CPU by skipping VLM and using CLIP-only dish selection + local DB.
    fast_mode: bool = os.getenv("FAST_MODE", "0").strip().lower() in ("1", "true", "yes", "on")


settings = Settings()

