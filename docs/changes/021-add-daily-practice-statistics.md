# Add Daily Practice Statistics

## Problem

The application records every answer but only shows all-time mastery totals.
Learners cannot see their recent effort, accuracy, or practice consistency.

## Desired behavior

Show a Home-page summary of today's activity, a 14-day attempts trend, and a
local-calendar practice streak.

## Scope

- Group attempt history by the browser's IANA timezone.
- Return daily attempts, accuracy, unique cards, score increases, and newly
  mastered cards with the existing statistics response.
- Show today's activity, streak, and an accessible 14-day attempts chart on
  Home.

## Constraints

- Reuse `practice_attempts`; do not change scoring, queue selection, or
  content imports.
- A streak carries through the current day when the learner practised yesterday.
- Reset actions remain excluded because they are not attempt-history events.

## Acceptance criteria

- The API returns 14 local dates including zero-activity days.
- UTC-boundary attempts appear on the correct browser-local day.
- Home renders activity, trend, and streak without a chart dependency.

## Status

Implemented
