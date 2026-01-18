from __future__ import annotations

import signal
import io
import time
import traceback
from contextlib import contextmanager

from PIL import Image

from config import settings
from db import claim_next_job, connect, init_db, set_job_error, set_job_result
from models import ClipFoodDetector, LocalVLM
from nutrition import (
    best_match_with_score,
    compute_nutrition,
    default_portion_label,
    daily_value_percent,
    estimate_portion_grams,
    generate_description,
    generate_health_note,
    load_nutrition_db,
    macro_percent_of_calories,
)
from storage import Storage


def _round_nutrition(n: dict[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    for k, v in n.items():
        if k.endswith("_mg"):
            out[k] = round(v)
        elif k.endswith("_kcal"):
            out[k] = round(v)
        else:
            out[k] = round(v, 1)
    return out


def main() -> None:
    print(f"[worker] sqlite={settings.sqlite_path}")
    print(f"[worker] storage_driver={settings.storage_driver}")
    print(f"[worker] device={settings.device}")
    print(f"[worker] clip_model={settings.clip_model}")
    print(f"[worker] vlm_model={settings.vlm_model}")
    print(f"[worker] use_vlm={settings.use_vlm}")
    print(f"[worker] fast_mode={settings.fast_mode}")

    conn = connect(settings.sqlite_path)
    init_db(conn)
    storage = Storage(
        driver=settings.storage_driver,
        local_upload_dir=settings.local_upload_dir,
        s3_bucket=settings.s3_bucket,
        aws_region=settings.aws_region,
    )

    nutrition_entries = load_nutrition_db(settings.nutrition_db_path)
    clip = ClipFoodDetector(settings.clip_model, device=settings.device)

    # Lazy-load VLM (it can be heavy).
    vlm: LocalVLM | None = None

    @contextmanager
    def alarm_timeout(seconds: float, label: str):
        # Unix-only, but our docker images are Linux.
        if seconds <= 0:
            yield
            return

        def handler(_signum, _frame):
            raise TimeoutError(f"{label} timed out after {seconds:.0f}s")

        old = signal.signal(signal.SIGALRM, handler)
        signal.alarm(int(seconds))
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)

    while True:
        job = claim_next_job(conn)
        if not job:
            time.sleep(settings.poll_interval_seconds)
            continue

        try:
            t0 = time.time()
            print(f"[worker] job={job.id} claimed key={job.image_key}")
            image_bytes = storage.read_bytes(key=job.image_key)
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            # Speed: downscale for model inference (keeps aspect ratio).
            model_image = image.copy()
            model_image.thumbnail((settings.image_max_side, settings.image_max_side))

            food_check = clip.predict(model_image)
            is_food = bool(food_check.is_food and food_check.food_confidence >= settings.food_threshold)
            print(
                f"[worker] job={job.id} clip_food_conf={food_check.food_confidence:.3f} is_food={is_food}"
            )

            if not is_food:
                result = {
                    "status": "done",
                    "is_food": False,
                    "message": "Image is not food",
                    "confidence": round(1.0 - food_check.food_confidence, 3),
                }
                set_job_result(conn, job.id, result)
                print(f"[worker] job={job.id} done (not food) in {time.time()-t0:.1f}s")
                continue

            dish_name = "food"
            portion_label = "1 serving"
            dish_conf = 0.35
            vlm_note: str | None = None
            description = ""
            health_note = ""

            if settings.fast_mode:
                vlm_note = "FAST_MODE=1: skipping VLM for speed; using CLIP dish selection."
                print(f"[worker] job={job.id} {vlm_note}")
                dish_name = "food"
            elif settings.use_vlm:
                try:
                    if vlm is None:
                        print(f"[worker] job={job.id} loading VLM model={settings.vlm_model} ...")
                        with alarm_timeout(settings.vlm_load_timeout_seconds, "VLM load"):
                            vlm = LocalVLM(settings.vlm_model, device=settings.device)
                        print(f"[worker] job={job.id} VLM loaded")

                    print(f"[worker] job={job.id} running VLM inference ...")
                    with alarm_timeout(settings.vlm_infer_timeout_seconds, "VLM inference"):
                        desc = vlm.describe_food_json(model_image)
                    dish_name = str(desc.get("dish_name") or "food")
                    portion_label = str(desc.get("portion_label") or "1 serving")
                    dish_conf = float(desc.get("confidence") or 0.5)
                    description = str(desc.get("description") or "").strip()
                    health_note = str(desc.get("health_note") or "").strip()
                    print(
                        f"[worker] job={job.id} vlm dish='{dish_name}' portion='{portion_label}' conf={dish_conf:.2f}"
                    )
                except Exception as e:
                    # IMPORTANT: Don't hang the UI forever.
                    # If VLM times out/fails, use a fast CLIP dish guess against the local DB labels.
                    vlm_note = f"VLM unavailable ({type(e).__name__}: {e}). Using CLIP fallback."
                    print(traceback.format_exc())
                    print(f"[worker] job={job.id} {vlm_note}")
            else:
                vlm_note = "VLM disabled (USE_VLM=0). Using generic estimate (no dish recognition)."
                print(f"[worker] job={job.id} {vlm_note}")

            # If VLM didn't produce a useful dish name, do a quick CLIP-based dish selection.
            if dish_name.strip().lower() in ("food", "unknown", ""):
                dish_texts: list[str] = []
                entry_for_text: list[str] = []
                for e in nutrition_entries:
                    # Prefer names over aliases for stability.
                    dish_texts.append(f"a photo of {e.name}")
                    entry_for_text.append(e.name)
                best_idx, best_prob = clip.top_text_match(model_image, dish_texts)
                dish_name = entry_for_text[best_idx]
                dish_conf = max(dish_conf, best_prob)

            entry, match_score = best_match_with_score(dish_name, nutrition_entries)
            # If VLM didn't provide a meaningful portion, use dish-aware default label for better UX.
            if not portion_label or portion_label.strip().lower() in ("1 serving", "serving"):
                portion_label = default_portion_label(entry)

            grams = estimate_portion_grams(portion_label, default_grams=350)
            n = compute_nutrition(entry, grams)
            n = _round_nutrition(n)

            # Confidence: VLM "confidence" can be unreliable. Blend it with the dish-name→DB match score.
            # This produces a more stable 0..1 confidence that better reflects "how grounded" the result is.
            match_conf = max(0.0, min(1.0, match_score / 100.0))
            calibrated_conf = max(0.0, min(1.0, 0.25 * dish_conf + 0.75 * match_conf))

            # Ideal UI text block: if VLM didn't generate it, create deterministic text from DB + nutrients.
            if not description:
                description = generate_description(entry)
            if not health_note:
                health_note = generate_health_note(n)

            result = {
                "status": "done",
                "is_food": True,
                "dish": entry.name,
                "model_dish_guess": dish_name,
                "confidence": round(calibrated_conf, 3),
                "notes": [vlm_note] if vlm_note else [],
                "description": description,
                "health_note": health_note,
                "portion": {"label": portion_label, "grams_estimate": grams},
                "nutrition": n,
                "macro_percent_of_calories": {k: round(v, 3) for k, v in macro_percent_of_calories(n).items()},
                "daily_value_percent": {k: round(v, 3) for k, v in daily_value_percent(n).items()},
                "ingredients": entry.ingredients,
                "potential_allergens": entry.allergens,
                "assumptions": [
                    f"Portion assumed from '{portion_label}' (~{grams}g)",
                    "Dish mapped from model output to local nutrition DB",
                ],
                "warning": "Nutrition is an estimate from a local database; actual values may vary.",
            }
            set_job_result(conn, job.id, result)
            print(f"[worker] job={job.id} done in {time.time()-t0:.1f}s")
        except Exception as e:
            tb = traceback.format_exc()
            set_job_error(conn, job.id, f"{e}\n{tb}")
            print(f"[worker] job={job.id} failed: {e}")


if __name__ == "__main__":
    main()

