from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass

from PIL import Image

# Reuse the exact same model code as production worker.
from worker.models import ClipFoodDetector


@dataclass(frozen=True)
class Example:
    image_path: str
    is_food: int  # 1 or 0
    source: str
    not_food_type: str


def load_labels_csv(csv_path: str, images_dir: str) -> list[Example]:
    out: list[Example] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            image_id = (row.get("image_id") or "").strip()
            if not image_id:
                continue
            is_food = int((row.get("is_food") or "0").strip() or "0")
            source = (row.get("source") or "unknown").strip()
            not_food_type = (row.get("not_food_type") or "").strip()

            path = image_id
            if not os.path.isabs(path):
                path = os.path.join(images_dir, image_id)
            out.append(Example(image_path=path, is_food=is_food, source=source, not_food_type=not_food_type))
    return out


def precision_recall(scores: list[tuple[float, int]], threshold: float) -> dict[str, float]:
    # scores: (p_food, true_is_food)
    tp = fp = tn = fn = 0
    for p, y in scores:
        pred = 1 if p >= threshold else 0
        if pred == 1 and y == 1:
            tp += 1
        elif pred == 1 and y == 0:
            fp += 1
        elif pred == 0 and y == 0:
            tn += 1
        else:
            fn += 1

    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    acc = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) else 0.0
    return {"precision": prec, "recall": rec, "accuracy": acc, "tp": tp, "fp": fp, "tn": tn, "fn": fn}


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate food vs not-food gate (CLIP) across thresholds.")
    ap.add_argument("--labels", required=True, help="Path to CSV labels (see datasets/labels_template.csv).")
    ap.add_argument("--images-dir", required=True, help="Directory that contains the image files referenced by image_id.")
    ap.add_argument("--device", default="cpu", help="cpu|cuda|auto (default cpu)")
    ap.add_argument("--clip-model", default="openai/clip-vit-base-patch32")
    ap.add_argument("--max-examples", type=int, default=0, help="Optional cap for quick runs (0 = no cap).")
    ap.add_argument("--thresholds", default="0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9")
    ap.add_argument("--out", default="results_food_gate.json", help="Output JSON report path.")
    args = ap.parse_args()

    examples = load_labels_csv(args.labels, args.images_dir)
    if args.max_examples and args.max_examples > 0:
        examples = examples[: args.max_examples]

    detector = ClipFoodDetector(args.clip_model, device=args.device)

    scored: list[tuple[float, int]] = []
    missing = 0
    for ex in examples:
        if not os.path.exists(ex.image_path):
            missing += 1
            continue
        img = Image.open(ex.image_path).convert("RGB")
        pred = detector.predict(img)
        scored.append((float(pred.food_confidence), int(ex.is_food)))

    thresholds = [float(x.strip()) for x in args.thresholds.split(",") if x.strip()]
    report = {
        "labels_csv": os.path.abspath(args.labels),
        "images_dir": os.path.abspath(args.images_dir),
        "clip_model": args.clip_model,
        "device": args.device,
        "num_examples": len(examples),
        "num_scored": len(scored),
        "missing_images": missing,
        "threshold_results": {},
    }

    best = None
    for t in thresholds:
        r = precision_recall(scored, t)
        report["threshold_results"][str(t)] = r
        # Simple objective: maximize F1.
        prec = r["precision"]
        rec = r["recall"]
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
        if best is None or f1 > best["f1"]:
            best = {"threshold": t, "f1": f1, **r}

    report["best_by_f1"] = best

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(json.dumps({"out": args.out, "best_by_f1": best}, indent=2))


if __name__ == "__main__":
    main()

