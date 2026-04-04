# Phase 1 — MVP

> Reference: [Architecture](../reference/meal_planner_architecture.md)
> Testing: [Testing Strategy](../reference/testing_strategy.md)

## Goal
A working end-to-end flow: import a nutrition plan, generate a weekly meal plan, swap individual meals, view a shopping list. Built TDD — tests written before implementation for each feature layer.

## Decisions & Constraints

- `ai/` is a top-level Python package (not a Django app); imports from `apps.*` as needed
- `PlannedMeal.day_offset: int` (0=Monday … 6=Sunday) — no `day_of_week` string field
- Always create new `Recipe` rows on generation — no deduplication (deferred to future phase)
- Shopping list generated eagerly in the same DB transaction as the meal plan
- Swap → full shopping list regeneration + reset all `is_checked`
- Importing a new `NutritionPlan` auto-deactivates the previous active one
- `GET /meals/` shows the plan whose `week_start_date` covers today; shows a generate prompt if none exists
- Meal plan agent generates ingredients for exactly 1 serving per meal; `recipe.servings` is display-only
- Shopping list groups by `(ingredient_name, unit)` — no unit conversion
- Database: SQLite
- CSS: Tailwind via CDN (no build step)
- Meal plan generation is synchronous; browser waits with an HTMX spinner (`hx-indicator`)

## Tasks

### Project Setup
- [ ] Django project scaffold: `config/`, `apps/`, `ai/`, `templates/`, `manage.py`, `requirements.txt`
  - Dependencies: `django`, `anthropic`, `python-decouple`
- [ ] `requirements-dev.txt`: `pytest`, `pytest-django`, `pytest-mock`, `model-bakery`, `playwright`, `pytest-playwright`, `ruff`, `pylint`, `pylint-django`
- [ ] `.env.example` with: `SECRET_KEY`, `ANTHROPIC_API_KEY`, `DEBUG`, `ALLOWED_HOSTS`, commented `DATABASE_URL`
- [ ] `config/settings.py` reads all config from `.env` via `python-decouple`
- [ ] Register apps: `nutrition`, `meals`, `shopping`
- [ ] `config/urls.py` — root URL conf wiring all apps; root `/` redirects to `/nutrition/plan/` or `/meals/`
- [ ] `templates/base.html` — HTMX CDN + Tailwind CSS CDN, nav bar (Nutrition Plan | Meal Plan | Shopping)

### Test Infrastructure
- [ ] `pytest.ini` (or `pyproject.toml`) — set `DJANGO_SETTINGS_MODULE = config.settings`
- [ ] `ruff.toml` — line length 100, select Django rules (`DJ`), enable isort + pyupgrade rules
- [ ] `.pylintrc` — load `pylint_django`, set `django-settings-module`, disable `missing-docstring` and `too-few-public-methods`
- [ ] `tests/conftest.py` — shared fixtures: Django test client, sample `NutritionPlan`, Anthropic client mock
- [ ] `tests/fixtures/` — canned API response JSON files:
  - `week_plan_valid.json` — valid 7-day plan
  - `week_plan_invalid_json.txt` — malformed response (tests `JSONDecodeError` retry path)
  - `week_plan_bad_nutrition.json` — valid JSON but totals outside ±15% (tests nutrition retry path)
  - `swap_response.json` — single-meal swap response
- [ ] `playwright install` — install browser binaries

### Data Models & Migrations
- [ ] `apps/nutrition/models.py` — `NutritionPlan` model + migration
- [ ] `apps/meals/models.py` — `MealPlan`, `PlannedMeal` (with `day_offset: int`), `Recipe`, `Ingredient` + migration
- [ ] `apps/shopping/models.py` — `ShoppingList`, `ShoppingItem` + migration

### Dietitian Agent
- [ ] Create `nutrition_plans/` directory at project root (gitignored — contains personal health data)
- [ ] `dietitian_agent.md` — Claude CLI agent definition:
  - Ask for person's name at the start
  - Conduct intake interview (health goals, restrictions, preferences, cooking style)
  - Write output to `nutrition_plans/<name>_<YYYY-MM-DD>.json`
  - Print JSON to terminal
  - Schema must match `NutritionPlan` fields exactly

### AI Layer
- [ ] `ai/__init__.py`
- [ ] `ai/client.py` — Anthropic client singleton
- [ ] `ai/prompts/meal_planner.txt` — prompt template with:
  - System role: expert meal prep chef and nutritionist
  - Full JSON response schema
  - Instruction to generate ingredients for exactly 1 serving per meal
  - `daily_nutrition_summary` block for validation
  - Instruction to inject `notes` field only when non-empty
- [ ] **Tests first** — `tests/unit/test_meal_agent.py`:
  - `notes` injected when non-empty; omitted when empty
  - Code fence stripping: ` ```json {...} ``` ` → `{...}`; plain `{...}` → unchanged
  - `JSONDecodeError` on first call → retries with "invalid JSON" message
  - `JSONDecodeError` on second call → raises
  - Nutrition totals within ±15% → passes
  - Nutrition totals outside ±15% → retries with correction message
  - Nutrition totals outside ±15% twice → raises
  - `generate_swap` excludes current recipe name from prompt
- [ ] **Tests first** — `tests/unit/test_shopping.py`:
  - Same `(name, unit)` → quantities summed
  - Same name, different units → two separate rows
  - Empty plan → empty list
- [ ] `ai/meal_planner_agent.py`:
  - Build prompt from `NutritionPlan`, injecting `notes` only when non-empty
  - Call API synchronously
  - Strip markdown code fences before parsing (`json.loads`)
  - On `JSONDecodeError`: retry once with "invalid JSON" correction message; raise on second failure
  - Validate daily totals within ±15% of targets; retry once with nutrition correction message; raise on second failure
  - Persist `MealPlan`, `PlannedMeal`, `Recipe`, `Ingredient` rows
  - Generate `ShoppingList` + `ShoppingItem` rows in the same transaction (grouped by `(ingredient_name, unit)`)
  - `generate_swap(planned_meal, reason=None)` — single-meal prompt excluding current recipe; on success update `PlannedMeal.recipe`, set `was_swapped=True`, regenerate full shopping list and reset all `is_checked`

### Nutrition App
- [ ] **Tests first** — `tests/unit/test_nutrition_import.py`:
  - Valid JSON → no errors
  - Missing required field → raises with field name in message
  - Wrong type → raises
  - Extra unknown fields → accepted
- [ ] **Tests first** — `tests/integration/test_nutrition_views.py`:
  - `GET /nutrition/import/` → 200, form present
  - `POST` valid JSON → plan saved, previous deactivated, redirect to `/nutrition/plan/`
  - `POST` missing field → 200, error shown, nothing saved
  - `GET /nutrition/plan/` with active plan → 200, data rendered
  - `GET /nutrition/plan/` with no plan → redirect to import
- [ ] `apps/nutrition/views.py` + `urls.py`:
  - `GET /nutrition/import/` — paste or file upload form
  - `POST /nutrition/import/` — strict schema validation; clear error messages on missing/wrong-type fields; auto-deactivate previous plan on success; redirect to `/nutrition/plan/`
  - `GET /nutrition/plan/` — display active plan summary
- [ ] `nutrition/import.html` — textarea (paste) + file upload input
- [ ] `nutrition/plan_summary.html` — card display of goals, macros, health flags, preferences

### Meals App
- [ ] **Tests first** — `tests/integration/test_meals_views.py`:
  - `GET /meals/` with no plan for today → generate prompt shown
  - `GET /meals/` with plan covering today → week grid shown
  - `POST /meals/generate/` → `MealPlan` + `ShoppingList` created, redirect
  - `POST /meals/swap/` → returns HTMX fragment, `was_swapped=True`, shopping list regenerated
- [ ] `apps/meals/views.py` + `urls.py`:
  - `POST /meals/generate/` — generate new `MealPlan` for current week (HTMX spinner via `hx-indicator`)
  - `GET /meals/` — show plan covering today's date; show "Generate" prompt if none exists
  - `GET /meals/<week_start>/` — show specific week plan
  - `POST /meals/swap/` — accepts `planned_meal_id` (PK) + optional `reason`; calls `generate_swap`; returns re-rendered meal cell fragment
- [ ] `meals/week_plan.html` — 7-column grid (days derived from `week_start_date + timedelta(days=day_offset)`), 5 rows (meal slots); each cell shows meal name + calories; Swap button per cell (HTMX POST → replaces cell in-place)
- [ ] `meals/meal_detail.html` — individual meal detail (recipe, ingredients, nutrition)

### Shopping App
- [ ] **Tests first** — `tests/integration/test_shopping_views.py`:
  - `GET /shopping/` → items grouped by category
  - `POST /shopping/check/` → `is_checked` toggled, HTMX fragment returned
- [ ] `apps/shopping/views.py` + `urls.py`:
  - `GET /shopping/` — shopping list for current week's active plan
  - `POST /shopping/check/` — toggle `is_checked` (HTMX, returns updated item fragment)
- [ ] `shopping/list.html` — items grouped by category, checkboxes via HTMX POST

### End-to-End Tests (Playwright)
- [ ] `tests/e2e/test_import_flow.py` — paste JSON → plan saved → redirect → plan details visible
- [ ] `tests/e2e/test_meal_plan_flow.py` — generate plan → spinner → 7-column grid renders
- [ ] `tests/e2e/test_swap_flow.py` — click Swap → cell updates in-place, no full page reload
- [ ] `tests/e2e/test_shopping_flow.py` — check off item → persists after page reload

### Verification
- [ ] `ruff check .` — no lint errors
- [ ] `ruff format --check .` — no formatting violations
- [ ] `pylint apps/ ai/` — no errors or warnings
- [ ] `pytest` — all unit and integration tests pass
- [ ] `pytest tests/e2e/` — all Playwright flows pass
- [ ] `python manage.py migrate` — all tables created clean
- [ ] Run `claude` with `dietitian_agent.md` → complete intake → `nutrition_plans/<name>_<date>.json` written and printed
- [ ] Visit `/nutrition/import/` → paste JSON → strict validation passes → plan saved, previous deactivated → redirect to plan summary
- [ ] Visit `/nutrition/import/` → paste malformed JSON → clear field-level errors shown, nothing saved
- [ ] Visit `/meals/` → click "Generate Week Plan" → spinner shown → week grid populated with 7 days × 5 meal slots
- [ ] Click "Swap" on any meal → cell updates in-place with a new meal; shopping list regenerated
- [ ] Visit `/shopping/` → all ingredients consolidated by `(ingredient_name, unit)`, grouped by category
- [ ] Check off items → persisted via HTMX POST

## Acceptance Criteria
`ruff` and `pylint` pass clean, all `pytest` tests pass, and all manual verification steps above pass cleanly.
