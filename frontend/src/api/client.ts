/**
 * Typed client for the KrishiNexus FastAPI backend (Steps 1-4) plus the live agent-trace WebSocket.
 *
 * Requests go through the Vite dev proxy (same origin), or to VITE_API_BASE when set. Every call made
 * through `withFallback` degrades to a deterministic demo snapshot when the backend is unreachable,
 * so the UI never renders blank; validation errors (HTTP 4xx) are surfaced, not masked.
 */

import {
  fallbackGrade,
  fallbackLocalModels,
  fallbackPools,
  fallbackQuota,
  fallbackTelemetry,
  fallbackVoice,
} from "./fallback";

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? "";

// ---------------------------------------------------------------------------
// Domain types (the subset of backend contracts the UI renders)
// ---------------------------------------------------------------------------

export type Crop = "Cardinal Potato" | "Diamant Potato" | "Green Chili" | "Brinjal" | "Boro Rice";
export type GradeableCrop = Exclude<Crop, "Boro Rice"> | "Mango" | "Banana";
export type DetectionClass = "uniform_A" | "minor_bruise" | "fungal_blight" | "undersized";
export type StepType = "THOUGHT" | "MCP_CALL" | "RAG_CRAG" | "GUARDRAIL" | "DECISION";
export type SamplePreset =
  | "high_grade_harvest"
  | "mixed_wholesale_lot"
  | "blight_affected_lot"
  | "undersized_processing_lot"
  | "field_sweep";

export interface BoundingBox {
  object_id: number;
  box: [number, number, number, number];
  class_label: DetectionClass;
  confidence: number;
  diameter_mm: number;
  defect_area_pct: number;
}

export interface GradingMetrics {
  sample_count: number;
  avg_diameter_mm: number;
  size_uniformity_pct: number;
  mechanical_bruising_pct: number;
  rot_blight_risk_pct: number;
  estimated_moisture_pct: number;
  undersized_pct: number;
}

export interface DigitalCertificate {
  cert_id: string;
  issued_at: string;
  grade: string;
  inspector_model_version: string;
  inference_backend: string;
  sha256_payload_hash: string;
  verification_hash: string;
}

export interface GradeCropResult {
  crop: GradeableCrop;
  district: string | null;
  source: string;
  inference_backend: string;
  inspector_model_version: string;
  frame_size: [number, number];
  video_frames_analyzed: number;
  bounding_boxes: BoundingBox[];
  metrics: GradingMetrics;
  assigned_grade: string;
  grade_letter: "A" | "B" | "C";
  grading_reasons: string[];
  price_premium_pct: number;
  premium_basis: string;
  digital_certificate: DigitalCertificate;
  latency_ms: number;
}

export interface TraceEvent {
  session_id: string;
  seq: number;
  timestamp: string;
  agent_name: string;
  step_type: StepType;
  tool_name: string | null;
  payload_summary: string;
  latency_ms: number;
  token_saved: number;
  data: Record<string, unknown>;
}

export interface PoolMatch {
  pool_id: string;
  upazila: string;
  current_kg: number;
  after_join_kg: number;
  capacity_kg: number;
  fill_pct_after_join: number;
  neighbor_farmers: number;
  will_trigger_dispatch: boolean;
}

export interface SyndicatePlan {
  farmer_offer_tk_per_kg: number | null;
  dam_grower_tk_per_kg: number;
  dam_wholesale_tk_per_kg: number;
  dam_retail_tk_per_kg: number;
  markup_pct: number;
  severity: string;
  aratdar_share_of_bepari_marketing_cost_pct: number;
  aratdar_take_tk_per_kg: number;
  aratdar_grading_spend_tk_per_kg: number;
  best_hub_name: string;
  best_hub_type: string;
  best_hub_district: string;
  pooled_transport_tk_per_kg: number;
  b2b_net_tk_per_kg: number;
  lot_value_b2b_tk: number;
  pool: PoolMatch | null;
  anomaly_alert: string;
}

export interface MicroCredit {
  credit_limit_bdt: number;
  annual_rate: number;
  tenor_months: number;
}

export interface CircuitBreaker {
  verdict: string;
  circuit_tripped: boolean;
  storage_branch_value_bdt: number;
  spot_branch_value_bdt: number;
  delta_pi_bdt: number;
  production_cost_floor_bdt: number;
  break_even_future_price_bdt: number;
  micro_credit: MicroCredit | null;
}

export interface StorageFacility {
  facility_id: string;
  name: string;
  road_distance_km: number;
  tariff_tk_per_kg: number;
  handling_fee_tk_per_kg: number;
  open_smallholder_quota_mt: number;
  chamber_temperature_f: number;
  chamber_rh_pct: number;
  chamber_in_optimal_band: boolean;
  power_source: string;
}

export interface ColdChainPlan {
  decision: "SELL_POOLED_B2B" | "STORE_AND_FINANCE" | "STORE" | "SELL_SPOT";
  horizon_days: number;
  expected_future_price_tk_per_kg: number | null;
  lambda_rot: number | null;
  facility: StorageFacility | null;
  circuit_breaker: CircuitBreaker | null;
  store_vs_b2b_delta_tk: number | null;
  b2b_net_tk_per_kg: number;
  distress_sale_blocked: boolean;
  block_reason: string | null;
  reservation: { receipt_id: string | null; status: string; facility_name: string } | null;
  projected_net_tk_per_kg: number;
  math_trace: string[];
}

export interface ScoreComponent {
  name: string;
  points: number;
  max_points: number;
  evidence: string;
}

export interface ClimateCreditReport {
  temperature_c: number;
  relative_humidity_pct: number;
  weather_source: string;
  rain_next_72h_mm: number;
  storm_warnings: string[];
  flood_applicable: boolean;
  flood_alert_level: string | null;
  flood_breach_probability_pct: number | null;
  sar_backscatter_db: number | null;
  seventy_two_hour_clearance: boolean;
  fungal_risk_pct: number;
  credit_score: number;
  score_band: string;
  score_components: ScoreComponent[];
  loan_eligible: boolean;
  loan_amount_tk: number;
  annual_rate_pct: number;
  tenor_months: number;
  collateral: string;
  lender_model: string;
}

export interface QualityCertificate {
  certificate_id: string;
  grade: string;
  market_grade: "A" | "B" | "C";
  grade_score: number;
  sha256_digest: string;
  detections: number;
  edge_certificate_id: string | null;
  metrics: { size_uniformity_pct: number; bruising_pct: number; rot_blight_risk_pct: number; moisture_pct: number };
}

export interface AgentState {
  session_id: string;
  farmer_id: string;
  scrubbed_query: string;
  district: string;
  upazila: string;
  crop: Crop;
  quantity_kg: number;
  farmer_offer_tk_per_kg: number | null;
  compression_report: { original_tokens?: number; compressed_tokens?: number; reduction_factor?: number };
  rag_crag_result: { verdict: string; confidence: number; intents: string[]; dialect: string } | null;
  optical_grade_cert: QualityCertificate | null;
  syndicate_bypass_plan: SyndicatePlan | null;
  cold_storage_arbitrage_plan: ColdChainPlan | null;
  climate_credit_report: ClimateCreditReport | null;
  final_bangla_voice_response: string;
  requires_farmer_voice_approval: boolean;
  node_path: string[];
  errors: string[];
  trace_events: TraceEvent[];
}

export interface OrchestrateResponse {
  session_id: string;
  status: string;
  graph_path: string[];
  latency_ms: number;
  trace_event_count: number;
  state: AgentState;
}

export interface VoiceEntities {
  crop: Crop | null;
  crop_local_term: string | null;
  quantity_kg: number | null;
  district: string | null;
  upazila: string | null;
  offered_faria_price_bdt: number | null;
  middleman_role: string | null;
  intent: string;
}

export interface VoiceInteractResponse {
  status: "COMPLETED" | "COMPLETED_WITH_ERRORS" | "NEEDS_CLARIFICATION";
  transcription: {
    dialect: string;
    raw_transcript: string;
    scrubbed_transcript: string;
    normalized_text: string;
    pii_entities: string[];
    entities: VoiceEntities;
  };
  grading: GradeCropResult | null;
  orchestration: OrchestrateResponse | null;
  spoken_response_bn: string;
  voice: { ssml: string; pronunciation_guide: { term: string; ipa: string; romanized: string }[]; estimated_duration_s: number };
  follow_up_question_bn: string | null;
}

export interface PoolLot {
  farmer_id: string;
  weight_kg: number;
  grade: "A" | "B" | "C";
  distance_km: number;
  source: "seed" | "farmer";
}

export interface PoolView {
  pool_id: string;
  district: string;
  upazila: string;
  union: string;
  crop: Crop;
  status: "OPEN" | "DISPATCHED";
  capacity_kg: number;
  loaded_kg: number;
  remaining_kg: number;
  fill_pct: number;
  smallholders: number;
  roster_size: number;
  union_radius_km: number;
  dispatch: {
    truck_booking_id: string;
    buyer_name: string;
    buyer_type: string;
    contract_price_tk_per_kg: number;
    contract_value_tk: number;
    escrow_id: string;
    escrow_amount_tk: number;
    eta_hours: number;
  } | null;
  lots: PoolLot[];
}

export interface JoinPoolResult {
  accepted: boolean;
  idempotent_replay: boolean;
  accepted_kg: number;
  message: string;
  pool: PoolView;
}

export interface ChamberTelemetry {
  facility_id: string;
  facility_name: string;
  chamber_id: string;
  stored_crop: string;
  stored_tons: number;
  temperature_c: number;
  temperature_f: number;
  relative_humidity_pct: number;
  co2_ppm: number;
  power_source: "GRID" | "DIESEL_GENERATOR" | "OUTAGE";
  rot_risk_pct: number;
  alerts: string[];
  simulated_anomaly_active: boolean;
}

export interface QuotaFacility {
  facility_id: string;
  name: string;
  total_capacity_mt: number;
  trader_quota_mt: number;
  owner_quota_mt: number;
  farmer_quota_mt: number;
  farmer_quota_booked_mt: number;
  open_smallholder_quota_mt: number;
  tariff_tk_per_kg: number;
  power_status: string;
}

export interface QuotaResult {
  district: string;
  facilities: QuotaFacility[];
  total_open_smallholder_quota_mt: number;
}

export interface SimulateAnomalyResponse {
  anomaly: { anomaly_id: string; anomaly_type: string; target: string };
  message: string;
  impact_tool: string;
  impact_preview: Record<string, unknown>;
}

export interface SarFloodReport {
  upazilas_checked: number;
  rows: { upazila: string; district: string; breach_probability_pct: number; alert_level: string; sar_backscatter_db: number }[];
  voice_alerts: { upazila: string; alert_level: string; recipients: number; message_bn: string }[];
  early_harvest_dispatches: string[];
}

export interface McpTool {
  server: string;
  name: string;
  title: string;
  description: string;
  inputSchema: Record<string, unknown>;
  outputSchema: Record<string, unknown>;
}

export interface LocalModelsReport {
  runtimes: { runtime: string; endpoint: string; reachable: boolean; models: string[] }[];
  models: {
    key: string;
    display_name: string;
    ollama_tag: string;
    quantization: string;
    role: string;
    lora_adapter: string | null;
    telemetry: { vram_mb: number; decode_tokens_per_s: number; fits_on_accelerator: boolean };
  }[];
  lora_adapter: { name: string; status: string; rank: number; dataset: { total_examples: number; by_category: Record<string, number> } };
}

// ---------------------------------------------------------------------------
// Transport
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
  }
}

export interface Result<T> {
  data: T;
  live: boolean;
  error?: string;
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = 120_000): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      detail = `${response.status} ${response.statusText}`;
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

const post = <T>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) });

/** Run a live call; on network/5xx failure return the deterministic fallback instead. */
export async function withFallback<T>(live: () => Promise<T>, fallback: () => T): Promise<Result<T>> {
  try {
    return { data: await live(), live: true };
  } catch (error) {
    if (error instanceof ApiError && error.status < 500) throw error;
    return { data: fallback(), live: false, error: error instanceof Error ? error.message : String(error) };
  }
}

interface JsonRpcReply<T> {
  result?: { structuredContent?: T; isError?: boolean; content?: { text: string }[] };
  error?: { code: number; message: string; data?: unknown };
}

export async function mcpCall<T>(name: string, args: Record<string, unknown>): Promise<T> {
  const reply = await post<JsonRpcReply<T>>("/mcp/call", {
    jsonrpc: "2.0",
    id: Date.now(),
    method: "tools/call",
    params: { name, arguments: args },
  });
  if (reply.error) throw new ApiError(400, `${reply.error.message}: ${JSON.stringify(reply.error.data ?? "")}`);
  if (!reply.result || reply.result.isError || !reply.result.structuredContent) {
    throw new ApiError(422, reply.result?.content?.[0]?.text ?? "MCP tool returned no structured content");
  }
  return reply.result.structuredContent;
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

export interface VoiceInteractBody {
  preset_id?: string;
  text?: string;
  district?: string;
  upazila?: string;
  farmer_id?: string;
  grade_sample_preset?: SamplePreset;
  offline_mode?: boolean;
  session_id?: string;
}

export const api = {
  health: () => request<{ status: string; tools: number; active_anomalies: number }>("/health", undefined, 4_000),

  voiceInteract: (body: VoiceInteractBody) =>
    withFallback(() => post<VoiceInteractResponse>("/edge/voice-interact", body), () => fallbackVoice(body)),

  gradeCrop: (crop: GradeableCrop, preset: SamplePreset, district: string, farmerId?: string) =>
    withFallback(
      () => post<GradeCropResult>("/edge/grade-crop", { crop, sample_preset: preset, district, farmer_id: farmerId }),
      () => fallbackGrade(crop, preset),
    ),

  orchestrate: (body: Record<string, unknown>) => post<OrchestrateResponse>("/agents/orchestrate", body),

  truckPools: () => withFallback(() => request<PoolView[]>("/automation/truck-pools"), fallbackPools),

  joinPool: (body: { cluster_id: string; farmer_id: string; crop: Crop; weight_kg: number; grade: string }) =>
    post<JoinPoolResult>("/automation/truck-pools/join", body),

  resetPools: () => post<PoolView[]>("/automation/truck-pools/reset", {}),

  chamberTelemetry: (facilityId: string, chamberId: string) =>
    withFallback(
      () => mcpCall<ChamberTelemetry>("get_chamber_telemetry", { facility_id: facilityId, chamber_id: chamberId }),
      () => fallbackTelemetry(facilityId, chamberId),
    ),

  coldStorageQuota: (district: string) =>
    withFallback(
      () => mcpCall<QuotaResult>("query_cold_storage_quota", { district, radius_km: 60, tons_needed: 1 }),
      () => fallbackQuota(district),
    ),

  /** Facility-wide cut (all chambers) so coldchain-iot-mcp re-routes smallholder allocations elsewhere. */
  simulatePowerCut: (facilityId: string) =>
    post<SimulateAnomalyResponse>("/mcp/simulate-anomaly", {
      anomaly_type: "cold_chamber_power_cut",
      facility_id: facilityId,
      generator_failed: true,
      elapsed_minutes: 300,
    }),

  simulateFlashFlood: (upazila = "Tahirpur") =>
    post<SimulateAnomalyResponse>("/mcp/simulate-anomaly", {
      anomaly_type: "haor_flash_flood",
      upazila,
      upstream_rainfall_72h_mm: 320,
      sar_water_backscatter_db: -19.5,
    }),

  clearAnomalies: () => request<{ cleared: number }>("/mcp/anomalies", { method: "DELETE" }),

  sarFloodCheck: () => post<SarFloodReport>("/automation/n8n/hourly-sar-flood-check", {}),

  guardrailsVerify: (body: Record<string, unknown>) => post<Record<string, unknown>>("/guardrails/verify", body),

  mcpTools: () => request<{ count: number; servers: string[]; tools: McpTool[] }>("/mcp/tools"),

  localModels: () => withFallback(() => request<LocalModelsReport>("/edge/local-models"), fallbackLocalModels),

  mcpServers: () => request<McpServerInfo[]>("/mcp/servers"),
  compress: (raw_context: string) => post<CompressReport>("/optimization/compress", { raw_context }),
  ragQuery: (query: string, district?: string, crop?: Crop) => post<RagQueryReport>("/rag/query", { query, district, crop }),
  promptsRegistry: () => request<PromptRegistryListing>("/prompts/registry?include_xml=false"),
  evalMetrics: (refresh = false) => request<RagasReport>(`/evals/metrics${refresh ? "?refresh=true" : ""}`),
  runRegression: (sampleSize: number) => post<RegressionReport>("/evals/run-regression", { sample_size: sampleSize }),
};

/** Raw JSON-RPC 2.0 round trip for the MCP inspector: returns HTTP status, latency and the untouched body. */
export async function rawJsonRpc(payload: unknown): Promise<{ status: number; latencyMs: number; body: unknown }> {
  const started = performance.now();
  const response = await fetch(`${API_BASE}/mcp/call`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(60_000),
  });
  const text = await response.text();
  let body: unknown = text;
  try {
    body = JSON.parse(text);
  } catch {
    body = text;
  }
  return { status: response.status, latencyMs: performance.now() - started, body };
}

// ---------------------------------------------------------------------------
// Step 6 report types
// ---------------------------------------------------------------------------

export interface McpServerInfo {
  name: string;
  title: string;
  version: string;
  description: string;
  protocol_version: string;
  transports: string[];
  endpoint: string;
  stdio_command: string;
  tool_count: number;
  tools: string[];
}

export interface CompressReport {
  compression: {
    method: string;
    original_tokens: number;
    compressed_tokens: number;
    reduction_factor: number;
    all_numbers_preserved: boolean;
    compressed_text: string;
    savings: { model_id: string; saved_usd_per_1k_calls: number }[];
  };
  deduplication: { input_chunks: number; kept_chunks: number };
  cache: { static_prefix_tokens: number; cache_eligible: Record<string, boolean> };
  routing: { display_name: string; reason: string };
}

export interface RagQueryReport {
  rewrite: { detected_dialect: string; formal_query: string; intents: string[] };
  retrieval: { chunk_id: string; title: string; bm25_rank: number | null; vector_rank: number | null; rerank_score: number }[];
  graph: { paths: { narrative: string }[] } | null;
  crag: { verdict: string; confidence: number; corrective_triggered: boolean };
  answer_summary: string;
  context_tokens: Record<string, number>;
}

export interface PromptRegistryListing {
  agents: {
    agent: string;
    title: string;
    active_version: string;
    optimization: { baseline_score: number; optimized_score: number; trials_evaluated: number; diff: string[]; method: string };
  }[];
}

export interface MetricValue {
  name: string;
  value: number;
  target: number;
  meets_target: boolean;
  method: string;
  sample_size: number;
}

export interface RagasReport {
  generated_at: string;
  duration_ms: number;
  metrics: MetricValue[];
  pii_redaction_precision: number;
  per_question: { question: string; gold_docs: string[]; retrieved_docs: string[]; context_precision: number; faithfulness: number }[];
  notes: string[];
}

export interface RegressionCase {
  case_id: string;
  category: string;
  title: string;
  inputs: Record<string, unknown>;
  expected: Record<string, unknown>;
  actual: Record<string, unknown>;
  passed: boolean;
  latency_ms: number;
  proof: string;
  judge: { judge: string; criteria: Record<string, boolean>; score: number } | null;
}

export interface RegressionReport {
  total_cases: number;
  passed: number;
  failed: number;
  pass_rate_pct: number;
  duration_ms: number;
  seed: number;
  categories: { category: string; title: string; total: number; passed: number; pass_rate_pct: number; avg_latency_ms: number }[];
  cases: RegressionCase[];
}

// ---------------------------------------------------------------------------
// Live agent trace WebSocket
// ---------------------------------------------------------------------------

export type TraceConnection = "connecting" | "open" | "closed";

export function connectAgentTrace(onEvents: (events: TraceEvent[]) => void, onStatus: (status: TraceConnection) => void): () => void {
  let socket: WebSocket | null = null;
  let retry = 0;
  let stopped = false;
  let ping: number | undefined;
  let reconnect: number | undefined;

  const open = () => {
    if (stopped) return;
    onStatus("connecting");
    const base = API_BASE ? API_BASE.replace(/^http/, "ws") : `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}`;
    socket = new WebSocket(`${base}/ws/agent-trace`);
    socket.onopen = () => {
      retry = 0;
      onStatus("open");
      ping = window.setInterval(() => socket?.readyState === WebSocket.OPEN && socket.send("ping"), 25_000);
    };
    socket.onmessage = (message) => {
      const payload = JSON.parse(String(message.data)) as { type: string; event?: TraceEvent; replay?: TraceEvent[] };
      if (payload.type === "trace" && payload.event) onEvents([payload.event]);
      if (payload.type === "hello" && payload.replay?.length) onEvents(payload.replay);
    };
    socket.onclose = () => {
      window.clearInterval(ping);
      onStatus("closed");
      if (!stopped) reconnect = window.setTimeout(open, Math.min(10_000, 1_000 * 2 ** retry++));
    };
    socket.onerror = () => socket?.close();
  };

  open();
  return () => {
    stopped = true;
    window.clearInterval(ping);
    window.clearTimeout(reconnect);
    socket?.close();
  };
}
