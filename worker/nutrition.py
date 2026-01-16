from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz


@dataclass(frozen=True)
class NutritionEntry:
    id: str
    name: str
    aliases: list[str]
    per_100g: dict[str, float]
    ingredients: list[str]
    allergens: list[str]


def load_nutrition_db(path: str) -> list[NutritionEntry]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    entries: list[NutritionEntry] = []
    for e in data.get("entries", []):
        entries.append(
            NutritionEntry(
                id=e["id"],
                name=e["name"],
                aliases=e.get("aliases", []),
                per_100g=e["per_100g"],
                ingredients=e.get("ingredients", []),
                allergens=e.get("allergens", []),
            )
        )
    return entries


def normalize_name(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9\s\-\(\)]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def best_match_with_score(dish_name: str, entries: list[NutritionEntry]) -> tuple[NutritionEntry, int]:
    dish_norm = normalize_name(dish_name)
    best: tuple[int, NutritionEntry] | None = None

    for e in entries:
        candidates = [e.name] + list(e.aliases)
        score = 0
        for c in candidates:
            score = max(score, int(fuzz.token_set_ratio(dish_norm, normalize_name(c))))
        if best is None or score > best[0]:
            best = (score, e)

    if best is None:
        raise ValueError("Nutrition DB is empty")

    # If it's a weak match, fall back to generic entry if present.
    score, entry = best
    if score < 50:
        for e in entries:
            if e.id == "unknown_food_generic":
                return e, score
    return entry, score


def best_match(dish_name: str, entries: list[NutritionEntry]) -> NutritionEntry:
    entry, _score = best_match_with_score(dish_name, entries)
    return entry


def estimate_portion_grams(portion_label: str | None, *, default_grams: int = 300) -> int:
    if not portion_label:
        return default_grams

    s = portion_label.lower()
    # Look for explicit grams in the label.
    m = re.search(r"(\d{2,4})\s*g", s)
    if m:
        return int(m.group(1))

    # Look for simple counts like "6 pieces".
    count = 1
    m2 = re.search(r"(\d+)\s*(pieces|piece|slices|slice|wings|wing)", s)
    if m2:
        count = max(1, int(m2.group(1)))

    # Unit heuristics.
    unit_grams = default_grams
    if any(u in s for u in ["bowl"]):
        unit_grams = 520
    elif any(u in s for u in ["plate"]):
        unit_grams = 350
    elif any(u in s for u in ["slice"]):
        unit_grams = 110
    elif any(u in s for u in ["piece", "wing"]):
        unit_grams = 80
    elif any(u in s for u in ["cup"]):
        unit_grams = 240
    elif any(u in s for u in ["small"]):
        unit_grams = 250
    elif any(u in s for u in ["medium"]):
        unit_grams = 350
    elif any(u in s for u in ["large"]):
        unit_grams = 500

    return int(unit_grams * count)


def compute_nutrition(entry: NutritionEntry, portion_grams: int) -> dict[str, float]:
    factor = portion_grams / 100.0
    out: dict[str, float] = {}
    for k, v in entry.per_100g.items():
        out[k] = float(v) * factor
    return out


def default_portion_label(entry: NutritionEntry) -> str:
    name = entry.name.lower()
    if "ramen" in name or "soup" in name or "salad" in name:
        return "1 bowl"
    if "pizza" in name:
        return "1 slice"
    if "fried chicken" in name:
        return "3 pieces"
    if "burger" in name:
        return "1 serving"
    return "1 serving"


def generate_description(entry: NutritionEntry) -> str:
    if entry.ingredients:
        items = ", ".join(entry.ingredients[:4])
        return f"A {entry.name.lower()} featuring {items}."
    return f"A serving of {entry.name.lower()}."


def generate_health_note(n: dict[str, Any]) -> str:
    # Lightweight heuristic note (no medical claims).
    cal = float(n.get("calories_kcal") or 0)
    fiber = float(n.get("fiber_g") or 0)
    sodium = float(n.get("sodium_mg") or 0)
    notes: list[str] = []
    if cal and cal <= 250:
        notes.append("Lower in calories")
    if fiber and fiber >= 5:
        notes.append("higher in fiber")
    if sodium and sodium >= 800:
        notes.append("higher in sodium")
    if not notes:
        return "Nutrition values may vary by ingredients and portion size."
    return "This looks " + " and ".join(notes) + "."


def macro_percent_of_calories(n: dict[str, Any]) -> dict[str, float]:
    carbs_g = float(n.get("carbs_g") or 0.0)
    protein_g = float(n.get("protein_g") or 0.0)
    fat_g = float(n.get("fat_g") or 0.0)
    total_kcal = float(n.get("calories_kcal") or (carbs_g * 4 + protein_g * 4 + fat_g * 9))
    if total_kcal <= 0:
        return {"carbs_pct": 0.0, "protein_pct": 0.0, "fat_pct": 0.0}
    carbs_kcal = carbs_g * 4
    protein_kcal = protein_g * 4
    fat_kcal = fat_g * 9
    return {
        "carbs_pct": carbs_kcal / total_kcal,
        "protein_pct": protein_kcal / total_kcal,
        "fat_pct": fat_kcal / total_kcal,
    }


DV = {
    "carbs_g": 275.0,
    "protein_g": 50.0,
    "fat_g": 78.0,
    "fiber_g": 28.0,
    "sodium_mg": 2300.0,
    "cholesterol_mg": 300.0,
    "sat_fat_g": 20.0,
    "sugar_g": 50.0,  # DV for added sugars; used here as a rough reference
    "vitamin_c_mg": 90.0,
    "iron_mg": 18.0
}


def daily_value_percent(n: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for k, dv in DV.items():
        val = float(n.get(k) or 0.0)
        out[k.replace("_", "") + "Pct"] = min(1.0, val / dv) if dv > 0 else 0.0
    return out

