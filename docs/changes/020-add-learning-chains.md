# Add Direct-Context Learning Chains

## Problem

Vocabulary is currently recommended and introduced as individual words, even
when unknown words occur together in the same useful imported sentences.

## Desired behavior

Show directly connected recommendation pairs and introduce one suitable
connected score-0 vocabulary card per batch, without replacing the existing
frequency, contextual relevance, reinforcement, or diversity priorities.

## Scope

- Treat candidate lemmas as connected only when they co-occur in an imported
  Finnish sentence.
- Show visible related candidates as "Learn alongside" suggestions and promote
  up to three companions into the 20-item recommendation list.
- Select at most one directly connected, same-frequency-band score-0
  vocabulary companion per batch.

## Constraints

- Do not infer semantic topics from broad shared vocabulary context.
- Preserve selection for score-1--3 cards, word-form cards, batch quotas,
  progress data, and existing ranking priorities.

## Acceptance criteria

- Recommendations expose only sentence-evidenced visible companions.
- Up to three companions can replace the lowest unconnected recommendations.
- A new-card batch includes no more than one same-band direct companion and
  remains diverse otherwise.

## Status

Implemented
