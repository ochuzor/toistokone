# Technical Specification — ToistoKone

**Status:** Draft 1.0  
**Companion:** `toistokone_prd.md`
**App name:** ToistoKone (repository: `toistokone`; Python package: `toistokone`; UI title: ToistoKone)  
**Target:** Local-only MVP, built quickly; no accounts, deployment, or AI generation

## 1. Architecture

- **Frontend:** React + TypeScript + Vite + React Router. Routes `/` (home) and `/practice` (continuous quiz).
- **Backend:** Python 3.11+ with FastAPI, Pydantic, standard-library `sqlite3` (no ORM required for v1).
- **Databases:** `data/content.sqlite` (replaced by pipeline) and `data/progress.sqlite` (owned by running backend, never touched by pipeline).
- **Pipeline:** Python CLI reading plain-text inputs and producing `content.sqlite` and `import-report.txt`; dry-run produces only report.
- **Development:** root `npm run dev` starts backend and frontend together; Vite proxies `/api` to FastAPI. Bind to localhost only.
- **Configuration:** root `.env`, with `QUIZ_BATCH_SIZE=20`. Backend reads it on startup; no settings UI.

**Suggested repository layout** (paths are proposed conventions, not product requirements):

```text
toistokone/
  .env.example
  package.json                  # root dev script, using concurrently
  dictionary.txt
  word-forms.txt
  sentences/                   # any number of *.txt files
  data/
    content.sqlite             # generated, disposable
    progress.sqlite            # persistent, never pipeline-owned
    import-report.txt          # generated
  backend/
    requirements.txt
    app/
      main.py
      config.py
      db.py
      models.py
      quiz.py
      sentences.py
    pipeline.py
    tests/
  frontend/
    package.json
    src/
      App.tsx
      pages/Home.tsx
      pages/Practice.tsx
      lib/api.ts
      lib/queue.ts
      components/
```

## 2. Content database (`content.sqlite`)

All imported content is regenerated from source files. Use foreign keys, unique constraints and indexes. Keep a single Finnish sentence with many English translations.

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE vocabulary (
  id INTEGER PRIMARY KEY,
  finnish TEXT NOT NULL UNIQUE
);
CREATE TABLE vocabulary_meanings (
  vocabulary_id INTEGER NOT NULL REFERENCES vocabulary(id) ON DELETE CASCADE,
  meaning TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  PRIMARY KEY (vocabulary_id, meaning)
);
CREATE INDEX idx_vocabulary_meanings_vocab ON vocabulary_meanings(vocabulary_id);

CREATE TABLE word_forms (
  id INTEGER PRIMARY KEY,
  vocabulary_id INTEGER NOT NULL REFERENCES vocabulary(id) ON DELETE CASCADE,
  form TEXT NOT NULL,
  UNIQUE (vocabulary_id, form)
);
CREATE INDEX idx_word_forms_vocab ON word_forms(vocabulary_id);

CREATE TABLE sentences (
  id INTEGER PRIMARY KEY,
  finnish TEXT NOT NULL UNIQUE
);
CREATE TABLE sentence_translations (
  sentence_id INTEGER NOT NULL REFERENCES sentences(id) ON DELETE CASCADE,
  english TEXT NOT NULL,
  ordinal INTEGER NOT NULL,
  PRIMARY KEY (sentence_id, english)
);
CREATE INDEX idx_sentence_translations_sentence ON sentence_translations(sentence_id);
```

**Word-form normalization:** Every imported vocabulary word must have a base-form entry in `word_forms`, even if it is absent from `word-forms.txt`. This is necessary for the separately scored base-form word-form card and for distractor selection. A `word-forms.txt` entry referencing a base word absent from `dictionary.txt` is reported and skipped rather than silently creating a vocabulary card with no English meaning.

**Sentence search:** Because the accepted matching rule is case-insensitive whole-word matching (not substring matching), use a two-stage search:

1. Fetch candidate sentences using a simple index-assisted strategy (optional) or scan the sentence table for v1; **never** treat `LIKE '%form%'` as a definitive match.
2. Verify each candidate using a Unicode-aware case-insensitive whole-word boundary matcher in Python; use the same matcher to blank every occurrence. Do not split Finnish words on accented letters. Avoid matching within longer words.

For the fastest correct v1 implementation, scan `sentences` with a Python matcher and cache matches per form in backend memory during batch generation; the imported database still has indexes on sentence IDs and translations. **Performance note:** A scan may become slow for very large Tatoeba corpora; see §12 for an optional search index. No sentence-to-form association table is persisted.

## 3. Progress database (`progress.sqlite`)

The backend creates this database on first launch and retains it across all content imports. Progress keys are based on spelling, not IDs from the regenerated content database.

```sql
CREATE TABLE card_progress (
  card_type TEXT NOT NULL CHECK (card_type IN ('vocabulary', 'word_form')),
  base_word TEXT NOT NULL,
  target_form TEXT NOT NULL DEFAULT '',
  score INTEGER NOT NULL DEFAULT 0 CHECK (score BETWEEN 0 AND 3),
  last_practiced_at TEXT,           -- UTC ISO-8601
  attempt_count INTEGER NOT NULL DEFAULT 0,
  correct_count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (card_type, base_word, target_form)
);
CREATE INDEX idx_card_progress_score_time ON card_progress(score, last_practiced_at);

CREATE TABLE practice_attempts (
  id INTEGER PRIMARY KEY,
  attempt_id TEXT NOT NULL UNIQUE, -- client-generated UUID for retry safety
  card_type TEXT NOT NULL,
  base_word TEXT NOT NULL,
  target_form TEXT NOT NULL DEFAULT '',
  correct INTEGER NOT NULL CHECK (correct IN (0, 1)),
  score_before INTEGER NOT NULL,
  score_after INTEGER NOT NULL,
  answered_at TEXT NOT NULL
);
CREATE INDEX idx_attempts_card ON practice_attempts(card_type, base_word, target_form, answered_at);
```

Key conventions:
- Vocabulary: `('vocabulary', exact_base_spelling, '')`.
- Word form: `('word_form', exact_base_spelling, exact_form_spelling)`.
- Preserve exact input spelling for keys; matching in sentences alone is case-insensitive. Ambiguity/homographs are explicitly not resolved in v1.
- Missing progress rows mean score 0, no attempts, never practiced. Do not eagerly create rows for all imported content.
- When content disappears, retain orphaned progress rows; they simply do not appear in current quiz eligibility or home statistics.
- If a vocabulary card is manually reset below 3, its existing word-form progress is **retained** but those forms become ineligible until the parent reaches 3 again.

### Atomic answer submission

Within a transaction: check whether `attempt_id` already exists; if yes return the stored result without changing score again. Otherwise read score, apply transition, insert/update progress, insert attempt, commit, return the new score. An incorrect answer at score 0 stays 0; at score 1 stays 1; at score 2 becomes 1; at score 3 stays 3. A correct answer increments up to 3. Even score-3 attempts update last-practiced timestamp and history.

Manual reset changes only the selected card's `score` to 0; it does not delete its attempt history. It is a separate action from answering.

## 4. Import pipeline

### Inputs and exact syntax

```text
# dictionary.txt
# Finnish base word - English meaning / additional meaning
talo - house / home

# word-forms.txt
# base word - additional form / additional form
ruoka - ruokaa / ruoasta / ruoan

# sentences/lesson-01.txt
Minä olen Liisa. - My name is Liisa. / I am Liisa.
```

Rules:
- Parse only `.txt` files directly under `sentences/`, in deterministic sorted filename order.
- Ignore empty/whitespace-only lines and lines whose **first character** is `#` (do not treat leading-space `#` as a comment unless later agreed).
- Require exactly one ` - ` separator between left and right, with nonempty trimmed sides.
- Split right-hand values only on exact ` / `, require each to be nonempty after trimming; do not accept alternative separators.
- Preserve Finnish spelling and case, sentence punctuation, and translation text, except trimming outer whitespace.
- Malformed lines are skipped and reported with filename, line number and reason; continue importing other lines.
- Deduplicate identical Finnish sentences across files using exact text, merge unique English translations preserving first-seen order; report duplicate sentence and translation counts.
- For vocabulary/forms, deduplicate identical values rather than making duplicate cards. Report conflicts or duplicates.
- Insert base-form word-form cards for every vocabulary entry, even if there is no `word-forms.txt` line for it.

### Output and safety

Normal run:
1. Parse/validate all sources and build an in-memory normalized representation.
2. Create a **temporary** content SQLite file and load it transactionally.
3. Build indexes, run `PRAGMA foreign_key_check` and `PRAGMA integrity_check`.
4. Atomically replace `data/content.sqlite` only after successful build.
5. Replace `data/import-report.txt` with a human-readable report.

Dry run (`python -m backend.pipeline --dry-run`): parse/validate and replace **only** `data/import-report.txt`; do not create, open for writing, or replace `data/content.sqlite`. Neither mode ever writes to `progress.sqlite`.

Suggested CLI: `python -m backend.pipeline [--dry-run]`. Running the pipeline while the backend is active is unsupported for v1; restart the app after rebuilding.

Report should include input file counts, imported vocabulary/forms/sentences/translations, duplicates, skipped lines and diagnostics. Exactly two generated artifacts on normal run, one on dry-run; temporary files must be cleaned up.

## 5. Quiz selection algorithm

Let `N = QUIZ_BATCH_SIZE` (positive integer). For v1 use `quota_12 = floor(0.7 * N)` and `quota_3 = N - quota_12`. **Rounding for sizes other than 20 is a proposed convention requiring confirmation.**

1. Build eligible cards from current content and progress. Vocabulary is always eligible. Word forms require parent vocabulary score 3 and at least one sentence match.
2. From score 1–2 cards, select up to `quota_12`.
3. From score 3 cards, select up to `quota_3`.
4. If the result contains fewer than `N` cards, select **once** up to `min(5, N - count)` score-0 cards.
5. **Do not backfill** missing score-1/2 or score-3 allocations from other buckets, except the single score-0 step.
6. Never repeat a card within a batch.
7. Within each bucket, order by `last_practiced_at` ascending, with NULL first; break ties randomly.
8. For each selected word-form card, choose one random matching sentence, blank all whole-word occurrences, and include every English translation.
9. Generate answer options and shuffle cards and options before returning.

Example results at N=20:

| Available (score 1–2, score 3, score 0) | Result |
|---|---|
| (20, 20, 20) | 14 + 6 = 20 |
| (8, 20, 20) | 8 + 6 + 5 = 19 |
| (20, 2, 20) | 14 + 2 + 4 = 20 |
| (5, 3, 2) | 5 + 3 + 2 = 10 |
| (0, 0, 20) | 0 + 0 + 5 = 5 |

**Important:** Batch uniqueness is per request only. Because the backend never tracks the active frontend queue, a later batch can include a card still queued locally. The frontend should filter duplicates against its remaining queue and append only unique cards. Do not ask the backend to persist queue state.

## 6. Question construction

### Vocabulary

- Prompt: exact Finnish base word.
- Correct option: all English meanings for that vocabulary entry, displayed together as `meaning 1 / meaning 2`.
- Distractors: up to three **random** other vocabulary entries' complete meaning groups; ensure no duplicate option text and no identical group to the correct answer.
- Shuffle options; return a stable `option_id` and the correct `option_id` to allow immediate client-side highlighting.

### Word form

- Prompt: sentence with every case-insensitive whole-word occurrence of the target form replaced by `____`.
- English: all translations of that sentence, in stored order.
- Options: target form plus up to three **distinct** other forms of the same base word, including the base form; randomize.
- If only one distinct form exists, a one-option question would not test recall. **Proposed v1 safeguard:** exclude such word-form cards until at least two distinct forms exist; see §13 for confirmation.
- Ensure that replacing target text does not accidentally blank a substring of a longer Finnish word.

No sentence is assigned its own mastery score. Multiple sentences share the same word-form card.

## 7. HTTP API (`/api`)

All JSON is UTF-8. Use predictable error responses (`{ "detail": "..." }`). Use Pydantic request/response models.

### `GET /api/health`

Returns `{ "status": "ok" }`, optionally with content database availability.

### `GET /api/stats`

Returns counts based on current content and progress (missing progress = score 0):

```json
{
  "vocabulary": { "total": 120, "mastered": 45 },
  "word_forms": { "total": 480, "mastered": 80 },
  "overall": { "total": 600, "mastered": 125, "mastery_percent": 20.83 }
}
```

Word-form totals include the separate base-form card. Counts may include cards not yet eligible for practice; statistics are about content/mastery, not current eligibility.

### `POST /api/quiz/batch`

Request `{}`; batch size comes from backend `.env`, not from the frontend.

Response example (illustrative, not real content):

```json
{
  "questions": [
    {
      "question_id": "random-uuid",
      "card": { "type": "vocabulary", "base_word": "talo", "target_form": "" },
      "score": 1,
      "prompt": "talo",
      "english_translations": [],
      "options": [
        { "id": "a", "text": "house / home" },
        { "id": "b", "text": "food / meal" }
      ],
      "correct_option_id": "a"
    }
  ]
}
```

For word-form questions, `prompt` is the blanked Finnish sentence and `english_translations` contains all sentence translations. Option count varies from 2 to 4, subject to the one-option safeguard above.

The batch endpoint does **not** create or modify progress, track issued questions, or store queue state.

### `POST /api/answers`

Request:

```json
{
  "attempt_id": "client-generated-uuid",
  "card": { "type": "word_form", "base_word": "ruoka", "target_form": "ruoasta" },
  "selected_option_id": "b",
  "correct_option_id": "a"
}
```

**Security/trust tradeoff for local v1:** The client sends both selected and correct option IDs, and the backend derives `correct = selected_option_id == correct_option_id`. This is acceptable for a single-user local app but not for later public deployment. The server validates that the card exists in current content and uses a transaction with `attempt_id` idempotency. **For a deployable design, use a signed question token or server-side verifiable answer instead.**

Response:

```json
{ "correct": false, "score_before": 2, "score_after": 1, "mastered": false }
```

If network submission fails, keep the answered card and pending `attempt_id` locally; retry the same attempt instead of advancing or silently losing progress.

### `POST /api/cards/reset`

Request `{ "card": { "type": "vocabulary", "base_word": "talo", "target_form": "" } }`.

Response `{ "score": 0 }`. Reset only the specified card, retain its practice history.

## 8. Frontend state and persistence

### Routes

- `/`: home with vocabulary total/mastered, word-form total/mastered, overall percentage and **Start Practicing**.
- `/practice`: current question, queue progress bar, mastery icon, clickable options, immediate grading, reset mastery after answer, **Next**, and navigation home.

### Queue model

Store locally (e.g. `localStorage` under a versioned key):

```ts
type SavedPracticeState = {
  schemaVersion: 1;
  queue: QuizQuestion[];
  currentAnswer?: {
    questionId: string;
    selectedOptionId: string;
    attemptId: string;
    submitted: boolean;
    result?: { correct: boolean; scoreAfter: number };
  };
};
```

- On `/practice` load, restore and validate saved queue. If missing, malformed, or incompatible, discard it and request a new batch.
- Persist queue updates after fetching, answering, resetting, and clicking Next. No backend queue endpoint.
- Click an option once; lock all options while grading/submitting. On successful backend response, highlight selected/correct options and update icon. Show reset button and enable Next.
- Next removes the current question and moves to the next one. Never remove a question before a successful answer submission.
- When remaining queue count is **<= 3**, request a new batch and append unique card keys not already in the queue. Prevent concurrent replenishment requests.
- If backend returns zero questions, show a friendly empty-state message and a Retry button rather than an endless request loop.
- A returning learner sees the same unanswered questions, options, and sentence choices. If a card was already answered but Next was not pressed, restore the feedback state rather than resubmitting the answer.
- Since content may change after restart, use a content-version fingerprint from the backend to invalidate stale queued questions **only when necessary**; if invalidated, generate a new batch. This does not affect progress.

### Progress bar

Define queue capacity as the queue length immediately after the most recent append, and show `remaining / capacity`. On Next it decreases; after append it refills. Persist capacity with the queue to avoid jumping on reload. This is a UI convention to implement the agreed refill behavior; no session-completion screen.

## 9. Local development and configuration

Example `.env`:

```dotenv
QUIZ_BATCH_SIZE=20
CONTENT_DB_PATH=data/content.sqlite
PROGRESS_DB_PATH=data/progress.sqlite
API_HOST=127.0.0.1
API_PORT=8000
```

Root `npm run dev` launches `uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000` and `vite --host 127.0.0.1` via `concurrently` (or equivalent). Document one-time Python/npm dependency installation in README. Vite proxies `/api` to `http://127.0.0.1:8000`.

If content database is missing, show a clear instruction to run the terminal pipeline rather than crashing without explanation. Backend should initialize progress database without modifying content database.

## 10. Testing requirements

**Pipeline:** exact delimiters, blank/comment lines, malformed-line reporting, multiple files, deduplication/translation merging, base-form insertion, orphan word forms, dry-run never touching existing content DB, normal-run atomic replacement, progress DB untouched.

**Sentence matcher:** case-insensitive matching, Finnish accented letters, punctuation boundaries, no substring matches, all repeated occurrences blanked, missing matches excluded.

**Mastery:** every transition in the score table, score-3 permanence, reset, persistence across content rebuild, idempotent retries, last-practiced updates.

**Batch selection:** all five example cases above, no redistribution, max five new cards, never-practiced first, least-recently-practiced order, no duplicates within batch, eligibility gates, mixed card types.

**Frontend:** restore exact queue after refresh, refill at <=3, no duplicate cards appended, one answer submission per attempt, Next-only removal, restore answered-but-not-advanced state, fallback on corrupt local state, empty batches, home navigation, progress bar behavior.

## 11. Delivery and scope boundaries

Required: working local pipeline, two databases, FastAPI service, two React routes, tests for core algorithms, `npm run dev`, and short README. No accounts, Docker, cloud hosting, AI generation, grammar teaching, keyboard shortcuts, settings UI, or import button.

## 12. Scale note: thousands of Tatoeba sentences

The `sentences` and `sentence_translations` primary/foreign-key indexes support lookups and joins but **do not themselves make arbitrary whole-word searches fast**. If a full scan proves slow, add a content-only inverted index (e.g. `sentence_tokens(token_casefold, sentence_id)` populated from each sentence during import) and index `(token_casefold, sentence_id)`. This is a search index, **not** a word-form association, and does not change the separate-sentence design. Verify exact whole-word matches in Python before using results. Prefer this optional index if initial Tatoeba imports are large enough to affect batch latency.

## 13. Open implementation decisions (do not silently invent product behavior)

1. **Non-20 batch rounding:** Proposed `floor(0.7N)` and remainder for score-3 quota; confirm if needed.
2. **Only one distinct form:** Proposed skipping the word-form question rather than showing a trivially correct single option; confirm if needed.
3. **Question grading trust:** Local MVP can submit selected/correct option IDs as above; later deployment needs server-verifiable answer integrity.
4. **Queue duplicate exhaustion:** If new batches repeatedly overlap the frontend queue, filter duplicates and allow an undersized queue; avoid infinite retries. The backend does not track frontend queue state.
5. **Sentence import scale:** Start with direct sentence scans; add a token index if Tatoeba corpus size causes unacceptable latency.

These are technical proposals, not changes to the confirmed PRD. All other behavior is governed by the agreed requirements.
