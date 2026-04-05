# Meal Planner Agent Improvement Plan

**Source:** Analysis of generated meal plan `john_2026-04-04_meal_plan.json` graded against `meal_planner_agent.md` and `john_2026-04-04.json`  
**Date:** April 2026  
**Agent file:** `meal_planner_agent.md`  
**Overall grade of current output:** C−

---

## Root Cause Analysis

The meal planner agent has three categories of failure:

**1. No self-verification loop** — the agent generates meals and writes the file without checking whether the output actually hits the macro targets it was given. It set its own ±15% compliance rule and violated it 6 of 7 days with no correction.

**2. Inherited bad inputs, made them worse** — the nutrition plan JSON already had underspec'd protein (155g vs. the recommended 195g). The meal planner failed to hit even that lower floor, averaging ~115g/day. A self-check would have caught this before writing.

**3. Rule ambiguity exploited incorrectly** — the `meal_variety: "low"` rule permits repetition but was interpreted as license to serve the same afternoon snack all 7 days. The batch-cook tagging was applied but no actionable batch cook summary was produced.

---

## Macro Compliance Audit (Current Output)

Target from nutrition plan: **2,200 cal | 155g protein | 235g carbs | 70g fat**  
Agent-defined tolerance: **±15%** → acceptable range: **1,870–2,530 cal | 132–178g protein**

| Day | Calories | Cal Pass? | Protein | Protein Pass? |
|---|---|---|---|---|
| Mon (0) | 1,910 | ⚠️ Barely | 124g | ❌ |
| Tue (1) | 1,790 | ❌ | 105g | ❌ |
| Wed (2) | 1,900 | ✅ | 135g | ✅ |
| Thu (3) | 1,810 | ❌ | 111g | ❌ |
| Fri (4) | 1,750 | ❌ | 102g | ❌ |
| Sat (5) | 1,790 | ❌ | 105g | ❌ |
| Sun (6) | 1,740 | ❌ | 121g | ❌ |

**6 of 7 days fail calories. 6 of 7 days fail protein.**  
Average daily shortfall: **~380 calories and ~40g protein** — systematic, not rounding error.

---

## What the Agent Does Well — Do Not Change

- Heart-healthy food selection (salmon, walnuts, olive oil, oats, avocado) — `heart_healthy: true` flag correctly applied at the ingredient level
- Cook time compliance — no meal exceeded the 60-minute max
- Schema structure — JSON well-formed, all required fields present, ingredient categories and tag formatting correct
- Cuisine alignment — Asian, American, Italian meals match `preferred_cuisines`
- Meal prep tagging — batch-cook candidates correctly tagged; Sunday prep referenced in ingredient notes
- Ingredient quality notes — detail like "omega-3 enriched eggs if available" and "skin-on salmon for omega-3s" show good nutritional awareness
- Night snack gating — correctly omitted on non-karate days per notes field

---

## Proposed Changes

---

### Change 1: Macro Verification and Gap-Filling Loop

**Problem:** The agent generates meals and writes the file in a single pass with no verification step. It produced a plan that fails its own ±15% rule on 6 of 7 days and never self-corrected.

**Solution:** Add a mandatory verification loop between generation and file write.

#### Required Logic

After generating all 7 days of meals, before writing any output:

1. Sum all meal slot macros for each day
2. Compare day totals to nutrition plan targets ± 15%
3. For each failing day:
   - If **calories low**: add a protein-dense snack or increase a meal portion
   - If **protein low**: swap or augment with a high-protein item (see protein gap table below)
   - If **calories high**: reduce a snack or swap a side
4. Re-sum and re-check after each correction
5. Only write the file when all 7 days pass — or flag explicitly in output if a day cannot be corrected within other constraints

#### Protein Gap Response Table

| Protein Shortfall | Correction |
|---|---|
| < 15g | Add: cottage cheese (14g/½ cup), hard-boiled egg x2 (12g), Greek yogurt (17g/¾ cup) |
| 15–30g | Add: protein shake (25g), 3 oz canned tuna (20g) + 1 hard-boiled egg |
| > 30g | Swap a meal — breakfast oatmeal → egg scramble + Greek yogurt; or add a second protein-dense snack slot |

#### Add to Agent Instructions

```
## Macro verification (required before file write)

After generating all meals, perform a day-by-day macro audit:
1. Sum calories, protein_grams, carbs_grams, fat_grams for every slot in each day
2. Compare to nutrition plan targets ± 15%
3. For any failing day, add or swap meals/ingredients to close the gap
4. Re-verify after corrections
5. Do not write the file until all days pass, or explicitly note which days could not be corrected and why
6. The daily_nutrition_summary values must equal the arithmetic sum of all meal slots — verify this before writing
```

---

### Change 2: Breakfast Protein Floor

**Problem:** Oatmeal-only breakfasts contributed only 12g protein — 8% of the daily target. This makes hitting the daily protein total mathematically near-impossible for the remaining meals and forces the agent to either fail or overload later meals.

**Solution:** Add an explicit breakfast protein minimum rule.

#### Rule

**Breakfast must contribute at least 25% of `protein_grams` from the nutrition plan.**

| Nutrition Plan Protein | Minimum Breakfast Protein |
|---|---|
| 130g | 33g |
| 155g | 39g |
| 195g | 49g |

#### Acceptable Breakfast Anchors (intermediate skill level)

| Meal | Protein | Notes |
|---|---|---|
| 3-egg scramble + Greek yogurt | ~42g | Fast, batch-friendly |
| Cottage cheese bowl + fruit | ~35g | No-cook |
| Protein oats (oats + protein powder + milk) | ~38g | Batch-cook candidate |
| 4-egg veggie omelette | ~32g | 15 min cook |
| Greek yogurt parfait (2% + granola + egg side) | ~40g | Quick assembly |

#### Add to Agent Instructions

```
## Breakfast protein rule

Breakfast must supply at least 25% of the nutrition plan's daily protein_grams target.
If a breakfast meal does not meet this floor, add a protein-dense side (eggs, Greek yogurt, 
cottage cheese) or swap to a higher-protein breakfast entirely.
Oatmeal alone does not qualify as a sufficient breakfast for protein targets above 130g/day.
```

---

### Change 3: Meal Variety Rule Clarification for Snacks

**Problem:** `meal_variety: "low"` was interpreted as license to serve "Apple with Almond Butter" as the afternoon snack all 7 days. The rule permits repetition but does not intend a single snack to dominate the entire week.

**Solution:** Add a snack repetition cap and enforce minimum snack variety.

#### Rule

Regardless of `meal_variety` setting:
- **No single snack may appear more than 4 times in a 7-day plan**
- **At least 2 distinct afternoon snacks must appear across the week**
- **At least 2 distinct night snacks must appear across the week** (if `include_night_snack: true`)

#### Update to Meal Variety Table

| `meal_variety` | Main Meal Rule | Snack Rule |
|---|---|---|
| `"high"` | No recipe name appears more than once across the entire plan | No snack appears more than once |
| `"medium"` | No recipe name appears more than once within the same meal slot | No snack appears more than twice |
| `"low"` | Repetition allowed; suggest 2–3 batch-cook candidates | No snack appears more than 4 times; minimum 2 distinct options |

#### Add to Agent Instructions

```
## Snack variety floor (applies at all meal_variety levels)

Snacks follow their own minimum variety rules regardless of the meal_variety setting:
- afternoon_snack: no more than 4 identical entries per week; minimum 2 distinct options
- night_snack: no more than 3 identical entries per week; minimum 2 distinct options
Batch cooking a snack is acceptable; serving only one snack all week is not.
```

---

### Change 4: Training Day Macro Cycling

**Problem:** The meal planner has no concept of training days vs. rest days. Monday and Wednesday are karate days with higher calorie and carb needs, but the plan treats all 7 days identically. The nutrition plan JSON notes field explicitly states karate twice weekly.

**Solution (Phase 1 — notes-based):** Parse the `notes` field for karate/training day references and apply a calorie/carb uplift on those days even without explicit training day fields in the JSON.

**Solution (Phase 2 — field-based):** Once the dietitian agent improvement adds `training_day_calories`, `training_day_carbs_grams`, `rest_day_calories`, and `rest_day_carbs_grams` fields, consume them directly.

#### Phase 1 Logic (immediate)

```
If notes field contains keywords ["karate", "martial arts", "training", "workout", "gym"] 
AND activity_sessions_per_week can be inferred:
  - Identify training days from notes (e.g. "Mondays and Wednesdays")
  - Apply +200 to +300 calorie uplift on those days, sourced from carbohydrates (+50–75g carbs)
  - Flag training days in terminal summary output
  - Tag training day meals with "training-day" in tags array
```

#### Phase 2 Logic (post-dietitian agent improvement)

```
If training_day_calories is not null in nutrition plan:
  - Use training_day_calories / training_day_carbs_grams for days matching training schedule
  - Use rest_day_calories / rest_day_carbs_grams for all other days
  - Protein stays flat across all days (training_day_protein_grams == rest_day_protein_grams)
  - Verify each day against its appropriate target (not the average daily_calories)
```

#### New JSON Fields to Add to Meal Plan Output

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

---

### Change 5: Batch Cook Summary Block

**Problem:** Batch-cook tags are applied correctly but there is no actionable summary of what to actually cook on Sunday, in what quantities, and for how many days it serves. The information exists in the plan but is not surfaced usably.

**Solution:** Add a required `batch_cook_summary` top-level field to the meal plan JSON and include it in the terminal output.

#### New JSON Field

```json
"batch_cook_summary": [
  {
    "item": "grilled chicken breast",
    "total_quantity": 35.0,
    "unit": "oz",
    "serves_days": [0, 2, 6],
    "serves_meals": ["lunch", "dinner"],
    "prep_notes": "Season simply — used in Asian bowl and tikka masala, season individually at serving"
  },
  {
    "item": "brown rice",
    "total_quantity": 5.0,
    "unit": "cups cooked",
    "serves_days": [0, 2, 6],
    "serves_meals": ["lunch", "dinner"],
    "prep_notes": "Cook plain; season at serving"
  },
  {
    "item": "rolled oats",
    "total_quantity": 2.5,
    "unit": "cups dry",
    "serves_days": [0, 1, 2, 3, 4],
    "serves_meals": ["breakfast"],
    "prep_notes": "Overnight oats option: combine with milk and refrigerate in portions"
  }
]
```

#### Terminal Output Addition

```
SUNDAY BATCH COOK LIST
────────────────────────────────────────
  Grilled chicken breast    35 oz total     → Mon lunch, Wed lunch, Sun lunch
  Brown rice                5 cups cooked   → Mon lunch, Wed dinner, Sun lunch
  Rolled oats               2.5 cups dry    → Mon–Fri breakfast
────────────────────────────────────────
```

#### Add to Agent Instructions

```
## Batch cook summary (required when meal_prep_friendly: true)

After generating the week plan, produce a batch_cook_summary array containing every 
meal-prep or batch-cook tagged ingredient, aggregated across all days that use it.
Each entry must include: item name, total quantity needed, unit, which days it serves, 
which meal slots it serves, and any prep notes relevant to multi-use (e.g. "season at serving").
Include this as a top-level field in the JSON output and print it in the terminal summary.
```

---

### Change 6: Cholesterol-Aware Numeric Compliance

**Problem:** The agent checks `heart_healthy: true` and makes good food choices in response, but there is no numeric verification of saturated fat or soluble fiber targets. Compliance is vibes-based — good ingredients don't guarantee good numbers.

**Solution (Phase 1 — immediate):** When `heart_healthy: true`, add per-day saturated fat tracking to the daily nutrition summary and flag days exceeding 20g.

**Solution (Phase 2 — post-dietitian agent improvement):** When `saturated_fat_limit_grams`, `soluble_fiber_target_grams`, and `omega3_sessions_per_week` fields are present, verify against those specific targets.

#### Phase 1 Changes

Add to meal schema:
```json
"saturated_fat_grams": 6.0
```

Add to daily_nutrition_summary:
```json
"saturated_fat_grams": 18.0,
"soluble_fiber_grams": 9.0
```

Add verification rule:
```
If heart_healthy: true:
  - Track saturated_fat_grams per meal and per day
  - Flag any day exceeding 20g saturated fat in terminal output
  - Ensure at least 3 days per week contain fatty fish (salmon, sardines, mackerel, tuna)
  - Ensure at least one soluble fiber source per day (oats, beans, avocado, chia, barley, apples)
```

#### Phase 2 Changes

```
If saturated_fat_limit_grams is not null:
  - Verify daily saturated_fat_grams <= saturated_fat_limit_grams
  - Correct non-compliant days by swapping saturated fat sources for unsaturated alternatives

If soluble_fiber_target_grams is not null:
  - Verify daily soluble_fiber_grams >= soluble_fiber_target_grams
  - Add soluble fiber sources if daily target is not met

If omega3_sessions_per_week is not null:
  - Count fatty fish meals across the week plan
  - Ensure count >= omega3_sessions_per_week
  - Flag deficit in terminal output if not achievable within other constraints
```

---

### Change 7: Daily Nutrition Summary Arithmetic Verification

**Problem:** The `daily_nutrition_summary` values are generated independently of the meal slot values. LLMs are prone to hallucinating nutrition numbers, and there is currently no check that the summary actually equals the sum of its parts.

**Solution:** Add an explicit arithmetic verification step as part of the pre-write verification loop.

#### Rule

```
For each day 0–6:
  computed_calories = sum of calories across all meal slots for that day
  computed_protein = sum of protein_grams across all meal slots for that day
  computed_carbs = sum of carbs_grams across all meal slots for that day
  computed_fat = sum of fat_grams across all meal slots for that day

  daily_nutrition_summary[day] must equal computed values within ±5 kcal / ±1g macro
  If values differ by more than this threshold, recalculate and correct before writing
```

#### Add to Agent Instructions

```
## Nutrition summary integrity check (required)

Before writing the file, verify that daily_nutrition_summary values for each day equal 
the arithmetic sum of all meal slot nutrition fields for that day.
Tolerance: ±5 kcal for calories, ±1g for each macro.
If any day's summary does not match, recalculate from meal slots and update the summary.
Do not rely on independently estimated summary values — always derive from meal slot data.
```

---

### Change 8: Consecutive Identical Meal Prevention

**Problem:** Oatmeal with Banana and Walnuts appeared on Monday and Tuesday back-to-back. For `meal_variety: "low"` this is technically permitted but produces a poor experience and signals lazy generation.

**Solution:** Add a soft rule preventing identical meals on consecutive days, regardless of variety setting.

#### Rule

```
Regardless of meal_variety setting:
- No meal slot (breakfast, lunch, dinner) may have the same recipe name on two consecutive days
- Snacks are exempt from this rule (batch-cook snacks may repeat on consecutive days)
- If the only available compliant meal would repeat, choose the closest alternative and note it
```

#### Add to Agent Instructions

```
## Consecutive day repetition rule

The same recipe name must not appear in the same meal slot on two consecutive days, 
regardless of meal_variety setting. For example, if Monday breakfast is "Oatmeal with 
Banana and Walnuts", Tuesday breakfast must be something different.
Snack slots are exempt — a batch-cook snack may repeat on consecutive days.
```

---

## Schema Changes Summary

### New Fields — Meal Plan JSON (top level)

```json
{
  "training_days": [0, 2],
  "day_type": {
    "0": "training",
    "1": "rest",
    "2": "training",
    "3": "rest",
    "4": "rest",
    "5": "rest",
    "6": "rest"
  },
  "batch_cook_summary": []
}
```

### New Fields — Per Meal

```json
{
  "saturated_fat_grams": 0.0
}
```

### New Fields — daily_nutrition_summary (per day)

```json
{
  "saturated_fat_grams": 0.0,
  "soluble_fiber_grams": 0.0
}
```

### Field Rules to Add

- `training_days`: array of day key integers (0–6); empty array `[]` if no training days identified
- `day_type`: object with keys `"0"`–`"6"`, values one of `"training"` or `"rest"`
- `batch_cook_summary`: array of batch cook objects; empty array `[]` if `meal_prep_friendly: false`
- `saturated_fat_grams`: float with one decimal place; required when `heart_healthy: true`, optional otherwise

---

## Implementation Priority

| Priority | Change | Effort | Impact |
|---|---|---|---|
| P0 | Change 1: Macro verification and gap-filling loop | High | Fixes the core failure — 6/7 days missing targets |
| P0 | Change 2: Breakfast protein floor | Low | Prevents the cascading protein deficit from the first meal |
| P0 | Change 7: Daily nutrition summary arithmetic check | Low | Ensures JSON integrity — catches hallucinated numbers |
| P1 | Change 3: Snack variety rule clarification | Low | Fixes the 7-day identical snack problem |
| P1 | Change 8: Consecutive identical meal prevention | Low | Improves experience without breaking batch-cook intent |
| P2 | Change 5: Batch cook summary block | Medium | High practical value for Sunday prep |
| P2 | Change 4 Phase 1: Training day cycling (notes-based) | Medium | Meaningful for active users |
| P3 | Change 6 Phase 1: Heart-healthy numeric compliance | Medium | Upgrades from vibes to verified |
| P4 | Change 4 Phase 2: Training day cycling (field-based) | Low | Depends on dietitian agent improvement delivery |
| P4 | Change 6 Phase 2: Cholesterol field consumption | Low | Depends on dietitian agent improvement delivery |

---

## Dependency on Dietitian Agent Improvements

Changes 4 Phase 2 and 6 Phase 2 require fields that do not yet exist in the nutrition plan JSON schema. These are blocked until the following dietitian agent improvements are delivered:

- `training_day_calories`, `training_day_carbs_grams`, `rest_day_calories`, `rest_day_carbs_grams`
- `cholesterol_focus`, `saturated_fat_limit_grams`, `soluble_fiber_target_grams`, `omega3_sessions_per_week`

Refer to `dietician_improvement_plan.md` for the dietitian agent improvement roadmap and delivery order.

---

## Verification Checklist (Add to Agent)

Before writing any meal plan file, the agent must be able to answer yes to all of the following:

- [ ] All 7 days pass the ±15% calorie target check
- [ ] All 7 days pass the ±15% protein target check
- [ ] Breakfast protein meets the 25% daily floor on every day
- [ ] No afternoon snack appears more than 4 times
- [ ] No night snack appears more than 3 times
- [ ] No recipe repeats in the same meal slot on consecutive days
- [ ] `daily_nutrition_summary` values match arithmetic sum of meal slots (±5 kcal / ±1g)
- [ ] At least 3 fatty fish meals present in the week (if `heart_healthy: true`)
- [ ] Batch cook summary populated (if `meal_prep_friendly: true`)
- [ ] All cook times within `max_cook_time_minutes`
- [ ] No disliked foods or allergens present

---

*Plan authored April 2026. Implement P0 changes first — they address the most critical failures with the least schema disruption. P4 changes are blocked on dietitian agent delivery.*
