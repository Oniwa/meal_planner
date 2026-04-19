# Implementation Order

> Last updated: April 2026 (post grilling session on meal_planner_agent_improvements.md)
> See `plans/in_review/` for the full plan files.
> See memory files for architectural decisions and future enhancements.

---

## Step 1 — Dietitian Agent Update
**Plan:** `plans/in_review/dietitian_agent_variety_training_update.md`
**Agent:** `.claude/agents/dietitian_agent.md` (v1.0 → v2.0)
**Blocked by:** Nothing — do this first

### What changes
- Replace flat `meal_variety: "medium"` with nested per-slot object (`breakfast`, `lunch`, `dinner`, `afternoon_snack`, `night_snack`)
- Add `training_days: []` field
- Update interview flow: global variety question → per-slot exception probing
- Add snack timing and variety interview block
- Add training day schedule question (when carb cycling is active)

### Done when
- [ ] `dietitian_agent.md` frontmatter shows `version: 2.0`
- [ ] Fresh `nutrition_plans/john_<date>.json` generated with nested `meal_variety` object and `training_days` array
- [ ] Old `john_2026-04-04.json` not used for any further testing

---

## Step 2 — Verification Script
**Plan:** `plans/in_review/verify_meal_plan_script.md`
**Artifact:** `scripts/verify_meal_plan.py` (new, v1.0)
**Blocked by:** Step 1 (schema must be final before writing the script)

### What to build
- `mkdir scripts && touch scripts/__init__.py`
- Script takes two args: meal plan JSON path + nutrition plan JSON path
- Runs full deterministic checklist (macros, arithmetic, breakfast floor, variety rules, cook time, allergens, fatty fish, saturated fat, training day targets, batch cook coverage)
- Outputs structured per-day pass/fail report with explicit deltas
- Core logic in importable functions (thin CLI wrapper) for Phase 1 Django reuse

### Done when
- [ ] `scripts/verify_meal_plan.py` exists
- [ ] Script runs against a sample meal plan and produces readable output
- [ ] Exit code 0 on pass, 1 on fail
- [ ] Null/missing-key handling confirmed for fields added by later changes (saturated_fat_grams, soluble_fiber_grams)

---

## Step 3 — Meal Planner Agent Improvements
**Plan:** `plans/in_review/meal_planner_agent_improvements_v2.md`
**Agent:** `.claude/agents/meal_planner_agent.md` (v1.0 → v2.0)
**Blocked by:** Steps 1 and 2 both complete; fresh John nutrition plan available

### Priority order within this step

**P0 — Do these first (core failures):**
- Verification loop (calls verify script, per-day correction, 3 attempts, best-attempt fallback)
- Per-slot meal_variety consumption (consumes new dietitian schema)
- Breakfast protein floor (≥25% of daily target, ≥3 anchors for low variety)
- Arithmetic summary integrity (now handled by verify script)

**P1 — Do next:**
- Consecutive identical meal prevention (suppressed when variety = "none"; snacks always exempt)

**P2 — Do after P1:**
- Batch cook summary block (agent-generated, consistent units, verify script checks coverage)
- Training day macro cycling (confirm days at startup, consume training_day_calories / rest_day_calories)

**P3 — Do last:**
- Cholesterol-aware numeric compliance (consume saturated_fat_limit_grams, soluble_fiber_target_grams, omega3_sessions_per_week)

### Done when
- [ ] `meal_planner_agent.md` frontmatter shows `version: 2.0`
- [ ] Verify script called at least once before file write
- [ ] Generated plan passes all 13 checklist items on first try (or flags correctly)
- [ ] `compliance_flags: []` present in output JSON
- [ ] `batch_cook_summary` present and terminal shows SUNDAY BATCH COOK LIST
- [ ] Training day confirmation shown at startup when carb cycling is active

---

## Future (not started — needs grill-me before implementing)

| Enhancement | Notes |
|---|---|
| Week-to-week overrides | Per-slot variety + training day overrides at generation time, no dietitian re-run |
| Fitbit MCP server | Historical workout days → `training_days`; real burn data → dietitian |
| Opus escalation (Phase 1 Django) | Switch to Opus on 3rd correction attempt in `ai/meal_planner_agent.py` |
| Best-attempt grading | Track and grade all correction attempts; surface in `compliance_flags` |
| Version check script | `scripts/check_versions.py` validates plan/agent version alignment |
| SQL plan storage | Replace `plans/` markdown files with DB (Phase 1 Django) |
| Django Phase 1 | Full web app — see `plans/in_review/phase_1_mvp.md` |

---

## Quick reference — version chain

```
dietitian_agent    v1.0  →  v2.0  (Step 1)
verify_meal_plan   —     →  v1.0  (Step 2)
meal_planner_agent v1.0  →  v2.0  (Step 3)
```
