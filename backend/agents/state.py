"""Strictly typed shared state for the LangGraph supervisor and its four specialist agents.

``KrishiAgentState`` is a Pydantic v2 model used directly as the LangGraph state schema.
``trace_events`` and ``errors`` carry ``operator.add`` reducers so every node appends to them
instead of overwriting; all other fields are last-writer-wins.
"""

from __future__ import annotations

import operator
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from config import now_bdt
from guardrails.financial_circuit import ArbitrageCheckResult
from schemas.mcp_models import (
    AnomalySeverity,
    Crop,
    FloodAlertLevel,
    Grade,
    HubType,
    ReserveCollectiveStorageSlotOutput,
    RiskLevel,
)


class StepType(StrEnum):
    THOUGHT = "THOUGHT"
    MCP_CALL = "MCP_CALL"
    RAG_CRAG = "RAG_CRAG"
    GUARDRAIL = "GUARDRAIL"
    DECISION = "DECISION"


class AgentTraceEvent(BaseModel):
    session_id: str
    seq: int = Field(ge=0, description="Per-session ordering index.")
    timestamp: datetime = Field(default_factory=now_bdt)
    agent_name: str
    step_type: StepType
    tool_name: str | None = None
    payload_summary: str
    latency_ms: float = Field(default=0.0, ge=0)
    token_saved: int = Field(default=0, ge=0)
    data: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Agent 1 — vision & grading
# ---------------------------------------------------------------------------


class QualityGrade(StrEnum):
    A = "Grade-A Export/Supermarket"
    B = "Grade-B Wholesale"
    C = "Grade-C Processing"


class HarvestMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    size_uniformity_pct: float = Field(ge=0, le=100)
    bruising_pct: float = Field(ge=0, le=100)
    rot_blight_risk_pct: float = Field(ge=0, le=100)
    moisture_pct: float = Field(ge=0, le=100, description="Tuber/fruit moisture or paddy grain moisture content.")
    source: Literal["farmer_supplied", "edge_optical_grader"] = "farmer_supplied"
    edge_certificate_id: str | None = Field(default=None, description="Optical grader certificate these metrics came from.")


class DigitalQualityCertificate(BaseModel):
    certificate_id: str
    farmer_id: str
    crop: Crop
    lot_kg: float
    metrics: HarvestMetrics
    grade: QualityGrade
    market_grade: Grade
    grade_score: float = Field(ge=0, le=100)
    grading_reasons: list[str]
    storage_protocol: list[str] = Field(description="Verified BARI/BAU post-harvest rules with citations.")
    packaging_recommendation: str
    edge_certificate_id: str | None = Field(description="Optical grader certificate backing these metrics, if any.")
    edge_inference_backend: str | None
    detections: int = Field(ge=0, description="Objects detected by the optical grader (0 for farmer-supplied metrics).")
    issued_at: datetime
    valid_until: date
    prompt_version: str
    sha256_digest: str
    hmac_signature: str


# ---------------------------------------------------------------------------
# Agent 2 — syndicate bypass & truck pooling
# ---------------------------------------------------------------------------


class TierCapture(BaseModel):
    tier: str
    gross_margin_tk_per_kg: float
    share_of_total_margin_pct: float


class PoolMatch(BaseModel):
    pool_id: str
    upazila: str
    union_radius_km: float
    current_kg: float
    after_join_kg: float
    capacity_kg: float
    fill_pct_after_join: float
    neighbor_farmers: int
    will_trigger_dispatch: bool
    status: str


class SyndicateBypassPlan(BaseModel):
    farmer_offer_tk_per_kg: float | None
    dam_grower_tk_per_kg: float
    dam_wholesale_tk_per_kg: float
    dam_retail_tk_per_kg: float
    markup_pct: float
    severity: AnomalySeverity
    anomaly_threshold_pct: float
    is_anomaly: bool
    aratdar_share_of_bepari_marketing_cost_pct: float
    aratdar_take_tk_per_kg: float
    aratdar_grading_spend_tk_per_kg: float
    tier_breakdown: list[TierCapture]
    best_hub_id: str
    best_hub_name: str
    best_hub_type: HubType
    best_hub_district: str
    pooled_transport_tk_per_kg: float
    b2b_net_tk_per_kg: float
    offer_shortfall_tk_per_kg: float | None
    lot_value_offer_tk: float | None
    lot_value_b2b_tk: float
    pool: PoolMatch | None
    anomaly_alert: str
    prompt_version: str


# ---------------------------------------------------------------------------
# Agent 3 — cold-chain arbitrage
# ---------------------------------------------------------------------------


class StorageFacilityChoice(BaseModel):
    facility_id: str
    name: str
    road_distance_km: float
    tariff_tk_per_kg: float
    handling_fee_tk_per_kg: float
    open_smallholder_quota_mt: float
    chamber_temperature_f: float
    chamber_rh_pct: float
    chamber_in_optimal_band: bool
    power_source: str


class ColdChainArbitragePlan(BaseModel):
    decision: Literal["SELL_POOLED_B2B", "STORE_AND_FINANCE", "STORE", "SELL_SPOT"]
    horizon_days: int
    release_date: date | None
    expected_future_price_tk_per_kg: float | None
    best_release_month: int
    lambda_rot: float | None
    facility: StorageFacilityChoice | None
    circuit_breaker: ArbitrageCheckResult | None = Field(description="None when the crop is not cold-storable in BCSA facilities.")
    store_vs_b2b_delta_tk: float | None = Field(description="Storage branch value minus pooled B2B sale value now.")
    b2b_net_tk_per_kg: float
    distress_sale_blocked: bool
    block_reason: str | None
    reservation: ReserveCollectiveStorageSlotOutput | None
    projected_net_tk_per_kg: float
    quota_capture_note: str
    math_trace: list[str]
    prompt_version: str


# ---------------------------------------------------------------------------
# Agent 4 — climate shield & credit
# ---------------------------------------------------------------------------


class ScoreComponent(BaseModel):
    name: str
    points: float
    max_points: float
    evidence: str


class ClimateCreditReport(BaseModel):
    temperature_c: float
    relative_humidity_pct: float
    weather_source: str
    rain_next_72h_mm: float
    storm_warnings: list[str]
    flood_applicable: bool
    flood_alert_level: FloodAlertLevel | None
    flood_breach_probability_pct: float | None
    boro_loss_benchmark_pct: float | None
    sar_backscatter_db: float | None
    sar_source: str | None
    seventy_two_hour_clearance: bool
    fungal_risk_pct: float
    fungal_risk_level: RiskLevel
    pathogen: str
    early_harvest_dispatch_id: str | None
    credit_score: int = Field(ge=300, le=850)
    score_band: str
    score_components: list[ScoreComponent]
    loan_eligible: bool
    loan_amount_tk: float
    annual_rate_pct: float
    tenor_months: int
    collateral: str
    lender_model: str
    prompt_version: str


# ---------------------------------------------------------------------------
# Retrieval summary and the graph state
# ---------------------------------------------------------------------------


class RagSummary(BaseModel):
    verdict: str
    confidence: float
    corrective_triggered: bool
    intents: list[str]
    dialect: str
    top_chunks: list[str]
    graph_paths: list[str]
    answer_summary: str
    tokens_saved: int


class KrishiAgentState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=False)

    session_id: str
    farmer_id: str
    raw_query_bangla: str
    scrubbed_query: str = ""
    pii_vault_map: dict[str, str] = Field(default_factory=dict, description="vault_id plus masked previews; never raw PII.")
    district: str
    upazila: str
    crop: Crop
    quantity_kg: float = Field(gt=0)
    farmer_offer_tk_per_kg: float | None = None
    harvest_metrics_input: HarvestMetrics | None = None
    sar_backscatter_override_db: float | None = None
    compression_report: dict[str, Any] = Field(default_factory=dict)
    rag_crag_result: RagSummary | None = None
    optical_grade_cert: DigitalQualityCertificate | None = None
    syndicate_bypass_plan: SyndicateBypassPlan | None = None
    cold_storage_arbitrage_plan: ColdChainArbitragePlan | None = None
    climate_credit_report: ClimateCreditReport | None = None
    final_bangla_voice_response: str = ""
    final_bangla_ssml: str = ""
    offline_mode: bool = False
    requires_farmer_voice_approval: bool = True
    review_iterations: int = 0
    replan_reason: str | None = None
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    node_path: Annotated[list[str], operator.add] = Field(default_factory=list)
    errors: Annotated[list[str], operator.add] = Field(default_factory=list)
    trace_events: Annotated[list[AgentTraceEvent], operator.add] = Field(default_factory=list)
