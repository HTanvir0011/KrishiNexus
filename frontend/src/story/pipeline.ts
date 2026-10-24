import type { TraceEvent } from "../api/client";

/** The LangGraph nodes in `backend/agents/supervisor.py:build_graph`, in run order, with their real state contracts. */
export interface PipelineNode {
  id: string;
  /** `agent_name` on the node's trace events. */
  agent: string;
  short: string;
  title: string;
  does: string;
  reads: string[];
  writes: string[];
  tools: string[];
  files: string[];
}

export const PIPELINE: PipelineNode[] = [
  {
    id: "pii_guardrail", agent: "pii_guardrail", short: "PII", title: "PII guardrail",
    does: "Hides phone numbers, NIDs and mobile-wallet IDs before any agent sees the question, then reads the middleman's offer.",
    reads: ["raw_query_bangla", "farmer_offer_tk_per_kg"], writes: ["scrubbed_query", "pii_vault_map", "farmer_offer_tk_per_kg"],
    tools: [], files: ["backend/agents/supervisor.py", "backend/guardrails/pii_scrubber.py"],
  },
  {
    id: "token_compression", agent: "token_compression", short: "Compress", title: "Token compression",
    does: "Loads the 7-day DAM price series and compresses it LLMLingua-2 style, keeping every number, behind a cacheable prompt prefix.",
    reads: ["crop", "district", "scrubbed_query"], writes: ["compression_report"],
    tools: ["get_daily_commodity_spread"], files: ["backend/agents/supervisor.py", "backend/optimization/token_compressor.py"],
  },
  {
    id: "crag_retrieval", agent: "crag_retrieval", short: "CRAG", title: "CRAG + GraphRAG retrieval",
    does: "Rewrites the dialect question (HyDE), retrieves with BM25, vectors and graph paths, grades the evidence and calls MCP tools by intent.",
    reads: ["scrubbed_query", "district", "crop"], writes: ["rag_crag_result"],
    tools: ["query_cold_storage_quota", "find_optimal_selling_hub", "get_daily_commodity_spread", "get_current_weather", "compute_crop_vpd_stress"],
    files: ["backend/rag/crag_pipeline.py", "backend/rag/hybrid_retriever.py", "backend/rag/graph_rag.py"],
  },
  {
    id: "vision_grading", agent: "vision_grading", short: "Grade", title: "Vision grading agent",
    does: "Grades the lot A, B or C against BARI thresholds and signs an HMAC digital quality certificate.",
    reads: ["crop", "district", "farmer_id", "quantity_kg", "harvest_metrics_input"], writes: ["optical_grade_cert"],
    tools: [], files: ["backend/agents/vision_grading_agent.py", "backend/edge_node/optical_grader.py"],
  },
  {
    id: "syndicate_bypass", agent: "syndicate_bypass", short: "Bypass", title: "Syndicate bypass agent",
    does: "Measures the five-tier markup and matches the lot to the best direct buyer through a pooled 5-ton union truck.",
    reads: ["crop", "district", "upazila", "quantity_kg", "farmer_offer_tk_per_kg", "optical_grade_cert"], writes: ["syndicate_bypass_plan"],
    tools: ["get_daily_commodity_spread", "detect_syndicate_markup_anomaly", "find_optimal_selling_hub"],
    files: ["backend/agents/syndicate_bypass_agent.py", "backend/automation/workflows.py"],
  },
  {
    id: "coldchain_arbitrage", agent: "coldchain_arbitrage", short: "Cold chain", title: "Cold-chain arbitrage agent",
    does: "Prices cold storage against the pooled sale with the ΔΠ equation and blocks a below-cost distress sale.",
    reads: ["crop", "district", "quantity_kg", "farmer_offer_tk_per_kg", "optical_grade_cert", "syndicate_bypass_plan", "replan_reason"],
    writes: ["cold_storage_arbitrage_plan"],
    tools: ["query_cold_storage_quota", "get_chamber_telemetry", "calculate_dynamic_shelf_life", "get_historical_seasonal_curve", "reserve_collective_storage_slot"],
    files: ["backend/agents/coldchain_arbitrage_agent.py", "backend/guardrails/financial_circuit.py"],
  },
  {
    id: "climate_credit", agent: "climate_credit", short: "Climate", title: "Climate and credit agent",
    does: "Clears 72-hour storm and haor-flood risk from Sentinel-1 radar and rain, then scores the farmer 300 to 850 for instant credit.",
    reads: ["crop", "upazila", "quantity_kg", "optical_grade_cert", "syndicate_bypass_plan", "cold_storage_arbitrage_plan", "sar_backscatter_override_db"],
    writes: ["climate_credit_report"],
    tools: ["get_current_weather", "get_weather_by_datetime_range", "calculate_haor_flash_flood_risk", "compute_crop_vpd_stress", "trigger_early_harvest_window"],
    files: ["backend/agents/climate_credit_agent.py"],
  },
  {
    id: "supervisor_review", agent: "supervisor", short: "Review", title: "Supervisor review",
    does: "Checks that the plans agree. If the chosen chamber is out of band it sends the cold-chain agent back, at most twice.",
    reads: ["cold_storage_arbitrage_plan", "review_iterations", "errors"], writes: ["replan_reason", "review_iterations"],
    tools: [], files: ["backend/agents/supervisor.py"],
  },
  {
    id: "voice_synthesizer", agent: "voice_synthesizer", short: "Voice", title: "Bangla voice synthesizer",
    does: "Turns the decision into a spoken Bangla reply with SSML and asks the farmer for a yes before anything is booked.",
    reads: ["optical_grade_cert", "syndicate_bypass_plan", "cold_storage_arbitrage_plan", "climate_credit_report", "offline_mode"],
    writes: ["final_bangla_voice_response", "final_bangla_ssml", "requires_farmer_voice_approval"],
    tools: [], files: ["backend/agents/supervisor.py", "backend/edge_node/bangla_voice.py"],
  },
];

/** Node a trace event belongs to. Token compression records its DAM lookup under the supervisor's name. */
export function nodeOf(event: TraceEvent): string {
  if (event.agent_name === "supervisor" && event.tool_name === "get_daily_commodity_spread") return "token_compression";
  return PIPELINE.find((n) => n.agent === event.agent_name)?.id ?? event.agent_name;
}

export interface NodeTiming {
  events: number;
  mcpCalls: number;
  mcpMs: number;
  /** Time from the previous node's last event to this node's last event. */
  wallMs: number | null;
}

/** Per-node counts and timings for one session's trace events. */
export function timingsFor(events: TraceEvent[]): Record<string, NodeTiming> {
  const out: Record<string, NodeTiming> = {};
  const last: Record<string, number> = {};
  let first = Number.POSITIVE_INFINITY;
  for (const event of events) {
    const id = nodeOf(event);
    const t = Date.parse(event.timestamp);
    if (!Number.isNaN(t)) {
      first = Math.min(first, t);
      last[id] = Math.max(last[id] ?? t, t);
    }
    const row = (out[id] ??= { events: 0, mcpCalls: 0, mcpMs: 0, wallMs: null });
    row.events += 1;
    if (event.step_type === "MCP_CALL") {
      row.mcpCalls += 1;
      row.mcpMs += event.latency_ms;
    }
  }
  let previous = first;
  for (const node of PIPELINE) {
    if (last[node.id] === undefined || !Number.isFinite(previous)) continue;
    out[node.id].wallMs = Math.max(0, last[node.id] - previous);
    previous = last[node.id];
  }
  return out;
}
