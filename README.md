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

## Tests

```bash
npm run test:backend
npm run test:frontend
```
