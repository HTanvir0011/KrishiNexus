# KrishiNexus OS

**An edge-to-cloud multi-agent operating system for Bangladeshi smallholder farmers.**
Built for the International AI Builders Congress 2026 · Track: AgriSphere AI → FarmMarket.

A farmer speaks in their own dialect (Rangpuri, Bogura/Varendri, Sylheti, Standard Bangla or Banglish). Four agents grade
the crop, expose the middleman markup, price cold storage against a pooled truck sale, check 72-hour flash-flood risk
and underwrite credit, then reply in spoken Bangla, online or offline at a union kiosk.

| The problem (figures cited from the project brief) | What KrishiNexus does |
|---|---|
| Five tiers of middlemen mark produce up by as much as **116%** (green chili), and a farmer short of cash sells below cost | The ΔΠ circuit breaker blocks a sale below the cost floor when storing or a pooled 5-ton truck pays more, and shows the working |
| Traders and plant owners hold **77.32%** of cold-storage quota, so smallholders can't store and wait | Live quota and tariff lookup, cold-chain arbitrage, and 1-tap escrow to the best buyer (simulated) |
| Haor flash floods destroy whole harvests (about **65%** of Sunamganj's Boro in April 2017), and farmers have no collateral for credit | A 72-hour flood check that reads Sentinel-1 radar through monsoon cloud, and a 300–850 credit score with HMAC-signed quality certificates |

**Try it.** Run `docker compose up --build` ([Quickstart](#quickstart)) and open http://localhost:5173/login. **Live demo: https://tanvir.health** (Render free plan, from `render.yaml`;
it sleeps after 15 minutes without visitors and takes about a minute to wake). Demo password: `krishi2026`.

| Demo account | Role |
|---|---|
| `FARM-RAN-001` | Rahim Mia, potato farmer, Rangpur |
| `COOP-BOG-01` | Shibganj Union Co-op |
| `HIMAGAR-BOG-05` | Shajahanpur Himagar, cold-storage manager (Himagar OS) |
| `BUY-BOG-02` | Bogura Agro Traders, a trader who bids directly on farmers' lots |
| `DRIVER-BOG-01` | Jalal Uddin, 5-ton truck driver |
| `BUY-DHK-01` | Dhaka Fresh DC (buyer) |
| `BANK-UCB-01` | UCB Agri Desk (bank) |
| `JUDGE-01` | Judge: every seat in split-screen |
| `ADMIN-01` | Admin console |

Every demo account uses the password `krishi2026`, or one click on the quick-login cards. This is a demo login, not
production security. On the public site, `ADMIN-01` is the exception: it needs the admin password set on the server
(Render → Environment → `KNX_ADMIN_PASSWORD`); quick login and the demo password don't open it. Logins, account changes
and the heavy AI calls are rate-limited per visitor there, and every response carries the usual security headers.

---

## Contents

- [Team](#team)
- [Project overview](#project-overview)
- [Recent changes](#recent-changes)
- [Trained models](#trained-models)
- [Quickstart](#quickstart)
- [Architecture](#architecture)
- [API at a glance](#api-at-a-glance)
- [Evaluation](#evaluation)
- [Testing](#testing)
- [Repository layout](#repository-layout)
- [What is real and what is simulated](#what-is-real-and-what-is-simulated)
- [Data, consent and field testing](#data-consent-and-field-testing)
- [Contributing, security and license](#contributing-security-and-license)

---

## Team

Team Heat Wave.

| Name | Role |
|---|---|
| Tanvir Hossin | Team Lead |
| Md. Omar Faruk | AI/ML Engineer |
| Md. Abdur Rahman | Full-Stack & Backend Developer |
| Mohammed Mahmud Parvez | Full-Stack Developer |
| Md. Morsalin | Full-Stack & Backend Developer |
| Md Rifat | Advisor: Domain Expert (Network Engineering), USA |

---

## Project overview

| Layer | What it does |
|---|---|
| **FastAPI backend** (`backend/`, port `8000`) | 73 routes (72 HTTP, 1 WebSocket); Pydantic v2 schemas throughout; JSON-RPC 2.0 MCP gateway; live agent trace over WebSocket `/ws/agent-trace` |
| **3 MCP servers, 13 tools** | DAM market & syndicate anomaly (4), Open-Meteo weather + Sentinel-1 SAR flood (5), BCSA cold-storage quota & IoT telemetry (4); HTTP, SSE and stdio transports |
| **CRAG pipeline with intent routing** | PII scrub → HyDE dialect rewrite → intent detection → hybrid BM25 + vector retrieval with RRF and reranking → GraphRAG multi-hop facts → Corrective-RAG grading → live MCP augmentation |
| **LangGraph supervisor + 4 agents** | Vision grading, syndicate bypass (5-ton pooled trucks), cold-chain arbitrage (ΔΠ circuit-breaker), climate credit (SAR flood shield + 300–850 score) |
| **Offline edge node** | Bangla voice pipeline, optical grader with signed certificates, local LLM manager for **Ollama** / llama.cpp / vLLM with automatic fallback when no runtime is reachable |
| **Vite + React + TypeScript frontend** (`frontend/`, port `5173`) | A product overview at `/` with one-click live farmer decisions and live MCP cards; the live OS at `/os` (farmer zero-UI app, co-op command center with a Three.js cold-storage twin, market and bank desk); the `/docs` whitepaper with a 13-tool MCP inspector |
| **Flutter mobile app** (`mobile/`) | Android app (iOS-ready) on the same API and accounts: Bangla voice questions, photo grading, lots and bids, driver jobs with live tracking, bank disputes. See [`mobile/README.md`](mobile/README.md) |
| **Demo login and admin console** | Seeded accounts for six roles (farmer, co-op, buyer, bank, judge, admin), password or quick login, HMAC-signed session tokens; `/admin` manages accounts and demo state |
| **Docker Compose** | Backend and nginx-served frontend; optional `local-llm` profile adds Ollama and pulls the quantised models; optional `data` profile adds PostgreSQL + pgvector, Neo4j, Redis and n8n, loaded with the app's own data |

The system runs end to end with **no paid API keys and no GPU**: every agent has deterministic logic seeded with
Bangladeshi agricultural data (DAM prices, BCSA storage quotas, BARI storage protocols, haor flood history).

---

## Recent changes

Latest (19 November 2026): the Flutter mobile app in `mobile/`, Bangla playback in every browser through `POST /edge/tts`,
and review fixes to photo grading, voice, bids, the bank desk, cold-store incidents and the co-op desk.
The full history is in [`CHANGELOG.md`](CHANGELOG.md).

## Trained models

Trained 8–13 November 2026 (Phase 9).

Five models are trained on Kaggle and measured against targets set before training. The notebooks are in
`training/kaggle/` and the measured reports in `training/runs/`. Full write-ups are in `docs/training-plan.md` §6, §7b, §8, §8b
and §8c. The weights are not in this repository; without them, the app says so and uses its labelled fallback.

| Model | What it does | Measured on held-out test data | In the app |
|---|---|---|---|
| `krishi-bangla-lora-v2`: Qwen2.5-1.5B + QLoRA, Q8_0 GGUF served by Ollama | Bangla advisor: fair offer, store or sell (with the ΔΠ working), flood alert, storage advice, read from the agents' tool results | 888 questions, deployed file: fair offer 0.988, store or sell 1.000, flood alert 0.955 (1.000 on wordings written separately), storage citation 0.800, **missing its 0.90 target**; on a later fresh batch of 600 storage questions worded about each answer's own subject, 0.933 (0.975 on sentences it never trained on) | yes: offline kiosk answers |
| `yolov11n-krishi-bd-v2.1`: two-stage YOLO11, Diamant Potato Dataset (CC BY 4.0) | finds each potato, then segments scab, rot, greening and damage | finder mAP50 0.994 (target 0.90); defect mask mAP50 0.342, **missing 0.50**; grade accuracy 0.764 (target 0.70) | yes: potato photo grading, with a size warning signed into the certificate |
| `krishi-price-v1`: LightGBM, GRU, TCN and an ensemble, on WFP prices | staple price forecasts 1–3 months ahead, plus margin flags | **misses 2 of 3 targets**; it doesn't beat "no change" overall | yes: shown as indicative only |
| `krishi-whisper-bn-v1`: Whisper Small, Common Voice 13 Bengali | Bangla speech-to-text on the device | word error 0.435 (target 0.45); character error 0.229, **missing 0.15**. Both were measured with a 128-token cap that cut long transcripts; the app's own setup scores 0.335 / 0.110 on 300 test clips | yes: offline, the farmer app records speech and the kiosk transcribes it |
| `krishi-dialect-e5-small-v1`: multilingual-e5-small, 840 dialect questions, int8 ONNX | reads the farmer's own words and scores each knowledge document; blended 50/50 into the retrieval ranking | 66 fresh blind questions: top-1 0.591 → 0.955, top-3 0.864 → 0.985; the frozen 66-question probe 0.500 → 0.833. It **missed one pre-registered target**: the curated set's context precision fell to 0.974. The owner switched it on anyway (`docs/training-plan.md` §7b) | yes, when its folder is installed; otherwise retrieval runs as before |

- **Freely worded questions (SFT prompts v5).** 4,800 generated training questions in colloquial Bangla, Rangpuri,
  Bogura, Sylheti, Banglish and English. The test includes 32 wordings written separately, which no model trained on.
  On the same test, the previous model scored 0.414 on flood alerts (1.000 on its own templates). That is the gap v5
  closed.
- **A question router for free-form text.** The router that attaches each question's tool result now reads prices,
  months, rent, rot rates, rain and radar readings in many phrasings. It routes 212 of the 239 held-out-wording test
  questions correctly.

Earlier phases (the frozen blind retrieval probe, the institutional interface, the dialect rewriter and more) are
recorded in [`CHANGELOG.md`](CHANGELOG.md).

---

## Quickstart

### Docker (recommended)

Requires Docker Engine with Compose v2.24 or later.

```bash
git clone https://github.com/HTanvir0011/KrishiNexus.git
cd KrishiNexus
docker compose up --build
```

| URL | What |
|---|---|
| http://localhost:5173 | Product overview with live decision cards (nginx) |
| http://localhost:5173/os | Live OS: split-screen judge mode |
| http://localhost:5173/docs | Live whitepaper, MCP inspector, evals |
| http://localhost:8000/docs | FastAPI OpenAPI reference |

With a local LLM (CPU works; the first start downloads about 6.7 GB of models):

```bash
docker compose --profile local-llm up --build
```

With the data services (PostgreSQL + pgvector on `5432`, Neo4j on `7474`/`7687`, n8n on `5678`, all on `127.0.0.1`;
Redis stays internal):

```bash
docker compose --profile data up --build
```

On the first start, n8n imports the two KrishiNexus cron workflows and tries to switch them on. If it cannot, switch
them on in the n8n editor.

Optional settings:
- `.env` next to `docker-compose.yml` (see `.env.example`): host ports, the Ollama and n8n image tags, and the data-profile passwords (local-demo defaults; set your own for anything else).
- `backend/.env` (see `backend/.env.example`): application settings. Any shared deployment sets `KNX_ENV=production`, its own `KNX_RECEIPT_SIGNING_KEY` and
  `KNX_ADMIN_PASSWORD`; production refuses to start with the public development key.

> A GitHub Actions workflow (`.github/workflows/docker-smoke.yml`) builds the images on a Linux Docker host and starts
> the default stack and then the `data` profile. Both pass its smoke test:
> - The default stack: health, all 13 MCP tools, the 100-case regression suite, the nginx proxy, and state surviving
>   a backend restart.
> - The `data` profile: PostgreSQL + pgvector and Neo4j hold exactly the backend's knowledge chunks and graph, n8n has
>   both cron workflows switched on, and the n8n container reaches the backend endpoint they call.

### Local development

```bash
# backend (Python 3.12+; the Docker image runs 3.14)
cd backend
python -m venv .venv
source .venv/Scripts/activate        # Windows Git Bash; use .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
uvicorn main:app --port 8000

# frontend (Node 20.19+ or 22.12+), in a second terminal
cd frontend
npm ci
npm run dev                           # http://localhost:5173, proxies the API to :8000
```

Smoke test:

```bash
curl http://localhost:8000/mcp/tools
curl -X POST http://localhost:8000/evals/run-regression -H "Content-Type: application/json" -d '{"sample_size": 20}'
```

The first returns `"count": 13`; the second runs 100 cases and should pass all of them.

### Mobile app and hosting

- Flutter app: see [`mobile/README.md`](mobile/README.md) (build, emulator, server setting).
- Hosted demo (Render, or Google Cloud Run): see [`docs/deployment.md`](docs/deployment.md).

---

## Architecture

```text
 farmer voice / text (dialect)                    judge / co-op / bank UI (React, Three.js)
            │                                                   │  REST + /ws/agent-trace
            ▼                                                   ▼
   edge node ─ Bangla STT/TTS, optical grader, Ollama ──►  FastAPI gateway (:8000)
                                                               │
              ┌────────────────────────────────────────────────┼────────────────────────────┐
              ▼                                                ▼                            ▼
   LangGraph supervisor                               CRAG pipeline                  MCP hub (JSON-RPC 2.0)
   pii → rag → vision → syndicate →                   HyDE rewrite + intents →       dam-market (4 tools)
   cold-chain ⇄ review → climate-credit → reply       hybrid retrieval → GraphRAG    agri-weather-sar (5)
                                                      → CRAG grade → MCP augment     coldchain-iot (4)
```

Key equations:

- **Net farmer surplus (circuit-breaker):**
  `ΔΠ = [Q(1−λ_rot)·E[P_future] − Q(C_storage + C_handling) − C_transport_storage] − [Q·P_spot − C_transport_market]`.
  A below-cost spot sale is blocked when ΔΠ > 0 and smallholder quota is open.
- **Shelf life:** Q10 model with λ_rot ∈ [0.012, 0.09].
- **Flood risk:** haor breach logistic over SAR backscatter and 72-hour upstream rain.
- **Disease risk:** VPD from the Tetens equation.

The full contracts are in [`docs/architecture.md`](docs/architecture.md).

---

## API at a glance

| Area | Routes |
|---|---|
| Meta | `GET /`, `GET /health` |
| MCP | `GET /mcp/servers`, `GET /mcp/tools`, `POST /mcp/call`, `POST /mcp` (JSON-RPC, SSE), `POST /mcp/servers/{server_name}` |
| Demo anomalies | `POST /mcp/simulate-anomaly`, `GET /mcp/anomalies`, `DELETE /mcp/anomalies`, `DELETE /mcp/anomalies/{anomaly_id}` |
| RAG | `POST /rag/query`, `POST /rag/graph-traverse`, `GET /rag/stats` |
| Guardrails & optimisation | `POST /guardrails/verify`, `POST /optimization/compress`, `GET /optimization/route` |
| Agents | `POST /agents/orchestrate`, `WS /ws/agent-trace`, `GET /agents/trace-history`, `GET /prompts/registry` |
| Automation | `GET /automation/truck-pools`, `POST /automation/truck-pools/join`, `POST /automation/truck-pools/{pool_id}/transit-check`, `POST /automation/truck-pools/reset`, n8n `POST /automation/n8n/daily-dam-sync`, `POST /automation/n8n/hourly-sar-flood-check`, `GET /automation/n8n/workflows` |
| Market (bids, escrow) | `GET /market/bids`, `POST /market/bids/lock` (simulated escrow), `GET /market/price-monitor` |
| Marketplace (lots, deliveries, disputes) | `GET`/`POST /market/lots`, `POST /market/lots/{lot_id}/bids`, `.../accept`, `.../cancel`, `.../disputes`; `GET /market/deliveries` and `POST /market/deliveries/{lot_id}/claim`, `.../pickup`, `.../temperature`, `.../location`, `.../deliver`; `GET /market/disputes`, `POST /market/disputes/{dispute_id}/resolve`; `GET /market/ledger`; live feed `GET /market/stream` (SSE) and `GET /market/events`; `POST /market/reset` |
| Edge | `POST /edge/voice-interact`, `GET /edge/voice-presets`, `POST /edge/grade-crop`, `POST /edge/verify-certificate`, `POST /edge/tts`, `GET /edge/local-models`, `POST /edge/local-inference`, `GET /edge/lora-dataset` |
| Evals | `GET /evals/metrics`, `POST /evals/run-regression`, `GET /evals/holdout` |
| Feedback | `POST /feedback`; admin only: `GET /auth/admin/feedback` |
| Auth (demo) | `GET /auth/demo-users`, `POST /auth/register`, `POST /auth/login`, `GET /auth/me`; admin only: `/auth/admin/users` (list, create, update, delete, reset), `GET /auth/admin/escrows`, `GET /auth/admin/overview` |

---

## Evaluation

Metrics are **computed live** by `backend/evals/regression_suite.py`; none are hard-coded.

| Metric | Measured | Target |
|---|---|---|
| Faithfulness | 1.00 | 0.94 |
| Answer relevancy | 1.00 | 0.92 |
| Context precision | 1.00 (0.974 with the dialect retriever installed) | 0.95 |
| Context recall | 1.00 | 0.91 |
| MCP JSON-schema validity (22 live calls) | 100% | 99.4% |
| PII redaction recall (12 entities) | 100% | 100% |
| Regression suite (5 categories × 20 seeded cases) | 100/100 | — |

**Blind retrieval probe.** `backend/evals/holdout_probe.py` holds 66 farmer questions written blind to the retrieval
rules (six dialects and surface forms, plus paraphrase, negation and cross-document traps), served at
`GET /evals/holdout`. On 29 October 2026 it read top-1 **0.500** and top-3 **0.848**; with the trained dialect retriever
(13 November 2026) it reads top-1 **0.833** and top-3 **0.970**. The set is frozen: nothing is tuned against it.

These scores come from deterministic token and intent checks plus a rubric judge, not an LLM judge. The labelled RAG
set has 19 questions, so treat the retrieval scores as measured on a small set.

---

## Testing

Self-checks are plain Python scripts that exit non-zero on the first failure. Run them with the backend's virtual
environment:

```bash
cd backend
.venv/Scripts/python -m tests.check_auth           # logins, signed tokens, admin API
.venv/Scripts/python -m tests.check_marketplace    # lots, bids, escrow, deliveries, live feed
.venv/Scripts/python -m tests.check_privacy        # PII vault, scrubbed feedback
.venv/Scripts/python -m tests.check_grader         # photo grading and the "no produce" refusal
.venv/Scripts/python -m tests.check_config         # production settings refuse the development key
cd ..
backend/.venv/Scripts/python deploy/cloudrun/tests/check_serve.py   # hosted server: limits, headers, downloads

cd frontend && npm run build                       # type-check and build the web app
cd mobile && flutter analyze && flutter test       # mobile app
```

CI (`.github/workflows/docker-smoke.yml`) builds the Docker images and runs the smoke test on every change to them.

---

## Repository layout

```text
├── backend/                    FastAPI service (Python)
│   ├── main.py  config.py      app, settings, multi-LLM router
│   ├── auth.py                 demo accounts, login, signed session tokens, admin API
│   ├── market_bids.py          buyer bids and the simulated 1-tap escrow
│   ├── marketplace.py          lots, direct bids, deliveries, disputes, ledger, live feed
│   ├── price_monitor.py        price monitor and margin flags
│   ├── feedback.py             PII-scrubbed advice feedback
│   ├── data_seed.py            seed files for the compose data profile (pgvector SQL, Neo4j Cypher, n8n workflows)
│   ├── agents/                 LangGraph supervisor + 4 agents
│   ├── automation/             durable truck pools, n8n-style jobs
│   ├── edge_node/              voice, optical grader, local LLM manager
│   ├── evals/                  metrics engine, 100-case regression suite, 66-question blind holdout
│   ├── guardrails/             PII scrubber, financial circuit-breaker
│   ├── mcp_servers/            3 MCP servers + JSON-RPC hub
│   ├── optimization/           token compressor
│   ├── prompts/                XML prompt registry + optimiser
│   ├── rag/                    lexicon, knowledge seed, hybrid retriever, GraphRAG, CRAG pipeline
│   ├── schemas/                Pydantic models shared by the routes
│   ├── tests/                  self-check scripts (see Testing)
│   └── requirements.txt / .lock   minimum versions for local installs / pinned versions for Docker
├── frontend/                   Vite + React + TypeScript web app
│   ├── src/                    story/ (overview), os/ (live OS), admin/, pages/, components/, api/, state/, data/, lib/
│   ├── public/                 icons, team photos, videos, and the Android APKs in download/
│   ├── scripts/prerender.mjs   static team and guide pages for search engines
│   └── nginx.conf  Dockerfile  production serving + API/WebSocket proxy
├── mobile/                     Flutter app (Android, iOS-ready); see mobile/README.md
├── training/                   data preparation, Kaggle notebooks (kaggle/), measured run reports (runs/)
├── deploy/cloudrun/            one-container hosted demo (Render, Cloud Run): Dockerfile, serve.py, tests/
├── docs/
│   ├── architecture.md         architecture contract: API contracts, formulas, dataset constants
│   ├── deployment.md           hosting on Render or Cloud Run, limits and checks
│   ├── training-plan.md        recipes, split rules, pre-registered targets and measured results for every model
│   ├── field-test-kit.md       plan for the first farmer study
│   └── design/mobile.md        design direction of the mobile app
├── .github/                    CI workflows, issue and PR templates, CODEOWNERS, Dependabot
├── CHANGELOG.md                dated change history
├── CONTRIBUTING.md  SECURITY.md  LICENSE
├── docker-compose.yml          backend + frontend; Ollama under profile local-llm; pgvector, Neo4j, Redis, n8n under profile data
├── render.yaml                 Render Blueprint for the hosted demo
└── .env.example                compose settings (backend settings: backend/.env.example)
```

---

## What is real and what is simulated

Real:
- live Open-Meteo weather;
- all equations and the circuit-breaker;
- hybrid retrieval, GraphRAG and CRAG;
- PII scrubbing;
- HMAC-signed certificates and receipts;
- the durable truck pools and their transit-heat reroute rule;
- the measured metrics;
- the five trained models and their test scores (above).

Simulated or modelled, and labelled as such in the UI and API:
- DAM, BCSA and IoT figures are seeded data, not live feeds;
- buyer bids are modelled from DAM hub prices, not offers from named buyers;
- the bKash / Nagad escrow is simulated: no money moves and no wallet API is called;
- the login is a demo: seeded accounts share a published password and quick login needs none;
- potato grading without the trained YOLO weights (they are not in the repo) falls back to classical CV, labelled `classical-cv`;
- local-LLM telemetry when no runtime is running;
- the fine-tuned Bangla model needs Ollama and its GGUF; without them the kiosk answers from a labelled deterministic fallback;
- agent replies are deterministic; no cloud LLM calls are made.

Figures quoted from the project brief, such as the CPD July 2026 study and partner terms, are attributed as cited.

## Data, consent and field testing

- **Consent:** the farmer app asks before the farmer's own voice or photo is used; recorded samples need none.
- **What is kept:** names, phone, NID, wallet and bank numbers are hidden before any agent reads the text. The hidden
  originals stay in memory for 24 hours at most. Voice and photos are not saved. Wallet numbers are masked before storing.
  The full table is in the whitepaper at `/docs#data`.
- **Online voice** uses the browser's own speech service; offline, the kiosk transcribes with its own Whisper model.
- **Feedback:** every decision can be rated; comments are PII-scrubbed and kept in `backend/.state/feedback.json`.
- **Field testing:** no study with farmers has been run yet. `docs/field-test-kit.md` sets out the first one: five farmers
  and an extension officer in Shibganj, Bogura, with the success bar fixed before the test.
- **Self-checks:** `backend/tests/check_privacy.py` (vault expiry, scrubbed feedback, admin-only summary) and
  `backend/tests/check_auth.py`.

## Contributing, security and license

- How to propose a change: [`CONTRIBUTING.md`](CONTRIBUTING.md).
- How to report a vulnerability, and what the demo deliberately leaves open: [`SECURITY.md`](SECURITY.md).
- Copyright © 2026 Team Heat Wave. All rights reserved; see [`LICENSE`](LICENSE).
