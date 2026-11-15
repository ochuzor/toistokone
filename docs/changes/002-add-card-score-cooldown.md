# Add a card-score cooldown

**Status:** Completed

## Problem

A learner can receive enough consecutive quiz appearances to take one card
from score 0 to permanent mastery in minutes. Current progress logic applies
the normal score transition to every distinct answer attempt.

## Desired behavior

After a score increase, that card's score remains unchanged for a configurable
cooldown period (default: 15 minutes). During the cooldown, both correct and
incorrect answers are still recorded as attempts, but neither increases nor
decreases the score. Once the cooldown has elapsed, the next answer uses the
existing score-transition rules.

## Proposed implementation

- Add `CARD_SCORE_COOLDOWN_MINUTES` to `.env` settings, defaulting to `15`.
  Validate it as a non-negative integer; `0` disables the delay for local
  testing or an explicit opt-out.
- Add nullable `last_score_increased_at` to `card_progress`. On application
  startup, safely migrate existing progress databases with `ALTER TABLE` only
  when the column is absent; preserve all existing scores and history.
- Update answer recording to compare the current UTC time with
  `last_score_increased_at`. If less than the configured cooldown has elapsed,
  return the unchanged score. Otherwise, apply the existing transition table.
- Set `last_score_increased_at` only when an answer actually increases the
  score. Continue updating `last_practiced_at` and practice-attempt history on
  every submitted answer, including cooldown-blocked attempts and score-3
  attempts.
- Pass the configured cooldown from the FastAPI route to the progress layer.
  No queue, quiz-selection, or frontend API-shape change is required.
- Document the new setting and learner-visible behavior in the README and
  product/technical documentation.

## Reset behavior

Proposed: retain the existing explicit **Reset mastery** action as an immediate
manual override. Cooldown blocks answer-driven score changes only. This avoids
silently changing the established reset behavior; approval of this plan
confirms that interpretation.

## Affected files

- `backend/app/config.py`
- `backend/app/db.py`
- `backend/app/main.py`
- `backend/tests/test_config.py`
- `backend/tests/test_progress.py`
- `backend/tests/test_progress_api.py`
- `.env.example`
- `README.md`
- `docs/toistokone_prd.md`
- `docs/toistokone_technical_spec.md`
- `docs/BACKLOG.md`

## Risks and constraints

- Existing `progress.sqlite` files must migrate in place and must never be
  reset, replaced, or touched by the import pipeline.
- Use UTC timestamps and inject the current time into database-layer tests to
  avoid flaky wall-clock tests.
- Preserve retry idempotency: a repeated `attempt_id` returns its original
  result and must not create another attempt or alter cooldown state.
- Preserve all current score transitions after cooldown expiry, including
  permanent score 3.
- The existing frontend has no unit-test runner. Do not add a testing
  dependency solely for queue-threshold coverage; verify replenishment and the
  complete cooldown flow through Playwright after approval.

## Acceptance criteria

- A correct answer increases a card's score and records its increase timestamp.
- Correct and incorrect answers within 15 minutes leave the score unchanged,
  while recording attempts and updating last-practiced time.
- An answer at exactly 15 minutes or later applies the existing score rules.
- `CARD_SCORE_COOLDOWN_MINUTES` defaults to 15, rejects invalid/negative
  values, and supports `0` as no cooldown.
- Existing progress databases gain the new column without losing progress or
  history; the import pipeline still does not modify them.
- Idempotent answer retries, reset behavior, stats, and quiz selection remain
  correct.
- Relevant backend tests, frontend build, and a Playwright complete-practice
  flow pass. Playwright also confirms replenishment at `<= 3` cards when
  practical with the available UI.
