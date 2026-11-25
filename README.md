# ToistoKone

**A full-stack application built through AI-assisted, specification-driven software development.**

ToistoKone is a local-first Finnish vocabulary and word-form practice application built with React, FastAPI, and SQLite.

The primary goal of this project is to demonstrate my approach to **AI-assisted software engineering**: using OpenAI Codex as a coding agent while retaining human ownership of requirements, architectural decisions, implementation approval, and software quality.

Development follows a structured workflow:

1. Define requirements and acceptance criteria.
2. Have Codex investigate the codebase and propose a solution.
3. Review and approve the implementation plan.
4. Implement and verify changes with automated tests and browser testing.
5. Document the results and maintain a traceable change history.

The repository includes the product specifications, architecture documentation, agent instructions, and completed change records to make this process transparent.

## Tech Stack

- **Frontend:** React, Vite
- **Backend:** Python, FastAPI
- **Database:** SQLite
- **AI Coding Agent:** OpenAI Codex
- **Development Tools:** Context7, Playwright MCP, SQLite MCP

## Development Approach

This project follows a lightweight, spec-driven development workflow inspired by approaches such as GitHub's Spec Kit, combining structured specifications, AI-assisted implementation, human review, and automated verification.

- Translating product requirements into technical specifications
- Designing and implementing a full-stack application
- Directing AI coding agents through structured development workflows
- Reviewing and validating AI-generated implementations
- Debugging and regression testing
- Maintaining documentation throughout iterative development

## One-time setup

Use Python 3.11+ and a current Node.js LTS release.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
npm install
npm --prefix frontend install
cp .env.example .env
```

## Start development

```bash
npm run dev
```

Open `http://127.0.0.1:5173`. The frontend proxies `/api` requests to the local FastAPI server at `127.0.0.1:8000`.

## Import content

Edit `dictionary.txt`, `frequency/fi_50k.txt`, and direct-child `.txt` files
in `sentences/`. Keep the Kaikki Finnish JSONL at
`lexicon/kaikki.org-dictionary-Finnish-words.jsonl`, then build the disposable content
database:

```bash
.venv/bin/python -m backend.pipeline
```

Use `--dry-run` to validate inputs and update only `data/import-report.txt`:

```bash
.venv/bin/python -m backend.pipeline --dry-run
```

The pipeline replaces only `data/content.sqlite` and `data/import-report.txt`. It never modifies `data/progress.sqlite`.

### One-time Tatoeba extraction

To turn the local Tatoeba export into an import-ready sentence source, run this
once:

```bash
.venv/bin/python -m backend.tatoeba_extract
```

It reads `tatoeba/fi_50k.txt` and `tatoeba/finn-eng.txt`, then writes
`sentences/tatoeba-filtered.txt` and `tatoeba/extraction-report.txt`. The
default beginner filter keeps Finnish sentences of at most eight word tokens
with no more than two words outside the 10,000 most frequent listed forms.
Missing frequency forms count as uncommon. Duplicate Finnish sentences are
merged with their distinct English translations. The extractor refuses to
overwrite either output unless `--force` is supplied. It is separate from the
normal import pipeline, so the raw Tatoeba files are no longer needed after you
have verified the generated source file.

### Source formats

Use only the exact separators shown below. Blank lines and lines beginning with `#` are ignored; malformed lines are reported and skipped.

```text
# dictionary.txt
talo - house / home

# frequency/fi_50k.txt
on 4061285
ei 2202943

# sentences/lesson-01.txt
Ruokaa on pöydällä. - Food is on the table.
```

The first pipeline run builds an ignored reusable `data/kaikki-forms.sqlite` index from the Kaikki source; later imports reuse it unless the source changes. Kaikki generates genitive, partitive, plural-genitive, plural-partitive, inessive, elative, illative, adessive, ablative, allative, and nominative-plural cards where applicable; singular nominative is already practised by the vocabulary meaning card. Plural genitive and plural partitive are limited to nouns, adjectives, pronouns/determiners, and numerals, excluding proper names and verb/participle entries. A capitalized entry whose English meaning is identical—for example, `Helsinki - Helsinki`—is forms-only: it has no meaning card and begins form practice from its first usable stage. The six personal pronouns (`minä`, `sinä`, `hän`, `me`, `te`, `he`) also receive accusative cards. Pronouns use separate singular and plural case profiles, so `se` and `ne`, for example, receive only their own forms. Nominal forms unlock in stages: core forms first, then inner local, outer local, and finally ordinary-entry plural genitive/partitive forms; personal-pronoun accusatives join the first stage. It also generates six active affirmative present-indicative and six past-indicative verb cards. After the base verb is mastered, verb cards unlock in four stages: present singular, past singular, present plural, then past plural; mastering two cards in a stage unlocks the next. Direct verb-form prompts label their present (`preesens`) or past (`imperfekti`) tense. Score-3 form cards use a matching blanked sentence and translation when available, otherwise they keep the grammar prompt. The report lists unsupported words and alternate valid forms; it selects the first ordinary single-word form. `frequency/fi_50k.txt` is required: every line must contain one word and a positive frequency count, and duplicate words are rejected. Only direct-child `.txt` files under `sentences/` are imported. Re-running a normal import replaces the disposable content database, so restart `npm run dev` afterward. The app detects that new content revision and refreshes any saved practice queue before showing it; learning history remains in `data/progress.sqlite`, so back it up periodically if it matters to you.

### Word recommendations

The **Word recommendations** page suggests common three-or-more-character
surface forms that occur in the imported sentences beside your existing
dictionary words or generated grammar forms. Suggestions are frequency-first and show
supporting Finnish-English examples. They are review aids only: add accepted
words manually to `dictionary.txt`, then rerun the pipeline. The app does not
infer lemmas, translations, or word-form trees automatically.

### Content health

The import report includes a content-health audit for dictionary entries without
generated grammar forms, base words without sentence support, form cards with
fewer than two supporting sentences, and imported sentences that do not contain
tracked vocabulary or forms. Findings are prioritized by focus requests, recent
practice, frequency, and sentence simplicity. The **Content health** page presents the same
current-content findings in manageable categories; it is read-only and does not
change quizzes or progress.

## Configuration and v1 limits

`.env` sets `QUIZ_BATCH_SIZE` (default `20`), `CARD_SCORE_COOLDOWN_MINUTES` (default `15`), and local content/progress database paths. After a card's score increases, answer attempts continue to be recorded but cannot change that card's score until its cooldown expires. Set `CARD_SCORE_COOLDOWN_MINUTES=0` to disable this delay. ToistoKone is local-only: it has no accounts or sync, and ambiguous Kaikki spellings are reported while the first ordinary candidate is selected. Content is imported from your files; the app does not generate or validate sentences.

## Tests

```bash
npm run test:backend
npm run test:frontend
```
