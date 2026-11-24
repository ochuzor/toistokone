# Prioritize Content-Health Findings

## Problem

The Content health page and import report order every finding alphabetically,
making large audits difficult to act on.

## Desired behavior

Rank coverage gaps by focus-word requests, recent practice, and frequency.
Rank untracked sentences by frequency-list coverage, commonness, and length.
Show the same ordering and a short reason in both the browser and import report.

## Scope

- Read current matching progress rows without writing progress data.
- Extend content-health findings with a priority reason.
- Preserve existing categories, counts, pagination, and health definitions.

## Constraints

- Ignore stale progress rows that do not match current vocabulary.
- Use the form's frequency rank when available, otherwise its base word's rank.

## Acceptance criteria

- Focus words appear before other coverage gaps.
- Recent practice and frequency provide deterministic fallback ordering.
- Untracked sentences prefer fewer unranked words, common vocabulary, and shorter length.
- Browser and import report have matching priority order and reasons.
- The import pipeline never modifies progress data.

## Status

Implemented
