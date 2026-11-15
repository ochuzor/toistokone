# ToistoKone

ToistoKone is a local-first Finnish vocabulary and word-form practice app.

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

`.env` sets `QUIZ_BATCH_SIZE` (default `20`) and local content/progress database paths. ToistoKone is local-only in v1: it has no accounts or sync, sentence matching is exact whole-word matching, and ambiguous spellings are not resolved. Content is imported from your files; the app does not generate or validate sentences.

## Tests

```bash
npm run test:backend
npm run test:frontend
```
