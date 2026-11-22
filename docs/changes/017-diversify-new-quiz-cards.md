# Diversify New Vocabulary Within Quiz Batches

## Problem

Contextual ranking can select several new vocabulary cards supported by the
same set of already tracked words, making a batch less varied.

## Desired behavior

When contextual relevance is otherwise equal within a frequency band, prefer
new vocabulary cards connected to different tracked-word neighborhoods.

## Scope

- Keep each candidate's related tracked families alongside contextual support.
- Select new vocabulary cards greedily and prefer lower overlap with
  neighborhoods already represented in that batch.
- Apply diversity after frequency band, contextual breadth, and supporting
  sentence count, but before exact frequency rank.

## Constraints

- Diversity is a soft tie-break, never an exclusion.
- Preserve existing quotas, the five-new-card limit, APIs, progress data, and
  all non-new-card behavior.

## Acceptance criteria

- Same-relevance candidates prefer a different neighborhood when available.
- Stronger contextual relevance and higher frequency bands remain preferred.
- Candidates still appear when all available neighborhoods overlap.

## Status

Implemented
