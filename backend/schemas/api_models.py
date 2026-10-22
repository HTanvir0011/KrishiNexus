"""Request / response contracts for the Step 2 REST endpoints (RAG, optimisation, guardrails)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from config import RoutingDecision
from guardrails.financial_circuit import ArbitrageCheckResult, DosageCheckInput, DosageCheckResult, ProposedAction
from guardrails.pii_scrubber import ScrubResult
from optimization.token_compressor import CachedMessages, CompressionResult, DedupResult
from schemas.mcp_models import CropField

DEFAULT_SYSTEM_PROMPT = (
    "You are KrishiNexus, an agricultural advisor for Bangladeshi smallholders. Answer in the farmer's "
    "language, cite the verified context, quote prices in Tk/kg, and never recommend banned chemicals."
)


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RagQueryRequest(_Request):
    query: str = Field(min_length=2, max_length=2_000, description="Farmer question in Bangla, dialect, Banglish or English.")
    district: str | None = Field(default=None, max_length=60)
    crop: CropField | None = None
    top_k: int = Field(default=5, ge=1, le=10)


class GraphTraverseRequest(_Request):
    start: str = Field(min_length=2, max_length=60, description="Upazila or district, e.g. 'Tongibari', 'Bogura'.")
    crop: CropField | None = None
    max_paths: int = Field(default=5, ge=1, le=20)


class CompressRequest(_Request):
    raw_context: str = Field(min_length=1, max_length=500_000, description="Prose, DAM price table or weather JSON.")
    target_ratio: float = Field(default=0.25, ge=0.05, le=1.0)
    chunks: list[str] = Field(default_factory=list, description="RAG passages to dedupe; defaults to the context's sentences.")
    similarity_threshold: float = Field(default=0.88, ge=0.5, le=0.999)
    system_prompt: str = Field(default=DEFAULT_SYSTEM_PROMPT, max_length=20_000)
    user_query: str = Field(default="এই সপ্তাহে আলু বিক্রি করব নাকি হিমাগারে রাখব?", max_length=2_000)


class CompressResponse(BaseModel):
    compression: CompressionResult
    deduplication: DedupResult
    cache: CachedMessages
    routing: RoutingDecision


class GuardrailVerifyRequest(_Request):
    raw_text: str | None = Field(default=None, max_length=10_000, description="Text to PII-scrub.")
    crop: CropField | None = None
    quantity_kg: float | None = Field(default=None, gt=0, le=2_000_000)
    spot_price_bdt: float | None = Field(default=None, ge=0)
    expected_future_price_bdt: float | None = Field(default=None, ge=0)
    storage_tariff_bdt: float | None = Field(default=None, ge=0)
    handling_cost_bdt: float | None = Field(default=None, ge=0)
    lambda_rot: float | None = Field(default=None, ge=0, le=0.5)
    transport_to_storage_bdt: float = Field(default=0.0, ge=0)
    transport_to_market_bdt: float = Field(default=0.0, ge=0)
    district: str | None = Field(default=None, max_length=60)
    holding_months: int = Field(default=6, ge=1, le=10)
    proposed_action: ProposedAction = ProposedAction.SELL_SPOT
    pesticide: DosageCheckInput | None = None


class GuardrailVerifyResponse(BaseModel):
    overall_verdict: Literal["BLOCKED", "PASS"]
    tripped: list[str]
    pii: ScrubResult | None
    arbitrage: ArbitrageCheckResult | None
    arbitrage_missing_fields: list[str]
    agronomic: DosageCheckResult | None
