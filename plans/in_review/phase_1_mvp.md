# Phase 1 — MVP

> Reference: [Architecture](../reference/meal_planner_architecture.md)

## Goal
A working end-to-end flow: import a nutrition plan, generate a weekly meal plan, swap individual meals, view a shopping list.

## Tasks

- [ ] Django project setup: `config/`, `apps/` structure, `requirements.txt`, `manage.py`
- [ ] `.env` / `.env.example` with `ANTHROPIC_API_KEY` and `SECRET_KEY`
- [ ] Register apps: `nutrition`, `meals`, `shopping`
- [ ] `apps/nutrition/models.py` — `NutritionPlan` model + migration
- [ ] `apps/meals/models.py` — `MealPlan`, `PlannedMeal`, `Recipe`, `Ingredient` + migration
- [ ] `apps/shopping/models.py` — `ShoppingList`, `ShoppingItem` + migration
- [ ] `ai/client.py` — Anthropic client singleton
- [ ] `dietitian_agent.md` — Claude CLI agent definition + `nutrition_plan.json` output schema
- [ ] `apps/nutrition/views.py` + `urls.py` — import JSON view (GET paste form, POST save)
- [ ] `nutrition/import.html` + `nutrition/plan_summary.html` templates
- [ ] `ai/prompts/meal_planner.txt` — meal plan prompt template with full JSON schema
- [ ] `ai/meal_planner_agent.py` — build prompt, call API, parse JSON, persist to DB
  - Validation: daily totals within ±15% of targets; retry once on failure
  - `generate_swap(planned_meal, reason=None)` method
- [ ] `apps/meals/views.py` + `urls.py` — generate plan, week view, swap endpoint
- [ ] `meals/week_plan.html` — 7-column grid, swap button per cell (HTMX)
- [ ] `meals/meal_detail.html` — individual meal detail
- [ ] `apps/shopping/views.py` + `urls.py` — shopping list view, toggle check (HTMX)
- [ ] `shopping/list.html` — grouped by category, checkboxes
- [ ] `templates/base.html` — HTMX CDN, nav bar
- [ ] `config/urls.py` — root URL conf wiring all apps
- [ ] Verify end-to-end against the checklist in the architecture doc

## Acceptance Criteria
All 7 verification steps in the architecture doc pass cleanly.
