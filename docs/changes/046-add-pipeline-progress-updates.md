# Add Pipeline Progress Updates

## Problem

Long content imports can appear to hang because the command prints only its
final report.

## Desired behavior

The command-line pipeline reports its active phase and gives periodic progress
during long Kaikki scans and sentence-file reads.

## Scope

- Send flushed progress messages to standard error from the CLI.
- End with a concise pointer to the full report file instead of printing it.
- Cover normal, dry-run, rebuilt-index, and reused-index paths.

## Constraints

- Programmatic imports remain silent unless supplied a progress callback.
- Do not change import results or progress-database behavior.

## Acceptance criteria

- A long import visibly advances through its phases.
- Kaikki scans show periodic approximate percentages.
- The full report remains available in `data/import-report.md`.

## Status

Implemented
