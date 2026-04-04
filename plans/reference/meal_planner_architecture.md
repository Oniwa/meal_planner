# Meal Planner — Architecture Reference

## Context

The user wants a personal nutrition and meal planning web application powered by Claude AI. The pipeline has **two stages**:

1. **Dietitian Stage (Claude CLI)** — The user runs a separate Claude CLI conversation against a markdown agent definition (`dietitian_agent.md`) to figure out their personal nutrition plan. The output is a structured `nutrition_plan.json` file.
2. **Meal Planner Web App (Django)** — Imports the nutrition plan JSON, then generates weekly meal plans using a Meal Planner Agent. Plans can be regenerated weekly, individual meals can be swapped, and a consolidated shopping list is auto-generated.

**Stack:** Django + HTMX + Tailwind CSS (all via CDN, no build step)

**Database:** SQLite for MVP. If deployed, migrate to PostgreSQL — Django's `DATABASE_URL` / `dj-database-url` pattern makes this a config-only change.

---

## Architecture Overview

```
Phase 0 (POC — Claude CLI only)
────────────────────────────────────────
claude --agent dietitian_agent
        │
  nutrition_plans/<name>_<date>.json
        │
claude --agent meal_planner_agent
        │
  meal_plans/<name>_<date>.json


Phase 1+ (Django web app)
────────────────────────────────────────
Claude CLI (dietitian_agent)
        │
  nutrition_plans/<name>_<date>.json
        │
Browser (Django templates + HTMX)
        │
Django Views
        │
  Meal Planner Agent (Claude API)
  [system prompt sourced from .claude/agents/meal_planner_agent.md]
        │
  MealPlan + Recipes ──► ShoppingList
```

---

## Django Project Structure

```
meal_planner/
├── manage.py
├── .env                          # ANTHROPIC_API_KEY, SECRET_KEY (gitignored)
├── .env.example
├── requirements.txt
├── .claude/
│   └── agents/
│       ├── dietitian_agent.md    # Claude CLI agent — nutrition intake interview
│       └── meal_planner_agent.md # Claude CLI agent — weekly meal plan generation
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── nutrition/                # NutritionPlan model + import
│   │   ├── models.py             # NutritionPlan
│   │   ├── views.py              # Import JSON, view plan, edit plan
│   │   ├── urls.py
│   │   └── templates/nutrition/
│   │       ├── import.html       # Paste/upload nutrition_plan.json
│   │       └── plan_summary.html # View current plan
│   ├── meals/                    # Meal plans, recipes, ingredients
│   │   ├── models.py             # MealPlan, PlannedMeal, Recipe, Ingredient
│   │   ├── views.py              # Generate plan, show week, swap meal
│   │   ├── urls.py
│   │   └── templates/meals/
│   │       ├── week_plan.html    # Weekly plan grid
│   │       └── meal_detail.html  # Individual meal detail
│   ├── shopping/                 # Shopping list
│   │   ├── models.py             # ShoppingList, ShoppingItem
│   │   ├── views.py              # Show list, check off items
│   │   ├── urls.py
│   │   └── templates/shopping/
│   │       └── list.html
│   └── pantry/                   # Phase 2
│       ├── models.py             # Pantry, PantryItem
│       ├── views.py
│       ├── urls.py
│       └── templates/pantry/
│           └── pantry.html
├── ai/
│   ├── __init__.py
│   ├── client.py                 # Anthropic client singleton
│   ├── meal_planner_agent.py     # Build prompt from NutritionPlan, call API, parse JSON
│   └── prompts/
│       └── meal_planner.txt      # Meal plan generation prompt template
└── templates/
    └── base.html                 # HTMX, base layout, nav
```

---

## Data Models

### `nutrition` app

**NutritionPlan** (populated by importing `nutrition_plan.json` from Claude CLI)
```python
label: str                        # e.g. "My Plan - April 2026"
created_at: datetime
is_active: bool                   # only one active at a time

# Calorie & macro targets
daily_calories: int
protein_grams: int
carbs_grams: int
fat_grams: int

# Health flags
heart_healthy: bool
low_sodium: bool
low_sugar: bool
diabetic_friendly: bool
anti_inflammatory: bool

# Dietary restrictions
is_vegetarian: bool
is_vegan: bool
is_gluten_free: bool
is_dairy_free: bool

# Preferences (stored as JSON fields)
allergies: JSONField              # list[str]
disliked_foods: JSONField         # list[str]
liked_foods: JSONField            # list[str]
preferred_cuisines: JSONField     # list[str]

# Cooking style
max_cook_time_minutes: int
meal_prep_friendly: bool
cooking_skill_level: str          # "beginner" | "intermediate" | "advanced"
meal_variety: str                 # "high" | "medium" | "low" — drives repetition constraints in meal plan prompt
include_night_snack: bool         # whether to generate the optional night_snack slot
notes: TextField                  # any extra context captured by dietitian agent
```

### `meals` app

**MealPlan**
```python
nutrition_plan: FK(NutritionPlan)
week_start_date: DateField        # Monday of the week
generated_at: datetime
status: str                       # "active" | "archived"
```

**PlannedMeal** (one row per day × slot)
```python
meal_plan: FK(MealPlan)
recipe: FK(Recipe)
day_offset: int                   # 0=Monday … 6=Sunday; display label derived as week_start_date + timedelta(days=day_offset)
meal_slot: str                    # "breakfast" | "lunch" | "dinner" | "afternoon_snack" | "night_snack"
is_optional: bool                 # True for night_snack
was_swapped: bool
swap_reason: TextField(blank=True)
```

**Recipe**
```python
name: str
description: TextField
instructions: TextField
prep_time_minutes: int
cook_time_minutes: int
servings: int
meal_type: str                    # "breakfast" | "lunch" | "dinner" | "snack"
cuisine_type: str

# Nutrition per serving
calories: int
protein_grams: FloatField
carbs_grams: FloatField
fat_grams: FloatField
fiber_grams: FloatField(null=True)
sodium_mg: FloatField(null=True)

tags: JSONField                   # ["meal-prep", "heart-healthy", "quick"]
created_at: datetime
```

> **Note (servings):** The meal plan agent is instructed to generate ingredient quantities for exactly 1 serving. Shopping list aggregation treats all quantities as single-serving — `recipe.servings` is display-only in MVP. Future: add `servings_consumed: int` to `PlannedMeal` (defaulting to `recipe.servings`) and scale ingredient quantities accordingly when building the shopping list.

> **Note (deduplication):** Each generation always creates a new `Recipe` row — no deduplication. The same dish generated across multiple weeks will produce duplicate rows. Recipe deduplication (by name, ingredient fingerprint, etc.) is deferred to a future phase.

**Ingredient**
```python
recipe: FK(Recipe)
name: str
quantity: FloatField
unit: str                         # "oz", "cup", "tbsp"
notes: str(blank=True)
category: str                     # "protein" | "produce" | "dairy" | "pantry"
```

### `shopping` app

**ShoppingList**
```python
meal_plan: OneToOneField(MealPlan)
generated_at: datetime
```

**ShoppingItem**
```python
shopping_list: FK(ShoppingList)
ingredient_name: str
total_quantity: FloatField
unit: str
category: str                     # for grouping (produce, protein, dairy, etc.)
is_checked: bool
notes: str(blank=True)
```

### `pantry` app (Phase 2)

**PantryItem**
```python
ingredient_name: str
quantity: FloatField
unit: str
expiry_date: DateField(null=True)
last_updated: datetime
```

---

## Agent Design

### Dietitian Agent (`dietitian_agent.md` — Claude CLI, run separately)

A markdown agent definition file used with `claude --agent dietitian_agent.md`. The agent:
1. Asks for the person's name at the start of the interview
2. Conducts a conversational intake interview (health goals, restrictions, preferences, cooking style)
3. At the end writes `nutrition_plans/<name>_<YYYY-MM-DD>.json` (e.g. `nutrition_plans/john_2026-04-03.json`) and prints the JSON to the terminal
4. The user then imports that JSON into the web app via `/nutrition/import/` (paste or file upload)

**`nutrition_plans/` directory** lives at the project root and is gitignored (contains personal health data). Multiple people can run the dietitian agent independently — each plan is namespaced by person and date, so no files are overwritten.

**Output schema** (`nutrition_plans/<name>_<date>.json`):
```json
{
  "name": "john",
  "label": "John - April 2026",
  "daily_calories": 2000,
  "protein_grams": 150,
  "carbs_grams": 200,
  "fat_grams": 65,
  "heart_healthy": true,
  "is_gluten_free": false,
  "allergies": ["peanuts"],
  "disliked_foods": ["cilantro"],
  "liked_foods": ["salmon", "quinoa"],
  "preferred_cuisines": ["Mediterranean"],
  "max_cook_time_minutes": 45,
  "meal_prep_friendly": true,
  "cooking_skill_level": "intermediate",
  "meal_variety": "medium",
  "include_night_snack": false,
  "notes": "..."
}
```

### Meal Planner Agent (`ai/meal_planner_agent.py`)

**Input:** `NutritionPlan` instance
**Output:** Full week JSON → parsed into `MealPlan`, `PlannedMeal`, `Recipe`, `Ingredient` rows

**Prompt strategy:**
- System role: expert meal prep chef and nutritionist
- User message: structured JSON of the nutrition plan + request for 7-day plan
- Demand JSON response with schema defined in prompt
- Request `daily_nutrition_summary` for validation

**Expected JSON shape:**
```json
{
  "week_plan": {
    "Monday": {
      "breakfast": { "name": "...", "calories": 420, "protein_grams": 32, ... "ingredients": [...] },
      "lunch": { ... },
      "dinner": { ... },
      "afternoon_snack": { ... },
      "night_snack": { ... }
    }
  },
  "daily_nutrition_summary": {
    "Monday": { "calories": 1980, "protein": 145, "carbs": 198, "fat": 64 }
  }
}
```

**Validation:** Check daily totals are within ±15% of targets. Retry once with a correction message if not.

**Swap method:** `generate_swap(planned_meal, reason=None)` — sends focused single-meal prompt with existing meal excluded, returns new `Recipe`.

---

## Key Views & URLs

```
GET  /                          → redirect to /nutrition/plan/ or /meals/
GET  /nutrition/import/         → paste/upload nutrition_plan.json
POST /nutrition/import/         → parse + save NutritionPlan
GET  /nutrition/plan/           → view current NutritionPlan summary

POST /meals/generate/           → generate new MealPlan for current week
GET  /meals/                    → current week plan view
GET  /meals/<week_start>/       → specific week plan view
POST /meals/swap/               → swap a specific PlannedMeal (HTMX, returns updated row)

GET  /shopping/                 → shopping list for current week
POST /shopping/check/           → toggle item checked (HTMX)

GET  /pantry/                   → pantry view (Phase 2)
POST /pantry/add/               → add item (Phase 2)
```

---

## Frontend (Django Templates + HTMX)

- **`base.html`**: HTMX CDN + Tailwind CSS CDN, basic nav (Nutrition Plan | Meal Plan | Shopping | Pantry)
- **`nutrition/import.html`**: Textarea to paste `nutrition_plan.json`, or file upload. Submit saves to DB.
- **`nutrition/plan_summary.html`**: Card display of current plan goals, preferences, health flags.
- **`meals/week_plan.html`**: 7-column grid (one per day), 5 rows (one per meal slot). Each cell shows meal name + calories. Click to see detail. "Swap" button per cell (HTMX POST → replaces cell in-place).
- **`shopping/list.html`**: Grouped by category, checkboxes via HTMX POST. Print-friendly CSS class.

---

## Critical Files

- `dietitian_agent.md` — Claude CLI agent definition; quality of the intake conversation + JSON output schema
- `ai/prompts/meal_planner.txt` — JSON schema definition + constraints = meal plan quality
- `ai/meal_planner_agent.py` — JSON parse + validation + retry logic
- `apps/nutrition/models.py` — NutritionPlan schema feeds every downstream agent call
- `apps/meals/models.py` — Recipe + Ingredient are central; schema must be stable

---

## Verification Checklist

1. `python manage.py migrate` — all tables created clean
2. Run `claude` with `dietitian_agent.md` → complete intake conversation → `nutrition_plan.json` written
3. Visit `/nutrition/import/` → paste JSON → NutritionPlan saved, redirected to plan summary
4. Visit `/meals/` → click "Generate Week Plan" → week grid populated with 7 days × 5 meal slots
5. Click "Swap" on any meal → cell updates in-place with a new meal suggestion
6. Visit `/shopping/` → all ingredients consolidated, grouped by category
7. Check off items → persisted via HTMX POST
