# Contributing

KrishiNexus is a FastAPI backend (`backend/`), a Vite React frontend (`frontend/`) and a Flutter app (`mobile/`).
Read [`AGENTS.md`](AGENTS.md) first: it is the architecture contract (directory tree, API contracts, formulas,
conventions). [`docs/internal/MEMORY.md`](docs/internal/MEMORY.md) is the live build state.

## Run it locally

Everything in one go, with Docker Compose v2.24 or later:

```bash
docker compose up --build        # http://localhost:5173 (app), http://localhost:8000/docs (API)
```

Or each part on its own. Backend (Python 3.12+):

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate    # Windows Git Bash; .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
uvicorn main:app --port 8000
```

Frontend (Node 20.19+ or 22.12+), in a second terminal. It proxies the API to port 8000:

```bash
cd frontend
npm ci
npm run dev                      # http://localhost:5173
npm run typecheck
npm run build
```

Mobile (see [`mobile/README.md`](mobile/README.md)):

```bash
cd mobile
flutter pub get
flutter run                      # a connected Android phone or emulator
flutter analyze; flutter test
```

Backend self-checks are the `backend/check_*.py` scripts. The regression suite runs through
`POST /evals/run-regression` (see the smoke test in the [README](README.md#local-development)).

## Rules that matter

- Never tune retrieval rules, prompts or training data against the frozen test sets
  (`backend/evals/holdout_probe.py`, the SFT test split).
- Eval numbers come from the measured reports in `training/runs/`. Do not type them into the app.
- A new backend route prefix must be added in the three places listed in `AGENTS.md` section 3.
- Regenerate `backend/requirements.lock` after any dependency change.
- No secrets in commits. Copy `.env.example` to `.env` for local settings.

## Branches and commits

- Branch from `main`: `feature/<short-name>`, `fix/<short-name>`, `docs/<short-name>` or `chore/<short-name>`.
- One logical change per commit. The subject line is short and imperative ("Fix photo grading", "Add the driver
  dashboard"), with no trailing period. Add a body when the reason is not obvious.
- Add a line to `CHANGELOG.md` for anything a user or a judge would notice.

## Pull requests

- Keep the PR to one topic. Fill in the PR template: what, why, how you tested it, screenshots for UI changes.
- Say what you ran: the backend self-checks, `npm run build`, `flutter analyze` and `flutter test`, whichever your
  change touches.
- Update `AGENTS.md` (and `CLAUDE.md`, its identical copy) when you change the architecture, a contract or a constant.
