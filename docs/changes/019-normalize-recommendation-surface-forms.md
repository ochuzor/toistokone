# Normalize Recommendation Surface Forms to Lemmas

## Problem

Recommendations use exact sentence tokens, so inflected variants can appear as
separate suggestions instead of the base form suitable for `dictionary.txt`.

## Desired behavior

Use Kaikki to merge unambiguous recommended surfaces under one lemma and show
the encountered forms as supporting evidence. Keep ambiguous or unresolved
surfaces unchanged.

## Scope

- Build an ignored reverse Kaikki index for the 100 highest-frequency current
  contextual candidates, covering the displayed recommendations without a
  full morphology scan for every possible token.
- Store unambiguous surface-to-lemma mappings in the generated content
  database.
- Merge normalized recommendation support and expose observed forms in the API
  and page.

## Constraints

- Do not create a full reverse morphology database.
- Do not modify progress data, quiz selection, or ambiguous suggestions. A
  standalone Kaikki headword is treated as a competing lemma.

## Acceptance criteria

- Unambiguous forms normalize and merge under their lemma.
- Ambiguous forms stay unchanged.
- The page shows observed forms for normalized results.
- Imports rebuild stale reverse indexes and preserve progress data.

## Status

Implemented
