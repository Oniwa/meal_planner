# Phase 3 — Meal Feedback & Rating

> Reference: [Architecture](../reference/meal_planner_architecture.md)
> Depends on: [Phase 1](phase_1_mvp.md) complete

## Goal
Track which meals were actually made and how much the user liked them. Feed this data back into future meal plan generation.

## Schema Changes

Add to `PlannedMeal`:
```python
was_made: bool                    # did you actually cook/eat this meal?
rating: int | None                # 1 = disliked, 2 = average, 3 = liked
rating_notes: str(blank=True)     # optional free-text (e.g. "too salty")
rated_at: datetime | None
```

## Tasks

- [ ] Migration: add `was_made`, `rating`, `rating_notes`, `rated_at` to `PlannedMeal`
- [ ] `POST /meals/rate/` endpoint — update rating + `was_made` flag (HTMX)
- [ ] `week_plan.html` — add "Did you make it?" toggle + 1/2/3 star tap per meal cell (HTMX, updates in place)
- [ ] `meal_planner_agent.py` — inject rating history into plan generation prompt:
  - Rating 1 meals → `disliked_meals` list (exclude from new plan)
  - Rating 3 meals → `liked_meals` list (repeat occasionally, use as style reference)
  - Rating 2 / unrated → neutral
- [ ] Helper query: fetch rated meals for the active `NutritionPlan` and format for prompt injection

## Acceptance Criteria
- Rating a meal persists and updates the cell in-place without page reload
- A newly generated plan avoids rating-1 meals
- A newly generated plan occasionally reuses rating-3 meals or meals of the same style/cuisine
