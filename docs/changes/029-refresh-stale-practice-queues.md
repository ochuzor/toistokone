# Refresh Stale Practice Queues After Content Imports

## Problem

The browser restores a locally saved queue without knowing whether
`content.sqlite` was rebuilt. A queue can therefore contain cards or answer
options that no longer match the current imported content.

## Desired behavior

Before restoring a practice queue, compare its saved content revision with the
current content revision. If they differ, discard the queue, load a fresh
batch, and briefly tell the learner why. Existing schema-1 queues are treated
as stale once.

## Scope

- Store a new opaque revision in each normal pipeline-built content database.
- Expose the revision through a read-only backend endpoint.
- Persist it with a schema-2 browser queue and validate it before rendering.
- Refresh stale or legacy queues without changing progress data.

## Constraints

- Dry runs must not change the live content revision.
- The import pipeline must never write `progress.sqlite`.
- Keep queue ownership in the frontend; do not add backend queue persistence.

## Acceptance criteria

- Each successful normal import produces a new content revision.
- A matching saved queue resumes unchanged.
- A mismatched or schema-1 queue is never displayed and is replaced with a
  fresh batch with a short notice.
- A content import does not alter mastery or practice history.

## Status

Implemented
