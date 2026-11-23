# Exclude Known Normalized Recommendations and Prioritize New Forms by Frequency

## Problem

Kaikki normalization can reintroduce known lemmas as recommendations through an
unknown surface form. Score-0 word forms are also selected randomly, so common
forms can be delayed behind less common forms.

## Desired behavior

Known normalized lemmas are never recommended. Within the existing selected
score-0 word-form slots, common eligible forms are introduced first.

## Scope

- Discard a recommendation after normalization when its lemma is a known
  dictionary base word.
- Load frequency ranks for generated form surfaces.
- Rank unpractised selected form slots globally by surface frequency.

## Constraints

- Preserve vocabulary selection, diversity, learning chains, score groups, and
  the selected vocabulary/form mix.
- Keep forms absent from the frequency list after ranked forms.

## Acceptance criteria

- A known lemma such as `olla` is not recommended through `ole` or `oli`.
- Common eligible forms precede less common and unranked forms.
- The score-0 vocabulary/form slot mix is unchanged.

## Status

Implemented
