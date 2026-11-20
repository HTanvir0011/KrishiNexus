# Contributing

This is a private team repository. Every push to `main` redeploys https://tanvir.health and resets its demo data, so
changes reach `main` through reviewed pull requests.

## Workflow

1. Create a branch from `main`: `feature/<short-name>`, `fix/<short-name>`, `docs/<short-name>` or `chore/<short-name>`.
2. Keep each pull request to one change, and fill in the pull-request template, including what you tested.
3. Run the checks for the parts you touched (below). CI builds the Docker images and runs the smoke test.
4. A team member reviews; the team lead merges. Put `[skip render]` in the message of a commit that should not
   redeploy the hosted demo (documentation only, for example).

## Commit messages

Write the subject in the imperative, about 70 characters at most ("Add driver location throttle"), and explain the
reason in the body when the diff does not show it. Update `CHANGELOG.md` for any change a user would notice.

## Checks

| Part | Command |
|---|---|
| Backend | from `backend/`: `python -m tests.check_auth`, `python -m tests.check_marketplace`, `python -m tests.check_privacy`, `python -m tests.check_grader`, `python -m tests.check_config` |
| Hosted server | from the repository root: `backend/.venv/Scripts/python deploy/cloudrun/tests/check_serve.py` |
| Frontend | from `frontend/`: `npm run build` (type-check and build) |
| Mobile | from `mobile/`: `flutter analyze` and `flutter test` |
| Dependencies | `npm audit` in `frontend/`, `pip-audit -r backend/requirements.lock` |

## Ground rules

- `docs/architecture.md` is the architecture contract: API shapes, formulas and dataset constants. Change it in the same pull
  request as the code it describes.
- Never commit secrets, `.env` files, trained model weights (`backend/models/`) or personal data. Report security
  problems as described in `SECURITY.md`.
- Never hard-code an evaluation number in the app; scores come from the evaluation code or the run reports in
  `training/runs/`.
