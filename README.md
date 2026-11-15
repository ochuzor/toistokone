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

## Phase 0 sample input

`dictionary.txt`, `word-forms.txt`, and `sentences/` contain small input examples for the later import pipeline. The pipeline is not implemented yet.

## Tests

```bash
npm run test:backend
npm run test:frontend
```
