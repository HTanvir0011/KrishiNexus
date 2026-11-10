# MEMORY.md — KrishiNexus OS Live State & Handover

**Last updated:** 2026-11-10 (BDT)

**Status:**
- Phases 0–10 are built and published to GitHub `HTanvir0011/KrishiNexus` `main`, pushed from the mirror
  `Claude to push` (each push's commit is in the handover log). The local `Claude` repo keeps its changes uncommitted,
  as before.
- Models trained on Kaggle and measured (TRAINING_PLAN §6, §8, §8b, §8c):
  - **Bangla advisor `krishi-bangla-lora-v2`** (prompts v5, freely worded questions) is **deployed**: Ollama
    `krishi-bangla:latest`, Q8_0, `PROMPT_VERSION = 5`.
    - It meets every target except storage citation (0.806 against 0.90).
    - v1 (prompts v4) is kept as `krishi-bangla:v4` and `backend/models/lora/krishi-bangla-v4-q8_0.gguf`.
  - **Potato cascade** run 2 is wired into the grader. Finder 0.99; defect model 0.34 (misses); grade accuracy 0.764.
    It has the size warning and the signed certificate.
  - **`krishi-price-v1`** is wired into the market seat. It misses 2 of 3 targets and is shown as indicative.
  - **Bangla Whisper** `krishi-whisper-bn-v1` is **installed**, and the offline farmer app transcribes speech with it.
    Pre-registered WER 0.435 meets and CER 0.229 misses, but both were measured with a 128-token cap that cut long
    transcripts. The app's path scores WER 0.335 and CER 0.110 on 300 clips.
  - **v3** (prompts v6) fixed storage citation but regressed store-or-sell verdicts, so it was not shipped. **v4**
    (prompts v7, `spot_below_floor` stated) is queued on Kaggle.
- Phase 10 (the developer task list, 2026-11-10) is built:
  - modelled buyer bids, including 4 agro-processors, with a simulated 1-tap bKash/Nagad escrow (`/os/market`);
  - a transit-heat truck reroute (`/os/coop`);
  - compose profile `data`: pgvector, Neo4j, Redis and n8n, seeded from the node's own data.
- The Docker files, including profile `data`, have never run on a Docker host.

**Next:**
1. When kernel v5 (v7 data, adapter `krishi-bangla-lora-v4`) finishes: download only the small reports, check the
   pre-registered v7 targets, record them, and ask the user before the ~1.6 GB download.
2. Run `docker compose up --build` and `docker compose --profile data up --build` on a Docker host.
3. Optional: re-score Whisper on the same 2,000 clips without the 128-token cap (an evaluation fix).
4. A demo rehearsal with a real microphone.

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

### Phase 9 — Datasets, training and honest evaluation (planned and partially shipped 2026-10-29)
- Scope set by the user (ponytail ultra): the plan, the proper splits and the honest evaluations now; **no GPU
  training and zero downloads**. The full recipe, verified by research plus adversarial review, lives in `TRAINING_PLAN.md`.
- [x] SFT split v2 in `edge_node/ollama_local.py` (`_family_split`): train/val/test replaces the leaky every-10th
      split; whole families share one split; OOD holdouts fully out of training (Chittagonian dialect 240,
      holding_months 7 → 117, খালিয়াজুরী haor 33); flood responses now name the haor so identical alerts cannot
      collide across upazilas. `/edge/lora-dataset?split=` now takes train|val|test; `DatasetStats` reports the three
      splits plus the holdout descriptions.
- [x] `training/prepare_data.py` (run with the backend venv): exports `training/data/{train,val,test}.jsonl` in TRL
      chat format with test subsets tagged iid/ood_*, writes `split_report.json`, and re-asserts on every export that
      no response family or negotiation cell straddles splits.
- [x] `evals/holdout_probe.py`: 66 blind retrieval probes (6 dialect/style groups, topical/paraphrase/negation/
      cross-doc) generated by agents that read only the knowledge docs; **frozen as a test set — never tune rules
      against it**. Measured today: top-1 gold 0.500, top-3 0.848 (details in §4).
- [x] Deploy-route fix: Ollama ≥ 0.34.2 removed LoRA `ADAPTER` loading, so `lora_adapter_spec` now documents the
      merge → `convert_hf_to_gguf` → `llama-quantize` → `FROM <gguf>` route and points `training_command` at the real files.
- [x] Research (14-agent workflow, 3 adversarial verdicts, none refuted): train on Qwen2.5-1.5B-Instruct
      (Apache-2.0, ungated, QLoRA peak ≈ 2.2–2.6 GB of the 4 GB card at seq 512; the 3B options OOM or carry
      restrictive licences); pip stack = torch cu128 + bitsandbytes ≥ 0.50.2 (their CUDA builds must pair) + TRL 1.x
      (`max_length`, `processing_class`, prompt-completion rows, `model_init_kwargs={'dtype': bf16}`); YOLO data =
      Diamant Potato Dataset (Mendeley, CC BY 4.0, shot in Dhaka markets), 3 visual classes with `undersized` derived
      geometrically.
- [ ] Not done, by the user's choice: pip installs, base-model download, LoRA training, GGUF/Ollama deployment, YOLO
      training, Whisper STT. `training/.venv` (Python 3.12.10) exists and is empty.
- Verified: backend boots with all changes; metrics 1.00 × 6; regression 100/100; leakage assertions pass.
- UI iteration (2026-10-29):
  - [x] `GET /evals/holdout?refresh=` — the frozen 66-probe blind test served live (`evals/holdout_probe.get_holdout_report`,
        10-min cache, ~1.5 s per run; route in `main.py`).
  - [x] Whitepaper (still English): `EvalsSection.tsx` third card "Blind holdout probe — frozen test set" with a run-live
        button (`/evals/holdout?refresh=true`), big top-1/top-3 numbers, per-kind and per-dialect bars and an expandable
        miss list — all from the API, no hard-coded numbers. `DepthMatrixSection.tsx`: the Fine-tuning row cites the
        family-aware train/val/test split + `TRAINING_PLAN.md`, the Evaluation row the frozen 66-probe holdout, and the
        local-models tester shows the split counts from the API. `api/client.ts` gained `HoldoutReport`, `api.holdoutProbe`
        and optional `train/val/test_examples` on `lora_adapter.dataset`.
  - [x] `ColdStorage3DTwin` is `React.lazy` + Suspense in `pages/CommandCenter.tsx`, splitting Three.js out of the OS chunk.
  - [x] Bangla: full COPY/`useCopy` coverage of the OS panel internals — `AgentTraceVisualizer`, `CommandCenter`,
        `BuyerBankPortal`, `TruckPoolMap`, `ColdStorage3DTwin`, `story/pipeline.ts` (`title_bn` per stage) and
        `story/PipelineSection.tsx`; technical tokens, IDs and units stay English. Done by a 5-agent parallel workflow.
  - [x] Build verified: `tsc -b` + `vite build` green; OsPage chunk 627 kB → 72 kB, Three.js in its own lazy chunk (569 kB).

---

## 4. Last measured results (2026-10-22; metrics and regression re-run 2026-10-24 after the lexicon change, unchanged)

| Check | Result |
|---|---|
| Regression suite (seed 20261226, 5 × 20) | **100/100 PASS**; rubric-judge 1.00 on every case (SYND-019 partial gone after the narrative change) |
| SFT dataset split v2 (2026-10-29) | train 2,301 / val 239 / test 660 (IID 270 + OOD 390: dialect 240, months 117, upazila 33); 1,096 response families and 56 negotiation cells, none straddling splits; caveat: 19 of 42 IID flood test responses are verbatim duplicates of each other |
| Blind retrieval probe (66 questions, 2026-10-29) | top-1 gold **0.500**, top-3 **0.848** — against 1.00 on the curated 19-question set. By dialect (top-1): English 0.91, Standard Bangla 0.46, Bogura 0.44, Banglish 0.43, Rangpuri 0.40, Sylheti 0.33. Cross-doc traps 0.17 top-1 / 0.83 top-3 (ranking, not recall). Frozen test set |
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
- `krishi-bangla-lora-v1` adapter not trained (3,200-example dataset generated deterministically); split v2 and the
  full 4 GB-GPU recipe are in TRAINING_PLAN.md — the user chose not to run training yet.
- No trained YOLO weights (`yolov11n-krishi-bd-v2.1` is a label); Gemini Vision not wired; uploaded photos use classical CV.
- Speech-to-text needs `faster-whisper` + `KNX_WHISPER_MODEL` (untested); presets and typed text work.
- Libraries named in the brief but not used: CrewAI, Pydantic-AI, DSPy, RAGAS, LLMLingua, Presidio, Neo4j server,
  n8n instance, Temporal server, BMAD-METHOD. Each is replaced by an in-repo implementation and labelled as such.
- Evaluation uses deterministic token/intent checks and a rubric judge, not an LLM judge; eval set is 19 questions.
- Retrieval is keyword and intent driven: there is no negation handling ("without collateral"), and intent words come from a fixed list
  in `crag_pipeline.INTENT_TRIGGERS`. A paraphrase that uses none of those words falls back to GENERAL. Precision 1.00
  is measured on a 19-question set written by the same team that wrote the rules — the blind 66-probe holdout
  (2026-10-29) measures top-1 0.500 / top-3 0.848, weakest on Sylheti/Rangpuri/Banglish phrasing and cross-doc
  ranking. Improvement protocol in TRAINING_PLAN.md §7: iterate on dev paraphrases, keep the 66 frozen, re-measure on
  a fresh blind batch.
- Brief figures not verifiable from here (CPD July 2026 study, UCB 6%, iFarmer terms) are attributed "as cited in the
  KrishiNexus brief" in the knowledge seed and on `/docs`.
- Bepari cost lines other than the Aratdar's 62.35% (freight 18%, labour 6.5%, wastage 5.25%, bags 4.4%, tolls 3.5%)
  and the Faria 20% / Bepari 70% cost-ratio split are modelled, not cited.
- Frontend: pages are code-split; since 2026-10-29 `ColdStorage3DTwin` is `React.lazy`, so Three.js lives in its own
  chunk and the OS paints before it arrives.
- Phase 8 UI, reviewed only in headless Chrome:
  - The language toggle covers the navbar, the overview, the OS headings, the farmer phone and — since 2026-10-29 —
    the OS panel internals; the whitepaper stays English.
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

### 2026-10-29 · Phase 9: train/test plan, split v2, blind retrieval probe
- **Why:** the user asked for a proper dataset train/test plan on their RTX 3050 (4 GB), then scoped it (ponytail
  ultra) to plan + honest evaluation with no training and no downloads.
- **Built:** `TRAINING_PLAN.md`; SFT split v2 + flood-response fix + deploy-route fix in `edge_node/ollama_local.py`
  (endpoint Literal updated in `main.py`); `training/prepare_data.py` + exported JSONL; `evals/holdout_probe.py`
  (66 blind probes, generated by a 14-agent research workflow whose three adversarial verdicts refuted nothing).
- **Measured:** split 2,301/239/660 with zero family straddles; blind retrieval top-1 0.500 / top-3 0.848 (vs 1.00 on
  the curated set); metrics 1.00 × 6 and regression 100/100 unchanged.
- **Caught on the way:** my first flood split leaked (identical alert texts across upazilas straddled train/test) —
  the self-check caught it; flood responses now name the haor. The repo's Ollama `ADAPTER` deploy flow is dead on
  Ollama ≥ 0.34.2; replaced with the merge → GGUF → quantize route.
- **Not committed**; the push repo does not mirror `training/` or `TRAINING_PLAN.md` yet — add them (minus `.venv/`
  and `data/`) when publishing Phase 9.
- **Next file when the user green-lights downloads:** `training/train_lora.py` per TRAINING_PLAN.md §4 (Qwen2.5-1.5B,
  cu128 stack, ~1.5–3 h), then `training/eval_lora.py` per §6.
  - Done later the same day (UI iteration): the lazy twin, the `/evals/holdout` endpoint + whitepaper blind-probe card,
    and full Bangla OS-panel coverage — see the Phase 9 UI-iteration bullets. Build verified the same day.

### 2026-11-06 · Kaggle training notebook + dataset card
- **Why:** the user asked for a complete notebook to train the model on Kaggle, plus an MD dataset description for
  running it there.
- **Built:**
  - `training/kaggle/krishinexus_lora_kaggle.ipynb`, 20 cells:
    - data checks;
    - QLoRA on one T4, choosing bf16 or fp16 automatically;
    - frozen-test eval of adapter vs base vs a prompt-blind baseline (train-only);
    - bf16 merge → GGUF f16 → Q4_K_M + Modelfile.
    - Outputs are named for `backend/models/lora/krishi-bangla-lora-v1/`.
  - `training/kaggle/KAGGLE_DATASET.md`: a run guide plus a paste-ready Kaggle card. Its examples, tables and
    metadata were checked against the files.
- **Verified locally (CPU):**
  - The scorer/report cell was self-tested on the real splits: gold answers score perfectly, empty answers score zero.
  - All code cells compile.
  - The config, helpers and data cells were executed.
  - Library facts were re-read from source by research agents: TRL 1.17.1 casts quantized-model adapters to bf16 in
    `__init__` and never calls `prepare_model_for_kbit_training`; transformers 5.22 dropped `warmup_ratio`;
    bitsandbytes 12.8+ wheels drop sm_60; the llama.cpp converter pins torch 2.11 CPU and transformers 4.57.6.
- **Fixed:** the pushed `training/train_qlora.ipynb` would have crashed on start. Its problems:
  - `warmup_ratio`;
  - `bf16=True` on a T4;
  - the clone path `KrishiNexus/krishinexus-os`;
  - `quantization_config` passed inside `model_init_kwargs`;
  - wrong exporter dependencies.

  It was regenerated with an explicit model load, precision detection, the fp32 adapter recast and `warmup_steps`.
- **Measured dataset properties:**
  - A prompt-blind baseline on the full test split scores negotiation decision 0.942 (balanced 0.500), arbitrage
    verdict 0.560, flood alert 0.680, storage citation 1.000 and chrF 19.47.
  - Only 22 of 380 test offers are fair.
  - Negotiation prompts never contain the market or date that the answers state.
  - Flood alerts depend on an unstated month for 11 of 75 test rows.
  - All 39 storage test questions also occur in train.
- **Not done:** no GPU run, no commit, no push.

### 2026-11-07 · SFT prompts v3: questions state every input the answer uses
- **Why:** the user chose to fix the data before training. The negotiation answers quoted a market and date that were
  absent from the question, and the flood answers depended on a hidden month.
- **Changed:** `ollama_local._negotiation` appends `({market} বাজার, {dd Mon})` to the question. `_flood` adds
  `{মার্চ|এপ্রিল|মে} মাসে` after the haor name; the name stays first because it is the OOD holdout key. A
  `MONTH_BN` constant was added, and the generator label now reads "prompts v3".
- **Verified:**
  - Against a snapshot of the v2 files: example ids per split, answers, subsets and dialects are identical. Only the
    1,200 negotiation and 500 flood questions changed.
  - Replaying the questions through `market_prices` and `breach_probability` reproduces 1,200/1,200 and 500/500
    answers.
  - The scorer self-tests pass, the baselines are unchanged, the Kaggle notebook's CPU cells re-ran, and
    `lora_adapter_spec` still reports 3,200 rows (2,301 / 239 / 660).
  - The new `jsonl_sha256` is `2ad09dcf…9825`.
- **Remaining limitations:** prices must still be learned from the seasonal curve, and the fair/unfair label is
  imbalanced (22/380 in test). Storage questions repeat with different answers, and arbitrage uses only 3 of its 5
  verdicts.
- **Next:** upload `training/data/` to Kaggle per `training/kaggle/KAGGLE_DATASET.md`, run the notebook, and record
  the `eval_report.json` numbers here. Nothing is committed or pushed.

### 2026-11-08 · First LoRA training run on Kaggle (T4): measured, fails targets
- **Why:** the user supplied a Kaggle API token and asked for training to start.
- **Token handling:** the token stays in `C:/Users/Asus/Downloads/congress/Kaggle Token.txt`, outside the repo. It is
  read only by a scratchpad wrapper. Never print, copy or commit it.
- **Kaggle resources:** everything is private and owned by `taksimulhasandip`.
  - Dataset: `krishinexus-bangla-agri-sft`, data sha `2ad09dcf…9825`.
  - Kernels: `krishinexus-lora-smoke-test` (20 steps) and `krishinexus-bangla-lora-training` (full run).
- **Notebook fixes found by the smoke runs** (now in `training/kaggle/krishinexus_lora_kaggle.ipynb`):
  - Kaggle's torchao 0.10 broke the PEFT merge, so the install cell uninstalls torchao.
  - llama.cpp's converter can't read a tokenizer_config written by transformers 5, so the original Qwen tokenizer
    files are copied into the merged folder.
  - Kaggle keeps no outputs from a failed run, so the merge and GGUF steps record an error instead of raising.
- **Full run:** 432 steps in 35.6 min, then the eval on all 660 test rows, then a Q4_K_M GGUF with no export error.
  - Versions: torch 2.11.0+cu130, transformers 5.22.2, TRL 1.17.1, PEFT 0.21.2.
  - Raw outputs are in `training/runs/kaggle-t4-2026-11-08/`.
  - The adapter (~74 MB) and GGUF (~1 GB) were **not downloaded**.
- **Measured (test split, greedy; adapter / base / prompt-blind baseline):**

  | Metric | Adapter | Base | Baseline |
  |---|---|---|---|
  | negotiation decision | 0.942 | 0.116 | 0.942 |
  | negotiation balanced | 0.500 | 0.083 | 0.500 |
  | negotiation price fidelity | 0.005 | 0.000 | 0.000 |
  | arbitrage verdict | 0.211 | 0.000 | 0.560 |
  | arbitrage trace | 0.000 | 0.000 | 0.000 |
  | flood alert | 0.560 | 0.000 | 0.680 |
  | flood within ±2 pts | 0.200 | 0.000 | 0.000 |
  | flood MAE | 23.54 pts | — | — |
  | storage citation | 0.051 | 0.000 | 1.000 |
  | storage chrF | 14.64 | 0.29 | 19.47 |

  - Only negotiation decision accuracy meets its target, and the baseline meets it too.
  - The adapter scores below the baseline on arbitrage, flood alert and storage.
- **Diagnosis:**
  - The adapter learned each answer template, not the decision inside it: always `unfair`, always `BLOCK_SPOT_SALE`,
    always `RED` or no alert.
  - Its numbers are guessed: the price has a 21% median relative error, and ΔΠ is never within tolerance.
  - Validation loss was lowest at step 50 and rose after that, so `load_best_model_at_end` evaluated a 0.35-epoch
    checkpoint.
  - Full analysis: TRAINING_PLAN.md §6.
- **Next (the user decides):** either
  - keep the LLM's job to extraction and phrasing, as the pipeline already works: put the engine's computed numbers
    in the prompt (tool-grounded SFT); or
  - rerun with checkpoint selection by task accuracy.

  Either way, score on a **freshly generated** test batch, because this split is spent for this formulation.

### 2026-11-09 · SFT prompts v4: tool-grounded data, second Kaggle run
- **Why:** the user chose tool-grounded data. The model should read the numbers the engines compute, then decide and
  explain.
- **Changed in `edge_node/ollama_local.py`:**
  - `_grounded` appends `<tool_result name="...">{json}</tool_result>` to each question:
    - `get_daily_commodity_spread`: prices rounded to whole taka;
    - `financial_circuit_breaker`: floor, storage value, spot value and ΔΠ;
    - `calculate_haor_flash_flood_risk`: breach percent;
    - `crag_retrieval`: three passages.
  - `_draw` re-samples inputs until the engine's label matches a drawn target, so labels are balanced.
  - The flood alert is now ruled on the shown whole percent.
  - Storage gets two distractor passages from other documents.
  - New constants `SFT_SEED` (20261109) and `SPLIT_SALT` (`split-v4`) make the test batch fresh.
  - The generator label now says "tool-grounded prompts v4".
- **Changed elsewhere:**
  - The notebook's `kaggle_helpers.question()` strips the tool result, so the prompt-blind storage baseline keys on the
    bare question.
  - The notebook was regenerated.
  - The card (KAGGLE_DATASET.md Part 2) was rewritten with measured v4 figures.
  - `dataset-metadata.json` was refreshed.
- **Measured:**
  - Splits: train 2,434, val 125, test 641. Test holds 240 IID rows plus the OOD subsets: 240 dialect, 128 months
    and 33 upazila.
  - Families: 1,170 answer families and 56 negotiation cells, none straddling splits.
  - `jsonl_sha256` is `794becfc…87a1`.
  - Labels: negotiation 575 fair / 625 unfair; arbitrage 236 / 224 / 240; flood alerts 114–129 each.
- **Verified:**
  - A rule reader recovers all 3,200 labels from the user turn alone, and an engine replay reproduces every tool
    payload. The check script is `check_v4.py` in the scratchpad.
  - Generation is deterministic.
  - No v4 test question appears in the v3 test split.
  - The scorer self-tests and the notebook CPU checks pass.
  - `lora_adapter_spec` reports 3,200 rows.
  - The prompt-blind baseline meets only storage citation (1.000). Its other scores: negotiation 0.547, arbitrage
    0.288, flood 0.229, chrF 21.52.
- **Kaggle:**
  - Dataset version 2 is uploaded and private; the card is live on it.
  - Kernel `krishinexus-bangla-lora-training` version 2 was pushed on a T4.
- **Not done:** `run_local_inference` still sends the raw prompt. To use the adapter in the app, it must put the same
  tool results into the prompt.

### 2026-11-09 · Second LoRA run (prompts v4): measured, meets every target
- **Run:** private kernel version 2 on data `794becfc…87a1`: 459 steps in 41.4 min on a T4, fp16. The Q4_K_M GGUF
  exported without errors.
  - Raw outputs are in `training/runs/kaggle-t4-2026-11-09/`.
  - The adapter and GGUF were **not downloaded**.
- **Measured (fresh 641-row test split, greedy; adapter / base / prompt-blind baseline):**

  | Metric | Adapter | Base | Baseline |
  |---|---|---|---|
  | negotiation decision | 0.909 | 0.000 | 0.547 |
  | negotiation balanced | 0.909 | 0.000 | 0.500 |
  | negotiation price fidelity | 0.985 | 0.003 | 0.000 |
  | arbitrage verdict | 1.000 | 0.000 | 0.288 |
  | arbitrage trace | 1.000 | 0.000 | 0.000 |
  | flood alert | 1.000 | 0.000 | 0.229 |
  | flood within ±2 pts | 1.000 | 0.571 | 0.000 |
  | storage citation | 0.925 | 0.000 | 1.000 |
  | storage chrF | 93.28 | 18.53 | 21.52 |

  - OOD: negotiation 0.904 on the unseen dialect; arbitrage (7-month holding) and flood (unseen haor) both 1.000.
  - Validation loss fell at every evaluation, to 0.00021, so the evaluated checkpoint is the last one.
- **Diagnosis** (full version in TRAINING_PLAN.md §6):
  - Negotiation is the only real decision left: 31/340 wrong, clustered near the 95% line (13 of 34 offers at 85–95%
    wrong). Some answers misstate the gap.
  - All 3 storage citation misses share one gold answer: the generator files a chili chilling-injury sentence under
    "pre-cooling". This is label noise.
  - Arbitrage and flood are now copy-and-threshold tasks. Their 1.000 shows faithful reading, not forecasting.
- **Not shown:**
  - The GGUF Ollama would serve was not scored.
  - Test questions share the training templates.
  - The app doesn't use the adapter yet.

### 2026-11-09 · Model 2, potato vision: notebook built, Kaggle runs started
- **Why:** the user asked to train more models on more datasets to win the competition.
  - The rubric is CloudCamp's 110-point AI Depth Score (International AI Builders Congress 2026, AgriSphere AI track).
  - `/docs` lists Fine-tuning, Multimodal and Local LLMs as "Partial". New models are chosen to turn those rows
    Live with measured evidence, not to raise the model count.
- **Dataset:** Diamant Potato Dataset (Mendeley, DOI 10.17632/4vty9rz7zw.1), CC BY 4.0, from Daffodil International
  University.
  - Two zips: `roi_dataset.zip` (5.02 GB, sha256 `27a32167…ea0d`) and `defect_dataset.zip` (3.92 GB, sha256 `89cbdfc1…3d48`).
  - Instance segmentation: ROI has 1 class (potato); defects have scab, rot, greening and mechanical damage.
  - The authors' own splits are used. TRAINING_PLAN.md §8 was rewritten with the real layout, the two-stage design and
    targets pre-registered before any result.
- **Notebook:** `scratchpad/gen_vision_nb.py` generates it, and its helpers module `vision_helpers.py` has a self-test.
  - The notebook goes into `training/kaggle/krishinexus_potato_vision_kaggle.ipynb` once the smoke run passes.
  - Without a GPU it runs a CPU smoke test, labelled as not results.
- **Kaggle:** private kernel `taksimulhasandip/krishinexus-potato-vision-training`. Version 1 is the CPU smoke run;
  the GPU run comes next.
- **Not allowed:** reading the zip index locally with a spoofed user agent was refused by the permission classifier. The
  kernel downloads with curl's default user agent instead.
- **Next models, as recommended to the user:**
  - ship the trained LoRA (needs the user's OK for a ~1 GB GGUF download);
  - Bangla Whisper STT on Common Voice 13 Bengali (`umongsain/common-voice-13-bengali-normalized` on Kaggle, CC0).

### 2026-11-09 · Shipping the fine-tuned Bangla model into the app
- **Why:** the user said "Yes, ship it" (put the trained model into the app, about a 1 GB download), then chose
  "Install Ollama via winget".
- **Installed:** the GGUF, adapter and Modelfile from Kaggle kernel version 2 are in `backend/models/lora/`.
  - SHA-256 values are in TRAINING_PLAN.md §5. `training_args.bin`, a pickle, was not downloaded.
  - `backend/models/` is git-ignored in this repo (new `krishinexus-os/.gitignore`) and in `Claude to push/.gitignore`.
    The publish mirror copies `backend/`, and GitHub rejects files over 100 MB.
- **Code:**
  - `ollama_local`: `krishi-bangla-1.5b` registry entry; 7B no longer claims the adapter; retargeted `lora_adapter_spec`
    with `eval_summary` read from the installed report.
  - `ground_prompt` / `_tool_result` mirror the SFT builders. Replaying the 641 test questions gives 0 mismatches
    (check script: `check_grounding.py` in the scratchpad).
  - Greedy decoding for the fine-tuned model. A blackout cuts only the internet, so local runtimes are always probed.
  - `LocalInferenceResult.grounded_prompt`.
  - `supervisor.voice_interact`: offline mode asks `krishi-bangla-1.5b` with the raw transcript.
  - `agri_weather_sar_mcp.simulated_sar_db` replaces two copies of the simulated Sentinel-1 pass.
  - Frontend:
    - the `/docs` LocalTester shows the score table plus "Ask the fine-tuned model";
    - the depth matrix's Fine-tuning row is "Live";
    - the CommandCenter offline line and `fallback.ts` name the 1.5B model.
  - `docker-compose.yml`: `ollama-pull` loads the GGUF when it is present. This is unverified, since there is no Docker host.
- **Verified:**
  - `/edge/local-models` reports `adapter_present` with 11 measured rows.
  - All 5 voice presets complete in offline mode with grounded prompts.
  - `tsc` passes.
  - In the browser, the `/docs` tester shows the score table and the labelled fallback answer.
- **Blocked:** GitHub release downloads returned 504 from about 11:15 BDT, so winget could not fetch OllamaSetup.exe
  (ollama.com redirects to GitHub). A retry loop runs every 5 minutes. The Kaggle vision smoke run v2 fetches its YOLO
  weights from GitHub too.
- **Update, 12:00–13:00:**
  - GitHub recovered and winget installed Ollama 0.40.15 (installer hash verified).
  - `ollama create krishi-bangla -f Modelfile` worked; Ollama's model layer SHA-256 equals the downloaded GGUF's.
  - Live through `/edge/local-inference`: `runtime: ollama`, measured, about 85 tok/s, 1.1 GB VRAM on the RTX 3050.
- **Deployed GGUF scored on all 641 test questions (`scratchpad/score_gguf.py`): it FAILS flood alert.**
  - Flood alert is 0.757 against a 0.90 target. Arbitrage verdict 0.911 and negotiation 0.903 only just pass.
  - Only 42% of answers are identical to the Kaggle 4-bit answers. The full table is in TRAINING_PLAN.md §5.
  - Suspects: Q4_K_M quantisation, or the merge into the bf16 base when the adapter trained against NF4.
- **Honesty fix:**
  - The report is installed as `backend/models/lora/gguf_eval_report.json` and recorded in
    `training/runs/local-ollama-2026-11-09/`.
  - The API serves it as `deployed_eval_summary`; the `/docs` table shows "Training run" beside "Deployed (Ollama)".
  - Depth matrix: Fine-tuning is "Live" (its note points to both columns); Local LLMs is "Live" (Ollama serves the GGUF).
- **Free-form prompts:** a flood question worded outside the training template gets a garbled answer. Training data
  needs paraphrased questions (a v5 candidate).
- **Running on Kaggle:**
  - `krishinexus-lora-gguf-export` v1 re-exports A-Q8_0, B-Q8_0 and B-Q4_K_M and scores each through Ollama.
  - `krishinexus-potato-vision-training` v3 trains on a T4.
- **Next:**
  - If an export meets every target, ask the user before downloading it (Q8_0 is about 1.6 GB), then
    `ollama create` it and install its report as `gguf_eval_report.json`.
  - Record the vision results.

### 2026-11-09 · Model 2 potato vision: first T4 run, measured
- **Run:** kernel `krishinexus-potato-vision-training` v3 on a T4 with Ultralytics 8.4.208.
  - Stage 1 (YOLO11n detect) ran 80 epochs in 20 min; stage 2 (YOLO11n-seg) stopped early at epoch 127 of 150, in
    34 min.
  - Outputs are in `training/runs/kaggle-t4-2026-11-09-vision/`.
  - Weights are in git-ignored `backend/models/yolo/` (`roi_best.pt` `b9d429d9…`, `defect_best.pt` `1b8ddded…`).
  - Earlier versions: v1 (CPU smoke) failed on a GitHub 504 and an over-strict ROI count check; v2 (CPU smoke) passed
    every data check and every cell.
- **Measured (test opened once; targets pre-registered):**
  - stage 1 box mAP50 0.994 (val 0.995): **meets** ≥0.90;
  - stage 2 mask mAP50 0.335 (val 0.396): **misses** ≥0.50;
  - grade accuracy 0.768 against always-C 0.674: **meets** ≥0.70; balanced accuracy 0.644 (always-C 0.333).
  - Mask AP50 by class: scab 0.435, rot 0.429, mechanical damage 0.286, greening 0.189.
  - Bruising-% MAE 19.2 points, rot-% MAE 1.0.
- **Next (selected on val only):**
  - stage 2 at 1024 px and/or YOLO11s-seg;
  - stage 1 as YOLO11n-seg, for background removal at inference;
  - then wire the cascade into `optical_grader.yolo_detect`.
- The Multimodal row in `/docs` stays "Partial", with a note naming the trained but unwired models.

### 2026-11-09 · Model 3, `krishi-price-v1`: staple price intelligence (the user's pasted brief)
- **Why:** the user asked, after the current plan, for AI commodity price monitoring: DAM/TCB/WFP-HDX prices,
  LightGBM and GRU/TCN forecasts, and wholesale-retail spread anomalies. They added "more and more ai model increases
  chances to win" and "keep updating everything into kaggle" (saved as a feedback memory).
- **Data:** WFP *Bangladesh - Food Prices* (HDX, CC BY-IGO; snapshot 2026-11-04, sha256 `2f009010…0ce`).
  - It is on Kaggle as the private dataset `taksimulhasandip/krishinexus-bd-food-prices`.
  - Series: 4 staples × 6 divisions. Each joins WFP's division averages (to mid-2020) with the median of district
    markets after; no feature or target crosses the join.
  - The joins jump by a median of 6%, and lentils by −8 to −16%, which looks like a change of variety.
- **Pipeline:** `scratchpad/price_pipeline.py` (self-test `test_price_pipeline.py`), embedded verbatim in
  `training/kaggle/krishinexus_price_kaggle.ipynb` (private kernel `krishinexus-price-intelligence`).
  - Features: returns, Ramadan share (tabular Islamic calendar), FX from WFP's `price/usdprice`, Open-Meteo rainfall
    anomaly.
  - Models: naive, seasonal naive, LightGBM per horizon, GRU, TCN, ensemble; the choice is made on validation.
  - Local debugging used `score_test=False`; the test year was scored once, on Kaggle.
- **Measured (Kaggle CPU, 49 s): misses 2 of the 3 pre-registered targets.**
  - Test mean sMAPE: chosen ensemble 2.747 against naive 2.643 (miss).
  - 3-month sMAPE: ensemble 3.619 against seasonal naive 8.17 (met; a weak baseline).
  - 3-month direction accuracy: 0.49 (miss). Validation had looked better (LightGBM direction 0.64), but it didn't
    hold on test.
  - Spread flags: 34, enrichment 1.1 against the three reported windows, i.e. none. The flags cluster in 2012 and
    early 2015.
  - Outputs are in `training/runs/kaggle-cpu-2026-11-09-price/`; the models are in `backend/models/price/`.
- **App:**
  - `backend/price_monitor.py` + `GET /market/price-monitor?division` return the latest prices, 1- and 12-month
    changes, the 3-month forecast, and the test scorecard against "no change" (from the report), plus the last 8
    margin flags and their provenance.
  - The frontend's `PriceMonitorPanel` (market seat `/os/market`, EN/BN) has a division picker and an amber note:
    "higher than assuming no change … indicative only".
  - `/market` was added to the Vite proxy and nginx.
  - Verified in the browser in EN and BN.
- **Gotcha:** Vite's file watcher once missed an edit to `client.ts` (it served a stale module); restarting the dev
  server fixed it.

### 2026-11-09 · Bangla model re-exported: B-Q8_0 meets every target and is now the deployed model
- **Kaggle `krishinexus-lora-gguf-export` v2** (T4, Ollama 0.40.15). v1 failed because Kaggle has no `zstd` for the
  Ollama installer; v2 runs `apt-get install zstd` first.
  - The run scored three re-exports of the same adapter on all 641 test questions.
  - Outputs are in `training/runs/kaggle-t4-2026-11-09-gguf-export/`.
- **Finding:** the merge was the main cause.
  - **B-Q8_0** (merged into the NF4 base, de-quantised as trained) reproduces the training run: arbitrage 1.000/1.000,
    flood 1.000/1.000, negotiation 0.912/0.979, storage 93.28/0.925.
  - A-Q8_0 (bf16 merge) passes, but the arbitrage verdict clears by only 0.0005.
  - B-Q4_K_M collapses (arbitrage verdict 0.393).
  - The full table is in TRAINING_PLAN.md §5.
- **Shipped B-Q8_0** with the user's conditional approval ("Yes, if it passes").
  - `backend/models/lora/krishi-bangla-q8_0.gguf`, 1,646,572,704 bytes, sha256 `7c0e7e66…ab75`, verified against the
    manifest. The Modelfile now reads `FROM ./krishi-bangla-q8_0.gguf`.
  - `ollama create` gave `krishi-bangla:latest`, Q8_0, 1.6 GB.
  - The registry gained a `quantization` field (krishi model: "Q8_0 GGUF", 1.65 GB); the fallback and compose were
    updated.
  - The old Q4_K_M file is still in `backend/models/lora/` but unused.
- **Live in the app:** 57 tok/s on the RTX 3050, 1.75 GB VRAM. The price answer is complete and correct.
  - A free-form flood question is still wrong ("5% (YELLOW)", with the prompt echoed). This is a template limit; the fix
    is SFT data with paraphrased questions (v5).
- **The training notebook now exports this way:** an NF4 merge, then `convert_hf_to_gguf --outtype q8_0`, with no
  llama.cpp build (`scratchpad/gen_kaggle_nb.py`; repo notebook regenerated). Kaggle still has the old version until
  the next training run, because pushing a kernel starts a run.
- **Local re-score on the RTX 3050: meets every target.** Arbitrage 1.000/1.000, flood 1.000/1.000, negotiation
  0.915/0.979, storage 93.28/0.925; 97.7% of answers are identical to the training run's (the old Q4 managed 42%);
  56 tok/s, 1,745 MB.
  - Installed as `gguf_eval_report.json` and recorded in `training/runs/local-ollama-2026-11-09-q8/`.

### 2026-11-09 · Kaggle dataset cards refreshed with measured results
- **SFT card** (`KAGGLE_DATASET.md` Part 2, which is `training/data/dataset-metadata.json`'s description): new section
  "A model trained on it (measured)" with the training run, the deployed Q8_0 and the baseline.
  - Published as dataset **version 3**. The live card is verified identical (15,887 chars), and the data is unchanged.
- **Price card** (`krishinexus-bd-food-prices`): a measured-results paragraph covering the misses, published as
  version 2.
- **Gotchas:**
  - `kaggle datasets metadata --update` rejected the licence id `CC-BY-4.0` and the tag `bangladesh`. When it finally
    "succeeded", it **truncated the card at the first Bangla example text** (to 1,763 chars).
  - What works: `datasets version -p . -t -m ...` run from inside the data folder. An absolute `-p` path breaks the
    CLI's upload-cache path.
  - The tag `bangladesh` was removed from the repo metadata.

### 2026-11-09 · Vision run 2 (T4 ×2) and Whisper (model 4) started
- **Vision v5:** stage 1 is YOLO11n-seg. Test box mAP50 0.9945 and mask mAP50 0.9946: meets, and now outlines
  potatoes.
  - Stage 2 candidates on validation: n at 1024 px 0.3956 (chosen) against s at 640 px 0.3937, both equal to run 1
    (0.396).
  - Test mask mAP50 0.342 **misses** 0.50 again. The ceiling looks like a data limit.
  - Grading was not measured: CUDA out of memory predicting at 1024 px with retina masks. Run 1's 0.768 is still the
    last measured.
  - Outputs are in `training/runs/kaggle-t4x2-2026-11-09-vision2/`; the weights are in `backend/models/yolo/run2/`.
- **Whisper `krishi-whisper-bn-v1`** (TRAINING_PLAN §8c; targets set before training: WER ≤ 0.45, CER ≤ 0.15, both
  below base; int8 CT2 within 0.02 WER).
  - Data: Common Voice 13 bn normalized (train 20,729 / dev 9,230 / test 9,230). The model is chosen on 500 dev clips;
    a seeded 2,000-clip test sample is scored once; the 300-clip parity check runs on CPU with faster-whisper.
  - Notebook: `training/kaggle/krishinexus_whisper_kaggle.ipynb` (generator `scratchpad/gen_whisper_nb.py`; helpers
    `whisper_helpers.py` with a self-test). Private kernel `krishinexus-bangla-whisper-training`.
  - The smoke runs found three bugs:
    - transformers 5 saves `processor_config.json`, but the CT2 converter needs `preprocessor_config.json`; it is now
      copied from the base model;
    - a `proj_out` "missing key" warning, which was harmless (the layer is tied), and is now asserted;
    - Kaggle's PyAV rejects faster-whisper's `metadata_errors` argument, so audio is now passed as a librosa array.
  - **GPU run v4 pushed at about 16:30.**

### 2026-11-09 · Potato cascade wired into the optical grader (the user said "Yes, connect them")
- **Why:** the user approved connecting run 2's models, although stage 2 misses its 0.50 mask target.
- **Backend (`edge_node/optical_grader.py`):**
  - `yolo_detect` is now the two-stage cascade for Cardinal and Diamant potato photos; other crops keep classical CV.
  - Weights come from `KNX_YOLO_WEIGHTS` (a folder) or the default `backend/models/yolo/run2/`. That folder holds
    `roi_best.pt`, `defect_best.pt` and `eval_report.json` (copied from
    `training/runs/kaggle-t4x2-2026-11-09-vision2/`).
  - Stage 1 runs at 640 px with conf 0.25. Each potato is cut out onto black and `green_boost`ed, then stage 2 runs at
    1024 px with conf 0.25.
  - Masks are rasterised from `masks.xy` by `fill_outlines`, so no full-size mask stack is built (the cause of run 2's
    grading OOM).
  - Per potato, bruising % and rot % give the label: undersized below 35 mm, else rot above the active grade-A rot
    limit (`a_rot`, 2%), else any blemish, else uniform_A. The lot metrics and the BARI grade rule are unchanged.
    - The first version flagged any rot pixel. A 0.1% rot speck at conf 0.30 then failed a clean potato to C, which
      the measured per-potato rule would not do.
  - A box's confidence is the deciding detection's (for example the rot mask's 0.64), not stage 1's potato
    confidence, which had read as "fungal_blight 99%".
  - `inference_backend` is `ultralytics-yolo two-stage (run2: roi_best.pt + defect_best.pt)`.
    - `yolo_reason` adds a reason read from the installed `eval_report.json` (defect test mask mAP50 0.3419 against
      0.5, not met) and `grade_check.json` (grade accuracy 0.764 against 0.7, always-C 0.6742).
    - The reasons also state the photo width assumed (`frame_width_mm`). The user then said "Yes, add it" to a
      picker: step 2 now has "How wide the photo is" (close-up 15 cm, handful 30 cm, crate 60 cm = default, heap
      1.5 m) above Grade a photo, and `api.gradePhoto` sends it.
      - The lot select moved above Scan sample lot; the crop select is full width above the canvas.
      - Checked: a close-up reads 64.5 mm at 15 cm (258 mm at the old fixed 60 cm). In the browser, a photo at 15 cm
        gives "sizes assume the photo spans 150 mm".
      - Gap: in a synthetic 8 × 8 mosaic (64 potatoes, 3000 px), stage 1 found only 17. It was trained on photos of
        one or two potatoes, at 640 px. Not tuned: tiled inference or retraining on heaps would be the fix.
      - Gotcha: the Vite dev server served a stale `FarmerZeroUIApp.tsx` again; a restart fixed it.
  - `decode_image` now applies `ImageOps.exif_transpose` (phone photos; the training images were transposed too).
  - `main.py` runs `/edge/grade-crop` through `asyncio.to_thread`: CPU YOLO takes seconds and was blocking the event
    loop. `_YOLO_LOCK` serialises the Ultralytics models, which aren't thread-safe.
  - `ultralytics` 8.4.208 (with torch 2.15.0+cpu and opencv 5.0.0) is installed in the backend venv. It stays an
    optional dependency: it is not in `requirements.lock`, and the Docker image stays on classical CV.
- **Frontend:**
  - `api.gradePhoto` has no offline fallback, because a photo can't be graded without the backend.
  - `FarmerZeroUIApp` step 2 has **Grade a photo** (a hidden JPEG/PNG input, read as a data URL) beside **Scan sample
    lot** (the preset sweep, renamed).
    - Diamant Potato is in the crop list.
    - A photo grade no longer sends `grade_sample_preset` to the voice flow.
  - `OpticalGraderCanvas` takes `photo` and draws the uploaded photo under its boxes, at the photo's aspect ratio. It
    draws a photo only when it matches the current result, never a stale one.
  - `CertificateCard` lists `grading_reasons` under photo grades.
  - The premium badge now shows "-12%" in red. It used to read "+-12%" in green for every Grade C.
  - The DepthMatrix Multimodal note is updated. It stays Partial: Whisper isn't wired, and stage 2 misses its target.
- **Grade check (run 2's pre-registered check, run once after its OOM; nothing retuned):**
  - Private CPU kernel `taksimulhasandip/krishinexus-potato-grade-check` v1 (about 15 min, mostly the 8.9 GB download).
  - Notebook `training/kaggle/krishinexus_potato_grade_check_kaggle.ipynb`; generator `scratchpad/gen_gradecheck_nb.py`;
    local cell test `test_gradecheck_nb.py`, run with the real weights on a synthetic set.
  - Report in `training/runs/kaggle-cpu-2026-11-09-gradecheck/grade_check.json`, also copied to
    `backend/models/yolo/run2/`.
  - **Grade accuracy 0.764: meets ≥ 0.70** (always-C 0.674; run 1 0.768). Balanced accuracy 0.663.
  - Bruising-% MAE 17.6, rot-% MAE 1.05. Presence F1: scab 0.94, rot 0.64, mechanical damage 0.51, greening 0.41.
  - The commonest error is C → A (31 of 180).
  - CPU time is 0.39 s per crop.
- **Real photos:** six untouched validation photos (3000 × 3000 px) saved by the kernel, in
  `scratchpad/downloads/gradecheck-v1/samples/`.
  - Every potato was found, matching the hand-drawn outline; grades A A C C C C; 0.5–0.8 s each on CPU.
  - Overlays from `scratchpad/overlay_cascade.py` show sensible scab spots, a decaying end marked as rot, and netted
    skins called scab across 59–95% of the surface.
- **Checked:**
  - the helper self-checks pass (`scratchpad/test_yolo_cascade.py`);
  - a drawn image returns 422 "No produce detected", and the app shows "Photo not graded";
  - chili photos stay `classical-cv`;
  - the typecheck passes.
  - In the browser (`/os/field`, Diamant Potato, real photo 0164 picked via a simulated file input), the graded photo
    shows with "fungal_blight 65%". The certificate shows Grade-C, "-12% vs ungraded" and the four reasons. The
    first call took 5–6 s, including the model load.
  - API on 127.0.0.1:8010:
    - a warm grade of a 3000 px photo takes 0.72 s end to end;
    - `/health` answers in 10–20 ms during grading (33 probes), so the worker thread keeps the event loop free.
    - Gotcha: probing `http://localhost` from Python on Windows adds about 2 s per new connection, because it tries
      ::1 first. Use 127.0.0.1 for latency checks.

### 2026-11-09 · Tiled potato finding for heap photos (the user said "Yes, try it")
- **Why:** stage 1 (trained on one or two potatoes per photo, run at 640 px) found 17 of 64 potatoes in a synthetic
  heap mosaic.
- **Change (`edge_node/optical_grader.py`):** `find_potatoes` runs stage 1 on the whole photo plus a 4 × 4 grid of
  overlapping square tiles (`TILE_GRID` 4, `TILE_OVERLAP` 15% of the long side, `tile_starts` spaces them evenly).
  - Each tile runs at 640 px, which shows potatoes 2.8× larger.
  - A tile detection cut by an inner tile edge is dropped; detections overlapping by more than half the smaller box
    (`overlap_of_smaller`) keep the surest.
  - `_cascade` grades whatever `find_potatoes` returns; stage 2 is unchanged.
  - Shortcut noted in the code: boxes, not outlines, decide overlap, so two piled potatoes sharing over half a box
    count once.
- **How the grid was chosen** (full write-up and table in TRAINING_PLAN §8, "Tiled potato finding"):
  - A scale sweep on the six validation photos found the potato at every input size from 128 to 1280 px, and only a
    fragment at 1920 px and above; a native-resolution pass is therefore out (it breaks close-ups and takes 5 s).
  - The candidates were 2 × 2, 3 × 3 and 4 × 4 grids, compared on two synthetic heaps built from validation photos:
    the 8 × 8 mosaic, and a seeded scatter of 40 cut-out potatoes at 2–9% of a 4000 × 3000 frame. Neither is a test
    set.
  - 4 × 4 found 64/64 and 34/40 (in memory), against 17 and 1 before, with no false detection and one potato per
    close-up.
- **Checked:**
  - From the saved JPEGs (decoded as the API does): 64/64 and 36/40. Three scatter misses are under 3% of the frame
    width, one is 4.7%.
  - `scratchpad/test_yolo_cascade.py` gains `tile_starts` and `overlap_of_smaller` asserts. It passes, and the six
    close-ups keep exactly one potato and their grades.
  - API on 127.0.0.1:8010 after a restart:
    - close-up 0762 at 150 mm: 64.5 mm, Grade A, 2.05 s warm (was 0.72 s) and 7.2 s cold;
    - mosaic at 1.5 m: 64 potatoes, Grade C, 9.2 s;
    - scatter at 1.5 m: 36 potatoes, Grade C, 7.5 s;
    - `/health` stays under 70 ms meanwhile. The app's request timeout is 120 s.
  - Browser (`/os/field`, "Heap, 1.5 m", the scatter uploaded through the file input): 36 boxes drawn on the photo,
    "36 objects", Grade-C certificate, reasons say 1500 mm. The staged `frontend/__knx_test_potato.jpg` was deleted.
- **Caveat measured:** finding small potatoes is fixed, grading them is weaker. On the mosaic's small copies (graded
  at 3,000 mm so none is undersized):
  - rot survives: 0164 is fungal_blight in 11/11 copies (15.5% against 16.0% full size);
  - fine scab is lost: 1229 (59% blemish full size) reads uniform_A in 8 of 10 copies.
- **Scratchpad:** `scale_sweep.py`, `tile_experiment.py` (writes `tiles/scatter_b.jpg` + `.json` and overlays),
  `score_heaps.py`.

### 2026-11-09 · Size sweep and a small-potato warning on the certificate (the user said "Yes, measure it")
- **Why:** finding small potatoes was fixed, but grading them was weaker (1229's scab vanished on small copies). The
  question was the width in pixels below which stage 2 stops seeing what it sees at full size.
- **Rule first:** TRAINING_PLAN §8 ("Defect detail against potato size") recorded the method and the decision rule
  before the run. The threshold is the smallest tested width at which, and at every larger width, at least 90% of
  potatoes keep their full-size per-potato grade.
- **Run:** Kaggle kernel `taksimulhasandip/krishinexus-potato-size-sweep` (private, CPU, v1, 34 min).
  - It took all 477 ROI validation photos; the defect test split stayed closed.
  - Each potato was cut out by its hand-drawn outline exactly as `_cascade` cuts one. The app's own `green_boost` and
    `fill_outlines` were copied in by `inspect.getsource`.
  - Stage 2 graded each potato at full size, then again with the photo shrunk (Lanczos + JPEG 90) to 48–768 px.
  - Notebook: `training/kaggle/krishinexus_potato_size_sweep_kaggle.ipynb`, generated by
    `scratchpad/gen_sizesweep_nb.py`.
  - Local test `scratchpad/test_sizesweep_nb.py` runs the cells on the six samples. Given the app's stage-1 outline
    and box, the notebook's cut matches the app's defect area to the rounding on all six.
- **Result:** 645 potatoes; grades kept 0.406 at 48 px, 0.690 at 128, 0.823 at 256, 0.892 at 512, 0.923 at 768.
  - The threshold is **768 px**.
  - Below about 192 px grades mostly turn milder, because defects vanish. Above that, changes go both ways.
  - Rot is the most fragile defect: 11 of 67 rotten potatoes lose it even at 768 px.
  - Full table in TRAINING_PLAN §8. Report in `training/runs/kaggle-cpu-2026-11-09-sizesweep/size_sweep.json`,
    installed as `backend/models/yolo/run2/size_sweep.json` (git-ignored there).
- **Change:**
  - `GradeCropResult.warnings` (default `[]`).
  - `optical_grader.size_warning` reads `min_potato_px` and the per-width numbers from the installed report. It is
    never typed in.
  - `grade()` turns each box's `diameter_mm` back into pixels (× image width / `frame_width_mm`). If any potato is
    narrower than the threshold, it adds one warning: how many potatoes are under the threshold, the smallest width,
    and the measured share of grades kept at the tested width nearest below it. The warning advises close-ups of a
    few potatoes at a time.
  - Frontend: `GradeCropResult.warnings` in `api/client.ts`; `warnings: []` in the offline fallback; `CertificateCard`
    renders each as an amber `role="note"` with a `TriangleAlert` icon under the grade.
  - The warning was not in the signed certificate payload at first; the next entry signs it.
- **Checked:**
  - `test_yolo_cascade.py` gained `size_warning` asserts against a stand-in report (no report, none small, below the
    smallest tested width, nearest tested width). It passes.
  - API after a backend restart:
    - close-up 0762 at 150 mm: no warning;
    - 0762 shrunk to 1000 px (potato 431 px): "87% of 638" at 384 px;
    - scatter at 1.5 m: "36 of 36 ... smallest is 83 px ... 47% of 645" at 64 px.
  - Browser: the scatter at "Heap, 1.5 m" shows the amber note on its Grade-C certificate; the grade request returned
    200. The staged test photo was deleted.
  - `tsc --noEmit` passes.
- **Limits:** hand-drawn outlines stand in for stage 1's, the photos are shrunk validation photos rather than real
  heaps, and the measure is the per-potato grade, not the lot grade. The warning quotes the smallest potato. A report
  with `min_potato_px: null` would fail in `size_warning` (shortcut noted in the code).

### 2026-11-10 · Size warning signed into the certificate (the user said "Yes, sign it")
- **Change (`edge_node/optical_grader.py`):**
  - `issue_certificate` takes the grade's `warnings` and signs them into the payload.
  - `verify_certificate` returns them in `CertificateVerification.warnings`, only when the hash and the HMAC both
    check. So a forged or edited payload never shows a warning as if it came from this node.
  - Frontend: `WarningNote` (exported from `OpticalGraderCanvas.tsx`) now draws the amber note both in
    `CertificateCard` and in `BuyerBankPortal` under the verification line; `api.verifyCertificate`'s type gained
    `warnings`.
- **Checked:**
  - `test_yolo_cascade.py` asserts the payload's warnings equal the result's and survive verification. A copy
    stripped of its warning reads tampered, with no warnings. It passes.
  - API after a backend restart, 0762 shrunk to 1000 px: verify by ID returns the same warning; the stripped
    certificate reads tampered with none. The full-size close-up has none, and an unknown ID still returns 404.
  - Browser `/os/market`: underwrite, then Verify HMAC reads valid with no note. That certificate is the voice
    pipeline's sample-sweep grade, which never carries a size warning.
  - `tsc --noEmit` passes.
- **Gap:** after an underwrite the portal verifies the pipeline's own certificate. A photo grade's warning reaches
  the portal only when the pipeline has no edge certificate, because the farmer app doesn't link its photo grade
  into the loan pipeline (`harvest_metrics.edge_certificate_id` is supported by the backend but not sent). Closed by
  the next entry.

### 2026-11-10 · Photo grade linked into the loan (the user said "Yes, link it")
- **Why:** the buyer portal verified the loan pipeline's own sample-sweep certificate, so a photo's signed size
  warning never reached a buyer.
- **Change:**
  - `agents/supervisor.py`: `VoiceInteractRequest.edge_certificate_id`. When it is set, `voice_interact` looks the
    certificate up on this node and checks it is the spoken crop. It builds the lot's `HarvestMetrics` from the
    certificate's signed payload metrics, so client-sent numbers are ignored.
  - An unknown ID (the node keeps certificates in memory until it restarts) or another crop raises
    `ToolExecutionError`, and the API returns 422 "... grade the photo again".
  - `lot_metrics()` now builds the metrics for both the photo link and the preset sweep.
  - `FarmerZeroUIApp.runVoice`: a photo grade still on screen for the same crop is sent as `edge_certificate_id`
    (sample scans still send `grade_sample_preset`).
  - `BuyerBankPortal.underwrite` sends the last photo grade's certificate when it is Cardinal Potato (the crop of its
    fixed request), else the old `high_grade_harvest` preset.
  - `VoiceInteractBody.edge_certificate_id` in `api/client.ts`.
- **Checked:**
  - `scratchpad/test_photo_link.py` against the API:
    - with a Cardinal photo certificate (0762 shrunk to 1000 px) the loan certificate carries its ID and its metrics
      (fake client metrics ignored), and is Grade A with credit score 712;
    - verifying it returns the photo's warning;
    - an unknown ID and a Diamant certificate for the Cardinal lot are refused with 422.
  - Browser: in `/os/field` grade the photo, switch inside the app to `/os/market`, underwrite, then Verify HMAC
    shows "DQC-EDGE-CAR-…: issued by this edge node · payload hash valid · signature valid" and the amber size
    warning. Rahim Mia's preset, run right after a photo grade, sent the photo's certificate. Its
    `harvest_metrics_input` and loan certificate name it (YOLO two-stage, 1 detection).
  - `tsc --noEmit` passes. The staged test photo was deleted.
- **Note:** `scanDone` is the farmer page's local state. Leaving the page and coming back hides the last grade and
  stops linking it; that was already true of sample scans.

### 2026-11-10 · Bangla advisor v5: freely worded questions, training started (the user said "Yes, start v5")
- **Why:** the deployed v4 model only handles questions in its training templates. Asked through the app on
  2026-11-09, a short store-or-sell question got a made-up trace, and a free-form flood question echoed the prompt and
  called a 5% breach YELLOW. The app's router also sent free-form store questions to the price tool, and couldn't read
  English or Banglish offers. Full write-up and the targets set before any result: TRAINING_PLAN §6, "Prompts v5".
- **Data (`build_sft_dataset(5)`, `training/prepare_data.py --version 5`, the default now):**
  - questions are drawn from wording banks in `edge_node/sft_wordings.py`: colloquial Bangla, Rangpuri, Bogura,
    Sylheti, Banglish and English, with v4's template included;
  - the arbitrage tool result carries the breaker's seven inputs;
  - 4,800 rows: train 3,638, val 274, test 888; jsonl sha256 `e35ace55…96fe9`;
  - test subsets: `iid` 221, `ood_wording` 239, `ood_dialect` 200, `ood_months` 178, `ood_upazila` 50.
- **Held-out wordings:** 32 test-only wordings (`edge_node/sft_heldout_wordings.json`), 8 per task. A separate agent
  wrote them from the task and slot descriptions only, told not to open the repo. I copied the file in without reading
  the templates. Never tune anything against them.
- **v4 untouched:** `PROMPT_VERSION = 4` keeps the app on v4 prompts. `build_sft_dataset(4)` still gives sha
  `794becfc…87a1`, and all 641 v4 test questions still route as before. The API still reports the v4 data.
- **Router** (`_tool_result`, `_stated_numbers`, `_STORE_WORDS`): reads many more phrasings of the numbers, plus store
  words, mm/dB readings and English months. `bangla_voice._offer` also reads "taka" and "tk", and the lexicon knows
  "diamond".
  - It rebuilds every train/val tool result from the question alone: 3,912 of 3,912.
  - **Target 5, measured once:** 212 of 239 held-out-wording questions routed correctly (0.887 ≥ 0.80). Negotiation
    66/66, storage 92/92, arbitrage 33/48 (mostly the rot rate), flood 21/33 (stated readings missed). The router is
    frozen against these wordings.
- **Checks** (`scratchpad/check_v5.py`):
  - every v5 row re-renders from its template, replays through the engines, and has a label that follows from the prompt;
  - the scorer self-tests pass on v5;
  - the regenerated notebook passes its CPU checks;
  - the prompt-blind baseline meets none of the eight targets.
- **Kaggle:**
  - new private dataset `taksimulhasandip/krishinexus-bangla-agri-sft-v5` (card in `scratchpad/card_sft_v5.md`);
  - kernel `krishinexus-bangla-lora-training` version 3 started at 02:37. Adapter `krishi-bangla-lora-v2`. The notebook
    now also scores the exported Q8_0 GGUF through Ollama on Kaggle (`gguf_eval_report.json`).
  - It runs alongside Whisper, which is still running.
- **Also:** the `/docs` depth matrix said the app serves a Q4_K_M GGUF. It now says Q8_0, checked in the browser. The
  backend was restarted on the new code: a free-form store question now reaches the breaker. The v4 model's trace is
  still garbled there, which is the gap v5 targets.
- **Baseline measured (pre-registered):** the deployed v4 Q8_0 model on the v5 test split, through local Ollama: 33.6 min,
  56.6 tok/s. Full table in TRAINING_PLAN §6.
  - Flood alert accuracy 0.414 overall and 0.303 on held-out wordings; it was 1.000 on v4's own test.
  - Negotiation 0.741 overall and 0.576 on held-out wordings.
  - Storage citation 0.778.
  - Arbitrage 0.410, but those rows are outside its format (the inputs are in the tool result).
  - Predictions are in `scratchpad/v5baseline/`.
- **Next:**
  - record kernel v3's results against targets 1–4;
  - if they are met, ask the user before downloading the ~1.6 GB GGUF;
  - then set `PROMPT_VERSION = 5`, install `gguf_eval_report.json`, and re-ask the three dev questions in the app.

### 2026-11-10 · Model 4, Bangla Whisper: measured, meets 2 of 3 targets
- **Run:** kernel `krishinexus-bangla-whisper-training` v4 (T4) finished at 03:54, inside Kaggle's 12-hour limit.
  - Training (3,000 steps) took 533 min, against the 4–5 h estimated.
  - Validation WER fell at every check, from 0.555 to 0.418, so the last checkpoint was used.
  - Reports are in `training/runs/kaggle-t4-2026-11-10-whisper/`; predictions and the log are in
    `scratchpad/downloads/whisper-v4/`. The model files were not downloaded.
- **Measured** (TRAINING_PLAN §8c; targets set before training):
  - WER 0.435 on 2,000 test clips: **meets** ≤ 0.45. The zero-shot base scored 1.164.
  - CER 0.229: **misses** ≤ 0.15. The base scored 1.108.
  - The int8 CTranslate2 model, as the app runs it (CPU, beam 5), scores WER 0.335 and CER 0.110 on the same 300
    clips where the greedy checkpoint scores 0.429 and 0.226. The parity target **is met** (gap −0.094); the gain
    comes from beam search. That 300-clip CER is not the pre-registered measure.
  - 10.3 s per clip on Kaggle's CPU. No greedy transcript is empty or runaway.
- **Not wired:** the app needs `pip install faster-whisper` (the backend venv has neither it nor ctranslate2 or av;
  Python 3.14 wheel support is unchecked), the ~250 MB CT2 folder `krishi-whisper-bn-v1-ct2-int8/`, and
  `KNX_WHISPER_MODEL` set to that folder. The user is being asked, because CER missed its target.

### 2026-11-10 · Bangla advisor v5 (`krishi-bangla-lora-v2`): measured, misses only storage citation
- **Run:** kernel `krishinexus-bangla-lora-training` v3 finished at 04:38.
  - 684 steps took 72.5 min on a T4; validation loss fell to 0.00046.
  - The Q8_0 GGUF exported and was scored through Ollama on Kaggle: 81.9 tok/s, 844 of 888 answers identical to the
    4-bit model's.
  - Reports are in `training/runs/kaggle-t4-2026-11-10-lora-v5/`; predictions are in `scratchpad/downloads/lora-v5/`.
  - The adapter and GGUF are **not downloaded**.
- **Targets** (TRAINING_PLAN §6, table):
  - 7 of the 8 metrics meet their target in all four checks: the full test split, held-out wordings, training
    wordings, and the GGUF.
  - Negotiation 0.991, held-out 0.985, GGUF 0.988. Arbitrage verdict and trace 1.000 everywhere. Flood alert 0.982,
    held-out 1.000, GGUF 0.964.
  - **Storage citation misses everywhere:** 0.789 overall, 0.717 held-out, 0.864 training wordings, 0.806 GGUF.
- **Against the deployed v4 model,** both as GGUFs on the v5 test split: every metric is higher. Flood alerts
  0.414 → 0.964, negotiation 0.741 → 0.988, arbitrage 0.410 → 1.000, storage citation only 0.778 → 0.806.
- **Diagnosis:** every storage miss cites one of the three passages shown. 18 of the 35 misses are gold
  `BARI-CHILI-01`, the "pre-cooling" document whose sentences are about temperature and chilling injury, and the model
  cites the brinjal document instead (the v4 label noise). Bangla-only questions miss 29% against 13%.
- **Not shipped:** by the rule set before training, it ships only if targets 1–4 are met. Shipping anyway is the
  user's call, asked on 2026-11-10. Shipping means a ~1.6 GB GGUF download, `ollama create`, `PROMPT_VERSION = 5`,
  and installing both reports.

### 2026-11-10 · Bangla advisor v5 shipped (the user said "Yes, ship v5")
- **Decision:** shipped despite the storage citation miss (0.806 against 0.90). The pre-registered rule would have held
  it back, so the miss is on record in TRAINING_PLAN §6. It beats v1 on every metric of the v5 test.
- **Files:**
  - `backend/models/lora/krishi-bangla-q8_0.gguf` is v5: 1,646,572,704 bytes, sha256 `069293ff…8e3b`.
  - `krishi-bangla-lora-v2/` holds the adapter and `eval_report.json`; `training_args.bin` was not downloaded.
  - `gguf_eval_report.json` is v5's, from the Kaggle Ollama scoring; it is to be replaced by the local re-score.
  - v1 rollback: `krishi-bangla-v4-q8_0.gguf`, `gguf_eval_report_v4.json`, `Modelfile.v4`, and the Ollama tag
    `krishi-bangla:v4`.
- **Ollama:** `krishi-bangla:latest` now has the layer `sha256-069293ff…`, the file's own hash.
- **Code:**
  - `PROMPT_VERSION = 5`.
  - The registry's adapter is `krishi-bangla-lora-v2`, and `lora_adapter_spec` reads that name.
  - The `main.py` route list, `fallback.ts` (v2, 4,800) and the `/docs` Fine-tuning row are updated.
- **Verified:**
  - Backend restarted: `/edge/local-models` reports v2 `adapter_present`, 4,800 examples, sha `e35ace55…`.
  - `/edge/local-inference`, offline: all five dev questions are correct, at about 57 tok/s. The Tahirpur flood
    question gives "৪% (GREEN)". The 4,000 kg store question gives the full trace, ΔΠ −36,008, ALLOW_SPOT_SALE.
  - Browser `/docs` → Ollama & LoRA: the score table (storage citation amber in both columns) and "Ask the fine-tuned
    model" answering live (screenshot taken). `tsc` passes.
- **Kaggle:** the private v5 dataset card is republished with the measured results. The live card is checked: 5,428
  chars, not truncated.
- **Also:** `memory-graph.jsonl` is updated (Latest metrics, Next steps, Known gaps, Phase 9), the HOW_TO_TRAIN model
  table too, and the MEMORY status summary is rewritten for 2026-11-10.
- **Local re-score** (RTX 3050, 35.2 min, 55.7 tok/s): negotiation 0.988, arbitrage 1.000, flood 0.955 (Kaggle T4
  0.964), storage citation 0.800. 874 of 888 answers are identical to Kaggle's GGUF answers.
  - Installed as `backend/models/lora/gguf_eval_report.json`, so the API's deployed column now reads 0.955 / 0.8.
  - Recorded in `training/runs/local-ollama-2026-11-10-v5/`.

### 2026-11-10 · Published to GitHub (the user said "Commit and push")
- **Synced** `krishinexus-os` into the mirror `Claude to push`.
  - Method: robocopy `/MIR` for `backend`, `frontend` and `training`, plus the root docs (AGENTS, CLAUDE, MEMORY,
    TRAINING_PLAN, memory-graph, docker-compose, .env.example).
  - Excluded: `backend/models/`, `training/data/`, `.venv`, `node_modules`, `__pycache__`, `.state`, caches, `*.pyc`
    and `.env`.
  - A `/L` dry run first: 13 backend, 10 frontend and 45 training files changed, nothing to delete.
- **README** (mirror only): a "Trained models" section with each model's measured scores and misses; "What is real and
  what is simulated" and the layout corrected. It had still said nothing was trained.
- **Checked before committing:**
  - 76 files, +50,081/−488; the largest is the 323 KB size-sweep report.
  - Secret scan over the staged diff: no tokens. The only hit is a doc line naming where `Kaggle Token.txt` lives,
    with no value. The user's email does not appear.
  - The `backend/models/` ignore rule is committed.
- **Commit** `cc65d8e` "Phase 9 training: four trained models, freely worded Bangla questions": author and committer
  HTanvir0011 <hossin23105101466@diu.edu.bd>, no AI trailer.
- **Pushed** `c2eabe2..cc65d8e` to `main` through `gh auth git-credential`. GitHub's API shows the commit with 76
  files, and the public repo lists the v5 run reports.
- **Note:** the published docs and notebooks now name the Kaggle account (`taksimulhasandip`). Its datasets and
  kernels stay private.

### 2026-11-10 · Bangla Whisper installed (the user said "Yes, install Whisper")
- **Installed:**
  - `faster-whisper` 1.2.1 in `backend/.venv`; all dependencies had Python 3.14 wheels.
  - The int8 CT2 model from the Kaggle run, in `backend/models/whisper/krishi-whisper-bn-v1-ct2-int8/` (244.6 MB
    `model.bin`, git-ignored).
  - It stays optional: commented in `requirements.txt` and not in the lock, like ultralytics.
- **Code:**
  - `bangla_voice.WHISPER_DIR` is the default when `KNX_WHISPER_MODEL` is unset.
  - `_decode_16k_mono` decodes audio with PyAV itself, because faster-whisper 1.2.1 passes `metadata_errors`, which
    PyAV 19 rejects (it was a 500). Undecodable audio is now a 422.
  - The STT label shows the folder name, not the full path.
  - Frontend: `lib/speech.recordOnce` (MediaRecorder). `FarmerZeroUIApp.toggleMic` records and sends `audio_base64`
    when offline or without Web Speech; `setHeard` shows Whisper's transcript. `VoiceInteractBody.audio_base64`.
  - The `/docs` Multimodal row is **Live**, with the measured caveats. No row is Partial now.
- **Found:** the Kaggle Whisper evaluation used `max_new_tokens=128` (about 70 Bangla characters).
  - 304 of 2,000 greedy transcripts are cut short; the longest is 70 chars, while 146 references exceed 100.
  - The recorded WER/CER understate the model. The earlier "errors spread through the text" reading was wrong.
  - TRAINING_PLAN §8c is corrected; the pre-registered verdicts stand, and a capless re-score was not run.
- **Verified:**
  - Six Common Voice test clips through `/edge/voice-interact`: WER 0.200, CER 0.095 (the notebook's scorer, 70 words;
    a smoke check), 7–12 s per request on the CPU.
  - A WebM/Opus clip (MediaRecorder's format) transcribed exactly.
  - In the browser, offline mode with a recorded clip as a stubbed microphone: the farmer app showed Whisper's exact
    transcript. No real microphone was used.
  - Regression 100/100; `tsc` passes. The staged clip was deleted, the stub reloaded away, and online mode restored.

### 2026-11-10 · Whisper install pushed (the user said "Yes, push")
- Mirror sync as before: a `/L` dry run showed 12 files, nothing to delete, plus the mirror README's Whisper row.
- 13 files, +189/−35. The secret scan was clean, and no audio, weights or test clips were staged.
- Commit `39c3dad` "Install Bangla Whisper: offline speech-to-text on the kiosk": author and committer HTanvir0011, no
  AI trailer. Pushed `cc65d8e..39c3dad` to `main`; the GitHub API shows it with 13 files.

### 2026-11-10 · SFT prompts v6 for storage citation, training started (the user said "Fix storage citation")
- **Cause** (seen in v4 and v5): each storage question asked about its document's first topic, while the answer was one
  sentence of it. For example, `BARI-CHILI-01`'s chilling-injury sentence was asked as "pre-cooling"; 18 of v5's 35
  misses were that document.
- **Fix:**
  - `sft_wordings.SENTENCE_TOPICS` gives all 60 knowledge sentences their own subject, in English and in Bangla, unique
    in each language (asserted at import).
  - `build_sft_dataset(6)` asks each storage question about its sentence's subject.
  - Storage puts 20% of its sentences in test (9 unseen sentences, 180 rows).
  - The seed (20261111) and salt (`split-v6`) are fresh. Everything else is as in v5; v4 and v5 still regenerate byte
    for byte.
- **Data:** 4,800 rows (3,598 / 318 / 884); sha `c4f21eb9…20ee`.
- **Checks** (`check_v5.py heldout 6`): every row replays and every storage question names its gold sentence's subject.
  Routing is 100% on train, val, iid and the OOD subsets, and 0.883 on held-out wordings (router unchanged). The
  prompt-blind baseline's storage citation is 0.000.
- **Pre-registered** (TRAINING_PLAN §6, "Prompts v6"): the eight targets on the full v6 test, `ood_wording`, `iid` and
  the GGUF. v3 ships only if all are met and the user approves the download.
- **Kaggle:** private dataset `krishinexus-bangla-agri-sft-v6`. Kernel `krishinexus-bangla-lora-training` v4 started
  at 12:28 with adapter `krishi-bangla-lora-v3`; a watcher is on it.
- **Running locally:** the deployed v2 model scored on the v6 test (baseline, `scratchpad/v6baseline/`).

### 2026-11-10 · v6 (`krishi-bangla-lora-v3`) measured: storage fixed, store-or-sell verdict regressed, not shipped
- **Run:** kernel v4 completed: 675 steps in 64.5 min, checkpoint 550; Q8_0 GGUF scored through Ollama on Kaggle.
  Reports are in `training/runs/kaggle-t4-2026-11-10-lora-v6/`.
- **Storage citation meets 0.90 everywhere:** 0.928 all, 0.919 held-out wordings, 0.936 iid, 0.911 GGUF (v5: 0.789 to
  0.864).
- **Arbitrage verdict misses:** 0.891 all, 0.857 held-out wordings, 0.900 iid, 0.895 GGUF (v5: 1.000).
  - All 27 misses are BLOCK_SPOT_SALE versus ALLOW_STORAGE, which only differ in today's price against the Tk 15 floor.
  - 17 of them are the unseen 7-month holding; the traces are all right.
  - All 996 gold labels follow the rule, so these are model errors.
- **Not shipped**, per the pre-registered rule; v2 stays in the app.
- **Next (proposed to the user):** v7, where the breaker's tool result states whether today's price is below the
  floor, so the model reads the comparison instead of computing it; retrain on a fresh batch.
- **Running:** the deployed v2 scored on the v6 test (baseline), output to the new session scratchpad `v6baseline/`.

### 2026-11-10 · SFT prompts v7, training started (the user said "Yes, train v7")
- **Change:** the store-or-sell tool result gains `spot_below_floor`, the breaker's own `ArbitrageCheckResult` flag, so
  the verdict follows from two stated values (the flag and ΔΠ's sign). v6 got that comparison wrong in 11% of rows.
  - `_breaker_payload` builds the result for both the data and the router.
  - The router adds the flag only for `PROMPT_VERSION >= 7`, so the deployed v2 is unchanged.
  - Storage subjects, wordings and router are as in v6.
- **Data:** 4,800 rows (3,454 / 322 / 1,024; 14 unseen storage sentences); sha `394c20da…c593`. v4, v5 and v6 still
  regenerate byte for byte.
- **Checks** (`check_v5.py heldout 7`): every row replays, every flag equals the breaker's, and every verdict follows
  from flag and ΔΠ. Routing is 100% on train, val, iid and OOD; 0.913 on held-out wordings.
- **Pre-registered:** the eight targets on all, `ood_wording`, `iid` and the GGUF (TRAINING_PLAN §6, "Prompts v7").
- **Kaggle:** private dataset `krishinexus-bangla-agri-sft-v7`; kernel v5 (adapter `krishi-bangla-lora-v4`) queued at
  22:19; a watcher is on it.
- **Still running locally:** v2 scored on the v6 test (baseline for the v6 comparison).

### 2026-11-10 · Phase 10: buyer bids with a 1-tap escrow, transit-heat reroute, compose data services (the user pasted a five-item developer task list: "analyze the scenario and take step to implement")
- **Analysis**, item by item:

  | # | Item | Before | Done |
  |---|---|---|---|
  | 1 | Farmer app UI | built: voice, photo grade, offline mic to Whisper | nothing to add |
  | 2 | Truck pooling, dynamic reroute | pools and dispatch, no reroute | transit-heat reroute |
  | 3 | MCP + pgvector, Neo4j, Redis, n8n in compose | 3 MCP servers; data in process only | compose profile `data` (untested) |
  | 4 | AI stack | Whisper, YOLO11n, Ollama Qwen 2.5 7B (local-llm profile), LangGraph, GraphRAG/CRAG, LLMLingua-2-style compression, Presidio-compatible scrubber all present | nothing to add; the kiosk advisor stays the fine-tuned 1.5B |
  | 5 | Buyer bids, best price, bKash/Nagad escrow | hub ranking by net payout; no processors, bids or escrow | all three |

- **Buyer bids** (`market_bids.bid_board`, `GET /market/bids`):
  - A bid is a hub's modelled price for the lot today. Bids are ranked by net payout after pooled freight, fees and
    transit loss, valid until 23:59 BDT, with `below_cost_floor` against the production-cost floor.
  - It reuses `find_optimal_selling_hub`; nothing is a live feed.
  - Real buyer names such as Chaldal were not used. The hubs keep their generic names.
- **Agro-processors:** 4 hubs in `_FIXED_HUBS` buy what retail refuses. Potato flakes and chips (Munshiganj, Bogura)
  pay wholesale × 0.95 / 0.92 / 0.85 for A / B / C. Chili paste (Tejgaon) pays × 0.85 for grades B and C. The rice
  mill (Kishoreganj) pays Boro at × 0.98 × grade. Fees are 2% + Tk 0.30/kg.
- **Escrow** (`POST /market/bids/lock`):
  - It is **simulated**: no money moves and no wallet API is called.
  - The node recomputes the bid. There is one escrow per farmer and bid, so a second tap returns the same one.
  - The receipt is HMAC-signed, the wallet number is stored masked, and receipts persist in `.state/escrows.json`.
  - A live escrow needs a bKash or Nagad merchant agreement and API credentials.
- **Transit-heat reroute** (`POST /automation/truck-pools/{pool_id}/transit-check`):
  - Shelf life comes from `calculate_dynamic_shelf_life` at the reported truck temperature.
  - The truck is rerouted iff the ETA exceeds 75% of the remaining shelf life. The new buyer is the best net payout
    within that reach (new `max_transit_hours` on the hub tool), and the escrow is locked again there.
  - Shortcut: distances run from the pool's district, not the truck's GPS position.
- **UI:**
  - `BuyerBidsPanel` on `/os/market`: lot controls, the top 6 bids, and a wallet picker with one lock button that
    shows a receipt marked simulated. EN and BN.
  - `TruckPoolMap` on `/os/coop`: a truck-temperature input, a "Check route" button and the latest transit event line.
- **Compose profile `data`:**
  - `data-seed` runs `python -m data_seed` from the backend image (the Dockerfile adds `/app/.seed` owned by uid 10001).
  - `postgres` (pgvector pg17) gets `rag_chunks` plus the n8n database.
  - `neo4j-seed` MERGEs `SupplyChainGraph`.
  - `n8n-import`, `n8n` and `n8n-worker` run queue mode on `redis`.
  - Ports bind to 127.0.0.1; the demo passwords are in `.env.example`.
  - The node does not read these servers back.
- **Verified:**
  - API script (`scratchpad/test_bids_reroute.py`):
    - 9 bids for Cardinal potato grade C from Bogura (400 kg); best is the Bogura chips processor at Tk 38.74/kg net.
    - A lock gives Tk 15,496, number masked; a second tap returns the same escrow.
    - An unknown hub, wallet or number is refused (422).
    - Potato at 38 °C keeps its route (343 h of shelf life).
    - Chili at 38 °C is rerouted from Mirpur DC (7.2 h) to Mahasthangarh Haat Arat (2.0 h).
    - An open pool and 90 °C are refused (422).
  - Browser: the lock shows "Held in escrow Tk 19,747 · bKash 017•••••344 · simulated". The reroute line shows on
    POOL-BOGURA-02 and "Route kept" on POOL-BOGURA-01. No console errors.
  - Regression 100/100. Holdout unchanged (top-1 0.500, top-3 0.848). `tsc` clean.
  - The seed files generate: 19 chunk rows (no duplicate ids), 1 constraint + 19 UNWIND statements covering every
    node and edge, and 2 workflows.
  - The compose file validates against the official compose-spec schema (draft 2020-12): 0 errors, and a copy with 3
    planted errors fails. Every reference resolves. Docker is not installed here, so it never ran.
- **Demo state:** `.state/truck_pools.json` was restored from the pre-test backup, and the test escrows and the
  overflow pool were removed.
- **Docs:** AGENTS/CLAUDE (run table, Docker layout, tree, 3 REST rows, constants), `.env.example`, DepthMatrix notes.
- **Next file:** `training/runs/kaggle-t4-2026-11-10-lora-v7/`, when kernel v5 completes.

### 2026-11-10 · Baseline: the deployed v2 on the v6 test (pre-registered for v6)
- **Run:** local Ollama 0.40.16, Q8_0, 33.8 min. Reports are in
  `training/runs/local-ollama-2026-11-10-v2-on-v6-test/` (TRAINING_PLAN §6).
- **Scores:** all 8 targets met on the full v6 test. Store-or-sell verdict 1.000 (v3: 0.895); storage citation 0.922.
- **Caveat** (`contamination.txt`): 7 of the 9 storage test sentences were in v2's training data. On the 2 it never
  saw, citation is 0.925 over 40 rows, too few sentences to conclude from. No store-or-sell prompt or answer overlaps.
- **Reading:** v3's verdict regression came from training on v6's data, not from the test rows. v7's stated flag
  removes the comparison either way. No rule changes: v2 stays deployed.
