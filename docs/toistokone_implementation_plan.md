# Implementation Plan — ToistoKone

**Status:** Draft 1.0  
**Companions:** `toistokone_prd.md`, `toistokone_technical_spec.md`
**Priority:** Get a useful, local-only practice app running as quickly as possible.  
**Implementation style:** Small, testable vertical slices; avoid infrastructure or features not required by the PRD.

## 1. Definition of done

The user can edit three kinds of plain-text input, run a terminal import, start the app with `npm run dev`, open the home screen, and practice vocabulary and contextual word forms continuously. Answers immediately persist mastery to `progress.sqlite`; the frontend restores its remaining queue after refresh/restart. Regenerating `content.sqlite` never erases progress.

## 2. Implementation sequence

### Phase 0 — Repository skeleton and local startup

**Tasks**

- [x] Create root project, `.env.example`, `.gitignore`, and short README.
- [x] Create Python FastAPI backend and React + TypeScript + Vite frontend with React Router.
- [x] Configure root `npm run dev` to start both services via `concurrently` or equivalent.
- [x] Configure Vite `/api` proxy; bind development services to localhost.
- [x] Read `QUIZ_BATCH_SIZE=20` from root `.env` on backend startup; validate positive integer.
- [x] Add `GET /api/health`; show home and practice routes with placeholders.
- [x] Ensure `data/progress.sqlite` and generated content/report files are gitignored; include tiny sample inputs for smoke tests.

**Exit gate:** Complete — one command starts both services, `/` and `/practice` render, and `/api/health` succeeds through the Vite proxy. One-time dependency setup is documented separately from the one-command startup.

### Phase 1 — Import pipeline and content database

**Tasks**

- [x] Implement strict parser for `dictionary.txt`, `word-forms.txt`, and sorted direct-child `sentences/*.txt`.
- [x] Support only exact ` - ` and ` / ` delimiters; skip empty lines and lines whose first character is `#`.
- [x] Skip/report malformed lines with filename, line number, and reason.
- [x] Build content schema: vocabulary, meanings, word forms, sentences, translations, foreign keys, and indexes.
- [x] Insert a separate base-form word-form row for every dictionary word; skip/report form entries without a dictionary base word.
- [x] Deduplicate identical vocabulary/forms and exact Finnish sentences; merge unique sentence translations preserving first-seen order.
- [x] Implement `python -m backend.pipeline` to build a temporary SQLite DB, verify integrity, then atomically replace `data/content.sqlite` and write `data/import-report.md`.
- [x] Implement `--dry-run` to write **only** the report, never changing content or progress DB.
- [x] Add representative sample data: at least two vocabulary words, a word with multiple forms, and multiple sentences/translations.

**Exit gate:** Complete — normal import creates only the content DB and report; dry-run replaces only the report. Sample data is queryable, malformed lines are reported, and `progress.sqlite` is never touched by the pipeline.

### Phase 2 — Persistent progress and scoring API

**Tasks**

- [x] Create `progress.sqlite` on backend startup (not during pipeline); implement `card_progress` and `practice_attempts` schema.
- [x] Key vocabulary cards by exact base spelling and word-form cards by exact `(base, form)` spelling; never key progress to regenerated content IDs.
- [x] Implement score transitions: `0→1/0`, `1→2/1`, `2→3/1`, `3→3/3` (correct/incorrect).
- [x] Implement `POST /api/answers` with atomic progress/history update and client-generated `attempt_id` idempotency.
- [x] Update last-practiced time and attempt history even for mastered cards; do not modify score 3.
- [x] Implement `POST /api/cards/reset` (score to 0, retain history).
- [x] Implement `GET /api/stats` using current content plus progress, including base-form word-form cards.
- [x] Keep orphaned progress if content is removed; resetting a vocabulary card below 3 temporarily gates its forms without erasing their scores.

**Exit gate:** Complete — automated tests cover transitions, reset, idempotent retries, current-content stats, and progress persistence across content rebuilds.

### Phase 3 — Sentence search and quiz batch API

**Tasks**

- [x] Implement Unicode-aware, case-insensitive whole-word matching against Finnish sentences; reject substring matches inside longer words.
- [x] Blank **all** target-form occurrences; preserve punctuation and show **all** English translations.
- [x] Select a random matching sentence for a selected word-form card; skip forms with no sentence matches.
- [x] Build eligible card pool: all vocabulary cards; word-form cards only when parent vocabulary is score 3 and form has a matching sentence.
- [x] Implement exact quota algorithm: up to 70% score 1–2; then up to 30% score 3; then **once** up to five score-0 cards for remaining deficit. No quota redistribution/backfill.
- [x] Within each bucket select never-practiced first, then least recently practiced; randomize ties.
- [x] Generate vocabulary questions: Finnish base prompt; full meaning group as correct option; up to three random other meaning groups as distractors.
- [x] Generate word-form questions: blanked sentence, all translations, correct form plus up to three distinct distractors from same base word (including base form).
- [x] Shuffle option order and final mixed vocabulary/form question order; no duplicate card in one batch.
- [x] Implement `POST /api/quiz/batch` using `.env` batch size. Backend does not store issued batches or queue state.
- [x] Add tests for the five agreed 20-card quota examples, eligibility, form matching, distractors, and undersized batches.

**Exit gate:** Complete — an API batch is generated from imported sample data; tests prove quota behavior, matching, eligibility, formatting, and undersized output safety.

### Phase 4 — Practice screen (first usable end-to-end milestone)

**Tasks**

- [x] Implement `/practice` with one card at a time, Finnish prompt, optional English translations, up to four clickable/tappable answer options, and mastery icon (empty / quarter / half / check).
- [x] On answer selection, lock choices, submit to backend, and show correct/incorrect feedback and correct answer.
- [x] Update mastery icon after successful answer response; display **Reset mastery** button after answering.
- [x] Implement reset API call and immediate UI update.
- [x] Implement **Next**; only Next removes an answered card and advances. No auto-advance and no keyboard shortcuts.
- [x] Show a clear message if no quiz cards are available, with a retry action.
- [x] Add navigation back to home without clearing the active queue.

**Exit gate:** Complete — browser verification covers navigation, answer feedback, reset, Next-only advancement, and preserved in-memory queue state on return from home.

### Phase 5 — Continuous frontend-owned queue and recovery

**Tasks**

- [x] Store unanswered question objects, their exact options/sentence, current answer feedback state, and progress-bar capacity in versioned frontend local storage.
- [x] Restore the same queue on refresh and when navigating back to practice; if storage is missing/corrupt/incompatible, request a fresh backend batch.
- [x] When queue has **three or fewer** remaining cards, request another batch and append it; prevent concurrent fetches and request loops.
- [x] Filter cards already in the local remaining queue when appending, because backend only guarantees uniqueness within each batch.
- [x] Keep answered-but-not-advanced card visible with feedback on reload; persist pending `attempt_id` for safe retries.
- [x] Implement progress bar as `remaining / capacity`, decreasing on Next and refilling when a new batch is appended; persist capacity across reloads.
- [x] Handle network failures, zero-result batches, and stale queue questions after content rebuild gracefully.

**Exit gate:** Complete — browser-local queue state restores exact questions and answer feedback after reload, while duplicate or empty refills safely leave an undersized queue without request loops.

### Phase 6 — Home summary and polish

**Tasks**

- [x] Implement `/` with total/mastered vocabulary, total/mastered word forms, overall mastery percentage, and **Start Practicing**.
- [x] Ensure stats refresh when returning from practice.
- [x] Keep layout responsive and fast to click; no settings/import/admin pages.
- [x] Add clear first-run message if `content.sqlite` is missing: run the terminal pipeline.
- [x] Verify restart-after-import workflow and progress preservation.
- [x] Update README with setup, import, dry-run, dev startup, source formats, `.env`, backup guidance for `progress.sqlite`, and known v1 limitations.

**Exit gate:** Complete — the home page reads persistent backend statistics, links to practice, and README instructions cover a new local setup and safe content reimports.

### Phase 7 — Focused regression and handoff

**Tasks**

- [x] Run pipeline, backend, and frontend tests; fix blocking failures.
- [x] Manually verify: initial score 0; reach score 3; forms unlock; incorrect at 2 returns to 1; score 3 stays mastered; reset; continue practicing; refresh; restart; reimport content; progress retained.
- [x] Test Finnish accented characters, case-insensitive word boundaries, repeated target forms, multiple English translations, duplicate sentence imports, and no matching sentences.
- [x] Test quota cases and local queue refill with both full and undersized batches.
- [x] Verify that the pipeline never writes `progress.sqlite`, and the backend never persists the active queue.
- [x] Deliver concise README and a list of any deviations/open decisions; no unrequested scope expansion.

**Exit gate:** Complete — the full regression suite and real reimport pass, with `progress.sqlite` unchanged.

## 3. Suggested coding-agent execution protocol

For each phase: implement only that phase; run its tests/smoke checks; fix failures; summarize changed files, commands run, and remaining issues. Do not rewrite agreed behavior to simplify tests. Commit after each passing phase if the repository uses Git. Prefer standard libraries and a small dependency footprint. Do not introduce authentication, ORM, Docker, AI generation, cloud services, or extra UI pages.

**Fastest value path:** Phases 0–4 produce a usable end-to-end quiz. Phases 5–7 add the agreed persistence, home dashboard, and reliability needed for daily use. The agent should still complete all phases before calling v1 done.

## 4. Explicit invariants for code review

1. **Only the pipeline** replaces `content.sqlite` and writes `import-report.md`; **never** `progress.sqlite`.
2. **Only the backend** writes mastery scores and practice history; **only the frontend** owns the active question queue.
3. A sentence is **not** a card; score is attached to a vocabulary entry or a `(base, form)` pair.
4. Score 3 never changes through ordinary answers, only explicit reset.
5. Quiz allocation is sequential 70% / 30% / up-to-five-new **without backfilling**.
6. A word-form card is eligible only when its parent vocabulary card is mastered and a matching sentence exists.
7. Every target occurrence is blanked; every available English sentence translation is displayed.
8. An answer updates progress immediately; a card leaves the frontend queue **only** when Next is clicked.
9. New quiz batches append when remaining count is three or fewer; the frontend filters overlap with its queue.
10. Normal import leaves exactly the two agreed generated artifacts; dry-run leaves only the report as its output.

## 5. Decisions to confirm before or during implementation

These are inherited from the technical-spec draft and are **not** new product requirements:

- **Batch sizes other than 20:** proposed `floor(0.7 × N)` for score 1–2, with the remainder allocated to score 3.
- **Word with only one distinct form:** proposed skipping its word-form quiz until there are at least two choices, rather than showing a one-answer question.
- **Local-only grading trust:** technical spec proposes sending both selected and correct option IDs for server scoring. This is fine for local v1 but must be hardened before public deployment.
- **Overlapping batches:** frontend filters duplicates against its own queue and accepts an undersized append without looping indefinitely.
- **Large Tatoeba import:** start with direct sentence scanning and add a content-only token index if matching becomes too slow; do not add persistent sentence-to-word associations.

The implementation agent should flag these clearly, use the documented proposed defaults only where needed to make progress, and not treat them as previously confirmed user decisions.
