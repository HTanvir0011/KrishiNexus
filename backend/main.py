"""KrishiNexus OS backend — FastAPI entrypoint (Step 1: MCP foundation).

Endpoints
---------
GET    /mcp/servers                  The 3 MCP servers, transports and endpoints
GET    /mcp/tools                    All 13 tools with JSON Schema input/output contracts
POST   /mcp/call                     JSON-RPC 2.0 gateway (tools/call, tools/list, initialize, ping)
POST   /mcp                          Same gateway at the conventional Streamable HTTP path
POST   /mcp/servers/{server_name}    Per-server JSON-RPC 2.0 endpoint (JSON or SSE response)
POST   /mcp/simulate-anomaly         Inject a cold-chamber power cut or haor flash flood (live demo)
GET    /mcp/anomalies                Active injected anomalies
DELETE /mcp/anomalies[/{id}]         Clear injected anomalies
POST   /rag/query                    HyDE dialect rewrite + hybrid retrieval + GraphRAG + CRAG
POST   /rag/graph-traverse           Multi-hop Upazila -> Crop -> ColdStorage -> Corridor -> Market paths
GET    /rag/stats                    Index, graph and pgvector schema
POST   /optimization/compress        LLMLingua-2-style compression, dedup and provider cache payloads
GET    /optimization/route           Cheap-to-reasoning model routing decision
POST   /guardrails/verify            PII scrub + dPi financial and agronomic circuit-breakers
POST   /agents/orchestrate           LangGraph supervisor over the 4 specialist agents
WS     /ws/agent-trace               Live agent trace stream (optional ?session_id=...)
GET    /agents/trace-history         Recent trace events (optional ?session_id=...)
GET    /prompts/registry             Versioned XML prompts, DSPy-style optimisation scores and diffs
GET    /automation/truck-pools       Durable 5-ton union truck pools
POST   /automation/truck-pools/join  Add a micro-lot to a pool (auto-dispatch + escrow at 5,000 kg)
POST   /automation/truck-pools/reset Re-seed the demo pools
POST   /automation/n8n/daily-dam-sync          6:00 AM DAM price sync job
POST   /automation/n8n/hourly-sar-flood-check  Hourly Sentinel-1 haor flood job
GET    /automation/n8n/workflows     Importable n8n workflow JSON
POST   /edge/voice-interact          Bangla dialect voice -> PII scrub -> 4 agents (or offline) -> SSML reply
GET    /edge/voice-presets           Five recorded rural farmer requests
POST   /edge/grade-crop              Optical grading with bounding boxes + signed certificate
POST   /edge/verify-certificate      Re-verify a Digital Quality Certificate
GET    /edge/local-models            Ollama / llama.cpp / vLLM runtimes, Q4_K_M telemetry, LoRA registry
POST   /edge/local-inference         On-device generation (live runtime or offline-blackout fallback)
GET    /edge/lora-dataset            krishi-bangla-lora-v1 SFT examples (json or jsonl)
GET    /evals/metrics                Measured RAGAS-style metrics, MCP schema validity, PII recall
POST   /evals/run-regression         Seeded 5-category regression suite (20 per category = 100 cases)

Run:  uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal

from fastapi import Body, FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from agents.state import AgentTraceEvent
from agents.supervisor import (
    OrchestrateRequest,
    OrchestrateResponse,
    VoiceInteractRequest,
    VoiceInteractResponse,
    orchestrate,
    voice_interact,
)
from agents.tracing import BROADCASTER
from automation.workflows import (
    N8N_HANDLERS,
    TRUCK_POOLS,
    DamSyncReport,
    JoinPoolRequest,
    JoinPoolResult,
    PoolView,
    SarFloodCheckRequest,
    SarFloodReport,
)
from config import MODEL_ROUTER, RoutingDecision, TaskType, now_bdt, settings
from edge_node.bangla_voice import VOICE_PRESETS, VoicePreset
from evals.regression_suite import CATEGORY_RUNNERS, EVALUATION_ENGINE, RagasReport, RegressionReport, RegressionRequest
from edge_node.ollama_local import (
    EDGE_ENGINE,
    LocalInferenceRequest,
    LocalInferenceResult,
    LocalModelsReport,
    SftExample,
    build_sft_dataset,
    local_models_report,
)
from edge_node.optical_grader import (
    OPTICAL_GRADER,
    CertificateVerification,
    GradeCropRequest,
    GradeCropResult,
    VerifyCertificateRequest,
)
from prompts.prompt_registry import PROMPT_REGISTRY, RegistryListing
from guardrails.financial_circuit import CIRCUIT_BREAKER, ArbitrageCheckInput
from guardrails.pii_scrubber import PII_SCRUBBER
from mcp_servers import registry
from mcp_servers.anomaly_state import ANOMALIES
from mcp_servers.base import JsonRpcDispatcher, ToolExecutionError, parse_error_response
from optimization.token_compressor import TOKEN_OPTIMIZER
from rag.crag_pipeline import CRAG_PIPELINE, RagQueryResult
from rag.graph_rag import GraphTraversalResult, get_graph
from rag.hybrid_retriever import PGVECTOR_SCHEMA, get_retriever
from schemas.api_models import (
    CompressRequest,
    CompressResponse,
    GraphTraverseRequest,
    GuardrailVerifyRequest,
    GuardrailVerifyResponse,
    RagQueryRequest,
)
from schemas.mcp_models import (
    ActiveAnomalyView,
    JsonRpcRequest,
    JsonRpcResponse,
    McpServerDescriptor,
    McpToolsListing,
    SimulateAnomalyRequest,
    SimulateAnomalyResponse,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await registry.shutdown()


app = FastAPI(
    title="KrishiNexus OS — MCP Backend",
    version=settings.app_version,
    description=(
        "Edge-to-cloud multi-agent agricultural OS for Bangladesh. Step 1 exposes three custom "
        "Model Context Protocol servers (13 strictly-typed tools) over JSON-RPC 2.0."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Mcp-Protocol-Version"],
)

_RPC_EXAMPLES: dict[str, dict[str, Any]] = {
    "syndicate_anomaly": {
        "summary": "Green Chili markup: Bogura grower -> Karwan Bazar retail",
        "value": {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "detect_syndicate_markup_anomaly",
                "arguments": {"crop": "Green Chili", "upazila": "Bogura", "retail_hub": "Dhaka Karwan Bazar"},
            },
        },
    },
    "sunamganj_weather": {
        "summary": "Live weather in Sunamganj",
        "value": {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "get_current_weather", "arguments": {"latitude": 25.0658, "longitude": 91.3950}},
        },
    },
    "cold_storage_quota": {
        "summary": "Open smallholder cold-storage quota near Munshiganj",
        "value": {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "query_cold_storage_quota",
                "arguments": {"district": "Munshiganj", "radius_km": 60, "tons_needed": 250},
            },
        },
    },
    "tools_list": {
        "summary": "MCP tool discovery",
        "value": {"jsonrpc": "2.0", "id": 4, "method": "tools/list"},
    },
}
_RPC_OPENAPI: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "content": {"application/json": {"schema": JsonRpcRequest.model_json_schema(), "examples": _RPC_EXAMPLES}},
    }
}


async def _serve_jsonrpc(request: Request, dispatcher: JsonRpcDispatcher) -> Response:
    """Decode the raw body so malformed JSON yields a JSON-RPC -32700 error rather than HTTP 422."""
    try:
        payload = json.loads(await request.body())
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return JSONResponse(parse_error_response(str(exc)))
    reply = await dispatcher.dispatch(payload)
    if reply is None:
        return Response(status_code=202)
    headers = {"Mcp-Protocol-Version": settings.mcp_protocol_version}
    accept = request.headers.get("accept", "")
    if "text/event-stream" in accept and "application/json" not in accept:
        event = f"event: message\ndata: {json.dumps(reply, ensure_ascii=False)}\n\n"
        return StreamingResponse(iter([event]), media_type="text/event-stream", headers={**headers, "Cache-Control": "no-cache"})
    return JSONResponse(reply, headers=headers)


@app.get("/", tags=["meta"])
async def root(request: Request) -> dict[str, Any]:
    base = str(request.base_url).rstrip("/")
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "stage": "Step 6 - complete: MCP, GraphRAG/CRAG, agents, edge node, frontend, evaluation suite",
        "docs": f"{base}/docs",
        "mcp_gateway": f"{base}/mcp",
        "servers": [s.name for s in registry.SERVERS],
        "tool_count": registry.GATEWAY.tool_count,
    }


@app.get("/health", tags=["meta"])
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "time": now_bdt().isoformat(),
        "mcp_servers": len(registry.SERVERS),
        "tools": registry.GATEWAY.tool_count,
        "active_anomalies": len(ANOMALIES.active()),
    }


@app.get("/mcp/servers", response_model=list[McpServerDescriptor], tags=["mcp"])
async def list_mcp_servers(request: Request) -> list[McpServerDescriptor]:
    return registry.server_descriptors(str(request.base_url).rstrip("/"))


@app.get("/mcp/tools", response_model=McpToolsListing, tags=["mcp"])
async def list_mcp_tools(
    server: Annotated[str | None, Query(description="Filter by server name, e.g. 'dam-market-mcp'.")] = None,
) -> McpToolsListing:
    if server is not None and server not in registry.SERVERS_BY_NAME:
        raise HTTPException(status_code=404, detail=f"Unknown MCP server '{server}'.")
    return registry.tools_listing(server)


@app.post("/mcp/call", response_model=JsonRpcResponse, tags=["mcp"], openapi_extra=_RPC_OPENAPI)
async def mcp_call(request: Request) -> Response:
    return await _serve_jsonrpc(request, registry.GATEWAY)


@app.post("/mcp", response_model=JsonRpcResponse, tags=["mcp"], openapi_extra=_RPC_OPENAPI)
async def mcp_gateway(request: Request) -> Response:
    return await _serve_jsonrpc(request, registry.GATEWAY)


@app.post("/mcp/servers/{server_name}", response_model=JsonRpcResponse, tags=["mcp"], openapi_extra=_RPC_OPENAPI)
async def mcp_server_endpoint(server_name: str, request: Request) -> Response:
    dispatcher = registry.SERVER_DISPATCHERS.get(server_name)
    if dispatcher is None:
        raise HTTPException(status_code=404, detail=f"Unknown MCP server '{server_name}'.")
    return await _serve_jsonrpc(request, dispatcher)


@app.post("/mcp/simulate-anomaly", response_model=SimulateAnomalyResponse, tags=["demo"])
async def simulate_anomaly(
    body: Annotated[
        SimulateAnomalyRequest,
        Body(
            openapi_examples={
                "power_cut": {
                    "summary": "Cold-chamber power cut, generator failed 2 h ago",
                    "value": {"anomaly_type": "cold_chamber_power_cut", "facility_id": "BCSA-MUN-01", "chamber_id": "CH-03"},
                },
                "flash_flood": {
                    "summary": "Sunamganj flash flood (April Boro scenario)",
                    "value": {"anomaly_type": "haor_flash_flood", "upazila": "Tahirpur", "upstream_rainfall_72h_mm": 320},
                },
            }
        ),
    ],
) -> SimulateAnomalyResponse:
    try:
        return await registry.simulate_anomaly(body)
    except ToolExecutionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/mcp/anomalies", response_model=list[ActiveAnomalyView], tags=["demo"])
async def list_anomalies() -> list[ActiveAnomalyView]:
    return [registry.anomaly_view(a) for a in ANOMALIES.active()]


@app.delete("/mcp/anomalies/{anomaly_id}", tags=["demo"])
async def clear_anomaly(anomaly_id: str) -> dict[str, Any]:
    if not ANOMALIES.clear(anomaly_id):
        raise HTTPException(status_code=404, detail=f"No active anomaly '{anomaly_id}'.")
    return {"cleared": anomaly_id}


@app.delete("/mcp/anomalies", tags=["demo"])
async def clear_all_anomalies() -> dict[str, Any]:
    return {"cleared": ANOMALIES.clear_all()}


# ---------------------------------------------------------------------------
# Step 2: RAG, optimisation and guardrail endpoints
# ---------------------------------------------------------------------------


@app.post("/rag/query", response_model=RagQueryResult, tags=["rag"])
async def rag_query(
    body: Annotated[
        RagQueryRequest,
        Body(openapi_examples={"munshiganj_potato": {
            "summary": "Bangla: storage temperature + syndicate-free selling (Munshiganj)",
            "value": {"query": "মুন্সিগঞ্জে কার্ডিনাল আলু কোল্ড স্টোরেজে কত তাপমাত্রায় রাখলে পচবে না এবং সিন্ডিকেট ছাড়া কোথায় বেচব?",
                      "district": "Munshiganj", "crop": "Cardinal Potato"},
        }, "rangpuri": {
            "summary": "Rangpuri dialect: where to sell potatoes",
            "value": {"query": "বাহে, মুই কাইল আলু কোনঠে বেচমু? ফড়িয়া দাম কম দেয়"},
        }}),
    ],
) -> RagQueryResult:
    return await CRAG_PIPELINE.run(body.query, body.district, body.crop, body.top_k)


@app.post("/rag/graph-traverse", response_model=GraphTraversalResult, tags=["rag"])
async def rag_graph_traverse(
    body: Annotated[
        GraphTraverseRequest,
        Body(openapi_examples={"tongibari": {"summary": "Tongibari potato supply paths",
                                             "value": {"start": "Tongibari", "crop": "Cardinal Potato", "max_paths": 5}}}),
    ],
) -> GraphTraversalResult:
    try:
        return get_graph().traverse(body.start, body.crop, body.max_paths)
    except ToolExecutionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/rag/stats", tags=["rag"])
async def rag_stats() -> dict[str, Any]:
    return {"retriever": get_retriever().stats, "graph": get_graph().stats(), "pgvector_schema": PGVECTOR_SCHEMA}


@app.post("/optimization/compress", response_model=CompressResponse, tags=["optimization"])
async def optimization_compress(body: CompressRequest) -> CompressResponse:
    compression = TOKEN_OPTIMIZER.compress_prompt_llmlingua(body.raw_context, body.target_ratio)
    chunks = body.chunks or [s for s in re.split(r"(?<=[.!?।])\s+", body.raw_context) if s.strip()]
    return CompressResponse(
        compression=compression,
        deduplication=TOKEN_OPTIMIZER.deduplicate_semantic_chunks(chunks, body.similarity_threshold),
        cache=TOKEN_OPTIMIZER.build_cached_messages(body.system_prompt, compression.compressed_text, body.user_query),
        routing=MODEL_ROUTER.route_query(TaskType.RAG_ANSWER, min(1.0, compression.compressed_tokens / 4_000)),
    )


@app.get("/optimization/route", response_model=RoutingDecision, tags=["optimization"])
async def optimization_route(
    task_type: TaskType,
    complexity: Annotated[float, Query(ge=0, le=1)] = 0.5,
    offline: bool = False,
) -> RoutingDecision:
    return MODEL_ROUTER.route_query(task_type, complexity, offline)


_ARBITRAGE_FIELDS = (
    "crop", "quantity_kg", "spot_price_bdt", "expected_future_price_bdt", "storage_tariff_bdt",
    "handling_cost_bdt", "lambda_rot",
)


@app.post("/guardrails/verify", response_model=GuardrailVerifyResponse, tags=["guardrails"])
async def guardrails_verify(body: GuardrailVerifyRequest) -> GuardrailVerifyResponse:
    pii = PII_SCRUBBER.scrub(body.raw_text) if body.raw_text else None
    missing = [name for name in _ARBITRAGE_FIELDS if getattr(body, name) is None]
    arbitrage = None
    if not missing:
        try:
            arbitrage = CIRCUIT_BREAKER.validate_arbitrage_recommendation(
                ArbitrageCheckInput(**body.model_dump(include={*_ARBITRAGE_FIELDS, "transport_to_storage_bdt",
                                                             "transport_to_market_bdt", "district", "holding_months",
                                                             "proposed_action"}))
            )
        except ToolExecutionError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    agronomic = CIRCUIT_BREAKER.validate_agronomic_dosage(body.pesticide) if body.pesticide else None
    tripped = [
        label for label, hit in (
            ("FINANCIAL_CIRCUIT_BREAKER", arbitrage is not None and arbitrage.circuit_tripped),
            ("AGRONOMIC_CIRCUIT_BREAKER", agronomic is not None and agronomic.circuit_tripped),
        ) if hit
    ]
    return GuardrailVerifyResponse(
        overall_verdict="BLOCKED" if tripped else "PASS",
        tripped=tripped,
        pii=pii,
        arbitrage=arbitrage,
        arbitrage_missing_fields=missing if len(missing) < len(_ARBITRAGE_FIELDS) else [],
        agronomic=agronomic,
    )


# ---------------------------------------------------------------------------
# Step 3: multi-agent orchestration, live trace, prompts and automation
# ---------------------------------------------------------------------------

_ORCHESTRATE_EXAMPLE = {
    "farmer_id": "FARM-BOG-104",
    "raw_query_bangla": "আমার নাম রহিম, ফোন 01711223344। আমার কাছে ৪০০ কেজি কার্ডিনাল আলু আছে। ফড়িয়া ১১ টাকা কেজি দাম বলছে। "
                        "আজ বিক্রি করব নাকি কোল্ড স্টোরেজে রাখব?",
    "district": "Bogura",
    "upazila": "Shibganj",
    "crop": "Cardinal Potato",
    "quantity_kg": 400,
}


@app.post("/agents/orchestrate", response_model=OrchestrateResponse, tags=["agents"])
async def agents_orchestrate(
    body: Annotated[OrchestrateRequest, Body(openapi_examples={"bogura_potato": {
        "summary": "Bogura farmer offered Tk 11/kg by a Faria", "value": _ORCHESTRATE_EXAMPLE}})],
) -> OrchestrateResponse:
    try:
        return await orchestrate(body)
    except ToolExecutionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.websocket("/ws/agent-trace")
async def ws_agent_trace(websocket: WebSocket, session_id: str | None = None) -> None:
    await websocket.accept()
    await websocket.send_json({"type": "hello", "session_filter": session_id,
                               "replay": [e.model_dump(mode="json") for e in BROADCASTER.history(session_id, 200)]})
    BROADCASTER.subscribe(websocket, session_id)
    try:
        while True:
            message = await websocket.receive_text()
            if message.strip().lower() == "ping":
                await websocket.send_json({"type": "pong", "time": now_bdt().isoformat()})
    except WebSocketDisconnect:
        logging.getLogger("krishinexus.ws").info("Trace subscriber disconnected (session filter: %s)", session_id)
    finally:
        BROADCASTER.unsubscribe(websocket)


@app.get("/agents/trace-history", response_model=list[AgentTraceEvent], tags=["agents"])
async def agents_trace_history(session_id: str | None = None,
                               limit: Annotated[int, Query(ge=1, le=2_000)] = 200) -> list[AgentTraceEvent]:
    return BROADCASTER.history(session_id, limit)


@app.get("/prompts/registry", response_model=RegistryListing, tags=["prompts"])
async def prompts_registry(agent: str | None = None, include_xml: bool = True) -> RegistryListing:
    listing = PROMPT_REGISTRY.listing()
    if agent is not None:
        listing.agents = [a for a in listing.agents if a.agent == agent]
        if not listing.agents:
            raise HTTPException(status_code=404, detail=f"Unknown agent '{agent}'. Known: {', '.join(PROMPT_REGISTRY.specs)}.")
    if not include_xml:
        for view in listing.agents:
            view.versions = [v.model_copy(update={"xml": ""}) for v in view.versions]
    return listing


@app.get("/automation/truck-pools", response_model=list[PoolView], tags=["automation"])
async def automation_truck_pools() -> list[PoolView]:
    return await TRUCK_POOLS.list_pools()


@app.post("/automation/truck-pools/join", response_model=JoinPoolResult, tags=["automation"])
async def automation_truck_pools_join(
    body: Annotated[JoinPoolRequest, Body(openapi_examples={"bogura": {"summary": "Fill POOL-BOGURA-01 to 5,000 kg", "value": {
        "cluster_id": "POOL-BOGURA-01", "farmer_id": "FARM-BOG-104", "crop": "Cardinal Potato", "weight_kg": 400, "grade": "Grade-A"}}})],
) -> JoinPoolResult:
    try:
        return await TRUCK_POOLS.join(body)
    except ToolExecutionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/automation/truck-pools/reset", response_model=list[PoolView], tags=["automation"])
async def automation_truck_pools_reset() -> list[PoolView]:
    return TRUCK_POOLS.reset()


@app.post("/automation/n8n/daily-dam-sync", response_model=DamSyncReport, tags=["automation"])
async def automation_daily_dam_sync() -> DamSyncReport:
    return await N8N_HANDLERS.daily_dam_sync()


@app.post("/automation/n8n/hourly-sar-flood-check", response_model=SarFloodReport, tags=["automation"])
async def automation_hourly_sar_flood_check(body: SarFloodCheckRequest | None = None) -> SarFloodReport:
    return await N8N_HANDLERS.hourly_sar_flood_check(body or SarFloodCheckRequest())


@app.get("/automation/n8n/workflows", tags=["automation"])
async def automation_n8n_workflows(request: Request) -> list[dict[str, Any]]:
    return N8N_HANDLERS.workflow_definitions(str(request.base_url).rstrip("/"))


# ---------------------------------------------------------------------------
# Step 4: rural edge node
# ---------------------------------------------------------------------------


@app.post("/edge/voice-interact", response_model=VoiceInteractResponse, tags=["edge"])
async def edge_voice_interact(
    body: Annotated[VoiceInteractRequest, Body(openapi_examples={
        "rangpur": {"summary": "Rangpuri potato distress sale (online)", "value": {"preset_id": "rangpur_potato_distress", "offline_mode": False}},
        "haor_offline": {"summary": "Sylheti haor flood question during an internet blackout",
                         "value": {"preset_id": "sunamganj_haor_flood", "offline_mode": True}},
        "typed": {"summary": "Typed Banglish request", "value": {"text": "Bogura theke bolchi, 20 mon alu ache, faria 13 taka dicche",
                                                                  "district": "Bogura", "upazila": "Shibganj"}},
    })],
) -> VoiceInteractResponse:
    try:
        return await voice_interact(body)
    except ToolExecutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/edge/voice-presets", response_model=list[VoicePreset], tags=["edge"])
async def edge_voice_presets() -> list[VoicePreset]:
    return list(VOICE_PRESETS.values())


@app.post("/edge/grade-crop", response_model=GradeCropResult, tags=["edge"])
async def edge_grade_crop(
    body: Annotated[GradeCropRequest, Body(openapi_examples={"bogura": {"summary": "High-grade Cardinal potato sweep", "value": {
        "crop": "Cardinal Potato", "district": "Bogura", "sample_preset": "high_grade_harvest"}}})],
) -> GradeCropResult:
    try:
        return OPTICAL_GRADER.grade(body)
    except ToolExecutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/edge/verify-certificate", response_model=CertificateVerification, tags=["edge"])
async def edge_verify_certificate(body: VerifyCertificateRequest) -> CertificateVerification:
    certificate = body.certificate or OPTICAL_GRADER.lookup(body.cert_id or "")
    if certificate is None:
        raise HTTPException(status_code=404, detail=f"No certificate '{body.cert_id}' was issued by this node.")
    return OPTICAL_GRADER.verify(certificate)


@app.get("/edge/local-models", response_model=LocalModelsReport, tags=["edge"])
async def edge_local_models(hardware_profile: str = "union-kiosk-cpu") -> LocalModelsReport:
    try:
        return await local_models_report(hardware_profile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/edge/local-inference", response_model=LocalInferenceResult, tags=["edge"])
async def edge_local_inference(
    body: Annotated[LocalInferenceRequest, Body(openapi_examples={"blackout": {"summary": "Offline blackout, DeepSeek arbitrage", "value": {
        "prompt": "মুন্সিগঞ্জে ৫০ মণ আলু, ফড়িয়া ১০ টাকা কেজি দিচ্ছে, হিমাগারে রাখব?", "model_name": "deepseek-r1-7b",
        "simulate_offline_blackout": True}}})],
) -> LocalInferenceResult:
    try:
        return await EDGE_ENGINE.run_local_inference(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/edge/lora-dataset", tags=["edge"], response_model=None)
async def edge_lora_dataset(
    category: str | None = None,
    split: Literal["train", "eval"] | None = None,
    limit: Annotated[int, Query(ge=1, le=3_200)] = 20,
    format: Literal["json", "jsonl"] = "json",
) -> list[SftExample] | PlainTextResponse:
    rows = [e for e in build_sft_dataset() if (category is None or e.category == category) and (split is None or e.split == split)]
    rows = rows[:limit]
    if format == "jsonl":
        return PlainTextResponse("\n".join(json.dumps(e.model_dump(), ensure_ascii=False) for e in rows),
                                 media_type="application/jsonl; charset=utf-8")
    return rows


# ---------------------------------------------------------------------------
# Step 6: evaluation
# ---------------------------------------------------------------------------


@app.get("/evals/metrics", response_model=RagasReport, tags=["evals"])
async def evals_metrics(refresh: bool = False) -> RagasReport:
    """Measured RAGAS-style retrieval metrics, MCP schema validity and PII recall (cached 10 minutes)."""
    return await EVALUATION_ENGINE.get_ragas_metrics(max_age_s=0.0 if refresh else 600.0)


@app.post("/evals/run-regression", response_model=RegressionReport, tags=["evals"])
async def evals_run_regression(body: RegressionRequest | None = None) -> RegressionReport:
    """Run the seeded regression suite: `sample_size` cases in each of the five categories (20 -> 100 cases)."""
    request = body or RegressionRequest()
    unknown = set(request.categories or []) - set(CATEGORY_RUNNERS)
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown categories {sorted(unknown)}; choose from {list(CATEGORY_RUNNERS)}.")
    return await EVALUATION_ENGINE.run_regression_suite(request.sample_size, request.categories)
