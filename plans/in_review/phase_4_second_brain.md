# Phase 4 — Second Brain Integration

> Reference: [Architecture](../reference/meal_planner_architecture.md)
> Depends on: [Phase 3](phase_3_meal_feedback.md) complete

## Goal
Augment structured DB data with free-form notes and patterns captured in the second brain MCP. Structured data (ratings, nutrition, ingredients) stays in Django. Second brain handles cross-domain free-text context.

## Integration Points

| Where | Action |
|---|---|
| Dietitian agent | Query second brain for health/diet context before starting the intake interview |
| Meal plan generation | Pull recent meal reflections and liked/disliked patterns into the Claude prompt alongside structured DB ratings |
| Weekly reflection | Capture a short free-text review each week as a second brain thought |
| Semantic search | Surface cuisine/style patterns into future plan prompts |

## Tasks

- [ ] `dietitian_agent.md` — add second brain query step before intake interview begins
- [ ] `ai/meal_planner_agent.py` — before building the prompt, query second brain for recent meal reflections; inject as an additional context block
- [ ] `POST /meals/reflect/` — weekly reflection endpoint: accepts free-text, saves to second brain via MCP
- [ ] `week_plan.html` — add "Weekly reflection" text input + submit (shown at end of week or on archive)
- [ ] Semantic search helper: query second brain for "cuisines consistently rated 3" and inject into prompt
- [ ] Document the thought schema used for meal reflections (tags, body format)

## Acceptance Criteria
- Generating a plan after saving a reflection results in the reflection context appearing in the prompt (verify via logging)
- Dietitian agent surfaces relevant second brain notes before asking intake questions
- Weekly reflection is saved and retrievable via second brain semantic search
