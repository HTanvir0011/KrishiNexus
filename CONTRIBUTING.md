# Contributing

KrishiNexus is a FastAPI backend (`backend/`), a Vite React frontend (`frontend/`) and a Flutter app (`mobile/`).
Read [`docs/architecture.md`](docs/architecture.md) first: it is the architecture contract (directory tree, API
contracts, formulas, conventions).

Every push to `main` redeploys https://tanvir.health and resets its demo data, so changes reach `main` through
reviewed pull requests.

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
```

Mobile (see [`mobile/README.md`](mobile/README.md)):

```bash
cd mobile
flutter pub get
flutter run                      # a connected Android phone or emulator
```

Local settings: copy `.env.example` to `.env` (Compose) and `backend/.env.example` to `backend/.env` (backend).

## Checks

| Part | Command |
|---|---|
| Backend | from `backend/`: `python -m tests.check_auth`, `python -m tests.check_marketplace`, `python -m tests.check_privacy`, `python -m tests.check_grader`, `python -m tests.check_config` |
| Regression suite | `POST /evals/run-regression` (see the smoke test in the [README](README.md#local-development)) |
| Hosted server | from the repository root: `backend/.venv/Scripts/python deploy/cloudrun/tests/check_serve.py` |
| Frontend | from `frontend/`: `npm run typecheck` and `npm run build` |
| Mobile | from `mobile/`: `flutter analyze` and `flutter test` |
| Dependencies | `npm audit` in `frontend/`, `pip-audit -r backend/requirements.lock` |

CI builds the Docker images and runs the smoke test.

## Rules that matter

- Never tune retrieval rules, prompts or training data against the frozen test sets
  (`backend/evals/holdout_probe.py`, the SFT test split).
- Eval numbers come from the measured reports in `training/runs/`. Do not type them into the app.
- A new backend route prefix must be added in the three places listed in `docs/architecture.md` section 3.
- Regenerate `backend/requirements.lock` after any dependency change.
- Never commit secrets, `.env` files, trained model weights (`backend/models/`) or personal data. Report security
  problems as described in [`SECURITY.md`](SECURITY.md).

## Branches and commits

- Branch from `main`: `feature/<short-name>`, `fix/<short-name>`, `docs/<short-name>` or `chore/<short-name>`.
- One logical change per commit. The subject line is short and imperative ("Fix photo grading", "Add the driver
  dashboard"), with no trailing period. Add a body when the reason is not obvious.
- Put `[skip render]` in the message of a commit that should not redeploy the hosted demo (documentation only, for
  example).
- Add a line to `CHANGELOG.md` for anything a user or a judge would notice.

## Pull requests

- Keep the PR to one topic. Fill in the PR template: what, why, how you tested it, screenshots for UI changes.
- Update `docs/architecture.md` when you change the architecture, a contract or a constant.
- A team member reviews; the team lead merges.
