# Phase 2 — Polish

> Reference: [Architecture](../reference/meal_planner_architecture.md)
> Depends on: [Phase 1](phase_1_mvp.md) complete

## Goal
Round out the core app with pantry tracking, historical plans, richer nutrition feedback, and a printable shopping list.

## Tasks

- [ ] `apps/pantry/models.py` — `PantryItem` model + migration
- [ ] `apps/pantry/views.py` + `urls.py` — pantry list view, add item
- [ ] `pantry/pantry.html` template
- [ ] Add pantry nav link to `base.html`
- [ ] Pantry-aware meal plan prompt: cross-reference pantry items against shopping list to exclude items already on hand
- [ ] Historical week plans: `GET /meals/<week_start>/` — browse past plans
- [ ] Nutrition summary bar on `week_plan.html`: daily totals vs targets, colour-coded (green ±10%, amber ±15%)
- [ ] Export shopping list: plain-text view + print-friendly CSS on `shopping/list.html`

## Acceptance Criteria
- Pantry items are saved and retrievable
- Generating a new plan excludes pantry-held ingredients from the shopping list
- Past week plans are browsable
- Nutrition summary bar renders correctly against a known plan
- Shopping list prints cleanly (no nav, no buttons)
