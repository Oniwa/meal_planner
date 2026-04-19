# verify_meal_plan.py — Meal Plan Verification Script

**Source:** Grilling session on meal_planner_agent_improvements.md — April 2026
**Agent version required:** dietitian_agent >= 2.0 (nested meal_variety schema and training_days field must be present)
**Artifact version produced:** verify_meal_plan.py 1.0
**Depends on:** dietitian_agent_variety_training_update.md (schema must be final before writing)
**Used by:** meal_planner_agent_improvements_v2.md (agent calls this script via Bash tool)
**Future reuse:** Phase 1 Django — import as a Python module inside `ai/meal_planner_agent.py`

---

## Purpose

A deterministic verification script that checks a generated meal plan JSON against a nutrition plan JSON. Used by the meal planner agent as a Bash tool call between generation and file write. Eliminates reliance on LLM self-verification for every check that can be computed deterministically.

---

## Interface

### CLI (Phase 0 — called by the agent via Bash tool)

```
python scripts/verify_meal_plan.py <meal_plan_path> <nutrition_plan_path>
```

**Exit codes:**
- `0`: all checks pass
- `1`: one or more checks fail

**Output:** always printed to stdout — the agent reads this to determine corrections needed.

### Python module (Phase 1 Django — imported by `ai/meal_planner_agent.py`)

Write the core logic in importable functions; keep the CLI wrapper thin:

```python
from scripts.verify_meal_plan import verify_plan

result = verify_plan(meal_plan_dict, nutrition_plan_dict)
# result.passing_days: list[int]
# result.failing_days: dict[int, list[CheckFailure]]
# result.global_failures: list[CheckFailure]
# result.all_pass: bool
```

The structured `result` object is what enables Opus escalation in Phase 1 — `ai/meal_planner_agent.py` calls `verify_plan()` after each attempt, checks `result.failing_days`, and on the third attempt switches to `claude-opus-4-7` for any day still in `result.failing_days`. The script is model-agnostic; escalation logic lives entirely in the Python wrapper.

---

## Output Format

Always print the full report — even on a full pass — so the agent has explicit confirmation.

```
VERIFICATION REPORT
────────────────────────────────────────────────────────────
GLOBAL CHECKS
  Allergen check:        PASS
  Disliked foods:        PASS
  Fatty fish count:      PASS  (3 sessions found, target ≥ 3)
  Batch cook coverage:   PASS

DAY-BY-DAY CHECKS
  Day 0 (Mon) [TRAINING]:
    Calories:            FAIL  got 1910, target 2400±15% (2040–2760) — short by 130
    Protein:             FAIL  got 124g, target 195g±15% (166–224g) — short by 42g
    Carbs:               PASS  got 270g, target 275g±15%
    Fat:                 PASS
    Summary arithmetic:  PASS
    Breakfast protein:   FAIL  got 12g (6%), floor is 49g (25% of 195g)
    Cook times:          PASS
    Variety rules:       PASS
    Consecutive repeat:  PASS
    Sat fat:             PASS  18g ≤ 20g limit

  Day 1 (Tue) [REST]:
    Calories:            FAIL  got 1790, target 2200±15% (1870–2530) — short by 80
    ...

CORRECTIONS NEEDED
  Day 0 (Mon):
    - Protein short by 42g — add protein-dense item or swap a meal
    - Calories short by 130 — a protein addition will likely close this gap too
    - Breakfast protein 12g (6%) — swap to qualifying anchor (≥49g); oatmeal alone does not qualify
  Day 1 (Tue):
    - Calories short by 80 — add a snack or increase a meal portion

SUMMARY
  Days passing all checks: 1 of 7
  Global checks passing:   4 of 4
  Days needing correction: [0, 1, 3, 4, 5, 6]
────────────────────────────────────────────────────────────
```

---

## Checks Implemented

### Global checks (run once per plan)

| Check | Logic |
|---|---|
| Allergen check | For every ingredient in every meal slot, check `ingredient.name` does not appear in `nutrition_plan.allergies` — case-insensitive substring match |
| Disliked foods | Same logic against `nutrition_plan.disliked_foods` |
| Fatty fish count | Count meals where any ingredient name matches `["salmon", "sardines", "mackerel", "tuna", "herring", "trout"]`; compare to `omega3_sessions_per_week`. Skip if `cholesterol_focus: false` or `omega3_sessions_per_week` is null |
| Batch cook coverage | When `meal_prep_friendly: true`: confirm `batch_cook_summary` field exists and is non-empty; confirm every ingredient with `"meal-prep"` or `"batch-cook"` in its tags has a matching entry in `batch_cook_summary[].item` |

### Per-day checks (run for each day 0–6)

| Check | Logic |
|---|---|
| Calories | Sum `calories` across all meal slots for the day. Target: use `training_day_calories` if day index is in `nutrition_plan.training_days` and `training_day_calories` is not null; else use `rest_day_calories` if carb cycling is active; else `daily_calories`. Compare to target ±15% |
| Protein | Sum `protein_grams`; compare to `protein_grams` ±15% |
| Carbs | Sum `carbs_grams`; compare to appropriate carbs target ±15% (training/rest/daily) |
| Fat | Sum `fat_grams`; compare to `fat_grams` ±15% |
| Summary arithmetic | Compare each `daily_nutrition_summary[day]` value to the computed sum; flag if calories differ by >5 kcal or any macro differs by >1g |
| Breakfast protein floor | `breakfast.protein_grams / nutrition_plan.protein_grams ≥ 0.25`; report actual % and required grams |
| Cook time | For every meal slot: `prep_time_minutes + cook_time_minutes ≤ max_cook_time_minutes` |
| Variety — none | When `meal_variety.<slot>` is `"none"`: all 7 days must have the same recipe name in that slot |
| Variety — low | When `"low"`: count distinct recipe names in this slot across 7 days; flag if < 3 |
| Variety — medium | When `"medium"`: flag any recipe name appearing more than once in the same slot |
| Variety — high | When `"high"`: flag any recipe name appearing more than once anywhere in the plan |
| Consecutive repeat | For breakfast, lunch, dinner: flag if day N and day N+1 share the same recipe name in the same slot. Skip this check when `meal_variety.<slot>` is `"none"`. Snack slots are always exempt |
| Saturated fat | Sum `saturated_fat_grams` across all meal slots; compare to `saturated_fat_limit_grams`. Skip if null |
| Soluble fiber | Read `soluble_fiber_grams` from `daily_nutrition_summary[day]`; compare to `soluble_fiber_target_grams`. Skip if null |

---

## Correction Output Format

For each failing day, output specific, actionable deltas — not generic advice:

```
CORRECTIONS NEEDED FOR DAY 0 (Mon) [TRAINING]:
  - Protein short by 42g:
      < 15g gap: add cottage cheese (14g/½ cup), 2 hard-boiled eggs (12g), or Greek yogurt (17g/¾ cup)
      15–30g gap: add protein shake (25g) or 3 oz canned tuna + 1 hard-boiled egg
      > 30g gap: swap a meal — replace oatmeal breakfast with egg scramble + Greek yogurt
  - Calories short by 130: a protein addition above will likely close this; re-verify before adding more
  - Breakfast protein 12g (6% of 195g target): floor is 49g (25%) — swap to a qualifying anchor
```

---

## Best-Attempt Tracking

The agent tracks the best attempt per failing day across up to 3 correction iterations. The script does not track state between runs — it evaluates the current draft only. The agent is responsible for:

1. Storing the deficit total from each attempt
2. Keeping the draft content of the best attempt seen per day
3. After 3 attempts, assembling the final plan from best-per-day attempts

---

## File Location

`scripts/verify_meal_plan.py` — project root `scripts/` directory.

Create the directory before writing the script:
```
mkdir scripts
touch scripts/__init__.py
```

Run from project root:
```
python scripts/verify_meal_plan.py meal_plans/.draft_john_2026-04-07.json nutrition_plans/john_2026-04-08.json
```

## Implementation Notes

### Null/missing-key handling

Several checks depend on fields added by later changes in `meal_planner_agent_improvements_v2.md`. The script must skip gracefully when these fields are absent — do not raise KeyError or treat missing as zero:

| Field | Added by | Script behavior when absent |
|---|---|---|
| `daily_nutrition_summary[day].soluble_fiber_grams` | Change 6 (P3) | Skip soluble fiber check for that day |
| `meal[slot].saturated_fat_grams` | Change 6 (P3) | Skip saturated fat check |
| `nutrition_plan.training_days` | Dietitian update | Treat all days as non-training; use `daily_calories` |
| `meal_plan.batch_cook_summary` | Change 5 (P2) | Skip batch cook coverage check |

Pattern: `if field is None or field not in obj: skip_check()` — never coerce null to 0.

### Batch cook coverage check — correct logic

The check verifies that every *ingredient name* appearing in a meal-prep-tagged meal slot also appears as an entry in `batch_cook_summary[].item`. It does **not** check ingredient tags against summary item names — it checks ingredient names:

```python
# For each day, for each slot, for each ingredient:
if any(tag in ["meal-prep", "batch-cook"] for tag in slot["tags"]):
    for ingredient in slot["ingredients"]:
        assert any(
            entry["item"] == ingredient["name"]
            for entry in meal_plan["batch_cook_summary"]
        ), f"Missing from batch_cook_summary: {ingredient['name']}"
```

The slot's tags (not the ingredient's tags) gate whether the slot's ingredients need coverage.
