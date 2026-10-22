# AGENTS.md — KrishiNexus OS Architecture Contract

> Read this file and `MEMORY.md` before touching code. `AGENTS.md` (mirrored verbatim as `CLAUDE.md`) is the stable
> contract: architecture, directory tree, API contracts, formulas and dataset constants. `MEMORY.md` is the live
> state tracker and handover log; update it after every phase.

International AI Builders Congress 2026 · Track: **AgriSphere AI → FarmMarket** · Showcase: 26 December 2026, Daffodil International University.

---

## 1. Mission

KrishiNexus OS is an edge-to-cloud multi-agent agricultural operating system for Bangladeshi smallholders. A farmer
speaks in their own dialect (or scans a crop); four agents grade the lot, expose the middleman markup, price cold
storage against a pooled truck sale with the ΔΠ equation, clear 72-hour flood risk and underwrite credit, then
answer in spoken Bangla, online or offline at a union kiosk. It targets three failures:

1. **5-tier syndicate** (Faria → Bepari → Aratdar → Paiker → Retailer) inflating retail prices up to 116%.
2. **Cold-storage quota capture** (77.32% held by traders and plant owners) forcing below-cost distress sales.
3. **Cloud-blinded haor flash floods** destroying Boro rice before harvest.

---

## 2. Non-negotiable engineering rules

- **Zero placeholders.** No `TODO`, `pass`, `// implement later` or empty stubs. Every function has complete
  deterministic logic, real calculations and Bangladeshi fallback data, so the system runs without paid API keys,
  internet or a GPU. (`except ...: pass` is also banned — log or handle instead.)
- **Strict typing.** Backend: Python 3.12+ (venv runs 3.14), FastAPI, Pydantic v2 `BaseModel` / `Field` for every
  schema, tool contract and agent state. Frontend: TypeScript `strict: true`, React, Tailwind, lucide-react, pure Three.js.
- **Authentic Bangladesh seed data.** Real districts, upazilas, crops and BDT (Tk) prices modelled on DAM
  (`market.dam.gov.bd`), BCSA, BARI, BAU, BRRI, DAE, CPD, FFWC and WFP benchmarks (section 7).
- **Integrity rules (established Steps 4–6, do not regress):**
  - Never hard-code evaluation results. Metrics are computed from labelled data; brief targets are shown *beside*
    measured values (`evals/regression_suite.py: TARGETS`).
  - Label simulated or modelled output as such: `inference_backend` (`simulated-video-sweep` / `classical-cv` /
    `ultralytics-yolo`), `telemetry_source` (`measured` / `modelled`), `data_source` (`OPEN_METEO_LIVE` /
    `CLIMATOLOGY_FALLBACK`), offline certificates prefixed `OFFLINE-PREVIEW`.
  - Brief figures with no primary source in the repo are shown as "cited in brief", never as computed results.
  - Untrained artefacts stay labelled untrained (`krishi-bangla-lora-v1.status = dataset_ready_not_trained`).
- **Verify before advancing.** Each phase ends with live endpoint and browser checks, recorded in `MEMORY.md`.

---

## 3. Runtime and ports

| Component | Command (from repo root) | Port / route |
|---|---|---|
| Backend (FastAPI) | `cd backend && .venv/Scripts/python -m uvicorn main:app --port 8000` | `http://localhost:8000`, OpenAPI at `/docs` |
| Frontend (Vite) | `npm --prefix frontend run dev` | `http://localhost:5173`, whitepaper at `/docs` |
| Live agent trace | WebSocket | `ws://localhost:8000/ws/agent-trace?session_id=...` (proxied as `/ws`) |
| MCP stdio servers | `cd backend && python -m mcp_servers.<server_module>` | newline-delimited JSON-RPC on stdin/stdout |
| Local LLM runtimes (optional) | Ollama / llama.cpp / vLLM | `11434` / `8080` / `8001` |
| Full stack in Docker | `docker compose up --build` | same host ports: backend `8000`, frontend (nginx) `5173` |
| + local Ollama | `docker compose --profile local-llm up --build` | `11434`; `ollama-pull` fetches `qwen2.5:7b-instruct-q4_K_M` + `llama3.2:3b-instruct-q4_K_M` (≈6.7 GB) |

Docker layout:
- `backend/Dockerfile`: `python:3.14-slim`, installs the pinned `backend/requirements.lock`, runs as uid 10001, HEALTHCHECK on `GET /health`, named volume `backend-state` at `/app/.state`.
- `frontend/Dockerfile`: `node:24-bookworm-slim` build stage, then `nginx:1.28-alpine`.
- `frontend/nginx.conf` mirrors the Vite proxy (same prefix list plus `openapi.json`, the `/api/` rewrite and the `/ws/` upgrade) with an SPA fallback for `/docs`.
- Compose host ports and the Ollama tag can be overridden in a root `.env` (see `.env.example`); application settings come from `backend/.env` (optional `env_file`).
- `KNX_OLLAMA_HOST` defaults to `http://ollama:11434` in compose; when the profile is off the edge node reports the runtime unreachable and falls back.

Environment (`backend/.env.example`): `KNX_OPEN_METEO_URL`, `KNX_HTTP_TIMEOUT_SECONDS`, `KNX_FORCE_OFFLINE_WEATHER`,
`KNX_RECEIPT_SIGNING_KEY` (HMAC for receipts and certificates), `KNX_CORS_ORIGINS`, `KNX_OLLAMA_HOST`,
`KNX_LLAMACPP_URL`, `KNX_VLLM_URL`; optional model upgrades `KNX_EMBEDDING_MODEL`, `KNX_RERANKER_MODEL`,
`KNX_WHISPER_MODEL`, `KNX_YOLO_WEIGHTS`; LLM keys `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`.
All times are BDT (UTC+06:00, `config.BDT`, `now_bdt()`); no `zoneinfo`/`tzdata` dependency.

Vite proxies `/mcp /rag /edge /agents /automation /guardrails /optimization /prompts /evals /health` and `/ws`
(ws: true) to `:8000`. A new backend prefix **must** be added to `BACKEND_PREFIXES` in `frontend/vite.config.ts` **and**
to the API `location` regex in `frontend/nginx.conf`. Regenerate `backend/requirements.lock` (`pip freeze`) after any
dependency change.

---

## 4. Directory tree (as built)

```text
krishinexus-os/
├── AGENTS.md / CLAUDE.md               # this contract (identical copies)
├── MEMORY.md                           # live state + handover log
├── docker-compose.yml                  # backend + frontend; ollama + ollama-pull under profile local-llm
├── .env.example                        # compose host ports, KNX_OLLAMA_HOST, OLLAMA_IMAGE_TAG
├── backend/
│   ├── requirements.txt                # fastapi uvicorn pydantic httpx numpy python-dotenv websockets networkx langgraph pillow
│   ├── requirements.lock               # exact verified versions (pip freeze) installed by the Docker image
│   ├── Dockerfile · .dockerignore      # python:3.14-slim, non-root, HEALTHCHECK /health
│   ├── .env.example
│   ├── main.py                         # FastAPI app: /mcp /rag /optimization /guardrails /agents /prompts /automation /edge /evals /ws
│   ├── config.py                       # Settings, BDT clock, MODEL_CATALOG, ModelRouter (route_query)
│   ├── schemas/
│   │   ├── mcp_models.py               # 13 tool Input/Output models, JSON-RPC envelopes, anomaly requests
│   │   └── api_models.py               # Step 2 REST request/response models
│   ├── mcp_servers/
│   │   ├── base.py                     # McpServer, ToolSpec, JsonRpcDispatcher, run_stdio, stable_unit, ToolExecutionError
│   │   ├── bd_geo.py                   # districts/upazilas, name resolution, road distance x1.32, bridge tolls
│   │   ├── anomaly_state.py            # ANOMALIES store for judge-injected power cuts / flash floods
│   │   ├── registry.py                 # GATEWAY (13 tools), SERVER_DISPATCHERS, simulate_anomaly
│   │   ├── dam_market_mcp.py           # Server 1 dam-market-mcp (4 tools)
│   │   ├── agri_weather_sar_mcp.py     # Server 2 agri-weather-sar-mcp (5 tools), NETWORK_BLACKOUT ContextVar
│   │   └── coldchain_iot_mcp.py        # Server 3 coldchain-iot-mcp (4 tools), 18 BCSA facilities
│   ├── guardrails/
│   │   ├── pii_scrubber.py             # BanglaPIIScrubber + PIIVault (PII_SCRUBBER)
│   │   └── financial_circuit.py        # FinancialCircuitBreaker: dPi + DAE dosage (CIRCUIT_BREAKER)
│   ├── optimization/token_compressor.py# TokenOptimizer, RollingSummaryMemory, estimate_tokens (TOKEN_OPTIMIZER)
│   ├── rag/
│   │   ├── lexicon.py                  # Bangla/dialect/Banglish concept lexicon, crop & district detection
│   │   ├── knowledge_seed.py           # 18 KnowledgeDoc with contextual headers + 8 GraphRule
│   │   ├── hybrid_retriever.py         # HashingEmbedder(384), SemanticChunker, BM25, RRF, BGEReranker, PGVECTOR_SCHEMA
│   │   ├── graph_rag.py                # SupplyChainGraph (NetworkX, Neo4j-compatible Cypher)
│   │   └── crag_pipeline.py            # HyDEDialectRewriter, CorrectiveRAGEvaluator, CragPipeline (CRAG_PIPELINE)
│   ├── prompts/prompt_registry.py      # versioned XML prompts, DSPyPromptOptimizer, decision rules (PROMPT_REGISTRY)
│   ├── agents/
│   │   ├── state.py                    # KrishiAgentState, AgentTraceEvent and agent output models
│   │   ├── tracing.py                  # TraceBroadcaster (BROADCASTER), TraceRecorder
│   │   ├── vision_grading_agent.py     # Agent 1
│   │   ├── syndicate_bypass_agent.py   # Agent 2
│   │   ├── coldchain_arbitrage_agent.py# Agent 3
│   │   ├── climate_credit_agent.py     # Agent 4
│   │   └── supervisor.py               # LangGraph GRAPH, orchestrate(), voice_interact()
│   ├── automation/workflows.py         # TemporalTruckPoolManager (TRUCK_POOLS), N8nWebhookHandlers (N8N_HANDLERS)
│   ├── edge_node/
│   │   ├── bangla_voice.py             # BanglaVoicePipeline (VOICE_PIPELINE), 5 VOICE_PRESETS, SSML
│   │   ├── optical_grader.py           # OpticalCropGrader (OPTICAL_GRADER), certificates
│   │   └── ollama_local.py             # LocalEdgeInferenceEngine (EDGE_ENGINE), LoRA spec, SFT dataset
│   ├── evals/regression_suite.py       # EvaluationEngine (EVALUATION_ENGINE): metrics + 100-case suite
│   └── .state/truck_pools.json         # runtime only: durable pool state (delete to re-seed)
└── frontend/
    ├── package.json · vite.config.ts · tsconfig.json · index.html
    ├── Dockerfile · .dockerignore · nginx.conf   # node build stage -> nginx serving dist + API/ws proxy
    └── src/
        ├── main.tsx · index.css · App.tsx      # navbar, split-screen judge mode, /docs routing
        ├── api/client.ts · api/fallback.ts     # typed REST + WebSocket client, OFFLINE-PREVIEW fallbacks
        ├── state/store.ts                      # useSyncExternalStore global store + actions
        ├── lib/format.ts · lib/speech.ts · lib/mcpExamples.ts
        ├── components/
        │   ├── ui.tsx · OpticalGraderCanvas.tsx · AgentTraceVisualizer.tsx · TruckPoolMap.tsx · ColdStorage3DTwin.tsx
        │   └── docs/ProvenanceSection.tsx · McpInspectorSection.tsx · DepthMatrixSection.tsx · EvalsSection.tsx · EconomicsSection.tsx
        └── pages/FarmerZeroUIApp.tsx · CommandCenter.tsx · BuyerBankPortal.tsx · DocsPage.tsx
```

---

## 5. MCP servers (JSON-RPC 2.0, protocol `2025-06-18`)

Methods: `initialize`, `notifications/initialized`, `ping`, `tools/list`, `tools/call`. Unknown tool / invalid
arguments → JSON-RPC error `-32602`; domain failures (`ToolExecutionError`) → result with `isError: true`.
Successful calls return `content[0].text` (JSON) **and** `structuredContent` validated against the tool's output model.

| # | Server (transports) | Tool | Input → Output model |
|---|---|---|---|
| 1 | `dam-market-mcp` (streamable-http, stdio) | `get_daily_commodity_spread(crop, district)` | `GetDailyCommoditySpreadInput` → `...Output` |
| 2 | | `detect_syndicate_markup_anomaly(crop, upazila, retail_hub)` | `DetectSyndicateMarkupAnomalyInput` → `...Output` |
| 3 | | `find_optimal_selling_hub(crop, weight_kg, origin_district, grade)` | `FindOptimalSellingHubInput` → `...Output` |
| 4 | | `get_historical_seasonal_curve(crop, month_range)` | `GetHistoricalSeasonalCurveInput` → `...Output` |
| 5 | `agri-weather-sar-mcp` (streamable-http, sse, stdio) | `get_current_weather(latitude, longitude)` | `GetCurrentWeatherInput` → `...Output` |
| 6 | | `get_weather_by_datetime_range(latitude, longitude, start_date, end_date)` (≤7 days) | `GetWeatherByDatetimeRangeInput` → `...Output` |
| 7 | | `calculate_haor_flash_flood_risk(upazila, sar_water_backscatter_db)` | `CalculateHaorFlashFloodRiskInput` → `...Output` |
| 8 | | `compute_crop_vpd_stress(crop, crop_stage, temp_c, rh_pct)` | `ComputeCropVpdStressInput` → `...Output` |
| 9 | | `trigger_early_harvest_window(cluster_id, upazila, urgency_level)` | `TriggerEarlyHarvestWindowInput` → `...Output` |
| 10 | `coldchain-iot-mcp` (streamable-http, stdio) | `query_cold_storage_quota(district, radius_km, tons_needed)` | `QueryColdStorageQuotaInput` → `...Output` |
| 11 | | `get_chamber_telemetry(facility_id, chamber_id)` | `GetChamberTelemetryInput` → `...Output` |
| 12 | | `calculate_dynamic_shelf_life(crop, grade, transit_temp_c, rh_pct)` | `CalculateDynamicShelfLifeInput` → `...Output` |
| 13 | | `reserve_collective_storage_slot(cluster_id, facility_id, tons, farmer_count)` | `ReserveCollectiveStorageSlotInput` → `...Output` |

Shared enums (`schemas/mcp_models.py`): `Crop` (Cardinal Potato, Diamant Potato, Green Chili, Brinjal, Boro Rice),
`Grade` (A/B/C), `HubType`, `AnomalySeverity`, `FloodAlertLevel`, `CropStage`, `UrgencyLevel`, `PowerSource`,
`ReservationStatus`, `WeatherDataSource`. Facility ids `BCSA-[A-Z]{3}-\d{2}`, chambers `CH-\d{2}`.

---

## 6. REST API contract (backend `main.py`)

| Method & path | Request → Response | Step |
|---|---|---|
| `GET /`, `GET /health` | → service info / health | 1 |
| `GET /mcp/servers` | → `list[McpServerDescriptor]` | 1 |
| `GET /mcp/tools?server=` | → `McpToolsListing` | 1 |
| `POST /mcp/call`, `POST /mcp`, `POST /mcp/servers/{server_name}` | JSON-RPC 2.0 (`JsonRpcRequest`) → envelope; per-server endpoint streams SSE when `Accept: text/event-stream` only | 1 |
| `POST /mcp/simulate-anomaly` | `PowerCutAnomalyRequest` \| `FlashFloodAnomalyRequest` (discriminator `anomaly_type`) → `SimulateAnomalyResponse` | 1 |
| `GET /mcp/anomalies`, `DELETE /mcp/anomalies[/{id}]` | → `list[ActiveAnomalyView]` / cleared count | 1 |
| `POST /rag/query` | `RagQueryRequest` → `RagQueryResult` | 2 |
| `POST /rag/graph-traverse` | `GraphTraverseRequest` → `GraphTraversalResult` | 2 |
| `GET /rag/stats` | → retriever + graph stats + `PGVECTOR_SCHEMA` | 2 |
| `POST /optimization/compress` | `CompressRequest` → `CompressResponse` | 2 |
| `GET /optimization/route?task_type&complexity&offline` | → `RoutingDecision` | 2 |
| `POST /guardrails/verify` | `GuardrailVerifyRequest` → `GuardrailVerifyResponse` | 2 |
| `POST /agents/orchestrate` | `OrchestrateRequest` → `OrchestrateResponse` (full `KrishiAgentState`) | 3 |
| `WS /ws/agent-trace?session_id=` | server sends `{type:"hello", replay:[...]}` then `{type:"trace", event: AgentTraceEvent}`; client may send `ping` | 3 |
| `GET /agents/trace-history` | → `list[AgentTraceEvent]` | 3 |
| `GET /prompts/registry?agent&include_xml` | → `RegistryListing` | 3 |
| `GET /automation/truck-pools` | → `list[PoolView]` (includes `lots`) | 3 |
| `POST /automation/truck-pools/join` | `JoinPoolRequest` → `JoinPoolResult` | 3 |
| `POST /automation/truck-pools/reset` | → `list[PoolView]` (re-seeds demo pools) | 3 |
| `POST /automation/n8n/daily-dam-sync` | → `DamSyncReport` | 3 |
| `POST /automation/n8n/hourly-sar-flood-check` | `SarFloodCheckRequest?` → `SarFloodReport` | 3 |
| `GET /automation/n8n/workflows` | → importable n8n workflow JSON | 3 |
| `POST /edge/voice-interact` | `VoiceInteractRequest` → `VoiceInteractResponse` | 4 |
| `GET /edge/voice-presets` | → `list[VoicePreset]` | 4 |
| `POST /edge/grade-crop` | `GradeCropRequest` → `GradeCropResult` | 4 |
| `POST /edge/verify-certificate` | `VerifyCertificateRequest` → `CertificateVerification` | 4 |
| `GET /edge/local-models?hardware_profile` | → `LocalModelsReport` | 4 |
| `POST /edge/local-inference` | `LocalInferenceRequest` → `LocalInferenceResult` | 4 |
| `GET /edge/lora-dataset?category&split&limit&format=json\|jsonl` | → `list[SftExample]` or JSONL | 4 |
| `GET /evals/metrics?refresh` | → `RagasReport` (cached 10 min) | 6 |
| `POST /evals/run-regression` | `RegressionRequest` (`sample_size` 1–20 per category) → `RegressionReport` | 6 |

LangGraph node order (`agents/supervisor.py`): `pii_guardrail → token_compression → crag_retrieval → vision_grading →
syndicate_bypass → coldchain_arbitrage → climate_credit → supervisor_review →(re-plan, max 2)→ coldchain_arbitrage |
voice_synthesizer → END`. `trace_events`, `errors`, `node_path` use `operator.add` reducers.

---

## 7. Dataset constants

### 7.1 From the project brief (cite as "brief"; primary sources not stored in repo)

| Domain | Constant |
|---|---|
| Spoilage | $2.4B annual post-harvest loss; 25–43.5% fruit/vegetable loss: jackfruit 38%, banana 37% (30.8% at trader level), pineapple 27%, mango 24% |
| Syndicate | CPD (July 2026): up to **116%** retail markup across Faria → Bepari → Aratdar → Paiker → Retailer; food = 59% of CPI basket; Aratdars extract **62.35%** of Bepari marketing cost while spending Tk 0 on grading |
| Grading uplift | Sorting, grading and MAP packaging: **+32% (+USD 947)** seasonal smallholder income (BAU) |
| Cold storage | 12–13M MT potato vs 2.7–3.27M MT storage across 300–393 BCSA plants; $430M annual loss; Munshiganj 540,760 MT storage vs 1,000,738 MT harvest |
| Quota capture | Traders **45.0%**, plant owners **32.32%** (= **77.32%** non-farmer), farmers **22.68%** |
| Tariff | BCSA hike 100%: Tk 4–5.50/kg → **Tk 8.00–9.50/kg** (Tk 19–20/kg total in Thakurgaon) |
| Prices | Distress farm-gate **Tk 5–14/kg** vs **Tk 15–20/kg** production cost floor; off-season **Tk 80–90/kg** |
| Chamber | Optimal **48–50°F (9–10°C)**, **92–95% RH**; internal rot 2–9% |
| Flood | 2017 haor Boro loss: Sunamganj **65%**, Kishoreganj **44%**, Netrokona **21%**; Sentinel-1 SAR sees through monsoon cloud (2x more damage detected than manual surveys) |
| Partners | **66 WFP Aggregation Centres** (62 Cox's Bazar, 4 Kurigram), iFarmer, UCB 6% collateral-free agri-credit |

### 7.2 Implemented model constants (source of truth is the code; change both if you change one)

| Constant | Value | Where |
|---|---|---|
| Potato production-cost floor | Tk 15.0/kg (Cardinal and Diamant) | `dam_market_mcp.SEASONAL_CURVES` |
| Syndicate anomaly threshold | markup > 40%; ELEVATED ≥40, SEVERE ≥75, CRITICAL ≥100 | `dam_market_mcp`, prompt param `anomaly_threshold_pct` |
| Tier split | primary margin: Faria 20%, Bepari grosses 80% and spends 70% of it on marketing; Aratdar take = **62.35% of that Bepari marketing cost** (→ Faria 20% · Bepari 45.08% net · Aratdar 34.92%); Aratdar grading spend Tk 0; secondary Paiker 35% · Retailer 65% | `dam_market_mcp.FARIA_SHARE_OF_PRIMARY_MARGIN`, `BEPARI_MARKETING_COST_RATIO`, `ARATDAR_SHARE_OF_BEPARI_MARKETING_COST`, `PRIMARY/SECONDARY_MARGIN_SPLIT` |
| Bepari cost lines | share of Bepari marketing cost: Aratdar commission/khajna 62.35%, freight 18%, labour 6.5%, wastage 5.25%, bags 4.4%, tolls/chanda 3.5% | `dam_market_mcp.BEPARI_OWN_COST_LINES` |
| Pooled truck | 5,000 kg; Tk 68/km + Tk 1,500/trip + tolls (Jamuna Tk 1,800, Padma Tk 2,800, Lalon Shah Tk 480); + Tk 0.10/kg pooling fee; 35 km/h + 1.5 h loading | `dam_market_mcp`, `bd_geo` |
| Road distance | haversine × 1.32 circuity | `bd_geo.ROAD_CIRCUITY_FACTOR` |
| Selling hubs | 7 arats, 3 urban retail DCs, 66 WFP centres (62 Cox's Bazar + 4 Kurigram) | `dam_market_mcp.SELLING_HUBS`, `WFP_CENTRES_BY_DISTRICT` |
| Distress price (regression) | non-control circuit-breaker cases sample P_spot uniformly in Tk 5–14/kg | `regression_suite.DISTRESS_SPOT_RANGE_TK` |
| Knowledge seed | 18 passages (incl. `AGRI-FIN-01` for UCB/iFarmer); RAG eval set 19 questions | `rag/knowledge_seed.KNOWLEDGE_DOCS`, `regression_suite.RAG_EVAL_SET` |
| BCSA facilities | 18 seeded (Munshiganj 5, Rangpur 4, Bogura 5, Thakurgaon 4); tariff Tk 8.00–9.50; chamber ≈1,800 MT | `coldchain_iot_mcp.FACILITIES` |
| District storage gap | Munshiganj 540,760 / 1,000,738 MT; Rangpur 412,300 / 1,086,500; Bogura 368,900 / 1,245,200; Thakurgaon 214,700 / 612,400 | `coldchain_iot_mcp.DISTRICT_STORAGE_STATS` |
| Chamber setpoint | 9.5°C; outage drift τ = 36 h toward ambient; CO₂ +380 ppm/h | `coldchain_iot_mcp` |
| Haor trigger rainfall (72 h) | Sunamganj 180 mm, Netrokona 200 mm, Kishoreganj 230 mm; catchments Sohra, Garo Hills, Barak | `agri_weather_sar_mcp.HAOR_DISTRICTS` |
| Flood alert bands | RED ≥70%, ORANGE ≥45%, YELLOW ≥20% | tool + prompt `ffwc-trigger` |
| Boro yield | 4.2 t/ha | `agri_weather_sar_mcp` |
| Grade thresholds (`bari-standard`) | A: uniformity ≥90%, bruising ≤3%, rot ≤2%; B: ≥75%, ≤8%, ≤5%; else C | `prompt_registry.VISION_VARIANTS` |
| Warehouse-receipt credit (circuit breaker) | LTV 70%, 9% p.a., storage search radius 80 km | `financial_circuit` |
| Agent 4 credit | 6% p.a., cap Tk 50,000, LTV 60% (≥750) / 50% (≥700) / 40% (≥650) | `climate_credit_agent` |
| Truck pool | capacity 5,000 kg, union radius 5 km, deadline 8 h, auto-dispatch at ≥80% fill | `automation/workflows` |
| Units | 1 mon/maund = 40 kg, bosta = 50 kg, ser = 0.933 kg, palla = 5 kg; acre 0.4047 ha, bigha 0.1338 ha, shotok 0.004047 ha | `edge_node/bangla_voice` |

---

## 8. Formulas

**Net farmer surplus (circuit-breaker, Agent 3):**

    ΔΠ = [Q(1 − λ_rot)·E[P_future] − Q(C_storage + C_handling) − C_transport_storage] − [Q·P_spot − C_transport_market]
    break-even E[P] = (Q·P_spot − C_tm + Q(C_s + C_h) + C_ts) / (Q(1 − λ_rot))

Circuit-breaker: BLOCK spot sale iff `P_spot < floor` **and** open smallholder quota ≥ Q **and** ΔΠ > 0; then enforce
storage + warehouse-receipt credit. Agent 3 also blocks a below-floor Faria offer when the pooled B2B net exceeds the
floor, evaluates releases at +30/+60/+90 days (E[P] = DAM-modelled farm-gate price on the release date) and reserves a
slot only when storing beats the pooled sale **and** the chamber is in band.

**Markup:** `(retail − grower) / grower × 100`; fair markup per crop (potato 35%, chili 45%, brinjal 42%, rice 22%).

**Aratdar take:** `M = wholesale − grower`; `C_bepari = (1 − 0.20) × M × 0.70`; `aratdar_take = 0.6235 × C_bepari`;
Bepari ladder margin = `0.80M − aratdar_take` (own costs = `0.3765 × C_bepari`); bypass uplift =
`Faria + Bepari ladder margins − pooled freight/kg` (the pooled lot still pays the Aratdar at the arat).

**Pooled freight:** `trip = road_km × 68 + 1,500 + tolls`; `freight/kg = trip / 5,000 + 0.10`;
`net/kg = hub_price × (1 − transit_loss%) − hub_fees − freight/kg` (excess over hub intake cap valued at farm-gate).

**Haor breach probability:** `w = 1 / (1 + e^((dB + 16.5)/1.6))`, `r = R72 / trigger`,
`z = −5.0 + 3.2r + 2.6w + 2.0·vulnerability + 1.2·seasonal_exposure`, `p = 1 / (1 + e^−z)`;
expected Boro loss = benchmark × p (`breach_probability()` in `agri_weather_sar_mcp`).

**VPD (Tetens / Magnus):** `SVP = 0.6108·e^(17.27T/(T+237.3))`, `AVP = SVP·RH/100`, `VPD = SVP − AVP`;
fungal risk = `100 · max(humidity_sigmoid, wetness_sigmoid) · e^(−((T−T_opt)/σ)²) · stage_multiplier`.

**Shelf life (Q10):** `remaining = ref_hours · Q10^((T_ref − T)/10) · humidity_factor · grade_factor · chill_factor`;
`λ_rot = 0.012 + 0.078 · stress^0.85`, `stress = clip(1 − remaining/ref_hours, 0, 1)` ∈ [0.012, 0.09].

**Chamber rot risk:** `0.6 + 1.8·max(0, T−10)^1.3 + 2.5·max(0, RH−96) + 0.002·max(0, CO₂−3000) + 0.4·outage_h` (cap 95%).

**Credit score (Agent 4, 300–850):** `300 + grade(≤120) + market_linkage(≤110) + collateral(≤100) + climate(≤120) +
agronomic(≤60) + verified_identity(≤40)`, climate = `(1 − p_flood) × 120`.

**Retrieval:** BM25 (k1 1.5, b 0.75) + 384-dim hashing embeddings, fused with RRF (k = 60) + metadata boost, reranked
by a logistic cross-feature reranker. CRAG chunk confidence = `0.5·rerank + 0.3·intent_coverage + 0.2·entity_match`;
overall = `0.6·best + 0.4·coverage`; CORRECT ≥ 0.70, AMBIGUOUS ≥ 0.45; below 0.70 → rewrite + re-retrieve + MCP augmentation.

**Query intents (`crag_pipeline.detect_intents`):**
- Signals are the lexicon concepts plus the question's own English words. "pre-harvest", "post-harvest" and "after harvest" are removed before matching, so they don't trigger HARVEST.
- The intents are STORAGE_CONDITIONS, STORAGE_ACCESS, SELLING_CHANNEL, PRICE, DISEASE, PESTICIDE_SAFETY, FLOOD, HARVEST, CREDIT and TRANSPORT, falling back to GENERAL.
- "Cold storage" names a place and never triggers STORAGE_CONDITIONS by itself. That intent needs a condition word: temperature, humidity, store, rot, spoilage, cooling, ventilation, chilling or curing.
- STORAGE_ACCESS (quota, tariff, fee, rent, hike, cost, space, capacity, booking, bcsa) counts only when cold, storage or BCSA is also present (`INTENT_CONTEXT`), so truck rent stays TRANSPORT.
- Each intent drives the formal query, the HyDE passage (the dense query) and the MCP augmentation. Both storage intents call `query_cold_storage_quota`.

**Prompt optimiser score:** `0.5·decision_accuracy + 0.3·json_validity + 0.1·label_coverage + 0.1·token_efficiency`;
versions `v1.0` → `v1.2-dspy-optimized`; agents read decision parameters from the active version.

---

## 9. Conventions

- Tools are `async def name(params: <Input>) -> <Output>` registered with `@server.tool(...)`; the docstring is the
  MCP tool description. Raise `ToolExecutionError` for domain errors.
- Determinism: `stable_unit(*parts)` (SHA-256) or seeded `numpy.random.default_rng`; never unseeded randomness.
- Offline: wrap a request in `NETWORK_BLACKOUT.set(True)` to force climatology weather (per-request ContextVar).
- Agents return `{"<plan field>": ..., "prompt_versions": {...}, "trace_events": trace.drain()}`; MCP calls go through
  `TraceRecorder.mcp(...)` so every call is timed and streamed.
- Frontend reads/writes shared state only through `state/store.ts` (`useAppState(selector)`; selectors return
  existing references). Network calls go through `api/client.ts`; `withFallback` masks only network/5xx failures.
- Shell heredocs fail on apostrophes in this environment's Bash tool; append to files with the editor instead.
