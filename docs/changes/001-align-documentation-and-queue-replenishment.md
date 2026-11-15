# Align documentation and queue replenishment

**Status:** Completed

## Problem

`AGENTS.md` names three non-existent `*_draft.md` project documents. The
repository instead contains the corresponding files without the `_draft`
suffix. The backlog also previously described queue replenishment
inconsistently with the PRD.

## Root cause

The project moved from its original implementation phase to maintenance, but
the documentation references were not updated to match the filenames now in
the repository. The backlog wording was written separately from the PRD and
did not preserve the inclusive threshold.

## Desired behavior

All project instructions refer to existing documentation files. Queue
replenishment remains defined and implemented as requesting/appending a batch
when **three or fewer** unanswered cards remain (`<= 3`).

## Proposed fix and scope

- Update the three document references in `AGENTS.md` to their existing,
  non-draft filenames.
- Update stale companion-document references in the technical specification
  and implementation plan.
- Ensure the backlog describes the inclusive `<= 3` threshold if it contains
  a queue-replenishment item; do not add a duplicate because the current
  backlog already tracks documentation mismatches.
- Preserve the existing `Practice.tsx` refill guard, which already returns
  only when `queue.length > 3` and therefore replenishes at `<= 3`.
- Verify the existing frontend queue threshold through the production build
  and browser automation. The project has no frontend unit-test framework, so
  do not add dependencies solely for this documentation-only change.

## Affected files

- `AGENTS.md`
- `docs/toistokone_technical_spec.md`
- `docs/toistokone_implementation_plan.md`
- `docs/BACKLOG.md` (only if threshold wording is present)
- `frontend/src/pages/Practice.tsx` (verification only unless inspection
  finds a defect)
- No application-code changes are expected

## Constraints and risks

- Do not change the mastery or batch-selection algorithms.
- Do not alter queue ownership or persistence behavior.
- Avoid changing unrelated wording or backlog priorities.

## Acceptance criteria

- `AGENTS.md`, the technical specification, and the implementation plan
  reference only existing companion documents.
- The PRD, implementation plan, backlog (where applicable), and implementation
  all specify or implement replenishment at three or fewer remaining cards.
- The refill guard is verified to trigger at queue lengths 1, 2, and 3, and
  not at 4 or more.
- Relevant automated tests and a Playwright browser check pass after approval.
