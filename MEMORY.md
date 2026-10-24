# MEMORY.md — KrishiNexus OS Live State & Handover

**Last updated:** 2026-10-24 (BDT) · **Status:** every file in the target tree is built. The Phase 8 institutional UI (daylight Design System v2: overview at `/`, live OS at `/os`, whitepaper at `/docs`) replaced the Phase 7 scroll story and is published to GitHub `HTanvir0011/KrishiNexus` (2026-10-24). Docker files are statically validated but not yet run on a Docker host · **Next:** run `docker compose up --build` on a machine with Docker

> Update this file at the end of every phase: tick checkboxes, record what was verified and how, and append a
> `Session Handover Log` entry naming the exact next file. Architecture, contracts and formulas live in `AGENTS.md`.
> `memory-graph.jsonl` is the same knowledge as a graph (MCP memory-server format); update its Phase, Metric, Next steps
> and Repository entities in the same pass.

---

## 1. Resume in five minutes

1. Read `AGENTS.md` (contract) then this file (state).
2. Start the backend: `cd backend && .venv/Scripts/python -m uvicorn main:app --port 8000`
3. Start the frontend: `npm --prefix frontend run dev` → open `http://localhost:5173`: the story at `/`, the live OS at
   `/os` (judge mode; `/os/field`, `/os/coop`, `/os/market`), the whitepaper at `/docs`.
   - If port 8000 is taken (on the dev PC `claude-science.exe serve` holds it), run the backend on another port and set
     `KNX_BACKEND_URL` for Vite. In the desktop app the preview tool moves `krishinexus-backend` to a free port (8002
     here), and `krishinexus-frontend-8002` serves the site on 5175 against it.
4. Smoke test:
   - `curl http://localhost:8000/mcp/tools` → `count: 13`
   - `curl -X POST http://localhost:8000/evals/run-regression -H "Content-Type: application/json" -d '{"sample_size": 20}'` → 100 cases, 100% PASS
5. Reset demo state if needed: `POST /automation/truck-pools/reset` (or delete `backend/.state/`), `DELETE /mcp/anomalies`.
6. Docker alternative (needs Docker Engine + Compose v2.24 or later for the optional `env_file`):
   - `docker compose up --build` → `http://localhost:5173` (nginx) and `http://localhost:8000` (API)
   - `docker compose --profile local-llm up --build` → also Ollama on `11434`, plus a one-shot pull of about 6.7 GB of models
   - In Docker, truck pools live in the named volume `backend-state`; `docker compose down -v` resets them.

## 2. Environment snapshot

| Item | Value |
|---|---|
| Repo root | `C:\Users\Asus\Downloads\congress\Claude\krishinexus-os`, inside the git repo `C:\Users\Asus\Downloads\congress\Claude` (branch `main`, one commit `9b190e7`; `origin` is a placeholder URL; 42 `__pycache__` files are tracked). GitHub `HTanvir0011/KrishiNexus` is published from the separate folder `C:\Users\Asus\Downloads\congress\Claude to push`, whose root is this folder's contents plus `README.md`, `assets/` and `.gitignore`. To publish, mirror `backend/` and `frontend/` and copy the root files; never mirror the root, which would delete those three and `.git` |
| Python | 3.14.6, venv `backend/.venv` — fastapi 0.159.1, uvicorn 0.54.0, pydantic 2.14.1, httpx 0.28.1, numpy 2.5.4, langgraph 1.2.16, networkx 3.7, pillow 13.0.0, websockets 16.1.1 |
| Node | 26.7.0 / npm 11.19 — react 19.3, vite 8.3, typescript 7.0, three 0.186, tailwindcss 4.3 (`@tailwindcss/vite`), lucide-react 1.61, `@fontsource-variable/anek-bangla` 5.3, `@fontsource/tiro-bangla` 5.3, dev `@types/node` 24 |
| Ports | backend `8000`, frontend `5173`, WebSocket `/ws/agent-trace`; optional Ollama `11434`, llama.cpp `8080`, vLLM `8001` |
| Launch configs | `C:\Users\Asus\Downloads\congress\Claude\.claude\launch.json`: `krishinexus-backend`, `krishinexus-frontend`, `krishinexus-backend-8010` / `krishinexus-frontend-8010`, `krishinexus-frontend-8002` (5175 → backend 8002) |
| Screenshots | The in-app browser pane is often hidden, which stops `requestAnimationFrame`. Use `puppeteer-core` with Chrome (`C:/Program Files/Google/Chrome/Application/chrome.exe`, `--enable-unsafe-swiftshader`). Edge's launcher exits at once, so puppeteer cannot drive it, and its CLI `--screenshot` returned blank frames for `/#story-*` deep links. |
| Not available on dev machine | Docker (no docker/podman/nerdctl on PATH), Ollama/llama.cpp/vLLM, GPU, LLM API keys |
| Docker images | `python:3.14-slim` (build arg `PYTHON_VERSION`), `node:24-bookworm-slim` (`NODE_VERSION`), `nginx:1.28-alpine`, `ollama/ollama:${OLLAMA_IMAGE_TAG:-latest}` |
| Runtime state | `backend/.state/truck_pools.json` (durable pools); anomalies, reservations, PII vault, trace history are in memory |
| Bangla over curl | Inline Bangla in `curl -d '...'` from Git Bash reaches the server garbled (every intent becomes GENERAL and offer parsing fails). Write the JSON to a UTF-8 file and send it with `--data-binary @file`. |

---

## 3. Phase checklist

### Phase 0 — Spec & memory bank
- [x] `AGENTS.md` (architecture contract) · [x] `CLAUDE.md` (identical mirror) · [x] `MEMORY.md`
- [x] `docker-compose.yml` (services `backend`, `frontend`; `ollama` + `ollama-pull` under profile `local-llm`; volumes
      `backend-state`, `ollama-models`) · [x] `.env.example` (compose overrides) · [x] `backend/Dockerfile`
      · [x] `backend/.dockerignore` · [x] `backend/requirements.lock` · [x] `frontend/Dockerfile` · [x] `frontend/.dockerignore`
      · [x] `frontend/nginx.conf`
- Verified without Docker:
  - [x] compose-spec JSON schema: 0 errors; a deliberately broken copy is caught.
  - [x] cross-references (build contexts, `COPY` sources, build args, named volumes, healthcheck dependencies).
  - [x] Linux CPython 3.14 x86_64 wheels exist for all 48 pinned packages.
  - [x] nginx config parses with crossplane (context and argument checks).
  - [x] nginx covers all 10 Vite prefixes and all 22 backend paths in `frontend/src`.
  - [x] lockfile has the Linux native bindings (rolldown, Tailwind oxide, lightningcss, TypeScript 7).
  - [x] backend run with the container's `CMD` flags and `KNX_OLLAMA_HOST=http://ollama:11434`: HEALTHCHECK exits 0; `/edge/local-models` reports all runtimes unreachable in 2.1 s.
  - [x] `npm run build` with `VITE_API_BASE` unset.
- [ ] **Not yet run:** `docker compose build` / `up`, nginx proxying at runtime (SSE, `/ws` upgrade, `/api` rewrite), the
      Ollama profile and the model pull, and the non-root write to the `backend-state` volume.

### Phase 1 — Backend foundation & 3 MCP servers (13 tools)
- [x] `backend/requirements.txt` · [x] `backend/.env.example` · [x] `backend/config.py` · [x] `backend/main.py`
- [x] `schemas/__init__.py` · [x] `schemas/mcp_models.py` (13 `*Input` + 13 `*Output`, `JsonRpcRequest`, `JsonRpcResponse`,
      `ToolCallParams`, `McpToolDescriptor`, `McpServerDescriptor`, `McpToolsListing`, `PowerCutAnomalyRequest`,
      `FlashFloodAnomalyRequest`, `SimulateAnomalyRequest` (Annotated union on `anomaly_type`), `SimulateAnomalyResponse`,
      `ActiveAnomalyView`, `TierValueCapture`, `MarketingCostLine`)
- [x] `mcp_servers/__init__.py` · [x] `base.py` · [x] `bd_geo.py` · [x] `anomaly_state.py` · [x] `registry.py`
- [x] `mcp_servers/dam_market_mcp.py` · [x] `agri_weather_sar_mcp.py` · [x] `coldchain_iot_mcp.py`
- Verified: [x] `GET /mcp/tools` → 13 · [x] `GET /mcp/servers` → 3 with transports · [x] `POST /mcp/call`
  (`detect_syndicate_markup_anomaly` Green Chili/Bogura → 123% CRITICAL; `get_current_weather` Sunamganj → live Open-Meteo)
  · [x] JSON-RPC errors −32700/−32601/−32602, notification → 202 · [x] SSE response · [x] stdio transport
  · [x] `POST /mcp/simulate-anomaly` (power cut + flash flood) · [x] `GET/DELETE /mcp/anomalies`

### Phase 2 — GraphRAG, CRAG, token optimisation, guardrails
- [x] `config.py` `ModelRouter` (`TaskType`, `ModelTier`, `ModelSpec`, `RoutingDecision`, `MODEL_CATALOG`)
- [x] `guardrails/pii_scrubber.py` (`ScrubbedEntity`, `ScrubResult`, `PIIVault`) · [x] `guardrails/financial_circuit.py`
      (`ArbitrageCheckInput`, `ArbitrageCheckResult`, `MicroCreditOffer`, `DosageCheckInput`, `DosageCheckResult`)
- [x] `optimization/token_compressor.py` (`CompressionResult`, `ModelSaving`, `DedupResult`, `CachedMessages`, `MemoryState`, `RollingSummaryMemory`)
- [x] `rag/lexicon.py` · [x] `rag/knowledge_seed.py` · [x] `rag/hybrid_retriever.py` (`RetrievedChunk`)
      · [x] `rag/graph_rag.py` (`GraphTraversalResult`) · [x] `rag/crag_pipeline.py` (`DialectRewrite`, `CragReport`, `RagQueryResult`)
- [x] `schemas/api_models.py` (`RagQueryRequest`, `GraphTraverseRequest`, `CompressRequest`, `CompressResponse`,
      `GuardrailVerifyRequest`, `GuardrailVerifyResponse`)
- Verified: [x] `POST /rag/query` (spec Bangla query → CRAG CORRECT 0.87, BARI 48–50°F rule) · [x] `POST /guardrails/verify`
  (NID/phone/bKash redacted; ΔΠ Tk 274,150; BLOCK_SPOT_SALE) · [x] `POST /optimization/compress` · [x] `POST /rag/graph-traverse`
  · [x] `GET /optimization/route` · [x] `GET /rag/stats`

### Phase 3 — LangGraph supervisor, 4 agents, prompts, automation
- [x] `prompts/prompt_registry.py` (`PromptVersion`, `PromptMetrics`, `OptimizationReport`, `RegistryListing`, 5 contracts)
- [x] `agents/state.py` (`KrishiAgentState`, `AgentTraceEvent`, `DigitalQualityCertificate`, `HarvestMetrics`,
      `SyndicateBypassPlan`, `PoolMatch`, `ColdChainArbitragePlan`, `StorageFacilityChoice`, `ClimateCreditReport`,
      `ScoreComponent`, `RagSummary`) · [x] `agents/tracing.py`
- [x] `vision_grading_agent.py` · [x] `syndicate_bypass_agent.py` · [x] `coldchain_arbitrage_agent.py`
      · [x] `climate_credit_agent.py` · [x] `supervisor.py` (`OrchestrateRequest`, `OrchestrateResponse`)
- [x] `automation/workflows.py` (`PoolView`, `PoolLot`, `JoinPoolRequest`, `JoinPoolResult`, `Dispatch`, `WorkflowEvent`,
      `DamSyncReport`, `SarFloodReport`, `SarFloodCheckRequest`)
- Verified: [x] `POST /agents/orchestrate` (FARM-BOG-104 spec request, 9 nodes, 31 events) · [x] `WS /ws/agent-trace`
  (31 live events to a pre-subscribed client) · [x] `POST /automation/truck-pools/join` (POOL-BOGURA-01 4,600 → 5,000 kg,
  DISPATCHED, escrow locked) · [x] `GET /prompts/registry` · [x] both n8n jobs · [x] pool persistence across restart
  · [~] re-plan loop: unit-tested only (October data never chooses storage)

### Phase 4 — Rural edge node
- [x] `edge_node/optical_grader.py` (`GradeCropRequest`, `GradeCropResult`, `BoundingBox`, `GradingMetrics`,
      `DigitalCertificate`, `VerifyCertificateRequest`, `CertificateVerification`)
- [x] `edge_node/bangla_voice.py` (`VoicePreset`, `TranscriptionResult`, `VoiceEntities`, `VoiceScript`)
- [x] `edge_node/ollama_local.py` (`LocalInferenceRequest`, `LocalInferenceResult`, `LocalModelsReport`, `LoraAdapterSpec`,
      `SftExample`, `DatasetStats`)
- [x] Supervisor wiring: `VoiceInteractRequest`, `VoiceInteractResponse`, `offline_mode`, `final_bangla_ssml`
- Verified: [x] `POST /edge/grade-crop` (high_grade_harvest → Grade-A, 11 boxes, 96.2%, rot 0.3%) · [x] real classical-CV
  grading of an uploaded tray photo · [x] `POST /edge/verify-certificate` (tamper detected) · [x] `POST /edge/voice-interact`
  (all 5 presets end to end; offline mode → climatology) · [x] `GET /edge/local-models` · [x] `POST /edge/local-inference`
  (blackout fallback) · [x] `GET /edge/lora-dataset` · [x] audio without Whisper → clear 422

### Phase 5 — React frontend & split-screen judge mode
- [x] `frontend/package.json` · [x] `tsconfig.json` · [x] `vite.config.ts` · [x] `index.html` · [x] `.gitignore`
- [x] `src/main.tsx` · [x] `src/index.css` · [x] `src/App.tsx` · [x] `src/api/client.ts` · [x] `src/api/fallback.ts`
      · [x] `src/state/store.ts` · [x] `src/lib/format.ts` · [x] `src/lib/speech.ts`
- [x] `components/ui.tsx` · [x] `OpticalGraderCanvas.tsx` · [x] `AgentTraceVisualizer.tsx` · [x] `TruckPoolMap.tsx` · [x] `ColdStorage3DTwin.tsx`
- [x] `pages/FarmerZeroUIApp.tsx` · [x] `CommandCenter.tsx` · [x] `BuyerBankPortal.tsx`
- Verified in browser (live backend): [x] split-screen renders · [x] voice preset → decision cards + 32 trace events
  · [x] 5 s scan → certificate · [x] power-cut + flash-flood simulations · [x] pool join → DISPATCH LOCKED · [x] bank + docs tabs
  · [x] backend-offline fallback banner · [x] `tsc --noEmit` and `npm run build` pass
  · [x] visual appearance screenshot-reviewed during Phase 7 (headless Chrome)

### Phase 6 — Evaluation & live `/docs`
- [x] `backend/evals/__init__.py` · [x] `backend/evals/regression_suite.py` (`RagasReport`, `MetricValue`, `QuestionScore`,
      `RegressionRequest`, `RegressionReport`, `RegressionCase`, `CategorySummary`, `JudgeScore`)
- [x] `pages/DocsPage.tsx` · [x] `components/docs/ProvenanceSection.tsx` · [x] `McpInspectorSection.tsx` · [x] `DepthMatrixSection.tsx`
      · [x] `EvalsSection.tsx` · [x] `EconomicsSection.tsx` · [x] `lib/mcpExamples.ts` · [x] `/docs` + `#section` routing in `App.tsx`
- [x] Removed `pages/DocsInspector.tsx` (replaced by DocsPage section 2)
- Verified: [x] `POST /evals/run-regression` → 100/100 · [x] `GET /evals/metrics` · [x] `/docs` deep link · [x] live MCP call
  (HTTP 200 + latency) · [x] regression animation (100 rows) · [x] all 6 depth testers · [x] economics sliders · [x] fresh tab: 0 console errors

### Phase 6b — Brief alignment (2026-10-22)
- [x] WFP 62 Cox's Bazar + 4 Kurigram · [x] distress Tk 5–14 · [x] 62.35% = Aratdar share of Bepari marketing cost
      (`MarketingCostLine`, Tk 0 grading) · [x] brief constants seeded (`AGRI-FIN-01` + 7 edited passages, `/docs` cards)
- Verified: [x] regression 100/100 · [x] metrics recomputed (19 questions) · [x] `POST /agents/orchestrate` trace
  · [x] `GET /mcp/tools` output schema · [x] `/docs` + bank portal in browser · [x] `tsc --noEmit` + `npm run build`

### Phase 6c — Retrieval ranking fix (2026-10-22)
- [x] `rag/crag_pipeline.py` (`detect_intents`, `Intent.STORAGE_ACCESS`, `INTENT_CONTEXT`) · [x] `rag/lexicon.py` (জায়গা → space)
- Verified: [x] context precision 1.00 (19 questions) · [x] regression 100/100 · [x] held-out probe 9/10 · [x] `POST /rag/query`
  Step 2 example · [x] `POST /agents/orchestrate` demo · [x] `POST /edge/voice-interact` `munshiganj_cold_storage`
  · [x] `GET /evals/metrics?refresh=true`

### Phase 7 — Immersive website redesign (approved and built 2026-10-24; replaced by Phase 8 the same day)
- Direction in one line: Rahim's own Rangpuri question ("এলা বেচমু না হিমাগারত থুমু?") over a persistent, scroll-driven
  delta landscape; night-paddy green `#0E211A` + one mustard accent `#EDB723`; Tiro Bangla for spoken words, Anek Bangla
  (variable width) for the system. User decisions: story at `/`, OS at `/os`, stylised delta, bilingual headlines,
  procedural imagery.
- [x] Plan: `frontend/design/DESIGN_PLAN.md` (approved; section 10 lists what changed during the build) · `style-tile.html`
- [x] Foundation: self-hosted fonts in `main.tsx` · `index.css` (`@theme` palette remap, `.num` `.wide` `.label` `.voice`
      `.panel` `.card`) · `index.html` (no Google Fonts, theme colour, inline SVG favicon) · `tsconfig.json` (`types: node`)
- [x] Routing: `lib/router.tsx` (`useLocation`, `routeOf`, `navigate`, `Link`; types `Route`, `OsView`) · `App.tsx`
      (lazy `story/StoryPage`, `os/OsPage`, `os/DocsShell`; OS polling only on `/os`) · `lib/summary.ts` (`englishSummary`)
- [x] Shell: `components/shell/TopBar.tsx` (`Wordmark`, overlay mode) · `Alerts.tsx` · `Backdrop.tsx` · `components/MosaicSvg.tsx`
      · `components/gauges.tsx` (`ArcGauge`, `Ring`, `ScoreDial`) · `components/ui.tsx` restyled
- [x] Story: `story/StoryPage.tsx` · `Hero.tsx` · `parts.tsx` (`ChapterHeading`, `SourceNote`, `StoryButton`, `Waveform`,
      `Anchor`) · `data.ts` (`useStoryFacts`, `SourceStatus`, `Sourced<T>`, `Ladder`, `RahimFacts`, `AbdulFacts`,
      `SNAPSHOT_DATE`) · `geo.ts` · `presets.ts` · `story.css` · `landscape/Landscape.ts` (`Landscape`, `CHAPTER_COUNT`,
      `RouteMode`) · `landscape/shaders.ts` · `chapters/` Cold, Road, Answer, Haor, Agents, Dawn
- [x] OS and docs: `os/OsPage.tsx` (judge, field, coop, market views) · `os/DocsShell.tsx` (no Three.js) · existing pages
      and components re-skinned; the cold-storage twin uses the story's quota colours
- [x] Backend: `rag/lexicon.py` crop names also match English plurals (`_contains(..., plural=True)` in `detect_crop`)
- Verified 2026-10-24 against the live backend:
  - [x] `tsc --noEmit` · `npm run build`
  - [x] headless Chrome screenshots (puppeteer-core, SwiftShader WebGL):
    - all 7 chapters at 1440×900, plus the deep links `/#story-cold` and `/#story-road`;
    - interactions: 4 districts, power cut and restore, pooled truck, 2017 flood simulation, agents re-run, a dialect preset, a typed English question;
    - phone 390×844, reduced motion, backend offline (cached snapshot, "Cached demo"), WebGL disabled (mosaic fallback);
    - `/os`, `/os/field`, `/os/coop`, `/os/market` and `/docs`.
  - [x] Console clean except the dev-only StrictMode warning when the trace WebSocket is closed before it opens.
  - [x] RAG metrics all 1.00 over 19 questions (gold doc first 19/19), MCP validity 22/22, PII 12/12, regression 100/100
        after the lexicon change
  - [ ] Not done: a GPU browser on real hardware, a real phone, a screen-reader pass, Lighthouse

### Phase 8 — Institutional UI and product architecture overhaul (built 2026-10-24)
- Direction:
  - daylight-first, high-trust institutional SaaS surface (stated references: Stripe, Flexport, Wise, Linear);
  - alabaster canvas `#F6F8F5`, white cards with `#E2E8F0` hairlines;
  - obsidian `#090D16` only for the agent trace terminal, the cold-storage CAD viewport and the SAR map;
  - emerald `#047857` brand, amber `#D97706` farmer quota/action, rose `#E11D48` danger, sky `#0284C7` cold chain.
  - Full spec in `frontend/design/DESIGN_PLAN.md` §11.
- Figma MCP: connected (Tanvir Hossin's team), but no file or frame was shared, so the tokens come from the written brief.
- [x] Design system:
  - `index.css` rewritten: Tailwind defaults restored, plus `--color-canvas`, `--color-obsidian`, `--shadow-card`, `--shadow-lift`, `.surface`, `.well`, `.num`, `.voice`, and `tabular-nums` on `body`;
  - `components/ui.tsx`: `Badge` (`dark`), `Panel` (`well`), `Button` (`quiet`), new `SourceChip`, `Segmented`, `LiveDot`;
  - `components/gauges.tsx` and `shell/Alerts.tsx` restyled.
- [x] Navigation and state:
  - `components/Navbar.tsx` (status pill, route switcher, বাং/EN, Online/Offline edge, judge CTA);
  - `lib/i18n.ts` (`useCopy`);
  - `store.ts` gained `lang` and `health`;
  - `App.tsx` renders the navbar once, health stores the server and tool counts, and `<html lang>` follows the toggle.
- [x] Overview (`story/`):
  - `StoryPage.tsx` (hero, `HeroMetrics` computed live, bento, pipeline, team footer);
  - `LiveDecisionCard.tsx`, `SyndicateCard.tsx` (`Select`), `QuotaCard.tsx`, `HaorCard.tsx` (`SarMap`), `PipelineSection.tsx`;
  - `pipeline.ts` (`PIPELINE`, `nodeOf`, `timingsFor`), `useLive.ts`;
  - `data.ts` trimmed to adapters and snapshots (`ladderFrom` and `DetectOutput` exported; `Ladder` gained severity, fair markup, excess and grading spend);
  - `presets.ts` without geography.
- [x] Deleted: `story/landscape/*`, `story/chapters/*`, `Hero.tsx`, `parts.tsx`, `story.css`, `geo.ts`, `components/MosaicSvg.tsx`, `shell/TopBar.tsx`, `shell/Backdrop.tsx`. They are in GitHub `11336ad`.
- [x] Live OS:
  - `os/OsPage.tsx`: 12-column judge mode, with sub-tabs;
  - `FarmerZeroUIApp.tsx`: daylight phone, five Tiro Bangla preset pills, mic, decision cards, the truck hero card with "হ্যাঁ, ৫-টন ট্রাকে যুক্ত করুন", and auto-scroll to the decision;
  - `CommandCenter.tsx`: live KPIs, and an edge-mode line driven by the navbar toggle;
  - `ColdStorage3DTwin.tsx`: obsidian CAD viewport, quota colours, telemetry pills;
  - `TruckPoolMap.tsx`: light radar, freight formula, destination;
  - `AgentTraceVisualizer.tsx`: plain-language and raw views;
  - `BuyerBankPortal.tsx`: LTV maths and HMAC verify;
  - `OpticalGraderCanvas.tsx`: light tray, HMAC badge;
  - `api/client.ts`: `health` types `mcp_servers`, new `verifyCertificate(certId)`; `lib/speech.ts` gained `hasBanglaVoice`.
- [x] Whitepaper, by a delegated subagent and reviewed:
  - `pages/DocsPage.tsx`: sticky numbered sidebar, mobile chips, deep-link scroll on mount;
  - `ProvenanceSection.tsx`: MathML formulas, plus a `declare module "react"` MathML typing block;
  - `McpInspectorSection.tsx`: two-column playground;
  - `DepthMatrixSection.tsx`: 110-point rubric framing, never a computed score;
  - `EvalsSection.tsx` restyled;
  - `EconomicsSection.tsx`: ARR composition and farmer-surplus charts.
  - `os/DocsShell.tsx` is a plain container now.
- Verified 2026-10-24:
  - [x] `tsc --noEmit` clean; `npm run build`: `index` 280 kB, `StoryPage` 60 kB (no Three.js on `/`), `DocsShell` 58 kB, `OsPage` 627 kB (Three.js; Vite warns above 500 kB).
  - [x] Headless Chrome: `/`, `/os`, `/os/field`, `/os/coop`, `/os/market`, `/docs` at 1440×900 and 390×844 all have `scrollWidth` equal to the viewport.
  - [x] Overflow found and fixed: panel header actions, trace toggle labels, WFP badge.
  - [x] Live interactions:
    - hero orchestration for Rahim (Faria Tk 12 blocked; Tk 4,800 / 8,298 / 24,764; credit 781) and Abdul (4.7% green, −12.7 dB, credit 764);
    - haor surge (99.7% red, 5 h) and reset;
    - judge-mode preset run with the plain and raw trace;
    - Bangla toggle;
    - MCP inspector, compressor, guardrails and the 100-case run in `/docs`.
  - [x] Backend untouched: metrics 1.00 ×4 over 19 questions (gold first 19/19), MCP validity 22/22, PII 12/12, regression 100/100.
  - [ ] Not done: a real phone, a GPU browser, a screen-reader pass, Lighthouse; Firefox/Safari MathML rendering.

---

## 4. Last measured results (2026-10-22; metrics and regression re-run 2026-10-24 after the lexicon change, unchanged)

| Check | Result |
|---|---|
| Regression suite (seed 20261226, 5 × 20) | **100/100 PASS**; rubric-judge 1.00 on every case (SYND-019 partial gone after the narrative change) |
| Frontend build (Phase 8, 2026-10-24) | `index` 280 kB, `StoryPage` 60 kB (no Three.js on `/`), `DocsShell` 58 kB, `OsPage` 627 kB including Three.js (Vite warns above 500 kB); fonts self-hosted (Anek Bangla Bengali subset 448 kB woff2) |
| Story live run (24 Oct 2026) | Rahim: Faria offer Tk 12, farm gate Tk 36.18, Karwan Bazar retail Tk 77.67, markup 115%, he keeps 46.6%; pooled truck Tk 61.91/kg = Tk 24,764 for 400 kg vs storage Tk 8,298 vs Faria Tk 4,800 (blocked). Rangpur: 4 stores, 35,200 t, 2,045 t open. Abdul: 4.6% GREEN today; the flood simulation (+320 mm upstream) gives 99.7% RED and harvest within 5 h |
| Faithfulness / answer relevancy | 1.00 / 1.00 (targets 0.94 / 0.92) — extractive answers, deterministic checks |
| Context precision / recall | **1.00** / 1.00 over 19 questions (targets 0.95 / 0.91); gold doc ranked first on every question. It was 0.9211 before the intent fix of 2026-10-22. |
| Held-out retrieval probe (10 paraphrases not in the eval set) | top-1 9/10. The "cost" trigger was added after seeing this probe (it was 8/10 before), so the probe is no longer fully held out. The remaining miss: "bank loan … without collateral" ranks `BB-WHR-01` above `AGRI-FIN-01`, because neither retriever handles negation. |
| MCP JSON schema validity | 22/22 live calls = 100% (target 99.4%) |
| PII redaction recall / precision | 12/12 = 100% / 100% |
| Prompt optimiser (v1.0 → v1.2) | supervisor 0.55→0.95, vision 0.44→0.95, syndicate 0.56→0.96, coldchain 0.50→0.95, climate 0.48→0.92 |
| Compression | 168-h weather JSON 8.2–9.0×, numbers preserved; farmer-query context 2.2× |
| Demo farmer FARM-BOG-104 (Bogura, 400 kg Cardinal, Faria Tk 11) | markup 115% CRITICAL; Aratdar takes Tk 8.79/kg = 62.35% of the Bepari's Tk 14.10/kg marketing cost, Tk 0 on grading; pooled B2B Tk 56.69–63.64/kg; ΔΠ vs Faria +Tk 3,882–4,110 → Faria sale BLOCKED; storage loses vs truck in October (−Tk 14–17k); credit 743–782; loan Tk 11,000–15,000 |

Prices are date-dependent (seasonal curves + daily jitter). In October storage is not recommended; the brief's demo
figures (truck Tk 24/kg, storage Tk 48.50/kg net) reproduce only in harvest season (Feb–Apr).

---

## 5. Known gaps & partial implementations

- The Docker stack is statically validated only. Nobody has run it on a Docker host yet (see Phase 0).
  - The Ollama image defaults to `latest`; set `OLLAMA_IMAGE_TAG` to pin it.
  - There is no GPU reservation in compose: Ollama runs on CPU unless a `deploy.resources.reservations.devices` block is added on a GPU host.
  - `KNX_RECEIPT_SIGNING_KEY` must be set in `backend/.env` for any shared deployment (the default is the dev key).
- Agents make **no live LLM calls**: decisions and Bangla replies are deterministic; `ModelRouter` records the model
  that would serve each step. Without API keys every route falls back to local Ollama.
- No local runtime ran: Ollama / llama.cpp / vLLM live paths written but untested; telemetry shown is modelled.
- `krishi-bangla-lora-v1` adapter not trained (3,200-example dataset generated deterministically).
- No trained YOLO weights (`yolov11n-krishi-bd-v2.1` is a label); Gemini Vision not wired; uploaded photos use classical CV.
- Speech-to-text needs `faster-whisper` + `KNX_WHISPER_MODEL` (untested); presets and typed text work.
- Libraries named in the brief but not used: CrewAI, Pydantic-AI, DSPy, RAGAS, LLMLingua, Presidio, Neo4j server,
  n8n instance, Temporal server, BMAD-METHOD. Each is replaced by an in-repo implementation and labelled as such.
- Evaluation uses deterministic token/intent checks and a rubric judge, not an LLM judge; eval set is 19 questions.
- Retrieval is keyword and intent driven: there is no negation handling ("without collateral"), and intent words come from a fixed list
  in `crag_pipeline.INTENT_TRIGGERS`. A paraphrase that uses none of those words falls back to GENERAL. Precision 1.00
  is measured on a 19-question set written by the same team that wrote the rules.
- Brief figures not verifiable from here (CPD July 2026 study, UCB 6%, iFarmer terms) are attributed "as cited in the
  KrishiNexus brief" in the knowledge seed and on `/docs`.
- Bepari cost lines other than the Aratdar's 62.35% (freight 18%, labour 6.5%, wastage 5.25%, bags 4.4%, tolls 3.5%)
  and the Faria 20% / Bepari 70% cost-ratio split are modelled, not cited.
- Frontend: pages are code-split; Three.js lives only in the `OsPage` chunk (627 kB). Lazy-loading
  `ColdStorage3DTwin` would let the OS paint before Three.js arrives.
- Phase 8 UI, reviewed only in headless Chrome:
  - The language toggle covers the navbar, the overview, the OS headings and the farmer phone; the whitepaper and the
    OS panel internals stay English.
  - The overview's haor card runs Abdul's full voice preset on load to get today's simulated SAR scene (about 2 s).
  - The hero card runs the regression suite on every load to fill the "100/100" pill (about 0.3 s).
  - The haor card's surge, and the OS twin's simulations, inject backend anomalies that every viewer sees.
    "Today" / "Reset" clears all anomalies.
  - The plain-language trace sentences are written by the frontend from the final agent state. The raw
    `payload_summary` text from the backend is unchanged and still shows Python reprs in the raw view.
  - Listening needs a Bangla voice on the device; without one the UI says so.
  - Snapshots in `story/data.ts` are dated 24 Oct 2026; refresh them if backend outputs change.
  - The pipeline shows nine nodes although the brief said ten; there are nine working LangGraph nodes.
- Model-card specs (layers, GGUF sizes) and DeepSeek/Gemini prices are from memory; Claude prices come from the
  claude-api reference (Sonnet 5.5 `claude-sonnet-5-5`, $2/$10 per MTok).

## 6. Spec deltas vs the master prompt

| # | Master prompt | Build now | Status |
|---|---|---|---|
| 1 | 66 WFP centres = 62 Cox's Bazar + 4 Kurigram | `dam_market_mcp.WFP_CENTRES_BY_DISTRICT` = 62 / 4; seed text and bank-portal badge say so | [x] resolved 2026-10-22 |
| 2 | Aratdars extract 62.35% of Bepari marketing cost, spend Tk 0 on grading | `DetectSyndicateMarkupAnomalyOutput.aratdar_share_of_bepari_marketing_cost_pct` (62.35), `aratdar_take_tk_per_kg`, `aratdar_grading_spend_tk_per_kg` (0), `bepari_marketing_cost_breakdown: list[MarketingCostLine]`; Aratdar ladder share now derived from the Bepari's cost (34.92% of primary margin, was a fixed 62.35%). Old field `aratdar_share_of_primary_margin_pct` removed from the tool, `SyndicateBypassPlan` and the frontend types | [x] resolved 2026-10-22 |
| 3 | Distress price Tk 5–14/kg | regression samples Tk 5–14 (`DISTRESS_SPOT_RANGE_TK`); seed, prompt and tool docstring say Tk 5–14; LoRA dataset spot range starts at Tk 5. Seasonal curve trough stays Tk 11–12 (national average inside the range) | [x] resolved 2026-10-22 |
| 4 | Pineapple 27%, mango 24%; 25–43.5%; $430M; 300–393 plants; 12–13M vs 2.7–3.27M MT; Tk 4–5.50 → 8.00–9.50 (100% hike); Thakurgaon Tk 19–20; 2–9% internal rot; SAR 2× vs manual surveys and Landsat; CPD July 2026; food 59% of CPI; sorting + grading + MAP +32%; iFarmer; UCB 6% | all added to `knowledge_seed.py` (7 passages edited, new `AGRI-FIN-01`) and `ProvenanceSection.tsx`; 3 eval questions added | [x] resolved 2026-10-22 |
| 5 | "RAGAS metrics (0.94 faithfulness)" | metrics computed live; targets shown alongside | kept (integrity rule) |
| 6 | Tailwind via `tailwindcss init`; Python 3.12 | Tailwind v4 Vite plugin; Python 3.14 venv | no change needed |

Files beyond the brief's tree (keep): `mcp_servers/base.py`, `bd_geo.py`, `anomaly_state.py`, `schemas/api_models.py`,
`rag/lexicon.py`, `agents/tracing.py`, `.env.example`, `frontend/src/api/fallback.ts`, `state/store.ts`, `lib/*`,
`components/ui.tsx`, `components/docs/*`, and the redesign: `frontend/design/*`, `src/story/*`, `src/os/*`,
`components/shell/Alerts.tsx`, `components/Navbar.tsx`, `components/gauges.tsx`, `lib/i18n.ts`.

---

## 7. Session Handover Log

### 2026-10-22 · Step 1 — Backend foundation & MCP servers
- **Built:** settings, schemas for 13 tools, MCP base/dispatcher/stdio, Bangladesh geography, anomaly store, 3 servers, gateway, FastAPI app.
- **Tested:** curl over HTTP — tool listing, live calls (markup 123% CRITICAL; live Open-Meteo), JSON-RPC error codes, SSE, stdio, anomaly injection.
- **Fixes:** Bangla alert capped at 99%; single-chamber power cut no longer marks whole facility OUTAGE.
- **Next file:** `config.py` ModelRouter (Step 2).

### 2026-10-22 · Step 2 — GraphRAG, CRAG, token optimisation, guardrails
- **Built:** model router, PII scrubber + vault, ΔΠ/DAE circuit-breaker, token optimiser, Bangla lexicon, 17-doc knowledge seed, hybrid retriever, GraphRAG, HyDE + CRAG pipeline, REST endpoints.
- **Tested:** the three Step 2 curls; dialect queries (Rangpuri, Sylheti, Banglish); 168-h JSON 8.2× compression with numbers preserved.
- **Fixes:** bank "a/c no" pattern; number regex comma bug; crop-aware answer selection; dialect → home-district prior.
- **Next file:** `prompts/prompt_registry.py` (Step 3).

### 2026-10-22 · Step 3 — LangGraph supervisor & agents
- **Built:** XML prompt registry + optimiser, agent state, trace broadcaster, 4 agents, LangGraph supervisor with re-plan loop, durable truck pools, n8n jobs, endpoints + WebSocket.
- **Tested:** orchestration of the spec request (9 nodes, 31 events, no errors), live WebSocket stream, pool join/dispatch/persistence, n8n jobs.
- **Next file:** `edge_node/optical_grader.py` (Step 4).

### 2026-10-22 · Step 4 — Rural edge node
- **Built:** optical grader (sweep simulation, classical CV, optional YOLO, signed certificates), Bangla dialect voice pipeline with SSML, local LLM manager + LoRA dataset, supervisor `voice_interact`, network-blackout ContextVar.
- **Tested:** grade-crop, verify-certificate, voice-interact for all presets (online + offline), local models/inference, LoRA dataset.
- **Next file:** `frontend/package.json` (Step 5).

### 2026-10-22 · Step 5 — Frontend
- **Built:** Vite + React + Tailwind v4 + Three.js app, typed client with offline fallbacks, global store, grader canvas, trace visualizer, pool radar, 3D twin, farmer app, command center, bank portal; `PoolView.lots` added to backend.
- **Tested:** all four Step 5 flows in the in-app browser against the live backend, plus the offline fallback; type-check and build.
- **Next file:** `backend/evals/regression_suite.py` (Step 6).

### 2026-10-22 · Step 6 — Evaluation & /docs
- **Built:** measured metrics engine, 100-case seeded regression suite with rubric judge, `/evals` endpoints, `/docs` portal with 5 sections and URL routing.
- **Tested:** Step 6 curl (100/100); `/docs` deep link, live MCP call, regression animation, depth testers, sliders; fresh tab 0 console errors.
- **Fixes:** added `/evals` to the Vite proxy; rubric criteria corrected; lexicon gained quota/trader/rent terms.
- **Next file:** memory bank.

### 2026-10-22 · Memory bank (this session)
- **Built:** `AGENTS.md` rewritten as the architecture contract (tree as built, MCP + REST contracts, constants, formulas, conventions); `CLAUDE.md` identical mirror; this `MEMORY.md`.
- **Tested:** directory tree cross-checked against the filesystem; route table against `main.py` decorators; model names against source.
- **Next file:** `docker-compose.yml` — services `backend` (Python 3.12+ image, `uvicorn main:app --host 0.0.0.0 --port 8000`, volume for `backend/.state`, `.env`) and `frontend` (Vite build served with SPA fallback for `/docs`, proxying API prefixes and `/ws` to `backend`); optional `ollama` service on `11434`. Needs a machine with Docker to verify. Alternatively resolve the spec deltas in section 6 first.

### 2026-10-22 · Brief alignment (spec deltas 1–4)
- **Built:**
  - `dam_market_mcp.py`: WFP 62/4; value chain re-derived so the Aratdar takes 62.35% of the Bepari's marketing cost with Tk 0 grading spend; new `BEPARI_OWN_COST_LINES`; tool output and narrative itemise the cost.
  - `schemas/mcp_models.py`: `MarketingCostLine` plus 5 new or renamed output fields.
  - `agents/state.py` and `syndicate_bypass_agent.py`: plan carries the take, share and grading spend; the trace line quotes them.
  - `regression_suite.py`: distress range Tk 5–14; syndicate cases check share = 62.35, take = 0.6235 × cost, cost lines sum to the total and grading = 0; 3 new RAG questions.
  - `knowledge_seed.py`: brief constants added and new `AGRI-FIN-01` passage.
  - `prompt_registry.py`, `ollama_local.py`, `client.ts`, `fallback.ts`, `ProvenanceSection.tsx`, `DepthMatrixSection.tsx`, `BuyerBankPortal.tsx`.
  - `AGENTS.md` §7.2 and §8 updated; `CLAUDE.md` re-mirrored.
- **Tested:**
  - Regression 100/100 in-process; metrics recomputed (precision 0.9211 over 19 questions; original 16 unchanged at 0.9375).
  - `GET /mcp/tools` = 13 with the new output schema.
  - `POST /agents/orchestrate` for FARM-BOG-104: no errors; trace "Aratdar takes Tk 8.79/kg = 62.35% of Bepari marketing cost, Tk 0 on grading"; B2B Tk 63.64/kg.
  - Browser: `/docs` provenance cards and the bank-portal WFP badge render with 0 console errors.
  - `tsc --noEmit` and `npm run build` pass.
- **Next file:** `docker-compose.yml` (unchanged).

### 2026-10-22 · Retrieval ranking fix (cold-storage questions)
- **Root cause:** the ranker was fine; the query rewriter was wrong.
  - Any mention of "cold storage" became a STORAGE_CONDITIONS intent. Its formal query and HyDE passage then asked about temperature and humidity, so `BARI-POT-STORE-01` won.
  - Loan, quota and tariff questions had no matching intent.
  - English questions were mostly GENERAL, because intents came only from the Bangla/Banglish lexicon.
- **Built:**
  - `rag/crag_pipeline.py`:
    - new `detect_intents()`: lexicon concepts plus the question's English words, with pre-/post-/after-harvest removed.
    - STORAGE_CONDITIONS now needs a condition word.
    - new `Intent.STORAGE_ACCESS`, gated on storage context via `INTENT_CONTEXT`, with its own formal query, HyDE passage and evidence.
    - the CREDIT query and HyDE passage now cover collateral-free loans.
    - `query_cold_storage_quota` augmentation and the "Capacity:" answer line now serve both storage intents.
  - `rag/lexicon.py`: জায়গা → `space`.
  - The hybrid retriever and reranker are unchanged.
- **Tested:**
  - Intent snapshot over 19 eval questions, 5 voice presets and the demo query: the demo and 4 presets keep their old intents; `munshiganj_cold_storage` moves to STORAGE_ACCESS + SELLING_CHANNEL, which matches its question.
  - Metrics: precision 1.00, recall 1.00, faithfulness 1.00, relevancy 1.00 (in-process and live `GET /evals/metrics?refresh=true`).
  - Regression 100/100.
  - Held-out probe 9/10.
  - Live (UTF-8 bodies): Step 2 example query CORRECT 0.877 and still cites the BARI 48–50°F rule; Bangla quota query → `BCSA-QUOTA-01` plus live quota; FARM-BOG-104 orchestration still BLOCKS the Tk 11 Faria sale; `munshiganj_cold_storage` voice preset COMPLETED with no errors.
- **Next file:** `docker-compose.yml`.

### 2026-10-22 · Docker packaging (`docker-compose.yml`)
- **Built:**
  - `docker-compose.yml`: `backend` (:8000, volume `backend-state`, optional `backend/.env`, `KNX_OLLAMA_HOST=http://ollama:11434`) and `frontend` (nginx on host :5173, starts once the backend is healthy). Profile `local-llm` adds `ollama` (:11434, volume `ollama-models`, healthcheck `ollama list`) and the one-shot `ollama-pull` for the two q4_K_M tags the edge node requests.
  - `backend/Dockerfile`: python:3.14-slim, pinned `requirements.lock`, non-root uid 10001, HEALTHCHECK `/health`, uvicorn on 0.0.0.0 with proxy headers.
  - `frontend/Dockerfile`: node:24 build, then nginx:1.28-alpine.
  - `frontend/nginx.conf`: the Vite proxy prefixes plus `openapi.json`, the `/api/` rewrite, the `/ws/` upgrade (1 h timeout), `proxy_buffering off` for MCP SSE, `client_max_body_size 25m`, immutable `/assets/` caching, and an SPA fallback.
  - `.dockerignore` files and a root `.env.example`.
  - AGENTS.md §3 and §4 updated; CLAUDE.md re-mirrored.
- **Tested:** Docker is not installed here, so nothing ran in a container. What was checked:
  - the official compose-spec schema (0 errors; negative test caught 2 schema errors and 3 cross-reference errors);
  - Linux CPython 3.14 wheels for all 48 pinned packages;
  - crossplane parse of `nginx.conf`, plus route coverage of every frontend backend path;
  - lockfile Linux bindings;
  - the backend started with the container's flags and an unresolvable Ollama host (healthcheck exits 0; edge node degrades in 2.1 s);
  - the production build with `VITE_API_BASE` unset.
- **Next:** on a Docker host, run `docker compose up --build`, then:
  - check `http://localhost:5173` live mode, the `/ws` agent trace, `POST /mcp` SSE through nginx, and a pool join that persists across `docker compose restart backend`;
  - optionally run `--profile local-llm` and `POST /edge/local-inference`.
  - After that, the next file is `frontend/src/App.tsx`: lazy-load `CommandCenter` / `ColdStorage3DTwin` to split the 934 kB bundle.

### 2026-10-24 · Immersive redesign: plan for review
- **Built:** `frontend/design/DESIGN_PLAN.md` and `frontend/design/style-tile.html` only; the running app is unchanged.
- **How it was made:** studied curtisdesignr.me, portalsystems.space, vay.io and the AgrixAI shot in the in-app browser; checked fonts with the ui-ux-pro-max data (Anek Bangla: wdth 75–125, wght 100–800, Bengali + Latin) and Google Fonts; confirmed `@fontsource-variable/anek-bangla` and `@fontsource/tiro-bangla` 5.3.0 exist for offline bundling; rendered the tile with headless Edge at 1440 px and 390 px.
- **Next:** wait for the user's review of the plan (section 1 decisions). On approval, start with foundation: tokens in `frontend/src/index.css`, then the self-hosted fonts and routing.

### 2026-10-24 · Immersive redesign built and verified
- **Built:** the Phase 7 file list. In short:
  - foundation: tokens, self-hosted fonts and a history router with lazy pages;
  - the story: one persistent Three.js landscape driven by scroll, 7 chapters on live agent data with a dated offline snapshot;
  - the live OS under `/os` with four views, and the whitepaper in its own chunk.
- **Fixed after the screenshot review:**
  - cold-storage framing per district; the whole road in Rahim's answer;
  - cold-store towers gone before the road;
  - map labels flip at the edge and avoid each other; the pooled-truck label follows the truck;
  - the header shade; on a phone, a two-row header that scrolls away;
  - agent step summaries wrap instead of widening the grid;
  - the twin's quota colours match the story; THREE.Clock removed (deprecated in r186);
  - favicon (the 404 is gone); whitepaper headline figures use `.num`;
  - English plural crop names in `rag/lexicon.py`.
- **Tested:** see the Phase 7 "Verified" list. Screenshots came from a puppeteer-core script in the session scratchpad, not from the repo.
- **Published (user's go-ahead):** copied into `Claude to push`, with the README routes updated (story `/`, judge mode `/os`).
  - Committed as HTanvir0011 <hossin23105101466@diu.edu.bd> with no AI trailers, as the user requires, and pushed to `HTanvir0011/KrishiNexus` `main`.
  - The `Claude` repo itself still has the redesign as uncommitted working-tree changes.
- **Next:**
  - The Docker run from the previous entries.
  - Next file for polish: `frontend/src/story/chapters/AgentsChapter.tsx`, to turn the raw trace summaries into plain sentences.

### 2026-10-24 · Phase 8 institutional UI overhaul
- **Why:** the user rejected the Phase 7 scroll-hijacked 3D delta and the dark "night paddy" palette, and asked for a daylight-first, high-trust institutional SaaS and field OS.
- **Built:** see the Phase 8 checklist.
  - The navbar is shared by every route.
  - `/` is a product overview whose live cards call the real MCP tools and the real orchestration.
  - `/os` is a 12-column workspace.
  - `/docs` is a Stripe-Docs layout with MathML formulas.
  - The whitepaper restyle was delegated to a subagent and reviewed by screenshot.
- **Found on the way:** an earlier, interrupted attempt at this prompt had left `components/gauges.tsx` in Design System v2 colours, and a code restore had put the Phase 7 versions back into `index.css`, `ui.tsx`, `store.ts` and `Alerts.tsx`. No other process was writing, so the work continued from that state.
- **Tested:** see the Phase 8 "Verified" list. Screenshots came from a puppeteer-core script in the session scratchpad.
- **Published (user's go-ahead):** mirrored into `Claude to push` with a Phase 8 README, committed as HTanvir0011 <hossin23105101466@diu.edu.bd> with no AI trailers, and pushed to `HTanvir0011/KrishiNexus` `main`.
  - The mirror deleted the Phase 7 story files from the push repo, matching their removal here.
  - The `Claude` repo itself still holds all of this as uncommitted working-tree changes.
- **Next:**
  - Run the Docker check.
  - Next file for polish: `frontend/src/pages/CommandCenter.tsx`, to lazy-load `ColdStorage3DTwin` so Three.js splits out of the OS chunk.
