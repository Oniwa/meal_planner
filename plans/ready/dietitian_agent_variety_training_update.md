# Dietitian Agent Update — Per-Slot Meal Variety and Training Days

**Source:** Grilling session on meal_planner_agent_improvements.md — April 2026
**Agent version required:** dietitian_agent 1.0
**Agent version produced:** dietitian_agent 2.0
**Depends on:** Nothing (prerequisite for verify_meal_plan_script.md and meal_planner_agent_improvements_v2.md)

---

## Summary

Two targeted additions to the dietitian agent:
1. Replace the global `meal_variety` flat string with a per-slot nested object
2. Add `training_days` field capturing which days of the week the user typically trains

Both require updates to the interview flow, JSON schema, and field rules.

---

## Change 1: Per-Slot Meal Variety

### Problem

The current `meal_variety: "medium"` flat string applies one variety level to all meal slots. Users may want no variety at breakfast (same every day), low variety at lunch, and high variety at dinner — the single field cannot express this.

### New Field

Replace:
```json
"meal_variety": "medium"
```

With:
```json
"meal_variety": {
  "breakfast": "none",
  "lunch": "low",
  "dinner": "high",
  "afternoon_snack": "low",
  "night_snack": "none"
}
```

### Variety Levels

| Level | Rule |
|---|---|
| `"none"` | Generate 1 meal for this slot; repeat all 7 days |
| `"low"` | Repetition allowed; ≥3 distinct options per week |
| `"medium"` | No repeat within the same slot across the week |
| `"high"` | No repeat across the entire plan |

### Updated Interview Flow

Replace the current single `meal_variety` question with a two-step probe:

**Step 1 — Global default:**
*"How much variety do you want in your meals day to day? Some people are happy eating the same thing every day, others want something different every meal — or anywhere in between."*
Map answer to one of: `"none"`, `"low"`, `"medium"`, `"high"`. Set as default for all 5 slots.

**Step 2 — Per-slot exception probing:**
*"Is there any meal type where you'd want something different? For example, some people are happy eating the same breakfast every day but want dinners to change."*
Update only the slots the user calls out.

**Step 3 — Snack follow-up:**
*"For snacks — do you want the same snack every day, or some variety there too?"*
Set `afternoon_snack` and `night_snack` independently if the user specifies.

### Key Rule: `include_night_snack` and `meal_variety.night_snack` are orthogonal

- `include_night_snack: false` = no night snack slot at all — do not ask about night snack variety
- `include_night_snack: true` + `meal_variety.night_snack: "none"` = same night snack every night
- Only ask about `night_snack` variety when `include_night_snack: true`
- Default `meal_variety.night_snack` to `"none"` when `include_night_snack: false`

### Updated Field Rules

- `meal_variety`: object with exactly these keys: `breakfast`, `lunch`, `dinner`, `afternoon_snack`, `night_snack`
- Each value: one of `"none"`, `"low"`, `"medium"`, `"high"`
- All 5 keys must be present; default all to the global answer if no per-slot exceptions given

### Specific Lines to Change in `dietitian_agent.md`

**Field rules section — replace:**
```
- `meal_variety`: one of `"high"`, `"medium"`, `"low"`
```
**With:**
```
- `meal_variety`: object with keys `breakfast`, `lunch`, `dinner`, `afternoon_snack`, `night_snack`; each value one of `"none"`, `"low"`, `"medium"`, `"high"`; all 5 keys always present
```

**Report field section — add to "Include only when applicable":**
```
- **Meal variety summary**: if any slot differs from the global default, note the per-slot breakdown in plain language (e.g. "Same breakfast every day, varied dinners")
```

---

## Change 2: Training Days Field

### Problem

The dietitian agent already outputs `training_day_calories`, `rest_day_calories`, etc. — the per-day macro targets exist. But nothing records *which specific days of the week* are training days. The meal planner cannot apply training-day targets without knowing the schedule.

### New Field

```json
"training_days": [0, 2]
```

Day offsets: 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday.
Empty array `[]` if no structured exercise or carb cycling does not apply.

### Interview Addition

When structured exercise is confirmed AND `activity_sessions_per_week` ≥ 2 AND carb cycling applies (intensity = "high"):

*"Which days of the week do you typically train?"*
Map day names to integers 0–6. Store as `training_days`.

If the user says their schedule varies week to week, note it in the `notes` field — the meal planner will confirm or override at generation time.

### Field Rules

- `training_days`: array of integers 0–6; `[]` when `training_day_calories` is null
- `null` is not valid — always use `[]` for no training days
- Length should equal `activity_sessions_per_week` when a fixed schedule exists

---

## Updated JSON Schema Diff

Add to the schema (after `rest_day_fat_grams`):
```json
"training_days": []
```

Replace:
```json
"meal_variety": "medium"
```
With:
```json
"meal_variety": {
  "breakfast": "medium",
  "lunch": "medium",
  "dinner": "medium",
  "afternoon_snack": "medium",
  "night_snack": "none"
}
```

---

## Implementation Notes

- After implementing, re-run the dietitian interview for John to regenerate a fresh `nutrition_plans/john_<date>.json`
- The existing `john_2026-04-04.json` uses the old flat `meal_variety` string — do not use it as input to the updated meal planner agent
- This plan must be completed before starting `verify_meal_plan_script.md` or `meal_planner_agent_improvements_v2.md`
