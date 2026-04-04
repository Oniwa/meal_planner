# Testing Strategy

> Reference: [Architecture](../reference/meal_planner_architecture.md)

## Philosophy

Test-driven development (TDD): write the test before writing the implementation. Red → Green → Refactor. Tests are not an afterthought — each feature task in the phase plans has a paired test task.

---

## Tools

| Tool | Purpose |
|---|---|
| `pytest` + `pytest-django` | Test runner and Django integration |
| `model-bakery` | Factory-style model creation without boilerplate fixtures |
| `unittest.mock` / `pytest-mock` | Mock the Anthropic API client — never make real API calls in tests |
| `Playwright` (`pytest-playwright`) | End-to-end browser tests for full user flows and HTMX interactions |
| `ruff` | Fast linter + formatter (replaces flake8, isort, pyupgrade) |
| `pylint` + `pylint-django` | Deep static analysis; catches Django-specific issues ruff misses |

Add to `requirements-dev.txt`:
```
pytest
pytest-django
pytest-mock
model-bakery
playwright
pytest-playwright
ruff
pylint
pylint-django
```

### Linting Configuration

**`ruff.toml`** (or `[tool.ruff]` in `pyproject.toml`):
```toml
line-length = 100
target-version = "py312"

[lint]
select = ["E", "F", "W", "I", "UP", "B", "C4", "DJ"]  # includes Django rules
ignore = ["DJ001"]  # allow CharField without max_length where appropriate
```

**`.pylintrc`** (key settings):
```ini
[MASTER]
load-plugins = pylint_django
django-settings-module = config.settings

[FORMAT]
max-line-length = 100

[MESSAGES CONTROL]
disable = missing-docstring, too-few-public-methods
```

Both run in CI and as a pre-commit check. All code must pass before merging.

---

## Test Structure

```
tests/
├── conftest.py                   # shared fixtures (db, client, sample NutritionPlan, etc.)
├── unit/
│   ├── test_nutrition_import.py  # JSON validation logic
│   ├── test_meal_agent.py        # prompt building, JSON parsing, retry logic, validation
│   └── test_shopping.py          # ingredient aggregation logic
├── integration/
│   ├── test_nutrition_views.py   # import view, plan summary view
│   ├── test_meals_views.py       # generate, week view, swap
│   └── test_shopping_views.py    # list view, toggle check
└── e2e/
    ├── test_import_flow.py       # paste JSON → plan saved → redirect
    ├── test_meal_plan_flow.py    # generate plan → week grid renders
    ├── test_swap_flow.py         # swap button → cell updates in-place (HTMX)
    └── test_shopping_flow.py     # check off items → persisted (HTMX)
```

`pytest.ini` (or `pyproject.toml`):
```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
```

---

## What to Test at Each Layer

### Unit Tests

**`test_nutrition_import.py`**
- Valid JSON → no errors
- Missing required field → raises with field name in error
- Wrong type (e.g. `daily_calories: "two thousand"`) → raises
- Extra unknown fields → accepted (ignored)

**`test_meal_agent.py`**
- Prompt includes `notes` when non-empty; omits when empty
- Code fence stripping: ` ```json {...} ``` ` → `{...}`
- Code fence stripping: plain `{...}` → unchanged
- `JSONDecodeError` on first call → retries with "invalid JSON" message
- `JSONDecodeError` on second call → raises
- Nutrition validation passes when totals within ±15%
- Nutrition validation fails → retries with correction message
- Nutrition validation fails twice → raises
- `generate_swap` excludes the current recipe name from the prompt

**`test_shopping.py`**
- Ingredients with same `(name, unit)` → quantities summed into one `ShoppingItem`
- Ingredients with same name but different units → two separate `ShoppingItem` rows
- Empty meal plan → empty shopping list

### Integration Tests

Use `pytest-django`'s `client` fixture and `model-bakery` for DB state. Mock the Anthropic client at the `ai.client` level.

**`test_nutrition_views.py`**
- `GET /nutrition/import/` → 200, form present
- `POST /nutrition/import/` with valid JSON → `NutritionPlan` saved, previous deactivated, redirect to `/nutrition/plan/`
- `POST /nutrition/import/` with missing field → 200, error message present, no plan saved
- `GET /nutrition/plan/` with active plan → 200, plan data rendered
- `GET /nutrition/plan/` with no active plan → redirect to import

**`test_meals_views.py`**
- `GET /meals/` with no plan for current week → generate prompt shown
- `GET /meals/` with plan covering today → week grid shown
- `POST /meals/generate/` → `MealPlan` + `ShoppingList` created, redirect to `/meals/`
- `POST /meals/swap/` with valid `planned_meal_id` → returns HTMX fragment, `was_swapped=True`, shopping list regenerated

**`test_shopping_views.py`**
- `GET /shopping/` → items grouped by category
- `POST /shopping/check/` → `is_checked` toggled, returns HTMX fragment

### End-to-End Tests (Playwright)

E2E tests run against a live Django dev server (`pytest-playwright` handles this via `live_server` fixture). The Anthropic client is patched at startup to return fixture JSON — no real API calls.

**`test_import_flow.py`**
- Navigate to `/nutrition/import/`
- Paste valid JSON into textarea
- Submit → redirected to `/nutrition/plan/`, plan details visible

**`test_meal_plan_flow.py`**
- Pre-seed an active `NutritionPlan`
- Navigate to `/meals/`
- Click "Generate Week Plan"
- Assert: spinner appears, then 7-column grid with 5 meal slots each renders

**`test_swap_flow.py`**
- Pre-seed an active `MealPlan`
- Navigate to `/meals/`
- Click "Swap" on a meal cell
- Assert: the cell updates in-place (HTMX), meal name changes, page does not reload

**`test_shopping_flow.py`**
- Pre-seed a `ShoppingList` with items
- Navigate to `/shopping/`
- Check off an item
- Assert: checkbox state persists after page reload (HTMX POST round-trip)

---

## Mocking the Anthropic Client

Never call the real API in tests. Patch `ai.client.get_client` (or the singleton) to return a mock that yields pre-canned fixture JSON. Keep fixture JSON files in `tests/fixtures/`:

```
tests/fixtures/
├── week_plan_valid.json          # valid 7-day plan response
├── week_plan_invalid_json.txt    # malformed (triggers JSONDecodeError path)
├── week_plan_bad_nutrition.json  # valid JSON but totals out of ±15% range
└── swap_response.json            # single-meal swap response
```

---

## Phase Coverage

| Phase | New test scope |
|---|---|
| Phase 1 | Unit + integration + E2E for nutrition, meals, shopping |
| Phase 2 | Pantry views; pantry-aware prompt injection; nutrition summary bar |
| Phase 3 | Rating persistence; rating history injected into prompt |
| Phase 4 | Second brain query/inject; weekly reflection save |
| Phase 5 | Per-user data isolation (each assertion run as two different users) |
