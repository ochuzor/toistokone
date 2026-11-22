# Prioritize New Quiz Cards by Contextual Relevance

## Problem

New vocabulary cards are selected only by frequency rank. The recommendation
engine also identifies words that occur alongside more of the learner's
tracked vocabulary, but quiz selection does not use that signal.

## Desired behavior

For never-practised vocabulary cards, use sentence-context relevance within
broad frequency bands. Keep the existing quiz mix and prefer words supported
by more distinct tracked vocabulary families and sentences.

## Scope

- Rank new vocabulary in bands: 1–100, 101–500, 501–2,000, 2,001+, then
  unranked words.
- Within a band, prefer greater related-vocabulary breadth, then more
  supporting sentences, then exact frequency rank.
- Use exact single-token base words and generated forms; exclude the card's
  own family from its contextual breadth.

## Constraints

- Do not alter score-0 cards already attempted, word-form selection, quotas,
  API responses, or progress data.

## Acceptance criteria

- Context changes selection among new cards in the same frequency band.
- A card in a higher frequency band remains preferred.
- Self-references do not count as contextual support.
- Existing batch composition and five-new-card maximum are unchanged.

## Status

Implemented
