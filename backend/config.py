"""Runtime configuration for the KrishiNexus OS backend.

Values are read once from the process environment (optionally populated from a
local ``.env`` file) and exposed as an immutable, validated ``Settings`` object.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

load_dotenv()

BDT = timezone(timedelta(hours=6), name="BDT")
"""Bangladesh Standard Time (UTC+06:00, no daylight saving)."""


def now_bdt() -> datetime:
    """Current wall-clock time in Bangladesh Standard Time."""
    return datetime.now(BDT)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings(BaseModel):
    """Validated, immutable backend settings."""

    model_config = ConfigDict(frozen=True)

    app_name: str = "KrishiNexus OS"
    app_version: str = "0.1.0"
    environment: str = "development"
    mcp_protocol_version: str = "2025-06-18"
    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    http_timeout_seconds: float = Field(default=8.0, gt=0, le=60)
    force_offline_weather: bool = False
    receipt_signing_key: str = Field(min_length=16)
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    ollama_host: str = "http://localhost:11434"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        environment=os.getenv("KNX_ENV", "development"),
        open_meteo_forecast_url=os.getenv(
            "KNX_OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast"
        ),
        http_timeout_seconds=float(os.getenv("KNX_HTTP_TIMEOUT_SECONDS", "8.0")),
        force_offline_weather=_env_bool("KNX_FORCE_OFFLINE_WEATHER", False),
        receipt_signing_key=os.getenv(
            "KNX_RECEIPT_SIGNING_KEY", "knx-dev-receipt-signing-key-change-me"
        ),
        cors_origins=_env_list("KNX_CORS_ORIGINS", ["*"]),
        ollama_host=os.getenv("KNX_OLLAMA_HOST", "http://localhost:11434"),
    )


settings = get_settings()


# ---------------------------------------------------------------------------
# Multi-LLM cheap-to-reasoning model router
# ---------------------------------------------------------------------------


class TaskType(StrEnum):
    VOICE_STATUS = "voice_status"
    PRICE_LOOKUP = "price_lookup"
    WEATHER_ALERT = "weather_alert"
    DIALECT_REWRITE = "dialect_rewrite"
    RAG_ANSWER = "rag_answer"
    ARBITRAGE_REASONING = "arbitrage_reasoning"
    CREDIT_SCORING = "credit_scoring"
    ORCHESTRATION = "orchestration"


class ModelTier(StrEnum):
    EDGE = "EDGE"
    CHEAP = "CHEAP"
    REASONING = "REASONING"
    FRONTIER = "FRONTIER"


class ModelSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    display_name: str
    provider: str
    model_id: str
    tier: ModelTier
    input_usd_per_mtok: float
    output_usd_per_mtok: float
    cached_input_multiplier: float = Field(description="Cache-read price as a fraction of the input price.")
    credential_env: tuple[str, ...] = Field(description="Any one of these env vars enables the model; empty = local.")


# List-price snapshot (USD per million tokens). Ollama models run locally at zero marginal cost.
MODEL_CATALOG: dict[str, ModelSpec] = {
    spec.key: spec
    for spec in (
        ModelSpec(key="claude-sonnet", display_name="Claude Sonnet 5.5", provider="anthropic",
                  model_id="claude-sonnet-5-5", tier=ModelTier.FRONTIER, input_usd_per_mtok=2.00,
                  output_usd_per_mtok=10.00, cached_input_multiplier=0.10,
                  credential_env=("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")),
        ModelSpec(key="deepseek-r1", display_name="DeepSeek-R1", provider="deepseek",
                  model_id="deepseek-reasoner", tier=ModelTier.REASONING, input_usd_per_mtok=0.55,
                  output_usd_per_mtok=2.19, cached_input_multiplier=0.25, credential_env=("DEEPSEEK_API_KEY",)),
        ModelSpec(key="gemini-flash", display_name="Gemini 2.5 Flash", provider="google",
                  model_id="gemini-2.5-flash", tier=ModelTier.CHEAP, input_usd_per_mtok=0.30,
                  output_usd_per_mtok=2.50, cached_input_multiplier=0.25,
                  credential_env=("GEMINI_API_KEY", "GOOGLE_API_KEY")),
        ModelSpec(key="ollama-qwen", display_name="Qwen-2.5-7B-Instruct (Ollama)", provider="ollama",
                  model_id="qwen2.5:7b-instruct", tier=ModelTier.EDGE, input_usd_per_mtok=0.0,
                  output_usd_per_mtok=0.0, cached_input_multiplier=1.0, credential_env=()),
        ModelSpec(key="ollama-llama", display_name="Llama-3.2-3B (Ollama)", provider="ollama",
                  model_id="llama3.2:3b", tier=ModelTier.EDGE, input_usd_per_mtok=0.0,
                  output_usd_per_mtok=0.0, cached_input_multiplier=1.0, credential_env=()),
    )
}

# Typical (input, output) tokens per task at complexity 0.5.
TASK_TOKEN_PROFILE: dict[TaskType, tuple[int, int]] = {
    TaskType.VOICE_STATUS: (250, 60),
    TaskType.PRICE_LOOKUP: (400, 120),
    TaskType.WEATHER_ALERT: (600, 150),
    TaskType.DIALECT_REWRITE: (300, 200),
    TaskType.RAG_ANSWER: (2_500, 500),
    TaskType.ARBITRAGE_REASONING: (3_500, 1_200),
    TaskType.CREDIT_SCORING: (3_000, 900),
    TaskType.ORCHESTRATION: (6_000, 1_500),
}
_SIMPLE_TASKS = {TaskType.VOICE_STATUS, TaskType.PRICE_LOOKUP, TaskType.WEATHER_ALERT, TaskType.DIALECT_REWRITE}


class RoutingDecision(BaseModel):
    task_type: TaskType
    complexity_score: float
    offline_mode: bool
    model_key: str
    display_name: str
    provider: str
    model_id: str
    tier: ModelTier
    available: bool
    reason: str
    fallback_chain: list[str]
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float


class ModelRouter:
    """Deterministic router: cheapest model that can handle the task, escalating with complexity."""

    def __init__(self, env: dict[str, str] | None = None) -> None:
        self._env = dict(os.environ) if env is None else env

    def is_available(self, spec: ModelSpec) -> bool:
        if not spec.credential_env:
            return True  # local Ollama at settings.ollama_host
        return any(self._env.get(name) for name in spec.credential_env)

    def _chain(self, task: TaskType, complexity: float, offline: bool) -> tuple[list[str], str]:
        if offline:
            if task is TaskType.VOICE_STATUS and complexity < 0.3:
                return ["ollama-llama", "ollama-qwen"], "offline edge node: smallest local model for short voice status"
            return ["ollama-qwen", "ollama-llama"], "offline edge node: local Qwen-2.5-7B"
        if task in _SIMPLE_TASKS:
            if complexity < 0.35:
                return ["ollama-qwen", "gemini-flash", "ollama-llama"], "simple status/voice query: free local model"
            return ["gemini-flash", "ollama-qwen", "claude-sonnet"], "simple query with some ambiguity: Gemini Flash (~$0.0001/query)"
        if task is TaskType.RAG_ANSWER:
            if complexity < 0.6:
                return ["gemini-flash", "claude-sonnet", "ollama-qwen"], "grounded answer over verified context: cheap tier"
            return ["claude-sonnet", "deepseek-r1", "gemini-flash", "ollama-qwen"], "multi-source synthesis: frontier tier"
        if task in (TaskType.ARBITRAGE_REASONING, TaskType.CREDIT_SCORING):
            if complexity < 0.85:
                return ["deepseek-r1", "claude-sonnet", "gemini-flash", "ollama-qwen"], "multi-variable numeric reasoning: DeepSeek-R1"
            return ["claude-sonnet", "deepseek-r1", "ollama-qwen"], "high-stakes multi-variable decision: Claude Sonnet"
        return ["claude-sonnet", "deepseek-r1", "gemini-flash", "ollama-qwen"], "multi-agent orchestration: Claude Sonnet"

    def route_query(self, task_type: TaskType, complexity_score: float, offline_mode: bool = False) -> RoutingDecision:
        complexity = min(1.0, max(0.0, complexity_score))
        chain, reason = self._chain(task_type, complexity, offline_mode)
        chosen = next((MODEL_CATALOG[k] for k in chain if self.is_available(MODEL_CATALOG[k])), MODEL_CATALOG[chain[0]])
        available = self.is_available(chosen)
        if chosen.key != chain[0]:
            reason += f"; {MODEL_CATALOG[chain[0]].display_name} has no credentials, fell back to {chosen.display_name}"
        base_in, base_out = TASK_TOKEN_PROFILE[task_type]
        scale = 0.6 + 0.8 * complexity
        tokens_in, tokens_out = round(base_in * scale), round(base_out * scale)
        cost = tokens_in / 1e6 * chosen.input_usd_per_mtok + tokens_out / 1e6 * chosen.output_usd_per_mtok
        return RoutingDecision(
            task_type=task_type,
            complexity_score=complexity,
            offline_mode=offline_mode,
            model_key=chosen.key,
            display_name=chosen.display_name,
            provider=chosen.provider,
            model_id=chosen.model_id,
            tier=chosen.tier,
            available=available,
            reason=reason,
            fallback_chain=chain,
            estimated_input_tokens=tokens_in,
            estimated_output_tokens=tokens_out,
            estimated_cost_usd=round(cost, 6),
        )


MODEL_ROUTER = ModelRouter()
