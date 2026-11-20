# Security policy

## Reporting a vulnerability

Please report security problems privately, not in a public issue:

- GitHub: **Security → Report a vulnerability** on this repository (private advisory), or
- contact the team lead, Tanvir Hossin ([@HTanvir0011](https://github.com/HTanvir0011)).

Include the affected route, page or file, steps to reproduce, and the impact you expect. We aim to reply within
3 working days and to fix confirmed issues before disclosing them.

## Supported versions

| Component | Supported |
|---|---|
| `main` branch and https://tanvir.health | yes |
| Android app, latest build from https://tanvir.health/download/ | yes |
| Older builds and forks | no |

## What the demo deliberately leaves open

KrishiNexus OS is a competition demo. These are design choices, not vulnerabilities:

- **Demo login.** Seeded accounts share a published password and quick login needs none. On a public host
  `KNX_ADMIN_PASSWORD` protects the admin account; quick login and the demo password never open it.
- **Open read routes.** Most read endpoints need no login so judges can explore. Writes, logins and heavy AI calls are
  rate-limited per visitor on the hosted server (`deploy/cloudrun/serve.py`).
- **Simulated money.** Escrow and bKash, Nagad, Rocket or Upay payouts are simulated; no payment API is called.
- **Debug-signed Android APK.** It installs by sideloading; a store release needs a real signing key.

## Secrets and configuration

- Never commit `.env` files, keys or tokens. Only `.env.example` files are tracked, with empty or local-demo values.
- Production (`KNX_ENV=production`, set by the hosted server) refuses to start without its own
  `KNX_RECEIPT_SIGNING_KEY`, and allows no cross-origin browser calls unless `KNX_CORS_ORIGINS` lists them.
- The Docker Compose data services and Ollama bind to `127.0.0.1`; their default passwords are for local use only.
- Dependabot opens weekly update pull requests for npm, pip, pub, Docker and GitHub Actions. Check dependencies by
  hand with `npm audit` (in `frontend/`) and `pip-audit -r backend/requirements.lock`.
