# Add POS-Gated Plural-Genitive Cards

## Problem

Common forms such as `talo → talojen` are absent because ordinary plural
genitives are not currently generated from Kaikki.

## Desired behavior

Generate `Genetiivi, monikko (minkä?)` cards for nouns, adjectives, pronouns,
determiners, and numerals. Keep existing plural-pronoun profiles without
creating duplicate cards.

## Scope

- Add a POS-gated `nominal:genitive-plural` slot.
- Rebuild the Kaikki index through its versioned signature.
- Update tests and relevant documentation.

## Constraints

- Exclude proper names, verbs, participles, unknown POS, and all other parts
  of speech.
- Do not alter scoring, queue selection, or existing progress data.

## Acceptance criteria

- Eligible words generate plural-genitive cards with the correct label.
- Ineligible POS generate none.
- Existing plural-pronoun genitives remain singular cards in their established
  plural profile, without duplicates.

## Status

Implemented
