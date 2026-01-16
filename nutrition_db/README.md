# Nutrition DB (local)

This folder contains a small **local nutrition dataset** used by the worker to convert a recognized dish into estimated nutrients.

## Data model

Each entry in `nutrition.json` provides nutrients **per 100g** plus optional `aliases`.

The worker:

- fuzzy-matches the model’s `dish_name` to `name`/`aliases`
- estimates portion grams
- multiplies nutrients accordingly
- computes macro % of calories and %DV

This is intentionally an MVP dataset you can expand over time (or replace with a larger dataset such as USDA SR Legacy / FoodData Central exported locally).

