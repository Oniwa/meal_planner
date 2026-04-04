# Phase 0 — Proof of Concept (Claude CLI Agents)

> Reference: [Architecture](../reference/meal_planner_architecture.md)

## Goal
Validate the full AI pipeline using Claude CLI only — no Django, no database, no web server. Two markdown agents that talk to each other via JSON files. Phase 1 only begins once the output quality of both agents is satisfactory.

## Pipeline

```
claude --agent dietitian_agent.md
        │
  nutrition_plans/<name>_<date>.json
        │
claude --agent meal_planner_agent.md
        │
  meal_plans/<name>_<date>.json
```

## Deliverables

### 1. `dietitian_agent.md`
A Claude CLI agent that:
- Asks for the person's name at the start
- Conducts a conversational intake interview (health goals, dietary restrictions, food preferences, cooking style, activity level)
- Produces a validated `nutrition_plans/<name>_<YYYY-MM-DD>.json` matching the `NutritionPlan` schema
- Prints the JSON to the terminal and writes it to the file

### 2. `meal_planner_agent.md`
A Claude CLI agent that:
- Asks which nutrition plan file to load (or defaults to the most recent in `nutrition_plans/`)
- Reads and parses the nutrition plan JSON
- Generates a full 7-day × 5-slot meal plan conforming to the plan's constraints
- Produces `meal_plans/<name>_<YYYY-MM-DD>.json` matching the `MealPlan` JSON schema (see below)
- Prints a human-readable summary of the week plan to the terminal
- Writes the full JSON to the file

### Output Directories
Both directories live at the project root and are gitignored (personal health data):
```
nutrition_plans/   # output of dietitian_agent.md
meal_plans/        # output of meal_planner_agent.md
```

## `meal_plans/` JSON Schema

This schema is the source of truth that `ai/meal_planner_agent.py` (Phase 1) will also consume:

```json
{
  "name": "john",
  "week_start_date": "2026-04-07",
  "generated_at": "2026-04-03T10:00:00",
  "week_plan": {
    "0": {
      "breakfast": {
        "name": "Greek Yogurt Parfait",
        "description": "...",
        "instructions": "...",
        "prep_time_minutes": 5,
        "cook_time_minutes": 0,
        "servings": 1,
        "meal_type": "breakfast",
        "cuisine_type": "American",
        "calories": 420,
        "protein_grams": 32.0,
        "carbs_grams": 45.0,
        "fat_grams": 10.0,
        "fiber_grams": 4.0,
        "sodium_mg": 120.0,
        "tags": ["meal-prep", "quick"],
        "ingredients": [
          { "name": "Greek yogurt", "quantity": 1.0, "unit": "cup", "category": "dairy", "notes": "" }
        ]
      },
      "lunch": { ... },
      "dinner": { ... },
      "afternoon_snack": { ... },
      "night_snack": { ... }
    },
    "1": { ... },
    "2": { ... },
    "3": { ... },
    "4": { ... },
    "5": { ... },
    "6": { ... }
  },
  "daily_nutrition_summary": {
    "0": { "calories": 1980, "protein_grams": 145.0, "carbs_grams": 198.0, "fat_grams": 64.0 }
  }
}
```

> **Note:** Days are keyed by `day_offset` integer (0=Monday … 6=Sunday) to match the `PlannedMeal.day_offset` field in Phase 1. `week_start_date` is always the Monday of the target week.

## Tasks

- [ ] Create `nutrition_plans/` and `meal_plans/` directories at project root
- [ ] Add both to `.gitignore`
- [ ] Write `dietitian_agent.md`
- [ ] Test: run dietitian agent, complete intake, verify `nutrition_plans/<name>_<date>.json` is written and valid
- [ ] Write `meal_planner_agent.md`
- [ ] Test: run meal planner agent against the nutrition plan, verify `meal_plans/<name>_<date>.json` is written
- [ ] Manually review meal plan output: check meals respect dietary restrictions, macros are plausible, variety across the week
- [ ] Iterate on both agent prompts until output quality is satisfactory

## Acceptance Criteria
- `nutrition_plans/<name>_<date>.json` produced by dietitian agent passes the `NutritionPlan` schema (all required fields present, correct types)
- `meal_plans/<name>_<date>.json` produced by meal planner agent passes the meal plan schema above
- Daily nutrition summaries are within ±15% of the plan's targets
- Meal variety is acceptable across 7 days (no repeated meals, cuisine mix matches preferences)
- Both JSON files can be read cleanly by a human and a script — no markdown wrapping, no extra text

## Relationship to Phase 1
- `dietitian_agent.md` carries forward unchanged into Phase 1
- `meal_planner_agent.md` becomes the source of truth for the system prompt in `ai/meal_planner_agent.py` — the Python agent loads its instructions from this file rather than duplicating them
- The `meal_plans/` JSON schema defined here is what `ai/meal_planner_agent.py` parses and persists to the database
