# Phase 5 — Multi-User

> Reference: [Architecture](../reference/meal_planner_architecture.md)
> Depends on: [Phase 1](phase_1_mvp.md) complete

## Goal
Extend the single-user app to support multiple independent users. Designed to be a mechanical migration — no structural changes to recipes, ingredients, or shopping logic.

## Migration Steps

1. Enable `django.contrib.auth` (already included in Django, zero extra packages)
2. Add `user = FK(User, on_delete=CASCADE)` to `NutritionPlan` and `MealPlan`
3. Create migrations for the FK additions
4. Add `login` / `logout` views + a minimal login template
5. Add `@login_required` to all views
6. Filter all querysets by `request.user`
7. Update `dietitian_agent.md` instructions: each user runs their own CLI session and imports their own JSON

## Tasks

- [ ] Migration: add `user` FK to `NutritionPlan`
- [ ] Migration: add `user` FK to `MealPlan`
- [ ] `config/urls.py` — add `auth` URLs (`login`, `logout`)
- [ ] `templates/registration/login.html` — minimal login form
- [ ] Decorate all views with `@login_required`
- [ ] Filter `NutritionPlan.objects` and `MealPlan.objects` by `request.user` everywhere
- [ ] Update root redirect (`GET /`) to handle unauthenticated users → login page
- [ ] Test: two users each import separate nutrition plans and see only their own data

## Acceptance Criteria
- Unauthenticated requests redirect to login
- User A cannot see User B's plans, meals, or shopping lists
- Each user can independently run the dietitian CLI and import their own JSON
