# Label Schema & Annotation Guide — Week 1

Target market: **East / Southeast Asia**.

## 1) What we label

Each image becomes one row (one example).

### Required fields
- **`image_id`**: unique id (filename is OK)
- **`source`**: `phone` | `web` | `screenshot`
- **`is_food`**: `1` (food) or `0` (not food)

### If `is_food=1`, also label:
- **`dish_label`**: one label from the **supported dish list** (start Top‑200), or `unknown`
- **`portion_label`**: `small` | `medium` | `large` | `unknown`
- **`portion_grams`** (optional): numeric grams if you know it, else blank
- **`notes`** (optional): free text, e.g. “multiple foods”, “very blurry”, “packaging visible”

### If `is_food=0`, also label:
- **`not_food_type`**: one of:
  - `person`
  - `animal`
  - `object`
  - `scene`
  - `text_menu`
  - `food_packaging`
  - `toy_food`
  - `drawing`
  - `kitchen_scene`
  - `other`

## 2) Definition: “food image”

Label **food** (`is_food=1`) if:
- a dish/ingredient is visible and would reasonably be eaten

Label **not food** (`is_food=0`) if:
- no edible food is visible (people, objects, scenery)
- only text/menu (even if it’s food-related)
- packaging is the main subject (unless actual prepared food is clearly visible)

Hard negatives (very important):
- menus
- food packaging
- grocery shelves
- toy food / plastic food
- drawings of food

## 3) Portion labeling rules (simple + consistent)

Use these heuristics (don’t overthink it):

- **small**: snack / half portion / small bowl / single item
- **medium**: typical single meal portion
- **large**: oversized portion / multiple servings / big tray

If you truly can’t tell: `unknown`.

## 4) East / Southeast Asia dish coverage guidance

Start with common categories:
- rice dishes (nasi goreng, fried rice, bibimbap)
- noodle soups (pho, ramen, laksa)
- stir-fried noodles (pad thai, chow mein)
- curries (thai curry, japanese curry)
- dumplings (gyoza, dim sum)
- street foods (satay, banh mi, spring rolls)

If the image contains multiple foods:
- pick the **dominant** dish (largest/central)
- add note: “multiple foods”

## 5) Quality flags (optional but useful)

Add tags to `notes`:
- `blurry`
- `low_light`
- `occluded`
- `multiple_items`
- `packaging_present`
- `text_present`

