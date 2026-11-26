# Show the Next Learning-Path Step on Home

## Problem

Learning paths are available on their own page, but Home does not indicate the
next set a learner should focus on.

## Desired behavior

Home shows one compact card per path with its next available set and live
progress toward the 70% base-card and 40% form-card thresholds.

## Scope

- Extend path summaries with an optional next available step.
- Show a link to that set on Home, or a path-complete link when applicable.
- Do not change activation or path progression behavior.

## Acceptance criteria

- Home hides the section when no paths are imported.
- Every imported path shows its next available set or completed state.
- Progress reflects current score-2+ card counts and links to the correct page.

## Status

Implemented
