# Prioritize New Cards by Reinforcement Potential

## Problem

New-card ranking counts supporting sentences but does not distinguish sentences
that can soon reinforce a word using mastered surrounding vocabulary.

## Desired behavior

Within a frequency band and contextual breadth, prefer vocabulary with higher
quality sentence support: sentences containing fewer other unmastered tracked
families are more valuable.

## Scope

- Score every candidate supporting sentence using the existing 16/8/4/1
  mastery-aware weighting, excluding the candidate's own family.
- Sum sentence quality per candidate.
- Rank this total after contextual breadth and before raw sentence count.

## Constraints

- Preserve frequency bands, diversity, batch quotas, APIs, and progress data.
- Use base vocabulary mastery score 3 as the definition of mastered.

## Acceptance criteria

- Supporting sentences with mastered surrounding vocabulary score higher.
- Reinforcement quality outranks raw sentence count at equal frequency band and
  contextual breadth.
- A candidate's own family does not reduce its reinforcement score.

## Status

Implemented
