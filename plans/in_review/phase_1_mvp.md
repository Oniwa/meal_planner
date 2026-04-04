# Phase 1 — MVP

> Reference: [Architecture](../reference/meal_planner_architecture.md)
> Testing: [Testing Strategy](../reference/testing_strategy.md)

## Goal
A working end-to-end flow: import a nutrition plan, generate a weekly meal plan, swap individual meals, view a shopping list. Built TDD — tests written before implementation for each feature layer.

## Decisions & Constraints

- `ai/` is a top-level Python package (not a Django app); imports from `apps.*` as needed
  - Future refactor: separate API call logic from DB writes so `ai/` has no ORM dependency
- `PlannedMeal.day_offset: int` (0=Monday … 6=Sunday) — no `day_of_week` string field
- Always create new `Recipe` rows on generation — no deduplication (deferred to future phase)
- Shopping list generated eagerly in the same DB transaction as the meal plan; full rollback on failure
- Swap → full shopping list regeneration; `is_checked` preserved for items with unchanged `(ingredient_name, unit)`, new items start unchecked, removed items deleted
- Importing a new `NutritionPlan` auto-deactivates the previous active one
- `GET /meals/` uses `MealPlan.status = "active"` to identify the current week's plan; on generation the new plan is set active and any previous plan for that week is archived
- `GET /meals/` redirects to `/nutrition/import/` if no active `NutritionPlan` exists
- `/` redirects to `/meals/` if an active `NutritionPlan` exists, otherwise to `/nutrition/import/`
- Meal plan agent generates ingredients for exactly 1 serving per meal (`servings: 1` in response); `recipe.servings` is stored but unused in calculations for MVP
  - Future improvement: add `servings_consumed: int` to `PlannedMeal` and scale shopping list quantities accordingly
- Shopping list groups by `(ingredient_name, unit)` — no unit conversion; `ShoppingItem.notes` = first non-empty ingredient note for that group
- Nutrition validation: per-day check on all four macros (calories, protein, carbs, fat) within ±15% of `NutritionPlan` targets
- Meal variety repetition rules (`high`/`medium`/`low`) are prompt-enforced only — no code-level validation in Phase 1
  - Future hardening: add code-level repetition check before persisting generated plan
- System prompt for `ai/meal_planner_agent.py` loaded from `.claude/agents/meal_planner_agent.md` — single source of truth shared with the Phase 0 CLI agent; no separate `ai/prompts/` file
- Meal plan generation is synchronous; browser waits with an HTMX spinner (`hx-indicator`); hard timeout of 120 seconds on the Anthropic API call; timeout/failure renders a user-facing error message (no raw 500)
- Agent raises on second retry failure (both JSON and nutrition paths); view catches and renders error
- Failed swap returns an HTMX error fragment with a retry button; original meal is preserved in DB
- `POST /meals/swap/` validates that `planned_meal_id` belongs to the active `MealPlan` before processing
- `GET /meals/<week_start>/` uses `YYYY-MM-DD` format; returns 404 if date is not a Monday
- `night_snack` row in the week grid is conditionally rendered based on `NutritionPlan.include_night_snack`
- `POST /shopping/check/` returns a single item row HTMX fragment
- Tooling config consolidated in `pyproject.toml` (ruff + pytest); `.pylintrc` kept as a separate file
- Database: SQLite
- CSS: Tailwind via CDN (no build step)

## Required Import Fields

The following fields are required when importing a `NutritionPlan` JSON; all others have safe defaults (booleans → `False`, lists → `[]`, text → `""`):

- `label`
- `daily_calories`
- `protein_grams`
- `carbs_grams`
- `fat_grams`
- `max_cook_time_minutes`
- `cooking_skill_level`
- `meal_variety`
- `include_night_snack`

## Tasks

### Project Setup
- [ ] Django project scaffold: `config/` (including `wsgi.py`), `apps/`, `ai/`, `templates/`, `manage.py`, `requirements.txt`
  - Dependencies: `django`, `anthropic`, `python-decouple`
- [ ] `requirements-dev.txt`: `pytest`, `pytest-django`, `pytest-mock`, `model-bakery`, `playwright`, `pytest-playwright`, `ruff`, `pylint`, `pylint-django`
- [ ] `.env.example` with: `SECRET_KEY`, `ANTHROPIC_API_KEY`, `DEBUG`, `ALLOWED_HOSTS`, commented `DATABASE_URL`
- [ ] `config/settings.py` reads all config from `.env` via `python-decouple`
- [ ] Register apps: `nutrition`, `meals`, `shopping`
- [ ] `config/urls.py` — root URL conf wiring all apps; root `/` redirects to `/meals/` if active `NutritionPlan` exists, otherwise to `/nutrition/import/`
- [ ] `templates/base.html` — HTMX CDN + Tailwind CSS CDN, nav bar (Nutrition Plan | Meal Plan | Shopping)

### Test Infrastructure
- [ ] `pyproject.toml` — pytest: `DJANGO_SETTINGS_MODULE = config.settings`; ruff: line length 100, select Django rules (`DJ`), enable isort + pyupgrade rules
- [ ] `.pylintrc` — load `pylint_django`, set `django-settings-module`, disable `missing-docstring` and `too-few-public-methods`
- [ ] `tests/conftest.py` — shared fixtures: Django test client, sample `NutritionPlan`, Anthropic client mock
  - Anthropic mock: `function`-scoped, opt-in (not `autouse`) — tests explicitly request it
  - Used by both unit/integration tests and e2e tests (e2e tests never hit the real API)
- [ ] `tests/fixtures/` — canned API response JSON files:
  - `week_plan_valid.json` — valid 7-day plan (also used by e2e tests via the Anthropic mock)
  - `week_plan_invalid_json.txt` — malformed response (individual payload for retry sequence)
  - `week_plan_bad_nutrition.json` — valid JSON but per-day totals outside ±15% on at least one macro (individual payload for retry sequence)
  - `swap_response.json` — single-meal swap response
  - Note: retry sequences are assembled in tests via `mock.side_effect = [first_response, second_response]`
- [ ] `playwright install` — install browser binaries

### Data Models & Migrations
- [ ] `apps/nutrition/models.py` — `NutritionPlan` model + migration
- [ ] `apps/meals/models.py` — `MealPlan` (with `status: "active"|"archived"`), `PlannedMeal` (with `day_offset: int`), `Recipe`, `Ingredient` + migration
- [ ] `apps/shopping/models.py` — `ShoppingList`, `ShoppingItem` + migration

### AI Layer
- [ ] `ai/__init__.py`
- [ ] `ai/client.py` — Anthropic client singleton; API calls use a hard timeout of 120 seconds
- [ ] **Tests first** — `tests/unit/test_meal_agent.py`:
  - `notes` injected into prompt when non-empty; omitted when empty
  - Code fence stripping: ` ```json {...} ``` ` → `{...}`; plain `{...}` → unchanged
  - `JSONDecodeError` on first call → retries with "invalid JSON" message
  - `JSONDecodeError` on second call → raises
  - Per-day nutrition totals within ±15% on all four macros → passes
  - Per-day totals outside ±15% on any macro → retries with correction message naming the failing days and fields
  - Per-day totals outside ±15% twice → raises
  - `generate_swap` excludes current recipe name from prompt
  - Shopping aggregation: same `(name, unit)` → quantities summed
  - Shopping aggregation: same name, different units → two separate rows
  - Shopping aggregation: empty plan → empty list
  - Shopping item notes: first non-empty ingredient note wins; all empty → blank
- [ ] `ai/meal_planner_agent.py`:
  - Load system prompt from `.claude/agents/meal_planner_agent.md` at import time
  - Build user message from `NutritionPlan`, injecting `notes` only when non-empty
  - Instruct model to set `servings: 1` on all recipes
  - Call API synchronously with 120s timeout
  - Strip markdown code fences before parsing (`json.loads`)
  - On `JSONDecodeError`: retry once with "invalid JSON" correction message; raise on second failure
  - Validate per-day totals for calories, protein, carbs, fat within ±15% of targets; retry once with correction message naming failing days and fields; raise on second failure
  - All DB writes (MealPlan, PlannedMeal, Recipe, Ingredient, ShoppingList, ShoppingItem) in a single transaction; full rollback on any failure
  - Shopping list grouped by `(ingredient_name, unit)`; `ShoppingItem.notes` = first non-empty ingredient note for the group
  - `generate_swap(planned_meal, reason=None)` — single-meal prompt excluding current recipe name; on success: update `PlannedMeal.recipe`, set `was_swapped=True`, regenerate shopping list preserving `is_checked` for unchanged `(ingredient_name, unit)` items; raise on second retry failure

### Nutrition App
- [ ] **Tests first** — `tests/unit/test_nutrition_import.py`:
  - Valid JSON with all required fields → no errors
  - Missing required field → raises with field name in message
  - Wrong type on required field → raises
  - Extra unknown fields → accepted (ignored)
  - Optional fields absent → safe defaults applied
- [ ] **Tests first** — `tests/integration/test_nutrition_views.py`:
  - `GET /nutrition/import/` → 200, form present
  - `POST` valid JSON → plan saved, previous deactivated, redirect to `/nutrition/plan/`
  - `POST` missing required field → 200, error shown, nothing saved
  - `GET /nutrition/plan/` with active plan → 200, data rendered
  - `GET /nutrition/plan/` with no plan → redirect to `/nutrition/import/`
- [ ] `apps/nutrition/views.py` + `urls.py`:
  - `GET /nutrition/import/` — paste or file upload form
  - `POST /nutrition/import/` — validate required fields; clear error messages on missing/wrong-type fields; auto-deactivate previous plan on success; redirect to `/nutrition/plan/`
  - `GET /nutrition/plan/` — display active plan summary; redirect to import if none
- [ ] `nutrition/import.html` — textarea (paste) + file upload input
- [ ] `nutrition/plan_summary.html` — card display of goals, macros, health flags, preferences

### Meals App
- [ ] **Tests first** — `tests/integration/test_meals_views.py`:
  - `GET /meals/` with no active `NutritionPlan` → redirect to `/nutrition/import/`
  - `GET /meals/` with active `NutritionPlan` but no plan for today → generate prompt shown
  - `GET /meals/` with active plan covering today → week grid shown
  - `POST /meals/generate/` → archives existing active plan for week if present, creates new `MealPlan` + `ShoppingList`, redirect
  - `POST /meals/generate/` on agent failure → user-facing error rendered, no plan created
  - `POST /meals/swap/` with valid `planned_meal_id` → returns HTMX fragment, `was_swapped=True`, shopping list regenerated with `is_checked` preserved for unchanged items
  - `POST /meals/swap/` with `planned_meal_id` not belonging to active plan → 404
  - `POST /meals/swap/` on agent failure → returns HTMX error fragment, original meal unchanged
  - `GET /meals/<week_start>/` with valid Monday date → 200
  - `GET /meals/<week_start>/` with non-Monday date → 404
  - `GET /meals/meal/<planned_meal_id>/` → 200, meal detail shown
  - `GET /meals/meal/<planned_meal_id>/` not belonging to active plan → 404
- [ ] `apps/meals/views.py` + `urls.py`:
  - `POST /meals/generate/` — archive existing active plan for week; generate new `MealPlan`; on failure render error message; uses HTMX spinner via `hx-indicator`
  - `GET /meals/` — redirect to `/nutrition/import/` if no active `NutritionPlan`; show generate prompt if no active plan covers today; show week grid if plan exists
  - `GET /meals/<week_start>/` (`YYYY-MM-DD`) — show specific week plan; 404 if not a Monday
  - `POST /meals/swap/` — validate `planned_meal_id` belongs to active plan (404 if not); call `generate_swap`; return re-rendered meal cell fragment on success, error fragment on failure
  - `GET /meals/meal/<planned_meal_id>/` — show meal detail; validate belongs to active plan (404 if not)
- [ ] `meals/week_plan.html` — 7-column grid (days derived from `week_start_date + timedelta(days=day_offset)`); `night_snack` row rendered only if `NutritionPlan.include_night_snack` is true; each cell shows meal name + calories with link to detail; Swap button per cell (HTMX POST → replaces cell in-place); swap failure renders inline error with retry button
- [ ] `meals/meal_detail.html` — individual meal detail (recipe, ingredients, nutrition)

### Shopping App
- [ ] **Tests first** — `tests/integration/test_shopping_views.py`:
  - `GET /shopping/` → items grouped by category
  - `POST /shopping/check/` → `is_checked` toggled, single item row HTMX fragment returned
- [ ] `apps/shopping/views.py` + `urls.py`:
  - `GET /shopping/` — shopping list for current week's active plan
  - `POST /shopping/check/` — toggle `is_checked`; return single item row fragment (HTMX)
- [ ] `shopping/list.html` — items grouped by category, checkboxes via HTMX POST; checked rows styled as struck-through

### End-to-End Tests (Playwright)
- All e2e tests use `pytest-django`'s `live_server` fixture; Anthropic client mocked via the shared `conftest.py` fixture (never hits real API)
- [ ] `tests/e2e/test_import_flow.py` — paste JSON → plan saved → redirect → plan details visible
- [ ] `tests/e2e/test_meal_plan_flow.py` — generate plan → spinner → 7-column grid renders (night_snack row absent when `include_night_snack: false`)
- [ ] `tests/e2e/test_swap_flow.py` — click Swap → cell updates in-place, no full page reload
- [ ] `tests/e2e/test_shopping_flow.py` — check off item → persists after page reload

### Verification
- [ ] `ruff check .` — no lint errors
- [ ] `ruff format --check .` — no formatting violations
- [ ] `pylint apps/ ai/` — no errors or warnings
- [ ] `pytest` — all unit and integration tests pass
- [ ] `pytest tests/e2e/` — all Playwright flows pass
- [ ] `python manage.py migrate` — all tables created clean
- [ ] Run `claude` with `.claude/agents/dietitian_agent.md` → complete intake → `nutrition_plans/<name>_<date>.json` written and printed
- [ ] Visit `/nutrition/import/` → paste JSON → strict validation passes → plan saved, previous deactivated → redirect to plan summary
- [ ] Visit `/nutrition/import/` → paste JSON missing a required field → clear field-level error shown, nothing saved
- [ ] Visit `/meals/` → click "Generate Week Plan" → spinner shown → week grid populated with 7 days × 4 or 5 meal slots (depending on `include_night_snack`)
- [ ] Click "Swap" on any meal → cell updates in-place with a new meal; previously checked shopping items remain checked
- [ ] Visit `/shopping/` → all ingredients consolidated by `(ingredient_name, unit)`, grouped by category
- [ ] Check off items → persisted via HTMX POST

## Acceptance Criteria
`ruff` and `pylint` pass clean, all `pytest` tests pass, and all manual verification steps above pass cleanly.
