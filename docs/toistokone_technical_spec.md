# Technical Specification — ToistoKone

**Status:** Draft 1.0  
**Companion:** `toistokone_prd.md`
**App name:** ToistoKone (repository: `toistokone`; Python package: `toistokone`; UI title: ToistoKone)  
**Target:** Local-only MVP, built quickly; no accounts, deployment, or AI generation

## 1. Architecture

- **Frontend:** React + TypeScript + Vite + React Router. Routes `/` (home) and `/practice` (continuous quiz).
- **Backend:** Python 3.11+ with FastAPI, Pydantic, standard-library `sqlite3` (no ORM required for v1).
- **Databases:** `data/content.sqlite` (replaced by pipeline) and `data/progress.sqlite` (owned by running backend, never touched by pipeline).
- **Pipeline:** Python CLI reading plain-text inputs and producing `content.sqlite` and `import-report.md`; dry-run produces only report.
- **Development:** root `npm run dev` starts backend and frontend together; Vite proxies `/api` to FastAPI. Bind to localhost only.
- **Configuration:** root `.env`, with `QUIZ_BATCH_SIZE=20`. Backend reads it on startup; no settings UI.

**Suggested repository layout** (paths are proposed conventions, not product requirements):

```text
toistokone/
  .env.example
  package.json                  # root dev script, using concurrently
  dictionary.txt
  lexicon/
    kaikki.org-dictionary-Finnish-words.jsonl  # local, ignored source
  frequency/
    fi_50k.txt
  sentences/                   # any number of *.txt files
  data/
    content.sqlite             # generated, disposable
    progress.sqlite            # persistent, never pipeline-owned
    import-report.md           # generated
    kaikki-forms.sqlite        # generated local morphology index
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
  finnish TEXT NOT NULL UNIQUE,
  meaning_quizzable INTEGER NOT NULL CHECK (meaning_quizzable IN (0, 1))
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
  card_key TEXT NOT NULL,
  form TEXT NOT NULL,
  profile TEXT NOT NULL,
  prompt_label TEXT NOT NULL,
  UNIQUE (vocabulary_id, card_key)
);
CREATE INDEX idx_word_forms_vocab ON word_forms(vocabulary_id);

CREATE TABLE learning_sets (
  key TEXT PRIMARY KEY,
  title TEXT NOT NULL
);
CREATE TABLE learning_set_words (
  set_key TEXT NOT NULL REFERENCES learning_sets(key) ON DELETE CASCADE,
  vocabulary_id INTEGER NOT NULL REFERENCES vocabulary(id) ON DELETE CASCADE,
  PRIMARY KEY (set_key, vocabulary_id)
);

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
CREATE TABLE sentence_tokens (
  token_casefold TEXT NOT NULL,
  sentence_id INTEGER NOT NULL REFERENCES sentences(id) ON DELETE CASCADE,
  PRIMARY KEY (token_casefold, sentence_id)
);
CREATE INDEX idx_sentence_tokens_sentence ON sentence_tokens(sentence_id);
CREATE TABLE frequency_words (
  token_casefold TEXT PRIMARY KEY,
  frequency_rank INTEGER NOT NULL UNIQUE,
  frequency_count INTEGER NOT NULL CHECK (frequency_count > 0)
);
CREATE TABLE content_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
```

**Grammar-card generation:** The pipeline indexes the local Kaikki JSONL source and generates form cards for matching dictionary headwords. Nominal cards cover genitive, partitive, plural genitive, plural partitive, inessive, elative, illative, adessive, ablative, allative, essive, and nominative plural; singular nominative is already the vocabulary meaning-card prompt and is not repeated as a form card. Plural genitive and plural partitive are generated only from Kaikki entries classified as nouns, adjectives, pronouns/determiners, or numerals; proper names and verb/participle entries are excluded. Only the six personal pronouns (`minä`, `sinä`, `hän`, `me`, `te`, `he`) also receive accusative cards. Pronouns use separate singular and plural case profiles, keeping pairs such as `se` and `ne` in their own paradigms. Verb cards cover six active affirmative present-indicative, past-indicative, and conditional persons; negative, passive, and multi-word perfect conditionals are excluded. After base-vocabulary mastery, ordinary nominal profiles unlock in five ordered stages: genitive, partitive, and nominative plural; inner local cases; outer local cases; essive; and plural genitive/partitive. Plural-pronoun profiles begin with nominative, genitive, partitive, and accusative, then unlock inner and outer local cases. Personal-pronoun accusative cards join their first stage. Verb cards unlock in six ordered three-card stages: present singular, past singular, present plural, past plural, conditional singular, then conditional plural. Two score-3 cards in a stage unlock the next; a sparse stage passes through only until its profile has at least two distinct answer options, and previously practised cards remain eligible. `card_key` identifies the grammar slot independently of its surface spelling, so a shared noun/verb spelling keeps separate progress. The first non-rare single-word candidate is selected and alternatives are reported.

**Verb-form presentation:** The practice screen presents a verb card's base form
as the visual anchor. Its person-and-blank cue is smaller supporting context,
followed by the present, past, or conditional tense label.

**Forms-only entries:** A dictionary word with an uppercase initial and English
meanings all exactly matching its Finnish spelling is imported with
`meaning_quizzable = 0`. It remains available for Kaikki form generation and
known-word filtering, but has no vocabulary card, vocabulary score, focus-word
request, or mastery-statistics entry. Its form cards bypass the usual base-card
mastery gate. This virtual mastery is limited to form eligibility.

**Learning sets:** Direct-child `learning-sets/*.md` files begin with a `---`,
`id: lower-case-kebab-id`, `---` block, then contain a single H1 title and a
bullet list of at least ten exact dictionary headwords. The pipeline rejects
missing, malformed, or duplicate IDs; missing titles; undersized sets;
malformed entries; duplicates within a set; and words absent from
`dictionary.txt`. It stores the declared ID as the stable set key in the
content database with vocabulary membership; generated forms inherit their base
word's membership. The import report warns about set-specific sentence coverage.
`progress.sqlite` stores at most one selected set key. Score-0 candidate ranking
prefers active-set vocabulary after focus requests and active-set forms before
other forms; review quotas are unchanged. Reading breaks add active-set surfaces
to their candidates and apply a small matching-sentence bonus.
The API lists set summaries at `GET /api/learning-sets` and exposes a selected
set's member words, meanings, base-card scores, and form mastery counts at
`GET /api/learning-sets/{set_key}`. The frontend presents that detail at
`/learning-sets/:setKey`.

**Learning paths:** Direct-child `learning-paths/*.md` files use the same
stable-ID header and H1 title format as learning sets, followed by ordered
learning-set IDs. The pipeline rejects malformed, missing, or duplicate path
IDs; unknown referenced set IDs; and duplicates within a path. It stores paths
and their ordered memberships in the content database; a set may be reused in
different paths. `GET /api/learning-paths` lists live summaries and
`GET /api/learning-paths/{path_key}` returns ordered steps. A step completes
when at least 70% of meaning-quizzable vocabulary cards and 40% of form cards
have score at least 2; a zero-card category is considered complete. The first
incomplete step after a fully completed prefix is available; later incomplete
steps are locked. No path state is stored in `progress.sqlite`, and paths never
change the selected active set automatically.

**Import preflight:** Dictionary entries, learning-set membership, Kaikki
source/index availability, and the required frequency list are validated before
the pipeline rebuilds any morphology or recommendation index. Fatal preflight
errors write the import report and leave the existing content and progress
databases unchanged. Malformed dictionary or sentence lines remain non-fatal
diagnostics and are skipped as before.

**Sentence storage:** The pipeline populates `sentence_tokens` with distinct case-folded Unicode tokens for contextual recommendations and score-3 form reinforcement. No sentence-to-form association table is persisted. `frequency_words` stores the required frequency source for contextual word recommendations; it is content-only and has no progress state.

## 3. Progress database (`progress.sqlite`)

The backend creates this database on first launch and retains it across all content imports. Progress keys are based on spelling, not IDs from the regenerated content database.

```sql
CREATE TABLE card_progress (
  card_type TEXT NOT NULL CHECK (card_type IN ('vocabulary', 'word_form')),
  base_word TEXT NOT NULL,
  target_form TEXT NOT NULL DEFAULT '',
  score INTEGER NOT NULL DEFAULT 0 CHECK (score BETWEEN 0 AND 3),
  last_practiced_at TEXT,           -- UTC ISO-8601
  last_score_increased_at TEXT,     -- UTC ISO-8601; nullable until first increase
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

CREATE TABLE active_learning_set (
  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
  set_key TEXT NOT NULL
);
```

Key conventions:
- Vocabulary: `('vocabulary', exact_base_spelling, '')`.
- Word form: `('word_form', root_dictionary_spelling, exact_form_spelling)`.
- Preserve exact input spelling for keys; matching in sentences alone is case-insensitive. Ambiguity/homographs are explicitly not resolved in v1.
- Missing progress rows mean score 0, no attempts, never practiced. Do not eagerly create rows for all imported content.
- When content disappears, retain orphaned progress rows; they simply do not appear in current quiz eligibility or home statistics.
- If a vocabulary card is manually reset below 3, its existing word-form progress is **retained** but those forms become ineligible until the parent reaches 3 again.

### Atomic answer submission

Within a transaction: check whether `attempt_id` already exists; if yes return the stored result without changing score again. Otherwise read score and `last_score_increased_at`. If the configured `CARD_SCORE_COOLDOWN_MINUTES` has not elapsed since that timestamp, retain the score; otherwise apply the transition. Insert/update progress, insert the attempt, commit, and return the score. An incorrect answer at score 0 stays 0; at score 1 stays 1; at score 2 becomes 1; at score 3 stays 3. A correct answer increments up to 3. Record `last_score_increased_at` only when score rises. Every answer updates last-practiced time and history, including cooldown-blocked and score-3 attempts. Existing progress databases are migrated in place to add the timestamp column.

Manual reset changes only the selected card's `score` to 0; it does not delete its attempt history. It is a separate action from answering.

## 4. Import pipeline

### Inputs and exact syntax

```text
# dictionary.txt
# Finnish base word - English meaning / additional meaning
talo - house / home

# lexicon/kaikki.org-dictionary-Finnish-words.jsonl
# local Kaikki source; parsed into data/kaikki-forms.sqlite

# frequency/fi_50k.txt
on 4061285

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
- Generate Kaikki cards only for the configured nominal and verb profiles. Skip rare, possessive, negative, passive, and multi-word forms; report words without a usable profile and alternate candidates.
- Require `frequency/fi_50k.txt`. Each line has one word and a positive integer count. Store case-folded tokens in source order as frequency ranks; a missing, malformed, non-positive, or duplicate entry is fatal.

### Output and safety

Normal run:
1. Parse/validate all sources and build an in-memory normalized representation.
2. Create a **temporary** content SQLite file and load it transactionally.
3. Build indexes, run `PRAGMA foreign_key_check` and `PRAGMA integrity_check`.
4. Atomically replace `data/content.sqlite` only after successful build.
5. Replace `data/import-report.md` with a human-readable Markdown report.

Dry run (`python -m backend.pipeline --dry-run`): parse/validate and replace `data/import-report.md`; do not create, open for writing, or replace `data/content.sqlite`. It may build or refresh the ignored reusable Kaikki index. Neither mode ever writes to `progress.sqlite`.

Suggested CLI: `python -m backend.pipeline [--dry-run]`. Running the pipeline while the backend is active is unsupported for v1; restart the app after rebuilding.

Report should include imported vocabulary/forms/sentences/translations/frequency entries, Kaikki index rebuild status, words without usable profiles, alternate form candidates, duplicates, diagnostics, and fatal validation errors. Exactly two content artifacts on a successful normal run, one on dry-run; the local reusable Kaikki index is built or refreshed separately from content replacement. A fatal source or frequency error writes only the report and leaves the prior content database intact.

## 5. Quiz selection algorithm

Let `N = QUIZ_BATCH_SIZE` (positive integer). For v1 use `quota_12 = floor(0.7 * N)` and `quota_3 = N - quota_12`. **Rounding for sizes other than 20 is a proposed convention requiring confirmation.**

1. Build eligible cards from current content and progress. Vocabulary is always eligible. Generated grammar cards require base-vocabulary score 3 and at least two distinct options in their nominal or verb profile.
2. From score 1–2 cards, select up to `quota_12`.
3. From score 3 cards, select up to `quota_3`.
4. If the result contains fewer than `N` cards, select **once** up to `min(5, N - count)` score-0 cards.
5. **Do not backfill** missing score-1/2 or score-3 allocations from other buckets, except the single score-0 step.
6. Preserve the chosen vocabulary/form mix in the score-0 selection. For its never-practised vocabulary slots, use the best available `frequency_words.frequency_rank`; unranked vocabulary follows ranked vocabulary and ties stay randomized. Do not prioritize word forms or previously practised score-0 cards this way.
7. Never repeat a card within a batch.
8. Within each bucket, order by `last_practiced_at` ascending, with NULL first; break ties randomly.
9. For score-3 selected word-form cards, choose a mastery-weighted exact matching sentence, blank every target occurrence, and include its translations. If no match exists, generate the stored base-word and grammar-label prompt. Score-0–2 cards always use the grammar-label prompt.
10. Generate answer options and shuffle cards and options before returning.

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

- Prompt: score-0–2 cards use the base word plus the stored grammar label, such as `talo — Inessiivi (missä?)` or `tehdä — hän ____`. Score-3 cards use a matching sentence with every target occurrence blanked when one exists.
- English translations: sentence translations for contextual score-3 cards; none for grammar-prompt cards.
- Options: target form plus up to three **distinct** options from its same-profile Kaikki forms; randomize. Exclude the card when this produces fewer than two distinct options.

Contextual prompts reuse their form card's existing mastery score; score 3 remains permanent unless manually reset.

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

For word-form questions, `target_form` is the stable grammar slot key (for example `nominal:elative`), `prompt` contains the base word and grammar cue, and `english_translations` is empty. Option count varies from 2 to 4.

The batch endpoint does **not** create or modify progress, track issued questions, or store queue state.

### `POST /api/practice/sentence-break`

Request `{}`. The endpoint reads the 30 most recently practised current cards
at score 3, resolves both vocabulary cards and word-form cards to their Finnish
surfaces, and returns up to five distinct imported sentences containing one of
those surfaces. It uses weighted random sampling: short sentences with more
mastered tracked families and recent anchor surfaces are favored; one or two
known-but-unmastered families are allowed, while three or more are strongly
deprioritized. Untracked tokens are neutral. It includes ordered English
translations. Stale progress rows are ignored.

```json
{
  "sentences": [
    { "finnish": "Talossa asun.", "english_translations": ["I live in the house."] }
  ]
}
```

The endpoint does not write progress or retain sentence-exposure history.

### `GET /api/content-health`

Returns a read-only audit of the current content database. Query parameters are
`category` (`missing_profiles`, `base_without_sentences`,
`under_supported_forms`, or `untracked_sentences`), `offset`, and a maximum
`limit` of 50. Every response includes summary counts and one paginated finding
category. Findings include a `priority_reason` and are ranked first by focus
requests, then latest practice for the base word, then frequency rank. Untracked
sentences use frequency-list coverage, commonness, and token count. The audit
uses exact case-insensitive matching and is rendered in full by the pipeline's
import report. It reads matching current progress rows only to rank findings;
it never writes progress.

### `POST /api/answers`

Request:

```json
{
  "attempt_id": "client-generated-uuid",
  "card": { "type": "word_form", "base_word": "ruoka", "target_form": "nominal:elative" },
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
The practice UI asks for browser confirmation before sending this request.

## 8. Frontend state and persistence

### Routes

- `/`: home with vocabulary total/mastered, word-form total/mastered, overall percentage and **Start Practicing**.
- `/practice`: current question, queue progress bar, mastery icon, clickable options, immediate grading, confirmed reset mastery after answer, contextual reading breaks, **Next**, and navigation home.

### Queue model

Store locally (e.g. `localStorage` under a versioned key):

```ts
type SavedPracticeState = {
  schemaVersion: 3;
  contentRevision: string;
  queue: QuizQuestion[];
  capacity: number;
  quizzesSinceSentenceBreak: number;
  nextSentenceBreakAt: number;
  sentenceBreak?: { finnish: string; english_translations: string[] }[];
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
- After a randomly selected 3–10 completed quizzes, request a contextual
  reading break. Persist a returned break until its **Next** is clicked; an
  empty or failed response skips the break and schedules another interval.
- Existing schema-version-2 queues migrate with a fresh interval and no
  pending reading break.
- When remaining queue count is **<= 3**, request a new batch and append unique card keys not already in the queue. Prevent concurrent replenishment requests.
- If backend returns zero questions, show a friendly empty-state message and a Retry button rather than an endless request loop.
- A returning learner sees the same unanswered questions, options, and sentence choices. If a card was already answered but Next was not pressed, restore the feedback state rather than resubmitting the answer.
- A normal content import creates a new opaque revision in `content_metadata`; dry runs leave the current content database and revision untouched. On `/practice` load, fetch `/api/content-version` before restoring a queue. If its saved revision is absent or different, clear that queue and generate a new batch. This does not affect progress.

### Progress bar

Define queue capacity as the queue length immediately after the most recent append, and show `remaining / capacity`. On Next it decreases; after append it refills. Persist capacity with the queue to avoid jumping on reload. This is a UI convention to implement the agreed refill behavior; no session-completion screen.

## 9. Local development and configuration

Example `.env`:

```dotenv
QUIZ_BATCH_SIZE=20
CARD_SCORE_COOLDOWN_MINUTES=15
CONTENT_DB_PATH=data/content.sqlite
PROGRESS_DB_PATH=data/progress.sqlite
API_HOST=127.0.0.1
API_PORT=8000
```

Root `npm run dev` launches `uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000` and `vite --host 127.0.0.1` via `concurrently` (or equivalent). Document one-time Python/npm dependency installation in README. Vite proxies `/api` to `http://127.0.0.1:8000`.

If content database is missing, show a clear instruction to run the terminal pipeline rather than crashing without explanation. Backend should initialize progress database without modifying content database.

## 10. Testing requirements

**Pipeline:** exact delimiters, blank/comment lines, malformed-line reporting, multiple files, Kaikki index creation/reuse, canonical and alternative form selection, deduplication/translation merging, dry-run never touching existing content DB, normal-run atomic replacement, progress DB untouched.

**Sentence matcher:** case-insensitive matching, Finnish accented letters, punctuation boundaries, no substring matches, all repeated occurrences blanked, missing matches excluded.

**Mastery:** every transition in the score table, score-3 permanence, reset, persistence across content rebuild, idempotent retries, last-practiced updates.

**Batch selection:** all five example cases above, no redistribution, max five new cards, never-practiced first, least-recently-practiced order, no duplicates within batch, eligibility gates, mixed card types.

**Frontend:** restore exact queue after refresh, refill at <=3, no duplicate cards appended, one answer submission per attempt, Next-only removal, restore answered-but-not-advanced state, fallback on corrupt local state, empty batches, home navigation, progress bar behavior.

## 11. Delivery and scope boundaries

Required: working local pipeline, two databases, FastAPI service, two React routes, tests for core algorithms, `npm run dev`, and short README. No accounts, Docker, cloud hosting, AI generation, grammar teaching, keyboard shortcuts, settings UI, or import button.

## 12. Scale note: thousands of Tatoeba sentences

The content-only `sentence_tokens(token_casefold, sentence_id)` index is populated on every import for recommendations and score-3 contextual reinforcement. It is not a sentence-to-word-form association.

## 13. Open implementation decisions (do not silently invent product behavior)

1. **Non-20 batch rounding:** Proposed `floor(0.7N)` and remainder for score-3 quota; confirm if needed.
2. **Question grading trust:** Local MVP can submit selected/correct option IDs as above; later deployment needs server-verifiable answer integrity.
3. **Queue duplicate exhaustion:** If new batches repeatedly overlap the frontend queue, filter duplicates and allow an undersized queue; avoid infinite retries. The backend does not track frontend queue state.
4. **Sentence import scale:** Start with direct sentence scans; add a token index if Tatoeba corpus size causes unacceptable latency.

These are technical proposals, not changes to the confirmed PRD. All other behavior is governed by the agreed requirements.
