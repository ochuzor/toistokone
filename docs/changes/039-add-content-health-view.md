# Add Content Health View

## Problem

Content diagnostics are split across import output and the application, and the
current report omits the promised audit of sentence coverage.

## Desired behavior

Generate one full content-health audit in the import report and expose the same
current-content findings through a read-only browser page.

## Scope

- Audit missing generated grammar profiles, base words without sentences, form
  cards with fewer than two supporting sentences, and untracked sentences.
- Add a paginated API and category-based browser view.
- Preserve existing import diagnostics and all learning behavior.

## Constraints

- Use exact case-insensitive matching.
- Do not record source-file provenance or modify progress data.

## Acceptance criteria

- Import reports contain counts and complete grouped findings.
- The browser page shows summary counts, category results, and batches of 50.
- Findings use current content only and remain read-only.

## Status

Implemented
