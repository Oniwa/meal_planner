# Supplement Awareness Plan

**Source:** Dietitian agent improvement grilling session  
**Date:** April 2026  
**Agent file:** `dietitian_agent.md`  
**Depends on:** Dietitian improvement plan P3 complete (report field must exist)

---

## Problem

The agent makes no mention of supplements, even in contexts where common supplements are directly relevant to the user's clinical or athletic goals. A vegan user is never flagged about B12. A high-intensity martial artist is never pointed toward creatine or magnesium. A cholesterol-focused user already gets omega-3 food targets but no awareness of supplemental options.

---

## Scope

Report-only. No new interview questions. No new schema fields. Supplement notes are appended to the existing `report` field conditionally based on flags already collected during the interview.

This is informational guidance, not clinical advice. Every mention must include a physician/pharmacist disclaimer. The agent does not recommend dosages.

---

## Report Section Rules

Add a **Supplement Awareness** section to the report when any of the following conditions apply:

| Condition | Supplement to mention |
|---|---|
| `is_vegan: true` or `is_vegetarian: true` | B12 — dietary sources limited; supplementation common and well-supported |
| `glycolytic_sport: true` AND `activity_intensity: "high"` | Creatine monohydrate (performance/recovery), magnesium (muscle function, sleep quality) |
| `cholesterol_focus: true` | Plant sterols — omega-3 already captured via `omega3_sessions_per_week` food targets |
| `anti_inflammatory: true` | Omega-3 fish oil, curcumin/turmeric |

If no conditions apply, omit the section entirely — do not include a generic supplement paragraph.

---

## Agent Instructions to Add

After finalizing the `report` field content, check the conditions above. If any apply, append a Supplement Awareness section using this structure for each relevant supplement:

1. What it is and why it's relevant to this user's specific situation (1–2 sentences)
2. Close with: *"This is worth discussing with your doctor or pharmacist before starting."*

Example (for a high-intensity martial artist):

> **Creatine monohydrate** — well-studied for improving performance in high-intensity, short-burst sports like martial arts. Supports strength and recovery between sessions. This is worth discussing with your doctor or pharmacist before starting.
>
> **Magnesium** — commonly depleted in athletes training at high intensity. Supports muscle recovery and sleep quality. This is worth discussing with your doctor or pharmacist before starting.

---

## Implementation Notes

- No schema changes required
- No new interview questions
- Implement after dietitian improvement plan P3 is complete (the `report` field must exist)
- If `medications_notes` is non-empty, the disclaimer language should be slightly stronger: *"Given the medications you mentioned, check with your doctor or pharmacist before adding any supplement."*

---

*Plan authored April 2026. Implement post-P3 once the dietitian agent core is stable.*
