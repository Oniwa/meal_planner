# Phase 0 — Proof of Concept (Claude CLI Agents)

> Reference: [Architecture](../reference/meal_planner_architecture.md)

## Goal
Validate the full AI pipeline using Claude CLI only — no Django, no database, no web server. Two markdown agents that talk to each other via JSON files. Phase 1 only begins once the output quality of both agents is satisfactory across three test runs.

## Pipeline

```
claude --agent agents/dietitian_agent.md
        │
  nutrition_plans/<name>_<date>.json
        │
claude --agent agents/meal_planner_agent.md
        │
  meal_plans/<name>_<date>.json
```

## Deliverables

### 1. `dietitian_agent.md`
A Claude CLI agent that:
- Asks for the person's name at the start
- Conducts an **adaptive** conversational intake interview:
  - Core questions first: goals, dietary restrictions, allergies, cuisine preferences, max cook time, cooking skill, meal variety preference, night snack preference
  - Branches based on answers (e.g. "heart healthy" → ask about sodium targets; "meal prep friendly" → ask about prep day and batch cooking preferences)
  - Captures anything the structured fields can't express in the `notes` field
- Produces `nutrition_plans/<name>_<YYYY-MM-DD>.json` matching the schema below
- Prints the JSON to the terminal and writes it to the file

### 2. `meal_planner_agent.md`
A Claude CLI agent that:
- Lists all files in `nutrition_plans/` and asks the user to pick one (most recent pre-selected as default), reading the chosen file directly with the `read` tool
- Asks which week to plan for (default: upcoming Monday)
- Generates a full 7-day × 5-slot meal plan (or 4-slot if `include_night_snack: false`) conforming to the nutrition plan's constraints
- Repetition rules driven by `meal_variety`:
  - `"high"` — no repeated recipes across the entire week
  - `"medium"` — no repeated recipes within the same meal slot
  - `"low"` — repetition allowed (meal prep friendly); agent should suggest batch-cook candidates
- Prints a compact terminal summary: meal name + calories + macros per slot, daily totals vs targets row
- Produces `meal_plans/<name>_<YYYY-MM-DD>.json` (generation date) matching the schema below
- Writes the JSON to the file

### Output Directories
Both directories live at the project root and are gitignored (personal health data):
```
nutrition_plans/   # output of dietitian_agent.md
meal_plans/        # output of meal_planner_agent.md
```

## Nutrition Plan JSON Schema

```json
{
  "name": "john",
  "label": "John - April 2026",
  "daily_calories": 2000,
  "protein_grams": 150,
  "carbs_grams": 200,
  "fat_grams": 65,
  "heart_healthy": true,
  "low_sodium": false,
  "low_sugar": false,
  "diabetic_friendly": false,
  "anti_inflammatory": false,
  "is_vegetarian": false,
  "is_vegan": false,
  "is_gluten_free": false,
  "is_dairy_free": false,
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

## Meal Plan JSON Schema

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
      "lunch": { },
      "dinner": { },
      "afternoon_snack": { },
      "night_snack": { }
    }
  },
  "daily_nutrition_summary": {
    "0": { "calories": 1980, "protein_grams": 145.0, "carbs_grams": 198.0, "fat_grams": 64.0 }
  }
}
```

> **Note:** Days are keyed by `day_offset` integer (0=Monday … 6=Sunday). `night_snack` is omitted from all days when `include_night_snack: false`. `week_start_date` is always the Monday of the target week. Filename uses generation date, not week start date.

## Tasks

- [ ] Create `nutrition_plans/` and `meal_plans/` directories at project root
- [ ] Confirm both are in `.gitignore`
- [ ] Write `dietitian_agent.md` (adaptive intake, all schema fields captured)
- [ ] Test run 1 — **standard profile**: run dietitian agent, complete intake, verify JSON written and valid; run meal planner agent, verify meal plan JSON written; review output for constraint compliance and plausible macros
- [ ] Write `meal_planner_agent.md` (file picker, week picker, variety rules, compact terminal summary)
- [ ] Test run 2 — **restrictive profile**: vegan + gluten-free + low-sodium, `meal_variety: "high"`; verify no restriction violations, no repeated meals, macros within ±15%
- [ ] Test run 3 — **meal prep profile**: `meal_prep_friendly: true`, `meal_variety: "low"`, `include_night_snack: true`; verify batch-cook suggestions, night snack slot present, shopping list mentally coherent
- [ ] Iterate on both agent prompts until all three test runs pass acceptance criteria

## Acceptance Criteria
- `nutrition_plans/<name>_<date>.json` contains all required fields with correct types
- `meal_plans/<name>_<date>.json` matches the meal plan schema above
- Daily nutrition summaries are within ±15% of the plan's targets
- Meal variety rules are respected per `meal_variety` setting
- Dietary restrictions and allergies are not violated
- `night_snack` slot present iff `include_night_snack: true`
- Terminal summary shows name + calories + macros per slot, daily totals vs targets
- Both JSON files are clean — no markdown wrapping, no extra text

## Relationship to Phase 1
- `agents/dietitian_agent.md` carries forward unchanged into Phase 1
- `agents/meal_planner_agent.md` becomes the source of truth for the system prompt in `ai/meal_planner_agent.py` — the Python agent loads its instructions from this file rather than duplicating them
- Both JSON schemas defined here are what Phase 1 imports and persists to the database
