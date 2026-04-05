# Dietitian Agent Improvement Plan

**Source:** Analysis comparing agent-generated nutrition JSON against a manually developed sports nutrition plan  
**Date:** April 2026  
**Agent file:** `dietitian_agent.md`  
**Sample profile:** 43-year-old male, 240 lbs, karate 2x/week, cholesterol management goal

---

## Root Cause Analysis

The agent produced a technically valid JSON but made three categories of errors:

**1. Generic macro math** — used weight-loss template defaults (~1.4 g/kg protein, 2,200 cal) without adjusting for activity type, intensity, or age. No sports nutrition logic exists in the current version.

**2. Shallow branching** — the interview captured lifestyle data well (cuisines, prep day, snack timing) but branch conditions don't connect activity data to macro calculation. Activity information was collected but not used to change the numbers.

**3. No narrative output** — the JSON is machine-readable but not human-useful. A person cannot act on it without a downstream agent or tool to interpret it.

---

## What the Agent Does Well — Do Not Change

- Cuisine preference capture
- Cook time and cooking skill level
- Meal prep day preference
- Snack timing specificity (e.g. Mon/Wed only)
- Dietary restriction and allergy collection
- Food likes and dislikes
- Overall interview warmth and flow
- JSON schema structure and field discipline

---

## Proposed Changes

---

### Change 1: Activity Intelligence Branch

**Problem:** The agent currently treats activity as a generic lifestyle descriptor. It collects that the user does karate but uses none of that data in macro calculation.

**Solution:** Add a dedicated activity branch to the interview flow.

#### New Interview Questions

Trigger this branch if the user mentions any sport, martial art, or structured exercise:

- How many sessions per week?
- How long is each session (minutes)?
- How would you describe the intensity — light, moderate, or hard?
- Does a fitness tracker report calorie burn for those sessions? If so, what does it typically say?

#### New JSON Fields

Add to schema:

```json
"activity_type": "martial_arts",
"activity_sessions_per_week": 2,
"activity_minutes_per_session": 120,
"activity_intensity": "high",
"wearable_reported_burn": 1000
```

- `activity_type`: free lowercase string (e.g. `"running"`, `"weightlifting"`, `"martial_arts"`, `"cycling"`)
- `activity_intensity`: one of `"light"`, `"moderate"`, `"high"`
- `wearable_reported_burn`: integer (calories); `null` if user does not use a tracker

---

### Change 2: Sports Nutrition Macro Calculation Logic

**Problem:** The calorie and macro estimation section uses a generic weight-loss template. It does not account for activity type, intensity, session volume, or age.

**Solution:** Replace the current flat estimation block with tiered conditional logic.

#### Protein Calculation Rules

| Condition | Protein Target |
|---|---|
| Sedentary, weight loss | 1.4 g/kg |
| Active (3+ hrs/week, moderate) | 1.6 g/kg |
| High intensity sport 2x+/week | 1.8–2.0 g/kg |
| High intensity sport 2x+/week AND age ≥ 40 | 2.0 g/kg (top of range) |

#### Calorie Calculation Rules

- Base TDEE should incorporate an activity multiplier using `activity_sessions_per_week` and `activity_intensity`, not a generic activity level selection
- If the user is doing high-intensity activity 2x+/week, cap the recommended deficit at **300 cal/day maximum**
- Flag this cap explicitly during the confirmation step with plain-language rationale

#### Carbohydrate Rules

- Add boolean field: `"glycolytic_sport"` — set to `true` for martial arts, running, cycling, team sports, HIIT
- If `glycolytic_sport: true`, carbs must be **40–50% of calories**, never below 35%
- Agent must surface this decision during confirmation: *"Because [sport] relies heavily on carbohydrates for fuel, I'm keeping carbs higher than a typical weight loss plan — this is intentional."*

---

### Change 3: Age-Aware Modifier

**Problem:** The agent has no age-based adjustment logic. At 40+, anabolic resistance means muscles require more protein stimulus to respond equivalently to a younger person doing the same activity.

**Solution:** Add a single conditional branch.

#### Rule

If `age >= 40`:
- Push protein to the **top** of the calculated range (not the midpoint)
- Add to `notes` field: *"Protein set at upper range due to age-related anabolic resistance."*

This is a small change with meaningful downstream impact on muscle retention during a caloric deficit.

---

### Change 4: Cholesterol / Heart Health Branch — Deepen It

**Problem:** The agent captures `heart_healthy: true` but the notes field produces only a vague directive ("emphasize unsaturated fats"). This is not actionable for a downstream meal planner agent.

**Solution:** Expand the heart health branch with additional interview questions and concrete JSON fields.

#### Additional Interview Questions (when heart_healthy is flagged)

- Has a doctor mentioned LDL, HDL, or triglycerides specifically?
- Are they on or considering cholesterol medication (e.g. statins)?
- Do they currently eat fatty fish? How often per week?

#### New JSON Fields

```json
"cholesterol_focus": true,
"saturated_fat_limit_grams": 20,
"soluble_fiber_target_grams": 12,
"omega3_sessions_per_week": 3
```

- `cholesterol_focus`: boolean; true if heart health was flagged and user confirmed LDL/cholesterol is a specific concern
- `saturated_fat_limit_grams`: integer; default 20 if cholesterol_focus is true, null otherwise
- `soluble_fiber_target_grams`: integer; default 12 if cholesterol_focus is true, null otherwise
- `omega3_sessions_per_week`: integer; target fatty fish servings per week; default 3 if cholesterol_focus is true, null otherwise

This gives downstream agents concrete numeric constraints rather than a vague boolean flag.

---

### Change 5: Training Day Carb Cycling

**Problem:** The agent outputs a single set of daily macro targets. For users doing high-intensity activity on specific days, a flat daily target misses a practical optimization — more carbs on training days, fewer on rest days, protein flat throughout.

**Solution:** If `activity_sessions_per_week >= 2` and `activity_intensity == "high"`, generate and record cycling targets in addition to the daily averages.

#### New JSON Fields

```json
"training_day_calories": 2750,
"training_day_carbs_grams": 330,
"training_day_protein_grams": 195,
"training_day_fat_grams": 75,
"rest_day_calories": 2500,
"rest_day_carbs_grams": 260,
"rest_day_protein_grams": 195,
"rest_day_fat_grams": 70
```

- Protein stays flat across both day types
- Calorie and carb delta between training and rest days should be 200–300 cal / 50–80g carbs
- Fat stays within ~5g across day types
- All fields are `null` if carb cycling does not apply

---

### Change 6: Narrative Report Field

**Problem:** The JSON output is not human-readable. The user cannot act on it directly without a downstream tool.

**Solution:** Add a `"report"` field — a markdown string generated by the agent after all other fields are finalized.

#### New JSON Field

```json
"report": "# Nutrition Plan Summary\n\n## Your Profile\n...\n\n## Calorie Targets\n..."
```

- Type: string (markdown-formatted)
- Generated **after** all fields are finalized — report must use the confirmed numbers, not estimates
- Empty string `""` is not acceptable; this field is always populated

#### Required Report Sections

The report must always include these sections (include conditional sections only when applicable):

| Section | Always / Conditional |
|---|---|
| Profile summary (age, weight, activity, goals) | Always |
| Calorie target with plain-English rationale | Always |
| Macro breakdown with explanation of each | Always |
| Training day vs. rest day targets | If carb cycling fields are populated |
| Cholesterol / heart health guidance | If `cholesterol_focus: true` |
| Key daily rules (5–8 items) | Always |
| Meal prep notes | If `meal_prep_friendly: true` |
| Night snack guidance | If `include_night_snack: true` |
| Reassessment trigger | Always |

#### Agent Instructions to Add

After writing the JSON file, generate the report field content using the finalized numbers. The report is the human-readable version of the machine-readable JSON — written in plain language a non-dietitian can act on. It should read like a reference document the user keeps, not a summary of the interview.

---

### Change 8: Calorie Floor Field

**Problem:** The current schema has no minimum calorie floor. The deficit cap in Change 2 reduces the risk of undereating, but nothing prevents a downstream agent from scheduling rest days too low. For a user at this size and activity level, dropping below ~1,800 cal/day is counterproductive and risks muscle loss, fatigue, and impaired recovery.

**Solution:** Add a `calorie_floor_grams` field derived from bodyweight at finalization time.

#### New JSON Field

```json
"calorie_floor_calories": 1800
```

#### Derivation Rule

- Default: `10 × bodyweight_lbs` (e.g. 240 lbs → 1,800 cal floor)
- If `activity_intensity == "high"`: use `11 × bodyweight_lbs` (e.g. 240 lbs → 2,640 cal floor)
- Cap at 2,000 minimum regardless of bodyweight — no adult should go below 2,000 on a high-intensity training day

Agent must surface this in the confirmation step and include it in the report's Key Rules section.

---

### Change 9: Medication and Supplement Field

**Problem:** The agent collects dietary restrictions and allergies but never asks about medications or supplements. This is a significant omission for any user with a clinical goal (cholesterol management, blood sugar control, anti-inflammatory). Statins interact with grapefruit; metformin depletes B12; blood pressure medication affects electrolyte needs.

**Solution:** Add a light medication/supplement probe when a clinical flag is set (`heart_healthy`, `diabetic_friendly`, `anti_inflammatory`).

#### Additional Interview Question (conditional on clinical flags)

> *"Are you currently taking any medications or supplements related to [cholesterol / blood sugar / inflammation]? I won't give medical advice, but knowing this helps me flag any food interactions worth discussing with your doctor."*

#### New JSON Fields

```json
"medications_notes": "",
"discuss_with_physician": false
```

- `medications_notes`: free text; empty string if none disclosed
- `discuss_with_physician`: set to `true` automatically if any clinical flag is true (`heart_healthy`, `diabetic_friendly`, `anti_inflammatory`) — ensures the report always includes a physician reminder for clinical plans

---

### Change 10: Alcohol Probe

**Problem:** Neither the interview nor the schema captures alcohol intake. Alcohol is a direct contributor to elevated triglycerides, adds significant hidden calories, and meaningfully undermines cholesterol management goals. It is a first-order variable for any user with `heart_healthy: true` or a weight loss goal.

**Solution:** Add a brief, non-judgmental probe to the intake interview.

#### New Interview Question

Trigger when `heart_healthy: true` or when weight loss is a stated goal:

> *"One last thing — do you drink alcohol? If so, roughly how often? I ask because it affects both calorie planning and cholesterol management, not to judge."*

#### New JSON Fields

```json
"alcohol_drinks_per_week": null
```

- Integer or `null` if user declines to answer / doesn't drink
- If value > 7: add a note to the `notes` field flagging elevated alcohol as a cholesterol and calorie risk factor
- If `cholesterol_focus: true` and value > 3: agent should surface this during the confirmation step

---

### Change 11: Fiber Ramp-Up Guidance

**Problem:** Change 4 correctly adds `soluble_fiber_target_grams` (default 12g) for cholesterol-focused plans, and the total fiber goal implied by the report section is 35–40g/day. However, most people eat far less fiber than this. Jumping to 35–40g cold causes significant GI distress — bloating, cramping, and gas — which tanks adherence in the first week.

**Solution:** Add ramp-up guidance to the report and a `fiber_current_estimate_grams` field to capture baseline.

#### New Interview Question (when `cholesterol_focus: true` or fiber guidance will be issued)

> *"How would you describe your current vegetable, bean, and whole grain intake — pretty low, moderate, or already quite high?"*

Map answers to an estimated current fiber intake:
- Low → ~10–15g/day
- Moderate → ~20–25g/day
- High → ~30g+/day

#### New JSON Field

```json
"fiber_current_estimate_grams": 15
```

#### Report Instruction

If `fiber_current_estimate_grams < 25`, the report's cholesterol section must include a ramp-up note:

> *"Fiber increase: Don't jump to the target amount overnight. Add one high-fiber food per week for the first 3–4 weeks, drink at least 2–3 liters of water daily, and let your gut adapt. Doing this too fast causes bloating and gas — slow ramp-up gets you to the same place without the friction."*

---

### Change 12: Liked/Disliked Foods — Deeper Interview Probe

**Problem:** The interview is marked as a strength for food preference capture, but in practice the output can be implausibly sparse (e.g. `liked_foods: ["chicken", "rice"]` for someone with five preferred cuisine categories). A person with Mexican, Asian, Italian, American, and pizza preferences almost certainly has more than two liked foods. The current interview doesn't probe deeply enough.

**Solution:** Add follow-up probes tied to stated cuisine preferences.

#### New Interview Logic

After the user states cuisine preferences, ask one follow-up per cuisine cluster (not per cuisine — combine similar ones):

- *"You mentioned [Mexican / Asian / Italian] — are there specific dishes in those you always enjoy, or proteins you reach for in those cuisines?"*
- *"Any foods you'd be happy eating multiple times a week? And on the flip side, anything you'd rather never see in your meal plan?"*

#### Updated Field Rule

- `liked_foods` and `disliked_foods` should have **at least 3 entries each** before the file is written if the user has stated cuisine preferences
- If the user truly has nothing to add after follow-up probing, that's acceptable — but the agent must ask, not assume

---

### Change 13: Sodium Awareness for Cardiovascular Plans

**Problem:** `low_sodium: false` is the default and is never revisited for users with `heart_healthy: true`. Sodium management is relevant for cardiovascular health — especially for users with hypertension or LDL concerns — and should at minimum be surfaced as a question rather than silently defaulted to false.

**Solution:** Add a conditional probe when `heart_healthy` is flagged.

#### New Interview Question (when `heart_healthy: true`)

> *"Has your doctor mentioned watching sodium intake alongside cholesterol? Some people with heart health goals are on a low-sodium restriction and some aren't — I want to make sure the plan reflects what's right for you."*

- If yes: set `low_sodium: true`
- If no or unsure: leave `low_sodium: false` but add to `notes`: *"Sodium not restricted per user; revisit if BP becomes a concern."*

This ensures the field reflects an actual answer rather than a silent default.

---

### Change 7: Smarter Confirmation Step

**Problem:** The current confirmation surfaces only calories and protein. The user has no visibility into the reasoning behind carb levels, deficit sizing, or any sport-specific decisions before the file is written.

**Solution:** Expand the confirmation to surface all key decisions with their rationale, giving the user a meaningful opportunity to push back.

#### Revised Confirmation Template

> *"Based on everything you've told me, here's what I'm proposing before I write the file:*
>
> - *[X] cal/day — [Y] cal deficit, kept conservative because of your [activity] intensity*
> - *[X]g protein — top of range because [age 40+ / high activity / both]*
> - *[X]g carbs — kept higher than a typical weight loss plan because [sport] is glycolytic*
> - *[If applicable] Saturated fat capped at [X]g/day for cholesterol management*
> - *[If applicable] Carb cycling: [X]g carbs on training days, [X]g on rest days — protein stays flat at [X]g every day*
>
> Does this look right, or would you like to adjust anything before I write the file?"*

The confirmation must surface the **reasoning**, not just the numbers. This is the last error-catching gate before the file is written.

---

## Schema Changes Summary

### New Fields to Add

```json
{
  "activity_type": null,
  "activity_sessions_per_week": null,
  "activity_minutes_per_session": null,
  "activity_intensity": null,
  "wearable_reported_burn": null,
  "glycolytic_sport": false,
  "cholesterol_focus": false,
  "saturated_fat_limit_grams": null,
  "soluble_fiber_target_grams": null,
  "omega3_sessions_per_week": null,
  "training_day_calories": null,
  "training_day_carbs_grams": null,
  "training_day_protein_grams": null,
  "training_day_fat_grams": null,
  "rest_day_calories": null,
  "rest_day_carbs_grams": null,
  "rest_day_protein_grams": null,
  "rest_day_fat_grams": null,
  "report": ""
}
```

### Field Rules to Add

- `activity_intensity`: one of `"light"`, `"moderate"`, `"high"`, or `null`
- `glycolytic_sport`: boolean; true for martial arts, running, cycling, HIIT, team sports
- `cholesterol_focus`: boolean; true only if heart_healthy AND user confirmed cholesterol is a specific clinical concern
- All `training_day_*` and `rest_day_*` fields: integers or `null` — null if carb cycling does not apply
- `report`: markdown string; never empty string; always populated

### Existing Field to Update

- `daily_calories`, `protein_grams`, `carbs_grams`, `fat_grams`: these remain as the **average** daily targets; training/rest day fields are additive, not replacements

---

## Implementation Priority

| Priority | Change | Effort |
|---|---|---|
| P0 | Change 2: Sports nutrition macro logic | Medium |
| P0 | Change 3: Age-aware modifier | Low |
| P1 | Change 1: Activity intelligence branch + fields | Medium |
| P1 | Change 6: Report field | Medium |
| P1 | Change 8: Calorie floor field | Low |
| P2 | Change 5: Training day carb cycling | Low |
| P2 | Change 4: Cholesterol branch deepening | Low |
| P2 | Change 12: Liked/disliked foods — deeper probe | Low |
| P2 | Change 13: Sodium awareness for cardiovascular plans | Low |
| P3 | Change 7: Smarter confirmation step | Low |
| P3 | Change 9: Medication and supplement field | Low |
| P3 | Change 10: Alcohol probe | Low |
| P3 | Change 11: Fiber ramp-up guidance | Low |

---

*Plan authored April 2026. Implement Changes 2 and 3 first — they fix the most consequential errors with the least schema disruption.*
