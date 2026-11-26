# Add Markdown Learning Paths

## Problem

Learning sets provide focused content, but do not show how several sets fit into
an ordered course or curriculum.

## Desired behavior

Markdown learning paths order existing learning sets and show live progress.
The next set becomes available after the prior set reaches 70% base-card and
40% form-card progress at score 2 or above, without changing the active set.

## Scope

- Import and validate path files using stable learning-set IDs.
- Add path API endpoints and list/detail pages.
- Compute path state from current progress without persisting path state.

## Acceptance criteria

- Invalid path IDs, missing set IDs, and duplicates within a path fail import.
- A learning set may belong to multiple paths.
- Path steps correctly become completed, available, or locked at the agreed thresholds.
- Paths never automatically select an active learning set.

## Status

Implemented
