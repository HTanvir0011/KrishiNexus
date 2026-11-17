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

**Try it.** Run `docker compose up --build` ([Quickstart](#quickstart)) and open http://localhost:5173/login. The hosted
demo runs on Render's free plan from `render.yaml`; its link will be added here once it is deployed
(`deploy/cloudrun/DEPLOY.md`).

| Demo account | Role |
|---|---|
| `FARM-RAN-001` | Rahim Mia, potato farmer, Rangpur |
| `COOP-BOG-01` | Shibganj Union Co-op |
| `HIMAGAR-BOG-05` | Shajahanpur Himagar, cold-storage manager (Himagar OS) |
| `BUY-DHK-01` | Dhaka Fresh DC (buyer) |
| `BANK-UCB-01` | UCB Agri Desk (bank) |
| `JUDGE-01` | Judge: every seat in split-screen |
| `ADMIN-01` | Admin console |

Every demo account uses the password `krishi2026`, or one click on the quick-login cards. This is a demo login, not
production security.

![Team Roster](assets/team_animation.svg)

---

## Contents

- [Team](#team)
- [Project overview](#project-overview)
- [Recent changes](#recent-changes)
- [Quickstart](#quickstart)
- [Architecture](#architecture)
- [API at a glance](#api-at-a-glance)
- [Evaluation](#evaluation)
- [Repository layout](#repository-layout)
- [What is real and what is simulated](#what-is-real-and-what-is-simulated)
- [Data, consent and field testing](#data-consent-and-field-testing)

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
| **FastAPI backend** (`backend/`, port `8000`) | 51 routes (50 HTTP, 1 WebSocket); Pydantic v2 schemas throughout; JSON-RPC 2.0 MCP gateway; live agent trace over WebSocket `/ws/agent-trace` |
| **3 MCP servers, 13 tools** | DAM market & syndicate anomaly (4), Open-Meteo weather + Sentinel-1 SAR flood (5), BCSA cold-storage quota & IoT telemetry (4); HTTP, SSE and stdio transports |
| **CRAG pipeline with intent routing** | PII scrub → HyDE dialect rewrite → intent detection → hybrid BM25 + vector retrieval with RRF and reranking → GraphRAG multi-hop facts → Corrective-RAG grading → live MCP augmentation |
| **LangGraph supervisor + 4 agents** | Vision grading, syndicate bypass (5-ton pooled trucks), cold-chain arbitrage (ΔΠ circuit-breaker), climate credit (SAR flood shield + 300–850 score) |
| **Offline edge node** | Bangla voice pipeline, optical grader with signed certificates, local LLM manager for **Ollama** / llama.cpp / vLLM with automatic fallback when no runtime is reachable |
| **Vite + React + TypeScript frontend** (`frontend/`, port `5173`) | A product overview at `/` with one-click live farmer decisions and live MCP cards; the live OS at `/os` (farmer zero-UI app, co-op command center with a Three.js cold-storage twin, market and bank desk); the `/docs` whitepaper with a 13-tool MCP inspector |
| **Demo login and admin console** | Seeded accounts for six roles (farmer, co-op, buyer, bank, judge, admin), password or quick login, HMAC-signed session tokens; `/admin` manages accounts and demo state |
| **Docker Compose** | Backend and nginx-served frontend; optional `local-llm` profile adds Ollama and pulls the quantised models; optional `data` profile adds PostgreSQL + pgvector, Neo4j, Redis and n8n, loaded with the app's own data |

The system runs end to end with **no paid API keys and no GPU**: every agent has deterministic logic seeded with
Bangladeshi agricultural data (DAM prices, BCSA storage quotas, BARI storage protocols, haor flood history).

---

## Recent changes

### Himagar OS, cold-storage seat (17 November 2026)

- `/os/himagar` gives a cold-storage manager one facility at a time: who holds the space (traders, plant owners,
  farmers), every chamber's temperature, humidity and rot risk beside the 3D twin, a pooled slot booking that returns an
  HMAC-signed warehouse receipt, and a shelf-life check at the chamber's live reading.
- New role `storage` with the demo account `HIMAGAR-BOG-05`; judges and admins see the seat too.

### Consent, data retention, feedback and the pilot plan (17 November 2026)

- The farmer app asks for consent, in Bangla and English, before the farmer's own voice or photo is used.
- Hidden names and phone numbers now leave the PII vault after 24 hours; nothing personal is written to disk.
- Every decision ends with "Was this advice useful?"; comments are PII-scrubbed, and admins read them at `/admin/feedback`.
- The whitepaper adds per-truck unit economics, a district break-even point and a dated pilot plan (`/docs#economics`),
  and a data, consent and safety section (`/docs#data`).
- `FIELD_TEST_KIT.md` is the plan for the first study with farmers. No study has been run yet.
- `render.yaml` deploys the hosted demo on Render's free plan, with gzipped responses and an optional keep-awake
  workflow (`DEMO_URL`). Deploying it is a dashboard step for the repository owner.

### Demo login and admin console (15 November 2026)

- `/login`: a sign-in form (account ID and password) with one-click quick-login cards, grouped by role.
- `/admin`: an admin console with a sidebar for accounts (add, edit, disable, delete, restore the seeds), escrows and
  overview counts. The last active admin can't be removed.
- Passwords are stored as salted PBKDF2 hashes and never returned by the API. Session tokens are HMAC-signed and last
  12 hours. `backend/check_auth.py` checks forged, tampered and expired tokens.
- `deploy/cloudrun/` packages the frontend and API in one container for a hosted demo, with per-visitor limits on
  writes that every visitor would see.

### Buyer bids, 1-tap escrow, truck reroute and data services (Phase 10, 10 November 2026)

- **Buyer bids** (market seat, `/os/market`).
  - Every buyer for the lot is listed, best net payout first: supermarket DCs, wholesale arats, the 66 WFP centres
    and four new agro-processors. The processors (potato flakes and chips, chili paste, a rice mill) buy grades that
    retail refuses.
  - Net payout is after pooled freight, fees and transit loss. Bids under the crop's production cost are flagged.
  - Bids are modelled from DAM hub prices, not live offers from named buyers.
- **1-tap escrow.**
  - One tap locks the best bid. The amount is held for the farmer's bKash or Nagad wallet and released when the
    delivery is weighed at the buyer's door.
  - The node recomputes the bid itself, a second tap returns the same escrow, and the receipt is HMAC-signed with the
    wallet number masked.
  - **The escrow is simulated:** no money moves and no wallet API is called. A live escrow needs a merchant agreement
    and API credentials.
- **Truck reroute on transit heat** (co-op seat, `/os/coop`).
  - The co-op enters the truck's temperature. If the produce would spoil before arrival (ETA over 75% of its
    remaining shelf life), the truck is sent to the best buyer it still reaches in time, and the escrow is locked
    again there.
  - At 38 °C a potato truck keeps its route; a green-chili truck moves from a 7.2 h buyer to a 2.0 h one.
- **Data services in Compose** (`docker compose --profile data up --build`).
  - PostgreSQL + pgvector receives the 19 knowledge chunks with the vectors the app indexes.
  - Neo4j receives the supply-chain graph.
  - n8n runs the two cron jobs in queue mode on Redis.
  - The app itself still answers from its in-process stores. This profile has not yet run on a Docker host.
- **Training update.**
  - Prompts v6 fixed storage citation (0.911 on the exported model) but store-or-sell verdicts fell to 0.895, so that
    model was not shipped.
  - Prompts v7, where the circuit breaker states whether today's price is below the floor, fixed those verdicts
    (1.000 in every check). But storage citation fell to 0.85–0.89 on 14 unseen sentences, so that model was not
    shipped either.
  - The deployed model is unchanged. All results are in `TRAINING_PLAN.md` §6.

### Trained models (Phase 9 training, 8–13 November 2026)

Five models are trained on Kaggle and measured against targets set before training. The notebooks are in
`training/kaggle/` and the measured reports in `training/runs/`. Full write-ups are in `TRAINING_PLAN.md` §6, §7b, §8, §8b
and §8c. The weights are not in this repository; without them, the app says so and uses its labelled fallback.

| Model | What it does | Measured on held-out test data | In the app |
|---|---|---|---|
| `krishi-bangla-lora-v2`: Qwen2.5-1.5B + QLoRA, Q8_0 GGUF served by Ollama | Bangla advisor: fair offer, store or sell (with the ΔΠ working), flood alert, storage advice, read from the agents' tool results | 888 questions, deployed file: fair offer 0.988, store or sell 1.000, flood alert 0.955 (1.000 on wordings written separately), storage citation 0.800, **missing its 0.90 target**; on a later fresh batch of 600 storage questions worded about each answer's own subject, 0.933 (0.975 on sentences it never trained on) | yes: offline kiosk answers |
| `yolov11n-krishi-bd-v2.1`: two-stage YOLO11, Diamant Potato Dataset (CC BY 4.0) | finds each potato, then segments scab, rot, greening and damage | finder mAP50 0.994 (target 0.90); defect mask mAP50 0.342, **missing 0.50**; grade accuracy 0.764 (target 0.70) | yes: potato photo grading, with a size warning signed into the certificate |
| `krishi-price-v1`: LightGBM, GRU, TCN and an ensemble, on WFP prices | staple price forecasts 1–3 months ahead, plus margin flags | **misses 2 of 3 targets**; it doesn't beat "no change" overall | yes: shown as indicative only |
| `krishi-whisper-bn-v1`: Whisper Small, Common Voice 13 Bengali | Bangla speech-to-text on the device | word error 0.435 (target 0.45); character error 0.229, **missing 0.15**. Both were measured with a 128-token cap that cut long transcripts; the app's own setup scores 0.335 / 0.110 on 300 test clips | yes: offline, the farmer app records speech and the kiosk transcribes it |
| `krishi-dialect-e5-small-v1`: multilingual-e5-small, 840 dialect questions, int8 ONNX | reads the farmer's own words and scores each knowledge document; blended 50/50 into the retrieval ranking | 66 fresh blind questions: top-1 0.591 → 0.955, top-3 0.864 → 0.985; the frozen 66-question probe 0.500 → 0.833. It **missed one pre-registered target**: the curated set's context precision fell to 0.974. The owner switched it on anyway (`TRAINING_PLAN.md` §7b) | yes, when its folder is installed; otherwise retrieval runs as before |

- **Freely worded questions (SFT prompts v5).** 4,800 generated training questions in colloquial Bangla, Rangpuri,
  Bogura, Sylheti, Banglish and English. The test includes 32 wordings written separately, which no model trained on.
  On the same test, the previous model scored 0.414 on flood alerts (1.000 on its own templates). That is the gap v5
  closed.
- **A question router for free-form text.** The router that attaches each question's tool result now reads prices,
  months, rent, rot rates, rain and radar readings in many phrasings. It routes 212 of the 239 held-out-wording test
  questions correctly.

Earlier phases (the frozen blind retrieval probe, the institutional interface, the dialect rewriter and more) are
recorded in [`MEMORY.md`](MEMORY.md).

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
- `backend/.env` (see `backend/.env.example`): application settings. Set `KNX_RECEIPT_SIGNING_KEY` before any shared deployment.

> A GitHub Actions workflow (`.github/workflows/docker-smoke.yml`) builds the images on a Linux Docker host and starts
> the default stack and then the `data` profile. Both pass its smoke test:
> - The default stack: health, all 13 MCP tools, the 100-case regression suite, the nginx proxy, and state surviving
>   a backend restart.
> - The `data` profile: PostgreSQL + pgvector and Neo4j hold exactly the backend's knowledge chunks and graph, n8n has
>   both cron workflows switched on, and the n8n container reaches the backend endpoint they call.

### Local development

```bash
# backend (Python 3.12+)
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

The full contracts are in [`AGENTS.md`](AGENTS.md).

---

## API at a glance

| Area | Routes |
|---|---|
| MCP | `GET /mcp/servers`, `GET /mcp/tools`, `POST /mcp/call`, `POST /mcp` (JSON-RPC, SSE), `POST /mcp/simulate-anomaly` |
| RAG | `POST /rag/query`, `POST /rag/graph-traverse`, `GET /rag/stats` |
| Guardrails & optimisation | `POST /guardrails/verify`, `POST /optimization/compress`, `GET /optimization/route` |
| Agents | `POST /agents/orchestrate`, `WS /ws/agent-trace`, `GET /agents/trace-history`, `GET /prompts/registry` |
| Automation | `GET /automation/truck-pools`, `POST /automation/truck-pools/join`, `POST /automation/truck-pools/{pool_id}/transit-check`, n8n `daily-dam-sync` and `hourly-sar-flood-check` |
| Market | `GET /market/bids`, `POST /market/bids/lock` (simulated escrow), `GET /market/price-monitor` |
| Edge | `POST /edge/voice-interact`, `POST /edge/grade-crop`, `POST /edge/verify-certificate`, `GET /edge/local-models`, `POST /edge/local-inference`, `GET /edge/lora-dataset` |
| Evals | `GET /evals/metrics`, `POST /evals/run-regression`, `GET /evals/holdout` |
| Auth (demo) | `GET /auth/demo-users`, `POST /auth/login`, `GET /auth/me`; admin only: `/auth/admin/users` (list, create, update, delete, reset), `GET /auth/admin/escrows`, `GET /auth/admin/overview` |

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

## Repository layout

```text
├── docker-compose.yml          backend + frontend; ollama under profile local-llm; pgvector, Neo4j, Redis, n8n under profile data
├── AGENTS.md / CLAUDE.md       architecture contract (identical copies)
├── MEMORY.md                   live build state and handover log
├── assets/team_animation.svg   animated team roster
├── backend/
│   ├── main.py  config.py      FastAPI app, settings, multi-LLM router
│   ├── auth.py  check_auth.py  demo accounts, login, signed session tokens, admin API, and its self-check
│   ├── market_bids.py          buyer bids and the simulated 1-tap escrow
│   ├── data_seed.py            seed files for the compose data profile (pgvector SQL, Neo4j Cypher, n8n workflows)
│   ├── mcp_servers/            3 MCP servers + JSON-RPC hub
│   ├── rag/                    lexicon, knowledge seed, hybrid retriever, GraphRAG, CRAG pipeline
│   ├── agents/                 LangGraph supervisor + 4 agents
│   ├── guardrails/             PII scrubber, financial circuit-breaker
│   ├── optimization/           token compressor
│   ├── prompts/                XML prompt registry + optimiser
│   ├── automation/             durable truck pools, n8n-style jobs
│   ├── edge_node/              voice, optical grader, local LLM manager
│   └── evals/                  metrics engine + 100-case regression suite + 66-probe blind holdout
├── training/                   SFT data export (prepare_data.py), Kaggle notebooks (kaggle/), measured run reports (runs/)
├── TRAINING_PLAN.md            recipes, split rules, pre-registered targets and measured results for every model
├── render.yaml                 Render Blueprint for the free hosted demo (one Docker web service)
├── deploy/cloudrun/            one-container hosted demo for Render or Google Cloud Run, with per-visitor write limits
└── frontend/
    ├── nginx.conf  Dockerfile  production serving + API/WebSocket proxy
    ├── design/                 redesign plan and style tile (not part of the build)
    └── src/                    story/ (overview and its live cards), os/ (live OS), admin/ (admin console), pages (incl. login), components, typed API client
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
- **Field testing:** no study with farmers has been run yet. `FIELD_TEST_KIT.md` sets out the first one: five farmers
  and an extension officer in Shibganj, Bogura, with the success bar fixed before the test.
- **Self-checks:** `backend/check_privacy.py` (vault expiry, scrubbed feedback, admin-only summary) and
  `backend/check_auth.py`.
