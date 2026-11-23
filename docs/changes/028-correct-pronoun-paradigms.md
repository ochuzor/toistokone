# Correct Singular and Plural Pronoun Paradigms

## Problem

Kaikki pronoun entries can contain both singular and plural forms. The import
index assigned the combined paradigm to each requested lemma, causing plural
pronouns such as `ne` to receive singular forms such as `se` and `sitä`.

## Desired behavior

Keep nominative cards, but assign forms only to the pronoun lemma with the
matching nominative number. Singular and plural pronouns receive separate
grammar profiles.

## Scope

- Add a plural nominal profile for the supported case slots.
- Identify requested pronouns from tagged nominative forms and separate their
  singular and plural candidates during indexing.
- Render plural nominal cards with the existing nominal-card presentation.

## Constraints

- Preserve ordinary-noun behavior, including their nominative-plural cards.
- Rebuild content only; never alter progress data.

## Acceptance criteria

- `se` has singular forms such as `sen` and `sitä`, but no `ne` forms.
- `ne` has plural forms such as `niiden` and `niitä`, but no `se` forms.
- Plural pronoun cards have plural labels and options only from their profile.

## Status

Implemented
