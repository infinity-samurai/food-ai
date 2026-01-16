# Backend (local inference, no external API calls)

This backend provides:

- **Upload support**
  - S3 presigned PUT uploads (recommended)
  - Local multipart upload fallback (for dev)
- **Async job API**
  - Create analysis jobs
  - Poll for status/results

The actual AI inference runs in the separate `worker/` process, using **local models** (no OpenAI / external API calls).

## Quickstart (local storage mode)

1) Create a venv and install deps:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Run the API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

3) Run the worker (in another terminal):

```bash
cd worker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## S3 mode (recommended)

Set environment variables:

- `STORAGE_DRIVER=s3`
- `S3_BUCKET=...`
- `AWS_REGION=...`
- `AWS_ACCESS_KEY_ID=...`
- `AWS_SECRET_ACCESS_KEY=...`

Optionally:

- `S3_PREFIX=uploads/`
- `S3_PUBLIC_BASE_URL=https://<your-cdn-or-bucket-domain>/` (used for display; optional)

