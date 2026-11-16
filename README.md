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

Edit `dictionary.txt`, `word-forms.txt`, and direct-child `.txt` files in `sentences/`, then build the disposable content database:

```bash
.venv/bin/python -m backend.pipeline
```

Use `--dry-run` to validate inputs and update only `data/import-report.txt`:

```bash
.venv/bin/python -m backend.pipeline --dry-run
```

The pipeline replaces only `data/content.sqlite` and `data/import-report.txt`. It never modifies `data/progress.sqlite`.

### Source formats

Use only the exact separators shown below. Blank lines and lines beginning with `#` are ignored; malformed lines are reported and skipped.

```text
# dictionary.txt
talo - house / home

# word-forms.txt
ruoka - ruokaa / ruoasta / ruoan

# sentences/lesson-01.txt
Ruokaa on pöydällä. - Food is on the table.
```

Only direct-child `.txt` files under `sentences/` are imported. Re-running a normal import replaces the disposable content database, so restart `npm run dev` afterward. Your learning history remains in `data/progress.sqlite`; back it up periodically if it matters to you.

## Configuration and v1 limits

`.env` sets `QUIZ_BATCH_SIZE` (default `20`), `CARD_SCORE_COOLDOWN_MINUTES` (default `15`), and local content/progress database paths. After a card's score increases, answer attempts continue to be recorded but cannot change that card's score until its cooldown expires. Set `CARD_SCORE_COOLDOWN_MINUTES=0` to disable this delay. For word-form practice, sentences with more mastered tracked vocabulary are favored; words absent from imported vocabulary and forms do not affect that preference. ToistoKone is local-only: it has no accounts or sync, sentence matching is exact whole-word matching, and ambiguous spellings are not resolved. Content is imported from your files; the app does not generate or validate sentences.

## Tests

```bash
npm run test:backend
npm run test:frontend
```
