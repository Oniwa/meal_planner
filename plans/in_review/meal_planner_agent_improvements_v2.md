# Meal Planner Agent Improvement Plan v2

**Source:** Grilling session on meal_planner_agent_improvements.md — April 2026
**Supersedes:** plans/done/meal_planner_agent_improvements.md
**Agent version required:** meal_planner_agent 1.0, dietitian_agent >= 2.0, verify_meal_plan.py >= 1.0
**Agent version produced:** meal_planner_agent 2.0
**Depends on:** dietitian_agent_variety_training_update.md (must be complete, fresh nutrition plan generated), verify_meal_plan_script.md (script must exist at scripts/verify_meal_plan.py)
**Minimum required fields in fresh nutrition plan:** `meal_variety` as nested object (not flat string), `training_days` as array — do not test against `john_2026-04-04.json` which has the old schema
**Agent file:** `.claude/agents/meal_planner_agent.md`
**Overall grade of current output:** C−

---

## Root Cause Analysis

1. **No self-verification loop** — generates and writes in a single pass; violated its own ±15% rule 6/7 days with no correction
2. **Inherited bad inputs, made worse** — nutrition plan had underspec'd protein (155g vs. recommended 195g); meal planner failed to hit even that lower floor, averaging ~115g/day
3. **Rule ambiguity exploited** — `meal_variety: "low"` interpreted as license to serve the same afternoon snack all 7 days

---

## Changes Summary

| # | Change | Status vs. v1 | Priority |
|---|---|---|---|
| 1 | Macro verification and gap-filling loop | Redesigned — C mechanism via verify script | P0 |
| 2 | Breakfast protein floor | Retained; clarified for per-slot variety | P0 |
| 3 | Snack variety caps | **Superseded** by per-slot meal_variety | — |
| 4 | Training day macro cycling | Phase 1 dropped; Phase 2 unblocked | P2 |
| 5 | Batch cook summary block | Retained; unit consistency rule added | P2 |
| 6 | Cholesterol-aware compliance | Phase 1 dropped; Phase 2 unblocked | P3 |
| 7 | Daily nutrition summary arithmetic | Absorbed into verify script | P0 |
| 8 | Consecutive identical meal prevention | Retained; suppressed for variety=none | P1 |
| NEW | Per-slot meal_variety consumption | New — consumes dietitian schema change | P0 |

---

## Change 1: Macro Verification and Gap-Filling Loop (REDESIGNED)

### Mechanism

The agent calls `scripts/verify_meal_plan.py` via its Bash tool — deterministic code, not LLM self-estimation.

### Required Logic

After generating all 7 days:

1. Write the draft to `meal_plans/.draft_<name>_<date>.json`
2. Call:
   ```
   python scripts/verify_meal_plan.py meal_plans/.draft_<name>_<date>.json <nutrition_plan_path>
   ```
3. Read the output report
4. For each FAILING day independently:
   - Apply corrections based on the script's specific delta output
   - Overwrite the draft with the corrected day only — do not touch passing days
   - Re-run the verify script; re-verify ALL macros (a protein fix changes calorie totals)
   - Repeat up to **3 attempts** per failing day
   - After 3 attempts, lock in the best attempt for that day (smallest total macro deficit)
5. Rename draft to final path
6. If any days still fail after 3 attempts, include explicit flags in terminal output and JSON

### Add to Agent Instructions

```
## Verification loop (required before final file write)

After generating all 7 days:
1. Write draft to meal_plans/.draft_<name>_<date>.json
2. Run: python scripts/verify_meal_plan.py meal_plans/.draft_<name>_<date>.json <nutrition_plan_path>
3. Read the output — do not estimate compliance from your own reasoning
4. For each failing day:
   - Apply corrections specified in the script output (targeted to that day only)
   - Re-run the script after each correction — re-check all macros, not just the corrected one
   - Repeat up to 3 times per failing day
   - After 3 attempts, use the best attempt for that day (smallest total deficit)
5. Rename draft to final path when done
6. If any days still fail, add to JSON: "compliance_flags": ["Day 0: protein short 18g after 3 attempts"]
   and flag them in the terminal summary

Always produce a plan — never block on persistent failure.
```

---

## Change 2: Breakfast Protein Floor (RETAINED)

### Rule

Breakfast must contribute at least 25% of the nutrition plan's `protein_grams` target.

### Interaction with Per-Slot Variety

| Slot variety | Rule |
|---|---|
| `"none"` | The single chosen breakfast must meet the floor |
| `"low"` | Every one of the ≥3 distinct breakfasts must meet the floor |
| `"medium"` or `"high"` | Every breakfast must meet the floor |

### Acceptable Breakfast Anchors (intermediate skill level)

| Meal | Protein | Notes |
|---|---|---|
| 3-egg scramble + Greek yogurt | ~42g | Fast, batch-friendly |
| Cottage cheese bowl + fruit | ~35g | No-cook |
| Protein oats (oats + protein powder + milk) | ~38g | Batch-cook candidate |
| 4-egg veggie omelette | ~32g | 15 min cook |
| Greek yogurt parfait (2% + granola + egg side) | ~40g | Quick assembly |

Oatmeal alone does not qualify for protein targets above 130g/day.

### Add to Agent Instructions

```
## Breakfast protein rule

Breakfast must supply at least 25% of the nutrition plan's daily protein_grams target.
This applies to every breakfast — including the repeated breakfast when variety is "none" or "low".
If a breakfast does not meet this floor, add a protein-dense side (eggs, Greek yogurt, cottage cheese)
or swap to a higher-protein breakfast.
Oatmeal alone does not qualify for protein targets above 130g/day.
```

---

## Change 3: Snack Variety Rule — SUPERSEDED

Change 3 from v1 (numeric caps: max 4x per week, min 2 distinct) is superseded by the per-slot `meal_variety` system. The `afternoon_snack` and `night_snack` keys in the nested variety object replace all snack-specific repetition caps.

---

## NEW: Per-Slot Meal Variety Consumption

### Schema

The meal planner now consumes `meal_variety` as a nested object:

```json
"meal_variety": {
  "breakfast": "none",
  "lunch": "low",
  "dinner": "high",
  "afternoon_snack": "low",
  "night_snack": "none"
}
```

### Rules Per Slot

| Level | Rule |
|---|---|
| `"none"` | All 7 days use the exact same recipe name in this slot |
| `"low"` | ≥3 distinct recipe names across the 7-day plan for this slot |
| `"medium"` | No recipe name appears more than once in this slot |
| `"high"` | No recipe name appears more than once anywhere in the entire plan |

### Replace Meal Variety Rules Section in Agent Instructions

```
## Meal variety rules

meal_variety is a per-slot object. Apply the rule for each slot independently:

| Level | Rule for this slot |
|---|---|
| "none" | Same recipe all 7 days — batch-cook optimized |
| "low" | ≥3 distinct recipes across the week |
| "medium" | No recipe repeats within this slot |
| "high" | No recipe repeats anywhere in the entire plan |

Check meal_variety.breakfast, .lunch, .dinner, .afternoon_snack, and .night_snack independently.

Night snack: only include the night_snack slot when include_night_snack is true.
meal_variety.night_snack is ignored when include_night_snack is false.
```

---

## Change 4: Training Day Macro Cycling (PHASE 2 ONLY)

Phase 1 (notes-based keyword parsing) is dropped — `training_day_calories`, `rest_day_calories`, and related fields are already present in the dietitian agent output.

### Phase 2 Logic

At startup, when `training_day_calories` is not null in the nutrition plan:

1. Read `training_days` array from the nutrition plan (e.g. `[0, 2]` = Mon + Wed)
2. Confirm with user:
   *"Your plan shows [days] as training days — is that right for this week? Any changes?"*
3. Apply `training_day_calories` / `training_day_carbs_grams` on confirmed training days
4. Apply `rest_day_calories` / `rest_day_carbs_grams` on all other days
5. Protein stays flat across all days (`training_day_protein_grams == rest_day_protein_grams`)
6. Output `training_days` and `day_type` as top-level fields in the meal plan JSON

### New JSON Output Fields

```json
"training_days": [0, 2],
"day_type": {
  "0": "training",
  "1": "rest",
  "2": "training",
  "3": "rest",
  "4": "rest",
  "5": "rest",
  "6": "rest"
}
```

### Placement in Startup Sequence

Insert after step 4 (week confirmation) and before meal generation begins:

```
Startup sequence (updated):
1. List nutrition_plans/ — show files, pre-select most recent
2. Ask which nutrition plan to use
3. Read chosen file
4. Ask which week to plan for; confirm "Planning meals for week of <date> using <label>"
5. [NEW] If training_day_calories is not null: confirm training days for this week
6. Generate meals
```

### Add to Agent Instructions

```
## Training day cycling

At startup (after confirming the week, before generating meals), check if
training_day_calories is not null in the nutrition plan. If so:
1. Read training_days (e.g. [0, 2] = Mon, Wed)
2. Confirm with user: "Your plan shows [days] as training days — correct for this week?"
   Accept changes (e.g. "move Wednesday to Thursday") and update the day list accordingly
3. Apply training_day_calories and training_day_carbs_grams on training days
4. Apply rest_day_calories and rest_day_carbs_grams on all other days
5. Protein is flat every day
6. Output training_days and day_type as top-level JSON fields
```

---

## Change 5: Batch Cook Summary Block (RETAINED)

### Unit Consistency Rule (new)

For any ingredient tagged as a batch-cook candidate, use the **same unit** across every meal that uses it. Do not use "oz" in one meal and "cup" in another for the same ingredient. This enables clean aggregation in the summary.

### Agent-Generated Summary

The agent generates `batch_cook_summary` directly — it knows which ingredients repeat. The verify script checks presence and coverage; it does not recompute quantities.

### Required JSON Field

```json
"batch_cook_summary": [
  {
    "item": "grilled chicken breast",
    "total_quantity": 35.0,
    "unit": "oz",
    "serves_days": [0, 2, 4],
    "serves_meals": ["lunch"],
    "prep_notes": "Season simply — season individually at serving for different dishes"
  }
]
```

### Terminal Output Addition

```
SUNDAY BATCH COOK LIST
────────────────────────────────────────
  Grilled chicken breast    35 oz total     → Mon, Wed, Fri lunch
  Brown rice                5 cups cooked   → Mon, Wed, Fri lunch
  Rolled oats               2.5 cups dry    → Mon–Fri breakfast
────────────────────────────────────────
```

### Add to Agent Instructions

```
## Batch cook summary (required when meal_prep_friendly: true)

After generating the week plan:
1. Use consistent units for batch-cook ingredients across all meals (e.g., always "oz" — never mix "oz" and "cup" for the same ingredient)
2. Aggregate batch-cook ingredients across all days
3. Output batch_cook_summary as a top-level JSON field
4. Print the SUNDAY BATCH COOK LIST in the terminal summary
```

---

## Change 6: Cholesterol-Aware Numeric Compliance (PHASE 2 ONLY)

Phase 1 (vibes-based) is dropped — `saturated_fat_limit_grams`, `soluble_fiber_target_grams`, and `omega3_sessions_per_week` are already present in the dietitian agent output.

### Phase 2 Logic

```
If saturated_fat_limit_grams is not null:
  - Track saturated_fat_grams per meal and per day
  - Verify daily total ≤ saturated_fat_limit_grams
  - Swap high-sat-fat ingredients on non-compliant days

If soluble_fiber_target_grams is not null:
  - Track soluble_fiber_grams per day
  - Verify daily total ≥ soluble_fiber_target_grams
  - Add soluble fiber sources if target not met (oats, beans, avocado, chia, barley, apples)

If omega3_sessions_per_week is not null:
  - Count meals with fatty fish (salmon, sardines, mackerel, tuna, herring, trout)
  - Ensure count ≥ omega3_sessions_per_week across the 7-day plan
```

### New Schema Fields

Per meal:
```json
"saturated_fat_grams": 6.0
```

Per day in `daily_nutrition_summary`:
```json
"saturated_fat_grams": 18.0,
"soluble_fiber_grams": 9.0
```

---

## Change 7: Daily Nutrition Summary Arithmetic

Fully absorbed into `verify_meal_plan.py` (summary arithmetic check, tolerance ±5 kcal / ±1g). No separate agent instruction needed — the verification loop in Change 1 covers this.

---

## Change 8: Consecutive Identical Meal Prevention (RETAINED, UPDATED)

### Rule

- Applies to: `breakfast`, `lunch`, `dinner`
- **Suppressed** when `meal_variety.<slot>` is `"none"` — same recipe every day is intentional
- **Always exempt:** `afternoon_snack`, `night_snack` — batch-cook snacks may repeat consecutively

### Add to Agent Instructions

```
## Consecutive day repetition rule

For breakfast, lunch, and dinner:
- If meal_variety for that slot is "none": the same recipe must appear all 7 days (intentional)
- Otherwise: the same recipe name must not appear in the same slot on two consecutive days

Snack slots (afternoon_snack, night_snack) are always exempt from this rule.
```

---

## Updated Schema Summary

### New Top-Level Fields (meal plan JSON)

```json
{
  "training_days": [],
  "day_type": {},
  "batch_cook_summary": [],
  "compliance_flags": []
}
```

### Field Rules for New Fields

- `training_days`: array of integers 0–6; `[]` when carb cycling not active
- `day_type`: object with string keys `"0"`–`"6"`, values `"training"` or `"rest"`; `{}` when carb cycling not active
- `batch_cook_summary`: array of batch cook objects; `[]` when `meal_prep_friendly: false`
- `compliance_flags`: array of strings describing days that could not be corrected within 3 attempts; `[]` when all days pass. Format: `"Day 0 (Mon): protein short by 18g after 3 correction attempts — best result was 177g of 195g target"`; always present as `[]` even when no flags

### New Per-Meal Fields

```json
{
  "saturated_fat_grams": 0.0
}
```

### Updated `daily_nutrition_summary` Per Day

```json
{
  "calories": 0.0,
  "protein_grams": 0.0,
  "carbs_grams": 0.0,
  "fat_grams": 0.0,
  "saturated_fat_grams": 0.0,
  "soluble_fiber_grams": 0.0
}
```

---

## Updated Verification Checklist

The verify script confirms all of the following before the agent writes the final file:

- [ ] All 7 days pass ±15% calorie target (training/rest/daily targets applied per day)
- [ ] All 7 days pass ±15% protein target
- [ ] All 7 days pass ±15% carbs and fat targets
- [ ] Breakfast protein ≥25% of daily protein target on every day
- [ ] Per-slot variety rules satisfied (none/low/medium/high per slot)
- [ ] No recipe repeats in the same main meal slot on consecutive days (unless variety=none)
- [ ] `daily_nutrition_summary` matches arithmetic sum of meal slots (±5 kcal / ±1g)
- [ ] No allergens in any ingredient
- [ ] No disliked foods in any ingredient
- [ ] All cook times within `max_cook_time_minutes`
- [ ] Fatty fish count ≥ `omega3_sessions_per_week` (when `cholesterol_focus: true`)
- [ ] Saturated fat ≤ `saturated_fat_limit_grams` per day (when set)
- [ ] `batch_cook_summary` present and covers all meal-prep tagged ingredients (when `meal_prep_friendly: true`)

---

## Future Improvements

- **Week-to-week overrides:** Accept per-slot variety and training day overrides at generation time without re-running the dietitian agent
- **Best-attempt memory:** Grade all correction attempts per failing day; surface the full attempt history in `compliance_flags`
- **Fitbit MCP server:** Wire historical workout data to populate `training_days` automatically; feed real wearable burn data to the dietitian agent
- **Phase 1 — Opus escalation on third attempt:** In `ai/meal_planner_agent.py`, switch to `claude-opus-4-7` for the third and final correction attempt on any failing day. Sonnet handles attempts 1 and 2; Opus only fires when needed. Note: escalation helps reasoning failures — if the failure is structural (constraint violation that no model can solve), the verify script output will make this clear regardless of model used

---

*Implement only after dietitian_agent_variety_training_update.md is complete and a fresh nutrition plan JSON has been generated. Scripts/verify_meal_plan.py must exist before the verification loop can be tested.*
