# Product Requirements Document — ToistoKone

**Status:** Draft 1.0  
**Product:** ToistoKone — Repetition Machine (local-first Finnish vocabulary and word-form practice app)  
**Priority:** Working MVP as quickly as possible for practice between Finnish classes

## 1. Purpose and scope

Build a small browser-based app for intensive Finnish vocabulary memorization followed by contextual practice of inflected forms. The learner already knows Finnish grammar, so the app does not teach grammatical rules or case names. Version 1 runs on a single local computer; deployment and AI-generated content are deferred.

## 2. User experience

### Home (`/`)

- Show total and mastered vocabulary cards, total and mastered word-form cards, and overall mastery percentage.
- Provide a **Start Practicing** button linking to `/practice`.
- Returning home must not discard the active quiz queue.

### Practice (`/practice`)

- Show one question at a time, a queue progress bar at the top, and a mastery indicator.
- Mastery icons: empty circle (0), quarter-filled circle (1), half-filled circle (2), and circle with check mark (3).
- Answers are selected by clicking/tapping; no keyboard shortcuts are required.
- Immediately after selection, grade the answer, highlight the correct choice, update the card score and icon, and show a **Reset mastery** control.
- Advance only when the learner clicks **Next**; remove the answered question from the queue at that point.
- No session-completion screen is required. The learner can stop and return whenever desired.

## 3. Card types

### Vocabulary cards

- Prompt: Finnish base word, with no hint.
- Answers: one correct English meaning group plus up to three randomly chosen distractor groups from other vocabulary entries, in randomized order.
- Each answer group displays all its English meanings together (e.g., `house / home`).
- A vocabulary card achieving score 3 unlocks all associated word-form cards.

### Word-form cards

- Each listed form is a distinct card, **including the base form itself**.
- Word-form cards are eligible only after the parent vocabulary card reaches score 3.
- Prompt: a Finnish example sentence with every whole-word occurrence of the target form blanked out; display **all** English translations of the full sentence.
- Sentence matching is case-insensitive and exact on whole words; no morphological analysis or precomputed associations.
- Choose a random matching sentence each time the card is used.
- Answers: correct form plus up to three distinct distractors drawn exclusively from other forms of the same base word (including its base form), shuffled. If fewer than four distinct forms exist, show fewer options.
- If no matching sentence exists, exclude that word-form card from quiz selection until content is updated.
- A sentence is not a card: mastery is tracked per word form, across all example sentences.
- All blanks in a question share one answer and count as a single attempt.

## 4. Mastery rules

Every vocabulary and word-form card starts at score 0 and has a score from 0 through 3.

| Current score | Correct | Incorrect |
|---|---:|---:|
| 0 | 1 | 0 |
| 1 | 2 | 1 |
| 2 | 3 | 1 |
| 3 | 3 | 3 |

- At score 3, mastery is permanent until manually reset.
- Reset mastery sets the individual card's score to 0; other cards are unchanged.
- Save scores and practice history immediately on answer submission, independently of the frontend queue.
- Track cards by exact spelling (with card type and parent base word where needed); ambiguous spellings are accepted as a v1 limitation.

## 5. Backend batch generation

Batch size is configured by `QUIZ_BATCH_SIZE` in `.env`, default `20`. For a batch of size N:

1. Select up to 70% of N from eligible score-1/2 cards.
2. Select up to 30% of N from eligible score-3 cards.
3. If slots remain, select **once** up to five eligible score-0 cards (or fewer if fewer slots/cards are available).

For the default N=20, these quotas are 14, 6, and at most 5 respectively. Do not redistribute unused quota between the first two groups or perform further backfilling. Return an undersized batch if necessary.

Within each score group, select the **least recently practiced** cards first, prioritizing never-practiced cards. Never duplicate a card within a batch. Mix vocabulary and word-form questions and shuffle their presentation order.

Examples (available score 1/2, score 3, score 0 → selected):

- 20, 20, 20 → 14 + 6 = 20
- 8, 20, 20 → 8 + 6 + 5 = 19
- 20, 2, 20 → 14 + 2 + 4 = 20
- 5, 3, 2 → 5 + 3 + 2 = 10
- 0, 0, 20 → 5

## 6. Continuous frontend quiz queue

- The **frontend alone** owns, stores, and restores the active queue; the backend never persists or tracks it.
- Request an initial backend batch if no valid saved queue exists.
- After each **Next**, remove the answered question.
- When **three or fewer unanswered questions remain**, request a new batch and append it. The progress bar decreases as questions are removed and fills again when a batch is appended.
- Save unanswered questions locally so the learner can resume the exact queue after navigation, refresh, or restart.
- If local queue data is missing, corrupt, or incompatible, discard it and fetch a fresh batch.
- The user may practice continuously without artificial session boundaries.

## 7. Import pipeline

The terminal-only pipeline reads:

- `dictionary.txt`: `talo - house / home`
- `word-forms.txt`: `ruoka - ruokaa / ruoasta / ruoan`
- `sentences/*.txt`: `Minä olen Liisa. - My name is Liisa. / I am Liisa.`

Input rules:

- Only exact ` - ` and ` / ` separators are accepted.
- Ignore blank lines and lines beginning with `#`.
- Skip malformed lines and report them.
- Import every `.txt` file in `sentences/`.
- Merge duplicate Finnish sentences by **exact Finnish text**, combining distinct English translations.
- Store sentences independently from words/forms and index them for efficient whole-word searches at quiz-generation time.
- Do not use AI to generate or validate content in v1. Sentences can be added manually or imported from Tatoeba after formatting.

A normal run **replaces exactly two artifacts**: the content SQLite database and a human-readable import report. A `--dry-run` generates only the report and leaves the existing content database untouched. The pipeline **never touches** the separate progress SQLite database. After regeneration, restarting the app is acceptable; no live reload is required.

## 8. Data ownership and persistence

| Data | Storage | Owner |
|---|---|---|
| Vocabulary, meanings, forms, sentences, translations | Content SQLite | Import pipeline |
| Mastery scores, last-practiced timestamps/history | Separate progress SQLite | Backend |
| Active unanswered quiz queue | Browser-local persistence | Frontend |

Content database IDs are not stable progress identifiers. Regenerating content must preserve progress for cards with matching exact spellings.

## 9. Technical and delivery constraints

- **Frontend:** React + Vite + React Router.
- **Backend:** Python + FastAPI.
- **Databases:** Two separate SQLite files (content and progress).
- **Configuration:** `.env`, including `QUIZ_BATCH_SIZE=20`.
- **Local development:** One command, `npm run dev`, launches frontend and backend together.
- No authentication, cloud hosting, Docker requirement, settings page, in-app pipeline controls, or keyboard shortcuts in v1.
- Prefer minimal dependencies and the fastest path to a functioning local MVP.

## 10. Acceptance criteria

- [ ] All three input sources import with exact delimiter and malformed-line rules.
- [ ] Normal and dry-run pipeline outputs follow the two-artifact/one-report contract.
- [ ] Regenerating content does not modify progress data.
- [ ] Home shows accurate vocabulary/form mastery totals and percentage.
- [ ] Vocabulary questions show all meanings and randomized distractors.
- [ ] Mastered vocabulary unlocks separate word-form cards, including the base form.
- [ ] Word-form questions use randomly selected matching sentences, blank every matching occurrence, and show all English translations.
- [ ] Word forms with no matching sentence are skipped.
- [ ] Every answer immediately updates grading, mastery score, and persistence.
- [ ] Score transitions, permanent mastery, and manual resets behave exactly as specified.
- [ ] Batch selection obeys the strict 70% / 30% / up-to-5 algorithm and least-recently-practiced priority.
- [ ] The frontend queue automatically appends new batches at three or fewer remaining questions.
- [ ] The queue survives page navigation and app restart; lost local queue data triggers a fresh batch.
- [ ] The app runs locally with `npm run dev`.

## 11. Deferred

AI-generated sentences, grammatical explanations, morphological matching, advanced ambiguity handling, cloud deployment, accounts, synchronization, settings UI, and additional management screens.

---

**Status:** PRD draft for review. Detailed database schemas, API contracts, and implementation tasks belong in the subsequent technical specification and implementation plan.
