# Metrics & Success Criteria (Food AI) — Week 1

Target market: **East / Southeast Asia** (street food, home-cooked meals, bowls/noodles/rice dishes, mixed plates).

This doc defines what we measure and how we decide if an upgrade is “better”.

## 1) Food vs Not-food (Gate)

### Goal
Only run dish/nutrition estimation when the image is food.

### Metrics
- **Precision (food)**: of images predicted “food”, how many truly are food
- **Recall (food)**: of truly-food images, how many we detect as food
- **FPR on hard negatives**: packaging, menus, drawings, toy food, kitchen scenes, groceries

### Reporting
- Confusion matrix + ROC curve
- Breakdown by source: phone photo vs web image vs screenshot
- Breakdown by “hard negative” class

### Acceptance targets (Phase 1 baseline → Phase 2)
- Baseline: record current precision/recall at threshold \(t\)
- Improve to: **≥ 95% precision and ≥ 95% recall** on the fixed test set

## 2) Dish Recognition (Supported Dish List)

### Goal
Predict a dish label from a controlled vocabulary (start with Top‑200).

### Metrics
- **Top‑1 accuracy** (exact match)
- **Top‑3 accuracy** (acceptable if correct label appears in top 3 candidates)
- **Unknown rate**: % predictions gated to “Unknown dish” when confidence is low
- **Wrong‑but‑confident rate**: wrong predictions with confidence ≥ threshold (must go down)

### Acceptance targets
- Top‑1 ≥ 70% (Top‑200)
- Top‑3 ≥ 85% (Top‑200)
- Wrong‑but‑confident rate decreases week over week

## 3) Nutrition Estimation (Grounded in Local DB)

### Goal
Return reasonable macro estimates for the predicted dish and portion.

### Metrics (portion-labeled eval set only)
- **Calories error**: median absolute percentage error (MdAPE)
- **Macros error**: MdAPE for carbs/protein/fat
- **Coverage**: % of images mapped to a non-generic DB entry
- **Range quality** (future): % of ground truth within predicted ranges

### Acceptance targets
- MdAPE (calories/macros) ≤ 20% on portion-labeled set
- Coverage ≥ 80% for Top‑200 dishes

## 4) Reliability & Performance

### Metrics
- **Job completion rate**: % jobs that end in done/failed (no stuck in_progress)
- **Failure reasons**: timeouts, OOM, missing weights, decode errors
- **P95 time-to-result**: end-to-end (upload → response)

### Acceptance targets
- ≥ 99% jobs complete (done or failed with reason)
- P95 ≤ 8s CPU-only (or ≤ 3s GPU)

## 5) Offline Capability (No network at runtime)

### Definition
After model prefetch, inference must run with:
- `HF_HUB_OFFLINE=1`
- `TRANSFORMERS_OFFLINE=1`

### Metric
- “Offline run pass”: analysis succeeds with networking disabled

