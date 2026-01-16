# Food Image Nutrition AI - Performance Upgrade Release Plan (12 weeks)

This document is a **phase-based, 3‑month (12‑week)** plan to measurably improve **accuracy + reliability + offline capability** of the food-image nutrition project.

It mirrors a structured “foundation → accuracy improvement → production release” approach similar to the provided template.

## Project goals (measurable)

By end of Week 12:

- **Food vs not-food**
  - Precision ≥ 95%
  - Recall ≥ 95%
  - Measured on a fixed offline eval set + ongoing live feedback set
- **Dish recognition (supported dish list)**
  - Top‑1 ≥ 70% (for top 200 dishes)
  - Top‑3 ≥ 85% (for top 200 dishes)
  - “Unknown dish” rate increases (instead of wrong answers) when confidence is low
- **Nutrition estimation**
  - Calories/macros median error ≤ 20% on portion-labeled eval set (use ranges when uncertain)
  - Macro/calorie consistency checks pass ≥ 99%
- **Reliability**
  - 99% jobs complete (no infinite `in_progress`)
  - P95 time-to-result ≤ 8s CPU-only (or ≤ 3s GPU)
- **Offline**
  - `prefetch` + offline flags pass a “no-network” test; inference uses local weights only

## Project timeline overview

| Phase | Duration | Focus |
| --- | --- | --- |
| Phase 1 | Weeks 1–4 | Data, Evaluation Harness, Baselines |
| Phase 2 | Weeks 5–8 | Accuracy Improvements & Validation |
| Phase 3 | Weeks 9–12 | Production Release, Monitoring, Offline Proof |

---

## Phase 1: Foundation & Baseline (Weeks 1–4)

### Week 1: Requirements, Metrics, Data Audit

**Goals**

- Define what “accuracy” means for this project and how it will be measured offline.
- Build the dataset plan and label schema to prevent guesswork on thresholds.

**Tasks**

- Define success metrics:
  - Food gate: precision/recall at chosen threshold(s)
  - Dish recognition: Top‑1/Top‑3 on supported dish list
  - Nutrition: error vs labeled ground truth (calories/macros) using portion/grams labels
  - Latency: queue time vs inference time
- Decide scope:
  - Supported dish list size (start 200)
  - Which nutrients are “must have” (calories, carbs, protein, fat; optional sodium/fiber/etc.)
- Data audit:
  - Collect examples of your real input distribution (phone photos, screenshots, restaurant menus, packaging, etc.)
  - Identify “hard negatives” (non-food that looks like food)

**Deliverables**

- `docs/metrics.md`: metric definitions + targets
- `docs/label_schema.md`: labeling format for food/non-food + dish + portion
- Dataset plan + annotation instructions v1

---

### Week 2: Offline Evaluation Harness (first version)

**Goals**

- Make evaluation repeatable: every model/threshold change can be compared to baseline.

**Tasks**

- Create an offline eval harness (CLI) to run:
  - Food classifier on images → metrics + confusion matrix
  - Dish recognition on food images → top‑k accuracy
  - Nutrition mapping (dish → DB) → coverage stats
- Define dataset splits:
  - Train/validation/test with fixed random seed
- Add structured logging fields:
  - `clip_food_confidence`, `food_threshold`, `vlm_confidence`, `match_score`, `fallback_reason`, latency breakdown

**Deliverables**

- `tools/eval/` scripts + `results/` output format
- Baseline report v0 (current behavior)

---

### Week 3: Baseline Models + Threshold Calibration (baseline locked)

**Goals**

- Stop guessing thresholds; pick them from a validation set.

**Tasks**

- Food gate:
  - Evaluate current CLIP prompts/labels on the dataset
  - Calibrate probability (temperature scaling / Platt scaling) if needed
  - Choose threshold(s) by objective:
    - “Reject more” mode (precision-first) vs “accept more” mode (recall-first)
- Dish recognition baseline:
  - Measure “% valid JSON”, “unknown rate”, and top‑k accuracy
- Nutrition baseline:
  - Measure DB match coverage and “generic fallback rate”

**Deliverables**

- Baseline thresholds documented + committed
- Baseline model + config frozen (Phase 1 sign-off target)

---

### Week 4: Baseline Review & Sign-off

**Goals**

- Align expected product behavior:
  - When to say “not food”
  - When to say “unknown dish”
  - How to represent uncertainty

**Tasks**

- Stakeholder review (UX + engineering):
  - Confirm “unknown” UX behavior
  - Confirm nutrition is estimate with warnings
- Finalize v1 supported dish list (top 200) and portion priors table (bowl/slice/piece)

**Deliverables**

- Approved baseline behavior + UX decision log
- Phase 1 sign-off

---

## Phase 2: Accuracy Improvement & Validation (Weeks 5–8)

### Week 5: Food Gate Improvements (hard negatives + classifier head)

**Goals**

- Increase food/not-food precision/recall with fewer false positives (esp. packaging/menus).

**Tasks**

- Replace 2-label CLIP prompt approach with one of:
  - Multi-class prompt set (food / dish / ingredient / packaging / menu / non-food)
  - Train a lightweight classifier head on CLIP embeddings (logistic regression / small MLP)
- Hard-negative mining:
  - Add “confusing negatives” to the dataset each week based on failures
- Add “reject option”:
  - If confidence too low, return “Not sure” and ask for another image (optional UI step)

**Deliverables**

- Food gate model v2 + updated threshold + report

---

### Week 6: Dish Recognition Improvements (constrain + rerank)

**Goals**

- Reduce wrong dish names; increase “unknown” when uncertain.

**Tasks**

- Constrain outputs to a controlled dish vocabulary:
  - VLM proposes top candidates + confidence
  - Deterministic matcher maps to supported dish list (fuzzy + embeddings)
- Add reranking:
  - Score candidates by match score + ingredient hints + cuisine hints
- Add JSON schema validation + repair

**Deliverables**

- Dish recognition pipeline v2
- Top‑1/Top‑3 report improvement vs baseline

---

### Week 7: Portion Estimation + Nutrition Range Outputs

**Goals**

- Improve nutrition accuracy by reducing portion errors and using honest ranges.

**Tasks**

- Add portion estimation output shape:
  - `{ portion_label, grams_min, grams_max }` or S/M/L with priors
- Nutrition:
  - Compute nutrients for min/max grams → return ranges
  - Enforce calorie/macros consistency checks
- Expand dish DB coverage:
  - Top 200 dishes: add variants (fried vs grilled, with/without sauce)

**Deliverables**

- Portion priors table v1
- Nutrition ranges + sanity checks
- Expanded DB v2

---

### Week 8: Business Validation + UX iteration

**Goals**

- Validate improvements with real user images and UX acceptance.

**Tasks**

- Add “Was this correct?” feedback in UI (opt-in):
  - food/not-food
  - dish choice from list
  - portion class (S/M/L)
- Run a controlled pilot:
  - track acceptance rate, correction rate, fallback rate

**Deliverables**

- Validation report + updated targets
- Phase 2 sign-off

---

## Phase 3: Production Release & Monitoring (Weeks 9–12)

### Week 9: Production Pipeline & Versioning

**Goals**

- Make improvements safe to deploy and rollback.

**Tasks**

- Version:
  - model versions (CLIP head / VLM)
  - nutrition DB versions
  - thresholds/config versions
- Add stored analysis metadata for auditing:
  - inference time, fallback reasons, scores, model versions

**Deliverables**

- Versioned pipeline + migration plan

---

### Week 10: Performance Optimization (latency + memory)

**Goals**

- Make it fast and stable under load.

**Tasks**

- CPU optimization:
  - quantize VLM (4-bit/8-bit where supported)
  - limit max tokens; reduce image resolution safely
- Concurrency controls:
  - limit number of in-flight jobs per worker
- Warmup:
  - load models on startup; preheat with a dummy image

**Deliverables**

- P95 latency report; no OOM; stable throughput

---

### Week 11: Monitoring, Drift, and Governance

**Goals**

- Detect regressions quickly.

**Tasks**

- Monitoring dashboards:
  - food/not-food rate changes
  - unknown dish rate
  - average calories/macros distribution drift
  - failure rate + timeout rate
- Drift checks:
  - weekly eval run on fixed test set
  - alert on metric drop beyond thresholds

**Deliverables**

- Monitoring dashboards + runbook

---

### Week 12: Offline Proof + Release + Post‑Launch Review

**Goals**

- Prove “offline inference” and ship.

**Tasks**

- Offline proof test:
  - Run `docker compose run --rm prefetch` once
  - Restart with `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`
  - Run with networking disabled (CI or documented manual steps)
- Final acceptance:
  - meet targets or document gaps + next-quarter roadmap

**Deliverables**

- Production release checklist
- Offline proof report
- Final project report + roadmap

---

## Summary

This 12‑week plan delivers measurable improvements through structured phases:

1) **Foundation** (data + eval harness + baselines)  
2) **Accuracy improvements** (food gate, dish recognition, portion/nutrition grounding)  
3) **Production + offline** (performance, monitoring, offline proof)  

