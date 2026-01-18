# food-ai (local, no external API calls)

End-to-end MVP inspired by `analyze.food` (everything runs on your own machine/servers — no OpenAI / external inference APIs):

- Frontend (Next.js): upload image / paste URL, preview, analyze, display nutrition cards
- Backend (FastAPI): presigned upload (S3) or local upload fallback, enqueue analysis jobs, job status API
- Worker (Python): runs **local models** (CLIP + local VLM), maps to a **local nutrition DB**, returns estimated nutrition

## Project link

- `https://github.com/<your-org-or-user>/food-ai` (update this)

## Performance upgrade plan (template)

- See `docs/FoodAI_Performance_Release_Plan.md`

## Week 1 (Jan 16) foundation docs (implemented)

- `docs/metrics.md`
- `docs/label_schema.md`
- `docs/dataset_plan_week1.md`
- `datasets/labels_template.csv`

## Week 1 code (implemented): offline eval harness starter

Food vs not-food gate evaluation (CLIP), using your labeled CSV:

```bash
python3 tools/eval/food_gate_eval.py \
  --labels datasets/labels.csv \
  --images-dir datasets/images \
  --device cpu \
  --out results_food_gate.json
```

## Accuracy Improvement Features (current)

1. **Local inference pipeline (no external LLM APIs)**
   - CLIP: food vs not-food
   - Local VLM: dish + portion estimate
   - Nutrition is computed from a local DB (reduces hallucinations)

2. **Streaming results (no polling loop from the browser)**
   - Uses SSE: `GET /v1/jobs/{job_id}/events`

3. **Guardrails + fallbacks**
   - Per-stage timeouts for VLM load/inference
   - If VLM fails, job still completes with a generic estimate + `notes` explaining why

4. **Offline-ready workflow**
   - `docker compose run --rm prefetch` downloads weights into the `hf_cache` volume
   - Runtime can be forced offline with `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`

## Run with Docker (one command)

This uses **local directory uploads** (no S3).

Copy the example env file:

```bash
cp env.example .env  # or copy env vars manually if your environment blocks dot-env files
```

```bash
docker compose up --build
```

Then open the frontend at `http://localhost:3000` and the API at `http://localhost:8000`.

Notes:

- First run will take time because the worker downloads local model weights into the `hf_cache` docker volume.
- Uploads + job DB live in the `foodai_data` docker volume.
- If a job gets stuck in `in_progress`, check `docker compose logs -f worker` (it will show whether the VLM is downloading/loading).
- **Speed**: by default Docker runs with `FAST_MODE=1` (CLIP-only dish selection) to keep analysis typically under ~10s on CPU. Set `FAST_MODE=0 USE_VLM=1` if you want to attempt VLM dish recognition (slower on CPU).

### 1) Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2) Worker

```bash
cd worker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### 3) Frontend

```bash
cd frontend
npm run dev
```

Set in your shell (or `.env.local`):

```bash
export NEXT_PUBLIC_API_BASE=http://localhost:8000
```

## Best architecture for “90%+ accuracy” offline (practical)

To hit high reliability, don’t rely on a single model output. Use a pipeline:

A) **Food gate** (deterministic-ish)

- CLIP embedding + calibrated threshold (trained on your dataset)

B) **Dish recognition** (local VLM)

- Generate structured JSON: `{ dish_name, portion_label, confidence }`
- Confidence gating: if low confidence, return `Unknown dish` instead of a wrong dish

C) **Nutrition grounding** (local database)

- Map dish → DB entry (fuzzy/embedding match)
- Portion model → grams range → nutrients range
- Sanity checks: calorie/macros consistency; clamp outliers

D) **Validator + Fixer (deterministic code)**

- Schema validation (always return valid JSON)
- Constraint checks (max sodium, forbidden allergens, etc.)

This yields measurable “accuracy” targets:

- ≥ 95% food/not-food precision/recall on your traffic
- ≥ 90% schema-valid outputs
- ≥ 90% constraint satisfaction (no forbidden ingredients, bounds, etc.)

## How to download once and run fully offline

1) **Prefetch (one time; requires internet)**

```bash
docker compose --profile tools run --rm prefetch
docker compose --profile tools run --rm prefetch
```

2) **Run offline**

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 USE_VLM=1 DEVICE=cpu docker compose up --build
```

## Offline test harness plan (1 quarter)

What to measure (realistic “90%+” goals):

- **Food vs not-food**
  - precision / recall / ROC; hard-negatives (packaging, menus, drawings)
- **Dish recognition**
  - Top‑1 / Top‑3 accuracy on a fixed dish list (start 200)
  - “Unknown” rate for low-confidence cases (should increase instead of wrong answers)
- **Nutrition estimate**
  - Macro/calorie error vs a labeled portion dataset (use ranges when uncertain)
- **Reliability**
  - % jobs completed (no infinite `in_progress`)
  - P95 time-to-result

Datasets (offline-friendly):

- **Food vs not-food**: Food‑101 + a curated non-food set (COCO/OpenImages samples)
- **Dish recognition**: UECFOOD‑256 (or your curated dish set)
- **Nutrition**: your own labeled images with portion/grams + FoodData‑style DB locally

## Run (S3 mode)

Export:

```bash
export STORAGE_DRIVER=s3
export S3_BUCKET=your-bucket
export AWS_REGION=your-region
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export NEXT_PUBLIC_API_BASE=http://localhost:8000
```

Then start backend/worker/frontend as above.

## Notes / accuracy

Nutrition from a photo is always an **estimate** (portion size and ingredients are uncertain). This MVP:

- rejects non-food images
- guesses dish + portion (via local VLM)
- computes nutrition from a local database per 100g

