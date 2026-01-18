# Dataset Plan (Week 1) — East / Southeast Asia

Purpose: create a fixed offline dataset to calibrate thresholds and measure improvements.

## Target size (initial)

Total: **2,000 images**

- **Food**: 1,000
- **Not food**: 1,000
  - at least **400 hard negatives**

This is enough to start threshold calibration and catch obvious regressions.

## Breakdown targets

### Food (1,000)
- **SEA/East Asia staples** (700)
  - rice bowls/plates (fried rice, bibimbap)
  - noodle soups (pho, ramen, laksa)
  - stir-fried noodles (pad thai)
  - curries (thai curry, japanese curry)
  - dumplings/dim sum
  - salads/light bowls
  - fried chicken variants
  - sandwiches (banh mi)
- **Desserts/drinks** (150)
  - boba / milk tea (note: beverage detection may be tricky)
  - shaved ice / cakes
- **Ambiguous food** (150)
  - soups with unclear contents
  - mixed plates / bento
  - food partially occluded

### Not food (1,000)
- **Hard negatives (400+)**
  - menus (text-only)
  - packaging (chips, instant noodles packs)
  - toy food / plastic
  - drawings/illustrations of food
  - grocery shelves
- **General non-food (600)**
  - people, pets, landscapes, objects

## Sources (recommended)

- Your own phone photos (best)
- Publicly licensed images (ensure legal use)
- Screenshots (menus, packaging pages) — for hard negatives

## Labeling workflow (minimum)

Use `docs/label_schema.md` and fill `datasets/labels_template.csv`.

Definition of “done for Week 1”:
- 500 labeled images minimum (balanced food/not-food)
- 100+ hard negatives included
- labels are consistent and reviewed once

