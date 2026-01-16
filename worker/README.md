# Worker (local models)

This worker process:

- polls `backend/data/app.db` for queued jobs
- loads models once, then processes images:
  - **CLIP**: food vs not-food
  - **Local VLM (default ON)**: dish + portion estimate (default: moondream2)
  - maps dish → `nutrition_db/nutrition.json`
  - computes nutrients and % values

## Install & run

```bash
cd worker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Smoke test (verify local models quickly)

```bash
python smoketest.py --image /path/to/your/image.jpg
```

## Environment

- `SQLITE_PATH`: defaults to `../backend/data/app.db`
- `STORAGE_DRIVER`: `local` (default) or `s3`
- `LOCAL_UPLOAD_DIR`: defaults to `../backend/data/uploads`
- `S3_BUCKET`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (for S3 mode)

Models:

- `CLIP_MODEL` (default `openai/clip-vit-base-patch32`)
- `VLM_MODEL` (default `vikhyatk/moondream2`)
- `DEVICE`: `auto` (default), `cpu`, or `cuda`

VLM controls:

- `USE_VLM`: `1` (default) enables dish/portion recognition. If `0`, the worker uses a **generic estimate** (no dish recognition).
- `VLM_LOAD_TIMEOUT_SECONDS`: max seconds to load VLM (default `300`)
- `VLM_INFER_TIMEOUT_SECONDS`: max seconds to run one VLM inference (default `300`)

Offline flags:

- `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`: force offline runtime (will fail if weights aren’t already cached)

## Offline mode (no internet at runtime)

Important: “local LLM/VLM” means inference is local, but you still need the **weights on disk**.
For Docker, we use the `hf_cache` volume.

### 1) Prefetch weights once (online)

```bash
docker compose --profile tools run --rm prefetch
```

### 2) Run offline

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 USE_VLM=1 DEVICE=cpu docker compose up --build
```


