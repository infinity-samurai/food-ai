from __future__ import annotations

import argparse
import json

from PIL import Image

from config import settings
from models import ClipFoodDetector, LocalVLM
from nutrition import (
    best_match_with_score,
    compute_nutrition,
    daily_value_percent,
    estimate_portion_grams,
    load_nutrition_db,
    macro_percent_of_calories,
)


def main() -> None:
    p = argparse.ArgumentParser(description="Smoke test local models (CLIP + VLM) on an image.")
    p.add_argument("--image", required=True, help="Path to an image file (jpg/png/webp/etc).")
    args = p.parse_args()

    image = Image.open(args.image).convert("RGB")

    print(f"[smoketest] device={settings.device}")
    print(f"[smoketest] clip_model={settings.clip_model}")
    print(f"[smoketest] vlm_model={settings.vlm_model}")

    clip = ClipFoodDetector(settings.clip_model, device=settings.device)
    food = clip.predict(image)

    out: dict = {
        "clip": {"is_food": food.is_food, "food_confidence": round(food.food_confidence, 4)},
    }

    if not (food.is_food and food.food_confidence >= settings.food_threshold):
        out["result"] = {"is_food": False, "message": "Image is not food (by CLIP threshold)"}
        print(json.dumps(out, indent=2))
        return

    vlm = LocalVLM(settings.vlm_model, device=settings.device)
    desc = vlm.describe_food_json(image)
    out["vlm"] = desc

    entries = load_nutrition_db(settings.nutrition_db_path)
    entry, score = best_match_with_score(str(desc.get("dish_name") or "food"), entries)
    grams = estimate_portion_grams(str(desc.get("portion_label") or "1 serving"))
    n = compute_nutrition(entry, grams)

    out["mapped_entry"] = {"id": entry.id, "name": entry.name, "portion_grams": grams, "match_score": score}
    out["nutrition"] = n
    out["macro_percent_of_calories"] = macro_percent_of_calories(n)
    out["daily_value_percent"] = daily_value_percent(n)

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

