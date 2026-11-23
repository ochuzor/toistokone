# Add Personal-Pronoun Accusative Cards

## Problem

The distinct accusative forms of Finnish personal pronouns, such as `hänet`,
are important but the importer excludes all accusative forms to avoid adding a
broad and low-priority nominal profile.

## Desired behavior

Generate one accusative card for each personal pronoun: `minut`, `sinut`,
`hänet`, `meidät`, `teidät`, and `heidät`. Do not generate accusative cards
for ordinary nouns, demonstratives, or other pronouns.

## Scope

- Add accusative slots only for `minä`, `sinä`, `hän`, `me`, `te`, and `he`.
- Use the existing singular and plural pronoun profiles and the label
  `Akkusatiivi`.
- Rebuild the reusable Kaikki index and update documentation and tests.

## Constraints

- Keep all non-personal accusative forms excluded.
- Preserve existing pronoun ownership and singular/plural separation.
- Do not add plural partitive or other new profiles.
- Never alter progress data during content import.

## Acceptance criteria

- Each supported personal pronoun has exactly one accusative card.
- `hän` produces `nominal:accusative → hänet`.
- Ordinary nouns and `se`/`ne` do not receive accusative cards.
- The cards unlock after vocabulary mastery and use normal same-profile answer
  choices.

## Status

Implemented
