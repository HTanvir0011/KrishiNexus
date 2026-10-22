"""LangGraph supervisor: cyclic StateGraph over guardrails, retrieval and the four specialist agents.

    START -> pii_guardrail -> token_compression -> crag_retrieval -> vision_grading -> syndicate_bypass
          -> coldchain_arbitrage -> climate_credit -> supervisor_review --(re-plan)--> coldchain_arbitrage
                                                                    \\--(consistent)--> voice_synthesizer -> END

``supervisor_review`` loops back to the cold-chain agent (at most twice) when a storing plan points
at a chamber that is out of the 48-50 F / 92-95% RH band or without power. Every node streams its
trace events to ``/ws/agent-trace`` as they happen. All agents are deterministic, so the workflow
runs identically with or without LLM API keys; the model router records which model each language
step would use.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field

from agents import climate_credit_agent, coldchain_arbitrage_agent, syndicate_bypass_agent, vision_grading_agent
from agents.state import HarvestMetrics, KrishiAgentState, RagSummary, StepType
from agents.tracing import RECORDERS, TraceRecorder, recorder_for
from config import MODEL_ROUTER, RoutingDecision, TaskType
from guardrails.pii_scrubber import PII_SCRUBBER
from edge_node.bangla_voice import VOICE_PIPELINE, TranscriptionResult, VoiceScript, digitize_numbers
from edge_node.ollama_local import EDGE_ENGINE, LocalInferenceRequest, LocalInferenceResult
from edge_node.optical_grader import OPTICAL_GRADER, GradeableCrop, GradeCropRequest, GradeCropResult, SamplePreset
from mcp_servers.agri_weather_sar_mcp import NETWORK_BLACKOUT, to_bangla_digits
from mcp_servers.base import ToolExecutionError
from mcp_servers.dam_market_mcp import get_daily_commodity_spread
from optimization.token_compressor import TOKEN_OPTIMIZER
from prompts.prompt_registry import PROMPT_REGISTRY
from rag.crag_pipeline import CRAG_PIPELINE
from schemas.mcp_models import Crop, CropField, GetDailyCommoditySpreadInput

logger = logging.getLogger("krishinexus.supervisor")

SUPERVISOR = "supervisor"
MAX_REVIEW_ITERATIONS = 2
_OFFER_RE = re.compile(r"(?:ফড়িয়া|ফরিয়া|faria|বেপারী|bepari|পাইকার|paiker|আড়তদার|aratdar|দাম|dam)[^0-9০-৯]{0,25}([0-9০-৯]+(?:\.[0-9০-৯]+)?)\s*(?:টাকা|taka|tk)",
                       re.IGNORECASE)
_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

CROP_BN = {Crop.CARDINAL_POTATO: "কার্ডিনাল আলু", Crop.DIAMANT_POTATO: "ডায়মন্ড আলু", Crop.GREEN_CHILI: "কাঁচা মরিচ",
           Crop.BRINJAL: "বেগুন", Crop.BORO_RICE: "বোরো ধান"}
GRADE_BN = {"A": "গ্রেড-এ (সুপারশপ/রপ্তানি মান)", "B": "গ্রেড-বি (পাইকারি মান)", "C": "গ্রেড-সি (প্রক্রিয়াজাত মান)"}


class OrchestrateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    farmer_id: str = Field(pattern=r"^[A-Za-z0-9\-]{3,40}$")
    raw_query_bangla: str = Field(min_length=2, max_length=4_000)
    district: str = Field(min_length=2, max_length=60)
    upazila: str = Field(min_length=2, max_length=60)
    crop: CropField
    quantity_kg: float = Field(gt=0, le=100_000)
    harvest_metrics: HarvestMetrics | None = None
    sar_water_backscatter_db: float | None = Field(default=None, ge=-35, le=5)
    farmer_offer_tk_per_kg: float | None = Field(default=None, ge=0, description="Overrides the offer parsed from the query.")
    offline_mode: bool = Field(default=False, description="Simulate a rural internet blackout: every tool uses on-device fallbacks.")
    session_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9\-]{4,60}$",
                                   description="Optional: pre-subscribe /ws/agent-trace?session_id=... before calling.")


class OrchestrateResponse(BaseModel):
    session_id: str
    status: Literal["COMPLETED", "COMPLETED_WITH_ERRORS"]
    graph_path: list[str]
    review_iterations: int
    latency_ms: float
    trace_event_count: int
    voice_routing: RoutingDecision
    state: KrishiAgentState


def parse_offer(text: str) -> float | None:
    ascii_text = text.translate(_DIGITS)
    match = _OFFER_RE.search(ascii_text)
    return float(match.group(1)) if match else None


def _bn(value: float, decimals: int = 0) -> str:
    return to_bangla_digits(f"{value:,.{decimals}f}")


Node = Callable[[KrishiAgentState], Awaitable[dict[str, Any]]]


def guarded(name: str, body: Callable[[KrishiAgentState, TraceRecorder], Awaitable[dict[str, Any]]]) -> Node:
    """Wrap a node: attach its recorder, append it to node_path, and turn exceptions into recorded errors."""

    async def node(state: KrishiAgentState) -> dict[str, Any]:
        trace = recorder_for(state.session_id)
        try:
            update = await body(state, trace)
        except Exception as exc:
            logger.exception("Node %s failed", name)
            await trace.emit(name, StepType.DECISION, f"{name} failed: {exc}", data={"error": type(exc).__name__})
            update = {"errors": [f"{name}: {exc}"], "trace_events": trace.drain()}
        update["node_path"] = [name]
        return update

    return node


# ---------------------------------------------------------------------------
# Supervisor-owned nodes
# ---------------------------------------------------------------------------


async def pii_guardrail(state: KrishiAgentState, trace: TraceRecorder) -> dict[str, Any]:
    scrub = PII_SCRUBBER.scrub(state.raw_query_bangla)
    for entity in scrub.entities:
        await trace.emit("pii_guardrail", StepType.GUARDRAIL,
                         f"Redacted {entity.entity_type} {entity.masked_preview} -> {entity.token} (score {entity.score}).",
                         tool="BanglaPIIScrubber", data={"recognizer": entity.recognizer})
    offer = state.farmer_offer_tk_per_kg if state.farmer_offer_tk_per_kg is not None else parse_offer(scrub.anonymized_text)
    await trace.emit("pii_guardrail", StepType.THOUGHT,
                     f"{len(scrub.entities)} PII entities vaulted; parsed intermediary offer: "
                     + (f"Tk {offer:g}/kg." if offer is not None else "none."))
    vault = {"vault_id": scrub.vault_id or ""} | {f"{e.entity_type}#{i}": e.masked_preview for i, e in enumerate(scrub.entities)}
    return {"scrubbed_query": scrub.anonymized_text, "pii_vault_map": vault, "farmer_offer_tk_per_kg": offer,
            "trace_events": trace.drain()}


async def token_compression(state: KrishiAgentState, trace: TraceRecorder) -> dict[str, Any]:
    spread = await trace.mcp(SUPERVISOR, "get_daily_commodity_spread", get_daily_commodity_spread,
                             GetDailyCommoditySpreadInput(crop=state.crop, district=state.district),
                             lambda r: f"Loaded 7-day DAM series for {r.crop.value} in {r.district}.")
    raw = json.dumps({"dam_7day": spread.model_dump(mode="json"), "farmer_query": state.scrubbed_query}, ensure_ascii=False, indent=2)
    compression = TOKEN_OPTIMIZER.compress_prompt_llmlingua(raw, 0.25)
    cache = TOKEN_OPTIMIZER.build_cached_messages(PROMPT_REGISTRY.active(SUPERVISOR).xml, compression.compressed_text,
                                                  state.scrubbed_query)
    saved = compression.original_tokens - compression.compressed_tokens
    await trace.emit("token_compression", StepType.THOUGHT,
                     f"LLMLingua-2 context {compression.original_tokens} -> {compression.compressed_tokens} tokens "
                     f"({compression.reduction_factor}x, numbers preserved: {compression.all_numbers_preserved}); "
                     f"supervisor prefix {cache.static_prefix_tokens} tokens cacheable.",
                     tool="TokenOptimizer", token_saved=saved, data={"cache_eligible": cache.cache_eligible})
    return {"compression_report": {
        "original_tokens": compression.original_tokens, "compressed_tokens": compression.compressed_tokens,
        "reduction_factor": compression.reduction_factor, "all_numbers_preserved": compression.all_numbers_preserved,
        "cache_prefix_sha256": cache.prefix_sha256, "cache_prefix_tokens": cache.static_prefix_tokens,
        "cache_eligible": cache.cache_eligible, "estimated_input_cost_usd": cache.estimated_input_cost_usd,
    }, "trace_events": trace.drain()}


async def crag_retrieval(state: KrishiAgentState, trace: TraceRecorder) -> dict[str, Any]:
    rag = await CRAG_PIPELINE.run(state.scrubbed_query, state.district, state.crop, top_k=5)
    summary = RagSummary(
        verdict=rag.crag.verdict, confidence=rag.crag.confidence, corrective_triggered=rag.crag.corrective_triggered,
        intents=[i.value for i in rag.rewrite.intents], dialect=rag.rewrite.detected_dialect,
        top_chunks=[c.chunk_id for c in rag.retrieval[:5]], graph_paths=[p.narrative for p in rag.graph.paths] if rag.graph else [],
        answer_summary=rag.answer_summary, tokens_saved=rag.context_tokens["saved"],
    )
    await trace.emit("crag_retrieval", StepType.RAG_CRAG,
                     f"HyDE ({summary.dialect}) intents {summary.intents}; CRAG {summary.verdict} ({summary.confidence:.2f}); "
                     f"GraphRAG {len(summary.graph_paths)} paths.", tool="CragPipeline", token_saved=summary.tokens_saved,
                     data={"top_chunks": summary.top_chunks})
    return {"rag_crag_result": summary, "trace_events": trace.drain()}


async def supervisor_review(state: KrishiAgentState, trace: TraceRecorder) -> dict[str, Any]:
    reason = coldchain_arbitrage_agent.needs_replan(state.cold_storage_arbitrage_plan)
    if reason and state.review_iterations < MAX_REVIEW_ITERATIONS:
        await trace.emit(SUPERVISOR, StepType.THOUGHT,
                         f"Review: storage plan uses {reason.split(':', 1)[1]} whose chamber is out of band; re-planning cold chain.")
        return {"replan_reason": reason, "review_iterations": state.review_iterations + 1, "trace_events": trace.drain()}
    await trace.emit(SUPERVISOR, StepType.THOUGHT,
                     "Review: plans are consistent" + (f" ({len(state.errors)} recorded errors)." if state.errors else "."))
    return {"replan_reason": None, "trace_events": trace.drain()}


def route_after_review(state: KrishiAgentState) -> str:
    return "coldchain_arbitrage" if state.replan_reason else "voice_synthesizer"


def compose_voice_reply(state: KrishiAgentState) -> tuple[str, bool]:
    parts: list[str] = []
    cert, syn, cold, climate = (state.optical_grade_cert, state.syndicate_bypass_plan,
                                state.cold_storage_arbitrage_plan, state.climate_credit_report)
    crop_bn = CROP_BN[state.crop]
    if climate and climate.flood_applicable and climate.flood_breach_probability_pct is not None:
        level = climate.flood_alert_level.value if climate.flood_alert_level else "GREEN"
        advice = {"RED": "এখনই ৮০% পাকা ধান কেটে উঁচু জায়গায় সরান।", "ORANGE": "২৪ ঘণ্টার মধ্যে ধান কাটার প্রস্তুতি নিন।",
                  "YELLOW": "যন্ত্র ও শ্রমিক প্রস্তুত রাখুন।", "GREEN": "স্বাভাবিক সময়সূচিতে ধান কাটুন।"}[level]
        parts.append(f"হাওরে বাঁধ ভাঙার সম্ভাবনা এখন {_bn(climate.flood_breach_probability_pct)}%; {advice}")
    if cert:
        parts.append(f"আপনার {_bn(state.quantity_kg)} কেজি {crop_bn} {GRADE_BN[cert.market_grade.value]} সনদ পেয়েছে।")
    if cold and cold.distress_sale_blocked and state.farmer_offer_tk_per_kg is not None:
        parts.append(f"ফড়িয়ার {_bn(state.farmer_offer_tk_per_kg)} টাকা দাম উৎপাদন খরচের (কেজি ১৫ টাকা) নিচে, তাই এই বিক্রি আটকে দেওয়া হয়েছে।")
    if syn:
        parts.append(f"বাজারে খুচরা দাম কৃষকের দামের চেয়ে {_bn(syn.markup_pct)}% বেশি — এটা সিন্ডিকেটের মুনাফা।")
        parts.append(f"৫ টনের যৌথ ট্রাকে সরাসরি {syn.best_hub_name}-এ বিক্রি করলে কেজিতে {_bn(syn.b2b_net_tk_per_kg, 2)} টাকা পাবেন।")
        if syn.pool:
            parts.append(f"আপনার ইউনিয়নের ট্রাকে এখন {_bn(syn.pool.current_kg)} কেজি আছে; আপনার মাল যোগ হলে "
                         f"{_bn(syn.pool.after_join_kg)} কেজি হবে" + (" এবং ট্রাক সঙ্গে সঙ্গে রওনা দেবে।" if syn.pool.will_trigger_dispatch else "।"))
    if cold:
        if cold.decision == "SELL_POOLED_B2B" and cold.expected_future_price_tk_per_kg is not None:
            parts.append(f"হিমাগারে {_bn(cold.horizon_days)} দিন রাখলে খামারে দাম প্রায় {_bn(cold.expected_future_price_tk_per_kg, 2)} "
                         f"টাকায় নামতে পারে, তাই এখন যৌথ ট্রাকে বিক্রি করাই লাভজনক।")
        elif cold.decision.startswith("STORE") and cold.facility:
            receipt = cold.reservation.receipt_id if cold.reservation and cold.reservation.receipt_id else None
            parts.append(f"{cold.facility.name} হিমাগারে জায়গা " + ("সংরক্ষণ করা হয়েছে" if receipt else "পাওয়া গেছে")
                         + f"; {_bn(cold.horizon_days)} দিন পর কেজিতে প্রায় {_bn(cold.projected_net_tk_per_kg, 2)} টাকা থাকবে।")
    if climate:
        if climate.seventy_two_hour_clearance:
            parts.append("আগামী ৭২ ঘণ্টায় ঝড় বা বন্যার বড় ঝুঁকি নেই।")
        elif climate.flood_alert_level is None:
            parts.append("আগামী ৭২ ঘণ্টায় ঝড়-বৃষ্টির সতর্কতা আছে; মাল ঢেকে রাখুন।")
        if climate.loan_eligible:
            parts.append(f"আপনার কৃষি-ঋণ স্কোর {_bn(climate.credit_score)}; {_bn(climate.loan_amount_tk)} টাকা পর্যন্ত "
                         f"{_bn(climate.annual_rate_pct)}% সুদে চলতি মূলধন ঋণ প্রস্তুত।")
        else:
            parts.append(f"আপনার কৃষি-ঋণ স্কোর {_bn(climate.credit_score)}; এখনই তাৎক্ষণিক ঋণের যোগ্যতা হয়নি।")
    needs_approval = bool((syn and syn.pool) or (cold and cold.decision.startswith("STORE")) or (climate and climate.loan_eligible))
    if needs_approval:
        parts.append("রাজি থাকলে 'হ্যাঁ' বলুন, আমরা ট্রাক ও ঋণের কাজ শুরু করব।")
    return " ".join(parts), needs_approval


async def voice_synthesizer(state: KrishiAgentState, trace: TraceRecorder) -> dict[str, Any]:
    routing = MODEL_ROUTER.route_query(TaskType.VOICE_STATUS, 0.3, offline_mode=state.offline_mode)
    text, needs_approval = compose_voice_reply(state)
    script = VOICE_PIPELINE.build_ssml(text)
    await trace.emit("voice_synthesizer", StepType.DECISION,
                     f"Bangla voice reply ready ({len(text)} chars, ~{script.estimated_duration_s:g} s SSML with "
                     f"{len(script.pronunciation_guide)} phoneme hints); approval required: {needs_approval}. "
                     f"Language model route: {routing.display_name} (deterministic template rendered"
                     + (" on-device during blackout)." if state.offline_mode else ")."),
                     data={"model": routing.model_id})
    return {"final_bangla_voice_response": text, "final_bangla_ssml": script.ssml, "requires_farmer_voice_approval": needs_approval,
            "prompt_versions": {**state.prompt_versions, SUPERVISOR: PROMPT_REGISTRY.active(SUPERVISOR).version},
            "trace_events": trace.drain()}


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


def build_graph() -> Any:
    builder = StateGraph(KrishiAgentState)
    nodes: dict[str, Callable[[KrishiAgentState, TraceRecorder], Awaitable[dict[str, Any]]]] = {
        "pii_guardrail": pii_guardrail,
        "token_compression": token_compression,
        "crag_retrieval": crag_retrieval,
        "vision_grading": vision_grading_agent.run,
        "syndicate_bypass": syndicate_bypass_agent.run,
        "coldchain_arbitrage": coldchain_arbitrage_agent.run,
        "climate_credit": climate_credit_agent.run,
        "supervisor_review": supervisor_review,
        "voice_synthesizer": voice_synthesizer,
    }
    for name, body in nodes.items():
        builder.add_node(name, guarded(name, body))
    sequence = list(nodes)[:8]
    builder.add_edge(START, sequence[0])
    for a, b in zip(sequence, sequence[1:]):
        builder.add_edge(a, b)
    builder.add_conditional_edges("supervisor_review", route_after_review,
                                  {"coldchain_arbitrage": "coldchain_arbitrage", "voice_synthesizer": "voice_synthesizer"})
    builder.add_edge("voice_synthesizer", END)
    return builder.compile()


GRAPH = build_graph()


async def orchestrate(request: OrchestrateRequest) -> OrchestrateResponse:
    session_id = request.session_id or f"KNX-{uuid.uuid4().hex[:12].upper()}"
    trace = recorder_for(session_id)
    started = time.perf_counter()
    await trace.emit(SUPERVISOR, StepType.THOUGHT,
                     f"Session {session_id} for {request.farmer_id}: {request.quantity_kg:g} kg {request.crop.value} in "
                     f"{request.upazila}, {request.district}. Route: PII -> compression -> CRAG -> 4 agents -> review -> voice.")
    initial = KrishiAgentState(
        session_id=session_id, farmer_id=request.farmer_id, raw_query_bangla=request.raw_query_bangla,
        district=request.district, upazila=request.upazila, crop=request.crop, quantity_kg=request.quantity_kg,
        harvest_metrics_input=request.harvest_metrics, sar_backscatter_override_db=request.sar_water_backscatter_db,
        farmer_offer_tk_per_kg=request.farmer_offer_tk_per_kg, offline_mode=request.offline_mode,
    )
    blackout = NETWORK_BLACKOUT.set(request.offline_mode)
    try:
        result = await GRAPH.ainvoke(initial, config={"recursion_limit": 40})
    finally:
        NETWORK_BLACKOUT.reset(blackout)
        RECORDERS.pop(session_id, None)
    state = KrishiAgentState.model_validate(result)
    return OrchestrateResponse(
        session_id=session_id,
        status="COMPLETED_WITH_ERRORS" if state.errors else "COMPLETED",
        graph_path=state.node_path,
        review_iterations=state.review_iterations,
        latency_ms=round((time.perf_counter() - started) * 1000, 1),
        trace_event_count=len(state.trace_events),
        voice_routing=MODEL_ROUTER.route_query(TaskType.VOICE_STATUS, 0.3, offline_mode=request.offline_mode),
        state=state,
    )


# ---------------------------------------------------------------------------
# Rural edge entry point: voice in, agents, voice out
# ---------------------------------------------------------------------------


class VoiceInteractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    preset_id: str | None = Field(default=None, description="One of GET /edge/voice-presets.")
    text: str | None = Field(default=None, max_length=4_000, description="Typed Bangla/Banglish farmer request.")
    audio_base64: str | None = Field(default=None, description="Recorded speech (needs KNX_WHISPER_MODEL + faster-whisper).")
    dialect_hint: str | None = None
    farmer_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9\-]{3,40}$")
    district: str | None = Field(default=None, max_length=60)
    upazila: str | None = Field(default=None, max_length=60)
    grade_sample_preset: SamplePreset | None = Field(default=None, description="Run the optical grader on this sweep first.")
    harvest_metrics: HarvestMetrics | None = None
    offline_mode: bool = False
    session_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9\-]{4,60}$")


class VoiceInteractResponse(BaseModel):
    status: Literal["COMPLETED", "COMPLETED_WITH_ERRORS", "NEEDS_CLARIFICATION"]
    transcription: TranscriptionResult
    grading: GradeCropResult | None
    local_inference: LocalInferenceResult | None
    orchestration: OrchestrateResponse | None
    spoken_response_bn: str
    voice: VoiceScript
    follow_up_question_bn: str | None


async def voice_interact(request: VoiceInteractRequest) -> VoiceInteractResponse:
    transcription = VOICE_PIPELINE.transcribe_and_normalize(request.preset_id, request.text, request.audio_base64, request.dialect_hint)
    entities = transcription.entities
    district = request.district or entities.district
    upazila = request.upazila or entities.upazila or (f"{district} Sadar" if district else None)
    missing = [label for label, value in (("ফসলের নাম", entities.crop), ("পরিমাণ (কেজি/মণ)", entities.quantity_kg),
                                          ("উপজেলা/জেলা", district)) if value is None]

    local = None
    if request.offline_mode:
        local = await EDGE_ENGINE.run_local_inference(LocalInferenceRequest(
            prompt=transcription.normalized_text, model_name="llama3.2-3b", simulate_offline_blackout=True))

    if missing:
        question = "আপনার কথা বুঝতে আরও তথ্য দরকার: " + ", ".join(missing) + " বলবেন?"
        return VoiceInteractResponse(status="NEEDS_CLARIFICATION", transcription=transcription, grading=None, local_inference=local,
                                     orchestration=None, spoken_response_bn=question, voice=VOICE_PIPELINE.build_ssml(question),
                                     follow_up_question_bn=question)
    assert entities.crop is not None and entities.quantity_kg is not None and district is not None and upazila is not None

    grading = None
    metrics = request.harvest_metrics
    if request.grade_sample_preset is not None and entities.crop.value in {c.value for c in GradeableCrop}:
        grading = OPTICAL_GRADER.grade(GradeCropRequest(crop=GradeableCrop(entities.crop.value), district=district,
                                                        farmer_id=request.farmer_id or transcription.farmer_id,
                                                        sample_preset=request.grade_sample_preset, lot_kg=entities.quantity_kg))
        m = grading.metrics
        metrics = HarvestMetrics(size_uniformity_pct=m.size_uniformity_pct, bruising_pct=m.mechanical_bruising_pct,
                                 rot_blight_risk_pct=m.rot_blight_risk_pct, moisture_pct=m.estimated_moisture_pct,
                                 source="edge_optical_grader", edge_certificate_id=grading.digital_certificate.cert_id)

    farmer_id = request.farmer_id or transcription.farmer_id or f"FARM-{district[:3].upper()}-VOICE"
    try:
        orchestration = await orchestrate(OrchestrateRequest(
            farmer_id=farmer_id, raw_query_bangla=digitize_numbers(transcription.raw_transcript), district=district,
            upazila=upazila, crop=entities.crop, quantity_kg=entities.quantity_kg, harvest_metrics=metrics,
            farmer_offer_tk_per_kg=entities.offered_faria_price_bdt, offline_mode=request.offline_mode,
            session_id=request.session_id,
        ))
    except ToolExecutionError as exc:
        question = f"দুঃখিত, এই এলাকার তথ্য পাওয়া যায়নি ({exc}). আপনার উপজেলার নাম আবার বলবেন?"
        return VoiceInteractResponse(status="NEEDS_CLARIFICATION", transcription=transcription, grading=grading, local_inference=local,
                                     orchestration=None, spoken_response_bn=question, voice=VOICE_PIPELINE.build_ssml(question),
                                     follow_up_question_bn=question)
    spoken = orchestration.state.final_bangla_voice_response
    return VoiceInteractResponse(status=orchestration.status, transcription=transcription, grading=grading, local_inference=local,
                                 orchestration=orchestration, spoken_response_bn=spoken, voice=VOICE_PIPELINE.build_ssml(spoken),
                                 follow_up_question_bn=None)
