# Confirm Mastery Resets

## Problem

The Reset mastery control immediately changes a card score to 0, so an
accidental click can undo progress.

## Desired behavior

Ask for native browser confirmation before resetting a card. Cancelling leaves
the score and feedback unchanged; confirming performs the existing reset.

## Scope

- Confirm the practice feedback Reset mastery action before its API request.
- Document the confirmation requirement.

## Constraints

- Do not change the reset API, stored practice history, or scoring rules.
- Do not affect any action other than per-card mastery reset.

## Acceptance criteria

- Clicking Reset mastery opens a browser confirmation dialog.
- Cancelling sends no reset request and preserves the displayed score.
- Confirming resets the displayed score to 0 through the existing API.

## Status

Implemented
