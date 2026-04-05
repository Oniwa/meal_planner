# MCP Integration Research

**Date:** April 2026  
**Purpose:** Track MCP servers relevant to the meal planner project — fitness tracking, nutrition logging, and health data ingestion.

---

## Fitbit MCP

**Repo:** [NitayRabi/fitbit-mcp](https://github.com/NitayRabi/fitbit-mcp)  
**Status:** Community-built, not officially endorsed by Fitbit  
**Also listed at:** [PulseMCP](https://www.pulsemcp.com/servers/thedigitalninja-fitbit), [Glama](https://glama.ai/mcp/servers/@NitayRabi/fitbit-mcp)

### What it supports

- Activity data, steps, calories burned
- Sleep logs
- Heart rate
- Body measurements
- Food and water logs
- Badges and device info

### Authentication

- OAuth 2.0
- Manual token acquisition via Fitbit Developer Portal
- Set `FITBIT_ACCESS_TOKEN` environment variable
- **No automatic token refresh** — tokens must be manually rotated

### Caveats

- No official Fitbit backing — subject to API changes or deprecation
- Manual auth is friction for end users; not suitable for multi-user deployment without wrapping in an auth flow

### Relevance to this project

Fitbit/Pixel Watch is already in the picture (mentioned in John's nutrition plan, including the known calorie overestimation bug). This MCP could allow agents to pull actual workout calorie burn and step data to inform TDEE calculations and training-day vs. rest-day meal planning rather than relying on self-reported estimates.

---

## MyFitnessPal MCP

**Primary repo:** [ai-mcp-garage/mcp-myfitnesspal](https://github.com/ai-mcp-garage/mcp-myfitnesspal)  
**Alternatives:** [AdamWalt/myfitnesspal-mcp-python](https://github.com/AdamWalt/myfitnesspal-mcp-python), [jevy/myfitnesspal-mcp](https://github.com/jevy/myfitnesspal-mcp)  
**Status:** Community-built, relies on scraping (no official MFP API)

### What it supports

- Daily nutrition summaries
- Meal-by-meal breakdowns
- Macro and micronutrient analysis
- Water intake monitoring
- Body measurements
- Exercise logs
- Nutrition goals
- Date range trend analysis

### Authentication

- Browser session cookies (30-day cache)
- Runs locally via stdio transport — data stays between local machine and MFP servers

### Requirements

- Python 3.12+
- `uv` package manager

### Caveats

- Scraping-based — fragile; can break if MFP changes its frontend
- No official API means no stability guarantees
- Cookie auth is manual; multi-user scenarios require per-user cookie management

### Relevance to this project

MFP is explicitly mentioned in John's nutrition plan (the 2,320 cal/day suggestion). This MCP could allow the meal planner agent to pull John's actual logged food data — real intake vs. plan targets — enabling adaptive meal planning based on adherence rather than assumptions. High-value integration if stable.

---

## StarFit

No MCP exists. StarFit does not appear to have a public API. Not actionable without reverse engineering or direct vendor contact.

---

## Agent Routing

The two MCPs map cleanly to different agents:

| MCP | Primary agent | Data provided |
|---|---|---|
| Fitbit | Dietitian | Activity calorie burn, heart rate zones, sleep quality, steps |
| MyFitnessPal | Meal planner | Actual food logged, macros hit, fiber/sat fat intake, meal timing |

MFP also feeds the **dietitian at reassessment time** — 3–4 week intake trends replace the need for a manual re-interview on routine check-ins.

### Additional Fitbit benefits

- **Sleep → dietitian.** Sleep quality affects LDL/HDL and cortisol (muscle catabolism). Poor sleep weeks could warrant a protein bump or deficit reduction. Currently untracked.
- **Heart rate zones → carb calibration.** Zone 2 vs. zone 4 during karate determines actual glycolytic demand. Training-day carb targets could flex by real session intensity rather than a static "high intensity" assumption.
- **Overestimation caveat.** John's plan already documents that Pixel Watch overstates calorie burn by up to 50%. Pulling Fitbit data via MCP doesn't fix this — the dietitian agent must still apply a correction factor. Automation here creates false precision if the correction isn't built in.

### Additional MFP benefits

- **Fiber and saturated fat actuals.** The cholesterol plan sets targets (12g soluble fiber, 20g sat fat cap) but nothing currently verifies adherence. MFP tracks both — the meal planner can prioritize high-fiber meals or flag sat fat creep based on real data.
- **Meal timing.** MFP logs *when* John eats, not just *what*. Pre/post-karate timing is currently unaddressed. Timing data lets the planner identify if he's training fasted or eating too close to sessions.

---

## Feedback Loop Architecture

The most significant benefit of both MCPs together is not any individual data point — it's closing the loop.

**Current system (open-loop):**
```
Dietitian interview → nutrition plan JSON → meal planner → meal plan
                                                                ↓
                                                           (nothing comes back)
```

**With MCPs (closed-loop):**
```
Dietitian interview → nutrition plan JSON → meal planner → meal plan
        ↑                      ↑                  ↑
   Fitbit: activity        MFP: 3-4 week      MFP: actual intake,
   sleep, heart rate       intake trends      fiber, sat fat, timing
```

This changes the system from "generate a plan once" to "maintain a plan over time." Specific adaptive behaviors this enables:

| Trigger (from MCP data) | Adaptive response |
|---|---|
| Protein target hit <80% for 2+ weeks | Meal planner prioritizes higher-protein meals; surfaces easier protein sources |
| Weight not moving after 4 weeks | Dietitian reduces calories by 100–150 (plan already specifies this trigger) |
| Sat fat consistently over 20g/day | Meal planner flags problem meals; swaps in lower sat fat alternatives |
| Sleep averaging <6 hrs for a week | Dietitian notes increased muscle catabolism risk; bumps protein |
| Karate session heart rate in zone 2 only | Dietitian reduces training-day carbs slightly; notes lower glycolytic demand |
| Fiber intake <50% of target | Meal planner adds high-fiber foods to next week's plan |

The reassessment trigger in the current plan ("reassess after 3–4 weeks") can be automated entirely with this data — no manual re-interview needed for routine check-ins. Manual interviews are reserved for goal changes or significant life changes.

---

## Integration Notes

Both MCPs are single-user tools in their current form. For the multi-user phase (Phase 5), per-user credential management would need to be solved before either could be used at scale. For the current single-user POC, both are viable to experiment with.
