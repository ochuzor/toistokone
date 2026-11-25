# Preflight Pipeline Validation

## Problem

The pipeline discovered fatal learning-set, Kaikki-source, and frequency-file
errors only after potentially expensive Kaikki indexing work had begun.

## Desired behavior

Validate all existing fatal input conditions before importing generated forms or
building morphology/recommendation indexes, then write the report and stop.

## Scope

- Run dictionary, learning-set, Kaikki-source/index, and frequency validation
  as a preflight phase.
- Return immediately on fatal preflight errors before any index work.
- Preserve current non-fatal diagnostics for malformed dictionary and sentence
  lines.

## Acceptance criteria

- Invalid frequency input leaves existing databases unchanged and does not call
  Kaikki or recommendation index builders.
- The import report retains the relevant validation errors.

## Status

Implemented
