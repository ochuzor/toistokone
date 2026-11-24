# Add Plural-Partitive Form Cards

## Problem

The form profiles omit useful plural-partitive forms such as `kana → kanoja`.
Adding every Kaikki plural-partitive form would also introduce low-value proper
name and verb-participle material.

## Desired behavior

Generate plural-partitive cards for nouns, adjectives, pronouns/determiners,
and numerals. Exclude proper names, verb/participle entries, unknown POS, and
all other word classes.

## Scope

- Add `nominal:partitive-plural` with the label `Partitiivi, monikko (mitä?)`.
- Gate it by the Kaikki entry POS.
- Preserve existing plural-pronoun profiles, which already have plural
  partitive cards.
- Rebuild the Kaikki index and update documentation and tests.

## Constraints

- Do not generate plural partitive for proper names or verb/participle entries.
- Preserve existing scoring, queue selection, and progress data.
- Do not add other plural cases.

## Acceptance criteria

- Noun, adjective, and numeral entries generate the expected plural-partitive
  cards.
- Proper-name and verb entries with tagged plural partitives generate none.
- Existing plural-pronoun plural-partitive cards remain available without
  duplicate cards.

## Status

Implemented
